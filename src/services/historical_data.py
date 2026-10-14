"""
Historical Data Retriever for forecast input preparation.

This module retrieves and preprocesses historical cost data:
1. Data retrieval from DynamoDB (Phase 1 data)
2. Aggregation by service and date
3. Explicit missing-date coverage (no active-path interpolation)
4. Data validation and completeness checking
"""

from typing import Optional, List, Dict
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from src.utils.types import InsufficientDataError, ProcessedData
from src.utils.helpers import normalize_service_name
from src.services.dynamodb import _generate_year_months


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
        # Forecasts use completed daily observations, never monthly aggregates
        # or interpolated records counted as observed days.
        end_date = datetime.now(UTC).date() - timedelta(days=1)
        start_date = end_date - timedelta(days=days_back-1)
        raw = self._query_dynamodb(start_date, end_date, service)
        unique = {}
        for item in raw:
            if item.get('granularity') != 'DAILY': continue
            key = (item['service'], item['date'])
            if key not in unique or item.get('sk', '').endswith('#DAILY'): unique[key] = item
        daily = list(unique.values())
        observed = sorted({item['date'] for item in daily})
        if len(observed) < 7:
            raise InsufficientDataError('At least 7 distinct DAILY observations are required; legacy records without granularity need an authorized daily backfill')
        if any(item.get('currency') != 'USD' for item in daily): raise InsufficientDataError('Forecasting requires consistent USD daily observations')
        aggregated = self.aggregate_by_service_and_date(daily)
        totals = {}
        for points in aggregated.values():
            for point in points: totals[point['date']] = totals.get(point['date'], 0.0) + point['cost']
        expected = {(start_date+timedelta(days=index)).isoformat() for index in range(days_back)}
        return ProcessedData(timestamps=sorted(totals), costs=[totals[day] for day in sorted(totals)], service=service,
            total_days=len(totals), observed_days=len(observed), missing_dates=sorted(expected-set(observed)),
            history_method='observed_only', cost_metric='BlendedCost',
            estimated_dates=sorted({item['date'] for item in daily if item.get('is_estimated') is True}),
            unknown_estimate_dates=sorted({item['date'] for item in daily if item.get('is_estimated') is None}))

    def _query_dynamodb(
        self,
        start_date,
        end_date,
        service: Optional[str]
    ) -> List[Dict]:
        """
        Query DynamoDB for cost data within date range.
        Uses Query by pk (COST#YYYY-MM) to match table schema; avoids full table Scan.
        """
        start_ym = f"{start_date.year:04d}-{start_date.month:02d}"
        end_ym = f"{end_date.year:04d}-{end_date.month:02d}"
        year_months = _generate_year_months(start_ym, end_ym)
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        items = []

        for year_month in year_months:
            pk_value = f"COST#{year_month}"
            expr_values = {
                ':pk': pk_value,
                ':start_date': start_str,
                ':end_date': end_str,
            }
            key_condition = 'pk = :pk'
            if service:
                sk_prefix = f"SERVICE#{normalize_service_name(service)}#"
                key_condition += ' AND begins_with(sk, :sk_prefix)'
                expr_values[':sk_prefix'] = sk_prefix

            last_key = None
            while True:
                query_params = {
                    'KeyConditionExpression': key_condition,
                    'ExpressionAttributeValues': expr_values,
                    'ExpressionAttributeNames': {'#dt': 'date'},
                    'FilterExpression': '#dt between :start_date and :end_date',
                }
                if last_key:
                    query_params['ExclusiveStartKey'] = last_key
                response = self.table.query(**query_params)
                items.extend(response.get('Items', []))
                last_key = response.get('LastEvaluatedKey')
                if not last_key:
                    break
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
            cost = next((item[key] for key in ('blendedCost', 'cost', 'unblendedCost') if key in item), None)
            if cost is None: raise InsufficientDataError('A historical cost observation has no amount')
            cost = Decimal(str(cost)) if not isinstance(cost, Decimal) else cost
            if not cost.is_finite(): raise InsufficientDataError('Historical cost observations must be finite')
            
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
            True if data is sufficient (at least 7 days)
        """
        if not data:
            return False
        
        # Check minimum 7 days of data (allow 7-day forecast with limited history)
        unique_dates = set(item['date'] for item in data)
        return len(unique_dates) >= 7
