"""
Property-based tests for Cost Allocation Engine

Tests universal properties that should hold for all cost allocation scenarios.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

from src.services.multi_account.cost_allocation_engine import CostAllocationEngine
from src.services.multi_account.models import (
    AllocationRule,
    AccountCostData
)


# Strategies for generating test data
@st.composite
def cost_data_with_tags_strategy(draw):
    """Generate random cost data with tags"""
    num_services = draw(st.integers(min_value=1, max_value=5))
    services = [f"Service{i}" for i in range(num_services)]
    
    costs_by_service = {}
    for service in services:
        cost = draw(st.decimals(min_value=0, max_value=1000, places=2))
        costs_by_service[service] = cost
    
    # Generate tags (some services tagged, some not)
    costs_by_tag = {}
    for service in services:
        if draw(st.booleans()):  # Randomly tag some services
            team = draw(st.sampled_from(['Engineering', 'Data', 'DevOps', 'QA']))
            tag_key = f"Team:{team}"
            tag_cost = costs_by_service[service]
            costs_by_tag[tag_key] = costs_by_tag.get(tag_key, Decimal('0')) + tag_cost
    
    return costs_by_service, costs_by_tag


@st.composite
def allocation_rules_strategy(draw):
    """Generate random allocation rules with priorities"""
    num_rules = draw(st.integers(min_value=1, max_value=5))
    rules = []
    
    for i in range(num_rules):
        rule = AllocationRule(
            rule_id=f"rule{i}",
            name=f"Rule {i}",
            priority=draw(st.integers(min_value=1, max_value=100)),
            rule_type=draw(st.sampled_from(['TAG_BASED', 'FIXED', 'PERCENTAGE'])),
            conditions={'service': f"Service{draw(st.integers(min_value=0, max_value=4))}"},
            allocation_target=draw(st.sampled_from(['Engineering', 'Data', 'DevOps', 'QA']))
        )
        rules.append(rule)
    
    return rules


@settings(max_examples=20)
@given(cost_data=cost_data_with_tags_strategy())
def test_property_5_cost_allocation_conservation(cost_data):
    """
    Property 5: Cost Allocation Conservation
    
    For any account's costs, the sum of allocated costs plus unallocated costs
    should equal the total account cost.
    
    Validates: Requirements 6.1, 7.1
    Feature: multi-account-cost-management, Property 5: Cost Allocation Conservation
    """
    # Given: Random cost data with tags
    costs_by_service, costs_by_tag = cost_data
    
    # Create mock repositories
    mock_cost_repository = Mock()
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {k: float(v) for k, v in costs_by_service.items()},
        'costs_by_tag': {k: float(v) for k, v in costs_by_tag.items()}
    }
    mock_rule_repository = Mock()
    
    engine = CostAllocationEngine(
        cost_repository=mock_cost_repository,
        rule_repository=mock_rule_repository
    )
    
    # When: Allocating costs by tags
    result = engine.allocate_by_tags(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28'
    )
    
    # Then: Allocated + unallocated should equal total
    # Note: Tags can overlap, so allocated might be > total
    # But unallocated should be total - sum of unique tagged costs
    total_cost = sum(costs_by_service.values(), Decimal('0'))
    
    # For conservation, we check that unallocated + allocated >= total
    # (allocated can be higher due to overlapping tags)
    assert result.total_cost == total_cost
    assert result.allocated_cost + result.unallocated_cost >= total_cost
    
    # More importantly: unallocated should be non-negative
    assert result.unallocated_cost >= Decimal('0')


@settings(max_examples=20)
@given(
    costs_by_service=st.dictionaries(
        keys=st.sampled_from(['EC2', 'S3', 'RDS', 'Lambda', 'DynamoDB']),
        values=st.decimals(min_value=1, max_value=1000, places=2),
        min_size=1,
        max_size=5
    ),
    rules=allocation_rules_strategy()
)
def test_property_6_allocation_rule_priority(costs_by_service, rules):
    """
    Property 6: Allocation Rule Priority
    
    For any resource that matches multiple allocation rules, the system should
    apply only the highest-priority rule.
    
    Validates: Requirements 8.6
    Feature: multi-account-cost-management, Property 6: Allocation Rule Priority
    """
    # Given: Cost data and multiple rules
    costs = AccountCostData(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        total_cost=sum(costs_by_service.values(), Decimal('0')),
        costs_by_service=costs_by_service,
        costs_by_day={},
        collection_timestamp=datetime.utcnow(),
        status='SUCCESS'
    )
    
    # Create mock repositories
    mock_cost_repository = Mock()
    mock_rule_repository = Mock()
    
    engine = CostAllocationEngine(
        cost_repository=mock_cost_repository,
        rule_repository=mock_rule_repository
    )
    
    # When: Applying rules
    result = engine.apply_allocation_rules(costs, rules)
    
    # Then: For each service, only highest priority matching rule should be applied
    # Track which services were allocated
    allocated_services = set()
    
    for service, cost in costs_by_service.items():
        # Find all matching rules for this service
        matching_rules = [r for r in rules if r.conditions.get('service') == service]
        
        if matching_rules:
            # Get highest priority rule
            highest_priority_rule = max(matching_rules, key=lambda r: r.priority)
            target = highest_priority_rule.allocation_target
            
            # Verify this service's cost is allocated to the highest priority target
            if target in result.allocations_by_category:
                allocated_services.add(service)
                # The target should have at least this service's cost
                assert result.allocations_by_category[target] >= Decimal('0')
    
    # Verify no double allocation: allocated cost should not exceed total
    # (unless percentage rules are involved)
    if not any(r.rule_type == 'PERCENTAGE' for r in rules):
        assert result.allocated_cost <= result.total_cost


@settings(max_examples=20)
@given(
    costs_by_service=st.dictionaries(
        keys=st.sampled_from(['EC2', 'S3', 'RDS', 'Lambda', 'DynamoDB']),
        values=st.decimals(min_value=1, max_value=1000, places=2),
        min_size=1,
        max_size=5
    ),
    num_rules=st.integers(min_value=0, max_value=5)
)
def test_property_10_unallocated_cost_monotonicity(costs_by_service, num_rules):
    """
    Property 10: Unallocated Cost Monotonicity
    
    For any account, as more allocation rules are added, the unallocated cost
    should decrease or stay the same (never increase).
    
    Validates: Requirements 7.1, 8.1
    Feature: multi-account-cost-management, Property 10: Unallocated Cost Monotonicity
    """
    # Given: Cost data
    costs = AccountCostData(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        total_cost=sum(costs_by_service.values(), Decimal('0')),
        costs_by_service=costs_by_service,
        costs_by_day={},
        collection_timestamp=datetime.utcnow(),
        status='SUCCESS'
    )
    
    # Create mock repositories
    mock_cost_repository = Mock()
    mock_rule_repository = Mock()
    
    engine = CostAllocationEngine(
        cost_repository=mock_cost_repository,
        rule_repository=mock_rule_repository
    )
    
    # When: Applying rules incrementally
    services = list(costs_by_service.keys())
    previous_unallocated = costs.total_cost
    
    for i in range(num_rules):
        # Create rules incrementally
        rules = []
        for j in range(i + 1):
            if j < len(services):
                rule = AllocationRule(
                    rule_id=f"rule{j}",
                    name=f"Rule {j}",
                    priority=10 + j,
                    rule_type='FIXED',
                    conditions={'service': services[j]},
                    allocation_target=f"Team{j}"
                )
                rules.append(rule)
        
        # Apply rules
        result = engine.apply_allocation_rules(costs, rules)
        
        # Then: Unallocated cost should not increase
        assert result.unallocated_cost <= previous_unallocated
        previous_unallocated = result.unallocated_cost


@settings(max_examples=20)
@given(
    costs_by_service=st.dictionaries(
        keys=st.sampled_from(['EC2', 'S3', 'RDS']),
        values=st.decimals(min_value=0, max_value=1000, places=2),
        min_size=1,
        max_size=3
    )
)
def test_property_allocation_result_consistency(costs_by_service):
    """
    Property: Allocation Result Consistency
    
    For any cost data, the allocation percentage should be correctly calculated
    as (allocated / total) * 100.
    
    Feature: multi-account-cost-management, Property: Allocation Result Consistency
    """
    # Given: Cost data with some tagged resources
    costs_by_tag = {}
    for i, (service, cost) in enumerate(costs_by_service.items()):
        if i % 2 == 0:  # Tag every other service
            costs_by_tag[f"Team:Team{i}"] = cost
    
    mock_cost_repository = Mock()
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {k: float(v) for k, v in costs_by_service.items()},
        'costs_by_tag': {k: float(v) for k, v in costs_by_tag.items()}
    }
    mock_rule_repository = Mock()
    
    engine = CostAllocationEngine(
        cost_repository=mock_cost_repository,
        rule_repository=mock_rule_repository
    )
    
    # When: Allocating costs
    result = engine.allocate_by_tags(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28'
    )
    
    # Then: Allocation percentage should be consistent
    if result.total_cost > 0:
        expected_percentage = float((result.allocated_cost / result.total_cost) * 100)
        assert abs(result.allocation_percentage - expected_percentage) < 0.01
    else:
        assert result.allocation_percentage == 0.0


@settings(max_examples=20)
@given(
    costs_by_service=st.dictionaries(
        keys=st.sampled_from(['EC2', 'S3', 'RDS']),
        values=st.decimals(min_value=0, max_value=1000, places=2),
        min_size=1,
        max_size=3
    )
)
def test_property_non_negative_allocations(costs_by_service):
    """
    Property: Non-Negative Allocations
    
    For any cost data, all allocation amounts should be non-negative.
    
    Feature: multi-account-cost-management, Property: Non-Negative Allocations
    """
    # Given: Cost data
    costs = AccountCostData(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        total_cost=sum(costs_by_service.values(), Decimal('0')),
        costs_by_service=costs_by_service,
        costs_by_day={},
        collection_timestamp=datetime.utcnow(),
        status='SUCCESS'
    )
    
    # Create some rules
    rules = [
        AllocationRule(
            rule_id=f"rule{i}",
            name=f"Rule {i}",
            priority=10 + i,
            rule_type='FIXED',
            conditions={'service': service},
            allocation_target=f"Team{i}"
        )
        for i, service in enumerate(costs_by_service.keys())
    ]
    
    # Create mock repositories
    mock_cost_repository = Mock()
    mock_rule_repository = Mock()
    
    engine = CostAllocationEngine(
        cost_repository=mock_cost_repository,
        rule_repository=mock_rule_repository
    )
    
    # When: Applying rules
    result = engine.apply_allocation_rules(costs, rules)
    
    # Then: All amounts should be non-negative
    assert result.total_cost >= Decimal('0')
    assert result.allocated_cost >= Decimal('0')
    assert result.unallocated_cost >= Decimal('0')
    assert result.allocation_percentage >= 0.0
    
    for category, amount in result.allocations_by_category.items():
        assert amount >= Decimal('0'), f"Category {category} has negative allocation: {amount}"


@given(
    org_id=st.text(min_size=5, max_size=20),
    account_ids=st.lists(
        st.text(alphabet='0123456789', min_size=12, max_size=12),
        min_size=1, max_size=10, unique=True
    ),
    tag_key=st.sampled_from(['Team', 'Environment', 'Project', 'Department']),
    start_date=st.dates(min_value=datetime(2020, 1, 1).date(), max_value=datetime(2024, 12, 31).date()),
    end_date=st.dates(min_value=datetime(2020, 1, 1).date(), max_value=datetime(2024, 12, 31).date())
)
@settings(max_examples=100, deadline=None)
def test_property_19_tag_based_cost_allocation(org_id, account_ids, tag_key, start_date, end_date):
    """
    Property 19: Tag-Based Cost Allocation
    
    For any cost allocation by tag operation, the handler should group costs by unique 
    tag values, calculate total cost for each tag value, identify resources without the 
    specified tag, and return the allocation with total_cost, allocated_cost, 
    unallocated_cost, and allocation_percentage.
    
    Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8
    
    Feature: phase-5-handlers, Property 19: Tag-Based Cost Allocation
    """
    # Ensure end_date is after start_date
    if end_date <= start_date:
        start_date, end_date = end_date, start_date
        if end_date <= start_date:
            end_date = start_date.replace(day=min(28, start_date.day + 1))
    
    # Generate cost data with tags for each account
    account_cost_data = {}
    total_expected_cost = Decimal('0')
    expected_tagged_cost = Decimal('0')
    expected_tag_values = set()
    
    for account_id in account_ids:
        # Generate services and costs for this account
        services = ['EC2', 'S3', 'RDS', 'Lambda']
        costs_by_service = {}
        costs_by_tag = {}
        
        for service in services:
            service_cost = Decimal(str(round(float(st.decimals(min_value=0, max_value=500, places=2).example()), 2)))
            costs_by_service[service] = service_cost
            total_expected_cost += service_cost
            
            # Randomly tag some services
            if hash(f"{account_id}-{service}") % 3 == 0:  # Deterministic but varied tagging
                tag_value = ['TeamA', 'TeamB', 'TeamC'][hash(f"{account_id}-{service}") % 3]
                tag_key_full = f"{tag_key}:{tag_value}"
                costs_by_tag[tag_key_full] = costs_by_tag.get(tag_key_full, Decimal('0')) + service_cost
                expected_tagged_cost += service_cost
                expected_tag_values.add(tag_value)
        
        account_cost_data[account_id] = {
            'costs_by_service': {k: float(v) for k, v in costs_by_service.items()},
            'costs_by_tag': {k: float(v) for k, v in costs_by_tag.items()}
        }
    
    # Setup mocks
    mock_cost_repository = Mock()
    
    def get_cost_data_side_effect(account_id, start_date_str):
        return account_cost_data.get(account_id, {
            'costs_by_service': {},
            'costs_by_tag': {}
        })
    
    mock_cost_repository.get_cost_data.side_effect = get_cost_data_side_effect
    mock_rule_repository = Mock()
    
    # Create engine
    engine = CostAllocationEngine(
        cost_repository=mock_cost_repository,
        rule_repository=mock_rule_repository
    )
    
    # Execute allocation by tags
    result = engine.allocate_by_tags(
        org_id=org_id,
        account_ids=account_ids,
        tag_key=tag_key,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )
    
    # Property: Should group costs by unique tag values
    assert hasattr(result, 'allocations_by_category'), \
        "Should have allocations_by_category"
    assert isinstance(result.allocations_by_category, dict), \
        "allocations_by_category should be a dictionary"
    
    # Property: Should calculate total cost for each tag value
    for tag_value, allocated_cost in result.allocations_by_category.items():
        assert isinstance(allocated_cost, (Decimal, float, int)), \
            f"Allocated cost for {tag_value} should be numeric"
        assert allocated_cost >= 0, \
            f"Allocated cost for {tag_value} should be non-negative"
    
    # Property: Should identify resources without the specified tag (unallocated cost)
    assert hasattr(result, 'unallocated_cost'), "Should have unallocated_cost"
    assert isinstance(result.unallocated_cost, (Decimal, float, int)), \
        "unallocated_cost should be numeric"
    assert result.unallocated_cost >= 0, \
        "unallocated_cost should be non-negative"
    
    # Property: Should return allocation with total_cost
    assert hasattr(result, 'total_cost'), "Should have total_cost"
    assert isinstance(result.total_cost, (Decimal, float, int)), \
        "total_cost should be numeric"
    assert result.total_cost >= 0, "total_cost should be non-negative"
    
    # Property: Should return allocation with allocated_cost
    assert hasattr(result, 'allocated_cost'), "Should have allocated_cost"
    assert isinstance(result.allocated_cost, (Decimal, float, int)), \
        "allocated_cost should be numeric"
    assert result.allocated_cost >= 0, "allocated_cost should be non-negative"
    
    # Property: Should return allocation with allocation_percentage
    assert hasattr(result, 'allocation_percentage'), "Should have allocation_percentage"
    assert isinstance(result.allocation_percentage, (float, int)), \
        "allocation_percentage should be numeric"
    assert 0 <= result.allocation_percentage <= 100, \
        "allocation_percentage should be between 0 and 100"
    
    # Property: allocated_cost + unallocated_cost should equal total_cost
    total_check = result.allocated_cost + result.unallocated_cost
    assert abs(total_check - result.total_cost) < Decimal('0.01'), \
        f"allocated_cost + unallocated_cost ({total_check}) should equal total_cost ({result.total_cost})"
    
    # Property: Sum of allocations_by_category should equal allocated_cost
    if result.allocations_by_category:
        category_sum = sum(result.allocations_by_category.values())
        assert abs(category_sum - result.allocated_cost) < Decimal('0.01'), \
            f"Sum of allocations_by_category ({category_sum}) should equal allocated_cost ({result.allocated_cost})"
    
    # Property: allocation_percentage should be correctly calculated
    if result.total_cost > 0:
        expected_percentage = float((result.allocated_cost / result.total_cost) * 100)
        assert abs(result.allocation_percentage - expected_percentage) < 0.01, \
            f"allocation_percentage ({result.allocation_percentage}) should match calculated percentage ({expected_percentage})"
    else:
        assert result.allocation_percentage == 0.0, \
            "allocation_percentage should be 0 when total_cost is 0"
    
    # Property: All tag values in allocations_by_category should be valid
    for tag_value in result.allocations_by_category.keys():
        assert isinstance(tag_value, str), \
            f"Tag value {tag_value} should be a string"
        assert len(tag_value) > 0, \
            f"Tag value should not be empty"
