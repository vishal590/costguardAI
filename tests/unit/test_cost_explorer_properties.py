"""
Property-based tests for Cost Explorer service.

Feature: cost-data-pipeline
"""
import pytest
from datetime import datetime
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, MagicMock

from src.services.cost_explorer import (
    fetch_cost_data,
    CostExplorerParams,
    _transform_response
)
from src.utils.types import CostRecord


# Strategy for generating valid dates
def valid_date_strategy():
    """Generate valid dates in YYYY-MM-DD format."""
    return st.dates(
        min_value=st.just('2020-01-01'),
        max_value=st.just('2025-12-31')
    ).map(lambda d: d.strftime('%Y-%m-%d'))


# Strategy for generating Cost Explorer API responses
def cost_explorer_response_strategy(num_pages: int = 1, services_per_page: int = 5):
    """Generate mock Cost Explorer API responses."""
    def generate_response(page_num):
        results = []
        for i in range(services_per_page):
            results.append({
                'TimePeriod': {
                    'Start': '2025-01-01',
                    'End': '2025-01-31'
                },
                'Groups': [
                    {
                        'Keys': [f'Service-{page_num}-{i}'],
                        'Metrics': {
                            'BlendedCost': {
                                'Amount': str(100.0 + i),
                                'Unit': 'USD'
                            },
                            'UnblendedCost': {
                                'Amount': str(100.0 + i),
                                'Unit': 'USD'
                            }
                        }
                    }
                ]
            })
        
        response = {
            'ResultsByTime': results
        }
        
        if page_num < num_pages - 1:
            response['NextPageToken'] = f'token-{page_num + 1}'
        
        return response
    
    return [generate_response(i) for i in range(num_pages)]


# Feature: cost-data-pipeline, Property 4: Cost Explorer pagination fetches all pages
@given(st.integers(min_value=1, max_value=5))
@settings(max_examples=100)
def test_cost_explorer_pagination_fetches_all_pages(num_pages):
    """
    Property 4: Cost Explorer pagination fetches all pages
    For any Cost Explorer API response with pagination, the fetch function should
    continue calling the API with NextPageToken until no token is returned,
    collecting all results.
    
    Validates: Requirements 1.5
    """
    # Generate mock responses
    responses = cost_explorer_response_strategy(num_pages=num_pages, services_per_page=3)
    
    # Create mock client
    mock_client = Mock()
    mock_client.get_cost_and_usage = Mock(side_effect=responses)
    
    # Fetch cost data
    params = CostExplorerParams(
        start_date='2025-01-01',
        end_date='2025-01-31',
        granularity='MONTHLY'
    )
    
    records = fetch_cost_data(params, client=mock_client)
    
    # Verify all pages were fetched
    assert mock_client.get_cost_and_usage.call_count == num_pages, \
        f"Expected {num_pages} API calls, got {mock_client.get_cost_and_usage.call_count}"
    
    # Verify all records were collected
    expected_records = num_pages * 3  # 3 services per page
    assert len(records) == expected_records, \
        f"Expected {expected_records} records, got {len(records)}"


# Feature: cost-data-pipeline, Property 22: Cost Explorer API calls include correct parameters
@given(
    st.dates(min_value=datetime(2020, 1, 1).date(), max_value=datetime(2025, 12, 31).date()).map(lambda d: d.strftime('%Y-%m-%d')),
    st.dates(min_value=datetime(2020, 1, 1).date(), max_value=datetime(2025, 12, 31).date()).map(lambda d: d.strftime('%Y-%m-%d')),
    st.sampled_from(['DAILY', 'MONTHLY', 'HOURLY'])
)
@settings(max_examples=100)
def test_cost_explorer_api_calls_include_correct_parameters(start_date, end_date, granularity):
    """
    Property 22: Cost Explorer API calls include correct parameters
    For any fetch operation, the Cost Explorer API call should include the correct
    TimePeriod (start and end dates), Granularity, Metrics (BlendedCost and UnblendedCost),
    and GroupBy (SERVICE dimension).
    
    Validates: Requirements 1.1, 1.3, 1.4
    """
    # Create mock client
    mock_client = Mock()
    mock_response = {
        'ResultsByTime': []
    }
    mock_client.get_cost_and_usage = Mock(return_value=mock_response)
    
    # Fetch cost data
    params = CostExplorerParams(
        start_date=start_date,
        end_date=end_date,
        granularity=granularity
    )
    
    records = fetch_cost_data(params, client=mock_client)
    
    # Verify API was called
    assert mock_client.get_cost_and_usage.call_count == 1
    
    # Get the call arguments
    call_args = mock_client.get_cost_and_usage.call_args
    kwargs = call_args[1] if call_args else {}
    
    # Verify TimePeriod
    assert 'TimePeriod' in kwargs
    assert kwargs['TimePeriod']['Start'] == start_date
    assert kwargs['TimePeriod']['End'] == end_date
    
    # Verify Granularity
    assert 'Granularity' in kwargs
    assert kwargs['Granularity'] == granularity
    
    # Verify Metrics
    assert 'Metrics' in kwargs
    assert 'BlendedCost' in kwargs['Metrics']
    assert 'UnblendedCost' in kwargs['Metrics']
    
    # Verify GroupBy
    assert 'GroupBy' in kwargs
    assert len(kwargs['GroupBy']) > 0
    assert kwargs['GroupBy'][0]['Type'] == 'DIMENSION'
    assert kwargs['GroupBy'][0]['Key'] == 'SERVICE'


# Additional property test: Verify response transformation
@given(
    st.integers(min_value=0, max_value=20),
    st.floats(min_value=0.0, max_value=10000.0)
)
@settings(max_examples=100)
def test_transform_response_produces_valid_records(num_services, base_cost):
    """
    Property: Response transformation produces valid CostRecord objects
    For any Cost Explorer API response, the transformation should produce
    valid CostRecord objects with all required fields.
    """
    # Generate mock response
    response = {
        'ResultsByTime': [
            {
                'TimePeriod': {
                    'Start': '2025-01-01',
                    'End': '2025-01-31'
                },
                'Groups': [
                    {
                        'Keys': [f'Service-{i}'],
                        'Metrics': {
                            'BlendedCost': {
                                'Amount': str(base_cost + i),
                                'Unit': 'USD'
                            },
                            'UnblendedCost': {
                                'Amount': str(base_cost + i),
                                'Unit': 'USD'
                            }
                        }
                    }
                    for i in range(num_services)
                ]
            }
        ]
    }
    
    # Transform response
    records = _transform_response(response)
    
    # Verify correct number of records
    assert len(records) == num_services
    
    # Verify each record has required fields
    for i, record in enumerate(records):
        assert isinstance(record, CostRecord)
        assert record.date == '2025-01-01'
        assert record.service == f'Service-{i}'
        assert record.blended_cost == base_cost + i
        assert record.unblended_cost == base_cost + i
        assert record.currency == 'USD'
        assert record.unit == 'USD'


# Property test: Empty response handling
def test_empty_response_returns_empty_list():
    """
    Property: Empty responses return empty lists
    For any empty Cost Explorer API response, the fetch function should
    return an empty list without errors.
    """
    # Create mock client with empty response
    mock_client = Mock()
    mock_response = {
        'ResultsByTime': []
    }
    mock_client.get_cost_and_usage = Mock(return_value=mock_response)
    
    # Fetch cost data
    params = CostExplorerParams(
        start_date='2025-01-01',
        end_date='2025-01-31',
        granularity='MONTHLY'
    )
    
    records = fetch_cost_data(params, client=mock_client)
    
    # Verify empty list is returned
    assert records == []
    assert isinstance(records, list)
