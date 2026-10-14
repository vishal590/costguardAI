"""
Approval Manager for managing approval workflow for automated actions.

Supports:
- Sending approval requests via SNS
- Waiting for approval response (30 minute timeout)
- Conditional decisions from a trusted integration (no legacy public receiver is defined)
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta, UTC
import uuid
import logging
import os
import json
from dataclasses import asdict

logger = logging.getLogger(__name__)


class ApprovalManager:
    """Manage approval workflow for automated actions."""
    
    def __init__(self, sns_client, dynamodb_client):
        """
        Initialize approval manager.
        
        Args:
            sns_client: boto3 SNS client
            dynamodb_client: boto3 DynamoDB client
        """
        self.sns = sns_client
        self.dynamodb = dynamodb_client
        self.approval_table = os.environ.get("APPROVAL_REQUESTS_TABLE", "costguard-approval-requests")
        self.approval_topic_arn = None  # Would be set from config
    
    def request_approval(self, actions: List[Dict[str, Any]]) -> Any:
        """
        Send approval request via SNS.
        
        Args:
            actions: List of planned actions
            
        Returns:
            ApprovalRequest object
        """
        from ..utils.types import ApprovalRequest, PlannedAction
        
        request_id = str(uuid.uuid4())
        expires_at = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
        
        planned_actions = []
        for action in actions:
            if isinstance(action, PlannedAction):
                planned_actions.append(action)
            else:
                planned_actions.append(PlannedAction(resource_id=action['resource'].resource_id,
                    resource_type=action['resource'].resource_type, action=action['action'],
                    reason='Budget threshold exceeded; resource review requested', estimated_savings=action.get('estimated_savings')))
        values = [action.estimated_savings for action in planned_actions]
        total_savings = sum(values) if values and all(value is not None for value in values) else None

        approval_request = ApprovalRequest(
            request_id=request_id,
            actions=planned_actions,
            total_estimated_savings=total_savings,
            expires_at=expires_at
        )
        
        # Store in DynamoDB
        self._store_approval_request(approval_request)
        
        # Send SNS notification
        self._send_approval_notification(approval_request)
        
        logger.info(f"Approval request created: {request_id}")
        return approval_request
    
    def wait_for_approval(self, request_id: str, timeout_minutes: int) -> Any:
        """
        Wait for approval response.
        
        Args:
            request_id: Approval request ID
            timeout_minutes: Timeout in minutes
            
        Returns:
            ApprovalResponse object
        """
        from ..utils.types import ApprovalResponse
        
        logger.info(f"Waiting for approval: {request_id}")
        
        # In a real implementation, this would poll DynamoDB or use a callback
        # For now, we'll simulate a timeout
        
        import time
        start_time = datetime.now(UTC)
        timeout = timedelta(minutes=timeout_minutes)
        
        while datetime.now(UTC) - start_time < timeout:
            # Check for approval response
            response = self._check_approval_status(request_id)
            
            if response:
                return response
            
            # Wait before checking again
            time.sleep(10)  # Check every 10 seconds
        
        # Timeout - default to not approved
        logger.warning(f"Approval request timed out: {request_id}")
        return ApprovalResponse(
            request_id=request_id,
            approved=False,
            approved_by=None,
            timestamp=datetime.now(UTC).isoformat()
        )
    
    def process_approval_response(self, request_id: str, approved: bool, approved_by: str = None):
        """
        Process approval response from API or email.
        
        Args:
            request_id: Approval request ID
            approved: Whether approved or denied
            approved_by: Who approved (optional)
        """
        from ..utils.types import ApprovalResponse
        
        logger.info(f"Processing approval response for {request_id}: {approved}")
        
        if type(approved) is not bool or not isinstance(approved_by, str) or not approved_by.strip() or len(approved_by) > 256:
            raise ValueError('A boolean decision and authenticated approver identity are required')
        response = ApprovalResponse(
            request_id=request_id,
            approved=approved,
            approved_by=approved_by,
            timestamp=datetime.now(UTC).isoformat()
        )
        
        # Store response in DynamoDB
        self._store_approval_response(response)
        
        return response
    
    def _store_approval_request(self, request: Any):
        """Store approval request in DynamoDB."""
        try:
            self.dynamodb.put_item(
                TableName=self.approval_table,
                Item={
                    'request_id': {'S': request.request_id},
                    'status': {'S': 'pending'},
                    'total_estimated_savings': {'N': str(request.total_estimated_savings)} if request.total_estimated_savings is not None else {'NULL': True},
                    'expires_at': {'S': request.expires_at},
                    'created_at': {'N': str(int(datetime.now(UTC).timestamp()))},
                    'created_at_iso': {'S': datetime.now(UTC).isoformat()},
                    'expires_at_epoch': {'N': str(int(datetime.fromisoformat(request.expires_at).timestamp()))},
                    'ttl': {'N': str(int(datetime.now(UTC).timestamp())+90*86400)},
                    'actions_json': {'S': json.dumps([asdict(action) for action in request.actions], default=str)},
                    'action_count': {'N': str(len(request.actions))}
                },
                ConditionExpression='attribute_not_exists(request_id)'
            )
        except Exception as e:
            logger.error(f"Failed to store approval request: {e}")
            raise RuntimeError("Approval request was not persisted") from e
    
    def _store_approval_response(self, response: Any):
        """Store approval response in DynamoDB."""
        try:
            self.dynamodb.update_item(
                TableName=self.approval_table,
                Key={'request_id': {'S': response.request_id}},
                UpdateExpression='SET #status = :status, approved_by = :approved_by, response_timestamp = :timestamp',
                ConditionExpression='attribute_exists(request_id) AND #status = :pending AND expires_at_epoch > :now',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': {'S': 'approved' if response.approved else 'denied'},
                    ':pending': {'S': 'pending'}, ':now': {'N': str(int(datetime.now(UTC).timestamp()))},
                    ':approved_by': {'S': response.approved_by or 'unknown'},
                    ':timestamp': {'S': response.timestamp}
                }
            )
        except Exception as e:
            logger.error(f"Failed to store approval response: {e}")
            raise RuntimeError("Approval decision was not persisted; request may be expired or already decided") from e
    
    def _check_approval_status(self, request_id: str) -> Any:
        """Check if approval has been received."""
        from ..utils.types import ApprovalResponse
        
        try:
            response = self.dynamodb.get_item(
                TableName=self.approval_table,
                Key={'request_id': {'S': request_id}}, ConsistentRead=True
            )
            
            item = response.get('Item')
            if not item:
                return None
            
            if int(item.get('expires_at_epoch', {}).get('N', '0')) <= int(datetime.now(UTC).timestamp()): return None
            status = item.get('status', {}).get('S')
            
            if status in ['approved', 'denied']:
                return ApprovalResponse(
                    request_id=request_id,
                    approved=(status == 'approved'),
                    approved_by=item.get('approved_by', {}).get('S'),
                    timestamp=item.get('response_timestamp', {}).get('S', datetime.now(UTC).isoformat())
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to check approval status: {e}")
            raise RuntimeError("Approval status is unavailable") from e
    
    def _send_approval_notification(self, request: Any):
        """Send approval request notification via SNS."""
        if not self.approval_topic_arn:
            logger.warning("No approval topic ARN configured")
            return
        
        from .notification_service import _opportunity
        message = f"""
Automated Cost Prevention - Approval Required

Request ID: {request.request_id}
Actions: {len(request.actions)}
Monetary opportunity: {_opportunity(request.total_estimated_savings)}
Expires: {request.expires_at}

Actions to be taken:
"""
        
        for action in request.actions:
            message += f"\n- {action.action} {action.resource_type} {action.resource_id} ({_opportunity(action.estimated_savings)})"
        
        message += f"\n\nUse the configured approval integration. This legacy manager has no public response endpoint and does not authorize resource changes by itself."
        
        try:
            self.sns.publish(
                TopicArn=self.approval_topic_arn,
                Subject="Cost Prevention - Approval Required",
                Message=message
            )
            logger.info(f"Sent approval notification for {request.request_id}")
        except Exception as e:
            logger.error(f"Failed to send approval notification: {e}")
