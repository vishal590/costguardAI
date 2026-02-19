"""
Property-based tests for Lambda handler.

Feature: cost-data-pipeline
"""
import pytest
import json
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.lambda_handler import handler, handle_fetch, handle_query, create_error_response


# Feature: cost-data-pipeline, Property 12: Successful fetch responses contain complete summaries
@given(
    st.integers(min_value=0, max_value=100),
    st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_successful_fetch_responses_contain_complete_summaries(num_records, total_cost):
    """
    Property 12: Successful fetch responses contain complete summaries
    For any successful fetch operation, the response should contain success: true,
    a message, and a data object with recordsProcessed, dateRange (start and end),
    totalCost, and services array.
    
    Validates: Requirements 8.1, 8.2
    """
    # Create mock records
    mock_records = [
        Mock(
            date='2025-01-01',
            service=f'Service-{i}',
            blended_cost=total_cost / max(num_records, 1),
            unblended_cost=total_cost / max(num_records, 1),
            currency='USD',
            unit='USD'
        )
        for i in range(num_records)
    ]
    
    # Mock the services
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
            
            response = handler(event, None)
            
            # Verify response structure
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            assert body['success'] is True
            assert 'message' in body
            assert 'data' in body
            
            # Verify data contains all required fields
            data = body['data']
            assert 'recordsProcessed' in data
            assert 'dateRange' in data
            assert 'start' in data['dateRange']
            assert 'end' in data['dateRange']
            assert 'totalCost' in data
            assert 'services' in data
            
            # Verify values
            assert data['recordsProcessed'] == num_records
            assert isinstance(data['services'], list)


# Feature: cost-data-pipeline, Property 13: Successful query responses contain cost records
@given(st.integers(min_value=0, max_value=50))
@settings(max_examples=100)
def test_successful_query_responses_contain_cost_records(num_records):
    """
    Property 13: Successful query responses contain cost records
    For any successful query operation, the response should contain success: true,
    a data array with cost records, and a count field.
    
    Validates: Requirements 8.3
    """
    # Create mock records
    mock_records = [
        Mock(
            date='2025-01-01',
            service=f'Service-{i}',
            blended_cost=100.0,
            unblended_cost=100.0,
            currency='USD'
        )
        for i in range(num_records)
    ]
    
    # Mock the query service
    with patch('src.lambda_handler.query_cost_data', return_value=mock_records):
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-data',
            'queryStringParameters': {
                'startDate': '2025-01-01',
                'limit': '100'
            }
        }
        
        response = handler(event, None)
        
        # Verify response structure
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['success'] is True
        assert 'data' in body
        assert 'count' in body
        
        # Verify data is an array
        assert isinstance(body['data'], list)
        assert body['count'] == num_records
        assert len(body['data']) == num_records


# Feature: cost-data-pipeline, Property 14: Error responses contain structured error information
@given(
    st.integers(min_value=400, max_value=599),
    st.text(min_size=1, max_size=50),
    st.text(min_size=1, max_size=100)
)
@settings(max_examples=100)
def test_error_responses_contain_structured_error_information(status_code, error_code, message):
    """
    Property 14: Error responses contain structured error information
    For any failed operation, the response should contain success: false and an error object
    with code, message, and optional details fields.
    
    Validates: Requirements 8.4, 8.5
    """
    response = create_error_response(status_code, error_code, message)
    
    # Verify response structure
    assert response['statusCode'] == status_code
    body = json.loads(response['body'])
    
    assert body['success'] is False
    assert 'error' in body
    
    # Verify error object
    error = body['error']
    assert 'code' in error
    assert 'message' in error
    assert error['code'] == error_code
    assert error['message'] == message


# Feature: cost-data-pipeline, Property 15: Cost records in responses contain all required fields
@given(st.integers(min_value=1, max_value=20))
@settings(max_examples=100)
def test_cost_records_in_responses_contain_all_required_fields(num_records):
    """
    Property 15: Cost records in responses contain all required fields
    For any cost record returned in a query response, it should contain date, service,
    blendedCost, unblendedCost, and currency fields.
    
    Validates: Requirements 8.6
    """
    # Create mock records
    mock_records = [
        Mock(
            date='2025-01-01',
            service=f'Service-{i}',
            blended_cost=100.0 + i,
            unblended_cost=100.0 + i,
            currency='USD'
        )
        for i in range(num_records)
    ]
    
    # Mock the query service
    with patch('src.lambda_handler.query_cost_data', return_value=mock_records):
        event = {
            'httpMethod': 'GET',
            'path': '/api/cost-data',
            'queryStringParameters': {
                'startDate': '2025-01-01'
            }
        }
        
        response = handler(event, None)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Verify each record has all required fields
        for record in body['data']:
            assert 'date' in record
            assert 'service' in record
            assert 'blendedCost' in record
            assert 'unblendedCost' in record
            assert 'currency' in record


# Feature: cost-data-pipeline, Property 19: Cost summaries calculate correct totals
@given(
    st.lists(
        st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=50
    )
)
@settings(max_examples=100)
def test_cost_summaries_calculate_correct_totals(costs):
    """
    Property 19: Cost summaries calculate correct totals
    For any set of cost records, the summary calculation should produce the correct
    total cost (sum of all blendedCost values), unique service count, and total record count.
    
    Validates: Requirements 12.1, 12.2, 12.3, 12.5
    """
    # Create mock records
    mock_records = [
        Mock(
            date='2025-01-01',
            service=f'Service-{i % 5}',  # 5 unique services
            blended_cost=cost,
            unblended_cost=cost,
            currency='USD',
            unit='USD'
        )
        for i, cost in enumerate(costs)
    ]
    
    # Mock the services
    with patch('src.lambda_handler.fetch_cost_data', return_value=mock_records):
        with patch('src.lambda_handler.store_cost_data'):
            event = {
                'httpMethod': 'POST',
                'path': '/api/cost-data/fetch',
                'body': json.dumps({
                    'startDate': '2025-01-01',
                    'endDate': '2025-01-31'
                })
            }
            
            response = handler(event, None)
            
            # Verify response
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            data = body['data']
            
            # Verify record count
            assert data['recordsProcessed'] == len(costs)
            
            # Verify total cost (allow small floating point differences)
            expected_total = sum(costs)
            assert abs(data['totalCost'] - expected_total) < 0.01
            
            # Verify service count
            if costs:
                expected_services = min(5, len(costs))  # Max 5 unique services
                assert len(data['services']) == expected_services
