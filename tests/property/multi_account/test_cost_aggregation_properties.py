"""
Property-based tests for Cost Aggregation Engine

Tests universal properties that should hold for all valid inputs.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

from src.services.multi_account.cost_aggregation_engine import CostAggregationEngine


# Strategy for generating account IDs (12-digit strings)
account_id_strategy = st.text(
    alphabet='0123456789',
    min_size=12,
    max_size=12
)

# Strategy for generating positive decimal costs
cost_strategy = st.decimals(
    min_value=0,
    max_value=10000,
    places=2,
    allow_nan=False,
    allow_infinity=False
)


@given(
    account_ids=st.lists(account_id_strategy, min_size=1, max_size=10, unique=True),
    costs=st.lists(cost_strategy, min_size=1, max_size=10)
)
@settings(max_examples=20)
def test_property_4_cost_aggregation_consistency(account_ids, costs):
    """
    Property 4: Cost Aggregation Consistency
    
    For any set of accounts, the sum of per-account costs should equal
    the aggregated organization cost for the same time period.
    
    Validates: Requirements 4.1
    """
    # Ensure we have matching number of accounts and costs
    if len(costs) < len(account_ids):
        costs = costs + [Decimal('0')] * (len(account_ids) - len(costs))
    costs = costs[:len(account_ids)]
    
    # Given: Mock repository with cost data
    mock_cost_repo = Mock()
    mock_account_repo = Mock()
    mock_org_repo = Mock()
    
    # Create cost data for each account - return data even for zero costs
    def get_cost_data_side_effect(account_id, start_date):
        # Find the cost for this account
        try:
            idx = account_ids.index(account_id)
            cost = costs[idx]
        except (ValueError, IndexError):
            cost = Decimal('0')
        
        return {
            'costs_by_service': {'EC2': float(cost)},
            'costs_by_day': {}
        }
    
    mock_cost_repo.get_cost_data.side_effect = get_cost_data_side_effect
    
    engine = CostAggregationEngine(
        cost_repository=mock_cost_repo,
        account_repository=mock_account_repo,
        org_repository=mock_org_repo
    )
    
    # When: Aggregating organization costs
    result = engine.aggregate_organization_costs(
        org_id='o-test',
        account_ids=account_ids,
        start_date='2026-02-01',
        end_date='2026-02-28',
        use_cache=False
    )
    
    # Then: Sum of per-account costs should equal aggregated total
    expected_total = sum(costs)
    actual_total = result.total_cost
    
    # Allow small floating point differences
    assert abs(actual_total - expected_total) < Decimal('0.01'), \
        f"Aggregated total {actual_total} != sum of accounts {expected_total}"
    
    # Verify sum of costs_by_account equals total
    account_sum = sum(result.costs_by_account.values())
    assert abs(account_sum - expected_total) < Decimal('0.01'), \
        f"Sum of costs_by_account {account_sum} != expected {expected_total}"


@given(
    account_ids=st.lists(account_id_strategy, min_size=1, max_size=5, unique=True),
    service_costs=st.lists(
        st.dictionaries(
            keys=st.sampled_from(['EC2', 'S3', 'RDS', 'Lambda', 'DynamoDB']),
            values=cost_strategy,
            min_size=1,
            max_size=3
        ),
        min_size=1,
        max_size=5
    )
)
@settings(max_examples=20)
def test_property_service_aggregation_consistency(account_ids, service_costs):
    """
    Property: Service Aggregation Consistency
    
    For any set of accounts, the sum of service costs across all accounts
    should equal the total aggregated cost.
    
    Validates: Requirements 4.3
    """
    # Ensure matching sizes
    if len(service_costs) < len(account_ids):
        service_costs = service_costs + [{}] * (len(account_ids) - len(service_costs))
    service_costs = service_costs[:len(account_ids)]
    
    # Given: Mock repository with service cost data
    mock_cost_repo = Mock()
    mock_account_repo = Mock()
    mock_org_repo = Mock()
    
    cost_data_list = []
    expected_total = Decimal('0')
    
    for services in service_costs:
        # Convert to float for mock
        services_float = {k: float(v) for k, v in services.items()}
        cost_data_list.append({
            'costs_by_service': services_float,
            'costs_by_day': {}
        })
        expected_total += sum(services.values(), Decimal('0'))
    
    mock_cost_repo.get_cost_data.side_effect = cost_data_list
    
    engine = CostAggregationEngine(
        cost_repository=mock_cost_repo,
        account_repository=mock_account_repo,
        org_repository=mock_org_repo
    )
    
    # When: Aggregating by service
    service_totals = engine.aggregate_by_service(
        account_ids=account_ids,
        start_date='2026-02-01',
        end_date='2026-02-28'
    )
    
    # Then: Sum of service costs should equal expected total
    actual_total = sum(service_totals.values(), Decimal('0'))
    
    assert abs(actual_total - expected_total) < Decimal('0.01'), \
        f"Service aggregation {actual_total} != expected {expected_total}"


@given(
    org_id=st.text(min_size=5, max_size=20),
    account_ids=st.lists(account_id_strategy, min_size=1, max_size=10, unique=True),
    costs=st.lists(cost_strategy, min_size=1, max_size=10)
)
@settings(max_examples=20)
def test_property_9_cache_consistency(org_id, account_ids, costs):
    """
    Property 9: Cache Consistency
    
    For any aggregation query, calling twice within TTL should return
    identical results without calling the repository again.
    
    Validates: Requirements 1.5, 4.5
    """
    # Ensure matching sizes
    if len(costs) < len(account_ids):
        costs = costs + [Decimal('0')] * (len(account_ids) - len(costs))
    costs = costs[:len(account_ids)]
    
    # Given: Mock repository
    mock_cost_repo = Mock()
    mock_account_repo = Mock()
    mock_org_repo = Mock()
    
    # Use side_effect function to handle any account_id
    def get_cost_data_side_effect(account_id, start_date):
        try:
            idx = account_ids.index(account_id)
            cost = costs[idx]
        except (ValueError, IndexError):
            cost = Decimal('0')
        
        return {
            'costs_by_service': {'EC2': float(cost)},
            'costs_by_day': {}
        }
    
    mock_cost_repo.get_cost_data.side_effect = get_cost_data_side_effect
    
    engine = CostAggregationEngine(
        cost_repository=mock_cost_repo,
        account_repository=mock_account_repo,
        org_repository=mock_org_repo,
        cache_ttl_seconds=3600
    )
    
    # When: Calling aggregation twice with cache enabled
    result1 = engine.aggregate_organization_costs(
        org_id=org_id,
        account_ids=account_ids,
        start_date='2026-02-01',
        end_date='2026-02-28',
        use_cache=True
    )
    
    # Reset call count after first aggregation
    first_call_count = mock_cost_repo.get_cost_data.call_count
    mock_cost_repo.get_cost_data.reset_mock(side_effect=True)
    mock_cost_repo.get_cost_data.side_effect = get_cost_data_side_effect
    
    result2 = engine.aggregate_organization_costs(
        org_id=org_id,
        account_ids=account_ids,
        start_date='2026-02-01',
        end_date='2026-02-28',
        use_cache=True
    )
    
    # Then: Results should be identical
    assert result1.total_cost == result2.total_cost, \
        "Cached results should be identical"
    assert result1.costs_by_account == result2.costs_by_account, \
        "Cached account costs should be identical"
    assert result1.costs_by_service == result2.costs_by_service, \
        "Cached service costs should be identical"
    
    # And: Repository should NOT be called for second aggregation (cache hit)
    assert mock_cost_repo.get_cost_data.call_count == 0, \
        f"Repository should not be called for cached aggregation, but was called {mock_cost_repo.get_cost_data.call_count} times"


@given(
    account_ids=st.lists(account_id_strategy, min_size=2, max_size=10, unique=True),
    costs=st.lists(cost_strategy, min_size=2, max_size=10)
)
@settings(max_examples=20)
def test_property_top_accounts_ordering(account_ids, costs):
    """
    Property: Top Accounts Ordering
    
    For any set of accounts, the top spending accounts should be
    ordered by cost in descending order.
    
    Validates: Requirements 5.5
    """
    # Ensure matching sizes
    if len(costs) < len(account_ids):
        costs = costs + [Decimal('0')] * (len(account_ids) - len(costs))
    costs = costs[:len(account_ids)]
    
    # Given: Mock repository
    mock_cost_repo = Mock()
    mock_account_repo = Mock()
    mock_org_repo = Mock()
    
    cost_data_list = []
    for cost in costs:
        cost_data_list.append({
            'costs_by_service': {'EC2': float(cost)},
            'costs_by_day': {}
        })
    
    mock_cost_repo.get_cost_data.side_effect = cost_data_list
    mock_account_repo.get_account.return_value = {'name': 'Test Account'}
    
    engine = CostAggregationEngine(
        cost_repository=mock_cost_repo,
        account_repository=mock_account_repo,
        org_repository=mock_org_repo
    )
    
    # When: Getting top spending accounts
    limit = min(5, len(account_ids))
    result = engine.get_top_spending_accounts(
        org_id='o-test',
        account_ids=account_ids,
        start_date='2026-02-01',
        end_date='2026-02-28',
        limit=limit
    )
    
    # Then: Results should be ordered by cost (descending)
    for i in range(len(result) - 1):
        assert result[i].total_cost >= result[i + 1].total_cost, \
            f"Top accounts not ordered: {result[i].total_cost} < {result[i + 1].total_cost}"
    
    # And: Should return at most 'limit' accounts
    assert len(result) <= limit, \
        f"Returned {len(result)} accounts, expected at most {limit}"


@given(
    account_ids=st.lists(account_id_strategy, min_size=1, max_size=10, unique=True),
    costs=st.lists(cost_strategy, min_size=1, max_size=10)
)
@settings(max_examples=20)
def test_property_non_negative_costs(account_ids, costs):
    """
    Property: Non-Negative Costs
    
    For any aggregation, all cost values should be non-negative.
    
    Validates: General correctness
    """
    # Ensure matching sizes
    if len(costs) < len(account_ids):
        costs = costs + [Decimal('0')] * (len(account_ids) - len(costs))
    costs = costs[:len(account_ids)]
    
    # Given: Mock repository
    mock_cost_repo = Mock()
    mock_account_repo = Mock()
    mock_org_repo = Mock()
    
    cost_data_list = []
    for cost in costs:
        cost_data_list.append({
            'costs_by_service': {'EC2': float(cost)},
            'costs_by_day': {}
        })
    
    mock_cost_repo.get_cost_data.side_effect = cost_data_list
    
    engine = CostAggregationEngine(
        cost_repository=mock_cost_repo,
        account_repository=mock_account_repo,
        org_repository=mock_org_repo
    )
    
    # When: Aggregating costs
    result = engine.aggregate_organization_costs(
        org_id='o-test',
        account_ids=account_ids,
        start_date='2026-02-01',
        end_date='2026-02-28',
        use_cache=False
    )
    
    # Then: All costs should be non-negative
    assert result.total_cost >= 0, "Total cost should be non-negative"
    
    for account_id, cost in result.costs_by_account.items():
        assert cost >= 0, f"Account {account_id} has negative cost: {cost}"
    
    for service, cost in result.costs_by_service.items():
        assert cost >= 0, f"Service {service} has negative cost: {cost}"
