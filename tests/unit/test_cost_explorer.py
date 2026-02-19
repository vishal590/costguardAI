"""
Unit tests for Cost Explorer service.

Tests specific examples and edge cases for Cost Explorer integration.
"""
import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from src.services.cost_explorer import (
    fetch_cost_data,
    CostExplorerParams,
    _transform_response
)
from src.utils.types import CostRecord


def create_client_error(error_code: str, http_status: int):
    """Helper to create a mock ClientError."""
    error_response = {
        'Error': {
            'Code': error_code,
            'Message': 'Test error'
        },
        'ResponseMetadata': {
            'HTTPStatusCode': http_status,
            'RequestId': 'test-request-id'
        }
    }
    return ClientError(error_response, 'get_cost_and_usage')


class TestFetchCostData:
    """Test fetch_cost_data with various scenarios."""
    
    def test_fetch_single_page_response(self):
        """Test fetching cost data with a single-page response."""
        # Create mock response
        mock_response = {
            'ResultsByTime': [
                {
                    'TimePeriod': {
                        'Start': '2025-01-01',
                        'End': '2025-01-31'
                    },
                    'Groups': [
                        {
                            'Keys': ['Amazon EC2'],
                            'Metrics': {
                                'BlendedCost': {
                                    'Amount': '100.50',
                                    'Unit': 'USD'
                                },
                                'UnblendedCost': {
                                    'Amount': '100.50',
                                    'Unit': 'USD'
                                }
                            }
                        },
                        {
                            'Keys': ['Amazon S3'],
                            'Metrics': {
                                'BlendedCost': {
                                    'Amount': '25.75',
                                    'Unit': 'USD'
                                },
                                'UnblendedCost': {
                                    'Amount': '25.75',
                                    'Unit': 'USD'
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        # Create mock client
        mock_client = Mock()
        mock_client.get_cost_and_usage = Mock(return_value=mock_response)
        
        # Fetch cost data
        params = CostExplorerParams('2025-01-01', '2025-01-31', 'MONTHLY')
        records = fetch_cost_data(params, client=mock_client)
        
        # Verify results
        assert len(records) == 2
        assert records[0].service == 'Amazon EC2'
        assert records[0].blended_cost == 100.50
        assert records[1].service == 'Amazon S3'
        assert records[1].blended_cost == 25.75
        
        # Verify API was called once
        assert mock_client.get_cost_and_usage.call_count == 1
    
    def test_fetch_multi_page_response(self):
        """Test fetching cost data with a multi-page response (3 pages)."""
        # Create mock responses for 3 pages
        page1 = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2025-01-01', 'End': '2025-01-31'},
                    'Groups': [
                        {
                            'Keys': ['Service1'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '10.0', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '10.0', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ],
            'NextPageToken': 'token-page2'
        }
        
        page2 = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2025-01-01', 'End': '2025-01-31'},
                    'Groups': [
                        {
                            'Keys': ['Service2'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '20.0', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '20.0', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ],
            'NextPageToken': 'token-page3'
        }
        
        page3 = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2025-01-01', 'End': '2025-01-31'},
                    'Groups': [
                        {
                            'Keys': ['Service3'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '30.0', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '30.0', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ]
        }
        
        # Create mock client
        mock_client = Mock()
        mock_client.get_cost_and_usage = Mock(side_effect=[page1, page2, page3])
        
        # Fetch cost data
        params = CostExplorerParams('2025-01-01', '2025-01-31', 'MONTHLY')
        records = fetch_cost_data(params, client=mock_client)
        
        # Verify all pages were fetched
        assert len(records) == 3
        assert records[0].service == 'Service1'
        assert records[1].service == 'Service2'
        assert records[2].service == 'Service3'
        
        # Verify API was called 3 times
        assert mock_client.get_cost_and_usage.call_count == 3
    
    def test_fetch_empty_response(self):
        """Test fetching cost data with an empty response."""
        # Create mock empty response
        mock_response = {
            'ResultsByTime': []
        }
        
        # Create mock client
        mock_client = Mock()
        mock_client.get_cost_and_usage = Mock(return_value=mock_response)
        
        # Fetch cost data
        params = CostExplorerParams('2025-01-01', '2025-01-31', 'MONTHLY')
        records = fetch_cost_data(params, client=mock_client)
        
        # Verify empty list is returned
        assert records == []
    
    def test_fetch_with_rate_limit_error(self):
        """Test fetching cost data with a rate limit error (429)."""
        # Create mock client that fails with 429 then succeeds
        mock_client = Mock()
        error = create_client_error('RequestLimitExceeded', 429)
        success_response = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2025-01-01', 'End': '2025-01-31'},
                    'Groups': [
                        {
                            'Keys': ['Amazon EC2'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '50.0', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '50.0', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ]
        }
        
        mock_client.get_cost_and_usage = Mock(side_effect=[error, success_response])
        
        # Fetch cost data
        params = CostExplorerParams('2025-01-01', '2025-01-31', 'MONTHLY')
        records = fetch_cost_data(params, client=mock_client)
        
        # Verify retry succeeded
        assert len(records) == 1
        assert records[0].service == 'Amazon EC2'
        
        # Verify API was called twice (initial + 1 retry)
        assert mock_client.get_cost_and_usage.call_count == 2
    
    def test_fetch_with_service_unavailable_error(self):
        """Test fetching cost data with a service unavailable error (503)."""
        # Create mock client that fails with 503 then succeeds
        mock_client = Mock()
        error = create_client_error('ServiceUnavailable', 503)
        success_response = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2025-01-01', 'End': '2025-01-31'},
                    'Groups': [
                        {
                            'Keys': ['Amazon S3'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '15.0', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '15.0', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ]
        }
        
        mock_client.get_cost_and_usage = Mock(side_effect=[error, success_response])
        
        # Fetch cost data
        params = CostExplorerParams('2025-01-01', '2025-01-31', 'MONTHLY')
        records = fetch_cost_data(params, client=mock_client)
        
        # Verify retry succeeded
        assert len(records) == 1
        assert records[0].service == 'Amazon S3'
    
    def test_api_call_parameters(self):
        """Test that API call includes correct GroupBy and Metrics parameters."""
        # Create mock response
        mock_response = {'ResultsByTime': []}
        
        # Create mock client
        mock_client = Mock()
        mock_client.get_cost_and_usage = Mock(return_value=mock_response)
        
        # Fetch cost data
        params = CostExplorerParams('2025-01-01', '2025-12-31', 'DAILY')
        records = fetch_cost_data(params, client=mock_client)
        
        # Get the call arguments
        call_args = mock_client.get_cost_and_usage.call_args
        kwargs = call_args[1]
        
        # Verify TimePeriod
        assert kwargs['TimePeriod']['Start'] == '2025-01-01'
        assert kwargs['TimePeriod']['End'] == '2025-12-31'
        
        # Verify Granularity
        assert kwargs['Granularity'] == 'DAILY'
        
        # Verify Metrics
        assert 'BlendedCost' in kwargs['Metrics']
        assert 'UnblendedCost' in kwargs['Metrics']
        
        # Verify GroupBy
        assert len(kwargs['GroupBy']) == 1
        assert kwargs['GroupBy'][0]['Type'] == 'DIMENSION'
        assert kwargs['GroupBy'][0]['Key'] == 'SERVICE'


class TestTransformResponse:
    """Test _transform_response function."""
    
    def test_transform_single_service(self):
        """Test transforming a response with a single service."""
        response = {
            'ResultsByTime': [
                {
                    'TimePeriod': {
                        'Start': '2025-01-01',
                        'End': '2025-01-31'
                    },
                    'Groups': [
                        {
                            'Keys': ['Amazon EC2'],
                            'Metrics': {
                                'BlendedCost': {
                                    'Amount': '123.45',
                                    'Unit': 'USD'
                                },
                                'UnblendedCost': {
                                    'Amount': '123.45',
                                    'Unit': 'USD'
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        records = _transform_response(response)
        
        assert len(records) == 1
        assert records[0].date == '2025-01-01'
        assert records[0].service == 'Amazon EC2'
        assert records[0].blended_cost == 123.45
        assert records[0].unblended_cost == 123.45
        assert records[0].currency == 'USD'
        assert records[0].unit == 'USD'
    
    def test_transform_multiple_services(self):
        """Test transforming a response with multiple services."""
        response = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2025-01-01', 'End': '2025-01-31'},
                    'Groups': [
                        {
                            'Keys': ['Amazon EC2'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '100.0', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '100.0', 'Unit': 'USD'}
                            }
                        },
                        {
                            'Keys': ['Amazon S3'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '50.0', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '50.0', 'Unit': 'USD'}
                            }
                        },
                        {
                            'Keys': ['AWS Lambda'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '25.0', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '25.0', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ]
        }
        
        records = _transform_response(response)
        
        assert len(records) == 3
        assert records[0].service == 'Amazon EC2'
        assert records[1].service == 'Amazon S3'
        assert records[2].service == 'AWS Lambda'
    
    def test_transform_empty_response(self):
        """Test transforming an empty response."""
        response = {'ResultsByTime': []}
        
        records = _transform_response(response)
        
        assert records == []
    
    def test_transform_zero_cost(self):
        """Test transforming a response with zero cost."""
        response = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2025-01-01', 'End': '2025-01-31'},
                    'Groups': [
                        {
                            'Keys': ['Amazon EC2'],
                            'Metrics': {
                                'BlendedCost': {'Amount': '0.00', 'Unit': 'USD'},
                                'UnblendedCost': {'Amount': '0.00', 'Unit': 'USD'}
                            }
                        }
                    ]
                }
            ]
        }
        
        records = _transform_response(response)
        
        assert len(records) == 1
        assert records[0].blended_cost == 0.0
        assert records[0].unblended_cost == 0.0
