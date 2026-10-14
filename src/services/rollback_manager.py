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
import ast
import json

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

    def _get_client(self, service: str, region: str = None):
        """Use the observed resource region when capturing or restoring state."""
        key = (service, region) if region else service
        if key not in self._clients:
            existing = self._clients.get(service)
            if existing is not None and getattr(getattr(existing, 'meta', None), 'region_name', None) == region:
                self._clients[key] = existing
            else:
                import boto3
                self._clients[key] = boto3.client(service, **({'region_name': region} if region else {}))
        return self._clients[key]

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
        
        if resource.service == 'lambda' and action == 'limit_concurrency':
            client = self._get_client('lambda', resource.region)
            prior = client.get_function_concurrency(FunctionName=resource.resource_id)
            value = prior.get('ReservedConcurrentExecutions')
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Invalid original Lambda reserved concurrency')
            state['reserved_concurrency'] = value

        try:
            self.dynamodb.put_item(
                TableName=self.audit_table,
                Item={
                    'action_id': {'S': f"{resource.resource_id}_{datetime.now(UTC).timestamp()}"},
                    'timestamp': {'N': str(int(datetime.fromisoformat(state['timestamp']).timestamp()))},
                    'timestamp_iso': {'S': state['timestamp']},
                    'event_type': {'S': 'pre_action_state'},
                    'resource_id': {'S': resource.resource_id},
                    'action': {'S': action},
                    'state': {'S': json.dumps(state, default=str)},
                    'ttl': {'N': str(int((datetime.now(UTC) + timedelta(hours=self.rollback_window_hours)).timestamp()))}
                }
            )
        except Exception as e:
            logger.error(f"Failed to store pre-action state: {e}")
            raise RuntimeError("Action blocked: rollback snapshot could not be stored") from e
    
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
        """Read JSON or bounded legacy literals without executing stored code."""
        if not isinstance(state_str, str) or not 1 <= len(state_str) <= 262144:
            return {}
        parsed = state_str
        for _ in range(2):
            if not isinstance(parsed, str): break
            try:
                parsed = json.loads(parsed)
            except (ValueError, TypeError):
                try: parsed = ast.literal_eval(parsed)
                except (ValueError, SyntaxError, TypeError, RecursionError): return {}
        if not isinstance(parsed, dict) or not parsed.get('service') or not parsed.get('action'):
            return {}
        return parsed

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
                from .time_values import parse_utc_timestamp
                action_timestamp = parse_utc_timestamp(timestamp_str)
                if action_timestamp.tzinfo is None: raise ValueError('Missing timestamp timezone')
                if action_timestamp > datetime.now(UTC)+timedelta(minutes=5): raise ValueError('Future rollback timestamp')
            except (ValueError, TypeError, OverflowError):
                return RollbackResult(action_id=action_id, resource_id=resource_id, success=False,
                    restored_state={}, timestamp=datetime.now(UTC).isoformat(),
                    error_message='Rollback blocked: original action timestamp is missing or invalid.')
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
            
            # Restore only a complete safely parsed state.
            state_dict = self._parse_state_string(state_str, action_id)
            if not state_dict or not state_dict.get('region') or state_dict.get('resource_id') != resource_id or state_dict.get('action') != action:
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
                return self._rollback_ec2_stop(resource_id, state.get('region'))
            elif service == 'rds' and action == 'stop':
                return self._rollback_rds_stop(resource_id, state.get('region'))
            elif service == 'lambda' and action == 'limit_concurrency':
                return self._rollback_lambda_concurrency(resource_id, state)
            else:
                logger.warning(f"No rollback handler for {service} {action}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to restore resource {resource_id}: {e}")
            return False
    
    def _rollback_ec2_stop(self, instance_id: str, region: str = None) -> bool:
        """Rollback EC2 stop by restarting instance."""
        try:
            ec2 = self._get_client('ec2', region)
            if not ec2:
                return False
            
            response = ec2.start_instances(InstanceIds=[instance_id])
            logger.info(f"Restarted EC2 instance: {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart EC2 instance {instance_id}: {e}")
            return False
    
    def _rollback_rds_stop(self, db_identifier: str, region: str = None) -> bool:
        """Rollback RDS stop by restarting database."""
        try:
            rds = self._get_client('rds', region)
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
            lambda_client = self._get_client('lambda', state.get('region'))
            if not lambda_client:
                return False
            
            if 'reserved_concurrency' not in state:
                logger.warning('Original Lambda concurrency is unavailable; rollback blocked')
                return False
            original = state['reserved_concurrency']
            if original is None:
                lambda_client.delete_function_concurrency(FunctionName=function_name)
            elif type(original) is int and original >= 0:
                lambda_client.put_function_concurrency(FunctionName=function_name, ReservedConcurrentExecutions=original)
            else:
                return False
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
                    'timestamp': {'N': str(int(datetime.fromisoformat(result.timestamp).timestamp()))},
                    'timestamp_iso': {'S': result.timestamp},
                    'event_type': {'S': 'rollback_submitted' if result.success else 'rollback_failed'},
                    'verification_status': {'S': 'unverified'},
                    'ttl': {'N': str(int(datetime.now(UTC).timestamp())+90*86400)},
                    'resource_id': {'S': result.resource_id},
                    'success': {'BOOL': result.success},
                    'target_state': {'S': json.dumps(result.restored_state, default=str)}
                }
            )
        except Exception as e:
            logger.error(f"Failed to log rollback: {e}")
