"""
Unit tests for Cost Allocation Engine
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock

from src.services.multi_account.cost_allocation_engine import CostAllocationEngine
from src.services.multi_account.models import (
    AllocationRule,
    AllocationResult,
    AccountCostData
)


@pytest.fixture
def mock_cost_repository():
    """Mock cost repository"""
    return Mock()


@pytest.fixture
def mock_rule_repository():
    """Mock rule repository"""
    return Mock()


@pytest.fixture
def engine(mock_cost_repository, mock_rule_repository):
    """Create engine instance with mocked dependencies"""
    return CostAllocationEngine(
        cost_repository=mock_cost_repository,
        rule_repository=mock_rule_repository
    )


def test_allocate_by_tags_success(engine, mock_cost_repository):
    """Test successful tag-based allocation"""
    # Given: Mock cost data with tags
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {
            'EC2': 100.00,
            'S3': 50.00,
            'RDS': 75.00
        },
        'costs_by_tag': {
            'Team:Engineering': 100.00,
            'Team:Data': 75.00,
            'Project:WebApp': 100.00,
            'Environment:Production': 150.00
        }
    }
    
    # When: Allocating by tags
    result = engine.allocate_by_tags(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28'
    )
    
    # Then: Should allocate costs correctly
    assert result.total_cost == Decimal('225.00')
    assert result.allocated_cost == Decimal('425.00')  # Tags can overlap
    assert 'Team:Engineering' in result.allocations_by_category
    assert 'Team:Data' in result.allocations_by_category
    assert 'Project:WebApp' in result.allocations_by_category


def test_allocate_by_tags_no_data(engine, mock_cost_repository):
    """Test tag-based allocation with no data"""
    # Given: No cost data
    mock_cost_repository.get_cost_data.return_value = None
    
    # When: Allocating by tags
    result = engine.allocate_by_tags(
        account_id='999999999999',
        start_date='2026-02-01',
        end_date='2026-02-28'
    )
    
    # Then: Should return empty result
    assert result.total_cost == Decimal('0')
    assert result.allocated_cost == Decimal('0')
    assert result.unallocated_cost == Decimal('0')
    assert result.allocation_percentage == 0.0


def test_allocate_by_tags_custom_keys(engine, mock_cost_repository):
    """Test tag-based allocation with custom tag keys"""
    # Given: Mock cost data with custom tags
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {
            'EC2': 100.00
        },
        'costs_by_tag': {
            'CostCenter:IT': 50.00,
            'Department:Engineering': 50.00
        }
    }
    
    # When: Allocating with custom tag keys
    result = engine.allocate_by_tags(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        tag_keys=['CostCenter', 'Department']
    )
    
    # Then: Should use custom tag keys
    assert 'CostCenter:IT' in result.allocations_by_category
    assert 'Department:Engineering' in result.allocations_by_category


def test_allocate_by_tags_unallocated(engine, mock_cost_repository):
    """Test tag-based allocation with unallocated costs"""
    # Given: Mock cost data with some untagged resources
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {
            'EC2': 100.00,
            'S3': 50.00
        },
        'costs_by_tag': {
            'Team:Engineering': 50.00  # Only partial allocation
        }
    }
    
    # When: Allocating by tags
    result = engine.allocate_by_tags(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28'
    )
    
    # Then: Should calculate unallocated costs
    assert result.total_cost == Decimal('150.00')
    assert result.allocated_cost == Decimal('50.00')
    assert result.unallocated_cost == Decimal('100.00')
    assert result.allocation_percentage == pytest.approx(33.33, rel=0.01)


def test_apply_allocation_rules_success(engine):
    """Test successful rule application"""
    # Given: Cost data and allocation rules
    costs = AccountCostData(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        total_cost=Decimal('300.00'),
        costs_by_service={
            'EC2': Decimal('100.00'),
            'S3': Decimal('50.00'),
            'RDS': Decimal('150.00')
        },
        costs_by_day={},
        collection_timestamp=datetime.utcnow(),
        status='SUCCESS'
    )
    
    rules = [
        AllocationRule(
            rule_id='rule1',
            name='EC2 to Engineering',
            priority=10,
            rule_type='FIXED',
            conditions={'service': 'EC2'},
            allocation_target='Engineering'
        ),
        AllocationRule(
            rule_id='rule2',
            name='RDS to Data',
            priority=5,
            rule_type='FIXED',
            conditions={'service': 'RDS'},
            allocation_target='Data'
        )
    ]
    
    # When: Applying rules
    result = engine.apply_allocation_rules(costs, rules)
    
    # Then: Should allocate correctly
    assert result.total_cost == Decimal('300.00')
    assert result.allocated_cost == Decimal('250.00')
    assert result.unallocated_cost == Decimal('50.00')  # S3 not allocated
    assert result.allocations_by_category['Engineering'] == Decimal('100.00')
    assert result.allocations_by_category['Data'] == Decimal('150.00')


def test_apply_allocation_rules_priority(engine):
    """Test rule priority ordering"""
    # Given: Cost data and rules with different priorities
    costs = AccountCostData(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        total_cost=Decimal('100.00'),
        costs_by_service={
            'EC2': Decimal('100.00')
        },
        costs_by_day={},
        collection_timestamp=datetime.utcnow(),
        status='SUCCESS'
    )
    
    rules = [
        AllocationRule(
            rule_id='rule1',
            name='Low priority',
            priority=1,
            rule_type='FIXED',
            conditions={'service': 'EC2'},
            allocation_target='LowPriority'
        ),
        AllocationRule(
            rule_id='rule2',
            name='High priority',
            priority=10,
            rule_type='FIXED',
            conditions={'service': 'EC2'},
            allocation_target='HighPriority'
        )
    ]
    
    # When: Applying rules
    result = engine.apply_allocation_rules(costs, rules)
    
    # Then: Should apply highest priority rule only
    assert result.allocations_by_category['HighPriority'] == Decimal('100.00')
    assert 'LowPriority' not in result.allocations_by_category


def test_apply_allocation_rules_no_match(engine):
    """Test rule application with no matching rules"""
    # Given: Cost data and non-matching rules
    costs = AccountCostData(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        total_cost=Decimal('100.00'),
        costs_by_service={
            'EC2': Decimal('100.00')
        },
        costs_by_day={},
        collection_timestamp=datetime.utcnow(),
        status='SUCCESS'
    )
    
    rules = [
        AllocationRule(
            rule_id='rule1',
            name='S3 rule',
            priority=10,
            rule_type='FIXED',
            conditions={'service': 'S3'},
            allocation_target='Storage'
        )
    ]
    
    # When: Applying rules
    result = engine.apply_allocation_rules(costs, rules)
    
    # Then: Should have all costs unallocated
    assert result.allocated_cost == Decimal('0')
    assert result.unallocated_cost == Decimal('100.00')
    assert result.allocation_percentage == 0.0


def test_calculate_unallocated_costs(engine, mock_cost_repository):
    """Test unallocated cost calculation"""
    # Given: Mock cost data with partial allocation
    mock_cost_repository.get_cost_data.return_value = {
        'costs_by_service': {
            'EC2': 100.00,
            'S3': 50.00
        },
        'costs_by_tag': {
            'Team:Engineering': 50.00
        }
    }
    
    # When: Calculating unallocated costs
    result = engine.calculate_unallocated_costs(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28'
    )
    
    # Then: Should return unallocated amount
    assert result == Decimal('100.00')


def test_get_allocation_by_team(engine, mock_cost_repository):
    """Test team allocation across multiple accounts"""
    # Given: Mock cost data for multiple accounts
    def get_cost_data_side_effect(account_id, start_date):
        if account_id == '111111111111':
            return {
                'costs_by_service': {'EC2': 100.00},
                'costs_by_tag': {'Team:Engineering': 100.00}
            }
        elif account_id == '222222222222':
            return {
                'costs_by_service': {'S3': 50.00},
                'costs_by_tag': {'Team:Engineering': 30.00, 'Team:Data': 20.00}
            }
        return None
    
    mock_cost_repository.get_cost_data.side_effect = get_cost_data_side_effect
    
    # When: Getting team allocations
    result = engine.get_allocation_by_team(
        org_id='o-123456',
        account_ids=['111111111111', '222222222222'],
        start_date='2026-02-01',
        end_date='2026-02-28'
    )
    
    # Then: Should aggregate team costs
    assert result['Engineering'] == Decimal('130.00')
    assert result['Data'] == Decimal('20.00')


def test_get_allocation_by_team_no_data(engine, mock_cost_repository):
    """Test team allocation with no data"""
    # Given: No cost data
    mock_cost_repository.get_cost_data.return_value = None
    
    # When: Getting team allocations
    result = engine.get_allocation_by_team(
        org_id='o-123456',
        account_ids=['999999999999'],
        start_date='2026-02-01',
        end_date='2026-02-28'
    )
    
    # Then: Should return empty result
    assert len(result) == 0


def test_rule_matches_tag_based(engine):
    """Test tag-based rule matching"""
    # Given: Tag-based rule and cost data
    rule = AllocationRule(
        rule_id='rule1',
        name='Team rule',
        priority=10,
        rule_type='TAG_BASED',
        conditions={'tag_key': 'Team', 'tag_value': 'Engineering'},
        allocation_target='Engineering'
    )
    
    costs = AccountCostData(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        total_cost=Decimal('100.00'),
        costs_by_service={'EC2': Decimal('100.00')},
        costs_by_day={},
        collection_timestamp=datetime.utcnow(),
        status='SUCCESS'
    )
    costs.costs_by_tag = {'Team:Engineering': Decimal('100.00')}
    
    # When: Checking if rule matches
    result = engine._rule_matches(rule, 'EC2', costs)
    
    # Then: Should match
    assert result is True


def test_rule_matches_fixed(engine):
    """Test fixed rule matching"""
    # Given: Fixed rule and cost data
    rule = AllocationRule(
        rule_id='rule1',
        name='EC2 rule',
        priority=10,
        rule_type='FIXED',
        conditions={'service': 'EC2'},
        allocation_target='Compute'
    )
    
    costs = AccountCostData(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        total_cost=Decimal('100.00'),
        costs_by_service={'EC2': Decimal('100.00')},
        costs_by_day={},
        collection_timestamp=datetime.utcnow(),
        status='SUCCESS'
    )
    
    # When: Checking if rule matches
    result = engine._rule_matches(rule, 'EC2', costs)
    
    # Then: Should match
    assert result is True


def test_rule_matches_percentage(engine):
    """Test percentage rule matching"""
    # Given: Percentage rule
    rule = AllocationRule(
        rule_id='rule1',
        name='Split rule',
        priority=10,
        rule_type='PERCENTAGE',
        conditions={'percentage': 50},
        allocation_target='Shared'
    )
    
    costs = AccountCostData(
        account_id='123456789012',
        start_date='2026-02-01',
        end_date='2026-02-28',
        total_cost=Decimal('100.00'),
        costs_by_service={'EC2': Decimal('100.00')},
        costs_by_day={},
        collection_timestamp=datetime.utcnow(),
        status='SUCCESS'
    )
    
    # When: Checking if rule matches
    result = engine._rule_matches(rule, 'EC2', costs)
    
    # Then: Should match (percentage rules match all)
    assert result is True
