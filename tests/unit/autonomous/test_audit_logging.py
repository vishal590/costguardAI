"""
Unit tests for audit logging.

Tests audit log creation, querying, and retention.

Requirements: 12.5, 12.6
"""

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest
from moto import mock_aws
import boto3

from autonomous.utils.audit_logger import (
    log_action,
    query_audit_logs,
    verify_audit_log_retention,
    get_current_user,
    get_source_ip,
)


@mock_aws
def test_log_action_creates_audit_entry():
    """
    Test that log_action creates audit entry in DynamoDB.
    
    Requirements: 12.5
    """
    # Create test table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="costguard-action-history",
        KeySchema=[
            {"AttributeName": "action_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "action_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    
    # Create audit log
    action_id = "act_test_123"
    action_type = "schedule"
    parameters = {"instance_type": "g4dn.xlarge"}
    outcome = "success"
    user = "test-user"
    source_ip = "192.168.1.1"
    
    log_action(
        action_id=action_id,
        action_type=action_type,
        parameters=parameters,
        outcome=outcome,
        user=user,
        source_ip=source_ip,
    )
    
    # Verify entry was created
    response = table.scan(FilterExpression="action_id = :action_id", ExpressionAttributeValues={":action_id": action_id})
    items = response["Items"]
    
    assert len(items) == 1
    item = items[0]
    
    assert item["action_id"] == action_id
    assert item["action_type"] == action_type
    assert item["status"] == outcome
    assert item["user"] == user
    assert item["source_ip"] == source_ip
    assert item["audit"] is True
    assert "ttl" in item
    
    print("✓ Audit log entry created successfully")


def test_get_current_user_from_api_gateway():
    """
    Test extracting user from API Gateway event.
    
    Requirements: 12.5
    """
    # API Gateway event with API key
    event = {
        "requestContext": {
            "authorizer": {
                "apiKeyId": "abc123",
            },
        },
    }
    
    user = get_current_user(event)
    assert user == "api_key:abc123"
    
    # API Gateway event with IAM user
    event = {
        "requestContext": {
            "authorizer": {
                "iam": {
                    "userId": "AIDAI123456789",
                },
            },
        },
    }
    
    user = get_current_user(event)
    assert user == "iam:AIDAI123456789"
    
    # EventBridge event
    event = {
        "source": "costguard.autonomous.scheduler",
    }
    
    user = get_current_user(event)
    assert user == "eventbridge:costguard.autonomous.scheduler"
    
    # No event
    user = get_current_user(None)
    assert user == "system"
    
    print("✓ User extraction works correctly")


def test_get_source_ip_from_api_gateway():
    """
    Test extracting source IP from API Gateway event.
    
    Requirements: 12.5
    """
    # API Gateway event with source IP
    event = {
        "requestContext": {
            "identity": {
                "sourceIp": "192.168.1.1",
            },
        },
    }
    
    source_ip = get_source_ip(event)
    assert source_ip == "192.168.1.1"
    
    # EventBridge event
    event = {
        "source": "costguard.autonomous.scheduler",
    }
    
    source_ip = get_source_ip(event)
    assert source_ip == "internal"
    
    # No event
    source_ip = get_source_ip(None)
    assert source_ip == "internal"
    
    print("✓ Source IP extraction works correctly")


@mock_aws
def test_audit_log_includes_cost_impact():
    """
    Test that audit logs include cost impact.
    
    Requirements: 12.5
    """
    # Create test table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="costguard-action-history",
        KeySchema=[
            {"AttributeName": "action_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "action_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    
    # Create audit log with cost impact
    action_id = "act_cost_test"
    cost_impact = -12.50
    performance_impact = 0.02
    
    log_action(
        action_id=action_id,
        action_type="right_sizing",
        parameters={"instance_type": "g4dn.xlarge"},
        outcome="success",
        user="test-user",
        source_ip="192.168.1.1",
        cost_impact=cost_impact,
        performance_impact=performance_impact,
    )
    
    # Verify cost impact is stored
    response = table.scan(FilterExpression="action_id = :action_id", ExpressionAttributeValues={":action_id": action_id})
    items = response["Items"]
    
    assert len(items) == 1
    item = items[0]
    
    assert float(item["actual_cost_impact"]) == cost_impact
    assert float(item["performance_impact"]) == performance_impact
    
    print("✓ Audit log includes cost and performance impact")


@mock_aws
def test_audit_log_retention_90_days():
    """
    Test that audit logs have 90-day TTL.
    
    Requirements: 12.6
    """
    # Create test table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="costguard-action-history",
        KeySchema=[
            {"AttributeName": "action_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "action_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    
    # Create audit log
    action_id = "act_ttl_test"
    now = datetime.utcnow()
    
    log_action(
        action_id=action_id,
        action_type="schedule",
        parameters={"test": "data"},
        outcome="success",
        user="test-user",
        source_ip="192.168.1.1",
    )
    
    # Verify TTL is set to 90 days
    response = table.scan(FilterExpression="action_id = :action_id", ExpressionAttributeValues={":action_id": action_id})
    items = response["Items"]
    
    assert len(items) == 1
    item = items[0]
    
    ttl = int(item["ttl"])
    expected_expiration = now + timedelta(days=90)
    actual_expiration = datetime.fromtimestamp(ttl)
    
    # Allow 1 minute tolerance
    time_diff = abs((actual_expiration - expected_expiration).total_seconds())
    assert time_diff < 60, "TTL should be set to 90 days from now"
    
    print("✓ Audit logs have 90-day retention")


@mock_aws
def test_query_audit_logs():
    """
    Test querying audit logs by action type and date range.
    
    Requirements: 12.5
    """
    # Create test table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="costguard-action-history",
        KeySchema=[
            {"AttributeName": "action_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "action_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    
    # Create multiple audit logs
    now = datetime.utcnow()
    
    for i in range(5):
        log_action(
            action_id=f"act_query_test_{i}",
            action_type="schedule" if i % 2 == 0 else "right_sizing",
            parameters={"test": f"data_{i}"},
            outcome="success",
            user="test-user",
            source_ip="192.168.1.1",
        )
    
    # Query all audit logs
    logs = query_audit_logs(limit=10)
    assert len(logs) >= 5
    
    # Query by action type
    schedule_logs = query_audit_logs(action_type="schedule", limit=10)
    assert all(log["action_type"] == "schedule" for log in schedule_logs)
    
    # Query by date range
    start_date = now - timedelta(minutes=5)
    end_date = now + timedelta(minutes=5)
    recent_logs = query_audit_logs(start_date=start_date, end_date=end_date, limit=10)
    assert len(recent_logs) >= 5
    
    print("✓ Audit log querying works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
