"""
Property-based tests for ApprovalManager.

Tests universal properties that should hold for approval workflow.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, UTC
from src.services.approval_manager import ApprovalManager
from src.utils.types import ApprovalRequest, ApprovalResponse, PlannedAction, Resource


# Feature: automated-cost-prevention, Property 11: Approval Timeout Handling
# Approval requests should timeout and default to not approved


@settings(max_examples=100)
@given(
    num_actions=st.integers(min_value=1, max_value=10),
    timeout_minutes=st.integers(min_value=1, max_value=60)
)
def test_property_approval_timeout_defaults_to_not_approved(num_actions, timeout_minutes):
    """
    Property 11: Approval Timeout Handling
    
    For any approval request:
    - If no response within timeout, should default to not approved
    - Timeout should be respected
    - ApprovalResponse should indicate not approved
    
    Validates: Requirements 7.5
    """
    mock_sns = Mock()
    mock_dynamodb = Mock()
    
    # Mock DynamoDB to always return pending status (no approval)
    mock_dynamodb.get_item.return_value = {
        'Item': {
            'request_id': {'S': 'test-request'},
            'status': {'S': 'pending'}
        }
    }
    
    manager = ApprovalManager(mock_sns, mock_dynamodb)
    manager.approval_topic_arn = "arn:aws:sns:us-east-1:123456789012:test"
    
    # Create actions
    actions = []
    for i in range(num_actions):
        resource = Resource(
            resource_id=f'resource-{i}',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        actions.append({
            'resource': resource,
            'action': 'stop',
            'estimated_savings': 10.0 * (i + 1)
        })
    
    # Request approval
    request = manager.request_approval(actions)
    
    # Verify request created
    assert isinstance(request, ApprovalRequest)
    assert len(request.actions) == num_actions
    
    # Simulate timeout by mocking time
    with patch('time.sleep'):
        with patch('src.services.approval_manager.datetime') as mock_datetime:
            start = datetime.now(UTC)
            # Simulate time passing beyond timeout
            # Need 3 calls: initial, loop check, final timestamp
            mock_datetime.now.side_effect = [
                start,  # Initial check
                start + timedelta(minutes=timeout_minutes + 1),  # After timeout (loop check)
                start + timedelta(minutes=timeout_minutes + 1)   # Final timestamp creation
            ]
            mock_datetime.UTC = UTC
            
            response = manager.wait_for_approval(request.request_id, timeout_minutes)
    
    # Verify timeout defaults to not approved
    assert isinstance(response, ApprovalResponse)
    assert response.request_id == request.request_id
    assert response.approved is False
    assert response.approved_by is None


@settings(max_examples=100)
@given(
    num_actions=st.integers(min_value=1, max_value=10),
    approved=st.booleans(),
    approver=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N')))
)
def test_property_approval_within_timeout_is_processed(num_actions, approved, approver):
    """
    Property 11: Approval Within Timeout
    
    For any approval request:
    - If response received within timeout, should be processed
    - Approved status should match response
    - Approver should be recorded
    
    Validates: Requirements 7.3, 7.4
    """
    mock_sns = Mock()
    mock_dynamodb = Mock()
    
    manager = ApprovalManager(mock_sns, mock_dynamodb)
    manager.approval_topic_arn = "arn:aws:sns:us-east-1:123456789012:test"
    
    # Create actions
    actions = []
    for i in range(num_actions):
        resource = Resource(
            resource_id=f'resource-{i}',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        actions.append({
            'resource': resource,
            'action': 'stop',
            'estimated_savings': 10.0 * (i + 1)
        })
    
    # Request approval
    request = manager.request_approval(actions)
    
    # Mock DynamoDB to return approved/denied status immediately
    status = 'approved' if approved else 'denied'
    mock_dynamodb.get_item.return_value = {
        'Item': {
            'request_id': {'S': request.request_id},
            'status': {'S': status},
            'approved_by': {'S': approver},
            'response_timestamp': {'S': datetime.now(UTC).isoformat()}
        }
    }
    
    # Wait for approval (should return immediately)
    with patch('time.sleep'):
        response = manager.wait_for_approval(request.request_id, timeout_minutes=30)
    
    # Verify response matches approval status
    assert isinstance(response, ApprovalResponse)
    assert response.request_id == request.request_id
    assert response.approved == approved
    assert response.approved_by == approver


@settings(max_examples=100)
@given(
    num_actions=st.integers(min_value=1, max_value=10),
    savings_per_action=st.floats(min_value=0.01, max_value=1000.0)
)
def test_property_approval_request_structure(num_actions, savings_per_action):
    """
    Property: Approval Request Structure
    
    For any approval request:
    - Should have unique request_id
    - Should contain all actions
    - Total savings should equal sum of individual savings
    - Should have expiration time
    
    Validates: Requirements 7.1
    """
    mock_sns = Mock()
    mock_dynamodb = Mock()
    
    manager = ApprovalManager(mock_sns, mock_dynamodb)
    manager.approval_topic_arn = "arn:aws:sns:us-east-1:123456789012:test"
    
    # Create actions
    actions = []
    expected_total = 0.0
    for i in range(num_actions):
        resource = Resource(
            resource_id=f'resource-{i}',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        actions.append({
            'resource': resource,
            'action': 'stop',
            'estimated_savings': savings_per_action
        })
        expected_total += savings_per_action
    
    # Request approval
    request = manager.request_approval(actions)
    
    # Verify request structure
    assert isinstance(request, ApprovalRequest)
    assert request.request_id is not None
    assert len(request.request_id) > 0
    assert len(request.actions) == num_actions
    assert abs(request.total_estimated_savings - expected_total) < 0.01
    assert request.expires_at is not None
    
    # Verify all actions are PlannedAction objects
    for action in request.actions:
        assert isinstance(action, PlannedAction)
        assert action.resource_id is not None
        assert action.action == 'stop'
        assert action.estimated_savings == savings_per_action


@settings(max_examples=100)
@given(
    approved=st.booleans(),
    has_approver=st.booleans()
)
def test_property_process_approval_response_consistency(approved, has_approver):
    """
    Property: Process Approval Response Consistency
    
    For any approval response:
    - Should create ApprovalResponse with correct status
    - Should store response in DynamoDB
    - Should handle missing approver gracefully
    
    Validates: Requirements 7.6
    """
    mock_sns = Mock()
    mock_dynamodb = Mock()
    
    manager = ApprovalManager(mock_sns, mock_dynamodb)
    
    request_id = 'test-request-123'
    approver = 'admin@example.com' if has_approver else None
    
    # Process approval response
    response = manager.process_approval_response(
        request_id=request_id,
        approved=approved,
        approved_by=approver
    )
    
    # Verify response structure
    assert isinstance(response, ApprovalResponse)
    assert response.request_id == request_id
    assert response.approved == approved
    assert response.approved_by == approver
    assert response.timestamp is not None
    
    # Verify DynamoDB update called
    mock_dynamodb.update_item.assert_called_once()
    call_args = mock_dynamodb.update_item.call_args
    
    # Verify correct status stored
    expected_status = 'approved' if approved else 'denied'
    assert call_args[1]['ExpressionAttributeValues'][':status']['S'] == expected_status
    
    # Verify approver stored (or 'unknown' if None)
    expected_approver = approver if approver else 'unknown'
    assert call_args[1]['ExpressionAttributeValues'][':approved_by']['S'] == expected_approver


@settings(max_examples=100)
@given(
    num_actions=st.integers(min_value=1, max_value=10)
)
def test_property_sns_notification_sent(num_actions):
    """
    Property: SNS Notification Sent
    
    For any approval request:
    - SNS notification should be sent if topic ARN configured
    - Notification should contain request details
    - Notification should include all actions
    
    Validates: Requirements 7.1
    """
    mock_sns = Mock()
    mock_dynamodb = Mock()
    
    manager = ApprovalManager(mock_sns, mock_dynamodb)
    manager.approval_topic_arn = "arn:aws:sns:us-east-1:123456789012:test"
    
    # Create actions
    actions = []
    for i in range(num_actions):
        resource = Resource(
            resource_id=f'resource-{i}',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        actions.append({
            'resource': resource,
            'action': 'stop',
            'estimated_savings': 10.0
        })
    
    # Request approval
    request = manager.request_approval(actions)
    
    # Verify SNS publish called
    mock_sns.publish.assert_called_once()
    call_args = mock_sns.publish.call_args
    
    # Verify notification contains key information
    assert call_args[1]['TopicArn'] == manager.approval_topic_arn
    message = call_args[1]['Message']
    assert request.request_id in message
    assert str(num_actions) in message
    assert 'Approval Required' in call_args[1]['Subject']


@settings(max_examples=100)
@given(
    num_actions=st.integers(min_value=1, max_value=10)
)
def test_property_no_notification_without_topic_arn(num_actions):
    """
    Property: No Notification Without Topic ARN
    
    For any approval request:
    - If no topic ARN configured, should not send notification
    - Should still create approval request
    
    Validates: Requirements 7.1
    """
    mock_sns = Mock()
    mock_dynamodb = Mock()
    
    manager = ApprovalManager(mock_sns, mock_dynamodb)
    manager.approval_topic_arn = None  # No topic configured
    
    # Create actions
    actions = []
    for i in range(num_actions):
        resource = Resource(
            resource_id=f'resource-{i}',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        actions.append({
            'resource': resource,
            'action': 'stop',
            'estimated_savings': 10.0
        })
    
    # Request approval
    request = manager.request_approval(actions)
    
    # Verify request created but no SNS notification sent
    assert isinstance(request, ApprovalRequest)
    mock_sns.publish.assert_not_called()
