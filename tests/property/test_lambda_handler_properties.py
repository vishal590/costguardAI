"""
Property-based tests for Lambda handler.

Tests Property 15: Backward Compatibility
Validates: Requirements 15.1-15.5
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, MagicMock
import json

from src.lambda_handler import handler


# Feature: automated-cost-prevention, Property 15: Backward Compatibility


class TestProperty15BackwardCompatibility:
    """
    Property 15: Backward Compatibility
    
    For any Phase 1, 1.5, or 2 API endpoint, it should continue to function 
    unchanged after Phase 3 deployment.
    
    Validates: Requirements 15.1-15.5
    """
    
    @settings(max_examples=100)
    @given(
        start_date=st.dates().map(lambda d: d.strftime('%Y-%m-%d')),
        end_date=st.dates().map(lambda d: d.strftime('%Y-%m-%d')),
        granularity=st.sampled_from(['DAILY', 'MONTHLY', 'HOURLY'])
    )
    def test_phase1_fetch_endpoint_unchanged(self, start_date, end_date, granularity):
        """
        Test that Phase 1 /fetch endpoint continues to work.
        
        Property: For any valid fetch request, the endpoint should return 
        a successful response with the expected structure.
        """
        # Create event for Phase 1 fetch endpoint
        event = {
            'httpMethod': 'POST',
            'path': '/api/fetch',
            'body': json.dumps({
                'startDate': start_date,
                'endDate': end_date,
                'granularity': granularity
            })
        }
        
        # Mock the fetch_cost_data and store_cost_data functions
        with patch('src.lambda_handler.fetch_cost_data') as mock_fetch, \
             patch('src.lambda_handler.store_cost_data') as mock_store:
            
            # Setup mock to return empty list (valid response)
            mock_fetch.return_value = []
            
            # Call handler
            response = handler(event, None)
            
            # Verify response structure is unchanged
            assert 'statusCode' in response
            assert 'headers' in response
            assert 'body' in response
            assert response['headers']['Content-Type'] == 'application/json'
            
            # Parse body
            body = json.loads(response['body'])
            
            # Verify Phase 1 response structure
            if response['statusCode'] == 200:
                assert 'success' in body
                assert 'data' in body or 'message' in body
    
    @settings(max_examples=100)
    @given(
        service=st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds', None]),
        limit=st.integers(min_value=1, max_value=1000)
    )
    def test_phase1_query_endpoint_unchanged(self, service, limit):
        """
        Test that Phase 1 /cost-data endpoint continues to work.
        
        Property: For any valid query request, the endpoint should return 
        a successful response with the expected structure.
        """
        # Create event for Phase 1 query endpoint
        query_params = {'limit': str(limit)}
        if service:
            query_params['service'] = service
        
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-data',
            'queryStringParameters': query_params
        }
        
        # Mock the query_cost_data function
        with patch('src.lambda_handler.query_cost_data') as mock_query:
            # Setup mock to return empty list
            mock_query.return_value = []
            
            # Call handler
            response = handler(event, None)
            
            # Verify response structure is unchanged
            assert 'statusCode' in response
            assert response['statusCode'] == 200
            assert 'headers' in response
            assert 'body' in response
            
            # Parse body
            body = json.loads(response['body'])
            
            # Verify Phase 1 response structure
            assert 'success' in body
            assert 'data' in body
            assert 'count' in body
            assert isinstance(body['data'], list)
    
    @settings(max_examples=100)
    @given(
        hours=st.integers(min_value=1, max_value=168)
    )
    def test_phase15_estimation_current_endpoint_unchanged(self, hours):
        """
        Test that Phase 1.5 /cost-estimation/current endpoint continues to work.
        
        Property: For any valid estimation request, the endpoint should return 
        a successful response with the expected structure.
        """
        # Create event for Phase 1.5 estimation endpoint
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-estimation/current',
            'queryStringParameters': {'hours': str(hours)}
        }
        
        # Mock the Phase 1.5 services
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector, \
             patch('src.lambda_handler.PricingManager') as mock_pricing, \
             patch('src.lambda_handler.CostEstimator') as mock_estimator:
            
            # Setup mocks
            mock_collector_instance = Mock()
            mock_collector_instance.collect_metrics.return_value = {}
            mock_collector.return_value = mock_collector_instance
            
            mock_pricing_instance = Mock()
            mock_pricing.return_value = mock_pricing_instance
            
            mock_estimator_instance = Mock()
            mock_estimator.return_value = mock_estimator_instance
            
            # Call handler
            response = handler(event, None)
            
            # Verify response structure is unchanged
            assert 'statusCode' in response
            assert response['statusCode'] == 200
            assert 'headers' in response
            assert 'body' in response
            
            # Parse body
            body = json.loads(response['body'])
            
            # Verify Phase 1.5 response structure
            assert 'success' in body
            assert 'estimates' in body
            assert 'totalCost' in body
            assert isinstance(body['estimates'], list)
    
    @settings(max_examples=100)
    @given(
        service=st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds']),
        hours=st.integers(min_value=1, max_value=168)
    )
    def test_phase15_estimation_service_endpoint_unchanged(self, service, hours):
        """
        Test that Phase 1.5 /cost-estimation/service/{service} endpoint continues to work.
        
        Property: For any valid service estimation request, the endpoint should return 
        a successful response with the expected structure.
        """
        # Create event for Phase 1.5 service estimation endpoint
        event = {
            'httpMethod': 'GET',
            'path': f'/api/cost-estimation/service/{service}',
            'queryStringParameters': {'hours': str(hours)}
        }
        
        # Mock the Phase 1.5 services
        with patch('src.lambda_handler.CloudWatchMetricsCollector') as mock_collector, \
             patch('src.lambda_handler.PricingManager') as mock_pricing, \
             patch('src.lambda_handler.CostEstimator') as mock_estimator:
            
            # Setup mocks
            mock_collector_instance = Mock()
            mock_collector_instance.collect_metrics.return_value = {service: []}
            mock_collector.return_value = mock_collector_instance
            
            mock_pricing_instance = Mock()
            mock_pricing.return_value = mock_pricing_instance
            
            mock_estimator_instance = Mock()
            mock_estimator.return_value = mock_estimator_instance
            
            # Call handler
            response = handler(event, None)
            
            # Verify response structure is unchanged
            assert 'statusCode' in response
            assert response['statusCode'] == 200
            assert 'headers' in response
            assert 'body' in response
            
            # Parse body
            body = json.loads(response['body'])
            
            # Verify Phase 1.5 response structure
            assert 'success' in body
            assert 'service' in body
    
    @settings(max_examples=100)
    @given(
        days=st.sampled_from([7, 14, 30]),
        granularity=st.sampled_from(['daily', 'weekly'])
    )
    def test_phase2_forecast_endpoint_unchanged(self, days, granularity):
        """
        Test that Phase 2 /cost-forecast endpoint continues to work.
        
        Property: For any valid forecast request, the endpoint should return 
        a successful response with the expected structure.
        """
        # Create event for Phase 2 forecast endpoint
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-forecast',
            'queryStringParameters': {
                'days': str(days),
                'granularity': granularity
            }
        }
        
        # Mock the Phase 2 services
        with patch('src.lambda_handler.get_dynamodb_client') as mock_dynamo, \
             patch('src.lambda_handler.BedrockClient') as mock_bedrock, \
             patch('src.lambda_handler.HistoricalDataRetriever') as mock_historical, \
             patch('src.lambda_handler.ForecastCacheManager') as mock_cache, \
             patch('src.lambda_handler.ForecastEngine') as mock_engine:
            
            # Setup mocks
            mock_engine_instance = Mock()
            mock_forecast_response = Mock()
            mock_forecast_response.success = True
            mock_forecast_response.forecast_data = []
            mock_forecast_response.metadata = Mock(
                timestamp='2024-01-01T00:00:00Z',
                forecast_horizon=days,
                granularity=granularity,
                model_used='test',
                service=None,
                services_included=[],
                cache_hit=False,
                historical_data_days=90
            )
            mock_engine_instance.generate_forecast.return_value = mock_forecast_response
            mock_engine.return_value = mock_engine_instance
            
            # Call handler
            response = handler(event, None)
            
            # Verify response structure is unchanged
            assert 'statusCode' in response
            assert response['statusCode'] == 200
            assert 'headers' in response
            assert 'body' in response
            
            # Parse body
            body = json.loads(response['body'])
            
            # Verify Phase 2 response structure
            assert 'success' in body
            assert 'forecast_data' in body
            assert 'metadata' in body
            assert isinstance(body['forecast_data'], list)
    
    @settings(max_examples=100)
    @given(
        service=st.sampled_from(['ec2', 'lambda', 'dynamodb', 's3', 'rds']),
        days=st.sampled_from([7, 14, 30]),
        granularity=st.sampled_from(['daily', 'weekly'])
    )
    def test_phase2_forecast_service_endpoint_unchanged(self, service, days, granularity):
        """
        Test that Phase 2 /cost-forecast/service/{service} endpoint continues to work.
        
        Property: For any valid service forecast request, the endpoint should return 
        a successful response with the expected structure.
        """
        # Create event for Phase 2 service forecast endpoint
        event = {
            'httpMethod': 'GET',
            'path': f'/api/cost-forecast/service/{service}',
            'queryStringParameters': {
                'days': str(days),
                'granularity': granularity
            }
        }
        
        # Mock the Phase 2 services
        with patch('src.lambda_handler.get_dynamodb_client') as mock_dynamo, \
             patch('src.lambda_handler.BedrockClient') as mock_bedrock, \
             patch('src.lambda_handler.HistoricalDataRetriever') as mock_historical, \
             patch('src.lambda_handler.ForecastCacheManager') as mock_cache, \
             patch('src.lambda_handler.ForecastEngine') as mock_engine:
            
            # Setup mocks
            mock_engine_instance = Mock()
            mock_forecast_response = Mock()
            mock_forecast_response.success = True
            mock_forecast_response.forecast_data = []
            mock_forecast_response.metadata = Mock(
                timestamp='2024-01-01T00:00:00Z',
                forecast_horizon=days,
                granularity=granularity,
                model_used='test',
                service=service,
                services_included=[service],
                cache_hit=False,
                historical_data_days=90
            )
            mock_engine_instance.generate_forecast.return_value = mock_forecast_response
            mock_engine.return_value = mock_engine_instance
            
            # Call handler
            response = handler(event, None)
            
            # Verify response structure is unchanged
            assert 'statusCode' in response
            assert response['statusCode'] == 200
            assert 'headers' in response
            assert 'body' in response
            
            # Parse body
            body = json.loads(response['body'])
            
            # Verify Phase 2 response structure
            assert 'success' in body
            assert 'forecast_data' in body
            assert 'metadata' in body
            assert body['metadata']['service'] == service
    
    @settings(max_examples=100)
    @given(
        phase=st.sampled_from([1, 1.5, 2]),
        method=st.sampled_from(['GET', 'POST'])
    )
    def test_all_phases_return_cors_headers(self, phase, method):
        """
        Test that all phase endpoints return CORS headers.
        
        Property: For any endpoint from any phase, the response should include 
        CORS headers for cross-origin access.
        """
        # Select endpoint based on phase
        if phase == 1:
            if method == 'POST':
                event = {
                    'httpMethod': 'POST',
                    'path': '/api/fetch',
                    'body': json.dumps({
                        'startDate': '2024-01-01',
                        'endDate': '2024-01-31',
                        'granularity': 'DAILY'
                    })
                }
            else:
                event = {
                    'httpMethod': 'GET',
                    'path': '/api/cost-data',
                    'queryStringParameters': {'limit': '10'}
                }
        elif phase == 1.5:
            event = {
                'httpMethod': 'GET',
                'path': '/api/cost-estimation/current',
                'queryStringParameters': {'hours': '1'}
            }
        else:  # phase == 2
            event = {
                'httpMethod': 'GET',
                'path': '/api/cost-forecast',
                'queryStringParameters': {'days': '7', 'granularity': 'daily'}
            }
        
        # Mock all necessary services
        with patch('src.lambda_handler.fetch_cost_data', return_value=[]), \
             patch('src.lambda_handler.store_cost_data'), \
             patch('src.lambda_handler.query_cost_data', return_value=[]), \
             patch('src.lambda_handler.CloudWatchMetricsCollector'), \
             patch('src.lambda_handler.PricingManager'), \
             patch('src.lambda_handler.CostEstimator'), \
             patch('src.lambda_handler.get_dynamodb_client'), \
             patch('src.lambda_handler.BedrockClient'), \
             patch('src.lambda_handler.HistoricalDataRetriever'), \
             patch('src.lambda_handler.ForecastCacheManager'), \
             patch('src.lambda_handler.ForecastEngine'):
            
            # Call handler
            response = handler(event, None)
            
            # Verify CORS headers are present
            assert 'headers' in response
            assert 'Access-Control-Allow-Origin' in response['headers']
            assert response['headers']['Access-Control-Allow-Origin'] == '*'
