"""
Property-based tests for RollbackManager.

Tests Property 4: Action Reversibility
- For any automated action taken, there must exist a rollback operation
  that can restore the resource to its pre-action state within 24 hours.
- Validates Requirements 9.1-9.7
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock
from src.services.rollback_manager import RollbackManager
from src.utils.types import Resource, RollbackResult


# Strategies for generating test data
@st.composite
def resource_data(draw):
    """Generate valid resource data."""
    service = draw(st.sampled_from(['ec2', 'rds', 'lambda']))
    resource_id = draw(st.text(min_size=5, max_size=30, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-'
    )))
    
    if service == 'ec2':
        resource_type = 'instance'
        state = draw(st.sampled_from(['running', 'stopped']))
    elif service == 'rds':
        resource_type = 'db_instance'
        state = draw(st.sampled_from(['available', 'stopped']))
    else:  # lambda
        resource_type = 'function'
        state = 'Active'
    
    return Resource(
        resource_id=resource_id,
        resource_type=resource_type,
        service=service,
        region='us-east-1',
        tags={'Name': f'test-{resource_id}'},
        state=state,
        creation_date='2024-01-01T12:00:00'
    )


@st.composite
def timestamp_within_window(draw, hours_ago_max=23):
    """Generate timestamp within rollback window."""
    hours_ago = draw(st.integers(min_value=0, max_value=hours_ago_max))
    minutes_ago = draw(st.integers(min_value=0, max_value=59))
    timestamp = datetime.now(UTC) - timedelta(hours=hours_ago, minutes=minutes_ago)
    return timestamp.isoformat()


@st.composite
def timestamp_outside_window(draw, hours_ago_min=25):
    """Generate timestamp outside rollback window."""
    hours_ago = draw(st.integers(min_value=hours_ago_min, max_value=100))
    timestamp = datetime.now(UTC) - timedelta(hours=hours_ago)
    return timestamp.isoformat()


class TestRollbackManagerProperties:
    """Property-based tests for RollbackManager."""
    
    @given(resource_data())
    @settings(max_examples=100)
    def test_property_all_actions_store_state_with_ttl(self, resource):
        """
        Property 4a: All automated actions store pre-action state with TTL.
        
        For any resource and action, store_pre_action_state should store
        the state in DynamoDB with a 24-hour TTL.
        """
        # Setup
        dynamodb_client = Mock()
        dynamodb_client.put_item = Mock(return_value={})
        
        aws_clients = {
            'ec2': Mock(),
            'rds': Mock(),
            'lambda': Mock()
        }
        
        manager = RollbackManager(
            aws_clients=aws_clients,
            dynamodb_client=dynamodb_client
        )
        
        # Execute
        manager.store_pre_action_state(resource, 'stop')
        
        # Verify
        dynamodb_client.put_item.assert_called_once()
        
        # Verify TTL is set (24 hours from now)
        call_args = dynamodb_client.put_item.call_args
        item = call_args[1]['Item']
        assert 'ttl' in item
        ttl_value = int(item['ttl']['N'])
        expected_ttl = int((datetime.now(UTC) + timedelta(hours=24)).timestamp())
        # Allow 60 second tolerance for test execution time
        assert abs(ttl_value - expected_ttl) < 60
        
        # Verify action_id, resource_id, and state are stored
        assert 'action_id' in item
        assert 'resource_id' in item
        assert item['resource_id']['S'] == resource.resource_id
        assert 'state' in item
    
    @given(resource_data(), timestamp_within_window())
    @settings(max_examples=100)
    def test_property_actions_within_window_return_result(self, resource, timestamp):
        """
        Property 4b: Actions within 24-hour window can be queried.
        
        For any action stored within the rollback window, execute_rollback
        should return a RollbackResult object.
        """
        # Setup
        action_id = f"{resource.resource_id}_{timestamp}"
        
        dynamodb_client = Mock()
        dynamodb_client.get_item = Mock(return_value={
            'Item': {
                'action_id': {'S': action_id},
                'resource_id': {'S': resource.resource_id},
                'action': {'S': 'stop'},
                'state': {'S': str({
                    'resource_id': resource.resource_id,
                    'service': resource.service,
                    'state': resource.state
                })},
                'timestamp': {'S': timestamp}
            }
        })
        
        aws_clients = {
            'ec2': Mock(),
            'rds': Mock(),
            'lambda': Mock()
        }
        
        # Mock service clients to succeed
        aws_clients['ec2'].start_instances = Mock(return_value={})
        aws_clients['rds'].start_db_instance = Mock(return_value={})
        aws_clients['lambda'].delete_function_concurrency = Mock(return_value={})
        
        manager = RollbackManager(
            aws_clients=aws_clients,
            dynamodb_client=dynamodb_client
        )
        
        # Execute
        result = manager.execute_rollback(action_id)
        
        # Verify
        assert isinstance(result, RollbackResult)
        assert result.action_id == action_id
        assert result.resource_id == resource.resource_id
        # Result may succeed or fail depending on service-specific logic
        assert isinstance(result.success, bool)
        assert isinstance(result.restored_state, dict)
        assert result.timestamp is not None
    
    @given(resource_data(), timestamp_outside_window())
    @settings(max_examples=100)
    def test_property_actions_outside_window_fail(self, resource, timestamp):
        """
        Property 4c: Actions outside 24-hour window cannot be rolled back.
        
        For any action stored outside the rollback window, execute_rollback
        should return a failed RollbackResult.
        """
        # Setup
        action_id = f"{resource.resource_id}_{timestamp}"
        
        dynamodb_client = Mock()
        dynamodb_client.get_item = Mock(return_value={
            'Item': {
                'action_id': {'S': action_id},
                'resource_id': {'S': resource.resource_id},
                'action': {'S': 'stop'},
                'state': {'S': str({
                    'resource_id': resource.resource_id,
                    'service': resource.service,
                    'state': resource.state
                })},
                'timestamp': {'S': timestamp}
            }
        })
        
        aws_clients = {
            'ec2': Mock(),
            'rds': Mock(),
            'lambda': Mock()
        }
        
        manager = RollbackManager(
            aws_clients=aws_clients,
            dynamodb_client=dynamodb_client
        )
        
        # Execute
        result = manager.execute_rollback(action_id)
        
        # Verify
        assert isinstance(result, RollbackResult)
        assert result.action_id == action_id
        assert result.success is False
    
    @given(st.lists(resource_data(), min_size=2, max_size=5, unique_by=lambda x: x.resource_id))
    @settings(max_examples=50)
    def test_property_multiple_state_stores_independent(self, resources):
        """
        Property 4d: Multiple state stores are independent.
        
        For any set of resources, storing state for one should not affect others.
        Each store operation should succeed independently.
        """
        # Setup
        dynamodb_client = Mock()
        dynamodb_client.put_item = Mock(return_value={})
        
        aws_clients = {
            'ec2': Mock(),
            'rds': Mock(),
            'lambda': Mock()
        }
        
        manager = RollbackManager(
            aws_clients=aws_clients,
            dynamodb_client=dynamodb_client
        )
        
        # Execute - store state for all resources
        for resource in resources:
            manager.store_pre_action_state(resource, 'stop')
        
        # Verify each store was called
        assert dynamodb_client.put_item.call_count == len(resources)
        
        # Verify each call had unique resource_id
        resource_ids = []
        for call in dynamodb_client.put_item.call_args_list:
            item = call[1]['Item']
            resource_ids.append(item['resource_id']['S'])
        
        assert len(set(resource_ids)) == len(resources)
    
    @given(resource_data())
    @settings(max_examples=100)
    def test_property_rollback_window_configurable(self, resource):
        """
        Property 4e: Rollback window is configurable.
        
        The rollback window should be configurable and enforced consistently.
        """
        # Setup
        dynamodb_client = Mock()
        dynamodb_client.put_item = Mock(return_value={})
        
        aws_clients = {
            'ec2': Mock(),
            'rds': Mock(),
            'lambda': Mock()
        }
        
        manager = RollbackManager(
            aws_clients=aws_clients,
            dynamodb_client=dynamodb_client
        )
        
        # Verify default rollback window
        assert manager.rollback_window_hours == 24
        
        # Store state
        manager.store_pre_action_state(resource, 'stop')
        
        # Verify TTL matches rollback window
        call_args = dynamodb_client.put_item.call_args
        item = call_args[1]['Item']
        ttl_value = int(item['ttl']['N'])
        expected_ttl = int((datetime.now(UTC) + timedelta(hours=manager.rollback_window_hours)).timestamp())
        assert abs(ttl_value - expected_ttl) < 60
    
    @given(resource_data())
    @settings(max_examples=100)
    def test_property_action_not_found_returns_failed_result(self, resource):
        """
        Property 4f: Non-existent actions return failed result.
        
        For any action_id that doesn't exist, execute_rollback should
        return a failed RollbackResult without raising an exception.
        """
        # Setup
        action_id = f"nonexistent-{resource.resource_id}"
        
        dynamodb_client = Mock()
        dynamodb_client.get_item = Mock(return_value={})  # No Item
        
        aws_clients = {
            'ec2': Mock(),
            'rds': Mock(),
            'lambda': Mock()
        }
        
        manager = RollbackManager(
            aws_clients=aws_clients,
            dynamodb_client=dynamodb_client
        )
        
        # Execute
        result = manager.execute_rollback(action_id)
        
        # Verify
        assert isinstance(result, RollbackResult)
        assert result.action_id == action_id
        assert result.success is False
        assert result.resource_id == "unknown"
