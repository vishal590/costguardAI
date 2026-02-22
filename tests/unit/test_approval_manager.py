"""
Unit tests for ApprovalManager.

Tests approval workflow for automated actions.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta, UTC
from src.services.approval_manager import ApprovalManager
from src.utils.types import ApprovalRequest, ApprovalResponse, PlannedAction, Resource


class TestApprovalManager:
    """Test ApprovalManager class."""
    
    @pytest.fixture
    def mock_sns_client(self):
        """Create mock SNS client."""
        client = Mock()
        client.publish = Mock(return_value={'MessageId': 'msg-123'})
        return client
    
    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        client = Mock()
        client.put_item = Mock()
        client.update_item = Mock()
        client.get_item = Mock()
        return client
    
    @pytest.fixture
    def approval_manager(self, mock_sns_client, mock_dynamodb_client):
        """Create ApprovalManager instance."""
        manager = ApprovalManager(mock_sns_client, mock_dynamodb_client)
        manager.approval_topic_arn = "arn:aws:sns:us-east-1:123456789012:approval-topic"
        return manager
    
    @pytest.fixture
    def sample_actions(self):
        """Create sample actions for approval."""
        resource1 = Resource(
            resource_id='i-test123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Name': 'test-instance'},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        resource2 = Resource(
            resource_id='db-test456',
            resource_type='db_instance',
            service='rds',
            region='us-east-1',
            tags={'Name': 'test-db'},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
        
        return [
            {
                'resource': resource1,
                'action': 'stop',
                'estimated_savings': 50.0
            },
            {
                'resource': resource2,
                'action': 'stop',
                'estimated_savings': 100.0
            }
        ]
    
    def test_initialization(self, approval_manager, mock_sns_client, mock_dynamodb_client):
        """Test ApprovalManager initialization."""
        assert approval_manager.sns == mock_sns_client
        assert approval_manager.dynamodb == mock_dynamodb_client
        assert approval_manager.approval_table == "approval-requests"
        assert approval_manager.approval_topic_arn is not None
    
    def test_request_approval_creates_request(self, approval_manager, sample_actions, mock_dynamodb_client):
        """Test request_approval creates approval request."""
        result = approval_manager.request_approval(sample_actions)
        
        # Verify ApprovalRequest structure
        assert isinstance(result, ApprovalRequest)
        assert result.request_id is not None
        assert len(result.actions) == 2
        assert result.total_estimated_savings == 150.0
        assert result.expires_at is not None
        
        # Verify actions converted to PlannedAction
        assert all(isinstance(action, PlannedAction) for action in result.actions)
        assert result.actions[0].resource_id == 'i-test123'
        assert result.actions[0].action == 'stop'
        assert result.actions[0].estimated_savings == 50.0
        assert result.actions[1].resource_id == 'db-test456'
        assert result.actions[1].estimated_savings == 100.0
    
    def test_request_approval_stores_in_dynamodb(self, approval_manager, sample_actions, mock_dynamodb_client):
        """Test request_approval stores request in DynamoDB."""
        result = approval_manager.request_approval(sample_actions)
        
        # Verify DynamoDB put_item called
        mock_dynamodb_client.put_item.assert_called_once()
        call_args = mock_dynamodb_client.put_item.call_args
        
        assert call_args[1]['TableName'] == 'approval-requests'
        item = call_args[1]['Item']
        assert item['request_id']['S'] == result.request_id
        assert item['status']['S'] == 'pending'
        assert item['total_estimated_savings']['N'] == '150.0'
        assert item['action_count']['N'] == '2'
    
    def test_request_approval_sends_sns_notification(self, approval_manager, sample_actions, mock_sns_client):
        """Test request_approval sends SNS notification."""
        result = approval_manager.request_approval(sample_actions)
        
        # Verify SNS publish called
        mock_sns_client.publish.assert_called_once()
        call_args = mock_sns_client.publish.call_args
        
        assert call_args[1]['TopicArn'] == approval_manager.approval_topic_arn
        assert 'Approval Required' in call_args[1]['Subject']
        assert result.request_id in call_args[1]['Message']
        assert '$150.00' in call_args[1]['Message']
    
    def test_request_approval_no_topic_arn(self, mock_sns_client, mock_dynamodb_client, sample_actions):
        """Test request_approval without topic ARN configured."""
        manager = ApprovalManager(mock_sns_client, mock_dynamodb_client)
        manager.approval_topic_arn = None
        
        result = manager.request_approval(sample_actions)
        
        # Should still create request but not send notification
        assert isinstance(result, ApprovalRequest)
        mock_sns_client.publish.assert_not_called()
    
    def test_wait_for_approval_approved(self, approval_manager, mock_dynamodb_client):
        """Test wait_for_approval with approval granted."""
        request_id = 'test-request-123'
        
        # Mock DynamoDB to return approved status
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'request_id': {'S': request_id},
                'status': {'S': 'approved'},
                'approved_by': {'S': 'admin@example.com'},
                'response_timestamp': {'S': datetime.now(UTC).isoformat()}
            }
        }
        
        with patch('time.sleep'):  # Skip actual sleep
            result = approval_manager.wait_for_approval(request_id, timeout_minutes=1)
        
        # Verify ApprovalResponse
        assert isinstance(result, ApprovalResponse)
        assert result.request_id == request_id
        assert result.approved is True
        assert result.approved_by == 'admin@example.com'
    
    def test_wait_for_approval_denied(self, approval_manager, mock_dynamodb_client):
        """Test wait_for_approval with approval denied."""
        request_id = 'test-request-123'
        
        # Mock DynamoDB to return denied status
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'request_id': {'S': request_id},
                'status': {'S': 'denied'},
                'approved_by': {'S': 'admin@example.com'},
                'response_timestamp': {'S': datetime.now(UTC).isoformat()}
            }
        }
        
        with patch('time.sleep'):  # Skip actual sleep
            result = approval_manager.wait_for_approval(request_id, timeout_minutes=1)
        
        # Verify ApprovalResponse
        assert isinstance(result, ApprovalResponse)
        assert result.request_id == request_id
        assert result.approved is False
        assert result.approved_by == 'admin@example.com'
    
    def test_wait_for_approval_timeout(self, approval_manager, mock_dynamodb_client):
        """Test wait_for_approval with timeout."""
        request_id = 'test-request-123'
        
        # Mock DynamoDB to return pending status (never approved)
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'request_id': {'S': request_id},
                'status': {'S': 'pending'}
            }
        }
        
        # Use very short timeout for testing
        with patch('time.sleep'):
            with patch('src.services.approval_manager.datetime') as mock_datetime:
                # Simulate timeout by making time progress
                start = datetime.now(UTC)
                mock_datetime.now.side_effect = [
                    start,  # Initial time
                    start + timedelta(minutes=2),  # After timeout (loop check)
                    start + timedelta(minutes=2)   # Final timestamp creation
                ]
                mock_datetime.UTC = UTC
                
                result = approval_manager.wait_for_approval(request_id, timeout_minutes=1)
        
        # Verify timeout defaults to not approved
        assert isinstance(result, ApprovalResponse)
        assert result.request_id == request_id
        assert result.approved is False
        assert result.approved_by is None
    
    def test_wait_for_approval_no_item(self, approval_manager, mock_dynamodb_client):
        """Test wait_for_approval when item not found."""
        request_id = 'test-request-123'
        
        # Mock DynamoDB to return no item
        mock_dynamodb_client.get_item.return_value = {}
        
        with patch('time.sleep'):
            with patch('src.services.approval_manager.datetime') as mock_datetime:
                start = datetime.now(UTC)
                mock_datetime.now.side_effect = [
                    start,
                    start + timedelta(minutes=2),  # After timeout (loop check)
                    start + timedelta(minutes=2)   # Final timestamp creation
                ]
                mock_datetime.UTC = UTC
                
                result = approval_manager.wait_for_approval(request_id, timeout_minutes=1)
        
        # Should timeout and return not approved
        assert result.approved is False
    
    def test_process_approval_response_approved(self, approval_manager, mock_dynamodb_client):
        """Test process_approval_response for approval."""
        request_id = 'test-request-123'
        
        result = approval_manager.process_approval_response(
            request_id=request_id,
            approved=True,
            approved_by='admin@example.com'
        )
        
        # Verify ApprovalResponse
        assert isinstance(result, ApprovalResponse)
        assert result.request_id == request_id
        assert result.approved is True
        assert result.approved_by == 'admin@example.com'
        assert result.timestamp is not None
        
        # Verify DynamoDB update
        mock_dynamodb_client.update_item.assert_called_once()
        call_args = mock_dynamodb_client.update_item.call_args
        assert call_args[1]['TableName'] == 'approval-requests'
        assert call_args[1]['Key']['request_id']['S'] == request_id
        assert call_args[1]['ExpressionAttributeValues'][':status']['S'] == 'approved'
    
    def test_process_approval_response_denied(self, approval_manager, mock_dynamodb_client):
        """Test process_approval_response for denial."""
        request_id = 'test-request-123'
        
        result = approval_manager.process_approval_response(
            request_id=request_id,
            approved=False,
            approved_by='admin@example.com'
        )
        
        # Verify ApprovalResponse
        assert isinstance(result, ApprovalResponse)
        assert result.request_id == request_id
        assert result.approved is False
        
        # Verify DynamoDB update
        call_args = mock_dynamodb_client.update_item.call_args
        assert call_args[1]['ExpressionAttributeValues'][':status']['S'] == 'denied'
    
    def test_process_approval_response_no_approver(self, approval_manager, mock_dynamodb_client):
        """Test process_approval_response without approver."""
        request_id = 'test-request-123'
        
        result = approval_manager.process_approval_response(
            request_id=request_id,
            approved=True
        )
        
        # Verify ApprovalResponse
        assert result.approved_by is None
        
        # Verify DynamoDB stores 'unknown' for missing approver
        call_args = mock_dynamodb_client.update_item.call_args
        assert call_args[1]['ExpressionAttributeValues'][':approved_by']['S'] == 'unknown'
    
    def test_store_approval_request_error_handling(self, approval_manager, mock_dynamodb_client):
        """Test _store_approval_request handles errors gracefully."""
        mock_dynamodb_client.put_item.side_effect = Exception("DynamoDB error")
        
        # Should not raise exception
        approval_request = ApprovalRequest(
            request_id='test-123',
            actions=[],
            total_estimated_savings=0.0,
            expires_at=datetime.now(UTC).isoformat()
        )
        
        approval_manager._store_approval_request(approval_request)
        # No assertion needed - just verify it doesn't crash
    
    def test_store_approval_response_error_handling(self, approval_manager, mock_dynamodb_client):
        """Test _store_approval_response handles errors gracefully."""
        mock_dynamodb_client.update_item.side_effect = Exception("DynamoDB error")
        
        # Should not raise exception
        approval_response = ApprovalResponse(
            request_id='test-123',
            approved=True,
            approved_by='admin',
            timestamp=datetime.now(UTC).isoformat()
        )
        
        approval_manager._store_approval_response(approval_response)
        # No assertion needed - just verify it doesn't crash
    
    def test_check_approval_status_error_handling(self, approval_manager, mock_dynamodb_client):
        """Test _check_approval_status handles errors gracefully."""
        mock_dynamodb_client.get_item.side_effect = Exception("DynamoDB error")
        
        result = approval_manager._check_approval_status('test-123')
        
        # Should return None on error
        assert result is None
    
    def test_send_approval_notification_error_handling(self, approval_manager, mock_sns_client):
        """Test _send_approval_notification handles errors gracefully."""
        mock_sns_client.publish.side_effect = Exception("SNS error")
        
        # Should not raise exception
        approval_request = ApprovalRequest(
            request_id='test-123',
            actions=[
                PlannedAction(
                    resource_id='i-123',
                    resource_type='instance',
                    action='stop',
                    reason='idle',
                    estimated_savings=50.0
                )
            ],
            total_estimated_savings=50.0,
            expires_at=datetime.now(UTC).isoformat()
        )
        
        approval_manager._send_approval_notification(approval_request)
        # No assertion needed - just verify it doesn't crash
