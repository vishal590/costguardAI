"""
Unit tests for Cross-Account AI Advisor Service
"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from src.services.multi_account.cross_account_advisor_service import CrossAccountAdvisorService
from src.services.multi_account.models import (
    Account, AccountCostData, AggregatedCosts, AllocationResult, AccountSpending
)
from src.utils.types import QueryIntent


@pytest.fixture
def mock_repositories():
    """Create mock repositories"""
    return {
        'org_repo': Mock(),
        'account_repo': Mock(),
        'cost_repo': Mock()
    }


@pytest.fixture
def mock_engines():
    """Create mock engines"""
    return {
        'aggregation_engine': Mock(),
        'allocation_engine': Mock()
    }


@pytest.fixture
def advisor_service(mock_repositories, mock_engines):
    """Create advisor service with mocked dependencies"""
    return CrossAccountAdvisorService(
        context_manager=Mock(),
        org_repository=mock_repositories['org_repo'],
        account_repository=mock_repositories['account_repo'],
        cost_repository=mock_repositories['cost_repo'],
        aggregation_engine=mock_engines['aggregation_engine'],
        allocation_engine=mock_engines['allocation_engine']
    )


@pytest.fixture
def sample_intent():
    """Create sample query intent"""
    return QueryIntent(
        intent_type='cost_analysis',
        services=['EC2', 'S3'],
        time_range=(
            datetime.now() - timedelta(days=30),
            datetime.now()
        ),
        accounts=[],
        entities={}
    )


@pytest.fixture
def sample_accounts():
    """Create sample accounts"""
    return [
        Account(
            id='111111111111',
            arn='arn:aws:organizations::111111111111:account/o-test/111111111111',
            name='Production',
            email='prod@example.com',
            status='ACTIVE',
            joined_method='CREATED',
            joined_timestamp=datetime.now()
        ),
        Account(
            id='222222222222',
            arn='arn:aws:organizations::222222222222:account/o-test/222222222222',
            name='Development',
            email='dev@example.com',
            status='ACTIVE',
            joined_method='CREATED',
            joined_timestamp=datetime.now()
        )
    ]


def test_get_organization_context_success(advisor_service, mock_repositories, mock_engines, sample_intent, sample_accounts):
    """Test getting organization context successfully"""
    # Arrange
    org_id = 'o-test123'
    mock_repositories['account_repo'].list_by_organization.return_value = sample_accounts
    
    aggregated = AggregatedCosts(
        entity_id=org_id,
        entity_type='ORGANIZATION',
        start_date='2024-01-01',
        end_date='2024-01-31',
        total_cost=Decimal('1000.00'),
        account_count=2,
        costs_by_account={
            '111111111111': Decimal('600.00'),
            '222222222222': Decimal('400.00')
        },
        costs_by_service={
            'EC2': Decimal('700.00'),
            'S3': Decimal('300.00')
        },
        costs_by_day={}
    )
    mock_engines['aggregation_engine'].aggregate_organization_costs.return_value = aggregated
    
    top_accounts = [
        AccountSpending(
            account_id='111111111111',
            account_name='Production',
            total_cost=Decimal('600.00'),
            percentage_of_total=60.0
        ),
        AccountSpending(
            account_id='222222222222',
            account_name='Development',
            total_cost=Decimal('400.00'),
            percentage_of_total=40.0
        )
    ]
    mock_engines['aggregation_engine'].get_top_spending_accounts.return_value = top_accounts
    
    allocation_result = AllocationResult(
        total_cost=Decimal('1000.00'),
        allocated_cost=Decimal('800.00'),
        unallocated_cost=Decimal('200.00'),
        allocation_percentage=80.0,
        allocations_by_category={'Team:Engineering': Decimal('800.00')}
    )
    mock_engines['allocation_engine'].allocate_by_tags.return_value = allocation_result
    
    # Act
    context = advisor_service.get_organization_context(org_id, sample_intent)
    
    # Assert
    assert context['organization_id'] == org_id
    assert context['account_count'] == 2
    assert context['total_cost'] == 1000.00
    assert 'EC2' in context['costs_by_service']
    assert 'S3' in context['costs_by_service']
    assert len(context['top_spending_accounts']) == 2
    assert context['top_spending_accounts'][0]['account_id'] == '111111111111'
    assert 'allocation_insights' in context
    
    # Verify repository calls
    mock_repositories['account_repo'].list_by_organization.assert_called_once_with(org_id)
    mock_engines['aggregation_engine'].aggregate_organization_costs.assert_called_once()


def test_get_organization_context_no_accounts(advisor_service, mock_repositories, sample_intent):
    """Test getting organization context with no accounts"""
    # Arrange
    org_id = 'o-test123'
    mock_repositories['account_repo'].list_by_organization.return_value = []
    
    # Act
    context = advisor_service.get_organization_context(org_id, sample_intent)
    
    # Assert
    assert context['organization_id'] == org_id
    assert context['account_count'] == 0
    assert 'error' in context


def test_get_account_context_success(advisor_service, mock_repositories, mock_engines, sample_intent):
    """Test getting account context successfully"""
    # Arrange
    account_id = '111111111111'
    account = Account(
        id=account_id,
        arn='arn:aws:organizations::111111111111:account/o-test/111111111111',
        name='Production',
        email='prod@example.com',
        status='ACTIVE',
        joined_method='CREATED',
        joined_timestamp=datetime.now()
    )
    mock_repositories['account_repo'].get.return_value = account
    
    cost_data = AccountCostData(
        account_id=account_id,
        start_date='2024-01-01',
        end_date='2024-01-31',
        total_cost=Decimal('500.00'),
        costs_by_service={
            'EC2': Decimal('300.00'),
            'S3': Decimal('200.00')
        },
        costs_by_day={},
        collection_timestamp=datetime.now(),
        status='SUCCESS'
    )
    mock_repositories['cost_repo'].get.return_value = cost_data
    
    allocation_result = AllocationResult(
        total_cost=Decimal('500.00'),
        allocated_cost=Decimal('400.00'),
        unallocated_cost=Decimal('100.00'),
        allocation_percentage=80.0,
        allocations_by_category={'Team:Engineering': Decimal('400.00')}
    )
    mock_engines['allocation_engine'].allocate_by_tags.return_value = allocation_result
    
    # Act
    context = advisor_service.get_account_context(account_id, sample_intent)
    
    # Assert
    assert context['account_id'] == account_id
    assert context['account_name'] == 'Production'
    assert context['total_cost'] == 500.00
    assert 'EC2' in context['costs_by_service']
    assert 'S3' in context['costs_by_service']
    assert context['allocation']['allocation_percentage'] == 80.0
    assert context['allocation']['unallocated_cost'] == 100.00
    
    # Verify repository calls
    mock_repositories['account_repo'].get.assert_called_once_with(account_id)
    mock_repositories['cost_repo'].get.assert_called_once()


def test_get_account_context_not_found(advisor_service, mock_repositories, sample_intent):
    """Test getting account context for non-existent account"""
    # Arrange
    account_id = '999999999999'
    mock_repositories['account_repo'].get.return_value = None
    
    # Act
    context = advisor_service.get_account_context(account_id, sample_intent)
    
    # Assert
    assert context['account_id'] == account_id
    assert 'error' in context
    assert context['error'] == 'Account not found'


def test_get_account_context_no_cost_data(advisor_service, mock_repositories, sample_intent):
    """Test getting account context with no cost data"""
    # Arrange
    account_id = '111111111111'
    account = Account(
        id=account_id,
        arn='arn:aws:organizations::111111111111:account/o-test/111111111111',
        name='Production',
        email='prod@example.com',
        status='ACTIVE',
        joined_method='CREATED',
        joined_timestamp=datetime.now()
    )
    mock_repositories['account_repo'].get.return_value = account
    mock_repositories['cost_repo'].get.return_value = None
    
    # Act
    context = advisor_service.get_account_context(account_id, sample_intent)
    
    # Assert
    assert context['account_id'] == account_id
    assert context['account_name'] == 'Production'
    assert 'error' in context
    assert context['error'] == 'No cost data found'


def test_enhance_prompt_with_organization_context(advisor_service, mock_repositories, mock_engines, sample_intent, sample_accounts):
    """Test enhancing prompt with organization context"""
    # Arrange
    org_id = 'o-test123'
    base_prompt = "Analyze my AWS costs"
    
    mock_repositories['account_repo'].list_by_organization.return_value = sample_accounts
    
    aggregated = AggregatedCosts(
        entity_id=org_id,
        entity_type='ORGANIZATION',
        start_date='2024-01-01',
        end_date='2024-01-31',
        total_cost=Decimal('1000.00'),
        account_count=2,
        costs_by_account={},
        costs_by_service={},
        costs_by_day={}
    )
    mock_engines['aggregation_engine'].aggregate_organization_costs.return_value = aggregated
    
    top_accounts = [
        AccountSpending(
            account_id='111111111111',
            account_name='Production',
            total_cost=Decimal('600.00'),
            percentage_of_total=60.0
        )
    ]
    mock_engines['aggregation_engine'].get_top_spending_accounts.return_value = top_accounts
    
    allocation_result = AllocationResult(
        total_cost=Decimal('1000.00'),
        allocated_cost=Decimal('800.00'),
        unallocated_cost=Decimal('200.00'),
        allocation_percentage=80.0,
        allocations_by_category={}
    )
    mock_engines['allocation_engine'].allocate_by_tags.return_value = allocation_result
    
    # Act
    enhanced = advisor_service.enhance_prompt_with_multi_account_context(
        base_prompt=base_prompt,
        org_id=org_id,
        intent=sample_intent
    )
    
    # Assert
    assert base_prompt in enhanced
    assert "Organization Context" in enhanced
    assert org_id in enhanced
    assert "Total Accounts: 2" in enhanced
    assert "Total Cost: $1000.00" in enhanced
    assert "Production" in enhanced


def test_enhance_prompt_with_account_context(advisor_service, mock_repositories, mock_engines, sample_intent):
    """Test enhancing prompt with account context"""
    # Arrange
    account_id = '111111111111'
    base_prompt = "Analyze my AWS costs"
    
    account = Account(
        id=account_id,
        arn='arn:aws:organizations::111111111111:account/o-test/111111111111',
        name='Production',
        email='prod@example.com',
        status='ACTIVE',
        joined_method='CREATED',
        joined_timestamp=datetime.now()
    )
    mock_repositories['account_repo'].get.return_value = account
    
    cost_data = AccountCostData(
        account_id=account_id,
        start_date='2024-01-01',
        end_date='2024-01-31',
        total_cost=Decimal('500.00'),
        costs_by_service={},
        costs_by_day={},
        collection_timestamp=datetime.now(),
        status='SUCCESS'
    )
    mock_repositories['cost_repo'].get.return_value = cost_data
    
    allocation_result = AllocationResult(
        total_cost=Decimal('500.00'),
        allocated_cost=Decimal('400.00'),
        unallocated_cost=Decimal('100.00'),
        allocation_percentage=80.0,
        allocations_by_category={}
    )
    mock_engines['allocation_engine'].allocate_by_tags.return_value = allocation_result
    
    # Act
    enhanced = advisor_service.enhance_prompt_with_multi_account_context(
        base_prompt=base_prompt,
        account_id=account_id,
        intent=sample_intent
    )
    
    # Assert
    assert base_prompt in enhanced
    assert "Account Context" in enhanced
    assert "Production" in enhanced
    assert account_id in enhanced
    assert "Total Cost: $500.00" in enhanced


def test_get_cross_account_insights_high_unallocated(advisor_service, mock_repositories, mock_engines, sample_intent, sample_accounts):
    """Test generating insights for high unallocated costs"""
    # Arrange
    org_id = 'o-test123'
    mock_repositories['account_repo'].list_by_organization.return_value = sample_accounts
    
    aggregated = AggregatedCosts(
        entity_id=org_id,
        entity_type='ORGANIZATION',
        start_date='2024-01-01',
        end_date='2024-01-31',
        total_cost=Decimal('1000.00'),
        account_count=2,
        costs_by_account={},
        costs_by_service={'EC2': Decimal('1000.00')},
        costs_by_day={}
    )
    mock_engines['aggregation_engine'].aggregate_organization_costs.return_value = aggregated
    mock_engines['aggregation_engine'].get_top_spending_accounts.return_value = []
    
    # High unallocated costs (only 50% allocated)
    allocation_result = AllocationResult(
        total_cost=Decimal('1000.00'),
        allocated_cost=Decimal('500.00'),
        unallocated_cost=Decimal('500.00'),
        allocation_percentage=50.0,
        allocations_by_category={}
    )
    mock_engines['allocation_engine'].allocate_by_tags.return_value = allocation_result
    
    # Act
    insights = advisor_service.get_cross_account_insights(org_id, sample_intent)
    
    # Assert
    assert len(insights) > 0
    allocation_insight = next((i for i in insights if i['type'] == 'allocation_warning'), None)
    assert allocation_insight is not None
    assert 'unallocated' in allocation_insight['description'].lower()
    assert allocation_insight['severity'] == 'medium'


def test_get_cross_account_insights_spending_concentration(advisor_service, mock_repositories, mock_engines, sample_intent, sample_accounts):
    """Test generating insights for spending concentration"""
    # Arrange
    org_id = 'o-test123'
    mock_repositories['account_repo'].list_by_organization.return_value = sample_accounts
    
    aggregated = AggregatedCosts(
        entity_id=org_id,
        entity_type='ORGANIZATION',
        start_date='2024-01-01',
        end_date='2024-01-31',
        total_cost=Decimal('1000.00'),
        account_count=2,
        costs_by_account={},
        costs_by_service={},
        costs_by_day={}
    )
    mock_engines['aggregation_engine'].aggregate_organization_costs.return_value = aggregated
    
    # High concentration in top accounts (85%)
    top_accounts = [
        AccountSpending(
            account_id='111111111111',
            account_name='Production',
            total_cost=Decimal('850.00'),
            percentage_of_total=85.0
        )
    ]
    mock_engines['aggregation_engine'].get_top_spending_accounts.return_value = top_accounts
    
    allocation_result = AllocationResult(
        total_cost=Decimal('1000.00'),
        allocated_cost=Decimal('900.00'),
        unallocated_cost=Decimal('100.00'),
        allocation_percentage=90.0,
        allocations_by_category={}
    )
    mock_engines['allocation_engine'].allocate_by_tags.return_value = allocation_result
    
    # Act
    insights = advisor_service.get_cross_account_insights(org_id, sample_intent)
    
    # Assert
    concentration_insight = next((i for i in insights if i['type'] == 'concentration_warning'), None)
    assert concentration_insight is not None
    assert 'spending' in concentration_insight['description'].lower()
    assert 'accounts' in concentration_insight['description'].lower()


def test_get_cross_account_insights_service_concentration(advisor_service, mock_repositories, mock_engines, sample_intent, sample_accounts):
    """Test generating insights for service cost concentration"""
    # Arrange
    org_id = 'o-test123'
    mock_repositories['account_repo'].list_by_organization.return_value = sample_accounts
    
    # EC2 represents 80% of costs
    aggregated = AggregatedCosts(
        entity_id=org_id,
        entity_type='ORGANIZATION',
        start_date='2024-01-01',
        end_date='2024-01-31',
        total_cost=Decimal('1000.00'),
        account_count=2,
        costs_by_account={},
        costs_by_service={
            'EC2': Decimal('800.00'),
            'S3': Decimal('200.00')
        },
        costs_by_day={}
    )
    mock_engines['aggregation_engine'].aggregate_organization_costs.return_value = aggregated
    mock_engines['aggregation_engine'].get_top_spending_accounts.return_value = []
    
    allocation_result = AllocationResult(
        total_cost=Decimal('1000.00'),
        allocated_cost=Decimal('900.00'),
        unallocated_cost=Decimal('100.00'),
        allocation_percentage=90.0,
        allocations_by_category={}
    )
    mock_engines['allocation_engine'].allocate_by_tags.return_value = allocation_result
    
    # Act
    insights = advisor_service.get_cross_account_insights(org_id, sample_intent)
    
    # Assert
    service_insight = next((i for i in insights if i['type'] == 'service_concentration'), None)
    assert service_insight is not None
    assert 'EC2' in service_insight['title']
    assert 'EC2' in service_insight['recommendation']


def test_get_date_range_from_intent(advisor_service):
    """Test extracting date range from intent"""
    # Arrange
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 31)
    intent = QueryIntent(
        intent_type='cost_analysis',
        services=[],
        time_range=(start, end),
        accounts=[],
        entities={}
    )
    
    # Act
    start_date, end_date = advisor_service._get_date_range(intent)
    
    # Assert
    assert start_date == '2024-01-01'
    assert end_date == '2024-01-31'


def test_get_date_range_default(advisor_service):
    """Test default date range when not in intent"""
    # Arrange
    intent = QueryIntent(
        intent_type='cost_analysis',
        services=[],
        time_range=None,
        accounts=[],
        entities={}
    )
    
    # Act
    start_date, end_date = advisor_service._get_date_range(intent)
    
    # Assert
    # Should default to last 30 days
    assert start_date is not None
    assert end_date is not None
    assert len(start_date) == 10  # YYYY-MM-DD format
    assert len(end_date) == 10
