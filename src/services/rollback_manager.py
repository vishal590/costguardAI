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
import os
import re

logger = logging.getLogger(__name__)


class RollbackManager:
    """Manage rollback of automated actions."""
    
    def __init__(self, aws_clients: Dict[str, Any], dynamodb_client):
        """
        Initialize rollback manager.
        
        Args:
            aws_clients: Dict of boto3 clients by service name (can be empty; clients created lazily on rollback)
            dynamodb_client: boto3 DynamoDB client
        """
        self._clients = dict(aws_clients) if aws_clients else {}
        self.dynamodb = dynamodb_client
        # Expose for tests; rollback code uses _get_client()
        self.clients = self._clients
        # Use same table as prevention_engine.get_action_history (PREVENTION_AUDIT_TABLE)
        self.audit_table = os.environ.get("PREVENTION_AUDIT_TABLE", "costguard-prevention-audit")
        try:
            self.rollback_window_hours = int(os.environ.get("ROLLBACK_WINDOW_HOURS", "24"))
        except (TypeError, ValueError):
            self.rollback_window_hours = 24

    def _get_client(self, service: str):
        """Get boto3 client for service, creating lazily if not in _clients (avoids creating clients on every prevention request)."""
        if service not in self._clients:
            try:
                import boto3
                self._clients[service] = boto3.client(service)
            except Exception as e:
                logger.warning(f"Could not create {service} client for rollback: {e}")
                return None
        return self._clients.get(service)
    
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
    
    def _get_str(self, item: Dict[str, Any], key: str) -> str:
        """Get string value from DynamoDB item attribute."""
        if key not in item:
            return ""
        val = item[key]
        if "S" in val:
            return val["S"]
        if "N" in val:
            return val["N"]
        return ""

    def _parse_state_string(self, state_str: str, action_id: str) -> Dict[str, Any]:
        """Parse state string from audit item into a dict. Tries eval, then regex fallback for service/action."""
        if not state_str or not state_str.strip():
            return {}
        s = state_str.replace("...", "None").strip()
        try:
            parsed = eval(s)
            if isinstance(parsed, dict) and parsed.get("service") and parsed.get("action"):
                return parsed
            if isinstance(parsed, str):
                inner = parsed.replace("...", "None").strip()
                parsed = eval(inner)
                if isinstance(parsed, dict) and parsed.get("service") and parsed.get("action"):
                    return parsed
        except Exception as e:
            logger.debug(f"eval state failed for {action_id}: {e}")
        # Fallback: extract 'service' and 'action' from string (e.g. "'service': 'ec2'" or "service': 'ec2")
        m_service = re.search(r"['\"]?service['\"]?\s*:\s*['\"]([^'\"]+)['\"]", state_str, re.I)
        m_action = re.search(r"['\"]?action['\"]?\s*:\s*['\"]([^'\"]+)['\"]", state_str, re.I)
        if m_service and m_action:
            return {"service": m_service.group(1).strip(), "action": m_action.group(1).strip(), "resource_id": ""}
        return {}

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
        
        if not self.dynamodb:
            logger.error("DynamoDB client not configured for rollback")
            return RollbackResult(
                action_id=action_id,
                resource_id="unknown",
                success=False,
                restored_state={},
                timestamp=datetime.now(UTC).isoformat(),
                error_message="Rollback not configured (no database connection)."
            )
        
        try:
            # Get pre-action state (same table as get_action_history)
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
                    timestamp=datetime.now(UTC).isoformat(),
                    error_message="Action not found."
                )
            
            # Parse required fields (written by store_pre_action_state)
            resource_id = self._get_str(item, 'resource_id')
            action = self._get_str(item, 'action')
            state_str = self._get_str(item, 'state')
            timestamp_str = self._get_str(item, 'timestamp')
            
            if not resource_id or not action or not state_str:
                logger.warning(f"Action {action_id} has no rollback state (e.g. manually added record)")
                return RollbackResult(
                    action_id=action_id,
                    resource_id=resource_id or "unknown",
                    success=False,
                    restored_state={},
                    timestamp=datetime.now(UTC).isoformat(),
                    error_message="This action cannot be rolled back (no rollback state; e.g. manually added record)."
                )
            
            # Check if within rollback window (timestamp may be ISO string or Unix epoch string from DynamoDB N type)
            try:
                if timestamp_str and timestamp_str.strip().isdigit():
                    action_timestamp = datetime.fromtimestamp(int(timestamp_str), tz=UTC)
                else:
                    action_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                action_timestamp = datetime.now(UTC)
            if datetime.now(UTC) - action_timestamp > timedelta(hours=self.rollback_window_hours):
                logger.error(f"Action {action_id} is outside rollback window ({self.rollback_window_hours}h)")
                return RollbackResult(
                    action_id=action_id,
                    resource_id=resource_id,
                    success=False,
                    restored_state={},
                    timestamp=datetime.now(UTC).isoformat(),
                    error_message=f"Rollback only available for actions in the last {self.rollback_window_hours} hours."
                )
            
            # Execute rollback based on action type (state may be dict string; "..." can break eval in some envs)
            state_dict = self._parse_state_string(state_str, action_id)
            if not state_dict:
                return RollbackResult(
                    action_id=action_id,
                    resource_id=resource_id,
                    success=False,
                    restored_state={},
                    timestamp=datetime.now(UTC).isoformat(),
                    error_message="This action cannot be rolled back (invalid state format)."
                )
            success = self.restore_resource_state(resource_id, state_dict)
            restore_error = None if success else (
                "Restore failed. The resource may not exist (e.g. placeholder i-xxxxx), "
                "or the Lambda role may lack permission to start it."
            )
            result = RollbackResult(
                action_id=action_id,
                resource_id=resource_id,
                success=success,
                restored_state=state_dict,
                timestamp=datetime.now(UTC).isoformat(),
                error_message=restore_error
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
                timestamp=datetime.now(UTC).isoformat(),
                error_message=f"Rollback failed: {e}"
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
            ec2 = self._get_client('ec2')
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
            rds = self._get_client('rds')
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
            lambda_client = self._get_client('lambda')
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
