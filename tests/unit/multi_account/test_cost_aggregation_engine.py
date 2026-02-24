"""
Unit tests for Cost Aggregation Engine
"""
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from src.services.multi_account.cost_aggregation_engine import CostAggregationEngine
from src.services.multi_account.models import AggregatedCosts, AccountSpending


@pytest.fixture
def mock_cost_repository():
    """Mock cost repository"""
    repo = Mock()
    return repo


@pytest.fixture
def mock_account_repository():
    """Mock account repository"""
    repo = Mock()
    return repo


@pytest.fixture
def mock_org_repository():
    """Mock organization repository"""
    repo = Mock()
    return repo


@pytest.fixture
def aggregation_engine(mock_cost_repository, mock_account_repository, mock_org_repository):
    """Create aggregation engine with mocked dependencies"""
    return CostAggregationEngine(
        cost_repository=mock_cost_repository,
        account_repository=mock_account_repository,
        org_repository=mock_org_repository,
        cache_ttl_seconds=3600
    )


def test_aggregate_organization_costs_success(aggregation_engine, mock_cost_repository):
    """Test successful organization-level cost aggregation"""
    # Given: Cost data for 3 accounts
    # Mock will be called twice per account (once for service costs, once for daily costs)
    mock_cost_repository.get_cost_data.side_effect = [
        # Account 111 - service costs
        {
            'costs_by_service': {'EC2': 100.0, 'S3': 50.0},
            'costs_by_day': {'2026-02-01': 75.0, '2026-02-02': 75.0}
        },
        # Account 111 - daily costs
        {
            'costs_by_service': {'EC2': 100.0, 'S3': 50.0},
            'costs_by_day': {'2026-02-01': 75.0, '2026-02-02': 75.0}
        },
        # Account 222 - service costs
        {
            'costs_by_service': {'EC2': 200.0, 'RDS': 100.0},
            'costs_by_day': {'2026-02-01': 150.0, '2026-02-02': 150.0}
        },
        # Account 222 - daily costs
        {
            'costs_by_service': {'EC2': 200.0, 'RDS': 100.0},
            'costs_by_day': {'2026-02-01': 150.0, '2026-02-02': 150.0}
        },
        # Account 333 - service costs
        {
            'costs_by_service': {'S3': 50.0, 'Lambda': 25.0},
            'costs_by_day': {'2026-02-01': 37.5, '2026-02-02': 37.5}
        },
        # Account 333 - daily costs
        {
            'costs_by_service': {'S3': 50.0, 'Lambda': 25.0},
            'costs_by_day': {'2026-02-01': 37.5, '2026-02-02': 37.5}
        }
    ]
    
    # When: Aggregating organization costs
    result = aggregation_engine.aggregate_organization_costs(
        org_id='o-123',
        account_ids=['111', '222', '333'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=False
    )
    
    # Then: Costs should be aggregated correctly
    assert result.entity_id == 'o-123'
    assert result.entity_type == 'ORGANIZATION'
    assert result.account_count == 3
    assert result.total_cost == Decimal('525.0')  # Sum of all service costs
    
    # Check per-account totals
    assert result.costs_by_account['111'] == Decimal('150.0')
    assert result.costs_by_account['222'] == Decimal('300.0')
    assert result.costs_by_account['333'] == Decimal('75.0')
    
    # Check per-service totals
    assert result.costs_by_service['EC2'] == Decimal('300.0')
    assert result.costs_by_service['S3'] == Decimal('100.0')
    assert result.costs_by_service['RDS'] == Decimal('100.0')
    assert result.costs_by_service['Lambda'] == Decimal('25.0')
    
    # Check daily totals
    assert result.costs_by_day['2026-02-01'] == Decimal('262.5')
    assert result.costs_by_day['2026-02-02'] == Decimal('262.5')


def test_aggregate_organization_costs_with_cache(aggregation_engine, mock_cost_repository):
    """Test that caching works for organization aggregation"""
    # Given: Cost data
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {'EC2': 100.0},
        'costs_by_day': {'2026-02-01': 100.0}
    }
    
    # When: Calling twice with cache enabled
    result1 = aggregation_engine.aggregate_organization_costs(
        org_id='o-123',
        account_ids=['111'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=True
    )
    
    result2 = aggregation_engine.aggregate_organization_costs(
        org_id='o-123',
        account_ids=['111'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=True
    )
    
    # Then: Repository should be called only for first aggregation (2 calls: service + daily)
    # Second call uses cache, so no additional calls
    assert mock_cost_repository.get_cost_data.call_count == 2
    assert result1.total_cost == result2.total_cost


def test_aggregate_ou_costs_success(aggregation_engine, mock_cost_repository):
    """Test successful OU-level cost aggregation"""
    # Given: Cost data for 2 accounts in OU
    mock_cost_repository.get_cost_data.side_effect = [
        # Account 111 - service costs
        {
            'costs_by_service': {'EC2': 100.0},
            'costs_by_day': {'2026-02-01': 100.0}
        },
        # Account 111 - daily costs
        {
            'costs_by_service': {'EC2': 100.0},
            'costs_by_day': {'2026-02-01': 100.0}
        },
        # Account 222 - service costs
        {
            'costs_by_service': {'S3': 50.0},
            'costs_by_day': {'2026-02-01': 50.0}
        },
        # Account 222 - daily costs
        {
            'costs_by_service': {'S3': 50.0},
            'costs_by_day': {'2026-02-01': 50.0}
        }
    ]
    
    # When: Aggregating OU costs
    result = aggregation_engine.aggregate_ou_costs(
        ou_id='ou-abc',
        account_ids=['111', '222'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=False
    )
    
    # Then: Costs should be aggregated correctly
    assert result.entity_id == 'ou-abc'
    assert result.entity_type == 'OU'
    assert result.account_count == 2
    assert result.total_cost == Decimal('150.0')
    assert result.costs_by_service['EC2'] == Decimal('100.0')
    assert result.costs_by_service['S3'] == Decimal('50.0')
    assert result.costs_by_day['2026-02-01'] == Decimal('150.0')


def test_aggregate_by_service(aggregation_engine, mock_cost_repository):
    """Test service-level aggregation across accounts"""
    # Given: Cost data with multiple services
    mock_cost_repository.get_cost_data.side_effect = [
        {
            'costs_by_service': {'EC2': 100.0, 'S3': 50.0},
            'costs_by_day': {'2026-02-01': 150.0}
        },
        {
            'costs_by_service': {'EC2': 200.0, 'RDS': 75.0},
            'costs_by_day': {'2026-02-01': 275.0}
        }
    ]
    
    # When: Aggregating by service
    result = aggregation_engine.aggregate_by_service(
        account_ids=['111', '222'],
        start_date='2026-02-01',
        end_date='2026-02-02'
    )
    
    # Then: Services should be aggregated correctly
    assert result['EC2'] == Decimal('300.0')
    assert result['S3'] == Decimal('50.0')
    assert result['RDS'] == Decimal('75.0')
    # Daily costs should not be included
    assert 'day:2026-02-01' not in result


def test_get_top_spending_accounts(aggregation_engine, mock_cost_repository, mock_account_repository):
    """Test getting top spending accounts"""
    # Given: Cost data for 5 accounts
    mock_cost_repository.get_cost_data.side_effect = [
        {'costs_by_service': {'EC2': 500.0}},  # Account 111
        {'costs_by_service': {'EC2': 300.0}},  # Account 222
        {'costs_by_service': {'EC2': 400.0}},  # Account 333
        {'costs_by_service': {'EC2': 200.0}},  # Account 444
        {'costs_by_service': {'EC2': 100.0}},  # Account 555
    ]
    
    mock_account_repository.get_account.side_effect = [
        {'name': 'Account-A'},
        {'name': 'Account-B'},
        {'name': 'Account-C'},
    ]
    
    # When: Getting top 3 spending accounts
    result = aggregation_engine.get_top_spending_accounts(
        org_id='o-123',
        account_ids=['111', '222', '333', '444', '555'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        limit=3
    )
    
    # Then: Should return top 3 accounts sorted by cost
    assert len(result) == 3
    assert result[0].account_id == '111'
    assert result[0].total_cost == Decimal('500.0')
    assert result[0].percentage_of_total == pytest.approx(33.33, rel=0.01)
    
    assert result[1].account_id == '333'
    assert result[1].total_cost == Decimal('400.0')
    
    assert result[2].account_id == '222'
    assert result[2].total_cost == Decimal('300.0')


def test_aggregate_with_missing_account_data(aggregation_engine, mock_cost_repository):
    """Test aggregation handles missing account data gracefully"""
    # Given: One account has no data
    mock_cost_repository.get_cost_data.side_effect = [
        {'costs_by_service': {'EC2': 100.0}},
        None,  # Missing data
        {'costs_by_service': {'S3': 50.0}}
    ]
    
    # When: Aggregating costs
    result = aggregation_engine.aggregate_organization_costs(
        org_id='o-123',
        account_ids=['111', '222', '333'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=False
    )
    
    # Then: Should aggregate available data only
    assert result.total_cost == Decimal('150.0')
    assert len(result.costs_by_account) == 2


def test_cache_expiration(aggregation_engine, mock_cost_repository):
    """Test that cache expires after TTL"""
    # Given: Short cache TTL
    aggregation_engine.cache_ttl_seconds = 0  # Expire immediately
    
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {'EC2': 100.0}
    }
    
    # When: Calling twice with expired cache
    result1 = aggregation_engine.aggregate_organization_costs(
        org_id='o-123',
        account_ids=['111'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=True
    )
    
    result2 = aggregation_engine.aggregate_organization_costs(
        org_id='o-123',
        account_ids=['111'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=True
    )
    
    # Then: Repository should be called twice (2 calls per aggregation: service + daily)
    assert mock_cost_repository.get_cost_data.call_count == 4


def test_clear_cache(aggregation_engine, mock_cost_repository):
    """Test clearing the cache"""
    # Given: Cached data
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {'EC2': 100.0}
    }
    
    aggregation_engine.aggregate_organization_costs(
        org_id='o-123',
        account_ids=['111'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=True
    )
    
    # When: Clearing cache
    aggregation_engine.clear_cache()
    
    # Then: Next call should hit repository again
    aggregation_engine.aggregate_organization_costs(
        org_id='o-123',
        account_ids=['111'],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=True
    )
    
    assert mock_cost_repository.get_cost_data.call_count == 4  # 2 calls per aggregation


def test_aggregate_empty_account_list(aggregation_engine):
    """Test aggregation with empty account list"""
    # When: Aggregating with no accounts
    result = aggregation_engine.aggregate_organization_costs(
        org_id='o-123',
        account_ids=[],
        start_date='2026-02-01',
        end_date='2026-02-02',
        use_cache=False
    )
    
    # Then: Should return empty aggregation
    assert result.total_cost == Decimal('0')
    assert result.account_count == 0
    assert len(result.costs_by_account) == 0
