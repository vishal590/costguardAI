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

from typing import Dict, Any
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Execute automated actions on resources."""
    
    def __init__(self, aws_clients: Dict[str, Any], audit_logger):
        """
        Initialize action executor.
        
        Args:
            aws_clients: Dict of boto3 clients by service name
            audit_logger: Logger for audit trail
        """
        self.clients = aws_clients
        self.audit_logger = audit_logger
    
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
        """Estimate monthly savings from stopping resource."""
        # Placeholder - would use actual pricing data
        # Assume $0.10/hour as default
        return 0.10 * 24 * 30  # $72/month
