"""
Unit tests for DynamoDB service.

Tests specific examples and edge cases for DynamoDB integration.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from botocore.exceptions import ClientError

from src.services.dynamodb import (
    transform_to_dynamodb_record,
    store_cost_data,
    query_cost_data,
    _generate_year_months
)
from src.utils.types import CostRecord, QueryParams


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
    return ClientError(error_response, 'dynamodb_operation')


class TestTransformToDynamoDBRecord:
    """Test transform_to_dynamodb_record function."""
    
    def test_transform_produces_correct_pk_format(self):
        """Test that partition key has correct format COST#YYYY-MM."""
        record = CostRecord(
            date='2025-01-15',
            service='Amazon EC2',
            blended_cost=100.50,
            unblended_cost=100.50,
            currency='USD',
            unit='USD'
        )
        
        result = transform_to_dynamodb_record(record)
        
        assert result.pk == 'COST#2025-01'
    
    def test_transform_produces_correct_sk_format(self):
        """Test that sort key has correct format SERVICE#normalized-name."""
        record = CostRecord(
            date='2025-01-15',
            service='Amazon Elastic Compute Cloud',
            blended_cost=100.50,
            unblended_cost=100.50,
            currency='USD',
            unit='USD'
        )
        
        result = transform_to_dynamodb_record(record)
        
        assert result.sk.startswith('SERVICE#')
        assert result.sk == 'SERVICE#amazon-elastic-compute-cloud'
    
    def test_transform_includes_all_fields(self):
        """Test that all required fields are included."""
        record = CostRecord(
            date='2025-01-15',
            service='Amazon S3',
            blended_cost=25.75,
            unblended_cost=26.00,
            currency='USD',
            unit='USD'
        )
        
        result = transform_to_dynamodb_record(record)
        
        assert result.date == '2025-01-15'
        assert result.service == 'Amazon S3'
        assert result.blended_cost == 25.75
        assert result.unblended_cost == 26.00
        assert result.currency == 'USD'
        assert result.unit == 'USD'
        assert result.timestamp is not None
        assert result.ttl is not None


class TestStoreCostData:
    """Test store_cost_data function."""
    
    def test_store_single_batch(self):
        """Test storing cost data with < 25 items (single batch)."""
        records = [
            CostRecord(
                date='2025-01-01',
                service=f'Service-{i}',
                blended_cost=100.0 + i,
                unblended_cost=100.0 + i,
                currency='USD',
                unit='USD'
            )
            for i in range(10)
        ]
        
        # Create mock table
        mock_table = Mock()
        mock_writer = MagicMock()
        mock_writer.__enter__ = Mock(return_value=mock_writer)
        mock_writer.__exit__ = Mock(return_value=False)
        mock_writer.put_item = Mock()
        mock_table.batch_writer = Mock(return_value=mock_writer)
        
        # Create mock DynamoDB resource
        mock_dynamodb = Mock()
        mock_dynamodb.Table = Mock(return_value=mock_table)
        
        # Store cost data
        store_cost_data(records, dynamodb_resource=mock_dynamodb)
        
        # Verify batch_writer was called once
        assert mock_table.batch_writer.call_count == 1
        
        # Verify put_item was called 10 times
        assert mock_writer.put_item.call_count == 10
    
    def test_store_multiple_batches(self):
        """Test storing cost data with > 25 items (multiple batches)."""
        records = [
            CostRecord(
                date='2025-01-01',
                service=f'Service-{i}',
                blended_cost=100.0,
                unblended_cost=100.0,
                currency='USD',
                unit='USD'
            )
            for i in range(60)
        ]
        
        # Create mock table
        mock_table = Mock()
        batch_count = [0]
        
        def create_mock_writer():
            batch_count[0] += 1
            mock_writer = MagicMock()
            mock_writer.__enter__ = Mock(return_value=mock_writer)
            mock_writer.__exit__ = Mock(return_value=False)
            mock_writer.put_item = Mock()
            return mock_writer
        
        mock_table.batch_writer = Mock(side_effect=create_mock_writer)
        
        # Create mock DynamoDB resource
        mock_dynamodb = Mock()
        mock_dynamodb.Table = Mock(return_value=mock_table)
        
        # Store cost data
        store_cost_data(records, dynamodb_resource=mock_dynamodb)
        
        # Verify batch_writer was called 3 times (60 / 25 = 2.4, rounded up to 3)
        assert batch_count[0] == 3
    
    def test_store_empty_list(self):
        """Test storing empty list of records."""
        records = []
        
        # Create mock DynamoDB resource
        mock_dynamodb = Mock()
        
        # Store cost data (should return without error)
        store_cost_data(records, dynamodb_resource=mock_dynamodb)
        
        # Verify Table was not called
        assert not mock_dynamodb.Table.called


class TestQueryCostData:
    """Test query_cost_data function."""
    
    def test_query_with_start_date_only(self):
        """Test querying with only start_date."""
        params = QueryParams(start_date='2025-01-01')
        
        # Create mock table
        mock_table = Mock()
        mock_table.query = Mock(return_value={
            'Items': [
                {
                    'pk': 'COST#2025-01',
                    'sk': 'SERVICE#amazon-ec2',
                    'date': '2025-01-01',
                    'service': 'Amazon EC2',
                    'blendedCost': Decimal('100.0'),
                    'unblendedCost': Decimal('100.0'),
                    'currency': 'USD',
                    'unit': 'USD',
                    'timestamp': '2025-01-01T00:00:00Z'
                }
            ]
        })
        
        # Create mock DynamoDB resource
        mock_dynamodb = Mock()
        mock_dynamodb.Table = Mock(return_value=mock_table)
        
        # Query cost data
        results = query_cost_data(params, dynamodb_resource=mock_dynamodb)
        
        # Verify results
        assert len(results) == 1
        assert results[0].service == 'Amazon EC2'
        assert results[0].blended_cost == 100.0
    
    def test_query_with_date_range(self):
        """Test querying with start_date and end_date."""
        params = QueryParams(
            start_date='2025-01-01',
            end_date='2025-03-31'
        )
        
        # Create mock table
        mock_table = Mock()
        mock_table.query = Mock(return_value={'Items': []})
        
        # Create mock DynamoDB resource
        mock_dynamodb = Mock()
        mock_dynamodb.Table = Mock(return_value=mock_table)
        
        # Query cost data
        results = query_cost_data(params, dynamodb_resource=mock_dynamodb)
        
        # Verify query was called multiple times (once per month)
        assert mock_table.query.call_count == 3  # Jan, Feb, Mar
    
    def test_query_with_service_filter(self):
        """Test querying with service filter."""
        params = QueryParams(
            start_date='2025-01-01',
            service='Amazon EC2'
        )
        
        # Create mock table
        mock_table = Mock()
        mock_table.query = Mock(return_value={'Items': []})
        
        # Create mock DynamoDB resource
        mock_dynamodb = Mock()
        mock_dynamodb.Table = Mock(return_value=mock_table)
        
        # Query cost data
        results = query_cost_data(params, dynamodb_resource=mock_dynamodb)
        
        # Verify query was called with service filter
        call_kwargs = mock_table.query.call_args[1]
        assert ':sk' in call_kwargs['ExpressionAttributeValues']
    
    def test_query_with_limit(self):
        """Test querying with limit."""
        params = QueryParams(
            start_date='2025-01-01',
            end_date='2025-12-31',
            limit=5
        )
        
        # Create mock table that returns 10 items per month
        mock_table = Mock()
        mock_table.query = Mock(return_value={
            'Items': [
                {
                    'pk': 'COST#2025-01',
                    'sk': f'SERVICE#service-{i}',
                    'date': '2025-01-01',
                    'service': f'Service-{i}',
                    'blendedCost': Decimal('100.0'),
                    'unblendedCost': Decimal('100.0'),
                    'currency': 'USD',
                    'unit': 'USD',
                    'timestamp': '2025-01-01T00:00:00Z'
                }
                for i in range(10)
            ]
        })
        
        # Create mock DynamoDB resource
        mock_dynamodb = Mock()
        mock_dynamodb.Table = Mock(return_value=mock_table)
        
        # Query cost data
        results = query_cost_data(params, dynamodb_resource=mock_dynamodb)
        
        # Verify limit was applied
        assert len(results) == 5
    
    def test_query_without_start_date(self):
        """Test querying without start_date returns empty list."""
        params = QueryParams(service='Amazon EC2')
        
        # Create mock DynamoDB resource
        mock_dynamodb = Mock()
        
        # Query cost data
        results = query_cost_data(params, dynamodb_resource=mock_dynamodb)
        
        # Verify empty list is returned
        assert results == []
    
    def test_query_uses_query_not_scan(self):
        """Test that query uses Query operation (not Scan)."""
        params = QueryParams(start_date='2025-01-01')
        
        # Create mock table
        mock_table = Mock()
        mock_table.query = Mock(return_value={'Items': []})
        mock_table.scan = Mock(return_value={'Items': []})
        
        # Create mock DynamoDB resource
        mock_dynamodb = Mock()
        mock_dynamodb.Table = Mock(return_value=mock_table)
        
        # Query cost data
        results = query_cost_data(params, dynamodb_resource=mock_dynamodb)
        
        # Verify Query was used, not Scan
        assert mock_table.query.called
        assert not mock_table.scan.called


class TestGenerateYearMonths:
    """Test _generate_year_months helper function."""
    
    def test_generate_single_month(self):
        """Test generating a single month."""
        result = _generate_year_months('2025-01', '2025-01')
        
        assert result == ['2025-01']
    
    def test_generate_multiple_months_same_year(self):
        """Test generating multiple months in the same year."""
        result = _generate_year_months('2025-01', '2025-03')
        
        assert result == ['2025-01', '2025-02', '2025-03']
    
    def test_generate_months_across_years(self):
        """Test generating months across year boundary."""
        result = _generate_year_months('2024-11', '2025-02')
        
        assert result == ['2024-11', '2024-12', '2025-01', '2025-02']
    
    def test_generate_full_year(self):
        """Test generating a full year."""
        result = _generate_year_months('2025-01', '2025-12')
        
        assert len(result) == 12
        assert result[0] == '2025-01'
        assert result[-1] == '2025-12'
