"""
Unit tests for IdleDetector.

Tests idle detection logic for all supported services.
"""

import pytest
from unittest.mock import Mock
from src.services.idle_detector import IdleDetector
from src.utils.types import Resource, ResourceMetadata, IdleStatus, IdleCriteria


class TestIdleDetector:
    """Test IdleDetector class."""
    
    @pytest.fixture
    def mock_cloudwatch(self):
        """Create mock CloudWatch client."""
        return Mock()
    
    @pytest.fixture
    def idle_detector(self, mock_cloudwatch):
        """Create IdleDetector instance."""
        return IdleDetector(mock_cloudwatch)
    
    @pytest.fixture
    def ec2_resource(self):
        """Create EC2 resource."""
        return Resource(
            resource_id='i-1234567890abcdef0',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
    
    @pytest.fixture
    def rds_resource(self):
        """Create RDS resource."""
        return Resource(
            resource_id='test-db',
            resource_type='db_instance',
            service='rds',
            region='us-east-1',
            tags={},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
    
    def test_initialization(self, idle_detector):
        """Test IdleDetector initialization."""
        assert idle_detector.cloudwatch is not None
        assert 'ec2' in idle_detector.idle_criteria
        assert 'rds' in idle_detector.idle_criteria
        assert 'lambda' in idle_detector.idle_criteria
        assert 'ebs' in idle_detector.idle_criteria
        assert 's3' in idle_detector.idle_criteria
        assert 'dynamodb' in idle_detector.idle_criteria
    
    def test_get_idle_criteria_ec2(self, idle_detector):
        """Test getting idle criteria for EC2."""
        criteria = idle_detector.get_idle_criteria('ec2')
        
        assert isinstance(criteria, IdleCriteria)
        assert criteria.service == 'ec2'
        assert criteria.metric_name == 'CPUUtilization'
        assert criteria.threshold == 5.0
        assert criteria.duration_minutes == 120
    
    def test_get_idle_criteria_rds(self, idle_detector):
        """Test getting idle criteria for RDS."""
        criteria = idle_detector.get_idle_criteria('rds')
        
        assert isinstance(criteria, IdleCriteria)
        assert criteria.service == 'rds'
        assert criteria.metric_name == 'DatabaseConnections'
        assert criteria.threshold == 0.0
        assert criteria.duration_minutes == 60
    
    def test_get_idle_criteria_lambda(self, idle_detector):
        """Test getting idle criteria for Lambda."""
        criteria = idle_detector.get_idle_criteria('lambda')
        
        assert isinstance(criteria, IdleCriteria)
        assert criteria.service == 'lambda'
        assert criteria.metric_name == 'Invocations'
        assert criteria.threshold == 0.0
        assert criteria.duration_minutes == 1440
    
    def test_get_idle_criteria_unknown_service(self, idle_detector):
        """Test getting idle criteria for unknown service."""
        criteria = idle_detector.get_idle_criteria('unknown')
        
        assert criteria is None
    
    def test_check_ec2_idle_low_cpu(self, idle_detector, ec2_resource):
        """Test EC2 idle detection with low CPU."""
        metadata = ResourceMetadata(
            resource=ec2_resource,
            cost_per_hour=0.10,
            last_activity='2024-01-01T12:00:00',
            metrics={'CPUUtilization': 2.5}
        )
        
        status = idle_detector._check_ec2_idle(
            ec2_resource,
            metadata,
            idle_detector.get_idle_criteria('ec2')
        )
        
        assert isinstance(status, IdleStatus)
        assert status.is_idle is True
        assert status.idle_duration == 120
        assert status.metrics_used['CPUUtilization'] == 2.5
        assert status.confidence == 0.95
    
    def test_check_ec2_idle_high_cpu(self, idle_detector, ec2_resource):
        """Test EC2 idle detection with high CPU."""
        metadata = ResourceMetadata(
            resource=ec2_resource,
            cost_per_hour=0.10,
            last_activity='2024-01-01T12:00:00',
            metrics={'CPUUtilization': 75.0}
        )
        
        status = idle_detector._check_ec2_idle(
            ec2_resource,
            metadata,
            idle_detector.get_idle_criteria('ec2')
        )
        
        assert status.is_idle is False
        assert status.idle_duration == 0
        assert status.confidence == 0.0
    
    def test_check_ec2_idle_at_threshold(self, idle_detector, ec2_resource):
        """Test EC2 idle detection at exact threshold."""
        metadata = ResourceMetadata(
            resource=ec2_resource,
            cost_per_hour=0.10,
            last_activity='2024-01-01T12:00:00',
            metrics={'CPUUtilization': 5.0}
        )
        
        status = idle_detector._check_ec2_idle(
            ec2_resource,
            metadata,
            idle_detector.get_idle_criteria('ec2')
        )
        
        # At threshold should not be idle (< not <=)
        assert status.is_idle is False
    
    def test_check_rds_idle_no_connections(self, idle_detector, rds_resource):
        """Test RDS idle detection with no connections."""
        metadata = ResourceMetadata(
            resource=rds_resource,
            cost_per_hour=0.20,
            last_activity='2024-01-01T12:00:00',
            metrics={'DatabaseConnections': 0.0}
        )
        
        status = idle_detector._check_rds_idle(
            rds_resource,
            metadata,
            idle_detector.get_idle_criteria('rds')
        )
        
        assert status.is_idle is True
        assert status.idle_duration == 60
        assert status.metrics_used['DatabaseConnections'] == 0.0
        assert status.confidence == 0.90
    
    def test_check_rds_idle_with_connections(self, idle_detector, rds_resource):
        """Test RDS idle detection with active connections."""
        metadata = ResourceMetadata(
            resource=rds_resource,
            cost_per_hour=0.20,
            last_activity='2024-01-01T12:00:00',
            metrics={'DatabaseConnections': 5.0}
        )
        
        status = idle_detector._check_rds_idle(
            rds_resource,
            metadata,
            idle_detector.get_idle_criteria('rds')
        )
        
        assert status.is_idle is False
        assert status.idle_duration == 0
    
    def test_check_lambda_idle_no_invocations(self, idle_detector):
        """Test Lambda idle detection with no invocations."""
        lambda_resource = Resource(
            resource_id='arn:aws:lambda:us-east-1:123456789012:function:test',
            resource_type='function',
            service='lambda',
            region='us-east-1',
            tags={},
            state='Active',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=lambda_resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={'Invocations': 0.0}
        )
        
        status = idle_detector._check_lambda_idle(
            lambda_resource,
            metadata,
            idle_detector.get_idle_criteria('lambda')
        )
        
        assert status.is_idle is True
        assert status.idle_duration == 1440
        assert status.confidence == 0.85
    
    def test_check_lambda_idle_with_invocations(self, idle_detector):
        """Test Lambda idle detection with invocations."""
        lambda_resource = Resource(
            resource_id='arn:aws:lambda:us-east-1:123456789012:function:test',
            resource_type='function',
            service='lambda',
            region='us-east-1',
            tags={},
            state='Active',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=lambda_resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={'Invocations': 100.0}
        )
        
        status = idle_detector._check_lambda_idle(
            lambda_resource,
            metadata,
            idle_detector.get_idle_criteria('lambda')
        )
        
        assert status.is_idle is False
    
    def test_check_ebs_idle_unattached(self, idle_detector):
        """Test EBS idle detection for unattached volume."""
        ebs_resource = Resource(
            resource_id='vol-1234567890abcdef0',
            resource_type='volume',
            service='ebs',
            region='us-east-1',
            tags={},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=ebs_resource,
            cost_per_hour=0.05,
            last_activity='2024-01-01T12:00:00',
            metrics={}
        )
        
        status = idle_detector._check_ebs_idle(
            ebs_resource,
            metadata,
            idle_detector.get_idle_criteria('ebs')
        )
        
        assert status.is_idle is True
        assert status.idle_duration == 10080  # 7 days
        assert status.confidence == 1.0
    
    def test_check_ebs_idle_attached(self, idle_detector):
        """Test EBS idle detection for attached volume."""
        ebs_resource = Resource(
            resource_id='vol-1234567890abcdef0',
            resource_type='volume',
            service='ebs',
            region='us-east-1',
            tags={},
            state='in-use',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=ebs_resource,
            cost_per_hour=0.05,
            last_activity='2024-01-01T12:00:00',
            metrics={}
        )
        
        status = idle_detector._check_ebs_idle(
            ebs_resource,
            metadata,
            idle_detector.get_idle_criteria('ebs')
        )
        
        assert status.is_idle is False
        assert status.idle_duration == 0
    
    def test_check_s3_idle_no_requests(self, idle_detector):
        """Test S3 idle detection with no requests."""
        s3_resource = Resource(
            resource_id='my-bucket',
            resource_type='bucket',
            service='s3',
            region='us-east-1',
            tags={},
            state='active',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=s3_resource,
            cost_per_hour=0.01,
            last_activity='2024-01-01T12:00:00',
            metrics={'AllRequests': 0.0}
        )
        
        status = idle_detector._check_s3_idle(
            s3_resource,
            metadata,
            idle_detector.get_idle_criteria('s3')
        )
        
        assert status.is_idle is True
        assert status.idle_duration == 43200  # 30 days
        assert status.confidence == 0.80
    
    def test_check_s3_idle_with_requests(self, idle_detector):
        """Test S3 idle detection with requests."""
        s3_resource = Resource(
            resource_id='my-bucket',
            resource_type='bucket',
            service='s3',
            region='us-east-1',
            tags={},
            state='active',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=s3_resource,
            cost_per_hour=0.01,
            last_activity='2024-01-01T12:00:00',
            metrics={'AllRequests': 1000.0}
        )
        
        status = idle_detector._check_s3_idle(
            s3_resource,
            metadata,
            idle_detector.get_idle_criteria('s3')
        )
        
        assert status.is_idle is False
    
    def test_check_dynamodb_idle_no_activity(self, idle_detector):
        """Test DynamoDB idle detection with no activity."""
        dynamodb_resource = Resource(
            resource_id='my-table',
            resource_type='table',
            service='dynamodb',
            region='us-east-1',
            tags={},
            state='ACTIVE',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=dynamodb_resource,
            cost_per_hour=0.15,
            last_activity='2024-01-01T12:00:00',
            metrics={
                'ConsumedReadCapacityUnits': 0.0,
                'ConsumedWriteCapacityUnits': 0.0
            }
        )
        
        status = idle_detector._check_dynamodb_idle(
            dynamodb_resource,
            metadata,
            idle_detector.get_idle_criteria('dynamodb')
        )
        
        assert status.is_idle is True
        assert status.idle_duration == 1440  # 24 hours
        assert status.confidence == 0.85
    
    def test_check_dynamodb_idle_with_reads(self, idle_detector):
        """Test DynamoDB idle detection with read activity."""
        dynamodb_resource = Resource(
            resource_id='my-table',
            resource_type='table',
            service='dynamodb',
            region='us-east-1',
            tags={},
            state='ACTIVE',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=dynamodb_resource,
            cost_per_hour=0.15,
            last_activity='2024-01-01T12:00:00',
            metrics={
                'ConsumedReadCapacityUnits': 10.0,
                'ConsumedWriteCapacityUnits': 0.0
            }
        )
        
        status = idle_detector._check_dynamodb_idle(
            dynamodb_resource,
            metadata,
            idle_detector.get_idle_criteria('dynamodb')
        )
        
        assert status.is_idle is False
    
    def test_check_dynamodb_idle_with_writes(self, idle_detector):
        """Test DynamoDB idle detection with write activity."""
        dynamodb_resource = Resource(
            resource_id='my-table',
            resource_type='table',
            service='dynamodb',
            region='us-east-1',
            tags={},
            state='ACTIVE',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=dynamodb_resource,
            cost_per_hour=0.15,
            last_activity='2024-01-01T12:00:00',
            metrics={
                'ConsumedReadCapacityUnits': 0.0,
                'ConsumedWriteCapacityUnits': 5.0
            }
        )
        
        status = idle_detector._check_dynamodb_idle(
            dynamodb_resource,
            metadata,
            idle_detector.get_idle_criteria('dynamodb')
        )
        
        assert status.is_idle is False
    
    def test_is_resource_idle_unknown_service(self, idle_detector):
        """Test idle detection for unknown service."""
        unknown_resource = Resource(
            resource_id='unknown-123',
            resource_type='unknown',
            service='unknown',
            region='us-east-1',
            tags={},
            state='active',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=unknown_resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={}
        )
        
        status = idle_detector.is_resource_idle(unknown_resource, metadata)
        
        assert status.is_idle is False
        assert status.idle_duration == 0
        assert status.confidence == 0.0
    
    def test_is_resource_idle_ec2(self, idle_detector, ec2_resource):
        """Test is_resource_idle for EC2."""
        metadata = ResourceMetadata(
            resource=ec2_resource,
            cost_per_hour=0.10,
            last_activity='2024-01-01T12:00:00',
            metrics={'CPUUtilization': 1.0}
        )
        
        status = idle_detector.is_resource_idle(ec2_resource, metadata)
        
        assert isinstance(status, IdleStatus)
        assert status.is_idle is True
    
    def test_is_resource_idle_rds(self, idle_detector, rds_resource):
        """Test is_resource_idle for RDS."""
        metadata = ResourceMetadata(
            resource=rds_resource,
            cost_per_hour=0.20,
            last_activity='2024-01-01T12:00:00',
            metrics={'DatabaseConnections': 0.0}
        )
        
        status = idle_detector.is_resource_idle(rds_resource, metadata)
        
        assert isinstance(status, IdleStatus)
        assert status.is_idle is True
    
    def test_check_generic_idle(self, idle_detector):
        """Test generic idle check for unsupported service."""
        resource = Resource(
            resource_id='test-123',
            resource_type='test',
            service='test',
            region='us-east-1',
            tags={},
            state='active',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={}
        )
        
        criteria = IdleCriteria(
            service='test',
            metric_name='TestMetric',
            threshold=0.0,
            duration_minutes=60
        )
        
        status = idle_detector._check_generic_idle(resource, metadata, criteria)
        
        assert status.is_idle is False
        assert status.idle_duration == 0
        assert status.confidence == 0.0
    
    def test_ec2_idle_missing_metrics(self, idle_detector, ec2_resource):
        """Test EC2 idle detection with missing metrics."""
        metadata = ResourceMetadata(
            resource=ec2_resource,
            cost_per_hour=0.10,
            last_activity='2024-01-01T12:00:00',
            metrics={}  # No CPUUtilization metric
        )
        
        status = idle_detector._check_ec2_idle(
            ec2_resource,
            metadata,
            idle_detector.get_idle_criteria('ec2')
        )
        
        # Should default to 100.0 (not idle)
        assert status.is_idle is False
        assert status.metrics_used['CPUUtilization'] == 100.0
    
    # Tests for new services - ElastiCache, Redshift, ECS, EKS
    def test_check_elasticache_idle(self, idle_detector):
        """Test ElastiCache idle detection."""
        resource = Resource(
            resource_id='test-cluster',
            resource_type='cache_cluster',
            service='elasticache',
            region='us-east-1',
            tags={},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.10,
            last_activity='2024-01-01T12:00:00',
            metrics={'CPUUtilization': 3.0}  # Below 5% threshold
        )
        
        status = idle_detector._check_elasticache_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('elasticache')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.90
    
    def test_check_redshift_idle(self, idle_detector):
        """Test Redshift idle detection."""
        resource = Resource(
            resource_id='test-cluster',
            resource_type='cluster',
            service='redshift',
            region='us-east-1',
            tags={},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.50,
            last_activity='2024-01-01T12:00:00',
            metrics={'DatabaseConnections': 0.0}
        )
        
        status = idle_detector._check_redshift_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('redshift')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.90
    
    def test_check_ecs_idle(self, idle_detector):
        """Test ECS idle detection."""
        resource = Resource(
            resource_id='test-cluster',
            resource_type='cluster',
            service='ecs',
            region='us-east-1',
            tags={},
            state='ACTIVE',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.20,
            last_activity='2024-01-01T12:00:00',
            metrics={'RunningTaskCount': 0.0}
        )
        
        status = idle_detector._check_ecs_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('ecs')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.85
    
    def test_check_eks_idle(self, idle_detector):
        """Test EKS idle detection."""
        resource = Resource(
            resource_id='test-cluster',
            resource_type='cluster',
            service='eks',
            region='us-east-1',
            tags={},
            state='ACTIVE',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.30,
            last_activity='2024-01-01T12:00:00',
            metrics={'ActivePodCount': 0.0}
        )
        
        status = idle_detector._check_eks_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('eks')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.85
    
    # Tests for NAT Gateway, Elastic IP, Load Balancers
    def test_check_nat_gateway_idle(self, idle_detector):
        """Test NAT Gateway idle detection."""
        resource = Resource(
            resource_id='nat-1234567890abcdef0',
            resource_type='nat_gateway',
            service='nat_gateway',
            region='us-east-1',
            tags={},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.045,
            last_activity='2024-01-01T12:00:00',
            metrics={
                'BytesOutToDestination': 0.0,
                'BytesInFromSource': 0.0
            }
        )
        
        status = idle_detector._check_nat_gateway_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('nat_gateway')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.85
    
    def test_check_elastic_ip_idle(self, idle_detector):
        """Test Elastic IP idle detection."""
        resource = Resource(
            resource_id='eipalloc-1234567890abcdef0',
            resource_type='elastic_ip',
            service='elastic_ip',
            region='us-east-1',
            tags={},
            state='available',  # Unattached
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.005,
            last_activity='2024-01-01T12:00:00',
            metrics={}
        )
        
        status = idle_detector._check_elastic_ip_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('elastic_ip')
        )
        
        assert status.is_idle is True
        assert status.confidence == 1.0
    
    def test_check_load_balancer_idle(self, idle_detector):
        """Test Load Balancer idle detection."""
        resource = Resource(
            resource_id='test-alb',
            resource_type='application_load_balancer',
            service='elb',
            region='us-east-1',
            tags={},
            state='active',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.0225,
            last_activity='2024-01-01T12:00:00',
            metrics={
                'RequestCount': 0.0,
                'ActiveFlowCount': 0.0
            }
        )
        
        status = idle_detector._check_load_balancer_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('elb')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.80
    
    # Tests for SNS, SQS, API Gateway, Step Functions
    def test_check_sns_idle(self, idle_detector):
        """Test SNS idle detection."""
        resource = Resource(
            resource_id='arn:aws:sns:us-east-1:123456789012:test-topic',
            resource_type='topic',
            service='sns',
            region='us-east-1',
            tags={},
            state='Active',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={'NumberOfMessagesPublished': 0.0}
        )
        
        status = idle_detector._check_sns_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('sns')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.85
    
    def test_check_sqs_idle(self, idle_detector):
        """Test SQS idle detection."""
        resource = Resource(
            resource_id='https://sqs.us-east-1.amazonaws.com/123456789012/test-queue',
            resource_type='queue',
            service='sqs',
            region='us-east-1',
            tags={},
            state='Active',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={'NumberOfMessagesSent': 0.0}
        )
        
        status = idle_detector._check_sqs_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('sqs')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.85
    
    def test_check_apigateway_idle(self, idle_detector):
        """Test API Gateway idle detection."""
        resource = Resource(
            resource_id='abc123',
            resource_type='rest_api',
            service='apigateway',
            region='us-east-1',
            tags={},
            state='REGIONAL',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={'Count': 0.0}
        )
        
        status = idle_detector._check_apigateway_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('apigateway')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.85
    
    def test_check_stepfunctions_idle(self, idle_detector):
        """Test Step Functions idle detection."""
        resource = Resource(
            resource_id='arn:aws:states:us-east-1:123456789012:stateMachine:test-sm',
            resource_type='state_machine',
            service='stepfunctions',
            region='us-east-1',
            tags={},
            state='ACTIVE',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={'ExecutionsStarted': 0.0}
        )
        
        status = idle_detector._check_stepfunctions_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('stepfunctions')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.85
    
    # Tests for Glue, SageMaker, CloudFront
    def test_check_glue_idle(self, idle_detector):
        """Test Glue idle detection."""
        resource = Resource(
            resource_id='test-job',
            resource_type='job',
            service='glue',
            region='us-east-1',
            tags={},
            state='IDLE',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={'JobRuns': 0.0}
        )
        
        status = idle_detector._check_glue_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('glue')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.80
    
    def test_check_sagemaker_idle(self, idle_detector):
        """Test SageMaker idle detection."""
        resource = Resource(
            resource_id='test-endpoint',
            resource_type='endpoint',
            service='sagemaker',
            region='us-east-1',
            tags={},
            state='InService',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.50,
            last_activity='2024-01-01T12:00:00',
            metrics={'Invocations': 0.0}
        )
        
        status = idle_detector._check_sagemaker_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('sagemaker')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.85
    
    def test_check_cloudfront_idle(self, idle_detector):
        """Test CloudFront idle detection."""
        resource = Resource(
            resource_id='E1234567890ABC',
            resource_type='distribution',
            service='cloudfront',
            region='global',
            tags={},
            state='Deployed',
            creation_date='2024-01-01T12:00:00'
        )
        
        metadata = ResourceMetadata(
            resource=resource,
            cost_per_hour=0.0,
            last_activity='2024-01-01T12:00:00',
            metrics={'Requests': 0.0}
        )
        
        status = idle_detector._check_cloudfront_idle(
            resource,
            metadata,
            idle_detector.get_idle_criteria('cloudfront')
        )
        
        assert status.is_idle is True
        assert status.confidence == 0.80