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
from botocore.exceptions import ClientError

from autonomous.action_executor import validate_parameters
from autonomous.utils.cloudwatch_metrics import get_metrics_publisher
from autonomous.utils.audit_logger import log_action, get_current_user, get_source_ip


# Environment variables
ACTION_HISTORY_TABLE = os.environ.get("ACTION_HISTORY_TABLE", "costguard-action-history")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "costguard-autonomous-events")
APPROVAL_SNS_TOPIC = os.environ.get("APPROVAL_SNS_TOPIC", "")
DRY_RUN_MODE = os.environ.get("DRY_RUN_MODE", "false").lower() == "true"
APPROVAL_TIMEOUT_MINUTES = int(os.environ.get("APPROVAL_TIMEOUT_MINUTES", "15"))
FREE_TIER_BUDGET_LIMIT = float(os.environ.get("FREE_TIER_BUDGET_LIMIT", "5.0"))
APPROVAL_REQUIRED_ACTIONS = ["schedule", "spot_migration", "right_sizing", "ondemand_fallback"]
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
            "parameters": json.loads(json.dumps(action.parameters, default=float), parse_float=Decimal),
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
    secret = APPROVAL_SECRET_KEY
    if os.environ.get("APPROVAL_SECRET_ARN"):
        secret = boto3.client("secretsmanager").get_secret_value(
            SecretId=os.environ["APPROVAL_SECRET_ARN"])["SecretString"]
    signature = hmac.new(
        secret.encode('utf-8'),
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

Submit POST /api/autonomous/approve-action with this JSON body:
{{"request_id": "{action.request_id}", "action_id": "{action.action_id}", "signature": "{signature}", "approved": true}}

To reject this action, use the same body with "approved": false.

This request will expire in {APPROVAL_TIMEOUT_MINUTES} minutes.
"""
        
        # Store approval request in DynamoDB
        ttl = int(time.time()) + APPROVAL_TIMEOUT_MINUTES * 60
        
        item = {
            "action_id": action.action_id,
            "timestamp": action.timestamp.isoformat(),
            "action_type": action.action_type,
            "status": "pending_approval",
            "parameters": json.loads(json.dumps(action.parameters, default=float), parse_float=Decimal),
            "confidence_score": Decimal(str(action.confidence_score)),
            "expected_cost_impact": Decimal(str(action.expected_cost_impact)),
            "approval_required": True,
            "approval_request_id": action.request_id,
            "approval_signature": signature,
            "approval_expires_at": ttl,
            "ttl": int(time.time()) + 90 * 86400,
        }
        
        # Producer IDs and timestamps are stable across EventBridge retries.
        try:
            action_history_table.put_item(Item=item, ConditionExpression="attribute_not_exists(action_id)")
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            existing = action_history_table.get_item(Key={"action_id": action.action_id,
                "timestamp": action.timestamp.isoformat()}, ConsistentRead=True)["Item"]
            if existing.get("approval_request_id") != action.request_id:
                raise ValueError("Action already has a different approval request")
            if existing.get("action_type") != action.action_type or existing.get("parameters") != item["parameters"]:
                raise ValueError("Approval request replay changed the action parameters")
            if existing.get("status") != "pending_approval":
                return action.request_id
            # A failed SNS publish must be retryable even after storing the row.

        # Persist the request before a recipient can respond to the notification.
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
        
        # Add rollback metadata without replacing a pending approval stored under
        # the same action/timestamp key or extending its approval deadline.
        ttl = int(time.time()) + 7 * 24 * 60 * 60
        action_history_table.update_item(
            Key={"action_id": action.action_id, "timestamp": action.timestamp.isoformat()},
            UpdateExpression=(
                "SET rollback_id = if_not_exists(rollback_id, :rollback_id), rollback_created = :created, "
                "action_type = if_not_exists(action_type, :action_type), "
                "#parameters = if_not_exists(#parameters, :parameters), "
                "#ttl = if_not_exists(#ttl, :ttl)"
            ),
            ExpressionAttributeNames={"#parameters": "parameters", "#ttl": "ttl"},
            ExpressionAttributeValues={
                ":rollback_id": rollback_id,
                ":created": True,
                ":action_type": action.action_type,
                ":parameters": json.loads(json.dumps(action.parameters, default=float), parse_float=Decimal),
                ":ttl": ttl,
            },
        )

        print(f"Rollback capability created: {rollback_id}")
        
        return rollback_id
        
    except Exception as e:
        print(f"ERROR: Failed to create rollback capability: {e}")
        raise


def execute_rollback(action_id: str) -> bool:
    """Submit resource restoration to the executor; never mark metadata restored."""
    query = {"KeyConditionExpression": Key("action_id").eq(action_id), "ConsistentRead": True}
    while True:
        page = action_history_table.query(**query)
        for item in page.get("Items", []):
            if item.get("approval_decision") == "approved" and item.get("rollback_created"):
                publish_execution(item, "ExecuteRollback")
                return True
        if not page.get("LastEvaluatedKey"):
            return False
        query["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def publish_execution(item, detail_type="ExecuteAction"):
    response = events_client.put_events(Entries=[{
        "Source": "costguard.autonomous.safetyguard", "DetailType": detail_type,
        "Detail": json.dumps({"action_id": item["action_id"], "action_timestamp": item["timestamp"]}),
        "EventBusName": EVENT_BUS_NAME}])
    if response.get("FailedEntryCount", 0):
        raise RuntimeError("Execution event was not accepted")


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


def handle_approval_response(event: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a signed API decision to its pending request, at most once."""
    detail = event.get("detail", {})
    request_id = detail.get("request_id")
    action_id = detail.get("action_id")
    signature = detail.get("signature")
    approved = detail.get("approved")

    def response(code, message):
        return {"statusCode": code, "body": json.dumps({"error": message})}

    expected_decision = event.get("detail-type") == "ActionApproved"
    if event.get("source") != "costguard.autonomous.api":
        return response(400, "Approval decisions must originate from the API")
    if not (isinstance(request_id, str) and request_id.strip()
            and isinstance(action_id, str) and action_id.strip()
            and isinstance(signature, str) and signature.strip()
            and isinstance(approved, bool) and approved == expected_decision):
        return response(400, "Invalid approval decision")

    # Audit entries share the action partition. Find the request rather than
    # assuming the first or newest item is the pending approval.
    query = {"KeyConditionExpression": Key("action_id").eq(action_id),
             "ConsistentRead": True, "ScanIndexForward": False}
    item = None
    while True:
        page = action_history_table.query(**query)
        item = next((record for record in page.get("Items", [])
                     if record.get("approval_request_id") == request_id), None)
        if item or not page.get("LastEvaluatedKey"):
            break
        query["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    if item is None:
        return response(404, "Approval request not found")
    stored_signature = item.get("approval_signature")
    if not (isinstance(stored_signature, str)
            and hmac.compare_digest(signature.encode("utf-8"), stored_signature.encode("utf-8"))
            and validate_approval_signature(request_id, action_id, signature)):
        return response(403, "Invalid approval signature")

    decision = "approved" if approved else "rejected"
    # EventBridge can deliver a decision again. Never reverse an applied decision.
    if item.get("approval_decision", item.get("status")) == decision:
        if approved:
            publish_execution(item)
        return {"statusCode": 200, "body": json.dumps({"status": decision,
                "action_id": action_id, "request_id": request_id, "duplicate": True})}
    if item.get("status") != "pending_approval":
        return response(409, "Approval request is no longer pending")
    now = int(time.time())
    if int(item.get("approval_expires_at", item.get("ttl", 0))) <= now:
        return response(410, "Approval request expired")
    try:
        action_history_table.update_item(
            Key={"action_id": action_id, "timestamp": item["timestamp"]},
            UpdateExpression="SET #status = :decision, approval_decision = :decision, approval_decided_at = :decided_at",
            ConditionExpression=("#status = :pending AND approval_request_id = :request_id "
                                 "AND approval_signature = :signature AND approval_expires_at > :now"),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":decision": decision, ":pending": "pending_approval",
                ":request_id": request_id, ":signature": signature, ":now": now,
                ":decided_at": datetime.utcnow().isoformat()},
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return response(409, "Approval request changed before the decision was applied")
        raise
    if approved:
        publish_execution(item)
    log_action(action_id=action_id, action_type=item.get("action_type"),
               parameters=item.get("parameters", {}), outcome=decision, event=event)
    return {"statusCode": 200, "body": json.dumps({"status": decision,
            "action_id": action_id, "request_id": request_id})}


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
        print(f"Safety Guard event: {event.get('detail-type')}")
        
        # Get metrics publisher
        metrics = get_metrics_publisher()
        
        # Determine event type
        detail_type = event.get("detail-type", "")
        
        if detail_type in ("ActionApproved", "ActionRejected"):
            return handle_approval_response(event)

        if detail_type == "ScheduleRecommendation":
            detail = event["detail"]
            workload = detail.get("workload")
            if not workload:
                return {"statusCode": 200, "body": json.dumps({"status": "recommendation_only"})}
            action_id = "act_" + detail["recommendation_id"]
            event = dict(event, **{"detail-type": "ActionRequest", "detail": {
                "request_id": "req_" + detail["recommendation_id"], "action_id": action_id,
                "action_type": "schedule", "parameters": workload,
                "timestamp": detail["timestamp"], "approval_required": True,
                "confidence_score": detail["confidence_score"],
                "expected_cost_impact": -detail["expected_savings_dollars"]}})
            detail_type = "ActionRequest"

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
            
            if detail.get("timestamp"):
                action.timestamp = datetime.fromisoformat(detail["timestamp"].replace("Z", "+00:00"))
            if not action.action_id or not action.request_id:
                return {"statusCode": 400, "body": json.dumps({"error": "Action and request IDs are required"})}
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
            
            # Validate the executable contract before requesting approval.
            try:
                validate_parameters(action.action_type, action.parameters)
            except (ValueError, KeyError, TypeError) as error:
                return {"statusCode": 400, "body": json.dumps({"status": "rejected", "error": str(error)})}

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
                
                stored = action_history_table.get_item(Key={"action_id": action.action_id,
                    "timestamp": action.timestamp.isoformat()}, ConsistentRead=True).get("Item")
                if isinstance(stored, dict) and stored.get("status") != "pending_approval":
                    return {"statusCode": 200, "body": json.dumps({"status": stored.get("status"),
                        "action_id": action.action_id, "request_id": request_id})}

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
                outcome="rollback_submitted" if success else "rollback_failed",
                event=event,
            )
            
            return {
                "statusCode": 202 if success else 404,
                "body": json.dumps({
                    "status": "rollback_submitted" if success else "rollback_failed",
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
        
        if event.get("detail-type"):
            raise
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
