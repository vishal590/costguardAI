"""
Cost Explorer service for fetching AWS cost data.
"""
import boto3
import math
from typing import List, Optional
from datetime import datetime

from ..utils.types import CostRecord, RetryConfig
from ..utils.error_handler import with_retry


class CostExplorerParams:
    """Parameters for Cost Explorer API calls."""
    
    def __init__(self, start_date: str, end_date: str, granularity: str = 'DAILY'):
        """
        Initialize Cost Explorer parameters.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: Time granularity (DAILY, MONTHLY, or HOURLY)
        """
        self.start_date = start_date
        self.end_date = end_date
        self.granularity = granularity


def fetch_cost_data(params: CostExplorerParams, client: Optional[object] = None) -> List[CostRecord]:
    """
    Fetch cost data from AWS Cost Explorer API with pagination handling.
    
    Args:
        params: Cost Explorer parameters (dates, granularity)
        client: Optional boto3 Cost Explorer client (for testing)
        
    Returns:
        List of CostRecord objects
        
    Raises:
        ClientError: If AWS API call fails after retries
    """
    # Initialize Cost Explorer client
    if client is None:
        client = boto3.client('ce')
    
    # Configure retry logic
    retry_config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=8.0
    )
    
    all_records = []
    next_token = None
    
    # Fetch all pages
    while True:
        # Build API request parameters
        request_params = {
            'TimePeriod': {
                'Start': params.start_date,
                'End': params.end_date
            },
            'Granularity': params.granularity,
            'Metrics': ['BlendedCost', 'UnblendedCost'],
            'GroupBy': [
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ]
        }
        
        # Add pagination token if present
        if next_token:
            request_params['NextPageToken'] = next_token
        
        # Call Cost Explorer API with retry logic
        def api_call():
            return client.get_cost_and_usage(**request_params)
        
        response = with_retry(api_call, retry_config)
        
        # Transform response to CostRecord objects
        records = _transform_response(response, params.granularity)
        all_records.extend(records)
        
        # Check for more pages
        next_token = response.get('NextPageToken')
        if not next_token:
            break
    
    return all_records


def _transform_response(response: dict, granularity: str = "UNKNOWN") -> List[CostRecord]:
    """
    Transform Cost Explorer API response to CostRecord objects.
    
    Args:
        response: Raw API response from get_cost_and_usage
        
    Returns:
        List of CostRecord objects
    """
    records = []
    
    # Iterate through time periods
    for result in response.get('ResultsByTime', []):
        time_period = result.get('TimePeriod', {})
        date = time_period.get('Start')
        if not date or not time_period.get('End'):
            raise ValueError('Cost Explorer returned an incomplete reporting period')
        
        # Iterate through service groups
        for group in result.get('Groups', []):
            # Extract service name
            keys = group.get('Keys', [])
            if len(keys) != 1 or not keys[0]:
                raise ValueError('Cost Explorer returned an unidentified service')
            service = keys[0]
            
            # Extract cost metrics
            metrics = group.get('Metrics', {})
            blended_cost_data = metrics.get('BlendedCost', {})
            unblended_cost_data = metrics.get('UnblendedCost', {})
            
            if 'Amount' not in blended_cost_data or 'Amount' not in unblended_cost_data:
                raise ValueError('Cost Explorer omitted a requested cost metric')
            blended_cost = float(blended_cost_data['Amount'])
            unblended_cost = float(unblended_cost_data['Amount'])
            currency = blended_cost_data.get('Unit')
            if not currency or currency != unblended_cost_data.get('Unit'):
                raise ValueError('Cost Explorer returned inconsistent cost currencies')
            if not math.isfinite(blended_cost) or not math.isfinite(unblended_cost):
                raise ValueError('Cost Explorer returned a non-finite cost amount')
            
            # Create CostRecord
            record = CostRecord(
                date=date,
                service=service,
                blended_cost=blended_cost,
                unblended_cost=unblended_cost,
                currency=currency,
                unit=currency, granularity=granularity, period_end=time_period.get("End"),
                is_estimated=result.get("Estimated") if type(result.get("Estimated")) is bool else None
            )
            
            records.append(record)
    
    return records
