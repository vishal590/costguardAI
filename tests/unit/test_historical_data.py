"""
Unit tests for Historical Data Retriever.

Tests cover:
- Data retrieval with various date ranges
- Aggregation logic
- Interpolation with gaps
- Validation with insufficient data
"""

import pytest
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import Mock, MagicMock
from src.services.historical_data import HistoricalDataRetriever
from src.utils.types import InsufficientDataError, ProcessedData


class TestHistoricalDataRetriever:
    """Test suite for HistoricalDataRetriever."""
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Create mock DynamoDB client."""
        dynamodb = Mock()
        table = Mock()
        dynamodb.Table.return_value = table
        return dynamodb, table
    
    @pytest.fixture
    def retriever(self, mock_dynamodb):
        """Create HistoricalDataRetriever instance."""
        dynamodb, _ = mock_dynamodb
        return HistoricalDataRetriever(dynamodb)
    
    def test_initialization(self, mock_dynamodb):
        """Test retriever initialization."""
        dynamodb, _ = mock_dynamodb
        retriever = HistoricalDataRetriever(dynamodb, "test-table")
        
        assert retriever.dynamodb == dynamodb
        assert retriever.table_name == "test-table"
        dynamodb.Table.assert_called_once_with("test-table")
    
    def test_aggregate_by_service_and_date_single_service(self, retriever):
        """Test aggregation with single service."""
        data = [
            {'service': 'EC2', 'date': '2024-01-01', 'cost': Decimal('10.5')},
            {'service': 'EC2', 'date': '2024-01-02', 'cost': Decimal('12.3')},
            {'service': 'EC2', 'date': '2024-01-01', 'cost': Decimal('5.2')},  # Same date
        ]
        
        result = retriever.aggregate_by_service_and_date(data)
        
        assert 'EC2' in result
        assert len(result['EC2']) == 2
        assert result['EC2'][0] == {'date': '2024-01-01', 'cost': 15.7}
        assert result['EC2'][1] == {'date': '2024-01-02', 'cost': 12.3}
    
    def test_aggregate_by_service_and_date_multiple_services(self, retriever):
        """Test aggregation with multiple services."""
        data = [
            {'service': 'EC2', 'date': '2024-01-01', 'cost': Decimal('10.0')},
            {'service': 'S3', 'date': '2024-01-01', 'cost': Decimal('5.0')},
            {'service': 'EC2', 'date': '2024-01-02', 'cost': Decimal('12.0')},
        ]
        
        result = retriever.aggregate_by_service_and_date(data)
        
        assert 'EC2' in result
        assert 'S3' in result
        assert len(result['EC2']) == 2
        assert len(result['S3']) == 1
    
    def test_aggregate_by_service_and_date_empty_data(self, retriever):
        """Test aggregation with empty data."""
        result = retriever.aggregate_by_service_and_date([])
        assert result == {}
    
    def test_interpolate_gaps_no_gaps(self, retriever):
        """Test interpolation with complete data."""
        from datetime import date
        
        data = [
            {'date': '2024-01-01', 'cost': 10.0},
            {'date': '2024-01-02', 'cost': 12.0},
            {'date': '2024-01-03', 'cost': 15.0},
        ]
        
        result = retriever.interpolate_gaps(
            data,
            date(2024, 1, 1),
            date(2024, 1, 3)
        )
        
        assert len(result) == 3
        assert result[0]['cost'] == 10.0
        assert result[1]['cost'] == 12.0
        assert result[2]['cost'] == 15.0
    
    def test_interpolate_gaps_with_gaps(self, retriever):
        """Test interpolation with missing dates."""
        from datetime import date
        
        data = [
            {'date': '2024-01-01', 'cost': 10.0},
            {'date': '2024-01-03', 'cost': 20.0},
        ]
        
        result = retriever.interpolate_gaps(
            data,
            date(2024, 1, 1),
            date(2024, 1, 3)
        )
        
        assert len(result) == 3
        assert result[0]['cost'] == 10.0
        assert result[1]['cost'] == 15.0  # Interpolated
        assert result[2]['cost'] == 20.0
    
    def test_interpolate_gaps_empty_data(self, retriever):
        """Test interpolation with empty data."""
        from datetime import date
        
        result = retriever.interpolate_gaps(
            [],
            date(2024, 1, 1),
            date(2024, 1, 3)
        )
        
        assert result == []
    
    def test_interpolate_value_between_two_points(self, retriever):
        """Test linear interpolation between two points."""
        from datetime import date
        
        date_map = {
            '2024-01-01': 10.0,
            '2024-01-05': 20.0,
        }
        
        # Interpolate for 2024-01-03 (midpoint)
        result = retriever._interpolate_value(
            '2024-01-03',
            date_map,
            date(2024, 1, 1),
            date(2024, 1, 5)
        )
        
        assert result == 15.0
    
    def test_interpolate_value_only_previous(self, retriever):
        """Test interpolation with only previous value."""
        from datetime import date
        
        date_map = {
            '2024-01-01': 10.0,
        }
        
        result = retriever._interpolate_value(
            '2024-01-03',
            date_map,
            date(2024, 1, 1),
            date(2024, 1, 5)
        )
        
        assert result == 10.0
    
    def test_interpolate_value_only_next(self, retriever):
        """Test interpolation with only next value."""
        from datetime import date
        
        date_map = {
            '2024-01-05': 20.0,
        }
        
        result = retriever._interpolate_value(
            '2024-01-03',
            date_map,
            date(2024, 1, 1),
            date(2024, 1, 5)
        )
        
        assert result == 20.0
    
    def test_interpolate_value_no_data(self, retriever):
        """Test interpolation with no data."""
        from datetime import date
        
        result = retriever._interpolate_value(
            '2024-01-03',
            {},
            date(2024, 1, 1),
            date(2024, 1, 5)
        )
        
        assert result == 0.0
    
    def test_validate_completeness_sufficient_data(self, retriever):
        """Test validation with sufficient data."""
        data = [
            {'date': f'2024-01-{i:02d}', 'cost': 10.0}
            for i in range(1, 32)  # 31 days
        ]
        
        assert retriever.validate_completeness(data, 90) is True
    
    def test_validate_completeness_insufficient_data(self, retriever):
        """Test validation with insufficient data."""
        data = [
            {'date': f'2024-01-{i:02d}', 'cost': 10.0}
            for i in range(1, 20)  # Only 19 days
        ]
        
        assert retriever.validate_completeness(data, 90) is False
    
    def test_validate_completeness_empty_data(self, retriever):
        """Test validation with empty data."""
        assert retriever.validate_completeness([], 90) is False
    
    def test_validate_completeness_exactly_30_days(self, retriever):
        """Test validation with exactly 30 days."""
        data = [
            {'date': f'2024-01-{i:02d}', 'cost': 10.0}
            for i in range(1, 31)  # Exactly 30 days
        ]
        
        assert retriever.validate_completeness(data, 90) is True
    
    def test_get_historical_data_success(self, mock_dynamodb, retriever):
        """Test successful historical data retrieval."""
        _, table = mock_dynamodb
        
        # Mock DynamoDB response
        table.scan.return_value = {
            'Items': [
                {'service': 'EC2', 'date': '2024-01-01', 'cost': Decimal('10.0')},
                {'service': 'EC2', 'date': '2024-01-02', 'cost': Decimal('12.0')},
            ] + [
                {'service': 'EC2', 'date': f'2024-01-{i:02d}', 'cost': Decimal('10.0')}
                for i in range(3, 32)  # Add more days to meet minimum
            ]
        }
        
        result = retriever.get_historical_data(service='EC2', days_back=30)
        
        assert isinstance(result, ProcessedData)
        assert result.service == 'EC2'
        assert len(result.timestamps) >= 30
        assert len(result.costs) >= 30
        assert result.total_days >= 30
    
    def test_get_historical_data_insufficient_data_error(self, mock_dynamodb, retriever):
        """Test error when insufficient data."""
        _, table = mock_dynamodb
        
        # Mock DynamoDB response with no data (truly insufficient)
        table.scan.return_value = {
            'Items': []
        }
        
        with pytest.raises(InsufficientDataError):
            retriever.get_historical_data(service='EC2', days_back=90)
    
    def test_get_historical_data_with_pagination(self, mock_dynamodb, retriever):
        """Test data retrieval with DynamoDB pagination."""
        _, table = mock_dynamodb
        
        # Mock paginated response
        table.scan.side_effect = [
            {
                'Items': [
                    {'service': 'EC2', 'date': f'2024-01-{i:02d}', 'cost': Decimal('10.0')}
                    for i in range(1, 16)
                ],
                'LastEvaluatedKey': {'date': '2024-01-15'}
            },
            {
                'Items': [
                    {'service': 'EC2', 'date': f'2024-01-{i:02d}', 'cost': Decimal('10.0')}
                    for i in range(16, 32)
                ]
            }
        ]
        
        result = retriever.get_historical_data(service='EC2', days_back=30)
        
        assert isinstance(result, ProcessedData)
        assert table.scan.call_count == 2
        assert len(result.timestamps) >= 30
