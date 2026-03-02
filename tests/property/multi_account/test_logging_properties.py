"""
Property-based tests for request/response logging and exception logging.

Tests Properties 3 and 15 from the design document.
"""
import json
import logging
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from unittest.mock import Mock, patch, MagicMock, call
from decimal import Decimal
from datetime import datetime, UTC

# Import handler
from src.multi_account_api_handler import handler


# ============================================================================
# Test Data Generators
# ============================================================================

@st.composite
def api_event_strategy(draw):
    """Generate API Gateway events."""
    method = draw(st.sampled_from(['GET', 'POST']))
    path = draw(st.sampled_from([
        '/api/organizations',
        '/api/costs/consolidated',
        '/api/costs/by-account',
        '/api/allocation/by-tag'
    ]))
    
    return {
        'httpMethod': method,
        'path': path,
        'headers': {'X-API-Key': 'cg_test_key_12345678901234567890'},
        'queryStringParameters': {},
        'body': None
    }


@st.composite
def exception_scenario_strategy(draw):
    """Generate different exception scenarios."""
    return draw(st.sampled_from([
        ('ValueError', 'Invalid value provided'),
        ('KeyError', 'Missing required key'),
        ('RuntimeError', 'Runtime error occurred'),
        ('Exception', 'Generic exception')
    ]))


# ============================================================================
# Property 3: Request and Response Logging
# ============================================================================

@given(event=api_event_strategy())
@settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_3_request_response_logging(event, caplog):
    """
    Property 3: Request and Response Logging
    
    For any request processed by any handler, the handler should log the 
    incoming request at INFO level with sanitized parameters, and log the 
    outgoing response at INFO level with status code and duration.
    
    Feature: phase-5-handlers, Property 3: Request and Response Logging
    Validates: Requirements 5.7, 5.8
    """
    # Set up logging capture
    with caplog.at_level(logging.INFO):
        # Mock authentication
        with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
            mock_auth.return_value = (True, None, {'user_id': 'test-user', 'permissions': ['read']})
            
            # Mock services
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
                        
                        # Call handler
                        response = handler(event, {})
                        
                        # Verify request was logged at INFO level
                        request_logged = any(
                            'Received multi-account API event' in record.message and 
                            record.levelname == 'INFO'
                            for record in caplog.records
                        )
                        assert request_logged, "Request should be logged at INFO level"
                        
                        # Verify authentication was logged
                        auth_logged = any(
                            'Request authenticated for user' in record.message and 
                            record.levelname == 'INFO'
                            for record in caplog.records
                        )
                        assert auth_logged, "Authentication should be logged at INFO level"
                        
                        # Verify response includes status code
                        assert 'statusCode' in response, "Response should include status code"
                        
                        # Verify metrics service recorded response time
                        mock_metrics_svc.record_api_response_time.assert_called()
                        call_args = mock_metrics_svc.record_api_response_time.call_args
                        assert call_args is not None, "Response time should be recorded"
                        # Verify duration is positive
                        duration = call_args[0][1]
                        assert duration >= 0, "Duration should be non-negative"


# ============================================================================
# Property 15: Exception Logging with Stack Trace
# ============================================================================

@given(exception_info=exception_scenario_strategy())
@settings(max_examples=100, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_15_exception_logging_with_stack_trace(exception_info, caplog):
    """
    Property 15: Exception Logging with Stack Trace
    
    For any exception that occurs in any handler, the exception should be 
    logged to CloudWatch with a complete stack trace.
    
    Feature: phase-5-handlers, Property 15: Exception Logging with Stack Trace
    Validates: Requirements 5.1
    """
    exception_class_name, exception_message = exception_info
    
    # Create exception class dynamically
    if exception_class_name == 'ValueError':
        exception_class = ValueError
    elif exception_class_name == 'KeyError':
        exception_class = KeyError
    elif exception_class_name == 'RuntimeError':
        exception_class = RuntimeError
    else:
        exception_class = Exception
    
    # Create event
    event = {
        'httpMethod': 'GET',
        'path': '/api/organizations',
        'headers': {'X-API-Key': 'cg_test_key_12345678901234567890'},
        'queryStringParameters': {},
        'body': None
    }
    
    # Set up logging capture
    with caplog.at_level(logging.ERROR):
        # Mock authentication to pass
        with patch('src.multi_account_api_handler.authenticate_and_authorize') as mock_auth:
            mock_auth.return_value = (True, None, {'user_id': 'test-user', 'permissions': ['read']})
            
            # Mock service to raise exception
            with patch('src.multi_account_api_handler._get_organization_service') as mock_org_svc:
                mock_org_service = Mock()
                mock_org_service.discover_organization.side_effect = exception_class(exception_message)
                mock_org_svc.return_value = mock_org_service
                
                with patch('src.multi_account_api_handler.get_metrics_service') as mock_metrics:
                    mock_metrics_svc = Mock()
                    mock_metrics.return_value = mock_metrics_svc
                    
                    # Call handler - should catch exception and return error response
                    response = handler(event, {})
                    
                    # Verify exception was logged at ERROR level
                    error_logged = any(
                        'Error in handle_list_organizations' in record.message and 
                        record.levelname == 'ERROR'
                        for record in caplog.records
                    )
                    assert error_logged, "Exception should be logged at ERROR level"
                    
                    # Verify stack trace was included (exc_info=True in logging)
                    # Check that at least one ERROR record has exc_info
                    has_stack_trace = any(
                        record.levelname == 'ERROR' and 
                        record.exc_info is not None
                        for record in caplog.records
                    )
                    assert has_stack_trace, "Exception should be logged with stack trace (exc_info=True)"
                    
                    # Verify error response was returned
                    assert response['statusCode'] == 500, "Should return 500 for internal error"
                    body = json.loads(response['body'])
                    assert body['success'] is False, "Error response should have success=False"
                    assert 'error' in body, "Error response should include error field"
