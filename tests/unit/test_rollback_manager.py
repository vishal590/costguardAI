"""
Unit tests for RollbackManager.

Tests rollback functionality for automated actions.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta, UTC
from src.services.rollback_manager import RollbackManager
from src.utils.types import Resource, RollbackResult


class TestRollbackManager:
    """Test RollbackManager class."""
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock AWS clients."""
        return {
            'ec2': Mock(),
            'rds': Mock(),
            'lambda': Mock()
        }
    
    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create mock DynamoDB client."""
        client = Mock()
        client.put_item = Mock()
        client.get_item = Mock()
        return client
    
    @pytest.fixture
    def rollback_manager(self, mock_clients, mock_dynamodb_client):
        """Create RollbackManager instance."""
        return RollbackManager(mock_clients, mock_dynamodb_client)
    
    @pytest.fixture
    def ec2_resource(self):
        """Create EC2 resource."""
        return Resource(
            resource_id='i-test123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Name': 'test-instance'},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
    
    @pytest.fixture
    def rds_resource(self):
        """Create RDS resource."""
        return Resource(
            resource_id='db-test123',
            resource_type='db_instance',
            service='rds',
            region='us-east-1',
            tags={'Name': 'test-db'},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
    
    @pytest.fixture
    def lambda_resource(self):
        """Create Lambda resource."""
        return Resource(
            resource_id='test-function',
            resource_type='function',
            service='lambda',
            region='us-east-1',
            tags={'Name': 'test-function'},
            state='Active',
            creation_date='2024-01-01T12:00:00'
        )
    
    def test_initialization(self, rollback_manager, mock_clients, mock_dynamodb_client):
        """Test RollbackManager initialization."""
        assert rollback_manager.clients == mock_clients
        assert rollback_manager.dynamodb == mock_dynamodb_client
        assert rollback_manager.audit_table == "prevention-audit"
        assert rollback_manager.rollback_window_hours == 24
    
    def test_store_pre_action_state_success(self, rollback_manager, ec2_resource, mock_dynamodb_client):
        """Test storing pre-action state successfully."""
        rollback_manager.store_pre_action_state(ec2_resource, 'stop')
        
        # Verify DynamoDB put_item called
        mock_dynamodb_client.put_item.assert_called_once()
        call_args = mock_dynamodb_client.put_item.call_args
        
        assert call_args[1]['TableName'] == 'prevention-audit'
        item = call_args[1]['Item']
        assert item['resource_id']['S'] == 'i-test123'
        assert item['action']['S'] == 'stop'
        assert item['event_type']['S'] == 'pre_action_state'
        assert 'ttl' in item
    
    def test_store_pre_action_state_error_handling(self, rollback_manager, ec2_resource, mock_dynamodb_client):
        """Test store_pre_action_state handles errors gracefully."""
        mock_dynamodb_client.put_item.side_effect = Exception("DynamoDB error")
        
        # Should not raise exception
        rollback_manager.store_pre_action_state(ec2_resource, 'stop')
        # No assertion needed - just verify it doesn't crash
    
    def test_execute_rollback_ec2_success(self, rollback_manager, mock_clients, mock_dynamodb_client):
        """Test executing rollback for EC2 instance."""
        action_id = 'test-action-123'
        
        # Mock DynamoDB response
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'action_id': {'S': action_id},
                'resource_id': {'S': 'i-test123'},
                'action': {'S': 'stop'},
                'timestamp': {'S': datetime.now(UTC).isoformat()},
                'state': {'S': str({
                    'resource_id': 'i-test123',
                    'service': 'ec2',
                    'action': 'stop',
                    'state': 'running'
                })}
            }
        }
        
        # Mock EC2 start_instances
        mock_clients['ec2'].start_instances.return_value = {}
        
        result = rollback_manager.execute_rollback(action_id)
        
        # Verify result
        assert isinstance(result, RollbackResult)
        assert result.action_id == action_id
        assert result.resource_id == 'i-test123'
        assert result.success is True
        
        # Verify EC2 start_instances called
        mock_clients['ec2'].start_instances.assert_called_once_with(InstanceIds=['i-test123'])
    
    def test_execute_rollback_rds_success(self, rollback_manager, mock_clients, mock_dynamodb_client):
        """Test executing rollback for RDS instance."""
        action_id = 'test-action-456'
        
        # Mock DynamoDB response
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'action_id': {'S': action_id},
                'resource_id': {'S': 'db-test123'},
                'action': {'S': 'stop'},
                'timestamp': {'S': datetime.now(UTC).isoformat()},
                'state': {'S': str({
                    'resource_id': 'db-test123',
                    'service': 'rds',
                    'action': 'stop',
                    'state': 'available'
                })}
            }
        }
        
        # Mock RDS start_db_instance
        mock_clients['rds'].start_db_instance.return_value = {}
        
        result = rollback_manager.execute_rollback(action_id)
        
        # Verify result
        assert isinstance(result, RollbackResult)
        assert result.success is True
        assert result.resource_id == 'db-test123'
        
        # Verify RDS start_db_instance called
        mock_clients['rds'].start_db_instance.assert_called_once_with(DBInstanceIdentifier='db-test123')
    
    def test_execute_rollback_lambda_success(self, rollback_manager, mock_clients, mock_dynamodb_client):
        """Test executing rollback for Lambda function."""
        action_id = 'test-action-789'
        
        # Mock DynamoDB response
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'action_id': {'S': action_id},
                'resource_id': {'S': 'test-function'},
                'action': {'S': 'limit_concurrency'},
                'timestamp': {'S': datetime.now(UTC).isoformat()},
                'state': {'S': str({
                    'resource_id': 'test-function',
                    'service': 'lambda',
                    'action': 'limit_concurrency',
                    'state': 'Active'
                })}
            }
        }
        
        # Mock Lambda delete_function_concurrency
        mock_clients['lambda'].delete_function_concurrency.return_value = {}
        
        result = rollback_manager.execute_rollback(action_id)
        
        # Verify result
        assert isinstance(result, RollbackResult)
        assert result.success is True
        assert result.resource_id == 'test-function'
        
        # Verify Lambda delete_function_concurrency called
        mock_clients['lambda'].delete_function_concurrency.assert_called_once_with(FunctionName='test-function')
    
    def test_execute_rollback_action_not_found(self, rollback_manager, mock_dynamodb_client):
        """Test executing rollback when action not found."""
        action_id = 'nonexistent-action'
        
        # Mock DynamoDB to return no item
        mock_dynamodb_client.get_item.return_value = {}
        
        result = rollback_manager.execute_rollback(action_id)
        
        # Verify result indicates failure
        assert isinstance(result, RollbackResult)
        assert result.success is False
        assert result.resource_id == "unknown"
    
    def test_execute_rollback_outside_window(self, rollback_manager, mock_dynamodb_client):
        """Test executing rollback outside 24-hour window."""
        action_id = 'old-action-123'
        
        # Mock DynamoDB response with old timestamp
        old_timestamp = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'action_id': {'S': action_id},
                'resource_id': {'S': 'i-test123'},
                'action': {'S': 'stop'},
                'timestamp': {'S': old_timestamp},
                'state': {'S': str({'resource_id': 'i-test123', 'service': 'ec2', 'action': 'stop'})}
            }
        }
        
        result = rollback_manager.execute_rollback(action_id)
        
        # Verify result indicates failure
        assert isinstance(result, RollbackResult)
        assert result.success is False
        assert result.resource_id == 'i-test123'
    
    def test_execute_rollback_with_exception(self, rollback_manager, mock_dynamodb_client):
        """Test executing rollback when exception occurs."""
        action_id = 'error-action'
        
        # Mock DynamoDB to raise exception
        mock_dynamodb_client.get_item.side_effect = Exception("DynamoDB error")
        
        result = rollback_manager.execute_rollback(action_id)
        
        # Verify result indicates failure
        assert isinstance(result, RollbackResult)
        assert result.success is False
        assert result.resource_id == "unknown"
    
    def test_restore_resource_state_ec2(self, rollback_manager, mock_clients):
        """Test restoring EC2 resource state."""
        state = {
            'resource_id': 'i-test123',
            'service': 'ec2',
            'action': 'stop',
            'state': 'running'
        }
        
        mock_clients['ec2'].start_instances.return_value = {}
        
        result = rollback_manager.restore_resource_state('i-test123', state)
        
        assert result is True
        mock_clients['ec2'].start_instances.assert_called_once()
    
    def test_restore_resource_state_rds(self, rollback_manager, mock_clients):
        """Test restoring RDS resource state."""
        state = {
            'resource_id': 'db-test123',
            'service': 'rds',
            'action': 'stop',
            'state': 'available'
        }
        
        mock_clients['rds'].start_db_instance.return_value = {}
        
        result = rollback_manager.restore_resource_state('db-test123', state)
        
        assert result is True
        mock_clients['rds'].start_db_instance.assert_called_once()
    
    def test_restore_resource_state_lambda(self, rollback_manager, mock_clients):
        """Test restoring Lambda resource state."""
        state = {
            'resource_id': 'test-function',
            'service': 'lambda',
            'action': 'limit_concurrency',
            'state': 'Active'
        }
        
        mock_clients['lambda'].delete_function_concurrency.return_value = {}
        
        result = rollback_manager.restore_resource_state('test-function', state)
        
        assert result is True
        mock_clients['lambda'].delete_function_concurrency.assert_called_once()
    
    def test_restore_resource_state_unsupported_service(self, rollback_manager):
        """Test restoring unsupported service."""
        state = {
            'resource_id': 'unknown-123',
            'service': 'unsupported',
            'action': 'stop',
            'state': 'active'
        }
        
        result = rollback_manager.restore_resource_state('unknown-123', state)
        
        assert result is False
    
    def test_restore_resource_state_with_exception(self, rollback_manager, mock_clients):
        """Test restoring resource state when exception occurs."""
        state = {
            'resource_id': 'i-test123',
            'service': 'ec2',
            'action': 'stop',
            'state': 'running'
        }
        
        mock_clients['ec2'].start_instances.side_effect = Exception("API Error")
        
        result = rollback_manager.restore_resource_state('i-test123', state)
        
        assert result is False
    
    def test_rollback_ec2_stop_success(self, rollback_manager, mock_clients):
        """Test rolling back EC2 stop."""
        mock_clients['ec2'].start_instances.return_value = {}
        
        result = rollback_manager._rollback_ec2_stop('i-test123')
        
        assert result is True
        mock_clients['ec2'].start_instances.assert_called_once_with(InstanceIds=['i-test123'])
    
    def test_rollback_ec2_stop_failure(self, rollback_manager, mock_clients):
        """Test rolling back EC2 stop with error."""
        mock_clients['ec2'].start_instances.side_effect = Exception("API Error")
        
        result = rollback_manager._rollback_ec2_stop('i-test123')
        
        assert result is False
    
    def test_rollback_ec2_stop_no_client(self, mock_dynamodb_client):
        """Test rolling back EC2 stop when client is missing."""
        manager = RollbackManager({}, mock_dynamodb_client)
        
        result = manager._rollback_ec2_stop('i-test123')
        
        assert result is False
    
    def test_rollback_rds_stop_success(self, rollback_manager, mock_clients):
        """Test rolling back RDS stop."""
        mock_clients['rds'].start_db_instance.return_value = {}
        
        result = rollback_manager._rollback_rds_stop('db-test123')
        
        assert result is True
        mock_clients['rds'].start_db_instance.assert_called_once_with(DBInstanceIdentifier='db-test123')
    
    def test_rollback_rds_stop_failure(self, rollback_manager, mock_clients):
        """Test rolling back RDS stop with error."""
        mock_clients['rds'].start_db_instance.side_effect = Exception("API Error")
        
        result = rollback_manager._rollback_rds_stop('db-test123')
        
        assert result is False
    
    def test_rollback_rds_stop_no_client(self, mock_dynamodb_client):
        """Test rolling back RDS stop when client is missing."""
        manager = RollbackManager({}, mock_dynamodb_client)
        
        result = manager._rollback_rds_stop('db-test123')
        
        assert result is False
    
    def test_rollback_lambda_concurrency_success(self, rollback_manager, mock_clients):
        """Test rolling back Lambda concurrency limit."""
        mock_clients['lambda'].delete_function_concurrency.return_value = {}
        
        state = {'resource_id': 'test-function'}
        result = rollback_manager._rollback_lambda_concurrency('test-function', state)
        
        assert result is True
        mock_clients['lambda'].delete_function_concurrency.assert_called_once_with(FunctionName='test-function')
    
    def test_rollback_lambda_concurrency_failure(self, rollback_manager, mock_clients):
        """Test rolling back Lambda concurrency with error."""
        mock_clients['lambda'].delete_function_concurrency.side_effect = Exception("API Error")
        
        state = {'resource_id': 'test-function'}
        result = rollback_manager._rollback_lambda_concurrency('test-function', state)
        
        assert result is False
    
    def test_rollback_lambda_concurrency_no_client(self, mock_dynamodb_client):
        """Test rolling back Lambda concurrency when client is missing."""
        manager = RollbackManager({}, mock_dynamodb_client)
        
        state = {'resource_id': 'test-function'}
        result = manager._rollback_lambda_concurrency('test-function', state)
        
        assert result is False
    
    def test_log_rollback_success(self, rollback_manager, mock_dynamodb_client):
        """Test logging rollback operation."""
        result = RollbackResult(
            action_id='test-action',
            resource_id='i-test123',
            success=True,
            restored_state={'state': 'running'},
            timestamp=datetime.now(UTC).isoformat()
        )
        
        rollback_manager._log_rollback(result)
        
        # Verify DynamoDB put_item called
        mock_dynamodb_client.put_item.assert_called_once()
        call_args = mock_dynamodb_client.put_item.call_args
        
        assert call_args[1]['TableName'] == 'prevention-audit'
        item = call_args[1]['Item']
        assert item['event_type']['S'] == 'rollback'
        assert item['resource_id']['S'] == 'i-test123'
        assert item['success']['BOOL'] is True
    
    def test_log_rollback_error_handling(self, rollback_manager, mock_dynamodb_client):
        """Test log_rollback handles errors gracefully."""
        mock_dynamodb_client.put_item.side_effect = Exception("DynamoDB error")
        
        result = RollbackResult(
            action_id='test-action',
            resource_id='i-test123',
            success=True,
            restored_state={},
            timestamp=datetime.now(UTC).isoformat()
        )
        
        # Should not raise exception
        rollback_manager._log_rollback(result)
        # No assertion needed - just verify it doesn't crash
    
    def test_rollback_window_hours_configurable(self, mock_clients, mock_dynamodb_client):
        """Test that rollback window hours is configurable."""
        manager = RollbackManager(mock_clients, mock_dynamodb_client)
        
        assert manager.rollback_window_hours == 24
        
        # Can be modified
        manager.rollback_window_hours = 48
        assert manager.rollback_window_hours == 48
    
    def test_store_pre_action_state_includes_ttl(self, rollback_manager, ec2_resource, mock_dynamodb_client):
        """Test that stored state includes TTL for automatic cleanup."""
        rollback_manager.store_pre_action_state(ec2_resource, 'stop')
        
        call_args = mock_dynamodb_client.put_item.call_args
        item = call_args[1]['Item']
        
        # Verify TTL is set
        assert 'ttl' in item
        ttl_value = int(item['ttl']['N'])
        
        # TTL should be approximately 24 hours from now
        expected_ttl = int((datetime.now(UTC) + timedelta(hours=24)).timestamp())
        assert abs(ttl_value - expected_ttl) < 60  # Within 1 minute
    
    def test_execute_rollback_logs_result(self, rollback_manager, mock_clients, mock_dynamodb_client):
        """Test that execute_rollback logs the result."""
        action_id = 'test-action-123'
        
        # Mock DynamoDB response
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'action_id': {'S': action_id},
                'resource_id': {'S': 'i-test123'},
                'action': {'S': 'stop'},
                'timestamp': {'S': datetime.now(UTC).isoformat()},
                'state': {'S': str({
                    'resource_id': 'i-test123',
                    'service': 'ec2',
                    'action': 'stop'
                })}
            }
        }
        
        mock_clients['ec2'].start_instances.return_value = {}
        
        rollback_manager.execute_rollback(action_id)
        
        # Verify put_item called twice: once for get, once for log
        assert mock_dynamodb_client.put_item.call_count == 1  # Only for logging
    
    def test_multiple_rollbacks_independent(self, rollback_manager, mock_clients, mock_dynamodb_client):
        """Test that multiple rollbacks are independent."""
        # First rollback succeeds
        mock_dynamodb_client.get_item.return_value = {
            'Item': {
                'action_id': {'S': 'action-1'},
                'resource_id': {'S': 'i-test1'},
                'action': {'S': 'stop'},
                'timestamp': {'S': datetime.now(UTC).isoformat()},
                'state': {'S': str({'resource_id': 'i-test1', 'service': 'ec2', 'action': 'stop'})}
            }
        }
        mock_clients['ec2'].start_instances.return_value = {}
        
        result1 = rollback_manager.execute_rollback('action-1')
        
        # Second rollback fails
        mock_clients['ec2'].start_instances.side_effect = Exception("API Error")
        
        result2 = rollback_manager.execute_rollback('action-1')
        
        # Verify results are independent
        assert result1.success is True
        assert result2.success is False
