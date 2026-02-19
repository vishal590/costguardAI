"""
Unit tests for Lambda handler.

Tests specific examples and edge cases for Lambda handler integration.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from src.lambda_handler import handler, handle_fetch, handle_query, create_error_response


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
