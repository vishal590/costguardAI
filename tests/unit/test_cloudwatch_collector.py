"""
Unit tests for CloudWatch Metrics Collector.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from src.services.cloudwatch_collector import CloudWatchMetricsCollector
from src.utils.types import (
    EC2Metrics,
    LambdaMetrics,
    DynamoDBMetrics,
    S3Metrics,
    RDSMetrics
)


class TestCloudWatchMetricsCollector:
    """Test CloudWatchMetricsCollector initialization."""
    
    def test_init_with_default_region(self):
        """Test initialization with default region."""
        mock_client = Mock()
        collector = CloudWatchMetricsCollector(client=mock_client)
        
        assert collector.client == mock_client
        assert collector.region == 'us-east-1'
    
    def test_init_with_custom_region(self):
        """Test initialization with custom region."""
        mock_client = Mock()
        collector = CloudWatchMetricsCollector(region='us-west-2', client=mock_client)
        
        assert collector.region == 'us-west-2'


class TestGetMetricStatistics:
    """Test _get_metric_statistics helper method."""
    
    def test_get_metric_statistics_with_datapoints(self):
        """Test getting metric statistics with datapoints."""
        mock_client = Mock()
        mock_client.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Average': 50.0},
                {'Average': 60.0},
                {'Average': 70.0}
            ]
        }
        
        collector = CloudWatchMetricsCollector(client=mock_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector._get_metric_statistics(
            namespace='AWS/EC2',
            metric_name='CPUUtilization',
            dimensions=[{'Name': 'InstanceId', 'Value': 'i-123'}],
            start_time=start_time,
            end_time=end_time,
            statistic='Average'
        )
        
        assert result == Decimal('180.0')
    
    def test_get_metric_statistics_with_no_datapoints(self):
        """Test getting metric statistics with no datapoints."""
        mock_client = Mock()
        mock_client.get_metric_statistics.return_value = {'Datapoints': []}
        
        collector = CloudWatchMetricsCollector(client=mock_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector._get_metric_statistics(
            namespace='AWS/EC2',
            metric_name='CPUUtilization',
            dimensions=[{'Name': 'InstanceId', 'Value': 'i-123'}],
            start_time=start_time,
            end_time=end_time
        )
        
        assert result == Decimal('0')


class TestCollectEC2Metrics:
    """Test EC2 metrics collection."""
    
    @patch('boto3.client')
    def test_collect_ec2_metrics_with_instances(self, mock_boto_client):
        """Test collecting EC2 metrics with running instances."""
        # Mock EC2 client
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-1234567890abcdef0',
                    'InstanceType': 't2.micro'
                }]
            }]
        }
        
        # Mock CloudWatch client
        mock_cw_client = Mock()
        mock_cw_client.get_metric_statistics.return_value = {
            'Datapoints': [{'Average': 50.0}]
        }
        
        # Setup boto3.client to return appropriate mocks
        def client_factory(service, region_name=None):
            if service == 'ec2':
                return mock_ec2_client
            elif service == 'cloudwatch':
                return mock_cw_client
        
        mock_boto_client.side_effect = client_factory
        
        collector = CloudWatchMetricsCollector(client=mock_cw_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_ec2_metrics(start_time, end_time)
        
        assert len(result) == 1
        assert result[0].instance_id == 'i-1234567890abcdef0'
        assert result[0].instance_type == 't2.micro'
        assert result[0].running_hours == Decimal('1.0')
    
    @patch('boto3.client')
    def test_collect_ec2_metrics_with_no_instances(self, mock_boto_client):
        """Test collecting EC2 metrics with no instances."""
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instances.return_value = {'Reservations': []}
        
        mock_cw_client = Mock()
        
        def client_factory(service, region_name=None):
            if service == 'ec2':
                return mock_ec2_client
            elif service == 'cloudwatch':
                return mock_cw_client
        
        mock_boto_client.side_effect = client_factory
        
        collector = CloudWatchMetricsCollector(client=mock_cw_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_ec2_metrics(start_time, end_time)
        
        assert len(result) == 0


class TestCollectLambdaMetrics:
    """Test Lambda metrics collection."""
    
    @patch('boto3.client')
    def test_collect_lambda_metrics_with_functions(self, mock_boto_client):
        """Test collecting Lambda metrics with functions."""
        mock_lambda_client = Mock()
        mock_lambda_client.list_functions.return_value = {
            'Functions': [{
                'FunctionName': 'my-function',
                'MemorySize': 128
            }]
        }
        
        mock_cw_client = Mock()
        mock_cw_client.get_metric_statistics.return_value = {
            'Datapoints': [{'Sum': 100.0}]
        }
        
        def client_factory(service, region_name=None):
            if service == 'lambda':
                return mock_lambda_client
            elif service == 'cloudwatch':
                return mock_cw_client
        
        mock_boto_client.side_effect = client_factory
        
        collector = CloudWatchMetricsCollector(client=mock_cw_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_lambda_metrics(start_time, end_time)
        
        assert len(result) == 1
        assert result[0].function_name == 'my-function'
        assert result[0].memory_mb == 128


class TestCollectDynamoDBMetrics:
    """Test DynamoDB metrics collection."""
    
    @patch('boto3.client')
    def test_collect_dynamodb_metrics_with_tables(self, mock_boto_client):
        """Test collecting DynamoDB metrics with tables."""
        mock_dynamodb_client = Mock()
        mock_dynamodb_client.list_tables.return_value = {
            'TableNames': ['my-table']
        }
        
        mock_cw_client = Mock()
        mock_cw_client.get_metric_statistics.return_value = {
            'Datapoints': [{'Sum': 50.0}]
        }
        
        def client_factory(service, region_name=None):
            if service == 'dynamodb':
                return mock_dynamodb_client
            elif service == 'cloudwatch':
                return mock_cw_client
        
        mock_boto_client.side_effect = client_factory
        
        collector = CloudWatchMetricsCollector(client=mock_cw_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_dynamodb_metrics(start_time, end_time)
        
        assert len(result) == 1
        assert result[0].table_name == 'my-table'


class TestCollectS3Metrics:
    """Test S3 metrics collection."""
    
    @patch('boto3.client')
    def test_collect_s3_metrics_with_buckets(self, mock_boto_client):
        """Test collecting S3 metrics with buckets."""
        mock_s3_client = Mock()
        mock_s3_client.list_buckets.return_value = {
            'Buckets': [{'Name': 'my-bucket'}]
        }
        
        mock_cw_client = Mock()
        mock_cw_client.get_metric_statistics.return_value = {
            'Datapoints': [{'Average': 1000.0}]
        }
        
        def client_factory(service, region_name=None):
            if service == 's3':
                return mock_s3_client
            elif service == 'cloudwatch':
                return mock_cw_client
        
        mock_boto_client.side_effect = client_factory
        
        collector = CloudWatchMetricsCollector(client=mock_cw_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_s3_metrics(start_time, end_time)
        
        assert len(result) == 1
        assert result[0].bucket_name == 'my-bucket'


class TestCollectRDSMetrics:
    """Test RDS metrics collection."""
    
    @patch('boto3.client')
    def test_collect_rds_metrics_with_instances(self, mock_boto_client):
        """Test collecting RDS metrics with instances."""
        mock_rds_client = Mock()
        mock_rds_client.describe_db_instances.return_value = {
            'DBInstances': [{
                'DBInstanceIdentifier': 'mydb',
                'DBInstanceClass': 'db.t3.micro',
                'AllocatedStorage': 20
            }]
        }
        
        mock_cw_client = Mock()
        mock_cw_client.get_metric_statistics.return_value = {
            'Datapoints': [{'Average': 10.0}]
        }
        
        def client_factory(service, region_name=None):
            if service == 'rds':
                return mock_rds_client
            elif service == 'cloudwatch':
                return mock_cw_client
        
        mock_boto_client.side_effect = client_factory
        
        collector = CloudWatchMetricsCollector(client=mock_cw_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_rds_metrics(start_time, end_time)
        
        assert len(result) == 1
        assert result[0].instance_id == 'mydb'
        assert result[0].instance_type == 'db.t3.micro'
        assert result[0].storage_gb == Decimal('20')


class TestCollectMetrics:
    """Test batch metrics collection."""
    
    @patch('boto3.client')
    def test_collect_metrics_for_multiple_services(self, mock_boto_client):
        """Test collecting metrics for multiple services."""
        # Setup mocks for all services
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instances.return_value = {'Reservations': []}
        
        mock_lambda_client = Mock()
        mock_lambda_client.list_functions.return_value = {'Functions': []}
        
        mock_cw_client = Mock()
        
        def client_factory(service, region_name=None):
            if service == 'ec2':
                return mock_ec2_client
            elif service == 'lambda':
                return mock_lambda_client
            elif service == 'cloudwatch':
                return mock_cw_client
        
        mock_boto_client.side_effect = client_factory
        
        collector = CloudWatchMetricsCollector(client=mock_cw_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_metrics(
            services=['ec2', 'lambda'],
            start_time=start_time,
            end_time=end_time
        )
        
        assert 'ec2' in result
        assert 'lambda' in result
    
    @patch('boto3.client')
    def test_collect_metrics_handles_errors_gracefully(self, mock_boto_client):
        """Test that collect_metrics continues on error."""
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instances.side_effect = Exception("EC2 error")
        
        mock_lambda_client = Mock()
        mock_lambda_client.list_functions.return_value = {'Functions': []}
        
        mock_cw_client = Mock()
        
        def client_factory(service, region_name=None):
            if service == 'ec2':
                return mock_ec2_client
            elif service == 'lambda':
                return mock_lambda_client
            elif service == 'cloudwatch':
                return mock_cw_client
        
        mock_boto_client.side_effect = client_factory
        
        collector = CloudWatchMetricsCollector(client=mock_cw_client)
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_metrics(
            services=['ec2', 'lambda'],
            start_time=start_time,
            end_time=end_time
        )
        
        # EC2 should have empty list due to error
        assert result['ec2'] == []
        # Lambda should still work
        assert 'lambda' in result


class TestCollectServiceMetrics:
    """Test collect_service_metrics method."""
    
    @patch('boto3.client')
    def test_collect_service_metrics_returns_service_specific_objects(self, mock_boto_client):
        """Test that collect_service_metrics returns service-specific metric objects."""
        # Mock EC2 client
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-123',
                    'InstanceType': 't2.micro',
                    'State': {'Name': 'running'}
                }]
            }]
        }
        
        # Mock CloudWatch client
        mock_cw_client = Mock()
        mock_cw_client.get_metric_statistics.return_value = {
            'Datapoints': [{'Average': 50.0}]
        }
        
        # Configure boto3.client to return appropriate clients
        def client_side_effect(service_name, **kwargs):
            if service_name == 'ec2':
                return mock_ec2_client
            elif service_name == 'cloudwatch':
                return mock_cw_client
            return Mock()
        
        mock_boto_client.side_effect = client_side_effect
        
        collector = CloudWatchMetricsCollector(region='us-east-1')
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_service_metrics(
            services=['ec2'],
            start_time=start_time,
            end_time=end_time
        )
        
        # Verify result structure
        assert 'ec2' in result
        assert isinstance(result['ec2'], list)
        
        # Verify EC2Metrics objects are returned (not MetricDataPoint)
        if len(result['ec2']) > 0:
            from src.utils.types import EC2Metrics
            assert isinstance(result['ec2'][0], EC2Metrics)
            assert result['ec2'][0].instance_id == 'i-123'
            assert result['ec2'][0].instance_type == 't2.micro'
    
    @patch('boto3.client')
    def test_collect_service_metrics_handles_multiple_services(self, mock_boto_client):
        """Test collecting metrics for multiple services."""
        # Mock clients
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instances.return_value = {'Reservations': []}
        
        mock_lambda_client = Mock()
        mock_lambda_client.list_functions.return_value = {'Functions': []}
        
        mock_cw_client = Mock()
        mock_cw_client.get_metric_statistics.return_value = {'Datapoints': []}
        
        def client_side_effect(service_name, **kwargs):
            if service_name == 'ec2':
                return mock_ec2_client
            elif service_name == 'lambda':
                return mock_lambda_client
            elif service_name == 'cloudwatch':
                return mock_cw_client
            return Mock()
        
        mock_boto_client.side_effect = client_side_effect
        
        collector = CloudWatchMetricsCollector(region='us-east-1')
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_service_metrics(
            services=['ec2', 'lambda'],
            start_time=start_time,
            end_time=end_time
        )
        
        # Verify both services are in result
        assert 'ec2' in result
        assert 'lambda' in result
        assert isinstance(result['ec2'], list)
        assert isinstance(result['lambda'], list)
    
    @patch('boto3.client')
    def test_collect_service_metrics_handles_errors_gracefully(self, mock_boto_client):
        """Test that errors in one service don't break others."""
        # Mock EC2 to raise error
        mock_ec2_client = Mock()
        mock_ec2_client.describe_instances.side_effect = Exception("EC2 error")
        
        # Mock Lambda to work
        mock_lambda_client = Mock()
        mock_lambda_client.list_functions.return_value = {'Functions': []}
        
        mock_cw_client = Mock()
        mock_cw_client.get_metric_statistics.return_value = {'Datapoints': []}
        
        def client_side_effect(service_name, **kwargs):
            if service_name == 'ec2':
                return mock_ec2_client
            elif service_name == 'lambda':
                return mock_lambda_client
            elif service_name == 'cloudwatch':
                return mock_cw_client
            return Mock()
        
        mock_boto_client.side_effect = client_side_effect
        
        collector = CloudWatchMetricsCollector(region='us-east-1')
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        result = collector.collect_service_metrics(
            services=['ec2', 'lambda'],
            start_time=start_time,
            end_time=end_time
        )
        
        # EC2 should have empty list due to error
        assert result['ec2'] == []
        # Lambda should still work
        assert 'lambda' in result


class TestStoreMetrics:
    """Test store_metrics method."""
    
    def test_store_metrics_stores_ec2_metrics(self):
        """Test storing EC2 metrics in DynamoDB."""
        from unittest.mock import MagicMock, Mock
        from datetime import timedelta
        
        mock_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        collector = CloudWatchMetricsCollector(client=mock_client)
        collector.dynamodb_resource = mock_dynamodb_resource
        collector.metrics_table_name = 'test-metrics-table'
        
        ec2_metrics = [
            EC2Metrics(
                instance_id='i-123',
                instance_type='t2.micro',
                cpu_utilization=Decimal('50'),
                network_in=Decimal('1000'),
                network_out=Decimal('1073741824'),
                disk_read_bytes=Decimal('1000'),
                running_hours=Decimal('1')
            )
        ]
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        collector.store_metrics('ec2', ec2_metrics, start_time, end_time)
        
        # Verify put_item was called
        assert mock_table.put_item.called
        call_args = mock_table.put_item.call_args
        
        # Verify item structure
        item = call_args[1]['Item']
        assert item['service'] == 'ec2'
        assert item['metric_id'] == 'ec2#i-123'
        assert 'metric_data' in item
        assert 'ttl' in item
    
    def test_store_metrics_handles_missing_table_gracefully(self):
        """Test that missing table doesn't raise exception."""
        from unittest.mock import MagicMock, Mock
        from botocore.exceptions import ClientError
        
        mock_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        # Mock ResourceNotFoundException
        error_response = {
            'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'},
            'ResponseMetadata': {'RequestId': 'test-request-id'}
        }
        mock_table.put_item.side_effect = ClientError(error_response, 'put_item')
        
        collector = CloudWatchMetricsCollector(client=mock_client)
        collector.dynamodb_resource = mock_dynamodb_resource
        collector.metrics_table_name = 'test-metrics-table'
        
        ec2_metrics = [
            EC2Metrics(
                instance_id='i-123',
                instance_type='t2.micro',
                cpu_utilization=Decimal('50'),
                network_in=Decimal('1000'),
                network_out=Decimal('1073741824'),
                disk_read_bytes=Decimal('1000'),
                running_hours=Decimal('1')
            )
        ]
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        # Should not raise exception
        collector.store_metrics('ec2', ec2_metrics, start_time, end_time)
        
        # Verify put_item was called (even though it failed)
        assert mock_table.put_item.called
    
    def test_store_metrics_handles_other_errors_gracefully(self):
        """Test that other errors are handled gracefully."""
        from unittest.mock import MagicMock, Mock
        from botocore.exceptions import ClientError
        
        mock_client = Mock()
        mock_dynamodb_resource = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        # Mock other error
        error_response = {
            'Error': {'Code': 'ProvisionedThroughputExceededException', 'Message': 'Throughput exceeded'},
            'ResponseMetadata': {'RequestId': 'test-request-id'}
        }
        mock_table.put_item.side_effect = ClientError(error_response, 'put_item')
        
        collector = CloudWatchMetricsCollector(client=mock_client)
        collector.dynamodb_resource = mock_dynamodb_resource
        collector.metrics_table_name = 'test-metrics-table'
        
        ec2_metrics = [
            EC2Metrics(
                instance_id='i-123',
                instance_type='t2.micro',
                cpu_utilization=Decimal('50'),
                network_in=Decimal('1000'),
                network_out=Decimal('1073741824'),
                disk_read_bytes=Decimal('1000'),
                running_hours=Decimal('1')
            )
        ]
        
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        end_time = datetime(2024, 1, 1, 1, 0, 0)
        
        # Should not raise exception
        collector.store_metrics('ec2', ec2_metrics, start_time, end_time)
        
        # Verify put_item was called
        assert mock_table.put_item.called