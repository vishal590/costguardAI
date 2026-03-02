"""
Property-Based Tests for AllocationRulesEngine

Tests universal properties of allocation rule validation and management.
"""
import pytest
from hypothesis import given, settings, strategies as st
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from src.services.multi_account.allocation_rules_engine import AllocationRulesEngine
from src.services.multi_account.models import AllocationRule
from src.services.multi_account.repositories import AllocationRuleRepository


# Test data generators
@st.composite
def valid_tag_based_conditions(draw):
    """Generate valid TAG_BASED rule conditions"""
    return {
        'tag_key': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        'tag_value': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    }


@st.composite
def valid_percentage_conditions(draw):
    """Generate valid PERCENTAGE rule conditions"""
    return {
        'percentage': draw(st.floats(min_value=0.01, max_value=100.0))
    }


@st.composite
def valid_fixed_conditions(draw):
    """Generate valid FIXED rule conditions"""
    choice = draw(st.sampled_from(['service', 'account_id', 'both']))
    conditions = {}
    
    if choice in ['service', 'both']:
        conditions['service'] = draw(st.sampled_from(['EC2', 'S3', 'Lambda', 'DynamoDB', 'RDS']))
    
    if choice in ['account_id', 'both']:
        conditions['account_id'] = draw(st.text(min_size=12, max_size=12, alphabet=st.characters(whitelist_categories=('Nd',))))
    
    return conditions


@st.composite
def invalid_tag_based_conditions(draw):
    """Generate invalid TAG_BASED rule conditions"""
    choice = draw(st.sampled_from(['missing_tag_key', 'missing_tag_value', 'invalid_type_key', 'invalid_type_value', 'empty']))
    
    if choice == 'missing_tag_key':
        return {'tag_value': 'value'}
    elif choice == 'missing_tag_value':
        return {'tag_key': 'key'}
    elif choice == 'invalid_type_key':
        return {'tag_key': 123, 'tag_value': 'value'}
    elif choice == 'invalid_type_value':
        return {'tag_key': 'key', 'tag_value': 123}
    else:
        return {}


@st.composite
def invalid_percentage_conditions(draw):
    """Generate invalid PERCENTAGE rule conditions"""
    choice = draw(st.sampled_from(['missing', 'negative', 'zero', 'over_100', 'invalid_type']))
    
    if choice == 'missing':
        return {}
    elif choice == 'negative':
        return {'percentage': draw(st.floats(max_value=-0.01))}
    elif choice == 'zero':
        return {'percentage': 0}
    elif choice == 'over_100':
        return {'percentage': draw(st.floats(min_value=100.01, max_value=1000.0))}
    else:
        return {'percentage': 'invalid'}


@st.composite
def invalid_fixed_conditions(draw):
    """Generate invalid FIXED rule conditions (missing both service and account_id)"""
    return {}


# Property 21: Allocation Rule Validation
@given(
    rule_name=st.text(min_size=1, max_size=100),
    rule_type=st.sampled_from(['TAG_BASED', 'PERCENTAGE', 'FIXED']),
    allocation_target=st.text(min_size=1, max_size=100)
)
@settings(max_examples=100, deadline=None)
def test_property_21_allocation_rule_validation_valid_rules(rule_name, rule_type, allocation_target):
    """
    Property 21: Allocation Rule Validation
    
    For any allocation rule creation request with valid parameters,
    the rule should be created successfully with all required fields.
    
    Feature: phase-5-handlers, Property 21: Allocation Rule Validation
    
    Validates: Requirements 10.1, 10.2, 10.3, 10.4
    """
    # Mock repository
    mock_repo = Mock(spec=AllocationRuleRepository)
    mock_repo.save_rule = MagicMock()
    
    engine = AllocationRulesEngine(rule_repository=mock_repo)
    
    # Generate valid conditions based on rule type
    if rule_type == 'TAG_BASED':
        conditions = {
            'tag_key': 'Team',
            'tag_value': 'Engineering'
        }
    elif rule_type == 'PERCENTAGE':
        conditions = {
            'percentage': 50.0
        }
    else:  # FIXED
        conditions = {
            'service': 'EC2'
        }
    
    # Create rule
    org_id = 'o-1234567890'
    priority = 100
    
    rule = engine.create_rule(
        org_id=org_id,
        name=rule_name,
        priority=priority,
        rule_type=rule_type,
        conditions=conditions,
        allocation_target=allocation_target
    )
    
    # Verify rule was created with all required fields
    assert rule.rule_id is not None
    assert rule.name == rule_name
    assert rule.priority == priority
    assert rule.rule_type == rule_type
    assert rule.conditions == conditions
    assert rule.allocation_target == allocation_target
    
    # Verify repository was called
    mock_repo.save_rule.assert_called_once()


@given(
    rule_name=st.text(min_size=1, max_size=100),
    rule_type=st.sampled_from(['INVALID', 'tag_based', 'percentage', 'fixed', '', 'OTHER']),
    allocation_target=st.text(min_size=1, max_size=100)
)
@settings(max_examples=100, deadline=None)
def test_property_21_allocation_rule_validation_invalid_rule_type(rule_name, rule_type, allocation_target):
    """
    Property 21: Allocation Rule Validation - Invalid Rule Type
    
    For any allocation rule creation request with invalid rule_type,
    the handler should raise ValueError.
    
    Feature: phase-5-handlers, Property 21: Allocation Rule Validation
    
    Validates: Requirements 10.2
    """
    # Mock repository
    mock_repo = Mock(spec=AllocationRuleRepository)
    engine = AllocationRulesEngine(rule_repository=mock_repo)
    
    org_id = 'o-1234567890'
    priority = 100
    conditions = {'tag_key': 'Team', 'tag_value': 'Engineering'}
    
    # Attempt to create rule with invalid type
    with pytest.raises(ValueError) as exc_info:
        engine.create_rule(
            org_id=org_id,
            name=rule_name,
            priority=priority,
            rule_type=rule_type,
            conditions=conditions,
            allocation_target=allocation_target
        )
    
    # Verify error message mentions invalid rule_type
    assert 'rule_type' in str(exc_info.value).lower()


@given(
    rule_name=st.text(min_size=1, max_size=100),
    conditions=invalid_tag_based_conditions()
)
@settings(max_examples=100, deadline=None)
def test_property_21_allocation_rule_validation_invalid_tag_based_conditions(rule_name, conditions):
    """
    Property 21: Allocation Rule Validation - Invalid TAG_BASED Conditions
    
    For any TAG_BASED allocation rule with invalid conditions,
    the handler should raise ValueError.
    
    Feature: phase-5-handlers, Property 21: Allocation Rule Validation
    
    Validates: Requirements 10.3
    """
    # Mock repository
    mock_repo = Mock(spec=AllocationRuleRepository)
    engine = AllocationRulesEngine(rule_repository=mock_repo)
    
    org_id = 'o-1234567890'
    priority = 100
    allocation_target = 'Engineering'
    
    # Attempt to create rule with invalid conditions
    with pytest.raises(ValueError):
        engine.create_rule(
            org_id=org_id,
            name=rule_name,
            priority=priority,
            rule_type='TAG_BASED',
            conditions=conditions,
            allocation_target=allocation_target
        )


@given(
    rule_name=st.text(min_size=1, max_size=100),
    conditions=invalid_percentage_conditions()
)
@settings(max_examples=100, deadline=None)
def test_property_21_allocation_rule_validation_invalid_percentage_conditions(rule_name, conditions):
    """
    Property 21: Allocation Rule Validation - Invalid PERCENTAGE Conditions
    
    For any PERCENTAGE allocation rule with invalid conditions,
    the handler should raise ValueError.
    
    Feature: phase-5-handlers, Property 21: Allocation Rule Validation
    
    Validates: Requirements 10.3
    """
    # Mock repository
    mock_repo = Mock(spec=AllocationRuleRepository)
    engine = AllocationRulesEngine(rule_repository=mock_repo)
    
    org_id = 'o-1234567890'
    priority = 100
    allocation_target = 'Engineering'
    
    # Attempt to create rule with invalid conditions
    with pytest.raises((ValueError, TypeError)):
        engine.create_rule(
            org_id=org_id,
            name=rule_name,
            priority=priority,
            rule_type='PERCENTAGE',
            conditions=conditions,
            allocation_target=allocation_target
        )


@given(
    rule_name=st.text(min_size=1, max_size=100),
    conditions=invalid_fixed_conditions()
)
@settings(max_examples=100, deadline=None)
def test_property_21_allocation_rule_validation_invalid_fixed_conditions(rule_name, conditions):
    """
    Property 21: Allocation Rule Validation - Invalid FIXED Conditions
    
    For any FIXED allocation rule with invalid conditions (missing both service and account_id),
    the handler should raise ValueError.
    
    Feature: phase-5-handlers, Property 21: Allocation Rule Validation
    
    Validates: Requirements 10.3
    """
    # Mock repository
    mock_repo = Mock(spec=AllocationRuleRepository)
    engine = AllocationRulesEngine(rule_repository=mock_repo)
    
    org_id = 'o-1234567890'
    priority = 100
    allocation_target = 'Engineering'
    
    # Attempt to create rule with invalid conditions
    with pytest.raises(ValueError):
        engine.create_rule(
            org_id=org_id,
            name=rule_name,
            priority=priority,
            rule_type='FIXED',
            conditions=conditions,
            allocation_target=allocation_target
        )


@given(
    rule_name=st.text(min_size=1, max_size=100),
    allocation_target=st.one_of(st.just(''), st.just(None), st.integers(), st.lists(st.text()))
)
@settings(max_examples=100, deadline=None)
def test_property_21_allocation_rule_validation_invalid_allocation_target(rule_name, allocation_target):
    """
    Property 21: Allocation Rule Validation - Invalid Allocation Target
    
    For any allocation rule with invalid allocation_target (empty or non-string),
    the handler should raise ValueError.
    
    Feature: phase-5-handlers, Property 21: Allocation Rule Validation
    
    Validates: Requirements 10.4
    """
    # Mock repository
    mock_repo = Mock(spec=AllocationRuleRepository)
    engine = AllocationRulesEngine(rule_repository=mock_repo)
    
    org_id = 'o-1234567890'
    priority = 100
    conditions = {'tag_key': 'Team', 'tag_value': 'Engineering'}
    
    # Attempt to create rule with invalid allocation_target
    with pytest.raises((ValueError, AttributeError, TypeError)):
        engine.create_rule(
            org_id=org_id,
            name=rule_name,
            priority=priority,
            rule_type='TAG_BASED',
            conditions=conditions,
            allocation_target=allocation_target
        )


@given(
    rule_count=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=50, deadline=None)
def test_property_21_allocation_rule_priority_ordering(rule_count):
    """
    Property 21: Allocation Rule Validation - Priority Ordering
    
    For any list of allocation rules, when retrieved by organization,
    the rules should be sorted by priority (highest first).
    
    Feature: phase-5-handlers, Property 21: Allocation Rule Validation
    
    Validates: Requirements 10.5
    """
    # Create mock rules with random priorities
    import random
    mock_rules = []
    for i in range(rule_count):
        rule = AllocationRule(
            rule_id=f'rule-{i}',
            name=f'Rule {i}',
            priority=random.randint(1, 1000),
            rule_type='TAG_BASED',
            conditions={'tag_key': 'Team', 'tag_value': f'Team{i}'},
            allocation_target=f'Target{i}'
        )
        mock_rules.append(rule)
    
    # Mock repository
    mock_repo = Mock(spec=AllocationRuleRepository)
    mock_repo.list_by_organization = MagicMock(return_value=mock_rules)
    
    engine = AllocationRulesEngine(rule_repository=mock_repo)
    
    # Get rules for organization
    org_id = 'o-1234567890'
    sorted_rules = engine.get_rules_for_organization(org_id)
    
    # Verify rules are sorted by priority (highest first)
    priorities = [rule.priority for rule in sorted_rules]
    assert priorities == sorted(priorities, reverse=True)
