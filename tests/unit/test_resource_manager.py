"""
Unit tests for ResourceManager.

Tests resource discovery, metadata retrieval, and inventory management.
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, MagicMock, patch
from src.services.resource_manager import ResourceManager
from src.utils.types import Resource, ResourceMetadata


class TestResourceManager:
    """Test ResourceManager class."""
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock AWS clients."""
        ec2 = Mock()
        ec2.meta.region_name = 'us-east-1'
        ec2.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'State': {'Name': 'running'},
                            'LaunchTime': datetime(2024, 1, 1, 12, 0, 0),
                            'Tags': [
                                {'Key': 'Name', 'Value': 'test-instance'},
                                {'Key': 'Environment', 'Value': 'dev'}
                            ]
                        }
                    ]
                }
            ]
        }
        
        rds = Mock()
        rds.meta.region_name = 'us-east-1'
        rds.describe_db_instances.return_value = {
            'DBInstances': [
                {
                    'DBInstanceIdentifier': 'test-db',
                    'DBInstanceStatus': 'available',
                    'InstanceCreateTime': datetime(2024, 1, 1, 12, 0, 0),
                    'TagList': [
                        {'Key': 'Name', 'Value': 'test-db'},
                        {'Key': 'Environment', 'Value': 'dev'}
                    ]
                }
            ]
        }
        
        lambda_client = Mock()
        lambda_client.meta.region_name = 'us-east-1'
        lambda_client.list_functions.return_value = {
            'Functions': [
                {
                    'FunctionArn': 'arn:aws:lambda:us-east-1:123456789012:function:test-func',
                    'LastModified': '2024-01-01T12:00:00.000+0000'
                }
            ]
        }
        
        return {
            'ec2': ec2,
            'rds': rds,
            'lambda': lambda_client
        }
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Create mock DynamoDB client."""
        dynamodb = Mock()
        dynamodb.put_item.return_value = {}
        return dynamodb
    
    @pytest.fixture
    def resource_manager(self, mock_clients, mock_dynamodb):
        """Create ResourceManager instance."""
        return ResourceManager(mock_clients, mock_dynamodb)
    
    def test_discover_ec2_resources(self, resource_manager):
        """Test EC2 resource discovery."""
        resources = resource_manager._discover_ec2()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'i-1234567890abcdef0'
        assert resources[0].resource_type == 'instance'
        assert resources[0].service == 'ec2'
        assert resources[0].region == 'us-east-1'
        assert resources[0].state == 'running'
        assert resources[0].tags['Name'] == 'test-instance'
        assert resources[0].tags['Environment'] == 'dev'
    
    def test_discover_rds_resources(self, resource_manager):
        """Test RDS resource discovery."""
        resources = resource_manager._discover_rds()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'test-db'
        assert resources[0].resource_type == 'db_instance'
        assert resources[0].service == 'rds'
        assert resources[0].region == 'us-east-1'
        assert resources[0].state == 'available'
        assert resources[0].tags['Name'] == 'test-db'
    
    def test_discover_lambda_resources(self, resource_manager):
        """Test Lambda resource discovery."""
        resources = resource_manager._discover_lambda()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'arn:aws:lambda:us-east-1:123456789012:function:test-func'
        assert resources[0].resource_type == 'function'
        assert resources[0].service == 'lambda'
        assert resources[0].state == 'Active'
    
    def test_discover_resources_multiple_services(self, resource_manager):
        """Test discovering resources across multiple services."""
        resources = resource_manager.discover_resources(['ec2', 'rds', 'lambda'])
        
        assert len(resources) == 3
        services = {r.service for r in resources}
        assert services == {'ec2', 'rds', 'lambda'}
    
    def test_discover_resources_with_error(self, resource_manager, mock_clients):
        """Test resource discovery continues on service error."""
        # Make EC2 fail
        mock_clients['ec2'].describe_instances.side_effect = Exception("API Error")
        
        resources = resource_manager.discover_resources(['ec2', 'rds'])
        
        # Should still get RDS resources
        assert len(resources) == 1
        assert resources[0].service == 'rds'
    
    def test_discover_resources_unknown_service(self, resource_manager):
        """Test discovering resources for unknown service."""
        resources = resource_manager.discover_resources(['unknown_service'])
        
        assert len(resources) == 0
    
    def test_update_inventory(self, resource_manager, mock_dynamodb):
        """Test inventory update in DynamoDB."""
        resource = Resource(
            resource_id='i-test',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Name': 'test'},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        resource_manager.update_inventory([resource])
        
        # Verify DynamoDB put_item was called
        mock_dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb.put_item.call_args[1]
        
        assert call_args['TableName'] == 'resource-inventory'
        assert call_args['Item']['resource_id']['S'] == 'i-test'
        assert call_args['Item']['service']['S'] == 'ec2'
        assert call_args['Item']['state']['S'] == 'running'
    
    def test_update_inventory_with_error(self, resource_manager, mock_dynamodb):
        """Test inventory update handles errors gracefully."""
        mock_dynamodb.put_item.side_effect = Exception("DynamoDB Error")
        
        resource = Resource(
            resource_id='i-test',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        # Should not raise exception
        resource_manager.update_inventory([resource])
    
    def test_get_resource_metadata(self, resource_manager):
        """Test getting resource metadata."""
        resource = Resource(
            resource_id='i-test',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = resource_manager.get_resource_metadata(resource)
        
        assert isinstance(metadata, ResourceMetadata)
        assert metadata.resource == resource
        assert isinstance(metadata.cost_per_hour, float)
        assert isinstance(metadata.last_activity, str)
        assert isinstance(metadata.metrics, dict)
    
    def test_extract_tags(self, resource_manager):
        """Test extracting tags from AWS format."""
        tag_list = [
            {'Key': 'Name', 'Value': 'test'},
            {'Key': 'Environment', 'Value': 'prod'}
        ]
        
        tags = resource_manager._extract_tags(tag_list)
        
        assert tags == {'Name': 'test', 'Environment': 'prod'}
    
    def test_extract_tags_empty(self, resource_manager):
        """Test extracting empty tag list."""
        tags = resource_manager._extract_tags([])
        
        assert tags == {}
    
    def test_format_tags_for_dynamodb(self, resource_manager):
        """Test formatting tags for DynamoDB."""
        tags = {'Name': 'test', 'Environment': 'prod'}
        
        formatted = resource_manager._format_tags(tags)
        
        assert formatted == {
            'Name': {'S': 'test'},
            'Environment': {'S': 'prod'}
        }
    
    def test_discover_resources_no_client(self, mock_dynamodb):
        """Test discovery when service client is missing."""
        # Create manager with empty clients
        manager = ResourceManager({}, mock_dynamodb)
        
        resources = manager._discover_ec2()
        
        assert len(resources) == 0
    
    def test_discover_resources_empty_response(self, resource_manager, mock_clients):
        """Test discovery with empty API response."""
        mock_clients['ec2'].describe_instances.return_value = {'Reservations': []}
        
        resources = resource_manager._discover_ec2()
        
        assert len(resources) == 0
    
    def test_discover_resources_multiple_instances(self, resource_manager, mock_clients):
        """Test discovering multiple instances."""
        mock_clients['ec2'].describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-111',
                            'State': {'Name': 'running'},
                            'LaunchTime': datetime(2024, 1, 1, 12, 0, 0),
                            'Tags': []
                        },
                        {
                            'InstanceId': 'i-222',
                            'State': {'Name': 'stopped'},
                            'LaunchTime': datetime(2024, 1, 2, 12, 0, 0),
                            'Tags': []
                        }
                    ]
                }
            ]
        }
        
        resources = resource_manager._discover_ec2()
        
        assert len(resources) == 2
        assert resources[0].resource_id == 'i-111'
        assert resources[0].state == 'running'
        assert resources[1].resource_id == 'i-222'
        assert resources[1].state == 'stopped'
    
    def test_discover_resources_updates_inventory(self, resource_manager, mock_dynamodb):
        """Test that discover_resources updates inventory."""
        resources = resource_manager.discover_resources(['ec2'])
        
        # Verify inventory was updated
        assert mock_dynamodb.put_item.called
        assert len(resources) == 1
    
    def test_discover_service_resources_all_services(self, resource_manager):
        """Test that all service discovery methods are mapped."""
        services = [
            'ec2', 'rds', 'lambda', 's3', 'dynamodb', 'ebs',
            'elasticache', 'redshift', 'ecs', 'eks', 'nat_gateway',
            'elastic_ip', 'elb', 'sns', 'sqs', 'apigateway',
            'stepfunctions', 'glue', 'sagemaker', 'cloudfront'
        ]
        
        for service in services:
            # Should not raise exception
            resources = resource_manager._discover_service_resources(service)
            assert isinstance(resources, list)
