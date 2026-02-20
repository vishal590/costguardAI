"""
Unit tests for Lambda handler.

Tests specific examples and edge cases for Lambda handler integration.
"""
import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.lambda_handler import (
    handler,
    handle_fetch,
    handle_query,
    handle_estimation_current,
    handle_estimation_service,
    create_error_response
)


class TestHandlerRouting:
    """Test main handler routing logic."""
    
    def test_handler_routes_to_fetch(self):
        """Test handler routes POST /fetch to handle_fetch."""
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
    
    def test_handler_routes_to_query(self):
        """Test handler routes GET /cost-data to handle_query."""
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
    
    def test_handler_returns_400_for_unsupported_method(self):
        """Test handler returns 400 for unsupported HTTP method."""
        event = {
            'httpMethod': 'DELETE',
            'path': '/api/cost-data'
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False


class TestHandleFetch:
    """Test handle_fetch function."""
    
    def test_fetch_with_valid_parameters(self):
        """Test POST /fetch with valid parameters."""
        mock_records = [
            Mock(
                date='2025-01-01',
                service='Amazon EC2',
                blended_cost=100.0,
                unblended_cost=100.0,
                currency='USD',
                unit='USD'
            )
        ]
        
        with patch('src.lambda_handler.fetch_cost_data', return_value=mock_records):
            with patch('src.lambda_handler.store_cost_data'):
                event = {
                    'httpMethod': 'POST',
                    'path': '/api/cost-data/fetch',
                    'body': json.dumps({
                        'startDate': '2025-01-01',
                        'endDate': '2025-01-31',
                        'granularity': 'MONTHLY'
                    })
                }
                
                response = handle_fetch(event)
                
                assert response['statusCode'] == 200
                body = json.loads(response['body'])
                assert body['success'] is True
                assert body['data']['recordsProcessed'] == 1
                assert body['data']['totalCost'] == 100.0
    
    def test_fetch_with_no_parameters_uses_defaults(self):
        """Test POST /fetch with no parameters uses defaults."""
        with patch('src.lambda_handler.fetch_cost_data', return_value=[]):
            with patch('src.lambda_handler.store_cost_data'):
                with patch('src.lambda_handler.calculate_default_date_range', return_value=('2024-01-01', '2024-12-31')):
                    event = {
                        'httpMethod': 'POST',
                        'path': '/api/cost-data/fetch',
                        'body': '{}'
                    }
                    
                    response = handle_fetch(event)
                    
                    assert response['statusCode'] == 200
                    body = json.loads(response['body'])
                    assert body['data']['dateRange']['start'] == '2024-01-01'
                    assert body['data']['dateRange']['end'] == '2024-12-31'
    
    def test_fetch_with_invalid_date_format(self):
        """Test POST /fetch with invalid date format returns 400."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/cost-data/fetch',
            'body': json.dumps({
                'startDate': '01-01-2025',  # Invalid format
                'endDate': '2025-01-31'
            })
        }
        
        response = handle_fetch(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'INVALID_DATE_FORMAT' in body['error']['code']
    
    def test_fetch_with_invalid_date_range(self):
        """Test POST /fetch with invalid date range returns 400."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/cost-data/fetch',
            'body': json.dumps({
                'startDate': '2025-12-31',
                'endDate': '2025-01-01'  # End before start
            })
        }
        
        response = handle_fetch(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'INVALID_DATE_RANGE' in body['error']['code']
    
    def test_fetch_with_invalid_granularity(self):
        """Test POST /fetch with invalid granularity returns 400."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/cost-data/fetch',
            'body': json.dumps({
                'startDate': '2025-01-01',
                'endDate': '2025-01-31',
                'granularity': 'WEEKLY'  # Invalid
            })
        }
        
        response = handle_fetch(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'INVALID_GRANULARITY' in body['error']['code']
    
    def test_fetch_response_format_for_success(self):
        """Test response format for successful fetch."""
        mock_records = [
            Mock(date='2025-01-01', service='EC2', blended_cost=50.0, unblended_cost=50.0, currency='USD', unit='USD'),
            Mock(date='2025-01-01', service='S3', blended_cost=25.0, unblended_cost=25.0, currency='USD', unit='USD')
        ]
        
        with patch('src.lambda_handler.fetch_cost_data', return_value=mock_records):
            with patch('src.lambda_handler.store_cost_data'):
                event = {
                    'body': json.dumps({
                        'startDate': '2025-01-01',
                        'endDate': '2025-01-31'
                    })
                }
                
                response = handle_fetch(event)
                
                assert response['statusCode'] == 200
                assert 'Content-Type' in response['headers']
                body = json.loads(response['body'])
                assert 'success' in body
                assert 'message' in body
                assert 'data' in body


class TestHandleQuery:
    """Test handle_query function."""
    
    def test_query_with_filters(self):
        """Test GET /query with filters."""
        mock_records = [
            Mock(
                date='2025-01-01',
                service='Amazon EC2',
                blended_cost=100.0,
                unblended_cost=100.0,
                currency='USD'
            )
        ]
        
        with patch('src.lambda_handler.query_cost_data', return_value=mock_records):
            event = {
                'httpMethod': 'GET',
                'path': '/api/cost-data',
                'queryStringParameters': {
                    'startDate': '2025-01-01',
                    'endDate': '2025-01-31',
                    'service': 'Amazon EC2',
                    'limit': '10'
                }
            }
            
            response = handle_query(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['count'] == 1
            assert len(body['data']) == 1
    
    def test_query_with_no_filters_uses_defaults(self):
        """Test GET /query with no filters uses defaults."""
        with patch('src.lambda_handler.query_cost_data', return_value=[]):
            event = {
                'httpMethod': 'GET',
                'path': '/api/cost-data',
                'queryStringParameters': None
            }
            
            response = handle_query(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['count'] == 0
    
    def test_query_with_invalid_date_format(self):
        """Test GET /query with invalid date format returns 400."""
        event = {
            'queryStringParameters': {
                'startDate': 'invalid-date'
            }
        }
        
        response = handle_query(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
    
    def test_query_with_invalid_date_range(self):
        """Test GET /query with invalid date range returns 400."""
        event = {
            'queryStringParameters': {
                'startDate': '2025-12-31',
                'endDate': '2025-01-01'
            }
        }
        
        response = handle_query(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
    
    def test_query_response_format_for_success(self):
        """Test response format for successful query."""
        mock_records = [
            Mock(date='2025-01-01', service='EC2', blended_cost=100.0, unblended_cost=100.0, currency='USD')
        ]
        
        with patch('src.lambda_handler.query_cost_data', return_value=mock_records):
            event = {
                'queryStringParameters': {'startDate': '2025-01-01'}
            }
            
            response = handle_query(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert 'success' in body
            assert 'data' in body
            assert 'count' in body
            
            # Verify record format
            record = body['data'][0]
            assert 'date' in record
            assert 'service' in record
            assert 'blendedCost' in record
            assert 'unblendedCost' in record
            assert 'currency' in record
    
    def test_query_response_format_for_error(self):
        """Test response format for errors."""
        event = {
            'queryStringParameters': {
                'limit': 'invalid'  # Should be integer
            }
        }
        
        response = handle_query(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'error' in body
        assert 'code' in body['error']
        assert 'message' in body['error']


class TestCreateErrorResponse:
    """Test create_error_response function."""
    
    def test_create_error_response_basic(self):
        """Test creating basic error response."""
        response = create_error_response(400, 'TEST_ERROR', 'Test message')
        
        assert response['statusCode'] == 400
        assert 'Content-Type' in response['headers']
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'TEST_ERROR'
        assert body['error']['message'] == 'Test message'
    
    def test_create_error_response_with_details(self):
        """Test creating error response with details."""
        details = {'field': 'value', 'count': 123}
        response = create_error_response(500, 'INTERNAL_ERROR', 'Error occurred', details)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error']['details'] == details
    
    def test_create_error_response_without_details(self):
        """Test creating error response without details."""
        response = create_error_response(404, 'NOT_FOUND', 'Resource not found')
        
        body = json.loads(response['body'])
        assert 'details' not in body['error']



class TestHandleEstimationCurrent:
    """Test handle_estimation_current function."""
    
    def test_estimation_current_with_default_time_range(self):
        """Test GET /cost-estimation/current with default time range (1 hour)."""
        mock_metrics = {
            'ec2': [Mock()],
            'lambda': [Mock()]
        }
        mock_estimate = Mock(
            service='ec2',
            estimated_cost=50.0,
            currency='USD',
            confidence_lower=45.0,
            confidence_upper=55.0,
            timestamp=datetime(2025, 1, 1),
            period_start=datetime(2025, 1, 1, 0, 0),
            period_end=datetime(2025, 1, 1, 1, 0),
            metrics_count=10
        )
        
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
            with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
                with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                    mock_collector = mock_collector_class.return_value
                    mock_collector.collect_metrics.return_value = mock_metrics
                    
                    mock_pricing = mock_pricing_class.return_value
                    mock_pricing.get_pricing_data.return_value = Mock()
                    
                    mock_estimator = mock_estimator_class.return_value
                    mock_estimator.estimate_cost.return_value = mock_estimate
                    
                    event = {
                        'httpMethod': 'GET',
                        'path': '/api/cost-estimation/current',
                        'queryStringParameters': {}
                    }
                    
                    response = handle_estimation_current(event)
                    
                    assert response['statusCode'] == 200
                    body = json.loads(response['body'])
                    assert body['success'] is True
                    assert 'estimates' in body
                    assert 'totalCost' in body
                    assert body['period'] == '1 hours'
    
    def test_estimation_current_with_custom_time_range(self):
        """Test GET /cost-estimation/current with custom time range."""
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
            with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
                with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                    mock_collector = mock_collector_class.return_value
                    mock_collector.collect_metrics.return_value = {}
                    
                    event = {
                        'queryStringParameters': {
                            'hours': '24'
                        }
                    }
                    
                    response = handle_estimation_current(event)
                    
                    assert response['statusCode'] == 200
                    body = json.loads(response['body'])
                    assert body['period'] == '24 hours'
    
    def test_estimation_current_with_invalid_hours(self):
        """Test GET /cost-estimation/current with invalid hours parameter."""
        event = {
            'queryStringParameters': {
                'hours': 'invalid'
            }
        }
        
        response = handle_estimation_current(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'INVALID_PARAMETER' in body['error']['code']
    
    def test_estimation_current_with_out_of_range_hours(self):
        """Test GET /cost-estimation/current with out of range hours."""
        event = {
            'queryStringParameters': {
                'hours': '200'  # More than 168 (7 days)
            }
        }
        
        response = handle_estimation_current(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'INVALID_TIME_RANGE' in body['error']['code']
    
    def test_estimation_current_response_format(self):
        """Test response format for successful estimation."""
        mock_estimate = Mock(
            service='ec2',
            estimated_cost=100.0,
            currency='USD',
            confidence_lower=90.0,
            confidence_upper=110.0,
            timestamp=datetime(2025, 1, 1, 12, 0),
            period_start=datetime(2025, 1, 1, 11, 0),
            period_end=datetime(2025, 1, 1, 12, 0),
            metrics_count=20
        )
        
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
            with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
                with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                    mock_collector = mock_collector_class.return_value
                    mock_collector.collect_metrics.return_value = {'ec2': [Mock()]}
                    
                    mock_pricing = mock_pricing_class.return_value
                    mock_pricing.get_pricing_data.return_value = Mock()
                    
                    mock_estimator = mock_estimator_class.return_value
                    mock_estimator.estimate_cost.return_value = mock_estimate
                    
                    event = {
                        'queryStringParameters': {}
                    }
                    
                    response = handle_estimation_current(event)
                    
                    assert response['statusCode'] == 200
                    body = json.loads(response['body'])
                    
                    # Verify response structure
                    assert 'success' in body
                    assert 'estimates' in body
                    assert 'totalCost' in body
                    assert 'currency' in body
                    assert 'timestamp' in body
                    assert 'period' in body
                    
                    # Verify estimate structure
                    estimate = body['estimates'][0]
                    assert 'service' in estimate
                    assert 'estimatedCost' in estimate
                    assert 'currency' in estimate
                    assert 'confidenceLower' in estimate
                    assert 'confidenceUpper' in estimate
                    assert 'timestamp' in estimate
                    assert 'periodStart' in estimate
                    assert 'periodEnd' in estimate
                    assert 'metricsCount' in estimate


class TestHandleEstimationService:
    """Test handle_estimation_service function."""
    
    def test_estimation_service_with_valid_service(self):
        """Test GET /cost-estimation/service/{service} with valid service."""
        mock_estimate = Mock(
            service='ec2',
            estimated_cost=75.0,
            currency='USD',
            confidence_lower=70.0,
            confidence_upper=80.0,
            timestamp=datetime(2025, 1, 1),
            period_start=datetime(2025, 1, 1, 0, 0),
            period_end=datetime(2025, 1, 1, 1, 0),
            metrics_count=15
        )
        
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
            with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
                with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                    mock_collector = mock_collector_class.return_value
                    mock_collector.collect_metrics.return_value = {'ec2': [Mock()]}
                    
                    mock_pricing = mock_pricing_class.return_value
                    mock_pricing.get_pricing_data.return_value = Mock()
                    
                    mock_estimator = mock_estimator_class.return_value
                    mock_estimator.estimate_cost.return_value = mock_estimate
                    
                    event = {
                        'httpMethod': 'GET',
                        'path': '/api/cost-estimation/service/ec2',
                        'queryStringParameters': {}
                    }
                    
                    response = handle_estimation_service(event)
                    
                    assert response['statusCode'] == 200
                    body = json.loads(response['body'])
                    assert body['success'] is True
                    assert body['service'] == 'ec2'
                    assert body['estimatedCost'] == 75.0
    
    def test_estimation_service_with_no_metrics(self):
        """Test GET /cost-estimation/service/{service} when no metrics found."""
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
            mock_collector = mock_collector_class.return_value
            mock_collector.collect_metrics.return_value = {'lambda': []}
            
            event = {
                'path': '/api/cost-estimation/service/lambda',
                'queryStringParameters': {}
            }
            
            response = handle_estimation_service(event)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['estimatedCost'] == 0.0
            assert 'No metrics found' in body['message']
    
    def test_estimation_service_with_invalid_service(self):
        """Test GET /cost-estimation/service/{service} with invalid service."""
        event = {
            'path': '/api/cost-estimation/service/invalid-service',
            'queryStringParameters': {}
        }
        
        response = handle_estimation_service(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'INVALID_SERVICE' in body['error']['code']
    
    def test_estimation_service_with_missing_service(self):
        """Test GET /cost-estimation/service/ with missing service name."""
        event = {
            'path': '/api/cost-estimation/service/',
            'queryStringParameters': {}
        }
        
        response = handle_estimation_service(event)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert 'MISSING_SERVICE' in body['error']['code']
    
    def test_estimation_service_with_custom_time_range(self):
        """Test GET /cost-estimation/service/{service} with custom time range."""
        mock_estimate = Mock(
            service='s3',
            estimated_cost=25.0,
            currency='USD',
            confidence_lower=22.0,
            confidence_upper=28.0,
            timestamp=datetime(2025, 1, 1),
            period_start=datetime(2025, 1, 1, 0, 0),
            period_end=datetime(2025, 1, 2, 0, 0),
            metrics_count=50
        )
        
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
            with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
                with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                    mock_collector = mock_collector_class.return_value
                    mock_collector.collect_metrics.return_value = {'s3': [Mock()]}
                    
                    mock_pricing = mock_pricing_class.return_value
                    mock_pricing.get_pricing_data.return_value = Mock()
                    
                    mock_estimator = mock_estimator_class.return_value
                    mock_estimator.estimate_cost.return_value = mock_estimate
                    
                    event = {
                        'path': '/api/cost-estimation/service/s3',
                        'queryStringParameters': {
                            'hours': '24'
                        }
                    }
                    
                    response = handle_estimation_service(event)
                    
                    assert response['statusCode'] == 200
                    body = json.loads(response['body'])
                    assert body['success'] is True
    
    def test_estimation_service_response_format(self):
        """Test response format for successful service estimation."""
        mock_estimate = Mock(
            service='dynamodb',
            estimated_cost=30.0,
            currency='USD',
            confidence_lower=27.0,
            confidence_upper=33.0,
            timestamp=datetime(2025, 1, 1, 12, 0),
            period_start=datetime(2025, 1, 1, 11, 0),
            period_end=datetime(2025, 1, 1, 12, 0),
            metrics_count=25
        )
        
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector_class:
            with patch('src.lambda_handler.PricingManager') as mock_pricing_class:
                with patch('src.lambda_handler.CostEstimator') as mock_estimator_class:
                    mock_collector = mock_collector_class.return_value
                    mock_collector.collect_metrics.return_value = {'dynamodb': [Mock()]}
                    
                    mock_pricing = mock_pricing_class.return_value
                    mock_pricing.get_pricing_data.return_value = Mock()
                    
                    mock_estimator = mock_estimator_class.return_value
                    mock_estimator.estimate_cost.return_value = mock_estimate
                    
                    event = {
                        'path': '/api/cost-estimation/service/dynamodb',
                        'queryStringParameters': {}
                    }
                    
                    response = handle_estimation_service(event)
                    
                    assert response['statusCode'] == 200
                    body = json.loads(response['body'])
                    
                    # Verify response structure
                    assert 'success' in body
                    assert 'service' in body
                    assert 'estimatedCost' in body
                    assert 'currency' in body
                    assert 'confidenceLower' in body
                    assert 'confidenceUpper' in body
                    assert 'timestamp' in body
                    assert 'periodStart' in body
                    assert 'periodEnd' in body
                    assert 'metricsCount' in body


class TestPhase1Compatibility:
    """Test Phase 1 endpoints still work with Phase 1.5 changes."""
    
    def test_handler_still_routes_to_fetch(self):
        """Test handler still routes POST /fetch correctly."""
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
    
    def test_handler_still_routes_to_query(self):
        """Test handler still routes GET /cost-data correctly."""
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
    
    def test_handler_routes_to_estimation_current(self):
        """Test handler routes GET /cost-estimation/current correctly."""
        with patch('src.lambda_handler.handle_estimation_current') as mock_estimation:
            mock_estimation.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {
                'httpMethod': 'GET',
                'path': '/api/cost-estimation/current',
                'queryStringParameters': {}
            }
            
            response = handler(event, None)
            
            assert mock_estimation.called
            assert response['statusCode'] == 200
    
    def test_handler_routes_to_estimation_service(self):
        """Test handler routes GET /cost-estimation/service/{service} correctly."""
        with patch('src.lambda_handler.handle_estimation_service') as mock_estimation:
            mock_estimation.return_value = {'statusCode': 200, 'body': '{}'}
            
            event = {
                'httpMethod': 'GET',
                'path': '/api/cost-estimation/service/ec2',
                'queryStringParameters': {}
            }
            
            response = handler(event, None)
            
            assert mock_estimation.called
            assert response['statusCode'] == 200
