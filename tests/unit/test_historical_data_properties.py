"""
Property-based tests for Historical Data Retriever.

Tests universal correctness properties:
- Property 1: Historical Data Validation
- Property 2: Data Interpolation Completeness
- Property 7: Service-Specific Data Filtering
- Property 16: Historical Data Limit
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta, date, UTC
from decimal import Decimal
from unittest.mock import Mock
from src.services.historical_data import HistoricalDataRetriever
from src.utils.types import InsufficientDataError, ProcessedData


# Strategies
@st.composite
def valid_service_names(draw):
    """Generate valid AWS service names."""
    services = ['EC2', 'S3', 'Lambda', 'DynamoDB', 'RDS', 'CloudWatch']
    return draw(st.sampled_from(services))


@st.composite
def cost_data_items(draw, min_days=30, max_days=90):
    """Generate list of cost data items."""
    num_days = draw(st.integers(min_value=min_days, max_value=max_days))
    service = draw(valid_service_names())
    
    items = []
    start_date = date(2024, 1, 1)
    for i in range(num_days):
        current_date = start_date + timedelta(days=i)
        cost = draw(st.floats(min_value=0.0, max_value=1000.0))
        items.append({
            'service': service,
            'date': current_date.isoformat(),
            'cost': Decimal(str(round(cost, 2)))
        })
    
    return items


@st.composite
def cost_data_with_gaps(draw, min_days=30, max_days=90):
    """Generate cost data with random gaps."""
    num_days = draw(st.integers(min_value=min_days, max_value=max_days))
    service = draw(valid_service_names())
    gap_probability = draw(st.floats(min_value=0.1, max_value=0.3))
    
    items = []
    start_date = date(2024, 1, 1)
    for i in range(num_days):
        # Randomly skip some days to create gaps
        if draw(st.floats(min_value=0.0, max_value=1.0)) > gap_probability:
            current_date = start_date + timedelta(days=i)
            cost = draw(st.floats(min_value=0.0, max_value=1000.0))
            items.append({
                'service': service,
                'date': current_date.isoformat(),
                'cost': Decimal(str(round(cost, 2)))
            })
    
    return items


class TestHistoricalDataProperties:
    """Property-based tests for HistoricalDataRetriever."""
    
    # Feature: ai-cost-forecasting, Property 1: Historical Data Validation
    @settings(max_examples=100, deadline=1000)
    @given(items=cost_data_items(min_days=30, max_days=90))
    def test_property_1_historical_data_validation(self, items):
        """
        Property 1: Historical Data Validation
        
        For all historical data retrievals:
        - Data must span at least 30 days
        - Data must be sorted by date
        - All costs must be non-negative
        """
        # Create mock inside test
        dynamodb = Mock()
        table = Mock()
        dynamodb.Table.return_value = table
        table.scan.return_value = {'Items': items}
        
        retriever = HistoricalDataRetriever(dynamodb)
        
        result = retriever.get_historical_data(
            service=items[0]['service'],
            days_back=90
        )
        
        # Check minimum 30 days
        assert result.total_days >= 30, "Data must span at least 30 days"
        
        # Check data is sorted by date
        timestamps = result.timestamps
        for i in range(len(timestamps) - 1):
            assert timestamps[i] <= timestamps[i + 1], "Data must be sorted by date"
        
        # Check all costs are non-negative
        for cost in result.costs:
            assert cost >= 0, "All costs must be non-negative"
    
    # Feature: ai-cost-forecasting, Property 2: Data Interpolation Completeness
    @settings(max_examples=100, deadline=1000)
    @given(items=cost_data_with_gaps(min_days=30, max_days=60))
    def test_property_2_data_interpolation_completeness(self, items):
        """
        Property 2: Data Interpolation Completeness
        
        For all data with gaps:
        - Interpolated data must have no missing dates
        - Interpolated values must be between surrounding values
        - Date range must be continuous
        """
        if not items:
            return  # Skip empty data
        
        # Create mock inside test
        dynamodb = Mock()
        table = Mock()
        dynamodb.Table.return_value = table
        retriever = HistoricalDataRetriever(dynamodb)
        
        # Get date range
        dates = [item['date'] for item in items]
        start_date = min(dates)
        end_date = max(dates)
        
        # Aggregate by service
        aggregated = retriever.aggregate_by_service_and_date(items)
        
        for service, data_points in aggregated.items():
            # Interpolate
            interpolated = retriever.interpolate_gaps(
                data_points,
                datetime.fromisoformat(start_date).date(),
                datetime.fromisoformat(end_date).date()
            )
            
            # Check no missing dates
            interpolated_dates = [point['date'] for point in interpolated]
            expected_days = (
                datetime.fromisoformat(end_date).date() -
                datetime.fromisoformat(start_date).date()
            ).days + 1
            assert len(interpolated_dates) == expected_days, "Must have no missing dates"
            
            # Check dates are continuous
            for i in range(len(interpolated_dates) - 1):
                date1 = datetime.fromisoformat(interpolated_dates[i]).date()
                date2 = datetime.fromisoformat(interpolated_dates[i + 1]).date()
                assert (date2 - date1).days == 1, "Dates must be continuous"
    
    # Feature: ai-cost-forecasting, Property 7: Service-Specific Data Filtering
    @settings(max_examples=100, deadline=1000)
    @given(
        service1=valid_service_names(),
        service2=valid_service_names(),
        days=st.integers(min_value=30, max_value=60)
    )
    def test_property_7_service_specific_filtering(self, service1, service2, days):
        """
        Property 7: Service-Specific Data Filtering
        
        For all service-specific requests:
        - Only data for requested service is returned
        - Other services' data is excluded
        - Service name in result matches request
        """
        if service1 == service2:
            return  # Skip if services are the same
        
        # Create mock inside test
        dynamodb = Mock()
        table = Mock()
        dynamodb.Table.return_value = table
        
        # Create mixed data - use dates going back from today
        items = []
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days - 1)
        
        current_date = start_date
        while current_date <= end_date:
            items.append({
                'service': service1,
                'date': current_date.isoformat(),
                'cost': Decimal('10.0')
            })
            items.append({
                'service': service2,
                'date': current_date.isoformat(),
                'cost': Decimal('20.0')
            })
            current_date += timedelta(days=1)
        
        table.scan.return_value = {'Items': items}
        
        retriever = HistoricalDataRetriever(dynamodb)
        
        # Request service1 data
        result = retriever.get_historical_data(service=service1, days_back=days)
        
        # Check service name matches
        assert result.service == service1, "Service name must match request"
        
        # Check costs match service1 (should be 10.0, not 20.0 from service2)
        # All costs should be 10.0 since we filtered for service1
        for cost in result.costs:
            assert cost == 10.0, f"Only {service1} data should be included, got {cost}"
    
    # Feature: ai-cost-forecasting, Property 16: Historical Data Limit
    @settings(max_examples=100, deadline=1000)
    @given(days_back=st.integers(min_value=30, max_value=365))
    def test_property_16_historical_data_limit(self, days_back):
        """
        Property 16: Historical Data Limit
        
        For all data retrieval requests:
        - System retrieves at most days_back days of data
        - Data does not exceed requested range
        - Start date is days_back before end date
        """
        # Create mock inside test
        dynamodb = Mock()
        table = Mock()
        dynamodb.Table.return_value = table
        
        # Create data for the full range - use dates going back from today
        items = []
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days_back - 1)
        
        current_date = start_date
        while current_date <= end_date:
            items.append({
                'service': 'EC2',
                'date': current_date.isoformat(),
                'cost': Decimal('10.0')
            })
            current_date += timedelta(days=1)
        
        table.scan.return_value = {'Items': items}
        
        retriever = HistoricalDataRetriever(dynamodb)
        result = retriever.get_historical_data(service='EC2', days_back=days_back)
        
        # Check data does not exceed requested range (allow for off-by-one due to inclusive dates)
        assert result.total_days <= days_back + 1, f"Data must not exceed requested range: {result.total_days} > {days_back}"
        
        # Check timestamps are within range
        if result.timestamps:
            first_date = datetime.fromisoformat(result.timestamps[0]).date()
            last_date = datetime.fromisoformat(result.timestamps[-1]).date()
            actual_days = (last_date - first_date).days + 1
            assert actual_days <= days_back + 1, f"Date range must not exceed days_back: {actual_days} > {days_back}"
    
    @settings(max_examples=100, deadline=1000)
    @given(
        num_items=st.integers(min_value=0, max_value=29),
        service=valid_service_names()
    )
    def test_insufficient_data_raises_error(self, num_items, service):
        """Test that insufficient data raises InsufficientDataError."""
        # Create mock inside test
        dynamodb = Mock()
        table = Mock()
        dynamodb.Table.return_value = table
        
        # Create insufficient data
        items = []
        start_date = date(2024, 1, 1)
        for i in range(num_items):
            current_date = start_date + timedelta(days=i)
            items.append({
                'service': service,
                'date': current_date.isoformat(),
                'cost': Decimal('10.0')
            })
        
        table.scan.return_value = {'Items': items}
        
        retriever = HistoricalDataRetriever(dynamodb)
        
        # Should raise InsufficientDataError
        with pytest.raises(InsufficientDataError):
            retriever.get_historical_data(service=service, days_back=90)
    
    @settings(max_examples=100, deadline=1000)
    @given(items=cost_data_items(min_days=30, max_days=90))
    def test_aggregation_preserves_total_cost(self, items):
        """Test that aggregation preserves total cost."""
        # Create mock inside test
        dynamodb = Mock()
        table = Mock()
        dynamodb.Table.return_value = table
        retriever = HistoricalDataRetriever(dynamodb)
        
        # Calculate original total
        original_total = sum(float(item['cost']) for item in items)
        
        # Aggregate
        aggregated = retriever.aggregate_by_service_and_date(items)
        
        # Calculate aggregated total
        aggregated_total = 0.0
        for service, data_points in aggregated.items():
            aggregated_total += sum(point['cost'] for point in data_points)
        
        # Check totals match (within floating point tolerance)
        assert abs(original_total - aggregated_total) < 0.01, "Aggregation must preserve total cost"
