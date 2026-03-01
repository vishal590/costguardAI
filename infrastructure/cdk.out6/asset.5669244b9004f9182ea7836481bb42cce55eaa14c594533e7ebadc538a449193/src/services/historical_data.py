"""
Historical Data Retriever for forecast input preparation.

This module retrieves and preprocesses historical cost data:
1. Data retrieval from DynamoDB (Phase 1 data)
2. Aggregation by service and date
3. Gap interpolation using linear interpolation
4. Data validation and completeness checking
"""

from typing import Optional, List, Dict
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from src.utils.types import InsufficientDataError, ProcessedData


class HistoricalDataRetriever:
    """Retrieves and preprocesses historical cost data."""
    
    def __init__(self, dynamodb_client, table_name: str = "costguard-cost-data"):
        """
        Initialize data retriever.
        
        Args:
            dynamodb_client: boto3 DynamoDB resource
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = dynamodb_client
        self.table_name = table_name
        self.table = self.dynamodb.Table(table_name)
        
    def get_historical_data(
        self,
        service: Optional[str] = None,
        days_back: int = 90
    ) -> ProcessedData:
        """
        Retrieve historical cost data from DynamoDB.
        
        Args:
            service: Service name (None for all services)
            days_back: Number of days of history to retrieve
            
        Returns:
            ProcessedData with historical costs and metadata
            
        Raises:
            InsufficientDataError: Less than minimum required data
        """
        # Calculate date range
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days_back)
        
        # Query DynamoDB for historical data
        raw_data = self._query_dynamodb(start_date, end_date, service)
        
        # Check we have enough raw data before processing
        if len(raw_data) < 30:
            raise InsufficientDataError(
                f"Insufficient historical data: need at least 30 data points, found {len(raw_data)}"
            )
        
        # Aggregate by service and date
        aggregated = self.aggregate_by_service_and_date(raw_data)
        
        # Interpolate gaps for each service
        interpolated = {}
        for svc, data_points in aggregated.items():
            interpolated[svc] = self.interpolate_gaps(data_points, start_date, end_date)
        
        # Convert to ProcessedData format (timestamps and costs lists)
        # If service-specific, use that service's data; otherwise aggregate all
        if service and service in interpolated:
            data_points = interpolated[service]
        else:
            # Aggregate all services by date
            date_totals = {}
            for svc, data_points in interpolated.items():
                for point in data_points:
                    date = point['date']
                    cost = point['cost']
                    date_totals[date] = date_totals.get(date, 0.0) + cost
            
            data_points = [
                {'date': date, 'cost': cost}
                for date, cost in sorted(date_totals.items())
            ]
        
        timestamps = [point['date'] for point in data_points]
        costs = [point['cost'] for point in data_points]
        
        # Build ProcessedData
        return ProcessedData(
            timestamps=timestamps,
            costs=costs,
            service=service,
            total_days=len(timestamps)
        )
    
    def _query_dynamodb(
        self,
        start_date,
        end_date,
        service: Optional[str]
    ) -> List[Dict]:
        """Query DynamoDB for cost data within date range."""
        items = []
        
        # Query by date range
        # Assuming table structure: PK=date, SK=service, cost attribute
        # Use filter expression instead of Key condition for scan
        from boto3.dynamodb.conditions import Attr
        
        filter_expr = Attr('date').between(
            start_date.isoformat(),
            end_date.isoformat()
        )
        
        response = self.table.scan(FilterExpression=filter_expr)
        
        items.extend(response.get('Items', []))
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = self.table.scan(
                FilterExpression=filter_expr,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        
        # Filter by service if specified
        if service:
            items = [item for item in items if item.get('service') == service]
        
        return items
        
    def aggregate_by_service_and_date(
        self,
        data: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Aggregate costs by service and date.
        
        Args:
            data: Raw DynamoDB items
            
        Returns:
            Dict mapping service name to list of {date, cost} dicts
        """
        aggregated: Dict[str, Dict[str, Decimal]] = {}
        
        for item in data:
            service = item.get('service', 'Unknown')
            date = item.get('date')
            cost = item.get('cost', Decimal('0'))
            
            if service not in aggregated:
                aggregated[service] = {}
            
            if date not in aggregated[service]:
                aggregated[service][date] = Decimal('0')
            
            aggregated[service][date] += Decimal(str(cost))
        
        # Convert to list format sorted by date
        result = {}
        for service, date_costs in aggregated.items():
            result[service] = [
                {'date': date, 'cost': float(cost)}
                for date, cost in sorted(date_costs.items())
            ]
        
        return result
        
    def interpolate_gaps(
        self,
        data: List[Dict],
        start_date,
        end_date
    ) -> List[Dict]:
        """
        Fill missing dates using linear interpolation.
        
        Args:
            data: List of {date, cost} dicts
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Complete list with interpolated values
        """
        if not data:
            return []
        
        # Create date-to-cost mapping
        date_map = {item['date']: item['cost'] for item in data}
        
        # Generate complete date range
        current_date = start_date
        complete_data = []
        
        while current_date <= end_date:
            date_str = current_date.isoformat()
            
            if date_str in date_map:
                # Use actual value
                complete_data.append({'date': date_str, 'cost': date_map[date_str]})
            else:
                # Interpolate
                interpolated_cost = self._interpolate_value(
                    date_str, date_map, start_date, end_date
                )
                complete_data.append({'date': date_str, 'cost': interpolated_cost})
            
            current_date += timedelta(days=1)
        
        return complete_data
    
    def _interpolate_value(
        self,
        target_date: str,
        date_map: Dict[str, float],
        start_date,
        end_date
    ) -> float:
        """Linear interpolation for missing date."""
        # Find nearest dates with data
        target = datetime.fromisoformat(target_date).date()
        
        # Find previous date with data
        prev_date = None
        prev_cost = None
        current = target - timedelta(days=1)
        while current >= start_date:
            if current.isoformat() in date_map:
                prev_date = current
                prev_cost = date_map[current.isoformat()]
                break
            current -= timedelta(days=1)
        
        # Find next date with data
        next_date = None
        next_cost = None
        current = target + timedelta(days=1)
        while current <= end_date:
            if current.isoformat() in date_map:
                next_date = current
                next_cost = date_map[current.isoformat()]
                break
            current += timedelta(days=1)
        
        # Interpolate
        if prev_date and next_date:
            # Linear interpolation
            days_diff = (next_date - prev_date).days
            days_from_prev = (target - prev_date).days
            ratio = days_from_prev / days_diff
            return prev_cost + (next_cost - prev_cost) * ratio
        elif prev_date:
            # Use previous value
            return prev_cost
        elif next_date:
            # Use next value
            return next_cost
        else:
            # No data available, use 0
            return 0.0
        
    def validate_completeness(self, data: List[Dict], days_back: int) -> bool:
        """
        Check if data meets minimum requirements.
        
        Args:
            data: List of data points
            days_back: Expected number of days
            
        Returns:
            True if data is sufficient (at least 30 days)
        """
        if not data:
            return False
        
        # Check minimum 30 days of data
        unique_dates = set(item['date'] for item in data)
        return len(unique_dates) >= 30
