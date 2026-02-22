"""
Property-based tests for SafetyGuard.

Tests universal properties that should hold for all safety checks.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from src.services.safety_guard import SafetyGuard
from src.utils.types import Resource, SafetyConfig, SafetyCheck


# Feature: automated-cost-prevention, Property 2: Protected Resource Safety
# Resources with protected tags must never be approved for actions


@settings(max_examples=100)
@given(
    resource_id=st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-')),
    environment=st.sampled_from(['production', 'staging', 'dev', 'test'])
)
def test_property_protected_tag_environment_production(resource_id, environment):
    """
    Property 2: Protected Resource Safety (Environment=production)
    
    For any resource with Environment=production tag:
    - Safety check must return is_safe=False
    - Blocked reason must indicate protected tag
    - No action should be approved
    
    Validates: Requirements 4.1
    """
    config = SafetyConfig(
        protected_tags=["Environment=production"],
        whitelist_ids=[],
        minimum_idle_minutes={},
        dry_run_mode=False
    )
    guard = SafetyGuard(config)
    
    resource = Resource(
        resource_id=resource_id,
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags={'Environment': environment},
        state='running',
        creation_date='2024-01-01T12:00:00'
    )
    
    result = guard.is_action_safe(resource, 'stop')
    
    # If environment is production, must be blocked
    if environment == 'production':
        assert result.is_safe is False
        assert 'protected tag' in result.blocked_reason.lower()
    else:
        # Other environments should pass tag check
        # (may fail other checks, but not tag check)
        assert guard.check_tags(resource) is True


@settings(max_examples=100)
@given(
    resource_id=st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-')),
    costguard_value=st.sampled_from(['protected', 'exclude', 'allow', 'monitor'])
)
def test_property_protected_tag_costguard(resource_id, costguard_value):
    """
    Property 2: Protected Resource Safety (CostGuard tags)
    
    For any resource with CostGuard=protected or CostGuard=exclude:
    - Safety check must return is_safe=False
    - Resources must be blocked from actions
    
    Validates: Requirements 4.2, 4.3
    """
    config = SafetyConfig(
        protected_tags=["CostGuard=protected", "CostGuard=exclude"],
        whitelist_ids=[],
        minimum_idle_minutes={},
        dry_run_mode=False
    )
    guard = SafetyGuard(config)
    
    resource = Resource(
        resource_id=resource_id,
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags={'CostGuard': costguard_value},
        state='stopped',
        creation_date='2024-01-01T12:00:00'
    )
    
    result = guard.is_action_safe(resource, 'terminate')
    
    # If CostGuard is protected or exclude, must be blocked
    if costguard_value in ['protected', 'exclude']:
        assert result.is_safe is False
        assert 'protected tag' in result.blocked_reason.lower()
    else:
        # Other values should pass tag check
        assert guard.check_tags(resource) is True


@settings(max_examples=100)
@given(
    whitelist_size=st.integers(min_value=0, max_value=100),
    resource_index=st.integers(min_value=0, max_value=150)
)
def test_property_whitelist_protection(whitelist_size, resource_index):
    """
    Property 2: Protected Resource Safety (Whitelist)
    
    For any resource in whitelist:
    - Safety check must return is_safe=False
    - Blocked reason must indicate whitelist
    
    Validates: Requirements 4.4
    """
    # Create whitelist
    whitelist_ids = [f'resource-{i}' for i in range(whitelist_size)]
    
    config = SafetyConfig(
        protected_tags=[],
        whitelist_ids=whitelist_ids,
        minimum_idle_minutes={},
        dry_run_mode=False
    )
    guard = SafetyGuard(config)
    
    resource_id = f'resource-{resource_index}'
    resource = Resource(
        resource_id=resource_id,
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags={},
        state='stopped',
        creation_date='2024-01-01T12:00:00'
    )
    
    result = guard.is_action_safe(resource, 'stop')
    
    # If resource is in whitelist, must be blocked
    if resource_id in whitelist_ids:
        assert result.is_safe is False
        assert 'whitelist' in result.blocked_reason.lower()
    else:
        # Not in whitelist, should pass whitelist check
        assert guard.check_whitelist(resource) is True


# Feature: automated-cost-prevention, Property 8: Safety Check Ordering
# Safety checks must be performed in correct order and stop on first failure


@settings(max_examples=100)
@given(
    has_protected_tag=st.booleans(),
    in_whitelist=st.booleans()
)
def test_property_safety_check_ordering(has_protected_tag, in_whitelist):
    """
    Property 8: Safety Check Ordering
    
    For any resource:
    - Checks must be performed in order: tags, whitelist, active_usage, idle_duration
    - Checks must stop on first failure
    - All passing checks must be recorded
    
    Validates: Requirements 4.1-4.7
    """
    whitelist_ids = ['whitelist-resource'] if in_whitelist else []
    
    config = SafetyConfig(
        protected_tags=["Environment=production"],
        whitelist_ids=whitelist_ids,
        minimum_idle_minutes={},
        dry_run_mode=False
    )
    guard = SafetyGuard(config)
    
    resource_id = 'whitelist-resource' if in_whitelist else 'normal-resource'
    tags = {'Environment': 'production'} if has_protected_tag else {}
    
    resource = Resource(
        resource_id=resource_id,
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags=tags,
        state='stopped',
        creation_date='2024-01-01T12:00:00'
    )
    
    result = guard.is_action_safe(resource, 'stop')
    
    # Verify check ordering
    if has_protected_tag:
        # Should fail at tag check
        assert result.is_safe is False
        assert result.checks_performed == ['tag_check']
    elif in_whitelist:
        # Should fail at whitelist check
        assert result.is_safe is False
        assert result.checks_performed == ['tag_check', 'whitelist_check']
    else:
        # Should pass all checks
        assert result.is_safe is True
        expected_checks = ['tag_check', 'whitelist_check', 'active_usage_check', 'idle_duration_check']
        assert result.checks_performed == expected_checks


@settings(max_examples=100)
@given(
    dry_run=st.booleans()
)
def test_property_dry_run_blocks_all_actions(dry_run):
    """
    Property: Dry run mode blocks all actions.
    
    For any resource when dry_run_mode=True:
    - Safety check must return is_safe=False
    - Blocked reason must indicate dry run
    
    Validates: Requirements 6.1, 6.2
    """
    config = SafetyConfig(
        protected_tags=[],
        whitelist_ids=[],
        minimum_idle_minutes={},
        dry_run_mode=dry_run
    )
    guard = SafetyGuard(config)
    
    resource = Resource(
        resource_id='test-resource',
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags={},
        state='stopped',
        creation_date='2024-01-01T12:00:00'
    )
    
    result = guard.is_action_safe(resource, 'stop')
    
    if dry_run:
        assert result.is_safe is False
        assert 'dry run' in result.blocked_reason.lower()
    else:
        assert result.is_safe is True


@settings(max_examples=100)
@given(
    state=st.sampled_from(['running', 'stopped', 'terminating', 'terminated', 'deleting', 'deleted'])
)
def test_property_unsafe_states_validation(state):
    """
    Property: Resources in unsafe states are identified.
    
    For any resource:
    - Terminating/terminated/deleting/deleted states should be unsafe
    - Other states should be safe
    
    Validates: Requirements 4.7
    """
    config = SafetyConfig(
        protected_tags=[],
        whitelist_ids=[],
        minimum_idle_minutes={},
        dry_run_mode=False
    )
    guard = SafetyGuard(config)
    
    resource = Resource(
        resource_id='test-resource',
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags={},
        state=state,
        creation_date='2024-01-01T12:00:00'
    )
    
    result = guard.validate_safe_state(resource)
    
    unsafe_states = ['terminating', 'terminated', 'deleting', 'deleted']
    if state in unsafe_states:
        assert result is False
    else:
        assert result is True


@settings(max_examples=100)
@given(
    num_tags=st.integers(min_value=0, max_value=10),
    has_protected=st.booleans()
)
def test_property_tag_check_consistency(num_tags, has_protected):
    """
    Property: Tag checking is consistent.
    
    For any number of tags:
    - If any tag is protected, resource must be blocked
    - If no protected tags, resource should pass tag check
    - Check should be deterministic
    
    Validates: Requirements 4.1-4.3
    """
    config = SafetyConfig(
        protected_tags=["Environment=production", "CostGuard=protected"],
        whitelist_ids=[],
        minimum_idle_minutes={},
        dry_run_mode=False
    )
    guard = SafetyGuard(config)
    
    # Build tags
    tags = {}
    for i in range(num_tags):
        tags[f'Tag{i}'] = f'value{i}'
    
    # Add protected tag if requested
    if has_protected:
        tags['Environment'] = 'production'
    
    resource = Resource(
        resource_id='test-resource',
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags=tags,
        state='running',
        creation_date='2024-01-01T12:00:00'
    )
    
    # Run check twice
    result1 = guard.check_tags(resource)
    result2 = guard.check_tags(resource)
    
    # Should be deterministic
    assert result1 == result2
    
    # Should match expected result
    if has_protected:
        assert result1 is False
    else:
        assert result1 is True


@settings(max_examples=100)
@given(
    service=st.sampled_from(['ec2', 'rds', 'lambda', 'ebs', 's3', 'dynamodb']),
    has_protection=st.booleans()
)
def test_property_protection_applies_to_all_services(service, has_protection):
    """
    Property: Protection mechanisms apply to all services.
    
    For any service:
    - Protected tags should block actions
    - Whitelist should block actions
    - Safety checks should work consistently
    
    Validates: Requirements 4.1-4.7
    """
    whitelist_ids = ['protected-resource'] if has_protection else []
    
    config = SafetyConfig(
        protected_tags=["Environment=production"],
        whitelist_ids=whitelist_ids,
        minimum_idle_minutes={},
        dry_run_mode=False
    )
    guard = SafetyGuard(config)
    
    resource_id = 'protected-resource' if has_protection else 'normal-resource'
    tags = {'Environment': 'production'} if has_protection else {}
    
    resource = Resource(
        resource_id=resource_id,
        resource_type='test',
        service=service,
        region='us-east-1',
        tags=tags,
        state='active',
        creation_date='2024-01-01T12:00:00'
    )
    
    result = guard.is_action_safe(resource, 'stop')
    
    # Protection should work for all services
    if has_protection:
        assert result.is_safe is False
    else:
        # May pass or fail other checks, but should pass tag/whitelist
        assert guard.check_tags(resource) is True
        assert guard.check_whitelist(resource) is True


@settings(max_examples=100)
@given(
    action=st.sampled_from(['stop', 'terminate', 'delete', 'modify', 'scale_down'])
)
def test_property_protection_applies_to_all_actions(action):
    """
    Property: Protection mechanisms apply to all actions.
    
    For any action type:
    - Protected resources should be blocked
    - Safety checks should work consistently
    
    Validates: Requirements 4.1-4.7
    """
    config = SafetyConfig(
        protected_tags=["Environment=production"],
        whitelist_ids=[],
        minimum_idle_minutes={},
        dry_run_mode=False
    )
    guard = SafetyGuard(config)
    
    protected_resource = Resource(
        resource_id='protected',
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags={'Environment': 'production'},
        state='running',
        creation_date='2024-01-01T12:00:00'
    )
    
    safe_resource = Resource(
        resource_id='safe',
        resource_type='instance',
        service='ec2',
        region='us-east-1',
        tags={'Environment': 'dev'},
        state='stopped',
        creation_date='2024-01-01T12:00:00'
    )
    
    # Protected resource should be blocked for all actions
    protected_result = guard.is_action_safe(protected_resource, action)
    assert protected_result.is_safe is False
    
    # Safe resource should pass for all actions
    safe_result = guard.is_action_safe(safe_resource, action)
    assert safe_result.is_safe is True


@settings(max_examples=100)
@given(
    tag_count=st.integers(min_value=1, max_value=5)
)
def test_property_multiple_protected_tags_any_blocks(tag_count):
    """
    Property: Any protected tag blocks the resource.
    
    For any number of protected tags:
    - If resource has ANY protected tag, it should be blocked
    - Order of tags should not matter
    
    Validates: Requirements 4.1-4.3
    """
    protected_tags = [f"Protected{i}=yes" for i in range(tag_count)]
    
    config = SafetyConfig(
        protected_tags=protected_tags,
        whitelist_ids=[],
        minimum_idle_minutes={},
        dry_run_mode=False
    )
    guard = SafetyGuard(config)
    
    # Test with each protected tag
    for i in range(tag_count):
        resource = Resource(
            resource_id=f'resource-{i}',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={f'Protected{i}': 'yes'},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = guard.check_tags(resource)
        assert result is False
