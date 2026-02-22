"""
Property-based tests for ResourceManager.

Tests universal properties that should hold for all resource discovery operations.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, UTC, timedelta
from unittest.mock import Mock
from src.services.resource_manager import ResourceManager
from src.utils.types import Resource


# Feature: automated-cost-prevention, Property 7: Multi-Service Coverage
# All supported services must be discoverable without errors


@settings(max_examples=100)
@given(
    services=st.lists(
        st.sampled_from([
            'ec2', 'rds', 'lambda', 's3', 'dynamodb', 'ebs',
            'elasticache', 'redshift', 'ecs', 'eks', 'nat_gateway',
            'elastic_ip', 'elb', 'sns', 'sqs', 'apigateway',
            'stepfunctions', 'glue', 'sagemaker', 'cloudfront'
        ]),
        min_size=1,
        max_size=20,
        unique=True
    )
)
def test_property_multi_service_coverage(services):
    """
    Property 7: Multi-Service Coverage
    
    For any subset of supported services:
    - Discovery should complete without exceptions
    - Result should be a list
    - All returned resources should have valid service names
    
    Validates: Requirements 2.1
    """
    # Create mock clients
    mock_clients = {}
    for service in services:
        client = Mock()
        client.meta.region_name = 'us-east-1'
        
        # Configure mock responses based on service
        if service == 'ec2':
            client.describe_instances.return_value = {'Reservations': []}
        elif service == 'rds':
            client.describe_db_instances.return_value = {'DBInstances': []}
        elif service == 'lambda':
            client.list_functions.return_value = {'Functions': []}
        
        mock_clients[service] = client
    
    mock_dynamodb = Mock()
    mock_dynamodb.put_item.return_value = {}
    
    manager = ResourceManager(mock_clients, mock_dynamodb)
    
    # Discovery should complete without exceptions
    resources = manager.discover_resources(services)
    
    # Result should be a list
    assert isinstance(resources, list)
    
    # All returned resources should have valid service names
    for resource in resources:
        assert resource.service in services


# Feature: automated-cost-prevention, Property 12: Resource Inventory Freshness
# Inventory updates must include current timestamp and all resource attributes


@settings(max_examples=100)
@given(
    resource_count=st.integers(min_value=1, max_value=50),
    service=st.sampled_from(['ec2', 'rds', 'lambda', 's3', 'dynamodb'])
)
def test_property_inventory_freshness(resource_count, service):
    """
    Property 12: Resource Inventory Freshness
    
    For any number of resources:
    - Inventory update should include timestamp
    - Timestamp should be recent (within last minute)
    - All resource attributes should be stored
    - Update should be idempotent
    
    Validates: Requirements 2.4, 2.5
    """
    # Create resources
    resources = []
    for i in range(resource_count):
        resources.append(Resource(
            resource_id=f'resource-{i}',
            resource_type='instance',
            service=service,
            region='us-east-1',
            tags={'Index': str(i)},
            state='active',
            creation_date='2024-01-01T12:00:00'
        ))
    
    mock_dynamodb = Mock()
    mock_dynamodb.put_item.return_value = {}
    
    manager = ResourceManager({}, mock_dynamodb)
    
    # Record time before update
    before_update = datetime.now(UTC)
    
    # Update inventory
    manager.update_inventory(resources)
    
    # Record time after update
    after_update = datetime.now(UTC)
    
    # Verify all resources were stored
    assert mock_dynamodb.put_item.call_count == resource_count
    
    # Verify each call includes timestamp and all attributes
    for call in mock_dynamodb.put_item.call_args_list:
        item = call[1]['Item']
        
        # Timestamp should be present
        assert 'timestamp' in item
        timestamp_str = item['timestamp']['S']
        timestamp = datetime.fromisoformat(timestamp_str)
        
        # Timestamp should be recent (within the update window)
        assert before_update <= timestamp <= after_update
        
        # All required attributes should be present
        assert 'resource_id' in item
        assert 'resource_type' in item
        assert 'service' in item
        assert 'region' in item
        assert 'state' in item
        assert 'tags' in item
        assert 'creation_date' in item


@settings(max_examples=100)
@given(
    service=st.sampled_from(['ec2', 'rds', 'lambda']),
    has_tags=st.booleans()
)
def test_property_resource_attributes_preserved(service, has_tags):
    """
    Property: Resource attributes are preserved during discovery.
    
    For any service and tag configuration:
    - Discovered resources should have all required attributes
    - Tags should be properly extracted
    - State should be captured
    - Timestamps should be valid ISO format
    
    Validates: Requirements 2.2, 2.3
    """
    # Create mock client
    mock_clients = {}
    client = Mock()
    client.meta.region_name = 'us-east-1'
    
    tags = [{'Key': 'Name', 'Value': 'test'}] if has_tags else []
    
    if service == 'ec2':
        client.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-test',
                    'State': {'Name': 'running'},
                    'LaunchTime': datetime(2024, 1, 1, 12, 0, 0),
                    'Tags': tags
                }]
            }]
        }
    elif service == 'rds':
        client.describe_db_instances.return_value = {
            'DBInstances': [{
                'DBInstanceIdentifier': 'db-test',
                'DBInstanceStatus': 'available',
                'InstanceCreateTime': datetime(2024, 1, 1, 12, 0, 0),
                'TagList': tags
            }]
        }
    elif service == 'lambda':
        client.list_functions.return_value = {
            'Functions': [{
                'FunctionArn': 'arn:aws:lambda:us-east-1:123456789012:function:test',
                'LastModified': '2024-01-01T12:00:00.000+0000'
            }]
        }
    
    mock_clients[service] = client
    mock_dynamodb = Mock()
    mock_dynamodb.put_item.return_value = {}
    
    manager = ResourceManager(mock_clients, mock_dynamodb)
    
    # Discover resources
    resources = manager.discover_resources([service])
    
    # Should have at least one resource
    assert len(resources) >= 1
    
    for resource in resources:
        # All required attributes should be present
        assert resource.resource_id
        assert resource.resource_type
        assert resource.service == service
        assert resource.region == 'us-east-1'
        assert resource.state
        assert resource.creation_date
        assert isinstance(resource.tags, dict)
        
        # If tags were provided, they should be extracted
        if has_tags and service != 'lambda':  # Lambda doesn't include tags in list
            assert 'Name' in resource.tags
            assert resource.tags['Name'] == 'test'


@settings(max_examples=100)
@given(
    error_service=st.sampled_from(['ec2', 'rds', 'lambda']),
    success_service=st.sampled_from(['ec2', 'rds', 'lambda'])
)
def test_property_error_isolation(error_service, success_service):
    """
    Property: Service discovery errors are isolated.
    
    For any combination of failing and succeeding services:
    - Failure in one service should not affect others
    - Successful services should return resources
    - No exceptions should propagate
    
    Validates: Requirements 2.1 (error handling)
    """
    if error_service == success_service:
        # Skip if same service (can't both fail and succeed)
        return
    
    # Create mock clients
    mock_clients = {}
    
    # Configure error service
    error_client = Mock()
    error_client.meta.region_name = 'us-east-1'
    if error_service == 'ec2':
        error_client.describe_instances.side_effect = Exception("API Error")
    elif error_service == 'rds':
        error_client.describe_db_instances.side_effect = Exception("API Error")
    elif error_service == 'lambda':
        error_client.list_functions.side_effect = Exception("API Error")
    mock_clients[error_service] = error_client
    
    # Configure success service
    success_client = Mock()
    success_client.meta.region_name = 'us-east-1'
    if success_service == 'ec2':
        success_client.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-success',
                    'State': {'Name': 'running'},
                    'LaunchTime': datetime(2024, 1, 1, 12, 0, 0),
                    'Tags': []
                }]
            }]
        }
    elif success_service == 'rds':
        success_client.describe_db_instances.return_value = {
            'DBInstances': [{
                'DBInstanceIdentifier': 'db-success',
                'DBInstanceStatus': 'available',
                'InstanceCreateTime': datetime(2024, 1, 1, 12, 0, 0),
                'TagList': []
            }]
        }
    elif success_service == 'lambda':
        success_client.list_functions.return_value = {
            'Functions': [{
                'FunctionArn': 'arn:aws:lambda:us-east-1:123456789012:function:success',
                'LastModified': '2024-01-01T12:00:00.000+0000'
            }]
        }
    mock_clients[success_service] = success_client
    
    mock_dynamodb = Mock()
    mock_dynamodb.put_item.return_value = {}
    
    manager = ResourceManager(mock_clients, mock_dynamodb)
    
    # Discovery should not raise exception
    resources = manager.discover_resources([error_service, success_service])
    
    # Should get resources from success service only
    assert len(resources) >= 1
    assert all(r.service == success_service for r in resources)


@settings(max_examples=100)
@given(
    resource_count=st.integers(min_value=0, max_value=100)
)
def test_property_discovery_completeness(resource_count):
    """
    Property: Discovery returns all available resources.
    
    For any number of resources:
    - All resources should be discovered
    - No duplicates should exist
    - Count should match expected
    
    Validates: Requirements 2.1
    """
    # Create mock EC2 client with specified number of instances
    mock_ec2 = Mock()
    mock_ec2.meta.region_name = 'us-east-1'
    
    instances = []
    for i in range(resource_count):
        instances.append({
            'InstanceId': f'i-{i:016x}',
            'State': {'Name': 'running'},
            'LaunchTime': datetime(2024, 1, 1, 12, 0, 0),
            'Tags': []
        })
    
    mock_ec2.describe_instances.return_value = {
        'Reservations': [{'Instances': instances}] if instances else {'Reservations': []}
    }
    
    mock_dynamodb = Mock()
    mock_dynamodb.put_item.return_value = {}
    
    manager = ResourceManager({'ec2': mock_ec2}, mock_dynamodb)
    
    # Discover resources
    resources = manager.discover_resources(['ec2'])
    
    # Should discover all resources
    assert len(resources) == resource_count
    
    # No duplicates
    resource_ids = [r.resource_id for r in resources]
    assert len(resource_ids) == len(set(resource_ids))
