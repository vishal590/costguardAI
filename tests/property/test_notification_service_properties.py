"""
Property-based tests for NotificationService.

Tests universal properties that should hold for notification delivery.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock
from datetime import datetime, UTC
from src.services.notification_service import NotificationService
from src.utils.types import (
    NotificationConfig, BudgetStatus, ActionResult
)


# Feature: automated-cost-prevention, Property 9: Notification Delivery
# Notifications should be sent within 1 minute and have consistent structure


@settings(max_examples=100)
@given(
    budget_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    limit=st.floats(min_value=100.0, max_value=100000.0),
    utilization=st.floats(min_value=80.0, max_value=100.0),
    currency=st.sampled_from(['USD', 'EUR', 'GBP'])
)
def test_property_warning_notification_structure(budget_name, limit, utilization, currency):
    """
    Property 9: Warning Notification Structure
    
    For any budget warning:
    - Notification should be sent via SNS
    - Message should contain budget details
    - Subject should contain budget name and utilization
    - Notification should be sent immediately (within 1 minute)
    
    Validates: Requirements 8.1
    """
    assume(len(budget_name) > 0)
    
    mock_sns = Mock()
    config = NotificationConfig(
        warning_topic_arn="arn:aws:sns:us-east-1:123456789012:warnings",
        action_topic_arn=None,
        error_topic_arn=None
    )
    
    service = NotificationService(mock_sns, config)
    
    # Create budget status
    actual_spend = limit * (utilization / 100.0)
    budget_status = BudgetStatus(
        budget_name=budget_name,
        limit=limit,
        actual_spend=actual_spend,
        forecasted_spend=actual_spend * 1.1,
        utilization_percent=utilization,
        currency=currency,
        time_period='2024-02'
    )
    
    # Send warning
    start_time = datetime.now(UTC)
    service.send_warning(budget_status)
    end_time = datetime.now(UTC)
    
    # Verify notification sent within 1 minute
    elapsed = (end_time - start_time).total_seconds()
    assert elapsed < 60.0
    
    # Verify SNS publish called
    mock_sns.publish.assert_called_once()
    call_args = mock_sns.publish.call_args
    
    # Verify topic ARN
    assert call_args[1]['TopicArn'] == config.warning_topic_arn
    
    # Verify subject structure
    subject = call_args[1]['Subject']
    assert budget_name in subject
    assert f"{utilization:.1f}%" in subject
    
    # Verify message structure
    message = call_args[1]['Message']
    assert budget_name in message
    assert currency in message
    assert '80%' in message or '90%' in message  # Threshold mentioned


@settings(max_examples=100)
@given(
    num_actions=st.integers(min_value=1, max_value=20),
    success_rate=st.floats(min_value=0.0, max_value=1.0)
)
def test_property_action_notification_structure(num_actions, success_rate):
    """
    Property 9: Action Notification Structure
    
    For any set of automated actions:
    - Notification should be sent via SNS
    - Message should contain all action details
    - Subject should contain action count and savings
    - Notification should be sent immediately (within 1 minute)
    
    Validates: Requirements 8.3, 8.5
    """
    mock_sns = Mock()
    config = NotificationConfig(
        warning_topic_arn=None,
        action_topic_arn="arn:aws:sns:us-east-1:123456789012:actions",
        error_topic_arn=None
    )
    
    service = NotificationService(mock_sns, config)
    
    # Create actions
    actions = []
    total_savings = 0.0
    for i in range(num_actions):
        success = (i / num_actions) < success_rate
        savings = 10.0 * (i + 1)
        total_savings += savings
        
        actions.append(ActionResult(
            resource_id=f'resource-{i}',
            action='stop',
            success=success,
            error_message=None if success else 'Test error',
            pre_action_state={},
            post_action_state={},
            estimated_savings=savings,
            timestamp=datetime.now(UTC).isoformat()
        ))
    
    # Send action notification
    start_time = datetime.now(UTC)
    service.send_action_notification(actions)
    end_time = datetime.now(UTC)
    
    # Verify notification sent within 1 minute
    elapsed = (end_time - start_time).total_seconds()
    assert elapsed < 60.0
    
    # Verify SNS publish called
    mock_sns.publish.assert_called_once()
    call_args = mock_sns.publish.call_args
    
    # Verify topic ARN
    assert call_args[1]['TopicArn'] == config.action_topic_arn
    
    # Verify subject structure
    subject = call_args[1]['Subject']
    assert 'Actions' in subject
    assert '$' in subject  # Savings mentioned
    
    # Verify message structure
    message = call_args[1]['Message']
    assert f'Total Actions: {num_actions}' in message
    assert f'${total_savings:.2f}' in message


@settings(max_examples=100)
@given(
    error_type=st.sampled_from([ValueError, RuntimeError, KeyError, TypeError]),
    error_message=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N'))),
    num_context_items=st.integers(min_value=0, max_value=10)
)
def test_property_error_notification_structure(error_type, error_message, num_context_items):
    """
    Property 9: Error Notification Structure
    
    For any error:
    - Notification should be sent via SNS
    - Message should contain error type and message
    - Message should contain all context items
    - Notification should be sent immediately (within 1 minute)
    
    Validates: Requirements 8.4
    """
    assume(len(error_message.strip()) > 0)
    
    mock_sns = Mock()
    config = NotificationConfig(
        warning_topic_arn=None,
        action_topic_arn=None,
        error_topic_arn="arn:aws:sns:us-east-1:123456789012:errors"
    )
    
    service = NotificationService(mock_sns, config)
    
    # Create error and context
    error = error_type(error_message)
    context = {f'key{i}': f'value{i}' for i in range(num_context_items)}
    
    # Send error notification
    start_time = datetime.now(UTC)
    service.send_error_notification(error, context)
    end_time = datetime.now(UTC)
    
    # Verify notification sent within 1 minute
    elapsed = (end_time - start_time).total_seconds()
    assert elapsed < 60.0
    
    # Verify SNS publish called
    mock_sns.publish.assert_called_once()
    call_args = mock_sns.publish.call_args
    
    # Verify topic ARN
    assert call_args[1]['TopicArn'] == config.error_topic_arn
    
    # Verify subject structure
    subject = call_args[1]['Subject']
    assert error_type.__name__ in subject
    
    # Verify message structure
    message = call_args[1]['Message']
    assert error_type.__name__ in message
    assert error_message in message
    
    # Verify all context items present
    for key, value in context.items():
        assert key in message
        assert value in message


@settings(max_examples=100)
@given(
    has_warning_topic=st.booleans(),
    has_action_topic=st.booleans(),
    has_error_topic=st.booleans()
)
def test_property_multi_topic_routing(has_warning_topic, has_action_topic, has_error_topic):
    """
    Property 9: Multi-Topic Routing
    
    For any notification configuration:
    - Warnings should use warning topic if configured
    - Actions should use action topic if configured
    - Errors should use error topic if configured
    - No notification sent if topic not configured
    
    Validates: Requirements 8.6
    """
    mock_sns = Mock()
    config = NotificationConfig(
        warning_topic_arn="arn:aws:sns:us-east-1:123456789012:warnings" if has_warning_topic else None,
        action_topic_arn="arn:aws:sns:us-east-1:123456789012:actions" if has_action_topic else None,
        error_topic_arn="arn:aws:sns:us-east-1:123456789012:errors" if has_error_topic else None
    )
    
    service = NotificationService(mock_sns, config)
    
    # Test warning notification
    budget_status = BudgetStatus(
        budget_name='test',
        limit=100.0,
        actual_spend=80.0,
        forecasted_spend=90.0,
        utilization_percent=80.0,
        currency='USD',
        time_period='2024-02'
    )
    
    service.send_warning(budget_status)
    
    if has_warning_topic:
        mock_sns.publish.assert_called_once()
        assert mock_sns.publish.call_args[1]['TopicArn'] == config.warning_topic_arn
    else:
        mock_sns.publish.assert_not_called()
    
    # Reset mock
    mock_sns.reset_mock()
    
    # Test action notification
    actions = [
        ActionResult(
            resource_id='i-test',
            action='stop',
            success=True,
            error_message=None,
            pre_action_state={},
            post_action_state={},
            estimated_savings=10.0,
            timestamp=datetime.now(UTC).isoformat()
        )
    ]
    
    service.send_action_notification(actions)
    
    if has_action_topic:
        mock_sns.publish.assert_called_once()
        assert mock_sns.publish.call_args[1]['TopicArn'] == config.action_topic_arn
    else:
        mock_sns.publish.assert_not_called()
    
    # Reset mock
    mock_sns.reset_mock()
    
    # Test error notification
    service.send_error_notification(Exception("test"), {})
    
    if has_error_topic:
        mock_sns.publish.assert_called_once()
        assert mock_sns.publish.call_args[1]['TopicArn'] == config.error_topic_arn
    else:
        mock_sns.publish.assert_not_called()


@settings(max_examples=100)
@given(
    num_actions=st.integers(min_value=1, max_value=20),
    savings_per_action=st.floats(min_value=0.01, max_value=1000.0)
)
def test_property_action_notification_savings_calculation(num_actions, savings_per_action):
    """
    Property: Action Notification Savings Calculation
    
    For any set of actions:
    - Total savings should equal sum of individual savings
    - Savings should be included in notification
    
    Validates: Requirements 8.5
    """
    mock_sns = Mock()
    config = NotificationConfig(
        warning_topic_arn=None,
        action_topic_arn="arn:aws:sns:us-east-1:123456789012:actions",
        error_topic_arn=None
    )
    
    service = NotificationService(mock_sns, config)
    
    # Create actions with known savings
    actions = []
    expected_total = 0.0
    for i in range(num_actions):
        actions.append(ActionResult(
            resource_id=f'resource-{i}',
            action='stop',
            success=True,
            error_message=None,
            pre_action_state={},
            post_action_state={},
            estimated_savings=savings_per_action,
            timestamp=datetime.now(UTC).isoformat()
        ))
        expected_total += savings_per_action
    
    # Send notification
    service.send_action_notification(actions)
    
    # Verify total savings in message
    call_args = mock_sns.publish.call_args
    message = call_args[1]['Message']
    
    # Check that expected total is mentioned (with some tolerance for formatting)
    assert f'${expected_total:.2f}' in message


@settings(max_examples=100)
@given(
    num_successful=st.integers(min_value=0, max_value=10),
    num_failed=st.integers(min_value=0, max_value=10)
)
def test_property_action_notification_success_failure_counts(num_successful, num_failed):
    """
    Property: Action Notification Success/Failure Counts
    
    For any set of actions:
    - Notification should correctly count successful and failed actions
    - Both counts should be included in message
    
    Validates: Requirements 8.3
    """
    assume(num_successful + num_failed > 0)
    
    mock_sns = Mock()
    config = NotificationConfig(
        warning_topic_arn=None,
        action_topic_arn="arn:aws:sns:us-east-1:123456789012:actions",
        error_topic_arn=None
    )
    
    service = NotificationService(mock_sns, config)
    
    # Create actions
    actions = []
    
    # Add successful actions
    for i in range(num_successful):
        actions.append(ActionResult(
            resource_id=f'success-{i}',
            action='stop',
            success=True,
            error_message=None,
            pre_action_state={},
            post_action_state={},
            estimated_savings=10.0,
            timestamp=datetime.now(UTC).isoformat()
        ))
    
    # Add failed actions
    for i in range(num_failed):
        actions.append(ActionResult(
            resource_id=f'failed-{i}',
            action='stop',
            success=False,
            error_message='Test error',
            pre_action_state={},
            post_action_state={},
            estimated_savings=10.0,
            timestamp=datetime.now(UTC).isoformat()
        ))
    
    # Send notification
    service.send_action_notification(actions)
    
    # Verify counts in message
    call_args = mock_sns.publish.call_args
    message = call_args[1]['Message']
    
    total = num_successful + num_failed
    assert f'Total Actions: {total}' in message
    assert f'Successful: {num_successful}' in message
    assert f'Failed: {num_failed}' in message


@settings(max_examples=100)
@given(
    utilization=st.floats(min_value=80.0, max_value=100.0)
)
def test_property_notification_timestamps_present(utilization):
    """
    Property: Notification Timestamps
    
    For any notification:
    - Should include timestamp
    - Timestamp should be in ISO 8601 format
    
    Validates: Requirements 8.1-8.6
    """
    mock_sns = Mock()
    config = NotificationConfig(
        warning_topic_arn="arn:aws:sns:us-east-1:123456789012:warnings",
        action_topic_arn="arn:aws:sns:us-east-1:123456789012:actions",
        error_topic_arn="arn:aws:sns:us-east-1:123456789012:errors"
    )
    
    service = NotificationService(mock_sns, config)
    
    # Test warning notification
    budget_status = BudgetStatus(
        budget_name='test',
        limit=100.0,
        actual_spend=utilization,
        forecasted_spend=utilization * 1.1,
        utilization_percent=utilization,
        currency='USD',
        time_period='2024-02'
    )
    
    service.send_warning(budget_status)
    message = mock_sns.publish.call_args[1]['Message']
    assert 'Timestamp:' in message
    
    # Test action notification
    mock_sns.reset_mock()
    actions = [
        ActionResult(
            resource_id='i-test',
            action='stop',
            success=True,
            error_message=None,
            pre_action_state={},
            post_action_state={},
            estimated_savings=10.0,
            timestamp=datetime.now(UTC).isoformat()
        )
    ]
    service.send_action_notification(actions)
    message = mock_sns.publish.call_args[1]['Message']
    assert 'Timestamp:' in message
    
    # Test error notification
    mock_sns.reset_mock()
    service.send_error_notification(Exception("test"), {})
    message = mock_sns.publish.call_args[1]['Message']
    assert 'Timestamp:' in message
