"""
Rollback Manager for reversing automated actions.

Supports:
- Storing pre-action state
- Rolling back actions within 24 hours
- Service-specific rollback operations
"""

from typing import Dict, Any
from datetime import datetime, timedelta, UTC
import logging

logger = logging.getLogger(__name__)


class RollbackManager:
    """Manage rollback of automated actions."""
    
    def __init__(self, aws_clients: Dict[str, Any], dynamodb_client):
        """
        Initialize rollback manager.
        
        Args:
            aws_clients: Dict of boto3 clients by service name
            dynamodb_client: boto3 DynamoDB client
        """
        self.clients = aws_clients
        self.dynamodb = dynamodb_client
        self.audit_table = "prevention-audit"
        self.rollback_window_hours = 24
    
    def store_pre_action_state(self, resource, action: str):
        """
        Store resource state before action.
        
        Args:
            resource: Resource object
            action: Action being performed
        """
        logger.info(f"Storing pre-action state for {resource.resource_id}")
        
        state = {
            'resource_id': resource.resource_id,
            'resource_type': resource.resource_type,
            'service': resource.service,
            'state': resource.state,
            'region': resource.region,
            'tags': resource.tags,
            'action': action,
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        try:
            self.dynamodb.put_item(
                TableName=self.audit_table,
                Item={
                    'action_id': {'S': f"{resource.resource_id}_{datetime.now(UTC).timestamp()}"},
                    'timestamp': {'S': state['timestamp']},
                    'event_type': {'S': 'pre_action_state'},
                    'resource_id': {'S': resource.resource_id},
                    'action': {'S': action},
                    'state': {'S': str(state)},
                    'ttl': {'N': str(int((datetime.now(UTC) + timedelta(hours=self.rollback_window_hours)).timestamp()))}
                }
            )
        except Exception as e:
            logger.error(f"Failed to store pre-action state: {e}")
    
    def execute_rollback(self, action_id: str) -> Any:
        """
        Rollback a specific action.
        
        Args:
            action_id: Action ID to rollback
            
        Returns:
            RollbackResult object
        """
        from ..utils.types import RollbackResult
        
        logger.info(f"Executing rollback for action: {action_id}")
        
        try:
            # Get pre-action state
            response = self.dynamodb.get_item(
                TableName=self.audit_table,
                Key={'action_id': {'S': action_id}}
            )
            
            item = response.get('Item')
            if not item:
                logger.error(f"Action not found: {action_id}")
                return RollbackResult(
                    action_id=action_id,
                    resource_id="unknown",
                    success=False,
                    restored_state={},
                    timestamp=datetime.now(UTC).isoformat()
                )
            
            # Parse state
            resource_id = item['resource_id']['S']
            action = item['action']['S']
            state_str = item['state']['S']
            
            # Check if within rollback window
            action_timestamp = datetime.fromisoformat(item['timestamp']['S'])
            if datetime.now(UTC) - action_timestamp > timedelta(hours=self.rollback_window_hours):
                logger.error(f"Action {action_id} is outside rollback window")
                return RollbackResult(
                    action_id=action_id,
                    resource_id=resource_id,
                    success=False,
                    restored_state={},
                    timestamp=datetime.now(UTC).isoformat()
                )
            
            # Execute rollback based on action type
            success = self.restore_resource_state(resource_id, eval(state_str))
            
            result = RollbackResult(
                action_id=action_id,
                resource_id=resource_id,
                success=success,
                restored_state=eval(state_str),
                timestamp=datetime.now(UTC).isoformat()
            )
            
            # Log rollback
            self._log_rollback(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Rollback failed for {action_id}: {e}")
            return RollbackResult(
                action_id=action_id,
                resource_id="unknown",
                success=False,
                restored_state={},
                timestamp=datetime.now(UTC).isoformat()
            )
    
    def restore_resource_state(self, resource_id: str, state: Dict[str, Any]) -> bool:
        """
        Restore resource to previous state.
        
        Args:
            resource_id: Resource ID
            state: Previous state dict
            
        Returns:
            True if successful, False otherwise
        """
        service = state.get('service')
        action = state.get('action')
        
        logger.info(f"Restoring {service} resource {resource_id}")
        
        try:
            if service == 'ec2' and action == 'stop':
                return self._rollback_ec2_stop(resource_id)
            elif service == 'rds' and action == 'stop':
                return self._rollback_rds_stop(resource_id)
            elif service == 'lambda' and action == 'limit_concurrency':
                return self._rollback_lambda_concurrency(resource_id, state)
            else:
                logger.warning(f"No rollback handler for {service} {action}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to restore resource {resource_id}: {e}")
            return False
    
    def _rollback_ec2_stop(self, instance_id: str) -> bool:
        """Rollback EC2 stop by restarting instance."""
        try:
            ec2 = self.clients.get('ec2')
            if not ec2:
                return False
            
            response = ec2.start_instances(InstanceIds=[instance_id])
            logger.info(f"Restarted EC2 instance: {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart EC2 instance {instance_id}: {e}")
            return False
    
    def _rollback_rds_stop(self, db_identifier: str) -> bool:
        """Rollback RDS stop by restarting database."""
        try:
            rds = self.clients.get('rds')
            if not rds:
                return False
            
            response = rds.start_db_instance(DBInstanceIdentifier=db_identifier)
            logger.info(f"Restarted RDS instance: {db_identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart RDS instance {db_identifier}: {e}")
            return False
    
    def _rollback_lambda_concurrency(self, function_name: str, state: Dict[str, Any]) -> bool:
        """Rollback Lambda concurrency limit."""
        try:
            lambda_client = self.clients.get('lambda')
            if not lambda_client:
                return False
            
            # Remove concurrency limit (restore to unreserved)
            response = lambda_client.delete_function_concurrency(FunctionName=function_name)
            logger.info(f"Restored Lambda concurrency for: {function_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore Lambda concurrency for {function_name}: {e}")
            return False
    
    def _log_rollback(self, result: Any):
        """Log rollback operation to audit trail."""
        try:
            self.dynamodb.put_item(
                TableName=self.audit_table,
                Item={
                    'action_id': {'S': f"rollback_{result.action_id}"},
                    'timestamp': {'S': result.timestamp},
                    'event_type': {'S': 'rollback'},
                    'resource_id': {'S': result.resource_id},
                    'success': {'BOOL': result.success},
                    'details': {'S': str(result.restored_state)}
                }
            )
        except Exception as e:
            logger.error(f"Failed to log rollback: {e}")
