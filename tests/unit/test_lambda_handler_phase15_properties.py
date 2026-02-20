"""
Property-based tests for Lambda handler Phase 1.5 endpoints.

Tests universal properties across all inputs using Hypothesis.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings
from decimal import Decimal

from src.lambda_handler import (
    handler,
    handle_estimation_current,
    handle_estimation_service
)


# Feature: near-realtime-cost-estimation, Property 4: API Response Structure
@given(
    hours=st.integers(min_value=1, max_value=168),
    service_count=st.integers(min_value=0, max_value=5)
)
@settings(max_examples=100)
def test_api_response_structure_for_estimation_current(hours, service_count):
    """
    Property 4: API Response Structure
    
    For any successful estimation request, the response must include service name,
    estimated cost, currency, and timestamp.
    
    Validates: Requirements 4.7
    """
    # Create mock estimates
    mock_estimates = []
    services = ['ec2', 'lambda', 'dynamodb', 's3', 'rds'][:service_count]
    
    base_time = datetime(2025, 1, 1, 0, 0)
    for service in services:
        mock_estimate = Mock(
            service=service,
            estimated_cost=Decimal('50.0'),
            currency='USD',
            confidence_lower=Decimal('45.0'),
            confidence_upper=Decimal('55.0'),
            timestamp=base_time,
            period_start=base_time,
            period_end=base_time + timedelta(hours=hours),
            metrics_count=10
        )
        mock_estimates.append(mock_estimate)
    
    with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
        with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
            with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                mock_collector = mock_collector_class.return_value
                mock_collector.collect_metrics.return_value = {s: [Mock()] for s in services}
                
                mock_pricing = mock_pricing_class.return_value
                mock_pricing.get_pricing_data.return_value = Mock()
                
                mock_estimator = mock_estimator_class.return_value
                mock_estimator.estimate_cost.side_effect = mock_estimates
                
                event = {
                    'queryStringParameters': {'hours': str(hours)}
                }
                
                response = handle_estimation_current(event)
                
                # Verify response structure
                assert response['statusCode'] == 200
                assert 'Content-Type' in response['headers']
                
                body = json.loads(response['body'])
                assert 'success' in body
                assert body['success'] is True
                assert 'estimates' in body
                assert 'totalCost' in body
                assert 'currency' in body
                assert 'timestamp' in body
                
                # Verify each estimate has required fields
                for estimate in body['estimates']:
                    assert 'service' in estimate
                    assert 'estimatedCost' in estimate
                    assert 'currency' in estimate
                    assert 'timestamp' in estimate
                    assert isinstance(estimate['estimatedCost'], (int, float))
                    assert isinstance(estimate['currency'], str)


# Feature: near-realtime-cost-estimation, Property 4: API Response Structure
@given(
    service=st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds']),
    hours=st.integers(min_value=1, max_value=168)
)
@settings(max_examples=100)
def test_api_response_structure_for_estimation_service(service, hours):
    """
    Property 4: API Response Structure
    
    For any successful service estimation request, the response must include
    service name, estimated cost, currency, and timestamp.
    
    Validates: Requirements 4.7
    """
    base_time = datetime(2025, 1, 1, 0, 0)
    mock_estimate = Mock(
        service=service,
        estimated_cost=Decimal('75.0'),
        currency='USD',
        confidence_lower=Decimal('70.0'),
        confidence_upper=Decimal('80.0'),
        timestamp=base_time,
        period_start=base_time,
        period_end=base_time + timedelta(hours=hours),
        metrics_count=15
    )
    
    with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
        with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
            with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                mock_collector = mock_collector_class.return_value
                mock_collector.collect_metrics.return_value = {service: [Mock()]}
                
                mock_pricing = mock_pricing_class.return_value
                mock_pricing.get_pricing_data.return_value = Mock()
                
                mock_estimator = mock_estimator_class.return_value
                mock_estimator.estimate_cost.return_value = mock_estimate
                
                event = {
                    'path': f'/api/cost-estimation/service/{service}',
                    'queryStringParameters': {'hours': str(hours)}
                }
                
                response = handle_estimation_service(event)
                
                # Verify response structure
                assert response['statusCode'] == 200
                assert 'Content-Type' in response['headers']
                
                body = json.loads(response['body'])
                assert 'success' in body
                assert body['success'] is True
                assert 'service' in body
                assert body['service'] == service
                assert 'estimatedCost' in body
                assert 'currency' in body
                assert 'timestamp' in body
                assert isinstance(body['estimatedCost'], (int, float))
                assert isinstance(body['currency'], str)


# Feature: near-realtime-cost-estimation, Property 6: Phase 1 Compatibility
@given(
    method=st.sampled_from(['POST', 'GET']),
    path=st.sampled_from(['/api/cost-data/fetch', '/api/cost-data'])
)
@settings(max_examples=100)
def test_phase1_compatibility(method, path):
    """
    Property 6: Phase 1 Compatibility
    
    For any Phase 1 endpoint request, the system must continue to function
    identically to Phase 1 behavior.
    
    Validates: Requirements 5.4
    """
    # Mock Phase 1 handlers
    if method == 'POST' and '/fetch' in path:
        with patch('src.lambda_handler.handle_fetch') as mock_fetch:
            mock_fetch.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {
                'httpMethod': method,
                'path': path,
                'body': '{}'
            }
            
            response = handler(event, None)
            
            # Verify Phase 1 handler was called
            assert mock_fetch.called
            assert response['statusCode'] == 200
    
    elif method == 'GET' and path.endswith('/cost-data'):
        with patch('src.lambda_handler.handle_query') as mock_query:
            mock_query.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {
                'httpMethod': method,
                'path': path,
                'queryStringParameters': {}
            }
            
            response = handler(event, None)
            
            # Verify Phase 1 handler was called
            assert mock_query.called
            assert response['statusCode'] == 200


# Feature: near-realtime-cost-estimation, Property 8: Error Isolation
@given(
    failing_services=st.lists(
        st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds']),
        min_size=1,
        max_size=4,
        unique=True
    )
)
@settings(max_examples=100)
def test_error_isolation_in_metric_collection(failing_services):
    """
    Property 8: Error Isolation
    
    For any service where metric collection fails, the system must continue
    collecting metrics for other services.
    
    Validates: Requirements 6.4
    """
    all_services = ['ec2', 'lambda', 'dynamodb', 's3', 'rds']
    successful_services = [s for s in all_services if s not in failing_services]
    
    # Create mock metrics - failing services return empty, successful return data
    mock_metrics = {}
    for service in all_services:
        if service in failing_services:
            mock_metrics[service] = []  # Empty indicates failure
        else:
            mock_metrics[service] = [Mock()]  # Has data
    
    mock_estimates = []
    for service in successful_services:
        mock_estimate = Mock(
            service=service,
            estimated_cost=Decimal('50.0'),
            currency='USD',
            confidence_lower=Decimal('45.0'),
            confidence_upper=Decimal('55.0'),
            timestamp=datetime(2025, 1, 1),
            period_start=datetime(2025, 1, 1, 0, 0),
            period_end=datetime(2025, 1, 1, 1, 0),
            metrics_count=10
        )
        mock_estimates.append(mock_estimate)
    
    with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
        with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
            with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                mock_collector = mock_collector_class.return_value
                mock_collector.collect_metrics.return_value = mock_metrics
                
                mock_pricing = mock_pricing_class.return_value
                mock_pricing.get_pricing_data.return_value = Mock()
                
                mock_estimator = mock_estimator_class.return_value
                mock_estimator.estimate_cost.side_effect = mock_estimates
                
                event = {
                    'queryStringParameters': {'hours': '1'}
                }
                
                response = handle_estimation_current(event)
                
                # Verify response is successful despite some failures
                assert response['statusCode'] == 200
                body = json.loads(response['body'])
                assert body['success'] is True
                
                # Verify only successful services are in estimates
                estimate_services = [est['service'] for est in body['estimates']]
                for service in successful_services:
                    assert service in estimate_services
                
                # Verify failing services are not in estimates
                for service in failing_services:
                    assert service not in estimate_services


# Feature: near-realtime-cost-estimation, Property 9: Response Time Bounds
@given(
    service=st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds']),
    hours=st.integers(min_value=1, max_value=168)
)
@settings(max_examples=50, deadline=3000)  # 3 second deadline per test
def test_response_time_bounds_for_service_estimation(service, hours):
    """
    Property 9: Response Time Bounds
    
    For any single service estimation request, the response time must be
    less than 2 seconds.
    
    Validates: Requirements 7.4
    
    Note: This test uses mocked services, so actual response time will be fast.
    In production, this property should be validated with real AWS services.
    """
    base_time = datetime(2025, 1, 1, 0, 0)
    mock_estimate = Mock(
        service=service,
        estimated_cost=Decimal('75.0'),
        currency='USD',
        confidence_lower=Decimal('70.0'),
        confidence_upper=Decimal('80.0'),
        timestamp=base_time,
        period_start=base_time,
        period_end=base_time + timedelta(hours=hours),
        metrics_count=15
    )
    
    with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
        with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
            with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                mock_collector = mock_collector_class.return_value
                mock_collector.collect_metrics.return_value = {service: [Mock()]}
                
                mock_pricing = mock_pricing_class.return_value
                mock_pricing.get_pricing_data.return_value = Mock()
                
                mock_estimator = mock_estimator_class.return_value
                mock_estimator.estimate_cost.return_value = mock_estimate
                
                event = {
                    'path': f'/api/cost-estimation/service/{service}',
                    'queryStringParameters': {'hours': str(hours)}
                }
                
                # Measure response time
                start_time = datetime.now()
                response = handle_estimation_service(event)
                end_time = datetime.now()
                
                elapsed_time = (end_time - start_time).total_seconds()
                
                # Verify response is successful
                assert response['statusCode'] == 200
                
                # Verify response time is reasonable (with mocks, should be very fast)
                # In production with real AWS calls, this should be < 2 seconds
                assert elapsed_time < 2.0, f"Response took {elapsed_time}s, expected < 2s"


# Feature: near-realtime-cost-estimation, Property 6: Phase 1 Compatibility
@given(
    phase15_path=st.sampled_from([
        '/api/cost-estimation/current',
        '/api/cost-estimation/service/ec2',
        '/api/cost-estimation/service/lambda'
    ])
)
@settings(max_examples=100)
def test_phase15_endpoints_do_not_break_phase1(phase15_path):
    """
    Property 6: Phase 1 Compatibility
    
    For any Phase 1.5 endpoint, Phase 1 endpoints must still work correctly.
    
    Validates: Requirements 5.4
    """
    # First, verify Phase 1.5 endpoint works
    if '/service/' in phase15_path:
        with patch('src.lambda_handler.handle_estimation_service') as mock_estimation:
            mock_estimation.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {
                'httpMethod': 'GET',
                'path': phase15_path,
                'queryStringParameters': {}
            }
            
            response = handler(event, None)
            assert mock_estimation.called
    else:
        with patch('src.lambda_handler.handle_estimation_current') as mock_estimation:
            mock_estimation.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {
                'httpMethod': 'GET',
                'path': phase15_path,
                'queryStringParameters': {}
            }
            
            response = handler(event, None)
            assert mock_estimation.called
    
    # Now verify Phase 1 endpoints still work
    with patch('src.lambda_handler.handle_fetch') as mock_fetch:
        mock_fetch.return_value = {'statusCode': 200, 'body': '{}'}
        
        event = {
            'httpMethod': 'POST',
            'path': '/api/cost-data/fetch',
            'body': '{}'
        }
        
        response = handler(event, None)
        assert mock_fetch.called
        assert response['statusCode'] == 200
    
    with patch('src.lambda_handler.handle_query') as mock_query:
        mock_query.return_value = {'statusCode': 200, 'body': '{}'}
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-data',
            'queryStringParameters': {}
        }
        
        response = handler(event, None)
        assert mock_query.called
        assert response['statusCode'] == 200
