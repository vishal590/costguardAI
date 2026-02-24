"""
Unit tests for CloudWatch Metrics Service
"""
import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime
from decimal import Decimal

from src.services.multi_account.cloudwatch_metrics import (
    CloudWatchMetricsService,
    MetricsCollector,
    MetricData,
    get_metrics_service,
    metrics_collector
)


class TestCloudWatchMetricsService:
    """Test CloudWatch metrics service functionality."""
    
    def setup_method(self, method):
        """Set up test fixtures."""
        # No setup needed - each test will mock boto3.client independently
        pass
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_put_metric_success(self, mock_boto3_client):
        """Test successful metric publication."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        service.put_metric('TestMetric', 42.0, 'Count', {'TestDim': 'TestValue'})
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        assert call_args['Namespace'] == 'CostGuard/MultiAccount'
        assert len(call_args['MetricData']) == 1
        
        metric = call_args['MetricData'][0]
        assert metric['MetricName'] == 'TestMetric'
        assert metric['Value'] == 42.0
        assert metric['Unit'] == 'Count'
        assert len(metric['Dimensions']) == 1
        assert metric['Dimensions'][0]['Name'] == 'TestDim'
        assert metric['Dimensions'][0]['Value'] == 'TestValue'
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_put_metric_no_dimensions(self, mock_boto3_client):
        """Test metric publication without dimensions."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        service.put_metric('TestMetric', 42.0)
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        metric = call_args['MetricData'][0]
        assert 'Dimensions' not in metric
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_put_metrics_batch(self, mock_boto3_client):
        """Test batch metric publication."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        
        metrics = [
            MetricData('Metric1', 1.0, 'Count', {'Dim1': 'Val1'}),
            MetricData('Metric2', 2.0, 'Seconds', {'Dim2': 'Val2'}),
            MetricData('Metric3', 3.0, 'Percent', {})
        ]
        
        service.put_metrics_batch(metrics)
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        assert len(call_args['MetricData']) == 3
        assert call_args['MetricData'][0]['MetricName'] == 'Metric1'
        assert call_args['MetricData'][1]['MetricName'] == 'Metric2'
        assert call_args['MetricData'][2]['MetricName'] == 'Metric3'
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_put_metrics_batch_large(self, mock_boto3_client):
        """Test batch metric publication with more than 20 metrics."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        
        # Create 25 metrics (more than CloudWatch batch limit of 20)
        metrics = [
            MetricData(f'Metric{i}', float(i), 'Count', {})
            for i in range(25)
        ]
        
        service.put_metrics_batch(metrics)
        
        # Should be called twice (20 + 5)
        assert mock_cloudwatch.put_metric_data.call_count == 2
        
        # First batch should have 20 metrics
        first_call = mock_cloudwatch.put_metric_data.call_args_list[0][1]
        assert len(first_call['MetricData']) == 20
        
        # Second batch should have 5 metrics
        second_call = mock_cloudwatch.put_metric_data.call_args_list[1][1]
        assert len(second_call['MetricData']) == 5
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_record_cost_collection_duration(self, mock_boto3_client):
        """Test cost collection duration metric."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        service.record_cost_collection_duration(120.5, 10)
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        metric = call_args['MetricData'][0]
        assert metric['MetricName'] == 'MultiAccountCostCollection.Duration'
        assert metric['Value'] == 120.5
        assert metric['Unit'] == 'Seconds'
        assert metric['Dimensions'][0]['Name'] == 'AccountCount'
        assert metric['Dimensions'][0]['Value'] == '10'
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_record_cost_collection_success_rate(self, mock_boto3_client):
        """Test cost collection success rate metric."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        service.record_cost_collection_success_rate(8, 10)
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        metric = call_args['MetricData'][0]
        assert metric['MetricName'] == 'MultiAccountCostCollection.SuccessRate'
        assert metric['Value'] == 80.0  # 8/10 * 100
        assert metric['Unit'] == 'Percent'
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_record_cache_hit_rate(self, mock_boto3_client):
        """Test cache hit rate metric."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        service.record_cache_hit_rate(7, 10, 'TestCache')
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        metric = call_args['MetricData'][0]
        assert metric['MetricName'] == 'TestCache.CacheHitRate'
        assert metric['Value'] == 70.0  # 7/10 * 100
        assert metric['Unit'] == 'Percent'
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_record_unallocated_percentage(self, mock_boto3_client):
        """Test unallocated percentage metric."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        service.record_unallocated_percentage(25.0, 100.0, 'org-123')
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        metric = call_args['MetricData'][0]
        assert metric['MetricName'] == 'AllocationEngine.UnallocatedPercentage'
        assert metric['Value'] == 25.0  # 25/100 * 100
        assert metric['Unit'] == 'Percent'
        assert metric['Dimensions'][0]['Value'] == 'org-123'
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_record_api_response_time(self, mock_boto3_client):
        """Test API response time metric."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        service.record_api_response_time('/api/costs', 250.5)
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        metric = call_args['MetricData'][0]
        assert metric['MetricName'] == 'API.ResponseTime'
        assert metric['Value'] == 250.5
        assert metric['Unit'] == 'Milliseconds'
        assert metric['Dimensions'][0]['Value'] == '/api/costs'
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_record_lambda_error(self, mock_boto3_client):
        """Test Lambda error metric."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        service.record_lambda_error('TestFunction', 'ValueError')
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        metric = call_args['MetricData'][0]
        assert metric['MetricName'] == 'Lambda.Errors'
        assert metric['Value'] == 1
        assert metric['Unit'] == 'Count'
        
        dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
        assert dimensions['FunctionName'] == 'TestFunction'
        assert dimensions['ErrorType'] == 'ValueError'
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_record_dynamodb_throttle(self, mock_boto3_client):
        """Test DynamoDB throttle metric."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        service = CloudWatchMetricsService()
        service.record_dynamodb_throttle('test-table', 'PutItem')
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        
        metric = call_args['MetricData'][0]
        assert metric['MetricName'] == 'DynamoDB.Throttles'
        assert metric['Value'] == 1
        assert metric['Unit'] == 'Count'
        
        dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
        assert dimensions['TableName'] == 'test-table'
        assert dimensions['Operation'] == 'PutItem'


class TestMetricsCollector:
    """Test metrics collector context manager."""
    
    @patch('src.services.multi_account.cloudwatch_metrics.get_metrics_service')
    def test_metrics_collector_success(self, mock_get_service):
        """Test metrics collector for successful operation."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        
        with metrics_collector('TestOperation', {'TestDim': 'TestVal'}) as collector:
            collector.record_custom_metric('CustomMetric', 42.0, 'Count')
        
        # Should record custom metric, duration, and success (in that order)
        assert mock_service.put_metric.call_count == 3
        
        calls = mock_service.put_metric.call_args_list
        
        # Check custom metric (recorded first, inside context)
        custom_call = calls[0]
        assert custom_call.kwargs['metric_name'] == 'TestOperation.CustomMetric'
        assert custom_call.kwargs['value'] == 42.0
        assert custom_call.kwargs['unit'] == 'Count'
        
        # Check duration metric (recorded on exit)
        duration_call = calls[1]
        assert duration_call.kwargs['metric_name'] == 'TestOperation.Duration'
        assert duration_call.kwargs['unit'] == 'Seconds'
        
        # Check success metric (should be 1 for success)
        success_call = calls[2]
        assert success_call.kwargs['metric_name'] == 'TestOperation.Success'
        assert success_call.kwargs['value'] == 1  # Success
        assert success_call.kwargs['unit'] == 'Count'
    
    @patch('src.services.multi_account.cloudwatch_metrics.get_metrics_service')
    def test_metrics_collector_exception(self, mock_get_service):
        """Test metrics collector for failed operation."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        
        try:
            with metrics_collector('TestOperation') as collector:
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Should record duration, failure, and error
        assert mock_service.put_metric.call_count == 3
        
        calls = mock_service.put_metric.call_args_list
        
        # Check success metric (should be 0 for failure)
        success_call = calls[1]
        assert success_call.kwargs['value'] == 0  # Failure
        
        # Check error metric
        error_call = calls[2]
        assert error_call.kwargs['metric_name'] == 'TestOperation.Errors'
        assert error_call.kwargs['value'] == 1
        
        # Check error type dimension
        error_dimensions = error_call.kwargs['dimensions']
        assert error_dimensions['ErrorType'] == 'ValueError'
    
    @patch('src.services.multi_account.cloudwatch_metrics.get_metrics_service')
    def test_add_dimension(self, mock_get_service):
        """Test adding dimensions to metrics collector."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        
        with metrics_collector('TestOperation') as collector:
            collector.add_dimension('NewDim', 'NewVal')
        
        # Check that new dimension is included
        calls = mock_service.put_metric.call_args_list
        duration_call = calls[0]
        dimensions = duration_call.kwargs['dimensions']
        assert dimensions['NewDim'] == 'NewVal'


class TestGlobalFunctions:
    """Test global utility functions."""
    
    @patch('src.services.multi_account.cloudwatch_metrics.boto3.client')
    def test_get_metrics_service_singleton(self, mock_boto3_client):
        """Test that get_metrics_service returns singleton."""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        # Reset the global singleton for this test
        import src.services.multi_account.cloudwatch_metrics as metrics_module
        metrics_module._metrics_service = None
        
        service1 = get_metrics_service()
        service2 = get_metrics_service()
        
        assert service1 is service2
    
    @patch('src.services.multi_account.cloudwatch_metrics.get_metrics_service')
    def test_metrics_collector_function(self, mock_get_service):
        """Test metrics_collector function."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        
        collector = metrics_collector('TestOp', {'TestDim': 'TestVal'})
        
        assert isinstance(collector, MetricsCollector)
        assert collector.operation_name == 'TestOp'
        assert collector.dimensions == {'TestDim': 'TestVal'}


class TestMetricData:
    """Test MetricData dataclass."""
    
    def test_metric_data_creation(self):
        """Test MetricData creation."""
        metric = MetricData(
            metric_name='TestMetric',
            value=42.0,
            unit='Count',
            dimensions={'TestDim': 'TestVal'}
        )
        
        assert metric.metric_name == 'TestMetric'
        assert metric.value == 42.0
        assert metric.unit == 'Count'
        assert metric.dimensions == {'TestDim': 'TestVal'}
        assert metric.timestamp is None
    
    def test_metric_data_with_timestamp(self):
        """Test MetricData with timestamp."""
        timestamp = datetime.utcnow()
        metric = MetricData(
            metric_name='TestMetric',
            value=42.0,
            unit='Count',
            dimensions={},
            timestamp=timestamp
        )
        
        assert metric.timestamp == timestamp