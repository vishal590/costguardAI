"""
Unit tests for Lambda handler Phase 2 (AI Cost Forecasting) endpoints.

Tests cover:
- Routing to Phase 2 endpoints
- Forecast request with various parameters
- Service-specific forecast requests
- Error responses
- Backward compatibility with Phase 1 & 1.5
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC

from src.lambda_handler import (
    handler,
    handle_forecast_request,
    handle_forecast_service_request
)
from src.utils.types import (
    ForecastResponse,
    ForecastDataPoint,
    ForecastMetadata,
    InsufficientDataError,
    BedrockAPIError,
    BedrockRateLimitError
)


@pytest.fixture
def mock_forecast_response():
    """Create a mock forecast response."""
    return ForecastResponse(
        success=True,
        forecast_data=[
            ForecastDataPoint(
                date='2024-01-01',
                predicted_cost=100.0,
                confidence_lower=90.0,
                confidence_upper=110.0,
                currency='USD'
            ),
            ForecastDataPoint(
                date='2024-01-02',
                predicted_cost=105.0,
                confidence_lower=95.0,
                confidence_upper=115.0,
                currency='USD'
            )
        ],
        metadata=ForecastMetadata(
            timestamp=datetime.now(UTC).isoformat(),
            forecast_horizon=30,
            granularity='daily',
            model_used='amazon.nova-lite-v1:0',
            service=None,
            services_included=['ec2', 'lambda', 's3'],
            cache_hit=False,
            historical_data_days=60
        )
    )


# Test: Routing to forecast endpoint
@patch('src.lambda_handler.ForecastEngine')
@patch('src.lambda_handler.get_dynamodb_client')
def test_routing_to_forecast_endpoint(mock_get_db, mock_engine_class, mock_forecast_response):
    """Test that GET /api/cost-forecast routes correctly."""
    mock_engine = Mock()
    mock_engine.generate_forecast.return_value = mock_forecast_response
    mock_engine_class.return_value = mock_engine
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast',
        'queryStringParameters': {'days': '30', 'granularity': 'daily'}
    }
    
    response = handler(event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'forecast_data' in body
    assert 'metadata' in body


# Test: Routing to service forecast endpoint
@patch('src.lambda_handler.ForecastEngine')
@patch('src.lambda_handler.get_dynamodb_client')
def test_routing_to_service_forecast_endpoint(mock_get_db, mock_engine_class, mock_forecast_response):
    """Test that GET /api/cost-forecast/service/{service} routes correctly."""
    mock_engine = Mock()
    mock_engine.generate_forecast.return_value = mock_forecast_response
    mock_engine_class.return_value = mock_engine
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast/service/lambda',
        'queryStringParameters': {'days': '30', 'granularity': 'daily'}
    }
    
    response = handler(event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True


# Test: Forecast request with default parameters
@patch('src.lambda_handler.ForecastEngine')
@patch('src.lambda_handler.get_dynamodb_client')
def test_forecast_request_default_parameters(mock_get_db, mock_engine_class, mock_forecast_response):
    """Test forecast request uses defaults when parameters omitted."""
    mock_engine = Mock()
    mock_engine.generate_forecast.return_value = mock_forecast_response
    mock_engine_class.return_value = mock_engine
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast',
        'queryStringParameters': None
    }
    
    response = handle_forecast_request(event)
    
    assert response['statusCode'] == 200
    # Verify defaults were used (30 days, daily)
    mock_engine.generate_forecast.assert_called_once_with(
        service=None,
        days=30,
        granularity='daily'
    )


# Test: Forecast request with custom parameters
@patch('src.lambda_handler.ForecastEngine')
@patch('src.lambda_handler.get_dynamodb_client')
def test_forecast_request_custom_parameters(mock_get_db, mock_engine_class, mock_forecast_response):
    """Test forecast request with custom days and granularity."""
    mock_engine = Mock()
    mock_engine.generate_forecast.return_value = mock_forecast_response
    mock_engine_class.return_value = mock_engine
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast',
        'queryStringParameters': {'days': '14', 'granularity': 'weekly'}
    }
    
    response = handle_forecast_request(event)
    
    assert response['statusCode'] == 200
    mock_engine.generate_forecast.assert_called_once_with(
        service=None,
        days=14,
        granularity='weekly'
    )


# Test: Invalid days parameter
def test_forecast_request_invalid_days():
    """Test forecast request with invalid days value."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast',
        'queryStringParameters': {'days': '45'}
    }
    
    response = handle_forecast_request(event)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'INVALID_PARAMETER' in body['error']['code']


# Test: Invalid granularity parameter
def test_forecast_request_invalid_granularity():
    """Test forecast request with invalid granularity."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast',
        'queryStringParameters': {'granularity': 'monthly'}
    }
    
    response = handle_forecast_request(event)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'INVALID_PARAMETER' in body['error']['code']


# Test: Service forecast with valid service
@patch('src.lambda_handler.ForecastEngine')
@patch('src.lambda_handler.get_dynamodb_client')
def test_service_forecast_valid_service(mock_get_db, mock_engine_class, mock_forecast_response):
    """Test service-specific forecast with valid service name."""
    mock_engine = Mock()
    mock_engine.generate_forecast.return_value = mock_forecast_response
    mock_engine_class.return_value = mock_engine
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast/service/lambda',
        'queryStringParameters': {'days': '30'}
    }
    
    response = handle_forecast_service_request(event)
    
    assert response['statusCode'] == 200
    mock_engine.generate_forecast.assert_called_once_with(
        service='lambda',
        days=30,
        granularity='daily'
    )


# Test: Service forecast with invalid service
def test_service_forecast_invalid_service():
    """Test service-specific forecast with invalid service name."""
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast/service/invalid-service',
        'queryStringParameters': {}
    }
    
    response = handle_forecast_service_request(event)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'INVALID_SERVICE' in body['error']['code']


# Test: InsufficientDataError handling
@patch('src.lambda_handler.ForecastEngine')
@patch('src.lambda_handler.get_dynamodb_client')
def test_insufficient_data_error(mock_get_db, mock_engine_class):
    """Test handling of InsufficientDataError."""
    mock_engine = Mock()
    mock_engine.generate_forecast.side_effect = InsufficientDataError("Minimum 30 days required")
    mock_engine_class.return_value = mock_engine
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast',
        'queryStringParameters': {}
    }
    
    response = handle_forecast_request(event)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'INSUFFICIENT_DATA' in body['error']['code']


# Test: BedrockRateLimitError handling
@patch('src.lambda_handler.ForecastEngine')
@patch('src.lambda_handler.get_dynamodb_client')
def test_bedrock_rate_limit_error(mock_get_db, mock_engine_class):
    """Test handling of BedrockRateLimitError."""
    mock_engine = Mock()
    mock_engine.generate_forecast.side_effect = BedrockRateLimitError("Rate limit exceeded")
    mock_engine_class.return_value = mock_engine
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast',
        'queryStringParameters': {}
    }
    
    response = handle_forecast_request(event)
    
    assert response['statusCode'] == 429
    body = json.loads(response['body'])
    assert 'RATE_LIMIT_EXCEEDED' in body['error']['code']


# Test: BedrockAPIError handling
@patch('src.lambda_handler.ForecastEngine')
@patch('src.lambda_handler.get_dynamodb_client')
def test_bedrock_api_error(mock_get_db, mock_engine_class):
    """Test handling of BedrockAPIError."""
    mock_engine = Mock()
    mock_engine.generate_forecast.side_effect = BedrockAPIError("API unavailable")
    mock_engine_class.return_value = mock_engine
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/cost-forecast',
        'queryStringParameters': {}
    }
    
    response = handle_forecast_request(event)
    
    assert response['statusCode'] == 503
    body = json.loads(response['body'])
    assert 'SERVICE_UNAVAILABLE' in body['error']['code']


# Test: Backward compatibility - Phase 1 fetch endpoint
@patch('src.lambda_handler.fetch_cost_data')
@patch('src.lambda_handler.store_cost_data')
def test_phase1_fetch_endpoint_still_works(mock_store, mock_fetch):
    """Test that Phase 1 /fetch endpoint still works after Phase 2 deployment."""
    mock_fetch.return_value = []
    
    event = {
        'httpMethod': 'POST',
        'path': '/fetch',
        'body': json.dumps({'startDate': '2024-01-01', 'endDate': '2024-01-31'})
    }
    
    response = handler(event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True


# Test: Backward compatibility - Phase 1 query endpoint
@patch('src.lambda_handler.query_cost_data')
def test_phase1_query_endpoint_still_works(mock_query):
    """Test that Phase 1 /cost-data endpoint still works after Phase 2 deployment."""
    mock_query.return_value = []
    
    event = {
        'httpMethod': 'GET',
        'path': '/cost-data',
        'queryStringParameters': {}
    }
    
    response = handler(event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True


# Test: Backward compatibility - Phase 1.5 estimation endpoint
@patch('src.lambda_handler.CloudWatchMetricsCollector')
@patch('src.lambda_handler.PricingManager')
@patch('src.lambda_handler.CostEstimator')
def test_phase15_estimation_endpoint_still_works(mock_estimator_class, mock_pricing_class, mock_collector_class):
    """Test that Phase 1.5 /cost-estimation/current endpoint still works."""
    mock_estimator = Mock()
    mock_estimator.estimate_current_cost.return_value = Mock(
        service='total',
        estimated_cost=100.0,
        currency='USD',
        confidence_lower=90.0,
        confidence_upper=110.0,
        timestamp=datetime.now(UTC),
        period_start=datetime.now(UTC),
        period_end=datetime.now(UTC),
        metrics_count=5
    )
    mock_estimator_class.return_value = mock_estimator
    
    event = {
        'httpMethod': 'GET',
        'path': '/cost-estimation/current',
        'queryStringParameters': {}
    }
    
    response = handler(event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
