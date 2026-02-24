"""
Basic integration tests for Multi-Account API Handler.

Tests basic functionality without complex model dependencies.
"""
import json
import pytest
from unittest.mock import Mock, patch

from src.multi_account_api_handler import handler


class TestMultiAccountAPIBasic:
    """Basic integration tests for multi-account API endpoints."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.valid_api_key = "cg_test_api_key_12345678901234567890"
        self.valid_headers = {
            'X-API-Key': self.valid_api_key,
            'Content-Type': 'application/json'
        }
        
        self.user_context = {
            'api_key_id': 'key_123',
            'user_id': 'test_user',
            'permissions': ['read', 'write'],
            'rate_limit': 100
        }
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_authentication_failure(self, mock_auth):
        """Test authentication failure returns 401."""
        # Setup mock to return authentication failure
        mock_auth.return_value = (False, 'Invalid API key', None)
        
        # Create event without API key
        event = {
            'httpMethod': 'GET',
            'path': '/api/organizations',
            'headers': {},
            'queryStringParameters': None
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'AUTHENTICATION_FAILED'
        assert 'Invalid API key' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_rate_limit_exceeded(self, mock_auth):
        """Test rate limit exceeded returns 429."""
        # Setup mock to return rate limit exceeded
        mock_auth.return_value = (False, 'Rate limit exceeded. Maximum 100 requests per minute.', self.user_context)
        
        # Create event
        event = {
            'httpMethod': 'GET',
            'path': '/api/organizations',
            'headers': self.valid_headers,
            'queryStringParameters': None
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 429
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'RATE_LIMIT_EXCEEDED'
        assert 'Rate limit exceeded' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_invalid_endpoint(self, mock_auth):
        """Test invalid endpoint returns 400."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Create event with invalid path
        event = {
            'httpMethod': 'GET',
            'path': '/api/invalid/endpoint',
            'headers': self.valid_headers,
            'queryStringParameters': None
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'INVALID_REQUEST'
        assert 'Unsupported method' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_invalid_date_format(self, mock_auth):
        """Test invalid date format returns 400."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Create event with invalid date format
        event = {
            'httpMethod': 'GET',
            'path': '/api/costs/consolidated',
            'headers': self.valid_headers,
            'queryStringParameters': {
                'start_date': 'invalid-date',
                'end_date': '2024-01-31'
            }
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'INVALID_DATE_FORMAT'
        assert 'Invalid start date format' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)
    
    @patch('src.multi_account_api_handler.authenticate_and_authorize')
    def test_missing_required_parameter(self, mock_auth):
        """Test missing required parameter returns 400."""
        # Setup mocks
        mock_auth.return_value = (True, None, self.user_context)
        
        # Create event with missing required parameter
        event = {
            'httpMethod': 'POST',
            'path': '/api/allocation/rules',
            'headers': self.valid_headers,
            'body': json.dumps({
                'rule_type': 'percentage',
                'conditions': {'service': 'VPC'}
                # Missing rule_name
            })
        }
        
        # Call handler
        response = handler(event, {})
        
        # Verify response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] is False
        assert body['error']['code'] == 'MISSING_PARAMETER'
        assert 'rule_name is required' in body['error']['message']
        
        # Verify auth was called
        mock_auth.assert_called_once_with(event)
    
    def test_handler_import_works(self):
        """Test that the handler can be imported successfully."""
        # This test just verifies the import works
        assert handler is not None
        assert callable(handler)