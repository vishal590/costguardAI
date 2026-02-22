"""
Unit tests for NotificationService.

Tests notification sending for warnings, actions, and errors.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, UTC
from src.services.notification_service import NotificationService
from src.utils.types import (
    NotificationConfig, BudgetStatus, ActionResult
)


class TestNotificationService:
    """Test NotificationService class."""
    
    @pytest.fixture
    def mock_sns_client(self):
        """Create mock SNS client."""
        client = Mock()
        client.publish = Mock(return_value={'MessageId': 'msg-123'})
        return client
    
    @pytest.fixture
    def notification_config(self):
        """Create notification configuration."""
        return NotificationConfig(
            warning_topic_arn="arn:aws:sns:us-east-1:123456789012:warnings",
            action_topic_arn="arn:aws:sns:us-east-1:123456789012:actions",
            error_topic_arn="arn:aws:sns:us-east-1:123456789012:errors"
        )
    
    @pytest.fixture
    def notification_service(self, mock_sns_client, notification_config):
        """Create NotificationService instance."""
        return NotificationService(mock_sns_client, notification_config)
    
    @pytest.fixture
    def sample_budget_status(self):
        """Create sample budget status."""
        return BudgetStatus(
            budget_name='monthly-budget',
            limit=1000.0,
            actual_spend=850.0,
            forecasted_spend=950.0,
            utilization_percent=85.0,
            currency='USD',
            time_period='2024-02'
        )
    
    @pytest.fixture
    def sample_actions(self):
        """Create sample action results."""
        return [
            ActionResult(
                resource_id='i-test123',
                action='stop',
                success=True,
                error_message=None,
                pre_action_state={'state': 'running'},
                post_action_state={'state': 'stopped'},
                estimated_savings=50.0,
                timestamp='2024-02-01T12:00:00Z'
            ),
            ActionResult(
                resource_id='db-test456',
                action='stop',
                success=True,
                error_message=None,
                pre_action_state={'state': 'available'},
                post_action_state={'state': 'stopped'},
                estimated_savings=100.0,
                timestamp='2024-02-01T12:00:00Z'
            )
        ]
    
    def test_initialization(self, notification_service, mock_sns_client, notification_config):
        """Test NotificationService initialization."""
        assert notification_service.sns == mock_sns_client
        assert notification_service.config == notification_config
        assert notification_service.warning_topic_arn == notification_config.warning_topic_arn
        assert notification_service.action_topic_arn == notification_config.action_topic_arn
        assert notification_service.error_topic_arn == notification_config.error_topic_arn
    
    def test_initialization_without_config(self, mock_sns_client):
        """Test NotificationService initialization without config."""
        service = NotificationService(mock_sns_client, None)
        
        assert service.sns == mock_sns_client
        assert service.config is None
        assert service.warning_topic_arn is None
        assert service.action_topic_arn is None
        assert service.error_topic_arn is None
    
    def test_send_warning_notification(self, notification_service, sample_budget_status, mock_sns_client):
        """Test send_warning sends SNS notification."""
        notification_service.send_warning(sample_budget_status)
        
        # Verify SNS publish called
        mock_sns_client.publish.assert_called_once()
        call_args = mock_sns_client.publish.call_args
        
        # Verify topic ARN
        assert call_args[1]['TopicArn'] == notification_service.warning_topic_arn
        
        # Verify subject contains budget name and utilization
        subject = call_args[1]['Subject']
        assert 'monthly-budget' in subject
        assert '85.0%' in subject
        
        # Verify message contains key information
        message = call_args[1]['Message']
        assert 'monthly-budget' in message
        assert '85.0%' in message
        assert 'USD 850.00' in message
        assert 'USD 1000.00' in message
        assert '2024-02' in message
        assert '80%' in message  # Warning threshold
        assert '90%' in message  # Action threshold
    
    def test_send_warning_no_topic_arn(self, mock_sns_client, sample_budget_status):
        """Test send_warning without topic ARN configured."""
        service = NotificationService(mock_sns_client, None)
        
        service.send_warning(sample_budget_status)
        
        # Should not send notification
        mock_sns_client.publish.assert_not_called()
    
    def test_send_warning_sns_error(self, notification_service, sample_budget_status, mock_sns_client):
        """Test send_warning handles SNS errors gracefully."""
        mock_sns_client.publish.side_effect = Exception("SNS error")
        
        # Should not raise exception
        notification_service.send_warning(sample_budget_status)
        
        # Verify publish was attempted
        mock_sns_client.publish.assert_called_once()
    
    def test_send_action_notification(self, notification_service, sample_actions, mock_sns_client):
        """Test send_action_notification sends SNS notification."""
        notification_service.send_action_notification(sample_actions)
        
        # Verify SNS publish called
        mock_sns_client.publish.assert_called_once()
        call_args = mock_sns_client.publish.call_args
        
        # Verify topic ARN
        assert call_args[1]['TopicArn'] == notification_service.action_topic_arn
        
        # Verify subject contains action count and savings
        subject = call_args[1]['Subject']
        assert '2 Actions' in subject
        assert '$150.00' in subject  # Total savings
        
        # Verify message contains action details
        message = call_args[1]['Message']
        assert 'Total Actions: 2' in message
        assert 'Successful: 2' in message
        assert 'Failed: 0' in message
        assert '$150.00' in message  # Total savings
        assert 'i-test123' in message
        assert 'db-test456' in message
        assert '$50.00' in message  # Individual savings
        assert '$100.00' in message
        assert 'rolled back within 24 hours' in message
    
    def test_send_action_notification_with_failures(self, notification_service, mock_sns_client):
        """Test send_action_notification with failed actions."""
        actions = [
            ActionResult(
                resource_id='i-success',
                action='stop',
                success=True,
                error_message=None,
                pre_action_state={},
                post_action_state={},
                estimated_savings=50.0,
                timestamp='2024-02-01T12:00:00Z'
            ),
            ActionResult(
                resource_id='i-failed',
                action='stop',
                success=False,
                error_message='Permission denied',
                pre_action_state={},
                post_action_state={},
                estimated_savings=30.0,
                timestamp='2024-02-01T12:00:00Z'
            )
        ]
        
        notification_service.send_action_notification(actions)
        
        # Verify SNS publish called
        call_args = mock_sns_client.publish.call_args
        message = call_args[1]['Message']
        
        # Verify counts
        assert 'Total Actions: 2' in message
        assert 'Successful: 1' in message
        assert 'Failed: 1' in message
        
        # Verify failed action details
        assert 'Failed Actions:' in message
        assert 'i-failed' in message
        assert 'Permission denied' in message
    
    def test_send_action_notification_no_topic_arn(self, mock_sns_client, sample_actions):
        """Test send_action_notification without topic ARN configured."""
        service = NotificationService(mock_sns_client, None)
        
        service.send_action_notification(sample_actions)
        
        # Should not send notification
        mock_sns_client.publish.assert_not_called()
    
    def test_send_action_notification_sns_error(self, notification_service, sample_actions, mock_sns_client):
        """Test send_action_notification handles SNS errors gracefully."""
        mock_sns_client.publish.side_effect = Exception("SNS error")
        
        # Should not raise exception
        notification_service.send_action_notification(sample_actions)
        
        # Verify publish was attempted
        mock_sns_client.publish.assert_called_once()
    
    def test_send_action_notification_empty_list(self, notification_service, mock_sns_client):
        """Test send_action_notification with empty action list."""
        notification_service.send_action_notification([])
        
        # Should still send notification
        mock_sns_client.publish.assert_called_once()
        call_args = mock_sns_client.publish.call_args
        message = call_args[1]['Message']
        
        assert 'Total Actions: 0' in message
        assert '$0.00' in message
    
    def test_send_error_notification(self, notification_service, mock_sns_client):
        """Test send_error_notification sends SNS notification."""
        error = ValueError("Invalid configuration")
        context = {
            'component': 'BudgetMonitor',
            'operation': 'poll_budgets',
            'budget_name': 'monthly-budget'
        }
        
        notification_service.send_error_notification(error, context)
        
        # Verify SNS publish called
        mock_sns_client.publish.assert_called_once()
        call_args = mock_sns_client.publish.call_args
        
        # Verify topic ARN
        assert call_args[1]['TopicArn'] == notification_service.error_topic_arn
        
        # Verify subject contains error type
        subject = call_args[1]['Subject']
        assert 'ValueError' in subject
        
        # Verify message contains error details and context
        message = call_args[1]['Message']
        assert 'ValueError' in message
        assert 'Invalid configuration' in message
        assert 'BudgetMonitor' in message
        assert 'poll_budgets' in message
        assert 'monthly-budget' in message
    
    def test_send_error_notification_no_topic_arn(self, mock_sns_client):
        """Test send_error_notification without topic ARN configured."""
        service = NotificationService(mock_sns_client, None)
        
        error = ValueError("Test error")
        context = {'key': 'value'}
        
        service.send_error_notification(error, context)
        
        # Should not send notification
        mock_sns_client.publish.assert_not_called()
    
    def test_send_error_notification_sns_error(self, notification_service, mock_sns_client):
        """Test send_error_notification handles SNS errors gracefully."""
        mock_sns_client.publish.side_effect = Exception("SNS error")
        
        error = ValueError("Test error")
        context = {'key': 'value'}
        
        # Should not raise exception
        notification_service.send_error_notification(error, context)
        
        # Verify publish was attempted
        mock_sns_client.publish.assert_called_once()
    
    def test_send_error_notification_empty_context(self, notification_service, mock_sns_client):
        """Test send_error_notification with empty context."""
        error = RuntimeError("Something went wrong")
        context = {}
        
        notification_service.send_error_notification(error, context)
        
        # Should still send notification
        mock_sns_client.publish.assert_called_once()
        call_args = mock_sns_client.publish.call_args
        message = call_args[1]['Message']
        
        assert 'RuntimeError' in message
        assert 'Something went wrong' in message
    
    def test_multi_topic_routing(self, mock_sns_client, notification_config):
        """Test that different notification types use different topics."""
        service = NotificationService(mock_sns_client, notification_config)
        
        # Send warning
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
        
        # Verify warning topic used
        call_args = mock_sns_client.publish.call_args
        assert call_args[1]['TopicArn'] == notification_config.warning_topic_arn
        
        # Reset mock
        mock_sns_client.reset_mock()
        
        # Send action notification
        actions = [
            ActionResult(
                resource_id='i-test',
                action='stop',
                success=True,
                error_message=None,
                pre_action_state={},
                post_action_state={},
                estimated_savings=10.0,
                timestamp='2024-02-01T12:00:00Z'
            )
        ]
        service.send_action_notification(actions)
        
        # Verify action topic used
        call_args = mock_sns_client.publish.call_args
        assert call_args[1]['TopicArn'] == notification_config.action_topic_arn
        
        # Reset mock
        mock_sns_client.reset_mock()
        
        # Send error notification
        service.send_error_notification(Exception("test"), {})
        
        # Verify error topic used
        call_args = mock_sns_client.publish.call_args
        assert call_args[1]['TopicArn'] == notification_config.error_topic_arn
    
    def test_notification_timestamps(self, notification_service, sample_budget_status, sample_actions, mock_sns_client):
        """Test that all notifications include timestamps."""
        # Warning notification
        notification_service.send_warning(sample_budget_status)
        message = mock_sns_client.publish.call_args[1]['Message']
        assert 'Timestamp:' in message
        
        # Action notification
        mock_sns_client.reset_mock()
        notification_service.send_action_notification(sample_actions)
        message = mock_sns_client.publish.call_args[1]['Message']
        assert 'Timestamp:' in message
        
        # Error notification
        mock_sns_client.reset_mock()
        notification_service.send_error_notification(Exception("test"), {})
        message = mock_sns_client.publish.call_args[1]['Message']
        assert 'Timestamp:' in message
