"""
Approval Manager for managing approval workflow for automated actions.

Supports:
- Sending approval requests via SNS
- Waiting for approval response (30 minute timeout)
- Processing approval via API or email
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta, UTC
import uuid
import logging

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
        self.approval_table = "approval-requests"
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
        
        # Convert actions to PlannedAction objects
        planned_actions = []
        total_savings = 0.0
        
        for action in actions:
            planned_action = PlannedAction(
                resource_id=action['resource'].resource_id,
                resource_type=action['resource'].resource_type,
                action=action['action'],
                reason="Budget threshold exceeded - resource is idle",
                estimated_savings=action['estimated_savings']
            )
            planned_actions.append(planned_action)
            total_savings += action['estimated_savings']
        
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
                    'total_estimated_savings': {'N': str(request.total_estimated_savings)},
                    'expires_at': {'S': request.expires_at},
                    'created_at': {'S': datetime.now(UTC).isoformat()},
                    'action_count': {'N': str(len(request.actions))}
                }
            )
        except Exception as e:
            logger.error(f"Failed to store approval request: {e}")
    
    def _store_approval_response(self, response: Any):
        """Store approval response in DynamoDB."""
        try:
            self.dynamodb.update_item(
                TableName=self.approval_table,
                Key={'request_id': {'S': response.request_id}},
                UpdateExpression='SET #status = :status, approved_by = :approved_by, response_timestamp = :timestamp',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': {'S': 'approved' if response.approved else 'denied'},
                    ':approved_by': {'S': response.approved_by or 'unknown'},
                    ':timestamp': {'S': response.timestamp}
                }
            )
        except Exception as e:
            logger.error(f"Failed to store approval response: {e}")
    
    def _check_approval_status(self, request_id: str) -> Any:
        """Check if approval has been received."""
        from ..utils.types import ApprovalResponse
        
        try:
            response = self.dynamodb.get_item(
                TableName=self.approval_table,
                Key={'request_id': {'S': request_id}}
            )
            
            item = response.get('Item')
            if not item:
                return None
            
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
            return None
    
    def _send_approval_notification(self, request: Any):
        """Send approval request notification via SNS."""
        if not self.approval_topic_arn:
            logger.warning("No approval topic ARN configured")
            return
        
        message = f"""
Automated Cost Prevention - Approval Required

Request ID: {request.request_id}
Actions: {len(request.actions)}
Estimated Monthly Savings: ${request.total_estimated_savings:.2f}
Expires: {request.expires_at}

Actions to be taken:
"""
        
        for action in request.actions:
            message += f"\n- {action.action} {action.resource_type} {action.resource_id} (${action.estimated_savings:.2f}/month)"
        
        message += f"\n\nTo approve or deny, respond via API or email within 30 minutes."
        
        try:
            self.sns.publish(
                TopicArn=self.approval_topic_arn,
                Subject="Cost Prevention - Approval Required",
                Message=message
            )
            logger.info(f"Sent approval notification for {request.request_id}")
        except Exception as e:
            logger.error(f"Failed to send approval notification: {e}")
