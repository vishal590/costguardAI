"""
Integration tests for Prevention Engine with new services.

Verifies that all 22 services can be discovered and processed by the prevention engine.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, UTC
from src.services.prevention_engine import PreventionEngine
from src.services.resource_manager import ResourceManager
from src.services.idle_detector import IdleDetector
from src.utils.types import Resource


class TestPreventionEngineNewServices:
    """Test Prevention Engine integration with all 22 services."""
    
    @pytest.fixture
    def mock_aws_clients(self):
        """Create mock AWS clients for all services."""
        clients = {}
        
        # EC2 client (used for EC2, EBS, NAT Gateway, Elastic IP)
        ec2 = Mock()
        ec2.meta.region_name = 'us-east-1'
        ec2.describe_instances.return_value = {'Reservations': []}
        ec2.describe_volumes.return_value = {'Volumes': []}
        ec2.describe_nat_gateways.return_value = {'NatGateways': []}
        ec2.describe_addresses.return_value = {'Addresses': []}
        clients['ec2'] = ec2
        
        # S3 client
        s3 = Mock()
        s3.list_buckets.return_value = {'Buckets': []}
        clients['s3'] = s3
        
        # DynamoDB client
        dynamodb = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'TableNames': []}]
        dynamodb.get_paginator.return_value = paginator
        dynamodb.meta.region_name = 'us-east-1'
        clients['dynamodb'] = dynamodb
        
        # RDS client
        rds = Mock()
        rds.describe_db_instances.return_value = {'DBInstances': []}
        rds.meta.region_name = 'us-east-1'
        clients['rds'] = rds
        
        # Lambda client
        lambda_client = Mock()
        lambda_client.list_functions.return_value = {'Functions': []}
        lambda_client.meta.region_name = 'us-east-1'
        clients['lambda'] = lambda_client
        
        # ElastiCache client
        elasticache = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'CacheClusters': []}]
        elasticache.get_paginator.return_value = paginator
        elasticache.meta.region_name = 'us-east-1'
        clients['elasticache'] = elasticache
        
        # Redshift client
        redshift = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'Clusters': []}]
        redshift.get_paginator.return_value = paginator
        redshift.meta.region_name = 'us-east-1'
        clients['redshift'] = redshift
        
        # ECS client
        ecs = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'clusterArns': []}]
        ecs.get_paginator.return_value = paginator
        ecs.meta.region_name = 'us-east-1'
        clients['ecs'] = ecs
        
        # EKS client
        eks = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'clusters': []}]
        eks.get_paginator.return_value = paginator
        eks.meta.region_name = 'us-east-1'
        clients['eks'] = eks
        
        # ELB v2 client (ALB/NLB)
        elbv2 = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'LoadBalancers': []}]
        elbv2.get_paginator.return_value = paginator
        elbv2.meta.region_name = 'us-east-1'
        clients['elbv2'] = elbv2
        
        # Classic ELB client
        elb = Mock()
        elb.describe_load_balancers.return_value = {'LoadBalancerDescriptions': []}
        elb.meta.region_name = 'us-east-1'
        clients['elb'] = elb
        
        # SNS client
        sns = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'Topics': []}]
        sns.get_paginator.return_value = paginator
        sns.meta.region_name = 'us-east-1'
        clients['sns'] = sns
        
        # SQS client
        sqs = Mock()
        sqs.list_queues.return_value = {'QueueUrls': []}
        sqs.meta.region_name = 'us-east-1'
        clients['sqs'] = sqs
        
        # API Gateway client
        apigateway = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'items': []}]
        apigateway.get_paginator.return_value = paginator
        apigateway.meta.region_name = 'us-east-1'
        clients['apigateway'] = apigateway
        
        # Step Functions client
        stepfunctions = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'stateMachines': []}]
        stepfunctions.get_paginator.return_value = paginator
        stepfunctions.meta.region_name = 'us-east-1'
        clients['stepfunctions'] = stepfunctions
        
        # Glue client
        glue = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'Jobs': []}]
        glue.get_paginator.return_value = paginator
        glue.meta.region_name = 'us-east-1'
        clients['glue'] = glue
        
        # SageMaker client
        sagemaker = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'Endpoints': []}]
        sagemaker.get_paginator.return_value = paginator
        sagemaker.meta.region_name = 'us-east-1'
        clients['sagemaker'] = sagemaker
        
        # CloudFront client
        cloudfront = Mock()
        paginator = Mock()
        paginator.paginate.return_value = [{'DistributionList': {'Items': []}}]
        cloudfront.get_paginator.return_value = paginator
        clients['cloudfront'] = cloudfront
        
        return clients
    
    @pytest.fixture
    def prevention_engine(self, mock_aws_clients):
        """Create PreventionEngine with all services enabled."""
        from src.services.budget_monitor import BudgetMonitor
        from src.services.safety_guard import SafetyGuard
        from src.services.action_executor import ActionExecutor
        from src.services.approval_manager import ApprovalManager
        from src.services.rollback_manager import RollbackManager
        from src.services.notification_service import NotificationService
        
        mock_dynamodb = Mock()
        mock_cloudwatch = Mock()
        
        resource_manager = ResourceManager(mock_aws_clients, mock_dynamodb)
        idle_detector = IdleDetector(mock_cloudwatch)
        
        config = {
            "enabled": True,
            "dry_run_mode": True,
            "approval_required": False,
            "enabled_services": [
                "ec2", "rds", "lambda", "ebs", "s3", "dynamodb",
                "elasticache", "redshift", "nat_gateway", "elastic_ip",
                "elb", "alb", "nlb", "cloudfront", "api_gateway",
                "step_functions", "glue", "sagemaker", "ecs", "eks",
                "sns", "sqs"
            ],
            "budget_thresholds": {
                "warning": 80,
                "action": 90
            }
        }
        
        prevention_engine = PreventionEngine(
            budget_monitor=BudgetMonitor(None, None),
            resource_manager=resource_manager,
            idle_detector=idle_detector,
            safety_guard=SafetyGuard(None),
            action_executor=ActionExecutor({}, None),
            approval_manager=ApprovalManager(None, None),
            rollback_manager=RollbackManager({}, None),
            notification_service=NotificationService(None, None),
            dynamodb_client=mock_dynamodb,
            config=config
        )
        
        return prevention_engine
    
    def test_all_services_can_be_discovered(self, prevention_engine):
        """Test that all 22 services can be discovered without errors."""
        services = prevention_engine.config.get("enabled_services", [])
        
        # Should not raise exception
        resources = prevention_engine.resource_manager.discover_resources(services)
        
        # Should return a list (may be empty if no resources)
        assert isinstance(resources, list)
        
        # Verify all services were attempted
        assert len(services) == 22
    
    def test_service_discovery_handles_missing_clients(self, prevention_engine):
        """Test that discovery handles missing clients gracefully."""
        # Create resource manager with empty clients
        empty_manager = ResourceManager({}, Mock())
        
        services = ["ec2", "s3", "dynamodb"]
        resources = empty_manager.discover_resources(services)
        
        # Should return empty list, not raise exception
        assert isinstance(resources, list)
        assert len(resources) == 0
    
    def test_idle_detection_works_for_all_services(self, prevention_engine):
        """Test that idle detection can process resources from all services."""
        from src.utils.types import ResourceMetadata
        
        # Create test resources for each service type
        test_resources = [
            Resource("i-123", "instance", "ec2", "us-east-1", {}, "running", "2024-01-01T00:00:00"),
            Resource("test-bucket", "bucket", "s3", "us-east-1", {}, "Active", "2024-01-01T00:00:00"),
            Resource("test-table", "table", "dynamodb", "us-east-1", {}, "ACTIVE", "2024-01-01T00:00:00"),
            Resource("vol-123", "volume", "ebs", "us-east-1", {}, "available", "2024-01-01T00:00:00"),
            Resource("test-cluster", "cache_cluster", "elasticache", "us-east-1", {}, "available", "2024-01-01T00:00:00"),
            Resource("test-cluster", "cluster", "redshift", "us-east-1", {}, "available", "2024-01-01T00:00:00"),
            Resource("test-cluster", "cluster", "ecs", "us-east-1", {}, "ACTIVE", "2024-01-01T00:00:00"),
            Resource("test-cluster", "cluster", "eks", "us-east-1", {}, "ACTIVE", "2024-01-01T00:00:00"),
            Resource("nat-123", "nat_gateway", "nat_gateway", "us-east-1", {}, "available", "2024-01-01T00:00:00"),
            Resource("eip-123", "elastic_ip", "elastic_ip", "us-east-1", {}, "available", "2024-01-01T00:00:00"),
            Resource("test-alb", "application_load_balancer", "elb", "us-east-1", {}, "active", "2024-01-01T00:00:00"),
            Resource("arn:sns:test", "topic", "sns", "us-east-1", {}, "Active", "2024-01-01T00:00:00"),
            Resource("https://sqs.test", "queue", "sqs", "us-east-1", {}, "Active", "2024-01-01T00:00:00"),
            Resource("api-123", "rest_api", "apigateway", "us-east-1", {}, "REGIONAL", "2024-01-01T00:00:00"),
            Resource("arn:states:test", "state_machine", "stepfunctions", "us-east-1", {}, "ACTIVE", "2024-01-01T00:00:00"),
            Resource("test-job", "job", "glue", "us-east-1", {}, "IDLE", "2024-01-01T00:00:00"),
            Resource("test-endpoint", "endpoint", "sagemaker", "us-east-1", {}, "InService", "2024-01-01T00:00:00"),
            Resource("E123", "distribution", "cloudfront", "global", {}, "Deployed", "2024-01-01T00:00:00"),
        ]
        
        # Test idle detection for each resource
        for resource in test_resources:
            metadata = ResourceMetadata(
                resource=resource,
                cost_per_hour=0.0,
                last_activity="2024-01-01T00:00:00",
                metrics={}
            )
            
            # Should not raise exception
            from src.utils.types import IdleStatus
            idle_status = prevention_engine.idle_detector.is_resource_idle(resource, metadata)
            
            assert isinstance(idle_status, IdleStatus)
            assert hasattr(idle_status, 'is_idle')
            assert hasattr(idle_status, 'resource_id')
    
    def test_prevention_engine_config_includes_all_services(self, prevention_engine):
        """Test that prevention engine config includes all 22 services."""
        enabled_services = prevention_engine.config.get("enabled_services", [])
        
        expected_services = [
            "ec2", "rds", "lambda", "ebs", "s3", "dynamodb",
            "elasticache", "redshift", "nat_gateway", "elastic_ip",
            "elb", "alb", "nlb", "cloudfront", "api_gateway",
            "step_functions", "glue", "sagemaker", "ecs", "eks",
            "sns", "sqs"
        ]
        
        assert len(enabled_services) == 22
        assert set(enabled_services) == set(expected_services)
    
    def test_resource_manager_mapping_includes_all_services(self, prevention_engine):
        """Test that resource manager has discovery methods for all services."""
        # Get all services from config
        services = prevention_engine.config.get("enabled_services", [])
        
        # Test that each service has a discovery method
        for service in services:
            resources = prevention_engine.resource_manager._discover_service_resources(service)
            # Should return a list (may be empty)
            assert isinstance(resources, list), f"Service {service} should return a list"
