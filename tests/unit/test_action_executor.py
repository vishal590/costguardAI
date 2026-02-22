"""
Unit tests for ActionExecutor.

Tests automated action execution on resources.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, UTC
from src.services.action_executor import ActionExecutor
from src.utils.types import Resource, ActionResult


class TestActionExecutor:
    """Test ActionExecutor class."""
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock AWS clients."""
        return {
            'ec2': Mock(),
            'rds': Mock(),
            'lambda': Mock(),
            'dynamodb': Mock()
        }
    
    @pytest.fixture
    def mock_audit_logger(self):
        """Create mock audit logger."""
        logger = Mock()
        logger.log_action = Mock()
        return logger
    
    @pytest.fixture
    def action_executor(self, mock_clients, mock_audit_logger):
        """Create ActionExecutor instance."""
        return ActionExecutor(mock_clients, mock_audit_logger)
    
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
    
    def test_initialization(self, action_executor, mock_clients, mock_audit_logger):
        """Test ActionExecutor initialization."""
        assert action_executor.clients == mock_clients
        assert action_executor.audit_logger == mock_audit_logger
    
    def test_stop_ec2_instance_success(self, action_executor, mock_clients):
        """Test stopping EC2 instance successfully."""
        mock_clients['ec2'].stop_instances.return_value = {'StoppingInstances': []}
        
        result = action_executor.stop_ec2_instance('i-test123')
        
        assert result is True
        mock_clients['ec2'].stop_instances.assert_called_once_with(InstanceIds=['i-test123'])
    
    def test_stop_ec2_instance_failure(self, action_executor, mock_clients):
        """Test stopping EC2 instance with error."""
        mock_clients['ec2'].stop_instances.side_effect = Exception("API Error")
        
        result = action_executor.stop_ec2_instance('i-test123')
        
        assert result is False
    
    def test_stop_ec2_instance_no_client(self, mock_audit_logger):
        """Test stopping EC2 instance when client is missing."""
        executor = ActionExecutor({}, mock_audit_logger)
        
        result = executor.stop_ec2_instance('i-test123')
        
        assert result is False
    
    def test_stop_rds_instance_success(self, action_executor, mock_clients):
        """Test stopping RDS instance successfully."""
        mock_clients['rds'].stop_db_instance.return_value = {'DBInstance': {}}
        
        result = action_executor.stop_rds_instance('db-test123')
        
        assert result is True
        mock_clients['rds'].stop_db_instance.assert_called_once_with(DBInstanceIdentifier='db-test123')
    
    def test_stop_rds_instance_failure(self, action_executor, mock_clients):
        """Test stopping RDS instance with error."""
        mock_clients['rds'].stop_db_instance.side_effect = Exception("API Error")
        
        result = action_executor.stop_rds_instance('db-test123')
        
        assert result is False
    
    def test_stop_rds_instance_no_client(self, mock_audit_logger):
        """Test stopping RDS instance when client is missing."""
        executor = ActionExecutor({}, mock_audit_logger)
        
        result = executor.stop_rds_instance('db-test123')
        
        assert result is False
    
    def test_limit_lambda_concurrency_success(self, action_executor, mock_clients):
        """Test limiting Lambda concurrency successfully."""
        mock_clients['lambda'].put_function_concurrency.return_value = {}
        
        result = action_executor.limit_lambda_concurrency('test-function', 0)
        
        assert result is True
        mock_clients['lambda'].put_function_concurrency.assert_called_once_with(
            FunctionName='test-function',
            ReservedConcurrentExecutions=0
        )
    
    def test_limit_lambda_concurrency_failure(self, action_executor, mock_clients):
        """Test limiting Lambda concurrency with error."""
        mock_clients['lambda'].put_function_concurrency.side_effect = Exception("API Error")
        
        result = action_executor.limit_lambda_concurrency('test-function', 0)
        
        assert result is False
    
    def test_limit_lambda_concurrency_no_client(self, mock_audit_logger):
        """Test limiting Lambda concurrency when client is missing."""
        executor = ActionExecutor({}, mock_audit_logger)
        
        result = executor.limit_lambda_concurrency('test-function', 0)
        
        assert result is False
    
    def test_snapshot_and_delete_volume_success(self, action_executor, mock_clients):
        """Test snapshot and delete EBS volume successfully."""
        mock_clients['ec2'].create_snapshot.return_value = {'SnapshotId': 'snap-123'}
        mock_clients['ec2'].delete_volume.return_value = {}
        
        result = action_executor._snapshot_and_delete_volume('vol-test123')
        
        assert result is True
        mock_clients['ec2'].create_snapshot.assert_called_once()
        mock_clients['ec2'].delete_volume.assert_called_once_with(VolumeId='vol-test123')
    
    def test_snapshot_and_delete_volume_failure(self, action_executor, mock_clients):
        """Test snapshot and delete volume with error."""
        mock_clients['ec2'].create_snapshot.side_effect = Exception("API Error")
        
        result = action_executor._snapshot_and_delete_volume('vol-test123')
        
        assert result is False
    
    def test_switch_to_ondemand_success(self, action_executor, mock_clients):
        """Test switching DynamoDB table to on-demand successfully."""
        mock_clients['dynamodb'].update_table.return_value = {}
        
        result = action_executor._switch_to_ondemand('test-table')
        
        assert result is True
        mock_clients['dynamodb'].update_table.assert_called_once_with(
            TableName='test-table',
            BillingMode='PAY_PER_REQUEST'
        )
    
    def test_switch_to_ondemand_failure(self, action_executor, mock_clients):
        """Test switching DynamoDB table with error."""
        mock_clients['dynamodb'].update_table.side_effect = Exception("API Error")
        
        result = action_executor._switch_to_ondemand('test-table')
        
        assert result is False
    
    def test_delete_nat_gateway_success(self, action_executor, mock_clients):
        """Test deleting NAT Gateway successfully."""
        mock_clients['ec2'].describe_nat_gateways.return_value = {
            'NatGateways': [{'NatGatewayId': 'nat-123', 'State': 'available'}]
        }
        mock_clients['ec2'].delete_nat_gateway.return_value = {}
        
        result = action_executor._delete_nat_gateway('nat-123')
        
        assert result is True
        mock_clients['ec2'].describe_nat_gateways.assert_called_once_with(NatGatewayIds=['nat-123'])
        mock_clients['ec2'].delete_nat_gateway.assert_called_once_with(NatGatewayId='nat-123')
    
    def test_delete_nat_gateway_failure(self, action_executor, mock_clients):
        """Test deleting NAT Gateway with error."""
        mock_clients['ec2'].describe_nat_gateways.side_effect = Exception("API Error")
        
        result = action_executor._delete_nat_gateway('nat-123')
        
        assert result is False
    
    def test_execute_action_ec2_success(self, action_executor, ec2_resource, mock_clients, mock_audit_logger):
        """Test execute_action for EC2 instance."""
        mock_clients['ec2'].stop_instances.return_value = {}
        
        result = action_executor.execute_action(ec2_resource, 'stop')
        
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.resource_id == 'i-test123'
        assert result.action == 'stop'
        assert result.error_message is None
        assert result.estimated_savings > 0
        mock_audit_logger.log_action.assert_called_once()
    
    def test_execute_action_rds_success(self, action_executor, rds_resource, mock_clients, mock_audit_logger):
        """Test execute_action for RDS instance."""
        mock_clients['rds'].stop_db_instance.return_value = {}
        
        result = action_executor.execute_action(rds_resource, 'stop')
        
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.resource_id == 'db-test123'
        assert result.action == 'stop'
        mock_audit_logger.log_action.assert_called_once()
    
    def test_execute_action_lambda_success(self, action_executor, lambda_resource, mock_clients, mock_audit_logger):
        """Test execute_action for Lambda function."""
        mock_clients['lambda'].put_function_concurrency.return_value = {}
        
        result = action_executor.execute_action(lambda_resource, 'limit_concurrency')
        
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.resource_id == 'test-function'
        mock_audit_logger.log_action.assert_called_once()
    
    def test_execute_action_ebs(self, action_executor, mock_clients, mock_audit_logger):
        """Test execute_action for EBS volume."""
        ebs_resource = Resource(
            resource_id='vol-test123',
            resource_type='volume',
            service='ebs',
            region='us-east-1',
            tags={},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
        
        mock_clients['ec2'].create_snapshot.return_value = {'SnapshotId': 'snap-123'}
        mock_clients['ec2'].delete_volume.return_value = {}
        
        result = action_executor.execute_action(ebs_resource, 'snapshot_delete')
        
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.resource_id == 'vol-test123'
        mock_audit_logger.log_action.assert_called_once()
    
    def test_execute_action_dynamodb(self, action_executor, mock_clients, mock_audit_logger):
        """Test execute_action for DynamoDB table."""
        dynamodb_resource = Resource(
            resource_id='test-table',
            resource_type='table',
            service='dynamodb',
            region='us-east-1',
            tags={},
            state='ACTIVE',
            creation_date='2024-01-01T12:00:00'
        )
        
        mock_clients['dynamodb'].update_table.return_value = {}
        
        result = action_executor.execute_action(dynamodb_resource, 'switch_ondemand')
        
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.resource_id == 'test-table'
        mock_audit_logger.log_action.assert_called_once()
    
    def test_execute_action_nat_gateway(self, action_executor, mock_clients, mock_audit_logger):
        """Test execute_action for NAT Gateway."""
        nat_resource = Resource(
            resource_id='nat-test123',
            resource_type='nat_gateway',
            service='nat_gateway',
            region='us-east-1',
            tags={},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
        
        mock_clients['ec2'].describe_nat_gateways.return_value = {
            'NatGateways': [{'NatGatewayId': 'nat-test123'}]
        }
        mock_clients['ec2'].delete_nat_gateway.return_value = {}
        
        result = action_executor.execute_action(nat_resource, 'delete')
        
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert result.resource_id == 'nat-test123'
        mock_audit_logger.log_action.assert_called_once()
    
    def test_execute_action_unsupported_service(self, action_executor, mock_audit_logger):
        """Test execute_action for unsupported service."""
        unsupported_resource = Resource(
            resource_id='unknown-123',
            resource_type='unknown',
            service='unsupported',
            region='us-east-1',
            tags={},
            state='active',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = action_executor.execute_action(unsupported_resource, 'stop')
        
        assert isinstance(result, ActionResult)
        assert result.success is False
        mock_audit_logger.log_action.assert_called_once()
    
    def test_execute_action_with_exception(self, action_executor, ec2_resource, mock_clients, mock_audit_logger):
        """Test execute_action when exception occurs."""
        mock_clients['ec2'].stop_instances.side_effect = Exception("API Error")
        
        result = action_executor.execute_action(ec2_resource, 'stop')
        
        assert isinstance(result, ActionResult)
        assert result.success is False
        # Service-specific methods catch exceptions and return False, so error_message is None
        assert result.error_message is None
        assert result.resource_id == 'i-test123'
        mock_audit_logger.log_action.assert_called_once()
    
    def test_get_resource_state(self, action_executor, ec2_resource):
        """Test getting resource state."""
        state = action_executor._get_resource_state(ec2_resource)
        
        assert state['resource_id'] == 'i-test123'
        assert state['state'] == 'running'
        assert state['service'] == 'ec2'
        assert 'timestamp' in state
    
    def test_estimate_savings(self, action_executor, ec2_resource):
        """Test estimating savings."""
        savings = action_executor._estimate_savings(ec2_resource)
        
        # Default estimate is $0.10/hour * 24 * 30 = $72/month (with floating point precision)
        assert abs(savings - 72.0) < 0.01
    
    def test_action_result_includes_pre_post_state(self, action_executor, ec2_resource, mock_clients, mock_audit_logger):
        """Test that action result includes pre and post action state."""
        mock_clients['ec2'].stop_instances.return_value = {}
        
        result = action_executor.execute_action(ec2_resource, 'stop')
        
        assert 'resource_id' in result.pre_action_state
        assert 'resource_id' in result.post_action_state
        assert result.pre_action_state['resource_id'] == 'i-test123'
        assert result.post_action_state['resource_id'] == 'i-test123'
    
    def test_action_result_includes_timestamp(self, action_executor, ec2_resource, mock_clients):
        """Test that action result includes timestamp."""
        mock_clients['ec2'].stop_instances.return_value = {}
        
        result = action_executor.execute_action(ec2_resource, 'stop')
        
        assert result.timestamp is not None
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(result.timestamp.replace('Z', '+00:00'))
    
    def test_audit_logger_called_on_success(self, action_executor, ec2_resource, mock_clients, mock_audit_logger):
        """Test that audit logger is called on successful action."""
        mock_clients['ec2'].stop_instances.return_value = {}
        
        action_executor.execute_action(ec2_resource, 'stop')
        
        mock_audit_logger.log_action.assert_called_once()
        call_args = mock_audit_logger.log_action.call_args[0][0]
        assert isinstance(call_args, ActionResult)
        assert call_args.success is True
    
    def test_audit_logger_called_on_failure(self, action_executor, ec2_resource, mock_clients, mock_audit_logger):
        """Test that audit logger is called on failed action."""
        mock_clients['ec2'].stop_instances.side_effect = Exception("API Error")
        
        action_executor.execute_action(ec2_resource, 'stop')
        
        mock_audit_logger.log_action.assert_called_once()
        call_args = mock_audit_logger.log_action.call_args[0][0]
        assert isinstance(call_args, ActionResult)
        assert call_args.success is False
        # Service-specific methods catch exceptions and return False, so error_message is None
        assert call_args.error_message is None
    
    def test_multiple_actions_on_different_resources(self, action_executor, mock_clients, mock_audit_logger):
        """Test executing multiple actions on different resources."""
        ec2_resource = Resource(
            resource_id='i-test1',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        rds_resource = Resource(
            resource_id='db-test1',
            resource_type='db_instance',
            service='rds',
            region='us-east-1',
            tags={},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
        
        mock_clients['ec2'].stop_instances.return_value = {}
        mock_clients['rds'].stop_db_instance.return_value = {}
        
        result1 = action_executor.execute_action(ec2_resource, 'stop')
        result2 = action_executor.execute_action(rds_resource, 'stop')
        
        assert result1.success is True
        assert result2.success is True
        assert result1.resource_id == 'i-test1'
        assert result2.resource_id == 'db-test1'
        assert mock_audit_logger.log_action.call_count == 2
    
    def test_limit_lambda_concurrency_with_custom_limit(self, action_executor, mock_clients):
        """Test limiting Lambda concurrency with custom limit."""
        mock_clients['lambda'].put_function_concurrency.return_value = {}
        
        result = action_executor.limit_lambda_concurrency('test-function', 10)
        
        assert result is True
        mock_clients['lambda'].put_function_concurrency.assert_called_once_with(
            FunctionName='test-function',
            ReservedConcurrentExecutions=10
        )
    
    def test_snapshot_includes_timestamp(self, action_executor, mock_clients):
        """Test that EBS snapshot includes timestamp in description."""
        mock_clients['ec2'].create_snapshot.return_value = {'SnapshotId': 'snap-123'}
        mock_clients['ec2'].delete_volume.return_value = {}
        
        action_executor._snapshot_and_delete_volume('vol-test123')
        
        call_args = mock_clients['ec2'].create_snapshot.call_args
        assert 'Description' in call_args[1]
        assert 'Automated snapshot before deletion' in call_args[1]['Description']
    
    def test_nat_gateway_documentation_logged(self, action_executor, mock_clients):
        """Test that NAT Gateway details are logged before deletion."""
        nat_details = {
            'NatGateways': [{
                'NatGatewayId': 'nat-123',
                'State': 'available',
                'SubnetId': 'subnet-123'
            }]
        }
        mock_clients['ec2'].describe_nat_gateways.return_value = nat_details
        mock_clients['ec2'].delete_nat_gateway.return_value = {}
        
        with patch('src.services.action_executor.logger') as mock_logger:
            result = action_executor._delete_nat_gateway('nat-123')
            
            assert result is True
            # Verify details were logged
            assert mock_logger.info.call_count >= 2
