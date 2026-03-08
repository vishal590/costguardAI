"""
Action Executor for performing automated actions on resources.

Actions by service:
- EC2: Stop instance (not terminate)
- RDS: Stop database
- Lambda: Set concurrency to 0
- EBS: Snapshot then delete (if unattached)
- DynamoDB: Switch to on-demand mode
- NAT Gateway: Delete (with documentation)
"""

from typing import Dict, Any, Optional
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Execute automated actions on resources."""
    
    def __init__(self, aws_clients: Dict[str, Any], audit_logger, pricing_manager=None):
        """
        Initialize action executor.
        
        Args:
            aws_clients: Dict of boto3 clients by service name
            audit_logger: Logger for audit trail
            pricing_manager: Optional PricingManager instance for savings estimation
        """
        self.clients = aws_clients
        self.audit_logger = audit_logger
        self.pricing_manager = pricing_manager
    
    def execute_action(self, resource, action: str) -> Any:
        """
        Execute action on resource.
        
        Args:
            resource: Resource object
            action: Action to perform
            
        Returns:
            ActionResult object
        """
        from ..utils.types import ActionResult
        
        logger.info(f"Executing {action} on {resource.resource_id}")
        
        # Get pre-action state
        pre_action_state = self._get_resource_state(resource)
        
        try:
            # Execute service-specific action
            if resource.service == 'ec2':
                success = self.stop_ec2_instance(resource.resource_id)
            elif resource.service == 'rds':
                success = self.stop_rds_instance(resource.resource_id)
            elif resource.service == 'lambda':
                success = self.limit_lambda_concurrency(resource.resource_id, 0)
            elif resource.service == 'ebs':
                success = self._snapshot_and_delete_volume(resource.resource_id)
            elif resource.service == 'dynamodb':
                success = self._switch_to_ondemand(resource.resource_id)
            elif resource.service == 'nat_gateway':
                success = self._delete_nat_gateway(resource.resource_id)
            else:
                logger.warning(f"No action handler for service: {resource.service}")
                success = False
            
            # Get post-action state
            post_action_state = self._get_resource_state(resource)
            
            # Estimate savings
            estimated_savings = self._estimate_savings(resource)
            
            result = ActionResult(
                resource_id=resource.resource_id,
                action=action,
                success=success,
                error_message=None,
                pre_action_state=pre_action_state,
                post_action_state=post_action_state,
                estimated_savings=estimated_savings,
                timestamp=datetime.now(UTC).isoformat()
            )
            
            # Log to audit trail
            self.audit_logger.log_action(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Action failed for {resource.resource_id}: {e}")
            
            result = ActionResult(
                resource_id=resource.resource_id,
                action=action,
                success=False,
                error_message=str(e),
                pre_action_state=pre_action_state,
                post_action_state={},
                estimated_savings=0.0,
                timestamp=datetime.now(UTC).isoformat()
            )
            
            self.audit_logger.log_action(result)
            return result
    
    def stop_ec2_instance(self, instance_id: str) -> bool:
        """
        Stop EC2 instance.
        
        Args:
            instance_id: EC2 instance ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            ec2 = self.clients.get('ec2')
            if not ec2:
                return False
            
            response = ec2.stop_instances(InstanceIds=[instance_id])
            logger.info(f"Stopped EC2 instance: {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop EC2 instance {instance_id}: {e}")
            return False
    
    def stop_rds_instance(self, db_identifier: str) -> bool:
        """
        Stop RDS database.
        
        Args:
            db_identifier: RDS database identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            rds = self.clients.get('rds')
            if not rds:
                return False
            
            response = rds.stop_db_instance(DBInstanceIdentifier=db_identifier)
            logger.info(f"Stopped RDS instance: {db_identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop RDS instance {db_identifier}: {e}")
            return False
    
    def limit_lambda_concurrency(self, function_name: str, limit: int) -> bool:
        """
        Set Lambda concurrency limit.
        
        Args:
            function_name: Lambda function name
            limit: Concurrency limit (0 to disable)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            lambda_client = self.clients.get('lambda')
            if not lambda_client:
                return False
            
            response = lambda_client.put_function_concurrency(
                FunctionName=function_name,
                ReservedConcurrentExecutions=limit
            )
            logger.info(f"Set Lambda concurrency to {limit} for: {function_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set Lambda concurrency for {function_name}: {e}")
            return False
    
    def _snapshot_and_delete_volume(self, volume_id: str) -> bool:
        """Snapshot EBS volume then delete it."""
        try:
            ec2 = self.clients.get('ec2')
            if not ec2:
                return False
            
            # Create snapshot
            snapshot = ec2.create_snapshot(
                VolumeId=volume_id,
                Description=f"Automated snapshot before deletion - {datetime.now(UTC).isoformat()}"
            )
            logger.info(f"Created snapshot {snapshot['SnapshotId']} for volume {volume_id}")
            
            # Delete volume
            ec2.delete_volume(VolumeId=volume_id)
            logger.info(f"Deleted EBS volume: {volume_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to snapshot/delete volume {volume_id}: {e}")
            return False
    
    def _switch_to_ondemand(self, table_name: str) -> bool:
        """Switch DynamoDB table to on-demand billing mode."""
        try:
            dynamodb = self.clients.get('dynamodb')
            if not dynamodb:
                return False
            
            response = dynamodb.update_table(
                TableName=table_name,
                BillingMode='PAY_PER_REQUEST'
            )
            logger.info(f"Switched DynamoDB table to on-demand: {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch DynamoDB table {table_name}: {e}")
            return False
    
    def _delete_nat_gateway(self, nat_gateway_id: str) -> bool:
        """Delete NAT Gateway after creating documentation."""
        try:
            ec2 = self.clients.get('ec2')
            if not ec2:
                return False
            
            # Get NAT Gateway details for documentation
            response = ec2.describe_nat_gateways(NatGatewayIds=[nat_gateway_id])
            nat_gateway = response['NatGateways'][0]
            
            # Log details for documentation
            logger.info(f"NAT Gateway details before deletion: {nat_gateway}")
            
            # Delete NAT Gateway
            ec2.delete_nat_gateway(NatGatewayId=nat_gateway_id)
            logger.info(f"Deleted NAT Gateway: {nat_gateway_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete NAT Gateway {nat_gateway_id}: {e}")
            return False
    
    def _get_resource_state(self, resource) -> Dict[str, Any]:
        """Get current state of resource."""
        return {
            'resource_id': resource.resource_id,
            'state': resource.state,
            'service': resource.service,
            'timestamp': datetime.now(UTC).isoformat()
        }
    
    def _estimate_savings(self, resource) -> float:
        """
        Estimate monthly savings from stopping resource using real pricing data.
        
        Args:
            resource: Resource object with service, region, resource_id
            
        Returns:
            Estimated monthly savings in USD
        """
        try:
            # Initialize PricingManager if not provided
            if not self.pricing_manager:
                from ..services.pricing_manager import PricingManager
                self.pricing_manager = PricingManager(region=resource.region)
            
            # Service-specific pricing logic
            if resource.service == 'ec2':
                return self._estimate_ec2_savings(resource)
            elif resource.service == 'rds':
                return self._estimate_rds_savings(resource)
            elif resource.service == 'lambda':
                return self._estimate_lambda_savings(resource)
            elif resource.service == 'dynamodb':
                return self._estimate_dynamodb_savings(resource)
            elif resource.service == 'ebs':
                return self._estimate_ebs_savings(resource)
            elif resource.service == 'nat_gateway':
                return self._estimate_nat_gateway_savings(resource)
            else:
                # Fallback for unknown services
                logger.warning(f"Unknown service for savings estimation: {resource.service}")
                return self._estimate_default_savings(resource)
                
        except Exception as e:
            logger.error(f"Error estimating savings for {resource.resource_id}: {e}")
            # Fallback to default
            return self._estimate_default_savings(resource)
    
    def _estimate_ec2_savings(self, resource) -> float:
        """Estimate EC2 instance savings."""
        try:
            ec2 = self.clients.get('ec2')
            if not ec2:
                return self._estimate_default_savings(resource)
            
            # Get instance type
            response = ec2.describe_instances(InstanceIds=[resource.resource_id])
            if not response.get('Reservations'):
                return self._estimate_default_savings(resource)
            
            instance = response['Reservations'][0]['Instances'][0]
            instance_type = instance.get('InstanceType', 't3.micro')
            
            # Get pricing for instance type
            pricing_data = self.pricing_manager.get_pricing_data('ec2', resource.region)
            hourly_price = pricing_data.prices.get(instance_type)
            
            if hourly_price:
                # Calculate monthly savings (24 hours * 30 days)
                monthly_savings = float(hourly_price) * 24 * 30
                logger.info(f"EC2 savings estimate: ${monthly_savings:.2f}/month for {instance_type}")
                return monthly_savings
            else:
                logger.warning(f"Pricing not found for instance type: {instance_type}")
                return self._estimate_default_savings(resource)
                
        except Exception as e:
            logger.error(f"Error estimating EC2 savings: {e}")
            return self._estimate_default_savings(resource)
    
    def _estimate_rds_savings(self, resource) -> float:
        """Estimate RDS instance savings."""
        try:
            rds = self.clients.get('rds')
            if not rds:
                return self._estimate_default_savings(resource)
            
            # Get DB instance class
            response = rds.describe_db_instances(DBInstanceIdentifier=resource.resource_id)
            if not response.get('DBInstances'):
                return self._estimate_default_savings(resource)
            
            db_instance = response['DBInstances'][0]
            instance_class = db_instance.get('DBInstanceClass', 'db.t3.micro')
            
            # Get pricing for instance class
            pricing_data = self.pricing_manager.get_pricing_data('rds', resource.region)
            # RDS pricing keys may include instance class
            hourly_price = pricing_data.prices.get(instance_class)
            
            if hourly_price:
                monthly_savings = float(hourly_price) * 24 * 30
                logger.info(f"RDS savings estimate: ${monthly_savings:.2f}/month for {instance_class}")
                return monthly_savings
            else:
                logger.warning(f"Pricing not found for DB instance class: {instance_class}")
                return self._estimate_default_savings(resource)
                
        except Exception as e:
            logger.error(f"Error estimating RDS savings: {e}")
            return self._estimate_default_savings(resource)
    
    def _estimate_lambda_savings(self, resource) -> float:
        """Estimate Lambda savings (complex - uses average pricing)."""
        try:
            # Lambda pricing is per-request and per-GB-second
            # For stopping (concurrency=0), estimate based on average usage
            # Use service-level pricing or default
            pricing_data = self.pricing_manager.get_pricing_data('lambda', resource.region)
            
            # Lambda pricing is complex, use conservative estimate
            # Average small function: ~$5-10/month
            # Use default for now, could be enhanced with CloudWatch metrics
            return self._estimate_default_savings(resource)
            
        except Exception as e:
            logger.error(f"Error estimating Lambda savings: {e}")
            return self._estimate_default_savings(resource)
    
    def _estimate_dynamodb_savings(self, resource) -> float:
        """Estimate DynamoDB savings (switching to on-demand)."""
        try:
            # DynamoDB on-demand vs provisioned savings
            # Use service-level pricing or default
            pricing_data = self.pricing_manager.get_pricing_data('dynamodb', resource.region)
            
            # DynamoDB savings depend on provisioned capacity
            # Use default for now, could be enhanced with table metadata
            return self._estimate_default_savings(resource)
            
        except Exception as e:
            logger.error(f"Error estimating DynamoDB savings: {e}")
            return self._estimate_default_savings(resource)
    
    def _estimate_ebs_savings(self, resource) -> float:
        """Estimate EBS volume savings."""
        try:
            # EBS pricing depends on volume type and size
            # Use default for now, could be enhanced with volume metadata
            return self._estimate_default_savings(resource)
            
        except Exception as e:
            logger.error(f"Error estimating EBS savings: {e}")
            return self._estimate_default_savings(resource)
    
    def _estimate_nat_gateway_savings(self, resource) -> float:
        """Estimate NAT Gateway savings (fixed hourly pricing)."""
        try:
            # NAT Gateway: $0.045/hour + data processing
            # Use fixed pricing
            hourly_price = 0.045  # Base NAT Gateway price
            monthly_savings = hourly_price * 24 * 30  # ~$32.40/month
            logger.info(f"NAT Gateway savings estimate: ${monthly_savings:.2f}/month")
            return monthly_savings
            
        except Exception as e:
            logger.error(f"Error estimating NAT Gateway savings: {e}")
            return self._estimate_default_savings(resource)
    
    def _estimate_default_savings(self, resource) -> float:
        """Default savings estimation fallback."""
        # Conservative default: $0.10/hour = $72/month
        default_hourly = 0.10
        monthly_savings = default_hourly * 24 * 30
        logger.warning(f"Using default savings estimate for {resource.service}: ${monthly_savings:.2f}/month")
        return monthly_savings
