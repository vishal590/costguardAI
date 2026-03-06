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
    
    # Tests for new services - S3, DynamoDB, EBS
    def test_discover_s3_resources(self, mock_dynamodb):
        """Test S3 bucket discovery."""
        s3 = Mock()
        s3.list_buckets.return_value = {
            'Buckets': [
                {
                    'Name': 'test-bucket',
                    'CreationDate': datetime(2024, 1, 1, 12, 0, 0)
                }
            ]
        }
        s3.get_bucket_location.return_value = {'LocationConstraint': 'us-west-2'}
        s3.get_bucket_tagging.return_value = {
            'TagSet': [
                {'Key': 'Name', 'Value': 'test-bucket'},
                {'Key': 'Environment', 'Value': 'dev'}
            ]
        }
        s3.head_bucket.return_value = None  # Success
        
        manager = ResourceManager({'s3': s3}, mock_dynamodb)
        resources = manager._discover_s3()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'test-bucket'
        assert resources[0].resource_type == 'bucket'
        assert resources[0].service == 's3'
        assert resources[0].region == 'us-west-2'
        assert resources[0].state == 'Active'
        assert resources[0].tags['Name'] == 'test-bucket'
    
    def test_discover_dynamodb_resources(self, mock_dynamodb):
        """Test DynamoDB table discovery."""
        dynamodb = Mock()
        dynamodb.meta.region_name = 'us-east-1'
        
        # Mock paginator
        paginator = Mock()
        page = Mock()
        page.get.return_value = ['test-table']
        paginator.paginate.return_value = [page]
        dynamodb.get_paginator.return_value = paginator
        
        dynamodb.describe_table.return_value = {
            'Table': {
                'TableName': 'test-table',
                'TableArn': 'arn:aws:dynamodb:us-east-1:123456789012:table/test-table',
                'TableStatus': 'ACTIVE',
                'CreationDateTime': datetime(2024, 1, 1, 12, 0, 0)
            }
        }
        dynamodb.list_tags_of_resource.return_value = {
            'Tags': [
                {'Key': 'Name', 'Value': 'test-table'}
            ]
        }
        
        manager = ResourceManager({'dynamodb': dynamodb}, mock_dynamodb)
        resources = manager._discover_dynamodb()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'test-table'
        assert resources[0].resource_type == 'table'
        assert resources[0].service == 'dynamodb'
        assert resources[0].state == 'ACTIVE'
    
    def test_discover_ebs_resources(self, mock_dynamodb):
        """Test EBS volume discovery."""
        ec2 = Mock()
        ec2.meta.region_name = 'us-east-1'
        ec2.describe_volumes.return_value = {
            'Volumes': [
                {
                    'VolumeId': 'vol-1234567890abcdef0',
                    'State': 'available',
                    'CreateTime': datetime(2024, 1, 1, 12, 0, 0),
                    'Tags': [
                        {'Key': 'Name', 'Value': 'test-volume'}
                    ]
                }
            ]
        }
        
        manager = ResourceManager({'ec2': ec2}, mock_dynamodb)
        resources = manager._discover_ebs()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'vol-1234567890abcdef0'
        assert resources[0].resource_type == 'volume'
        assert resources[0].service == 'ebs'
        assert resources[0].state == 'available'
        assert resources[0].tags['Name'] == 'test-volume'
    
    # Tests for ElastiCache, Redshift, ECS, EKS
    def test_discover_elasticache_resources(self, mock_dynamodb):
        """Test ElastiCache cluster discovery."""
        elasticache = Mock()
        elasticache.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = Mock()
        page.get.return_value = [
            {
                'CacheClusterId': 'test-cluster',
                'CacheClusterStatus': 'available',
                'CacheClusterCreateTime': datetime(2024, 1, 1, 12, 0, 0),
                'ARN': 'arn:aws:elasticache:us-east-1:123456789012:cluster:test-cluster'
            }
        ]
        paginator.paginate.return_value = [page]
        elasticache.get_paginator.return_value = paginator
        elasticache.list_tags_for_resource.return_value = {
            'TagList': [
                {'Key': 'Name', 'Value': 'test-cluster'}
            ]
        }
        
        manager = ResourceManager({'elasticache': elasticache}, mock_dynamodb)
        resources = manager._discover_elasticache()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'test-cluster'
        assert resources[0].resource_type == 'cache_cluster'
        assert resources[0].service == 'elasticache'
        assert resources[0].state == 'available'
    
    def test_discover_redshift_resources(self, mock_dynamodb):
        """Test Redshift cluster discovery."""
        redshift = Mock()
        redshift.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = Mock()
        page.get.return_value = [
            {
                'ClusterIdentifier': 'test-cluster',
                'ClusterStatus': 'available',
                'CacheClusterCreateTime': datetime(2024, 1, 1, 12, 0, 0)
            }
        ]
        paginator.paginate.return_value = [page]
        redshift.get_paginator.return_value = paginator
        redshift.describe_tags.return_value = {
            'TaggedResources': [
                {
                    'Tag': {'Key': 'Name', 'Value': 'test-cluster'}
                }
            ]
        }
        
        manager = ResourceManager({'redshift': redshift}, mock_dynamodb)
        resources = manager._discover_redshift()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'test-cluster'
        assert resources[0].resource_type == 'cluster'
        assert resources[0].service == 'redshift'
    
    def test_discover_ecs_resources(self, mock_dynamodb):
        """Test ECS cluster discovery."""
        ecs = Mock()
        ecs.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = Mock()
        page.get.return_value = ['arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster']
        paginator.paginate.return_value = [page]
        ecs.get_paginator.return_value = paginator
        
        ecs.describe_clusters.return_value = {
            'clusters': [
                {
                    'clusterName': 'test-cluster',
                    'clusterArn': 'arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster',
                    'status': 'ACTIVE',
                    'registeredAt': datetime(2024, 1, 1, 12, 0, 0)
                }
            ]
        }
        ecs.list_tags_for_resource.return_value = {
            'tags': [
                {'Key': 'Name', 'Value': 'test-cluster'}
            ]
        }
        
        manager = ResourceManager({'ecs': ecs}, mock_dynamodb)
        resources = manager._discover_ecs()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'test-cluster'
        assert resources[0].resource_type == 'cluster'
        assert resources[0].service == 'ecs'
        assert resources[0].state == 'ACTIVE'
    
    def test_discover_eks_resources(self, mock_dynamodb):
        """Test EKS cluster discovery."""
        eks = Mock()
        eks.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = {'clusters': ['test-cluster']}  # Make page a dict directly
        paginator.paginate.return_value = [page]
        eks.get_paginator.return_value = paginator
        
        eks.describe_cluster.return_value = {
            'cluster': {
                'name': 'test-cluster',
                'status': 'ACTIVE',
                'createdAt': datetime(2024, 1, 1, 12, 0, 0),
                'tags': {'Name': 'test-cluster'}
            }
        }
        
        manager = ResourceManager({'eks': eks}, mock_dynamodb)
        resources = manager._discover_eks()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'test-cluster'
        assert resources[0].resource_type == 'cluster'
        assert resources[0].service == 'eks'
        assert resources[0].state == 'ACTIVE'
    
    # Tests for NAT Gateway, Elastic IP, Load Balancers
    def test_discover_nat_gateways(self, mock_dynamodb):
        """Test NAT Gateway discovery."""
        ec2 = Mock()
        ec2.meta.region_name = 'us-east-1'
        ec2.describe_nat_gateways.return_value = {
            'NatGateways': [
                {
                    'NatGatewayId': 'nat-1234567890abcdef0',
                    'State': 'available',
                    'CreateTime': datetime(2024, 1, 1, 12, 0, 0),
                    'Tags': [
                        {'Key': 'Name', 'Value': 'test-nat'}
                    ]
                }
            ]
        }
        
        manager = ResourceManager({'ec2': ec2}, mock_dynamodb)
        resources = manager._discover_nat_gateways()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'nat-1234567890abcdef0'
        assert resources[0].resource_type == 'nat_gateway'
        assert resources[0].service == 'nat_gateway'
        assert resources[0].state == 'available'
    
    def test_discover_elastic_ips(self, mock_dynamodb):
        """Test Elastic IP discovery."""
        ec2 = Mock()
        ec2.meta.region_name = 'us-east-1'
        ec2.describe_addresses.return_value = {
            'Addresses': [
                {
                    'AllocationId': 'eipalloc-1234567890abcdef0',
                    'PublicIp': '1.2.3.4',
                    'InstanceId': None,  # Unattached
                    'NetworkInterfaceId': None
                }
            ]
        }
        ec2.describe_tags.return_value = {
            'Tags': [
                {'Key': 'Name', 'Value': 'test-eip'}
            ]
        }
        
        manager = ResourceManager({'ec2': ec2}, mock_dynamodb)
        resources = manager._discover_elastic_ips()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'eipalloc-1234567890abcdef0'
        assert resources[0].resource_type == 'elastic_ip'
        assert resources[0].service == 'elastic_ip'
        assert resources[0].state == 'available'
    
    def test_discover_load_balancers(self, mock_dynamodb):
        """Test Load Balancer discovery (ALB/NLB)."""
        elbv2 = Mock()
        elbv2.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = Mock()
        page.get.return_value = [
            {
                'LoadBalancerArn': 'arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test-alb/1234567890abcdef0',
                'LoadBalancerName': 'test-alb',
                'Type': 'application',
                'State': {'Code': 'active'},
                'CreatedTime': datetime(2024, 1, 1, 12, 0, 0),
                'AvailabilityZones': [{'ZoneName': 'us-east-1a'}]
            }
        ]
        paginator.paginate.return_value = [page]
        elbv2.get_paginator.return_value = paginator
        elbv2.describe_tags.return_value = {
            'TagDescriptions': [
                {
                    'ResourceArn': 'arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test-alb/1234567890abcdef0',
                    'Tags': [
                        {'Key': 'Name', 'Value': 'test-alb'}
                    ]
                }
            ]
        }
        
        manager = ResourceManager({'elbv2': elbv2}, mock_dynamodb)
        resources = manager._discover_load_balancers()
        
        assert len(resources) >= 1
        alb = next((r for r in resources if r.service == 'elb'), None)
        assert alb is not None
        assert alb.resource_id == 'test-alb'
        assert 'load_balancer' in alb.resource_type
    
    # Tests for SNS, SQS, API Gateway, Step Functions
    def test_discover_sns_resources(self, mock_dynamodb):
        """Test SNS topic discovery."""
        sns = Mock()
        sns.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = Mock()
        page.get.return_value = [
            {'TopicArn': 'arn:aws:sns:us-east-1:123456789012:test-topic'}
        ]
        paginator.paginate.return_value = [page]
        sns.get_paginator.return_value = paginator
        
        sns.get_topic_attributes.return_value = {
            'Attributes': {}
        }
        sns.list_tags_for_resource.return_value = {
            'Tags': [
                {'Key': 'Name', 'Value': 'test-topic'}
            ]
        }
        
        manager = ResourceManager({'sns': sns}, mock_dynamodb)
        resources = manager._discover_sns()
        
        assert len(resources) == 1
        assert 'test-topic' in resources[0].resource_id
        assert resources[0].resource_type == 'topic'
        assert resources[0].service == 'sns'
    
    def test_discover_sqs_resources(self, mock_dynamodb):
        """Test SQS queue discovery."""
        sqs = Mock()
        sqs.meta.region_name = 'us-east-1'
        sqs.list_queues.return_value = {
            'QueueUrls': ['https://sqs.us-east-1.amazonaws.com/123456789012/test-queue']
        }
        sqs.get_queue_attributes.return_value = {
            'Attributes': {
                'CreatedTimestamp': '1704110400'  # Unix timestamp
            }
        }
        sqs.list_queue_tags.return_value = {
            'Tags': {'Name': 'test-queue'}
        }
        
        manager = ResourceManager({'sqs': sqs}, mock_dynamodb)
        resources = manager._discover_sqs()
        
        assert len(resources) == 1
        assert 'test-queue' in resources[0].resource_id
        assert resources[0].resource_type == 'queue'
        assert resources[0].service == 'sqs'
    
    def test_discover_api_gateway_resources(self, mock_dynamodb):
        """Test API Gateway discovery."""
        apigateway = Mock()
        apigateway.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = {  # Make page a dict directly
            'items': [
                {
                    'id': 'abc123',
                    'name': 'test-api',
                    'createdDate': datetime(2024, 1, 1, 12, 0, 0),
                    'endpointConfiguration': {'types': ['REGIONAL']}
                }
            ]
        }
        paginator.paginate.return_value = [page]
        apigateway.get_paginator.return_value = paginator
        apigateway.get_tags.return_value = {
            'tags': {'Name': 'test-api'}
        }
        
        manager = ResourceManager({'apigateway': apigateway}, mock_dynamodb)
        resources = manager._discover_api_gateway()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'abc123'
        assert resources[0].resource_type == 'rest_api'
        assert resources[0].service == 'apigateway'
    
    def test_discover_step_functions_resources(self, mock_dynamodb):
        """Test Step Functions discovery."""
        stepfunctions = Mock()
        stepfunctions.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = {  # Make page a dict directly
            'stateMachines': [
                {
                    'stateMachineArn': 'arn:aws:states:us-east-1:123456789012:stateMachine:test-sm',
                    'name': 'test-sm',
                    'status': 'ACTIVE',
                    'creationDate': datetime(2024, 1, 1, 12, 0, 0)
                }
            ]
        }
        paginator.paginate.return_value = [page]
        stepfunctions.get_paginator.return_value = paginator
        stepfunctions.list_tags_for_resource.return_value = {
            'tags': [
                {'Key': 'Name', 'Value': 'test-sm'}
            ]
        }
        
        manager = ResourceManager({'stepfunctions': stepfunctions}, mock_dynamodb)
        resources = manager._discover_step_functions()
        
        assert len(resources) == 1
        assert 'test-sm' in resources[0].resource_id
        assert resources[0].resource_type == 'state_machine'
        assert resources[0].service == 'stepfunctions'
    
    # Tests for Glue, SageMaker, CloudFront
    def test_discover_glue_resources(self, mock_dynamodb):
        """Test Glue job discovery."""
        glue = Mock()
        glue.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = {  # Make page a dict directly
            'Jobs': [
                {
                    'Name': 'test-job',
                    'CreatedOn': datetime(2024, 1, 1, 12, 0, 0),
                    'LastRun': {'JobRunState': 'SUCCEEDED'}
                }
            ]
        }
        paginator.paginate.return_value = [page]
        glue.get_paginator.return_value = paginator
        glue.get_tags.return_value = {
            'Tags': {'Name': 'test-job'}
        }
        
        manager = ResourceManager({'glue': glue}, mock_dynamodb)
        resources = manager._discover_glue()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'test-job'
        assert resources[0].resource_type == 'job'
        assert resources[0].service == 'glue'
    
    def test_discover_sagemaker_resources(self, mock_dynamodb):
        """Test SageMaker endpoint discovery."""
        sagemaker = Mock()
        sagemaker.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page = {  # Make page a dict directly
            'Endpoints': [
                {
                    'EndpointName': 'test-endpoint'
                }
            ]
        }
        paginator.paginate.return_value = [page]
        sagemaker.get_paginator.return_value = paginator
        
        sagemaker.describe_endpoint.return_value = {
            'Endpoint': {
                'EndpointName': 'test-endpoint',
                'EndpointArn': 'arn:aws:sagemaker:us-east-1:123456789012:endpoint/test-endpoint',
                'EndpointStatus': 'InService',
                'CreationTime': datetime(2024, 1, 1, 12, 0, 0)
            }
        }
        sagemaker.list_tags.return_value = {
            'Tags': [
                {'Key': 'Name', 'Value': 'test-endpoint'}
            ]
        }
        
        manager = ResourceManager({'sagemaker': sagemaker}, mock_dynamodb)
        resources = manager._discover_sagemaker()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'test-endpoint'
        assert resources[0].resource_type == 'endpoint'
        assert resources[0].service == 'sagemaker'
        assert resources[0].state == 'InService'
    
    def test_discover_cloudfront_resources(self, mock_dynamodb):
        """Test CloudFront distribution discovery."""
        cloudfront = Mock()
        
        paginator = Mock()
        page = {  # Make page a dict directly
            'DistributionList': {
                'Items': [
                    {
                        'Id': 'E1234567890ABC',
                        'Status': 'Deployed',
                        'LastModifiedTime': datetime(2024, 1, 1, 12, 0, 0),
                        'ARN': 'arn:aws:cloudfront::123456789012:distribution/E1234567890ABC'
                    }
                ]
            }
        }
        paginator.paginate.return_value = [page]
        cloudfront.get_paginator.return_value = paginator
        cloudfront.list_tags_for_resource.return_value = {
            'Tags': {
                'Items': [
                    {'Key': 'Name', 'Value': 'test-distribution'}
                ]
            }
        }
        
        manager = ResourceManager({'cloudfront': cloudfront}, mock_dynamodb)
        resources = manager._discover_cloudfront()
        
        assert len(resources) == 1
        assert resources[0].resource_id == 'E1234567890ABC'
        assert resources[0].resource_type == 'distribution'
        assert resources[0].service == 'cloudfront'
        assert resources[0].region == 'global'
        assert resources[0].state == 'Deployed'
    
    # Error handling tests
    def test_discover_s3_no_client(self, mock_dynamodb):
        """Test S3 discovery with no client."""
        manager = ResourceManager({}, mock_dynamodb)
        resources = manager._discover_s3()
        assert len(resources) == 0
    
    def test_discover_s3_tagging_error(self, mock_dynamodb):
        """Test S3 discovery handles tagging errors gracefully."""
        s3 = Mock()
        s3.list_buckets.return_value = {
            'Buckets': [
                {
                    'Name': 'test-bucket',
                    'CreationDate': datetime(2024, 1, 1, 12, 0, 0)
                }
            ]
        }
        s3.get_bucket_location.return_value = {'LocationConstraint': 'us-west-2'}
        s3.get_bucket_tagging.side_effect = Exception("Access Denied")
        s3.head_bucket.return_value = None
        
        manager = ResourceManager({'s3': s3}, mock_dynamodb)
        resources = manager._discover_s3()
        
        # Should still return resource even if tagging fails
        assert len(resources) == 1
        assert resources[0].tags == {}
    
    def test_discover_dynamodb_pagination(self, mock_dynamodb):
        """Test DynamoDB discovery with pagination."""
        dynamodb = Mock()
        dynamodb.meta.region_name = 'us-east-1'
        
        paginator = Mock()
        page1 = Mock()
        page1.get.return_value = ['table1']
        page2 = Mock()
        page2.get.return_value = ['table2']
        paginator.paginate.return_value = [page1, page2]
        dynamodb.get_paginator.return_value = paginator
        
        dynamodb.describe_table.return_value = {
            'Table': {
                'TableName': 'table1',
                'TableArn': 'arn:aws:dynamodb:us-east-1:123456789012:table/table1',
                'TableStatus': 'ACTIVE',
                'CreationDateTime': datetime(2024, 1, 1, 12, 0, 0)
            }
        }
        dynamodb.list_tags_of_resource.return_value = {'Tags': []}
        
        manager = ResourceManager({'dynamodb': dynamodb}, mock_dynamodb)
        resources = manager._discover_dynamodb()
        
        # Should handle pagination
        assert dynamodb.describe_table.call_count >= 1
    
    def test_discover_load_balancers_classic_elb(self, mock_dynamodb):
        """Test Classic ELB discovery."""
        elb = Mock()
        elb.meta.region_name = 'us-east-1'
        elb.describe_load_balancers.return_value = {
            'LoadBalancerDescriptions': [
                {
                    'LoadBalancerName': 'test-elb',
                    'CreatedTime': datetime(2024, 1, 1, 12, 0, 0)
                }
            ]
        }
        elb.describe_tags.return_value = {
            'TagDescriptions': [
                {
                    'LoadBalancerName': 'test-elb',
                    'Tags': [
                        {'Key': 'Name', 'Value': 'test-elb'}
                    ]
                }
            ]
        }
        
        manager = ResourceManager({'elb': elb}, mock_dynamodb)
        resources = manager._discover_load_balancers()
        
        assert len(resources) >= 1
        elb_resource = next((r for r in resources if r.resource_type == 'classic_load_balancer'), None)
        assert elb_resource is not None
        assert elb_resource.resource_id == 'test-elb'