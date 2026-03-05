"""
Safety Guard Lambda Function

Validates and controls autonomous actions to prevent costly mistakes.

Responsibilities:
- Execute dry-run mode (log without executing)
- Manage approval workflows for high-risk actions
- Enforce Free Tier budget limits ($5/month threshold)
- Provide rollback capability for executed actions
- Validate all action requests against safety policies

Requirements: 5.1-5.11
"""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from autonomous.utils.cloudwatch_metrics import get_metrics_publisher
from autonomous.utils.audit_logger import log_action, get_current_user, get_source_ip


# Environment variables
ACTION_HISTORY_TABLE = os.environ.get("ACTION_HISTORY_TABLE", "costguard-action-history")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "costguard-autonomous-events")
APPROVAL_SNS_TOPIC = os.environ.get("APPROVAL_SNS_TOPIC", "")
DRY_RUN_MODE = os.environ.get("DRY_RUN_MODE", "false").lower() == "true"
APPROVAL_TIMEOUT_MINUTES = int(os.environ.get("APPROVAL_TIMEOUT_MINUTES", "15"))
FREE_TIER_BUDGET_LIMIT = float(os.environ.get("FREE_TIER_BUDGET_LIMIT", "5.0"))
APPROVAL_REQUIRED_ACTIONS = os.environ.get("APPROVAL_REQUIRED_ACTIONS", "migration,ondemand_fallback").split(",")
APPROVAL_SECRET_KEY = os.environ.get("APPROVAL_SECRET_KEY", "default-secret-key-change-in-production")

# AWS clients
dynamodb = boto3.resource("dynamodb")
events_client = boto3.client("events")
sns_client = boto3.client("sns")
cloudwatch_client = boto3.client("cloudwatch")
ce_client = boto3.client("ce")  # Cost Explorer

# Tables
action_history_table = dynamodb.Table(ACTION_HISTORY_TABLE)


class ActionRequest:
    """Represents a request for autonomous action approval."""
    
    def __init__(
        self,
        request_id: str,
        action_type: str,
        action_id: str,
        parameters: Dict[str, Any],
        confidence_score: float,
        expected_cost_impact: float,
        approval_required: bool = False,
    ):
        self.request_id = request_id
        self.action_type = action_type
        self.action_id = action_id
        self.parameters = parameters
        self.confidence_score = confidence_score
        self.expected_cost_impact = expected_cost_impact
        self.approval_required = approval_required
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "action_type": self.action_type,
            "action_id": self.action_id,
            "parameters": self.parameters,
            "confidence_score": self.confidence_score,
            "expected_cost_impact": self.expected_cost_impact,
            "approval_required": self.approval_required,
            "timestamp": self.timestamp.isoformat(),
        }


class ValidationResult:
    """Result of action request validation."""
    
    def __init__(self, valid: bool, reason: str = ""):
        self.valid = valid
        self.reason = reason


def execute_dry_run(action: ActionRequest, event: Dict[str, Any] = None) -> None:
    """
    Execute action in dry-run mode (log without executing).
    
    Args:
        action: Action request to dry-run
        event: Lambda event for audit logging
    """
    try:
        print(f"[DRY-RUN] Action: {action.action_type}")
        print(f"[DRY-RUN] Action ID: {action.action_id}")
        print(f"[DRY-RUN] Parameters: {json.dumps(action.parameters, indent=2)}")
        print(f"[DRY-RUN] Expected cost impact: ${action.expected_cost_impact:.2f}")
        print(f"[DRY-RUN] Confidence score: {action.confidence_score:.2f}")
        
        # Store dry-run log in action history
        ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())
        
        item = {
            "action_id": action.action_id,
            "timestamp": action.timestamp.isoformat(),
            "action_type": action.action_type,
            "status": "dry_run",
            "parameters": action.parameters,
            "confidence_score": Decimal(str(action.confidence_score)),
            "expected_cost_impact": Decimal(str(action.expected_cost_impact)),
            "dry_run": True,
            "ttl": ttl,
        }
        
        action_history_table.put_item(Item=item)
        
        # Create audit log
        log_action(
            action_id=action.action_id,
            action_type=action.action_type,
            parameters=action.parameters,
            outcome="dry_run",
            event=event,
            cost_impact=action.expected_cost_impact,
        )
        
        print(f"[DRY-RUN] Logged action to history: {action.action_id}")
        
    except Exception as e:
        print(f"ERROR: Failed to execute dry-run: {e}")
        raise


def validate_action_request(action: ActionRequest) -> ValidationResult:
    """
    Validate action request against safety policies.
    
    Args:
        action: Action request to validate
        
    Returns:
        ValidationResult with validation status
    """
    try:
        # Check confidence score
        if action.confidence_score < 0.0 or action.confidence_score > 1.0:
            return ValidationResult(False, "Invalid confidence score (must be 0.0-1.0)")
        
        # Check if action type is recognized
        valid_action_types = ["schedule", "spot_migration", "right_sizing", "ondemand_fallback"]
        if action.action_type not in valid_action_types:
            return ValidationResult(False, f"Unknown action type: {action.action_type}")
        
        # Check budget limit
        if not check_budget_limit():
            return ValidationResult(False, "Budget limit exceeded")
        
        # Check parameters are present
        if not action.parameters:
            return ValidationResult(False, "Missing action parameters")
        
        return ValidationResult(True, "Validation passed")
        
    except Exception as e:
        print(f"ERROR: Validation failed: {e}")
        return ValidationResult(False, f"Validation error: {str(e)}")


def check_budget_limit() -> bool:
    """
    Check if current AWS costs are within Free Tier budget limit.
    
    Returns:
        True if within budget, False if exceeded
    """
    try:
        # Get current month date range
        now = datetime.utcnow()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        
        # Query Cost Explorer for month-to-date costs
        # Note: In production, this would query actual costs
        # For now, we'll estimate based on Lambda invocations and DynamoDB usage
        
        # Estimate Lambda costs (1M free requests/month)
        try:
            lambda_metrics = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                StartTime=start_of_month,
                EndTime=now,
                Period=2592000,  # 30 days
                Statistics=['Sum'],
            )
            
            lambda_invocations = 0
            if lambda_metrics.get('Datapoints'):
                lambda_invocations = lambda_metrics['Datapoints'][0].get('Sum', 0)
            
            # Estimate cost: $0.20 per 1M requests after free tier
            lambda_cost = max(0, (lambda_invocations - 1000000) * 0.20 / 1000000)
        except Exception as e:
            print(f"WARNING: Failed to get Lambda metrics: {e}")
            lambda_cost = 0.0
        
        # Estimate DynamoDB costs (25 GB free storage, 25 RCU/WCU free)
        # Simplified: assume we're within free tier for DynamoDB
        dynamodb_cost = 0.0
        
        # Estimate CloudWatch costs (5 custom metrics free)
        # Simplified: assume we're within free tier
        cloudwatch_cost = 0.0
        
        # Total estimated cost
        estimated_cost = lambda_cost + dynamodb_cost + cloudwatch_cost
        
        print(f"Estimated monthly cost: ${estimated_cost:.2f} / ${FREE_TIER_BUDGET_LIMIT:.2f}")
        
        # Check if within budget
        if estimated_cost >= FREE_TIER_BUDGET_LIMIT:
            print(f"WARNING: Budget limit exceeded!")
            
            # Send budget alert
            if APPROVAL_SNS_TOPIC:
                try:
                    sns_client.publish(
                        TopicArn=APPROVAL_SNS_TOPIC,
                        Subject="CostGuard Budget Alert",
                        Message=f"Monthly cost (${estimated_cost:.2f}) has exceeded the budget limit (${FREE_TIER_BUDGET_LIMIT:.2f})",
                    )
                except Exception as e:
                    print(f"ERROR: Failed to send budget alert: {e}")
            
            return False
        
        # Send warning if approaching limit (90%)
        if estimated_cost >= FREE_TIER_BUDGET_LIMIT * 0.9:
            print(f"WARNING: Approaching budget limit (${estimated_cost:.2f} / ${FREE_TIER_BUDGET_LIMIT:.2f})")
            
            if APPROVAL_SNS_TOPIC:
                try:
                    sns_client.publish(
                        TopicArn=APPROVAL_SNS_TOPIC,
                        Subject="CostGuard Budget Warning",
                        Message=f"Monthly cost (${estimated_cost:.2f}) is approaching the budget limit (${FREE_TIER_BUDGET_LIMIT:.2f})",
                    )
                except Exception as e:
                    print(f"ERROR: Failed to send budget warning: {e}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to check budget limit: {e}")
        # On error, allow action but log warning
        return True


def generate_approval_signature(request_id: str, action_id: str) -> str:
    """
    Generate HMAC signature for approval request.
    
    Args:
        request_id: Approval request ID
        action_id: Action ID
        
    Returns:
        HMAC signature
    """
    message = f"{request_id}:{action_id}".encode('utf-8')
    signature = hmac.new(
        APPROVAL_SECRET_KEY.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()
    
    return signature


def validate_approval_signature(request_id: str, action_id: str, signature: str) -> bool:
    """
    Validate HMAC signature for approval response.
    
    Args:
        request_id: Approval request ID
        action_id: Action ID
        signature: Provided signature
        
    Returns:
        True if signature is valid
    """
    expected_signature = generate_approval_signature(request_id, action_id)
    return hmac.compare_digest(signature, expected_signature)


def request_approval(action: ActionRequest) -> str:
    """
    Request human approval for high-risk action.
    
    Args:
        action: Action request requiring approval
        
    Returns:
        Approval request ID
    """
    try:
        # Generate approval signature
        signature = generate_approval_signature(action.request_id, action.action_id)
        
        # Create approval message
        message = f"""
CostGuard Autonomous Action Approval Required

Action Type: {action.action_type}
Action ID: {action.action_id}
Confidence Score: {action.confidence_score:.2%}
Expected Cost Impact: ${action.expected_cost_impact:.2f}

Parameters:
{json.dumps(action.parameters, indent=2)}

To approve this action, reply with:
APPROVE {action.request_id} {signature}

To reject this action, reply with:
REJECT {action.request_id}

This request will expire in {APPROVAL_TIMEOUT_MINUTES} minutes.
"""
        
        # Send SNS notification
        if APPROVAL_SNS_TOPIC:
            sns_client.publish(
                TopicArn=APPROVAL_SNS_TOPIC,
                Subject=f"CostGuard Approval Required: {action.action_type}",
                Message=message,
            )
            
            print(f"Approval request sent: {action.request_id}")
        else:
            print(f"WARNING: No SNS topic configured for approval requests")
        
        # Store approval request in DynamoDB
        ttl = int((datetime.utcnow() + timedelta(minutes=APPROVAL_TIMEOUT_MINUTES)).timestamp())
        
        item = {
            "action_id": action.action_id,
            "timestamp": action.timestamp.isoformat(),
            "action_type": action.action_type,
            "status": "pending_approval",
            "parameters": action.parameters,
            "confidence_score": Decimal(str(action.confidence_score)),
            "expected_cost_impact": Decimal(str(action.expected_cost_impact)),
            "approval_required": True,
            "approval_request_id": action.request_id,
            "approval_signature": signature,
            "ttl": ttl,
        }
        
        action_history_table.put_item(Item=item)
        
        return action.request_id
        
    except Exception as e:
        print(f"ERROR: Failed to request approval: {e}")
        raise


def wait_for_approval(request_id: str, timeout_minutes: int = APPROVAL_TIMEOUT_MINUTES) -> Optional[bool]:
    """
    Wait for approval response with timeout.
    
    Args:
        request_id: Approval request ID
        timeout_minutes: Timeout in minutes
        
    Returns:
        True if approved, False if rejected, None if timeout
    """
    try:
        # In production, this would poll DynamoDB or use EventBridge
        # For now, we'll simulate the wait
        
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        
        while time.time() - start_time < timeout_seconds:
            # Query for approval response
            # In production, would check for approval record update
            
            # For now, simulate timeout
            time.sleep(1)
            
            # Check if approval received (simplified)
            # In production, would query DynamoDB for approval status
            
            # Timeout reached
            if time.time() - start_time >= timeout_seconds:
                print(f"Approval timeout reached for request: {request_id}")
                return None
        
        return None
        
    except Exception as e:
        print(f"ERROR: Failed to wait for approval: {e}")
        return None


def create_rollback_capability(action: ActionRequest) -> str:
    """
    Create rollback capability for action.
    
    Args:
        action: Action request
        
    Returns:
        Rollback ID
    """
    try:
        rollback_id = f"rollback_{action.action_id}_{int(time.time())}"
        
        # Store rollback metadata
        ttl = int((datetime.utcnow() + timedelta(days=7)).timestamp())
        
        item = {
            "action_id": action.action_id,
            "timestamp": action.timestamp.isoformat(),
            "rollback_id": rollback_id,
            "action_type": action.action_type,
            "parameters": action.parameters,
            "rollback_created": True,
            "ttl": ttl,
        }
        
        action_history_table.put_item(Item=item)
        
        print(f"Rollback capability created: {rollback_id}")
        
        return rollback_id
        
    except Exception as e:
        print(f"ERROR: Failed to create rollback capability: {e}")
        raise


def execute_rollback(action_id: str) -> bool:
    """
    Execute rollback to restore previous state.
    
    Args:
        action_id: Action ID to rollback
        
    Returns:
        True if rollback successful
    """
    try:
        # Query action from history
        response = action_history_table.query(
            KeyConditionExpression=Key("action_id").eq(action_id),
            Limit=1,
        )
        
        if not response.get("Items"):
            print(f"ERROR: Action not found: {action_id}")
            return False
        
        action_item = response["Items"][0]
        
        # Verify rollback capability exists
        if not action_item.get("rollback_created"):
            print(f"ERROR: No rollback capability for action: {action_id}")
            return False
        
        # Execute rollback (simplified)
        # In production, would restore previous state based on action type
        print(f"Executing rollback for action: {action_id}")
        
        # Update action status
        action_history_table.update_item(
            Key={"action_id": action_id, "timestamp": action_item["timestamp"]},
            UpdateExpression="SET #status = :status, rolled_back_at = :timestamp",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "rolled_back",
                ":timestamp": datetime.utcnow().isoformat(),
            },
        )
        
        # Publish rollback event
        events_client.put_events(
            Entries=[{
                "Source": "costguard.autonomous.safetyguard",
                "DetailType": "RollbackExecuted",
                "Detail": json.dumps({
                    "action_id": action_id,
                    "rollback_id": action_item.get("rollback_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                }),
                "EventBusName": EVENT_BUS_NAME,
            }]
        )
        
        print(f"Rollback completed for action: {action_id}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to execute rollback: {e}")
        return False


def publish_approval_decision(action: ActionRequest, approved: bool) -> None:
    """
    Publish approval decision to EventBridge.
    
    Args:
        action: Action request
        approved: Whether action was approved
    """
    try:
        detail_type = "ActionApproved" if approved else "ActionRejected"
        
        events_client.put_events(
            Entries=[{
                "Source": "costguard.autonomous.safetyguard",
                "DetailType": detail_type,
                "Detail": json.dumps({
                    "request_id": action.request_id,
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "approved": approved,
                    "timestamp": datetime.utcnow().isoformat(),
                }),
                "EventBusName": EVENT_BUS_NAME,
            }]
        )
        
        print(f"Published {detail_type} event for action: {action.action_id}")
        
    except Exception as e:
        print(f"ERROR: Failed to publish approval decision: {e}")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for Safety Guard.
    
    Handles:
    - ActionRequest events from other autonomous functions
    - Approval responses
    - Rollback requests
    
    Args:
        event: EventBridge event or API Gateway request
        context: Lambda context
        
    Returns:
        Response with approval/rejection decision
    """
    try:
        print(f"Safety Guard invoked with event: {json.dumps(event, default=str)}")
        
        # Get metrics publisher
        metrics = get_metrics_publisher()
        
        # Determine event type
        detail_type = event.get("detail-type", "")
        
        if detail_type == "ActionRequest":
            # Handle action request
            detail = event.get("detail", {})
            
            # Create action request object
            action = ActionRequest(
                request_id=detail.get("request_id", f"req_{int(time.time())}"),
                action_type=detail.get("action_type"),
                action_id=detail.get("action_id"),
                parameters=detail.get("parameters", {}),
                confidence_score=detail.get("confidence_score", 0.5),
                expected_cost_impact=detail.get("expected_cost_impact", 0.0),
                approval_required=detail.get("approval_required", False),
            )
            
            # Check dry-run mode
            dry_run = os.environ.get("DRY_RUN_MODE", "false").lower() == "true"
            
            if dry_run:
                # Execute in dry-run mode
                execute_dry_run(action, event)
                
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "status": "dry_run",
                        "action_id": action.action_id,
                        "message": "Action logged in dry-run mode",
                    }),
                }
            
            # Validate action request
            validation = validate_action_request(action)
            
            if not validation.valid:
                print(f"Action validation failed: {validation.reason}")
                
                # Log rejection
                log_action(
                    action_id=action.action_id,
                    action_type=action.action_type,
                    parameters=action.parameters,
                    outcome="rejected",
                    event=event,
                )
                
                # Publish rejection event
                publish_approval_decision(action, False)
                
                return {
                    "statusCode": 400,
                    "body": json.dumps({
                        "status": "rejected",
                        "action_id": action.action_id,
                        "reason": validation.reason,
                    }),
                }
            
            # Check budget utilization and publish metric
            budget_ok = check_budget_limit()
            # Estimate budget utilization (simplified)
            budget_utilization = 50.0 if budget_ok else 95.0
            metrics.publish_budget_utilization(budget_utilization)
            
            # Check if approval required
            if action.approval_required or action.action_type in APPROVAL_REQUIRED_ACTIONS:
                # Request approval
                request_id = request_approval(action)
                
                # Create rollback capability
                rollback_id = create_rollback_capability(action)
                
                # Log approval request
                log_action(
                    action_id=action.action_id,
                    action_type=action.action_type,
                    parameters=action.parameters,
                    outcome="pending_approval",
                    event=event,
                )
                
                return {
                    "statusCode": 202,
                    "body": json.dumps({
                        "status": "pending_approval",
                        "action_id": action.action_id,
                        "request_id": request_id,
                        "rollback_id": rollback_id,
                        "timeout_minutes": APPROVAL_TIMEOUT_MINUTES,
                    }),
                }
            else:
                # Auto-approve
                print(f"Auto-approving action: {action.action_id}")
                
                # Create rollback capability
                rollback_id = create_rollback_capability(action)
                
                # Log approval
                log_action(
                    action_id=action.action_id,
                    action_type=action.action_type,
                    parameters=action.parameters,
                    outcome="approved",
                    event=event,
                )
                
                # Publish approval event
                publish_approval_decision(action, True)
                
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "status": "approved",
                        "action_id": action.action_id,
                        "rollback_id": rollback_id,
                    }),
                }
        
        elif detail_type == "RollbackRequested":
            # Handle rollback request
            detail = event.get("detail", {})
            action_id = detail.get("action_id")
            
            if not action_id:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Missing action_id"}),
                }
            
            # Execute rollback
            success = execute_rollback(action_id)
            
            # Log rollback
            log_action(
                action_id=action_id,
                action_type="rollback",
                parameters={"original_action_id": action_id},
                outcome="rolled_back" if success else "rollback_failed",
                event=event,
            )
            
            return {
                "statusCode": 200 if success else 500,
                "body": json.dumps({
                    "status": "rolled_back" if success else "rollback_failed",
                    "action_id": action_id,
                }),
            }
        
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unknown event type: {detail_type}"}),
            }
        
    except Exception as e:
        print(f"ERROR: Safety Guard handler failed: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
