"""
Unit tests for Multi-Account DynamoDB Repositories
"""
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock
from botocore.exceptions import ClientError

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
    
    def test_list_by_organization(self, repository, mock_dynamodb):
        """Test listing accounts by organization"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'account_id': {'S': '111111111111'},
                    'name': {'S': 'Account 1'},
                    'email': {'S': 'account1@example.com'},
                    'status': {'S': 'ACTIVE'}
                },
                {
                    'account_id': {'S': '222222222222'},
                    'name': {'S': 'Account 2'},
                    'email': {'S': 'account2@example.com'},
                    'status': {'S': 'ACTIVE'}
                }
            ]
        }
        
        result = repository.list_by_organization('o-123456789')
        
        assert len(result) == 2
        assert result[0].id == '111111111111'
        assert result[1].id == '222222222222'


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
                'collection_timestamp': {'N': '1704067200'}
            }
        }
        
        result = repository.get('111111111111', '2024-01-01')
        
        assert result is not None
        assert result.account_id == '111111111111'
        assert result.total_cost == Decimal('100.50')
        assert 'EC2' in result.costs_by_service
    
    def test_list_by_date(self, repository, mock_dynamodb):
        """Test listing cost data by date"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'account_id': {'S': '111111111111'},
                    'date': {'S': '2024-01-01'},
                    'total_cost': {'N': '100.50'},
                    'costs_by_service': {'M': {}},
                    'costs_by_day': {'M': {}},
                    'collection_timestamp': {'N': '1704067200'}
                },
                {
                    'account_id': {'S': '222222222222'},
                    'date': {'S': '2024-01-01'},
                    'total_cost': {'N': '200.75'},
                    'costs_by_service': {'M': {}},
                    'costs_by_day': {'M': {}},
                    'collection_timestamp': {'N': '1704067200'}
                }
            ]
        }
        
        result = repository.list_by_date('2024-01-01')
        
        assert len(result) == 2
        assert result[0].account_id == '111111111111'
        assert result[1].account_id == '222222222222'


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
        """Test listing rules by organization"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'rule_id': {'S': 'rule-1'},
                    'name': {'S': 'Rule 1'},
                    'priority': {'N': '1'},
                    'rule_type': {'S': 'TAG_BASED'},
                    'conditions': {'M': {'Team': {'S': 'TeamA'}}},
                    'allocation_target': {'S': 'TeamA'}
                },
                {
                    'rule_id': {'S': 'rule-2'},
                    'name': {'S': 'Rule 2'},
                    'priority': {'N': '2'},
                    'rule_type': {'S': 'TAG_BASED'},
                    'conditions': {'M': {'Team': {'S': 'TeamB'}}},
                    'allocation_target': {'S': 'TeamB'}
                }
            ]
        }
        
        result = repository.list_by_organization('o-123456789')
        
        assert len(result) == 2
        assert result[0].rule_id == 'rule-1'
        assert result[0].priority == 1


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
            budget_amount=Decimal('10000'),
            period='MONTHLY'
        )
        
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args
        assert call_args[1]['TableName'] == 'budgets'
        assert call_args[1]['Item']['budget_id']['S'] == 'budget-123'
    
    def test_get_budget(self, repository, mock_dynamodb):
        """Test getting budget"""
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'budget_id': {'S': 'budget-123'},
                'entity_id': {'S': 'o-123456789'},
                'entity_type': {'S': 'ORGANIZATION'},
                'budget_amount': {'N': '10000'},
                'period': {'S': 'MONTHLY'},
                'current_spend': {'N': '5000'},
                'utilization_percentage': {'N': '50.0'}
            }
        }
        
        result = repository.get('budget-123')
        
        assert result is not None
        assert result['budget_id'] == 'budget-123'
        assert result['budget_amount'] == Decimal('10000')
        assert result['utilization_percentage'] == 50.0
    
    def test_list_by_entity(self, repository, mock_dynamodb):
        """Test listing budgets by entity"""
        mock_dynamodb.query.return_value = {
            'Items': [
                {
                    'budget_id': {'S': 'budget-1'},
                    'entity_id': {'S': 'o-123456789'},
                    'entity_type': {'S': 'ORGANIZATION'},
                    'budget_amount': {'N': '10000'},
                    'period': {'S': 'MONTHLY'},
                    'current_spend': {'N': '5000'},
                    'utilization_percentage': {'N': '50.0'}
                }
            ]
        }
        
        result = repository.list_by_entity('o-123456789', 'ORGANIZATION')
        
        assert len(result) == 1
        assert result[0]['budget_id'] == 'budget-1'
