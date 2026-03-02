"""
Unit tests for Multi-Account DynamoDB Repositories
Tests CRUD operations, error handling, GSI queries, and retry logic
"""
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch, call
from botocore.exceptions import ClientError
import time

from src.services.multi_account.repositories import (
    OrganizationRepository,
    AccountRepository,
    MultiAccountCostRepository,
    AllocationRuleRepository,
    BudgetRepository
)
from src.services.multi_account.models import (
    Organization,
    Account,
    AccountCostData,
    AllocationRule
)


class TestOrganizationRepository:
    """Test suite for OrganizationRepository"""
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Mock DynamoDB client"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_dynamodb):
        """Create repository instance"""
        return OrganizationRepository(dynamodb_client=mock_dynamodb)
    
    def test_save_organization(self, repository, mock_dynamodb):
        """Test saving organization"""
        org = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        
        mock_dynamodb.put_item.return_value = {}
        
        repository.save(org, ttl=1234567890)
        
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]['TableName'] == 'organizations'
        assert call_args[1]['Item']['org_id']['S'] == 'o-123456789'
    
    def test_get_organization_found(self, repository, mock_dynamodb):
        """Test getting organization that exists"""
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'org_id': {'S': 'o-123456789'},
                'arn': {'S': 'arn:aws:organizations::123456789012:organization/o-123456789'},
                'master_account_id': {'S': '123456789012'},
                'feature_set': {'S': 'ALL'}
            }
        }
        
        result = repository.get('o-123456789')
        
        assert result is not None
        assert result.id == 'o-123456789'
        assert result.master_account_id == '123456789012'
    
    def test_get_organization_not_found(self, repository, mock_dynamodb):
        """Test getting organization that doesn't exist"""
        mock_dynamodb.get_item.return_value = {}
        
        result = repository.get('o-nonexistent')
        
        assert result is None
    
    def test_save_organization_with_throttling_retry(self, repository, mock_dynamodb):
        """Test saving organization with throttling error and retry"""
        org = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        
        # First call fails with throttling, second succeeds
        mock_dynamodb.put_item.side_effect = [
            ClientError(
                error_response={'Error': {'Code': 'ProvisionedThroughputExceededException'}},
                operation_name='PutItem'
            ),
            {}
        ]
        
        with patch('time.sleep') as mock_sleep:
            repository.save(org, ttl=1234567890)
        
        assert mock_dynamodb.put_item.call_count == 2
        mock_sleep.assert_called_once()
    
    def test_save_organization_max_retries_exceeded(self, repository, mock_dynamodb):
        """Test saving organization when max retries exceeded"""
        org = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        
        # All calls fail with throttling
        mock_dynamodb.put_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ProvisionedThroughputExceededException'}},
            operation_name='PutItem'
        )
        
        with pytest.raises(ClientError):
            with patch('time.sleep'):
                repository.save(org, ttl=1234567890)
        
        assert mock_dynamodb.put_item.call_count == 4  # Initial + 3 retries
    
    def test_get_organization_with_client_error(self, repository, mock_dynamodb):
        """Test getting organization with client error"""
        mock_dynamodb.get_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ResourceNotFoundException'}},
            operation_name='GetItem'
        )
        
        with pytest.raises(ClientError):
            repository.get('o-123456789')
    
    def test_save_organization_with_validation_error(self, repository, mock_dynamodb):
        """Test saving organization with validation error"""
        mock_dynamodb.put_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ValidationException'}},
            operation_name='PutItem'
        )
        
        org = Organization(
            id='o-123456789',
            arn='arn:aws:organizations::123456789012:organization/o-123456789',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        
        with pytest.raises(ClientError):
            repository.save(org, ttl=1234567890)


class TestAccountRepository:
    """Test suite for AccountRepository"""
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Mock DynamoDB client"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_dynamodb):
        """Create repository instance"""
        return AccountRepository(dynamodb_client=mock_dynamodb)
    
    def test_save_account(self, repository, mock_dynamodb):
        """Test saving account"""
        account = Account(
            id='111111111111',
            arn='arn:aws:organizations::123456789012:account/o-123456789/111111111111',
            name='Test Account',
            email='test@example.com',
            status='ACTIVE',
            joined_method='CREATED',
            joined_timestamp=datetime(2024, 1, 1)
        )
        
        mock_dynamodb.put_item.return_value = {}
        
        repository.save(account, org_id='o-123456789')
        
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]['TableName'] == 'accounts'
        assert call_args[1]['Item']['account_id']['S'] == '111111111111'
    
    def test_get_account_found(self, repository, mock_dynamodb):
        """Test getting account that exists"""
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'account_id': {'S': '111111111111'},
                'arn': {'S': 'arn:aws:organizations::123456789012:account/o-123456789/111111111111'},
                'name': {'S': 'Test Account'},
                'email': {'S': 'test@example.com'},
                'status': {'S': 'ACTIVE'},
                'joined_method': {'S': 'CREATED'},
                'joined_timestamp': {'S': '2024-01-01T00:00:00'},
                'org_id': {'S': 'o-123456789'}
            }
        }
        
        result = repository.get('111111111111')
        
        assert result is not None
        assert result.id == '111111111111'
        assert result.name == 'Test Account'
        assert result.status == 'ACTIVE'
    
    def test_get_account_not_found(self, repository, mock_dynamodb):
        """Test getting account that doesn't exist"""
        mock_dynamodb.get_item.return_value = {}
        
        result = repository.get('999999999999')
        
        assert result is None
    
    def test_list_by_organization(self, repository, mock_dynamodb):
        """Test listing accounts by organization using GSI"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'account_id': {'S': '111111111111'},
                    'name': {'S': 'Account 1'},
                    'email': {'S': 'account1@example.com'},
                    'status': {'S': 'ACTIVE'},
                    'org_id': {'S': 'o-123456789'}
                },
                {
                    'account_id': {'S': '222222222222'},
                    'name': {'S': 'Account 2'},
                    'email': {'S': 'account2@example.com'},
                    'status': {'S': 'ACTIVE'},
                    'org_id': {'S': 'o-123456789'}
                }
            ]
        }
        
        result = repository.list_by_organization('o-123456789')
        
        assert len(result) == 2
        assert result[0].id == '111111111111'
        assert result[1].id == '222222222222'
        
        # Verify GSI query was used
        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert call_args[1]['IndexName'] == 'org_id-index'
    
    def test_list_by_organization_with_throttling(self, repository, mock_dynamodb):
        """Test listing accounts with throttling error and retry"""
        # First call fails with throttling, second succeeds
        mock_dynamodb.query.side_effect = [
            ClientError(
                error_response={'Error': {'Code': 'ThrottlingException'}},
                operation_name='Query'
            ),
            {
                'Items': [
                    {
                        'account_id': {'S': '111111111111'},
                        'name': {'S': 'Account 1'},
                        'email': {'S': 'account1@example.com'},
                        'status': {'S': 'ACTIVE'},
                        'org_id': {'S': 'o-123456789'}
                    }
                ]
            }
        ]
        
        with patch('time.sleep') as mock_sleep:
            result = repository.list_by_organization('o-123456789')
        
        assert len(result) == 1
        assert mock_dynamodb.query.call_count == 2
        mock_sleep.assert_called_once()
    
    def test_list_by_organization_empty_result(self, repository, mock_dynamodb):
        """Test listing accounts when organization has no accounts"""
        mock_dynamodb.query.return_value = {'Items': []}
        
        result = repository.list_by_organization('o-empty')
        
        assert len(result) == 0
    
    def test_save_account_with_update(self, repository, mock_dynamodb):
        """Test saving account that already exists (update scenario)"""
        account = Account(
            id='111111111111',
            arn='arn:aws:organizations::123456789012:account/o-123456789/111111111111',
            name='Updated Account Name',
            email='updated@example.com',
            status='ACTIVE',
            joined_method='CREATED',
            joined_timestamp=datetime(2024, 1, 1)
        )
        
        mock_dynamodb.put_item.return_value = {}
        
        repository.save(account, org_id='o-123456789')
        
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]['Item']['name']['S'] == 'Updated Account Name'
        assert call_args[1]['Item']['email']['S'] == 'updated@example.com'
    
    def test_save_account_with_conditional_check_failed(self, repository, mock_dynamodb):
        """Test saving account with conditional check failed error"""
        account = Account(
            id='111111111111',
            arn='arn:aws:organizations::123456789012:account/o-123456789/111111111111',
            name='Test Account',
            email='test@example.com',
            status='ACTIVE',
            joined_method='CREATED',
            joined_timestamp=datetime(2024, 1, 1)
        )
        
        mock_dynamodb.put_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ConditionalCheckFailedException'}},
            operation_name='PutItem'
        )
        
        with pytest.raises(ClientError):
            repository.save(account, org_id='o-123456789')


class TestMultiAccountCostRepository:
    """Test suite for MultiAccountCostRepository"""
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Mock DynamoDB client"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_dynamodb):
        """Create repository instance"""
        return MultiAccountCostRepository(dynamodb_client=mock_dynamodb)
    
    def test_save_cost_data(self, repository, mock_dynamodb):
        """Test saving cost data"""
        cost_data = AccountCostData(
            account_id='111111111111',
            start_date='2024-01-01',
            end_date='2024-01-01',
            total_cost=Decimal('100.50'),
            costs_by_service={'EC2': Decimal('50.25'), 'S3': Decimal('50.25')},
            costs_by_day={'2024-01-01': Decimal('100.50')},
            collection_timestamp=datetime(2024, 1, 1),
            status='SUCCESS'
        )
        
        mock_dynamodb.put_item.return_value = {}
        
        repository.save(cost_data)
        
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]['TableName'] == 'multi_account_costs'
        assert call_args[1]['Item']['account_id']['S'] == '111111111111'
    
    def test_get_cost_data(self, repository, mock_dynamodb):
        """Test getting cost data"""
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'account_id': {'S': '111111111111'},
                'date': {'S': '2024-01-01'},
                'total_cost': {'N': '100.50'},
                'costs_by_service': {
                    'M': {
                        'EC2': {'N': '50.25'},
                        'S3': {'N': '50.25'}
                    }
                },
                'costs_by_day': {
                    'M': {
                        '2024-01-01': {'N': '100.50'}
                    }
                },
                'collection_timestamp': {'N': '1704067200'},
                'status': {'S': 'SUCCESS'}
            }
        }
        
        result = repository.get('111111111111', '2024-01-01')
        
        assert result is not None
        assert result.account_id == '111111111111'
        assert result.total_cost == Decimal('100.50')
        assert 'EC2' in result.costs_by_service
        assert result.status == 'SUCCESS'
    
    def test_get_cost_data_not_found(self, repository, mock_dynamodb):
        """Test getting cost data that doesn't exist"""
        mock_dynamodb.get_item.return_value = {}
        
        result = repository.get('999999999999', '2024-01-01')
        
        assert result is None
    
    def test_list_by_date(self, repository, mock_dynamodb):
        """Test listing cost data by date using GSI"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'account_id': {'S': '111111111111'},
                    'date': {'S': '2024-01-01'},
                    'total_cost': {'N': '100.50'},
                    'costs_by_service': {'M': {}},
                    'costs_by_day': {'M': {}},
                    'collection_timestamp': {'N': '1704067200'},
                    'status': {'S': 'SUCCESS'}
                },
                {
                    'account_id': {'S': '222222222222'},
                    'date': {'S': '2024-01-01'},
                    'total_cost': {'N': '200.75'},
                    'costs_by_service': {'M': {}},
                    'costs_by_day': {'M': {}},
                    'collection_timestamp': {'N': '1704067200'},
                    'status': {'S': 'SUCCESS'}
                }
            ]
        }
        
        result = repository.list_by_date('2024-01-01')
        
        assert len(result) == 2
        assert result[0].account_id == '111111111111'
        assert result[1].account_id == '222222222222'
        
        # Verify GSI query was used
        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert call_args[1]['IndexName'] == 'date-index'
    
    def test_list_by_date_with_pagination(self, repository, mock_dynamodb):
        """Test listing cost data by date with pagination"""
        # First call returns partial results with LastEvaluatedKey
        # Second call returns remaining results
        mock_dynamodb.query.side_effect = [
            {
                'Items': [
                    {
                        'account_id': {'S': '111111111111'},
                        'date': {'S': '2024-01-01'},
                        'total_cost': {'N': '100.50'},
                        'costs_by_service': {'M': {}},
                        'costs_by_day': {'M': {}},
                        'collection_timestamp': {'N': '1704067200'},
                        'status': {'S': 'SUCCESS'}
                    }
                ],
                'LastEvaluatedKey': {'account_id': {'S': '111111111111'}}
            },
            {
                'Items': [
                    {
                        'account_id': {'S': '222222222222'},
                        'date': {'S': '2024-01-01'},
                        'total_cost': {'N': '200.75'},
                        'costs_by_service': {'M': {}},
                        'costs_by_day': {'M': {}},
                        'collection_timestamp': {'N': '1704067200'},
                        'status': {'S': 'SUCCESS'}
                    }
                ]
            }
        ]
        
        result = repository.list_by_date('2024-01-01')
        
        assert len(result) == 2
        assert mock_dynamodb.query.call_count == 2
    
    def test_save_cost_data_with_batch_write(self, repository, mock_dynamodb):
        """Test saving multiple cost data items using batch write"""
        cost_data_list = [
            AccountCostData(
                account_id='111111111111',
                start_date='2024-01-01',
                end_date='2024-01-01',
                total_cost=Decimal('100.50'),
                costs_by_service={'EC2': Decimal('50.25')},
                costs_by_day={'2024-01-01': Decimal('100.50')},
                collection_timestamp=datetime(2024, 1, 1),
                status='SUCCESS'
            ),
            AccountCostData(
                account_id='222222222222',
                start_date='2024-01-01',
                end_date='2024-01-01',
                total_cost=Decimal('200.75'),
                costs_by_service={'S3': Decimal('200.75')},
                costs_by_day={'2024-01-01': Decimal('200.75')},
                collection_timestamp=datetime(2024, 1, 1),
                status='SUCCESS'
            )
        ]
        
        mock_dynamodb.batch_write_item.return_value = {'UnprocessedItems': {}}
        
        repository.batch_save(cost_data_list)
        
        mock_dynamodb.batch_write_item.assert_called_once()
        call_args = mock_dynamodb.batch_write_item.call_args
        assert len(call_args[1]['RequestItems']['multi_account_costs']) == 2
    
    def test_save_cost_data_with_item_size_limit(self, repository, mock_dynamodb):
        """Test saving cost data that exceeds DynamoDB item size limit"""
        # Create cost data with very large service breakdown
        large_costs_by_service = {f'Service{i}': Decimal('1.00') for i in range(1000)}
        
        cost_data = AccountCostData(
            account_id='111111111111',
            start_date='2024-01-01',
            end_date='2024-01-01',
            total_cost=Decimal('1000.00'),
            costs_by_service=large_costs_by_service,
            costs_by_day={'2024-01-01': Decimal('1000.00')},
            collection_timestamp=datetime(2024, 1, 1),
            status='SUCCESS'
        )
        
        mock_dynamodb.put_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ItemSizeTooLargeException'}},
            operation_name='PutItem'
        )
        
        with pytest.raises(ClientError):
            repository.save(cost_data)
    
    def test_list_by_date_with_filter_expression(self, repository, mock_dynamodb):
        """Test listing cost data by date with filter for successful collections only"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'account_id': {'S': '111111111111'},
                    'date': {'S': '2024-01-01'},
                    'total_cost': {'N': '100.50'},
                    'costs_by_service': {'M': {}},
                    'costs_by_day': {'M': {}},
                    'collection_timestamp': {'N': '1704067200'},
                    'status': {'S': 'SUCCESS'}
                }
            ]
        }
        
        result = repository.list_by_date('2024-01-01', status_filter='SUCCESS')
        
        assert len(result) == 1
        assert result[0].status == 'SUCCESS'
        
        # Verify filter expression was used
        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert 'FilterExpression' in call_args[1]


class TestAllocationRuleRepository:
    """Test suite for AllocationRuleRepository"""
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Mock DynamoDB client"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_dynamodb):
        """Create repository instance"""
        return AllocationRuleRepository(dynamodb_client=mock_dynamodb)
    
    def test_save_rule(self, repository, mock_dynamodb):
        """Test saving allocation rule"""
        rule = AllocationRule(
            rule_id='rule-123',
            name='Team A Rule',
            priority=1,
            rule_type='TAG_BASED',
            conditions={'Team': 'TeamA'},
            allocation_target='TeamA'
        )
        
        mock_dynamodb.put_item.return_value = {}
        
        repository.save(rule, org_id='o-123456789')
        
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]['TableName'] == 'allocation_rules'
        assert call_args[1]['Item']['rule_id']['S'] == 'rule-123'
    
    def test_list_by_organization(self, repository, mock_dynamodb):
        """Test listing rules by organization using GSI with priority sorting"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'rule_id': {'S': 'rule-1'},
                    'name': {'S': 'Rule 1'},
                    'priority': {'N': '1'},
                    'rule_type': {'S': 'TAG_BASED'},
                    'conditions': {'M': {'Team': {'S': 'TeamA'}}},
                    'allocation_target': {'S': 'TeamA'},
                    'org_id': {'S': 'o-123456789'}
                },
                {
                    'rule_id': {'S': 'rule-2'},
                    'name': {'S': 'Rule 2'},
                    'priority': {'N': '2'},
                    'rule_type': {'S': 'TAG_BASED'},
                    'conditions': {'M': {'Team': {'S': 'TeamB'}}},
                    'allocation_target': {'S': 'TeamB'},
                    'org_id': {'S': 'o-123456789'}
                }
            ]
        }
        
        result = repository.list_by_organization('o-123456789')
        
        assert len(result) == 2
        assert result[0].rule_id == 'rule-1'
        assert result[0].priority == 1
        assert result[1].rule_id == 'rule-2'
        assert result[1].priority == 2
        
        # Verify GSI query with priority sorting was used
        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert call_args[1]['IndexName'] == 'org_id-priority-index'
        assert call_args[1]['ScanIndexForward'] is True  # Ascending order by priority
    
    def test_get_rule_by_id(self, repository, mock_dynamodb):
        """Test getting allocation rule by ID"""
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'rule_id': {'S': 'rule-123'},
                'name': {'S': 'Team A Rule'},
                'priority': {'N': '1'},
                'rule_type': {'S': 'TAG_BASED'},
                'conditions': {'M': {'Team': {'S': 'TeamA'}}},
                'allocation_target': {'S': 'TeamA'},
                'org_id': {'S': 'o-123456789'}
            }
        }
        
        result = repository.get('rule-123')
        
        assert result is not None
        assert result.rule_id == 'rule-123'
        assert result.name == 'Team A Rule'
        assert result.rule_type == 'TAG_BASED'
    
    def test_get_rule_not_found(self, repository, mock_dynamodb):
        """Test getting allocation rule that doesn't exist"""
        mock_dynamodb.get_item.return_value = {}
        
        result = repository.get('rule-nonexistent')
        
        assert result is None
    
    def test_delete_rule(self, repository, mock_dynamodb):
        """Test deleting allocation rule"""
        mock_dynamodb.delete_item.return_value = {}
        
        repository.delete('rule-123')
        
        mock_dynamodb.delete_item.assert_called_once()
        call_args = mock_dynamodb.delete_item.call_args
        assert call_args[1]['TableName'] == 'allocation_rules'
        assert call_args[1]['Key']['rule_id']['S'] == 'rule-123'
    
    def test_update_rule_priority(self, repository, mock_dynamodb):
        """Test updating rule priority"""
        mock_dynamodb.update_item.return_value = {}
        
        repository.update_priority('rule-123', new_priority=5)
        
        mock_dynamodb.update_item.assert_called_once()
        call_args = mock_dynamodb.update_item.call_args
        assert call_args[1]['TableName'] == 'allocation_rules'
        assert call_args[1]['Key']['rule_id']['S'] == 'rule-123'
        assert 'priority' in call_args[1]['UpdateExpression']
    
    def test_list_by_organization_with_rule_type_filter(self, repository, mock_dynamodb):
        """Test listing rules by organization with rule type filter"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'rule_id': {'S': 'rule-1'},
                    'name': {'S': 'Tag Rule'},
                    'priority': {'N': '1'},
                    'rule_type': {'S': 'TAG_BASED'},
                    'conditions': {'M': {'Team': {'S': 'TeamA'}}},
                    'allocation_target': {'S': 'TeamA'},
                    'org_id': {'S': 'o-123456789'}
                }
            ]
        }
        
        result = repository.list_by_organization('o-123456789', rule_type='TAG_BASED')
        
        assert len(result) == 1
        assert result[0].rule_type == 'TAG_BASED'
        
        # Verify filter expression was used
        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert 'FilterExpression' in call_args[1]
    
    def test_save_rule_with_duplicate_priority(self, repository, mock_dynamodb):
        """Test saving rule with duplicate priority in same organization"""
        rule = AllocationRule(
            rule_id='rule-456',
            name='Duplicate Priority Rule',
            priority=1,  # Same priority as existing rule
            rule_type='PERCENTAGE',
            conditions={'percentage': 50},
            allocation_target='TeamB'
        )
        
        mock_dynamodb.put_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ConditionalCheckFailedException'}},
            operation_name='PutItem'
        )
        
        with pytest.raises(ClientError):
            repository.save(rule, org_id='o-123456789')


class TestBudgetRepository:
    """Test suite for BudgetRepository"""
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Mock DynamoDB client"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_dynamodb):
        """Create repository instance"""
        return BudgetRepository(dynamodb_client=mock_dynamodb)
    
    def test_save_budget(self, repository, mock_dynamodb):
        """Test saving budget"""
        mock_dynamodb.put_item.return_value = {}
        
        repository.save(
            budget_id='budget-123',
            entity_id='o-123456789',
            entity_type='ORGANIZATION',
            budget_data={
                'budget_amount': Decimal('10000'),
                'time_period': 'MONTHLY',
                'alert_threshold': 80.0,
                'created_at': '2024-01-01T00:00:00Z'
            }
        )
        
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]['TableName'] == 'budgets'
        assert call_args[1]['Item']['budget_id']['S'] == 'budget-123'
        assert call_args[1]['Item']['entity_type']['S'] == 'ORGANIZATION'
    
    def test_get_budget(self, repository, mock_dynamodb):
        """Test getting budget"""
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'budget_id': {'S': 'budget-123'},
                'entity_id': {'S': 'o-123456789'},
                'entity_type': {'S': 'ORGANIZATION'},
                'budget_amount': {'N': '10000'},
                'time_period': {'S': 'MONTHLY'},
                'alert_threshold': {'N': '80.0'},
                'current_spend': {'N': '5000'},
                'utilization_percentage': {'N': '50.0'},
                'created_at': {'S': '2024-01-01T00:00:00Z'}
            }
        }
        
        result = repository.get('budget-123')
        
        assert result is not None
        assert result['budget_id'] == 'budget-123'
        assert result['budget_amount'] == Decimal('10000')
        assert result['utilization_percentage'] == 50.0
        assert result['entity_type'] == 'ORGANIZATION'
    
    def test_get_budget_not_found(self, repository, mock_dynamodb):
        """Test getting budget that doesn't exist"""
        mock_dynamodb.get_item.return_value = {}
        
        result = repository.get('budget-nonexistent')
        
        assert result is None
    
    def test_list_by_entity(self, repository, mock_dynamodb):
        """Test listing budgets by entity using GSI"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'budget_id': {'S': 'budget-1'},
                    'entity_id': {'S': 'o-123456789'},
                    'entity_type': {'S': 'ORGANIZATION'},
                    'budget_amount': {'N': '10000'},
                    'time_period': {'S': 'MONTHLY'},
                    'current_spend': {'N': '5000'},
                    'utilization_percentage': {'N': '50.0'}
                },
                {
                    'budget_id': {'S': 'budget-2'},
                    'entity_id': {'S': 'o-123456789'},
                    'entity_type': {'S': 'ORGANIZATION'},
                    'budget_amount': {'N': '20000'},
                    'time_period': {'S': 'QUARTERLY'},
                    'current_spend': {'N': '8000'},
                    'utilization_percentage': {'N': '40.0'}
                }
            ]
        }
        
        result = repository.list_by_entity('o-123456789', 'ORGANIZATION')
        
        assert len(result) == 2
        assert result[0]['budget_id'] == 'budget-1'
        assert result[1]['budget_id'] == 'budget-2'
        
        # Verify GSI query was used
        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert call_args[1]['IndexName'] == 'entity-index'
    
    def test_update_budget_spend(self, repository, mock_dynamodb):
        """Test updating budget current spend and utilization"""
        mock_dynamodb.update_item.return_value = {
            'Attributes': {
                'budget_id': {'S': 'budget-123'},
                'current_spend': {'N': '7500'},
                'utilization_percentage': {'N': '75.0'}
            }
        }
        
        result = repository.update_spend('budget-123', current_spend=Decimal('7500'))
        
        mock_dynamodb.update_item.assert_called_once()
        call_args = mock_dynamodb.update_item.call_args
        assert call_args[1]['TableName'] == 'budgets'
        assert call_args[1]['Key']['budget_id']['S'] == 'budget-123'
        assert 'current_spend' in call_args[1]['UpdateExpression']
        assert 'utilization_percentage' in call_args[1]['UpdateExpression']
        
        assert result['current_spend'] == Decimal('7500')
        assert result['utilization_percentage'] == 75.0
    
    def test_delete_budget(self, repository, mock_dynamodb):
        """Test deleting budget"""
        mock_dynamodb.delete_item.return_value = {}
        
        repository.delete('budget-123')
        
        mock_dynamodb.delete_item.assert_called_once()
        call_args = mock_dynamodb.delete_item.call_args
        assert call_args[1]['TableName'] == 'budgets'
        assert call_args[1]['Key']['budget_id']['S'] == 'budget-123'
    
    def test_list_by_entity_with_time_period_filter(self, repository, mock_dynamodb):
        """Test listing budgets by entity with time period filter"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'budget_id': {'S': 'budget-1'},
                    'entity_id': {'S': 'o-123456789'},
                    'entity_type': {'S': 'ORGANIZATION'},
                    'budget_amount': {'N': '10000'},
                    'time_period': {'S': 'MONTHLY'},
                    'current_spend': {'N': '5000'},
                    'utilization_percentage': {'N': '50.0'}
                }
            ]
        }
        
        result = repository.list_by_entity(
            'o-123456789', 
            'ORGANIZATION', 
            time_period_filter='MONTHLY'
        )
        
        assert len(result) == 1
        assert result[0]['time_period'] == 'MONTHLY'
        
        # Verify filter expression was used
        mock_dynamodb.query.assert_called_once()
        call_args = mock_dynamodb.query.call_args
        assert 'FilterExpression' in call_args[1]
    
    def test_list_over_budget_entities(self, repository, mock_dynamodb):
        """Test listing entities that are over budget"""
        mock_dynamodb.scan.return_value = {
            'Items': [
                {
                    'budget_id': {'S': 'budget-1'},
                    'entity_id': {'S': 'account-111111111111'},
                    'entity_type': {'S': 'ACCOUNT'},
                    'budget_amount': {'N': '1000'},
                    'current_spend': {'N': '1200'},
                    'utilization_percentage': {'N': '120.0'}
                },
                {
                    'budget_id': {'S': 'budget-2'},
                    'entity_id': {'S': 'ou-987654321'},
                    'entity_type': {'S': 'OU'},
                    'budget_amount': {'N': '5000'},
                    'current_spend': {'N': '5500'},
                    'utilization_percentage': {'N': '110.0'}
                }
            ]
        }
        
        result = repository.list_over_budget()
        
        assert len(result) == 2
        assert all(budget['utilization_percentage'] > 100.0 for budget in result)
        
        # Verify scan with filter expression was used
        mock_dynamodb.scan.assert_called_once()
        call_args = mock_dynamodb.scan.call_args
        assert 'FilterExpression' in call_args[1]
    
    def test_save_budget_with_invalid_entity_type(self, repository, mock_dynamodb):
        """Test saving budget with invalid entity type"""
        mock_dynamodb.put_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ValidationException'}},
            operation_name='PutItem'
        )
        
        with pytest.raises(ClientError):
            repository.save(
                budget_id='budget-123',
                entity_id='invalid-entity',
                entity_type='INVALID_TYPE',
                budget_data={'budget_amount': Decimal('1000')}
            )
    
    def test_concurrent_budget_update(self, repository, mock_dynamodb):
        """Test concurrent budget update with conditional check"""
        mock_dynamodb.update_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ConditionalCheckFailedException'}},
            operation_name='UpdateItem'
        )
        
        with pytest.raises(ClientError):
            repository.update_spend(
                'budget-123', 
                current_spend=Decimal('7500'),
                expected_version=1
            )
