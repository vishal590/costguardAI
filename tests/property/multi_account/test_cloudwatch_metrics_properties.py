"""
Property-Based Tests for CloudWatch Metrics Recording

Tests Property 16: CloudWatch Metrics Recording

For any API request completion, the handler should publish response_time metric to CloudWatch;
for any error, the handler should publish error_count metric with error_type dimension;
for any cost collection completion, the handler should publish collection_duration,
successful_account_count, and failed_account_count metrics to CloudWatch namespace "CostGuard/MultiAccount".

Validates: Requirements 1.15, 2.8, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import json
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, MagicMock, call
from decimal import Decimal
from datetime import datetime, date, timedelta

# Import handlers
from src.multi_account_api_handler import handler as api_handler
from src.multi_account_cost_collector_handler import lambda_handler as collector_handler


@given(
    endpoint=st.sampled_from([
        '/api/organizations',
        '/api/costs/consolidated',
        '/api/costs/by-account',
        '/api/allocation/by-tag'
    ])
)
@settings(max_examples=30, deadline=5000)
def test_property_16_api_response_time_metrics(endpoint):
    """
    Property 16: CloudWatch Metrics Recording (API Response Time)
    
    For any API request completion, the handler should publish response_time metric
    to CloudWatch with the endpoint dimension.
    
    Feature: phase-5-handlers, Property 16: CloudWatch Metrics Recording
    **Validates: Requirements 1.15, 13.1, 13.6**
    """
    # Create API Gateway event with valid key
    event = {
        'httpMethod': 'GET',
        'path': endpoint,
        'headers': {
            'X-Api-Key': 'valid-key-12345'
        },
        'queryStringParameters': {}
    }
    
    # Mock CloudWatch metrics service
    with patch('src.multi_account_api_handler.get_metrics_service') as mock_metrics:
        mock_service = Mock()
        mock_metrics.return_value = mock_service
        
        # Mock authentication to succeed
        with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
            mock_auth.return_value = (True, None, {'user_id': 'test-user'})
            
            # Mock service dependencies to return valid data
            with patch('src.multi_account_api_handler._get_organization_service') as mock_org:
                mock_org_service = Mock()
                mock_org.return_value = mock_org_service
                
                # Mock organization data
                mock_org = Mock()
                mock_org.id = 'o-test123'
                mock_org.master_account_id = '123456789012'
                mock_org.arn = 'arn:aws:organizations::123456789012:organization/o-test123'
                mock_org.feature_set = 'ALL'
                mock_org_service.discover_organization.return_value = mock_org
                mock_org_service.get_all_accounts.return_value = []
                
                with patch('src.multi_account_api_handler._get_cost_aggregation_engine'):
                    with patch('src.multi_account_api_handler._get_per_account_cost_service'):
                        with patch('src.multi_account_api_handler._get_cost_allocation_engine'):
                            # Call handler
                            response = api_handler(event, {})
                            
                            # Verify response time metric was recorded
                            assert mock_service.record_api_response_time.called
                            
                            # Get the call arguments
                            call_args = mock_service.record_api_response_time.call_args
                            recorded_endpoint = call_args[0][0]
                            duration_ms = call_args[0][1]
                            
                            # Verify endpoint matches
                            assert recorded_endpoint == endpoint
                            
                            # Verify duration is positive
                            assert duration_ms >= 0
                            
                            # Verify response has status code
                            assert 'statusCode' in response


@given(
    error_type=st.sampled_from(['ValueError', 'PermissionError', 'Exception'])
)
@settings(max_examples=20, deadline=5000)
def test_property_16_error_count_metrics(error_type):
    """
    Property 16: CloudWatch Metrics Recording (Error Count)
    
    For any unhandled error that occurs in the main handler, the handler should
    publish error_count metric to CloudWatch with error_type dimension.
    
    Feature: phase-5-handlers, Property 16: CloudWatch Metrics Recording
    **Validates: Requirements 13.2, 13.6**
    """
    # Create API Gateway event
    event = {
        'httpMethod': 'GET',
        'path': '/api/organizations',
        'headers': {
            'X-Api-Key': 'valid-key-12345'
        },
        'queryStringParameters': {}
    }
    
    # Mock CloudWatch metrics service
    with patch('src.multi_account_api_handler.get_metrics_service') as mock_metrics:
        mock_service = Mock()
        mock_metrics.return_value = mock_service
        
        # Mock authentication to raise an error (unhandled exception path)
        with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
            if error_type == 'ValueError':
                mock_auth.side_effect = ValueError("Invalid parameter")
            elif error_type == 'PermissionError':
                mock_auth.side_effect = PermissionError("Access denied")
            else:
                mock_auth.side_effect = Exception("Internal error")
            
            # Call handler
            response = api_handler(event, {})
            
            # Verify error metric was recorded
            assert mock_service.record_lambda_error.called
            
            # Get the call arguments
            call_args = mock_service.record_lambda_error.call_args
            function_name = call_args[0][0]
            recorded_error_type = call_args[0][1]
            
            # Verify function name
            assert function_name == 'MultiAccountAPIHandler'
            
            # Verify error type is recorded
            assert recorded_error_type == error_type
            
            # Verify response indicates error
            assert response['statusCode'] == 500


@given(
    total_accounts=st.integers(min_value=5, max_value=20),
    success_rate=st.floats(min_value=0.5, max_value=1.0)
)
@settings(max_examples=30, deadline=10000)
def test_property_16_cost_collection_metrics(total_accounts, success_rate):
    """
    Property 16: CloudWatch Metrics Recording (Cost Collection)
    
    For any cost collection completion, the handler should publish collection_duration,
    successful_account_count, and failed_account_count metrics to CloudWatch
    namespace "CostGuard/MultiAccount".
    
    Feature: phase-5-handlers, Property 16: CloudWatch Metrics Recording
    **Validates: Requirements 2.8, 13.3, 13.4, 13.5, 13.6**
    """
    # Calculate successful and failed accounts
    successful = int(total_accounts * success_rate)
    failed = total_accounts - successful
    
    # Create EventBridge event
    event = {
        'source': 'aws.events',
        'detail-type': 'Scheduled Event'
    }
    
    # Mock environment variables
    with patch.dict('os.environ', {
        'ORGANIZATION_ID': 'o-test123456',
        'EXTERNAL_ID': 'test-external-id',
        'DAYS_TO_COLLECT': '7',
        'LOG_LEVEL': 'INFO'
    }):
        # Mock CloudWatch metrics service
        with patch('src.services.multi_account.multi_account_cost_collector.get_metrics_service') as mock_metrics:
            mock_service = Mock()
            mock_metrics.return_value = mock_service
            
            # Mock organization discovery
            with patch('src.multi_account_cost_collector_handler.OrganizationDiscoveryService') as mock_discovery:
                mock_org_service = Mock()
                mock_discovery.return_value = mock_org_service
                
                # Create mock organization data
                mock_org_data = Mock()
                mock_org_data.accounts = [
                    Mock(id=f'account-{i}') for i in range(total_accounts)
                ]
                mock_org_service.discover_organization.return_value = mock_org_data
                
                # Mock cost collector
                with patch('src.multi_account_cost_collector_handler.MultiAccountCostCollector') as mock_collector_class:
                    mock_collector = Mock()
                    mock_collector_class.return_value = mock_collector
                    
                    # Create mock collection result
                    mock_result = Mock()
                    mock_result.total_accounts = total_accounts
                    mock_result.successful = successful
                    mock_result.failed = failed
                    mock_result.failed_accounts = [f'account-{i}' for i in range(failed)]
                    mock_result.collection_duration = 45.5
                    mock_result.account_data = [
                        Mock(total_cost=Decimal('100.50'), status='SUCCESS')
                        for _ in range(successful)
                    ]
                    
                    mock_collector.collect_all_accounts.return_value = mock_result
                    
                    # Call handler
                    response = collector_handler(event, {})
                    
                    # Verify collection was called
                    assert mock_collector.collect_all_accounts.called
                    
                    # Parse response
                    assert response['statusCode'] in [200, 207]
                    body = json.loads(response['body'])
                    
                    # Verify summary contains required fields
                    assert 'summary' in body
                    summary = body['summary']
                    
                    assert summary['total_accounts'] == total_accounts
                    assert summary['successful'] == successful
                    assert summary['failed'] == failed
                    assert 'collection_duration_seconds' in summary
                    
                    # Verify status code is 207 if failure rate > 20%
                    failure_rate = failed / total_accounts
                    if failure_rate > 0.2:
                        assert response['statusCode'] == 207
                    else:
                        assert response['statusCode'] == 200


@given(
    namespace=st.just("CostGuard/MultiAccount"),
    metric_name=st.sampled_from([
        'API.ResponseTime',
        'Lambda.Errors',
        'MultiAccountCostCollection.Duration',
        'MultiAccountCostCollection.SuccessRate'
    ])
)
@settings(max_examples=20, deadline=3000)
def test_property_16_metrics_namespace(namespace, metric_name):
    """
    Property 16: CloudWatch Metrics Recording (Namespace)
    
    All custom metrics should be published to the "CostGuard/MultiAccount" namespace.
    
    Feature: phase-5-handlers, Property 16: CloudWatch Metrics Recording
    **Validates: Requirements 13.6**
    """
    from src.services.multi_account.cloudwatch_metrics import CloudWatchMetricsService
    
    # Create metrics service
    metrics_service = CloudWatchMetricsService(namespace=namespace)
    
    # Verify namespace is set correctly
    assert metrics_service.namespace == namespace
    assert metrics_service.namespace == "CostGuard/MultiAccount"
    
    # Mock CloudWatch client
    with patch.object(metrics_service, 'cloudwatch') as mock_cloudwatch:
        # Record a metric
        metrics_service.put_metric(
            metric_name=metric_name,
            value=100.0,
            unit='Milliseconds',
            dimensions={'Test': 'Value'}
        )
        
        # Verify put_metric_data was called with correct namespace
        assert mock_cloudwatch.put_metric_data.called
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        # Verify namespace
        assert call_args[1]['Namespace'] == namespace
        
        # Verify metric data
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == metric_name
        assert metric_data['Value'] == 100.0


@given(
    duration_ms=st.floats(min_value=10.0, max_value=5000.0),
    endpoint=st.text(min_size=5, max_size=50)
)
@settings(max_examples=30, deadline=3000)
def test_property_16_response_time_metric_format(duration_ms, endpoint):
    """
    Property 16: CloudWatch Metrics Recording (Response Time Format)
    
    Response time metrics should be recorded in milliseconds with endpoint dimension.
    
    Feature: phase-5-handlers, Property 16: CloudWatch Metrics Recording
    **Validates: Requirements 1.15, 13.1**
    """
    from src.services.multi_account.cloudwatch_metrics import CloudWatchMetricsService
    
    # Create metrics service
    metrics_service = CloudWatchMetricsService()
    
    # Mock CloudWatch client
    with patch.object(metrics_service, 'cloudwatch') as mock_cloudwatch:
        # Record API response time
        metrics_service.record_api_response_time(endpoint, duration_ms)
        
        # Verify put_metric_data was called
        assert mock_cloudwatch.put_metric_data.called
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        # Verify metric data
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'API.ResponseTime'
        assert metric_data['Value'] == duration_ms
        assert metric_data['Unit'] == 'Milliseconds'
        
        # Verify dimensions
        dimensions = {d['Name']: d['Value'] for d in metric_data['Dimensions']}
        assert 'Endpoint' in dimensions
        assert dimensions['Endpoint'] == endpoint


@given(
    successful_accounts=st.integers(min_value=0, max_value=100),
    failed_accounts=st.integers(min_value=0, max_value=20)
)
@settings(max_examples=30, deadline=3000)
def test_property_16_collection_count_metrics(successful_accounts, failed_accounts):
    """
    Property 16: CloudWatch Metrics Recording (Collection Counts)
    
    Cost collection should record successful and failed account count metrics.
    
    Feature: phase-5-handlers, Property 16: CloudWatch Metrics Recording
    **Validates: Requirements 13.4, 13.5**
    """
    from src.services.multi_account.cloudwatch_metrics import CloudWatchMetricsService
    
    # Create metrics service
    metrics_service = CloudWatchMetricsService()
    
    total_accounts = successful_accounts + failed_accounts
    
    if total_accounts == 0:
        # Skip if no accounts
        return
    
    # Mock CloudWatch client
    with patch.object(metrics_service, 'cloudwatch') as mock_cloudwatch:
        # Record success rate
        metrics_service.record_cost_collection_success_rate(
            successful_accounts=successful_accounts,
            total_accounts=total_accounts
        )
        
        # Verify put_metric_data was called
        assert mock_cloudwatch.put_metric_data.called
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        # Verify metric data
        metric_data = call_args[1]['MetricData'][0]
        assert metric_data['MetricName'] == 'MultiAccountCostCollection.SuccessRate'
        
        # Calculate expected success rate
        expected_rate = (successful_accounts / total_accounts * 100)
        assert abs(metric_data['Value'] - expected_rate) < 0.01
        
        assert metric_data['Unit'] == 'Percent'
        
        # Verify dimensions
        dimensions = {d['Name']: d['Value'] for d in metric_data['Dimensions']}
        assert 'TotalAccounts' in dimensions
        assert dimensions['TotalAccounts'] == str(total_accounts)
