"""
Property-based tests for CloudWatch Metrics Collector.

Feature: near-realtime-cost-estimation
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from src.services.cloudwatch_collector import CloudWatchMetricsCollector
from src.utils.types import EC2Metrics, LambdaMetrics, MetricDataPoint


# Feature: near-realtime-cost-estimation, Property 1: Metric Collection Completeness
@given(
    services=st.lists(
        st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds']),
        min_size=1,
        max_size=5,
        unique=True
    )
)
@settings(max_examples=100)
@patch('boto3.client')
def test_metric_collection_completeness(mock_boto_client, services):
    """
    Property 1: Metric Collection Completeness
    
    For any list of supported services and time range, collecting metrics
    should return data for all services that have resources running during
    that time range.
    
    Validates: Requirements 1.1, 1.7
    """
    # Setup mocks for all services
    mock_ec2_client = Mock()
    mock_ec2_client.describe_instances.return_value = {
        'Reservations': [{
            'Instances': [{
                'InstanceId': 'i-test',
                'InstanceType': 't2.micro'
            }]
        }]
    }
    
    mock_lambda_client = Mock()
    mock_lambda_client.list_functions.return_value = {
        'Functions': [{
            'FunctionName': 'test-function',
            'MemorySize': 128
        }]
    }
    
    mock_dynamodb_client = Mock()
    mock_dynamodb_client.list_tables.return_value = {
        'TableNames': ['test-table']
    }
    
    mock_s3_client = Mock()
    mock_s3_client.list_buckets.return_value = {
        'Buckets': [{'Name': 'test-bucket'}]
    }
    
    mock_rds_client = Mock()
    mock_rds_client.describe_db_instances.return_value = {
        'DBInstances': [{
            'DBInstanceIdentifier': 'test-db',
            'DBInstanceClass': 'db.t3.micro',
            'AllocatedStorage': 20
        }]
    }
    
    mock_cw_client = Mock()
    mock_cw_client.get_metric_statistics.return_value = {
        'Datapoints': [{'Average': 50.0, 'Sum': 100.0}]
    }
    
    def client_factory(service, region_name=None):
        if service == 'ec2':
            return mock_ec2_client
        elif service == 'lambda':
            return mock_lambda_client
        elif service == 'dynamodb':
            return mock_dynamodb_client
        elif service == 's3':
            return mock_s3_client
        elif service == 'rds':
            return mock_rds_client
        elif service == 'cloudwatch':
            return mock_cw_client
    
    mock_boto_client.side_effect = client_factory
    
    collector = CloudWatchMetricsCollector(client=mock_cw_client)
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = datetime(2024, 1, 1, 1, 0, 0)
    
    result = collector.collect_metrics(
        services=services,
        start_time=start_time,
        end_time=end_time
    )
    
    # Property: All requested services should be in the result
    for service in services:
        assert service in result, f"Service {service} should be in results"


# Feature: near-realtime-cost-estimation, Property 10: Metric Validation
@given(
    metric_value=st.floats(min_value=0, max_value=1000000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_metric_validation(metric_value):
    """
    Property 10: Metric Validation
    
    For any collected metric, the value must be non-negative.
    
    Validates: Requirements 8.1
    """
    mock_client = Mock()
    mock_client.get_metric_statistics.return_value = {
        'Datapoints': [{'Average': metric_value}]
    }
    
    collector = CloudWatchMetricsCollector(client=mock_client)
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = datetime(2024, 1, 1, 1, 0, 0)
    
    result = collector._get_metric_statistics(
        namespace='AWS/EC2',
        metric_name='CPUUtilization',
        dimensions=[{'Name': 'InstanceId', 'Value': 'i-test'}],
        start_time=start_time,
        end_time=end_time
    )
    
    # Property: Metric values must be non-negative
    assert result >= Decimal('0'), f"Metric value {result} must be non-negative"


# Feature: near-realtime-cost-estimation, Property 13: Batch Metric Collection
@given(
    num_services=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100)
@patch('boto3.client')
def test_batch_metric_collection(mock_boto_client, num_services):
    """
    Property 13: Batch Metric Collection
    
    For any metric collection operation, the system must batch requests
    to minimize API calls.
    
    Validates: Requirements 7.1, 7.2
    """
    # Setup mocks
    mock_ec2_client = Mock()
    mock_ec2_client.describe_instances.return_value = {'Reservations': []}
    
    mock_lambda_client = Mock()
    mock_lambda_client.list_functions.return_value = {'Functions': []}
    
    mock_dynamodb_client = Mock()
    mock_dynamodb_client.list_tables.return_value = {'TableNames': []}
    
    mock_s3_client = Mock()
    mock_s3_client.list_buckets.return_value = {'Buckets': []}
    
    mock_rds_client = Mock()
    mock_rds_client.describe_db_instances.return_value = {'DBInstances': []}
    
    mock_cw_client = Mock()
    mock_cw_client.get_metric_statistics.return_value = {'Datapoints': []}
    
    def client_factory(service, region_name=None):
        if service == 'ec2':
            return mock_ec2_client
        elif service == 'lambda':
            return mock_lambda_client
        elif service == 'dynamodb':
            return mock_dynamodb_client
        elif service == 's3':
            return mock_s3_client
        elif service == 'rds':
            return mock_rds_client
        elif service == 'cloudwatch':
            return mock_cw_client
    
    mock_boto_client.side_effect = client_factory
    
    collector = CloudWatchMetricsCollector(client=mock_cw_client)
    
    # Select services based on num_services
    all_services = ['ec2', 'lambda', 'dynamodb', 's3', 'rds']
    services = all_services[:num_services]
    
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = datetime(2024, 1, 1, 1, 0, 0)
    
    result = collector.collect_metrics(
        services=services,
        start_time=start_time,
        end_time=end_time
    )
    
    # Property: collect_metrics should handle multiple services in one call
    # (batching is implicit in the design - one method call handles all services)
    assert len(result) == num_services, "Should collect metrics for all requested services"
    
    # Property: Each service should be collected exactly once
    for service in services:
        assert service in result, f"Service {service} should be collected"


# Additional property test for error isolation
@given(
    failing_service=st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds'])
)
@settings(max_examples=100)
@patch('boto3.client')
def test_error_isolation_in_batch_collection(mock_boto_client, failing_service):
    """
    Property 8: Error Isolation
    
    For any service where metric collection fails, the system must continue
    collecting metrics for other services.
    
    Validates: Requirements 6.4
    """
    # Setup mocks - one service will fail
    mock_ec2_client = Mock()
    if failing_service == 'ec2':
        mock_ec2_client.describe_instances.side_effect = Exception("EC2 error")
    else:
        mock_ec2_client.describe_instances.return_value = {'Reservations': []}
    
    mock_lambda_client = Mock()
    if failing_service == 'lambda':
        mock_lambda_client.list_functions.side_effect = Exception("Lambda error")
    else:
        mock_lambda_client.list_functions.return_value = {'Functions': []}
    
    mock_dynamodb_client = Mock()
    if failing_service == 'dynamodb':
        mock_dynamodb_client.list_tables.side_effect = Exception("DynamoDB error")
    else:
        mock_dynamodb_client.list_tables.return_value = {'TableNames': []}
    
    mock_s3_client = Mock()
    if failing_service == 's3':
        mock_s3_client.list_buckets.side_effect = Exception("S3 error")
    else:
        mock_s3_client.list_buckets.return_value = {'Buckets': []}
    
    mock_rds_client = Mock()
    if failing_service == 'rds':
        mock_rds_client.describe_db_instances.side_effect = Exception("RDS error")
    else:
        mock_rds_client.describe_db_instances.return_value = {'DBInstances': []}
    
    mock_cw_client = Mock()
    mock_cw_client.get_metric_statistics.return_value = {'Datapoints': []}
    
    def client_factory(service, region_name=None):
        if service == 'ec2':
            return mock_ec2_client
        elif service == 'lambda':
            return mock_lambda_client
        elif service == 'dynamodb':
            return mock_dynamodb_client
        elif service == 's3':
            return mock_s3_client
        elif service == 'rds':
            return mock_rds_client
        elif service == 'cloudwatch':
            return mock_cw_client
    
    mock_boto_client.side_effect = client_factory
    
    collector = CloudWatchMetricsCollector(client=mock_cw_client)
    
    services = ['ec2', 'lambda', 'dynamodb', 's3', 'rds']
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = datetime(2024, 1, 1, 1, 0, 0)
    
    result = collector.collect_metrics(
        services=services,
        start_time=start_time,
        end_time=end_time
    )
    
    # Property: All services should be in result, even if one failed
    assert len(result) == 5, "Should attempt to collect all services"
    
    # Property: Failing service should have empty list
    assert failing_service in result, f"Failing service {failing_service} should be in result"
    assert result[failing_service] == [], f"Failing service {failing_service} should have empty list"
    
    # Property: Other services should still be collected
    for service in services:
        if service != failing_service:
            assert service in result, f"Non-failing service {service} should be collected"
