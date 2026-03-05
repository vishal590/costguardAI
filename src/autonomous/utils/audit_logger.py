"""
Audit Logging Utility for Autonomous Actions

Provides structured audit logging for all autonomous actions with user tracking,
source IP, timestamps, parameters, and outcomes. Logs are retained for 90 days
in CloudWatch Logs.

Requirements: 12.5, 12.6
"""

import json
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
ACTION_HISTORY_TABLE = os.environ.get("ACTION_HISTORY_TABLE", "costguard-action-history")

# AWS clients
dynamodb = boto3.resource("dynamodb")
action_history_table = dynamodb.Table(ACTION_HISTORY_TABLE)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def get_current_user(event: Optional[Dict[str, Any]] = None) -> str:
    """
    Extract current user from Lambda event.
    
    Args:
        event: Lambda event (API Gateway or EventBridge)
        
    Returns:
        User identifier or 'system' for automated actions
    """
    if not event:
        return "system"
    
    # Check for API Gateway request context
    request_context = event.get("requestContext", {})
    
    # Try to get user from authorizer
    authorizer = request_context.get("authorizer", {})
    if authorizer:
        # Check for API key name
        api_key_id = authorizer.get("apiKeyId")
        if api_key_id:
            return f"api_key:{api_key_id}"
        
        # Check for IAM user
        iam_user = authorizer.get("iam", {}).get("userId")
        if iam_user:
            return f"iam:{iam_user}"
    
    # Check for identity
    identity = request_context.get("identity", {})
    user_arn = identity.get("userArn")
    if user_arn:
        return user_arn
    
    # For EventBridge events, use source
    source = event.get("source")
    if source:
        return f"eventbridge:{source}"
    
    return "system"


def get_source_ip(event: Optional[Dict[str, Any]] = None) -> str:
    """
    Extract source IP address from Lambda event.
    
    Args:
        event: Lambda event (API Gateway or EventBridge)
        
    Returns:
        Source IP address or 'internal' for automated actions
    """
    if not event:
        return "internal"
    
    # Check for API Gateway request context
    request_context = event.get("requestContext", {})
    identity = request_context.get("identity", {})
    
    source_ip = identity.get("sourceIp")
    if source_ip:
        return source_ip
    
    # For EventBridge events, return internal
    if event.get("source"):
        return "internal"
    
    return "internal"


def log_action(
    action_id: str,
    action_type: str,
    parameters: Dict[str, Any],
    outcome: str,
    user: Optional[str] = None,
    source_ip: Optional[str] = None,
    event: Optional[Dict[str, Any]] = None,
    cost_impact: Optional[float] = None,
    performance_impact: Optional[float] = None,
) -> None:
    """
    Log autonomous action for audit trail.
    
    Creates structured audit log with all required fields and stores in both
    CloudWatch Logs and DynamoDB action history table. Logs are retained for
    90 days.
    
    Args:
        action_id: Unique action identifier
        action_type: Type of action (schedule, spot_migration, right_sizing)
        parameters: Action parameters
        outcome: Action outcome (success, failed, rolled_back)
        user: User who initiated action (optional, will be extracted from event)
        source_ip: Source IP address (optional, will be extracted from event)
        event: Lambda event for extracting user and IP (optional)
        cost_impact: Cost impact in dollars (optional)
        performance_impact: Performance impact percentage (optional)
        
    Requirements: 12.5, 12.6
    """
    try:
        # Extract user and source IP if not provided
        if user is None:
            user = get_current_user(event)
        
        if source_ip is None:
            source_ip = get_source_ip(event)
        
        # Create audit log entry
        timestamp = datetime.utcnow()
        audit_log = {
            "timestamp": timestamp.isoformat(),
            "action_id": action_id,
            "action_type": action_type,
            "parameters": parameters,
            "outcome": outcome,
            "user": user,
            "source_ip": source_ip,
            "audit": True,
        }
        
        # Add optional fields
        if cost_impact is not None:
            audit_log["cost_impact"] = cost_impact
        
        if performance_impact is not None:
            audit_log["performance_impact"] = performance_impact
        
        # Log to CloudWatch Logs (structured JSON)
        logger.info(json.dumps(audit_log, cls=DecimalEncoder))
        
        # Store in DynamoDB for queryable audit trail
        # TTL set to 90 days from now
        ttl = int((timestamp + timedelta(days=90)).timestamp())
        
        dynamodb_item = {
            "action_id": action_id,
            "timestamp": timestamp.isoformat(),
            "action_type": action_type,
            "status": outcome,
            "parameters": parameters,
            "user": user,
            "source_ip": source_ip,
            "audit": True,
            "ttl": ttl,
        }
        
        # Add optional fields
        if cost_impact is not None:
            dynamodb_item["actual_cost_impact"] = Decimal(str(cost_impact))
        
        if performance_impact is not None:
            dynamodb_item["performance_impact"] = Decimal(str(performance_impact))
        
        # Store in DynamoDB
        action_history_table.put_item(Item=dynamodb_item)
        
        logger.info(f"Audit log created for action {action_id}")
        
    except Exception as e:
        # Log error but don't fail the action
        logger.error(f"Failed to create audit log: {e}")


def query_audit_logs(
    action_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    user: Optional[str] = None,
    limit: int = 100,
) -> list:
    """
    Query audit logs from DynamoDB.
    
    Args:
        action_type: Filter by action type (optional)
        start_date: Filter by start date (optional)
        end_date: Filter by end date (optional)
        user: Filter by user (optional)
        limit: Maximum number of results (default 100)
        
    Returns:
        List of audit log entries
        
    Requirements: 12.5
    """
    try:
        # Build query parameters
        filter_expression = "audit = :audit"
        expression_values = {":audit": True}
        expression_names = {}
        
        # Add action type filter
        if action_type:
            filter_expression += " AND action_type = :action_type"
            expression_values[":action_type"] = action_type
        
        # Add date range filter
        if start_date:
            filter_expression += " AND #ts >= :start_date"
            expression_values[":start_date"] = start_date.isoformat()
            expression_names["#ts"] = "timestamp"
        
        if end_date:
            filter_expression += " AND #ts <= :end_date"
            expression_values[":end_date"] = end_date.isoformat()
            if "#ts" not in expression_names:
                expression_names["#ts"] = "timestamp"
        
        # Add user filter
        if user:
            filter_expression += " AND #user = :user"
            expression_values[":user"] = user
            expression_names["#user"] = "user"
        
        # Query DynamoDB
        # Note: This uses scan for simplicity. In production, consider using GSI
        scan_kwargs = {
            "FilterExpression": filter_expression,
            "ExpressionAttributeValues": expression_values,
            "Limit": limit,
        }
        
        # Only add ExpressionAttributeNames if we have any
        if expression_names:
            scan_kwargs["ExpressionAttributeNames"] = expression_names
        
        response = action_history_table.scan(**scan_kwargs)
        
        items = response.get("Items", [])
        
        # Sort by timestamp descending
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return items
        
    except Exception as e:
        logger.error(f"Failed to query audit logs: {e}")
        return []


def verify_audit_log_retention() -> Dict[str, Any]:
    """
    Verify that audit logs are being retained for 90 days.
    
    Returns:
        Dictionary with retention verification results
        
    Requirements: 12.6
    """
    try:
        # Query recent audit logs
        now = datetime.utcnow()
        start_date = now - timedelta(days=90)
        
        logs = query_audit_logs(start_date=start_date, limit=10)
        
        # Check TTL values
        retention_ok = True
        for log in logs:
            ttl = log.get("ttl")
            if ttl:
                expiration = datetime.fromtimestamp(int(ttl))
                log_timestamp = datetime.fromisoformat(log.get("timestamp"))
                retention_days = (expiration - log_timestamp).days
                
                # Verify retention is approximately 90 days
                if retention_days < 85 or retention_days > 95:
                    retention_ok = False
                    logger.warning(
                        f"Audit log {log.get('action_id')} has retention of {retention_days} days"
                    )
        
        return {
            "retention_ok": retention_ok,
            "logs_checked": len(logs),
            "expected_retention_days": 90,
        }
        
    except Exception as e:
        logger.error(f"Failed to verify audit log retention: {e}")
        return {
            "retention_ok": False,
            "error": str(e),
        }
