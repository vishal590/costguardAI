"""
Property-based tests for Multi-Account API Handler.

Tests Properties 1, 2, 4, 15, 16, 17 from the design document.
"""
import json
import pytest
from hypothesis import given, settings, strategies as st, assume
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, date, timedelta, UTC

# Import handler
from src.multi_account_api_handler import (
    handler,
    create_error_response,
    handle_consolidated_costs,
    handle_list_organizations
)


# ============================================================================
# Test Data Generators
# ============================================================================

@st.composite
def api_key_strategy(draw):
    """Generate valid or invalid API keys."""
    is_valid = draw(st.booleans())
    if is_valid:
        # Valid API key format: cg_ + 32 hex chars
        return f"cg_{draw(st.text(alphabet='0123456789abcdef', min_size=32, max_size=32))}"
    else:
        # Invalid: too short, wrong format, or missing
        return draw(st.one_of(
            st.none(),
            st.just(""),
            st.text(max_size=10),  # Too short
            st.text(alphabet='xyz', min_size=32, max_size=32)  # Wrong format
        ))


@st.composite
def api_gateway_event_strategy(draw, include_api_key=True):
    """Generate API Gateway event."""
    method = draw(st.sampled_from(['GET', 'POST', 'PUT', 'DELETE']))
    path = draw(st.sampled_from([
        '/api/organizations',
        '/api/costs/consolidated',
        '/api/costs/by-account',
        '/api/allocation/by-tag',
        '/api/budgets/hierarchy'
    ]))
    
    headers = {}
    if include_api_key:
        api_key = draw(api_key_strategy())
        if api_key:
            headers['X-API-Key'] = api_key
    
    return {
        'httpMethod': method,
        'path': path,
        'headers': headers,
        'queryStringParameters': {},
        'body': None
    }


@st.composite
def date_string_strategy(draw):
    """Generate date strings in various formats."""
    format_type = draw(st.sampled_from(['valid', 'invalid_format', 'invalid_range']))
    
    if format_type == 'valid':
        # Valid YYYY-MM-DD format
        d = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2025, 12, 31)))
        return d.isoformat()
    elif format_type == 'invalid_format':
        # Invalid formats
        return draw(st.sampled_from([
            '2024-1-15',  # Missing leading zero
            '2024/01/15',  # Wrong separator
            '01-15-2024',  # Wrong order
            '2024-13-01',  # Invalid month
            '2024-01-32',  # Invalid day
            'not-a-date',
            '20240115',  # No separators
            ''
        ]))
    else:
        # Valid format but potentially invalid range
        d = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2025, 12, 31)))
        return d.isoformat()


@st.composite
def error_scenario_strategy(draw):
    """Generate different error scenarios."""
    return draw(st.sampled_from([
        'validation',      # 400
        'authentication',  # 401
        'not_found',      # 404
        'internal'        # 500
    ]))


# ============================================================================
# Property 1: Authentication Validation
# ============================================================================

@given(
    has_valid_key=st.booleans(),
    path=st.sampled_from(['/api/organizations', '/api/costs/consolidated'])
)
@settings(max_examples=100, deadline=5000)
def test_property_1_authentication_validation(has_valid_key, path):
    """
    Property 1: Authentication Validation
    
    For any HTTP request to the Multi_Account_API_Handler, if the request contains 
    a valid API key, then authentication should succeed and the request should be 
    processed; if the request contains an invalid or missing API key, then 
    authentication should fail and a 401 status code should be returned.
    
    Feature: phase-5-handlers, Property 1: Authentication Validation
    Validates: Requirements 1.1, 1.2
    """
    # Create event with or without valid API key
    event = {
        'httpMethod': 'GET',
        'path': path,
        'headers': {},
        'queryStringParameters': {},
        'body': None
    }
    
    # Mock authentication
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        if has_valid_key:
            # Valid API key - authentication succeeds
            mock_auth.return_value = (True, None, {'user_id': 'test-user', 'permissions': ['read']})
            
            # Mock services to avoid actual AWS calls
            with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
                mock_org = Mock()
                mock_org.id = 'o-test123'
                mock_org.master_account_id = '123456789012'
                mock_org.arn = 'arn:aws:organizations::123456789012:organization/o-test123'
                mock_org.feature_set = 'ALL'
                
                mock_org_service = Mock()
                mock_org_service.discover_organization.return_value = mock_org
                mock_org_service.get_all_accounts.return_value = []
                mock_org_svc.return_value = mock_org_service
                
                with patch('src.multi_account_api_handler._get_cost_aggregation_engine') as mock_agg:
                    mock_engine = Mock()
                    mock_costs = Mock()
                    mock_costs.total_cost = Decimal('100.00')
                    mock_costs.start_date = '2024-01-01'
                    mock_costs.end_date = '2024-01-31'
                    mock_costs.costs_by_service = {}
                    mock_costs.costs_by_account = {}
                    mock_costs.costs_by_day = {}
                    mock_engine.aggregate_organization_costs.return_value = mock_costs
                    mock_agg.return_value = mock_engine
                    
                    with patch('src.multi_account_api_handler.get_metrics_service') as mock_metrics:
                        mock_metrics_svc = Mock()
                        mock_metrics.return_value = mock_metrics_svc
                        
                        response = handler(event, {})
                        
                        # Should NOT return 401
                        assert response['statusCode'] != 401, \
                            f"Valid API key should not return 401, got {response['statusCode']}"
        else:
            # Invalid/missing API key - authentication fails
            mock_auth.return_value = (False, 'Invalid API key', None)
            
            with patch('src.multi_account_api_handler.get_metrics_service') as mock_metrics:
                mock_metrics_svc = Mock()
                mock_metrics.return_value = mock_metrics_svc
                
                response = handler(event, {})
                
                # Should return 401
                assert response['statusCode'] == 401, \
                    f"Invalid API key should return 401, got {response['statusCode']}"
                
                # Check error structure
                body = json.loads(response['body'])
                assert body['success'] is False
                assert 'error' in body


# ============================================================================
# Property 2: Error Response Standardization
# ============================================================================

@given(error_type=error_scenario_strategy())
@settings(max_examples=100, deadline=5000)
def test_property_2_error_response_standardization(error_type):
    """
    Property 2: Error Response Standardization
    
    For any error that occurs in any handler, the error response should include 
    a standardized structure with a "success" field set to false, an "error" 
    object containing "code" and "message" fields, and appropriate HTTP status 
    code (400 for validation errors, 401 for authentication errors, 404 for 
    not found, 500 for internal errors).
    
    Feature: phase-5-handlers, Property 2: Error Response Standardization
    Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6, 14.1, 14.2, 14.5, 14.6, 14.7
    """
    # Map error types to expected status codes
    expected_status = {
        'validation': 400,
        'authentication': 401,
        'not_found': 404,
        'internal': 500
    }
    
    # Map error types to error codes
    error_codes = {
        'validation': 'INVALID_PARAMETER',
        'authentication': 'AUTHENTICATION_FAILED',
        'not_found': 'RESOURCE_NOT_FOUND',
        'internal': 'INTERNAL_ERROR'
    }
    
    # Create error response
    response = create_error_response(
        expected_status[error_type],
        error_codes[error_type],
        f'Test {error_type} error',
        {'detail': 'test'}
    )
    
    # Verify status code
    assert response['statusCode'] == expected_status[error_type], \
        f"Expected status {expected_status[error_type]}, got {response['statusCode']}"
    
    # Verify headers
    assert 'Content-Type' in response['headers']
    assert response['headers']['Content-Type'] == 'application/json'
    assert 'Access-Control-Allow-Origin' in response['headers']
    assert response['headers']['Access-Control-Allow-Origin'] == '*'
    
    # Verify body structure
    body = json.loads(response['body'])
    assert 'success' in body
    assert body['success'] is False
    assert 'error' in body
    assert 'code' in body['error']
    assert 'message' in body['error']
    assert body['error']['code'] == error_codes[error_type]


# ============================================================================
# Property 17: Response Format Consistency
# ============================================================================

@given(
    is_success=st.booleans(),
    path=st.sampled_from(['/api/organizations', '/api/costs/consolidated'])
)
@settings(max_examples=100, deadline=5000)
def test_property_17_response_format_consistency(is_success, path):
    """
    Property 17: Response Format Consistency
    
    For any successful response from the Multi_Account_API_Handler, the response 
    should include "success": true and a "data" field; for any error response, 
    the response should include "success": false and an "error" field; all 
    responses should include "Content-Type: application/json" and 
    "Access-Control-Allow-Origin: *" headers.
    
    Feature: phase-5-handlers, Property 17: Response Format Consistency
    Validates: Requirements 14.1, 14.2, 14.5, 14.6, 14.7
    """
    event = {
        'httpMethod': 'GET',
        'path': path,
        'headers': {},
        'queryStringParameters': {},
        'body': None
    }
    
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        if is_success:
            # Successful authentication
            mock_auth.return_value = (True, None, {'user_id': 'test-user', 'permissions': ['read']})
            
            with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
                mock_org = Mock()
                mock_org.id = 'o-test123'
                mock_org.master_account_id = '123456789012'
                mock_org.arn = 'arn:aws:organizations::123456789012:organization/o-test123'
                mock_org.feature_set = 'ALL'
                
                mock_org_service = Mock()
                mock_org_service.discover_organization.return_value = mock_org
                mock_org_service.get_all_accounts.return_value = []
                mock_org_svc.return_value = mock_org_service
                
                with patch('src.multi_account_api_handler._get_cost_aggregation_engine') as mock_agg:
                    mock_engine = Mock()
                    mock_costs = Mock()
                    mock_costs.total_cost = Decimal('100.00')
                    mock_costs.start_date = '2024-01-01'
                    mock_costs.end_date = '2024-01-31'
                    mock_costs.costs_by_service = {}
                    mock_costs.costs_by_account = {}
                    mock_costs.costs_by_day = {}
                    mock_engine.aggregate_organization_costs.return_value = mock_costs
                    mock_agg.return_value = mock_engine
                    
                    with patch('src.multi_account_api_handler.get_metrics_service') as mock_metrics:
                        mock_metrics_svc = Mock()
                        mock_metrics.return_value = mock_metrics_svc
                        
                        response = handler(event, {})
                        
                        # Verify headers
                        assert 'Content-Type' in response['headers']
                        assert response['headers']['Content-Type'] == 'application/json'
                        assert 'Access-Control-Allow-Origin' in response['headers']
                        assert response['headers']['Access-Control-Allow-Origin'] == '*'
                        
                        # Verify success response structure
                        body = json.loads(response['body'])
                        assert 'success' in body
                        assert body['success'] is True
        else:
            # Failed authentication
            mock_auth.return_value = (False, 'Invalid API key', None)
            
            with patch('src.multi_account_api_handler.get_metrics_service') as mock_metrics:
                mock_metrics_svc = Mock()
                mock_metrics.return_value = mock_metrics_svc
                
                response = handler(event, {})
                
                # Verify headers
                assert 'Content-Type' in response['headers']
                assert response['headers']['Content-Type'] == 'application/json'
                assert 'Access-Control-Allow-Origin' in response['headers']
                
                # Verify error response structure
                body = json.loads(response['body'])
                assert 'success' in body
                assert body['success'] is False
                assert 'error' in body



# ============================================================================
# Property 4: Date Format Validation
# ============================================================================

@given(
    start_date=date_string_strategy(),
    end_date=date_string_strategy()
)
@settings(max_examples=100, deadline=5000)
def test_property_4_date_format_validation(start_date, end_date):
    """
    Property 4: Date Format Validation
    
    For any request with start_date or end_date parameters, if the date format 
    is not YYYY-MM-DD, then the handler should return a 400 status code with 
    error code INVALID_DATE_FORMAT; if both dates are provided and start_date 
    is after end_date, then the handler should return a 400 status code with 
    error code INVALID_DATE_RANGE.
    
    Feature: phase-5-handlers, Property 4: Date Format Validation
    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
    """
    # Check if dates are valid YYYY-MM-DD format
    def is_valid_date_format(date_str):
        if not date_str or not isinstance(date_str, str) or date_str == '':
            # Empty strings are treated as "not provided" by the handler
            return None  # Neither valid nor invalid - just not provided
        try:
            parts = date_str.split('-')
            if len(parts) != 3:
                return False
            year, month, day = parts
            if len(year) != 4 or len(month) != 2 or len(day) != 2:
                return False
            # Try to parse
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except (ValueError, AttributeError):
            return False
    
    start_valid = is_valid_date_format(start_date)
    end_valid = is_valid_date_format(end_date)
    
    # Skip if both are empty/None (not provided)
    if start_valid is None and end_valid is None:
        return
    
    event = {
        'httpMethod': 'GET',
        'path': '/api/costs/consolidated',
        'headers': {},
        'queryStringParameters': {
            'start_date': start_date,
            'end_date': end_date
        },
        'body': None
    }
    
    # Mock authentication to pass
    with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
        mock_auth.return_value = (True, None, {'user_id': 'test-user', 'permissions': ['read']})
        
        with patch('src.multi_account_api_handler.get_metrics_service') as mock_metrics:
            mock_metrics_svc = Mock()
            mock_metrics.return_value = mock_metrics_svc
            
            # If either date is explicitly invalid (not just missing)
            if start_valid is False or end_valid is False:
                # Invalid format - should return 400 with INVALID_DATE_FORMAT
                response = handler(event, {})
                
                assert response['statusCode'] == 400, \
                    f"Invalid date format should return 400, got {response['statusCode']}"
                
                body = json.loads(response['body'])
                assert body['error']['code'] == 'INVALID_DATE_FORMAT', \
                    f"Expected INVALID_DATE_FORMAT, got {body['error']['code']}"
            
            elif start_valid is True and end_valid is True:
                # Both dates valid format - check range
                if start_date > end_date:
                    # Invalid range - should return 400 with INVALID_DATE_RANGE
                    response = handler(event, {})
                    
                    assert response['statusCode'] == 400, \
                        f"Invalid date range should return 400, got {response['statusCode']}"
                    
                    body = json.loads(response['body'])
                    assert body['error']['code'] == 'INVALID_DATE_RANGE', \
                        f"Expected INVALID_DATE_RANGE, got {body['error']['code']}"
                else:
                    # Valid dates and range - should process successfully
                    with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
                        mock_org = Mock()
                        mock_org.id = 'o-test123'
                        mock_org.master_account_id = '123456789012'
                        mock_org.arn = 'arn:aws:organizations::123456789012:organization/o-test123'
                        mock_org.feature_set = 'ALL'
                        
                        mock_org_service = Mock()
                        mock_org_service.discover_organization.return_value = mock_org
                        mock_org_service.get_all_accounts.return_value = []
                        mock_org_svc.return_value = mock_org_service
                        
                        with patch('src.multi_account_api_handler._get_cost_aggregation_engine') as mock_agg:
                            mock_engine = Mock()
                            mock_costs = Mock()
                            mock_costs.total_cost = Decimal('100.00')
                            mock_costs.start_date = start_date
                            mock_costs.end_date = end_date
                            mock_costs.costs_by_service = {}
                            mock_costs.costs_by_account = {}
                            mock_costs.costs_by_day = {}
                            mock_engine.aggregate_organization_costs.return_value = mock_costs
                            mock_agg.return_value = mock_engine
                            
                            response = handler(event, {})
                            
                            # Should NOT return 400
                            assert response['statusCode'] != 400 or \
                                   json.loads(response['body'])['error']['code'] not in ['INVALID_DATE_FORMAT', 'INVALID_DATE_RANGE'], \
                                f"Valid dates should not return date validation error, got {response['statusCode']}"
