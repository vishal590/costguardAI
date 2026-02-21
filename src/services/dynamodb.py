"""
DynamoDB service for storing and querying AWS cost data.
"""
import boto3
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from decimal import Decimal

from ..utils.types import CostRecord, DynamoDBRecord, QueryParams, RetryConfig
from ..utils.error_handler import with_retry
from ..utils.helpers import calculate_ttl, normalize_service_name


def get_dynamodb_client():
    """
    Get DynamoDB client instance.
    
    Returns:
        boto3 DynamoDB client
    """
    return boto3.client('dynamodb')


def transform_to_dynamodb_record(record: CostRecord, ttl_days: int = 365) -> DynamoDBRecord:
    """
    Transform a CostRecord to DynamoDB format.
    
    Args:
        record: CostRecord from Cost Explorer
        ttl_days: Number of days until record expires (default: 365)
        
    Returns:
        DynamoDBRecord with partition key and sort key
    """
    # Extract year-month from date (YYYY-MM-DD -> YYYY-MM)
    date_parts = record.date.split('-')
    year_month = f"{date_parts[0]}-{date_parts[1]}"
    
    # Create partition key: COST#YYYY-MM
    pk = f"COST#{year_month}"
    
    # Create sort key: SERVICE#normalized-service-name
    normalized_service = normalize_service_name(record.service)
    sk = f"SERVICE#{normalized_service}"
    
    # Calculate TTL
    ttl = calculate_ttl(ttl_days)
    
    # Get current timestamp
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    return DynamoDBRecord(
        pk=pk,
        sk=sk,
        date=record.date,
        service=record.service,
        blended_cost=record.blended_cost,
        unblended_cost=record.unblended_cost,
        currency=record.currency,
        unit=record.unit,
        timestamp=timestamp,
        ttl=ttl
    )


def store_cost_data(
    records: List[CostRecord],
    table_name: str = 'costguard-cost-data',
    dynamodb_resource: Optional[object] = None
) -> None:
    """
    Store cost records in DynamoDB using batch write operations.
    
    Args:
        records: List of CostRecord objects to store
        table_name: Name of the DynamoDB table
        dynamodb_resource: Optional boto3 DynamoDB resource (for testing)
        
    Raises:
        ClientError: If DynamoDB operations fail after retries
    """
    if not records:
        return
    
    # Initialize DynamoDB resource
    if dynamodb_resource is None:
        dynamodb_resource = boto3.resource('dynamodb')
    
    table = dynamodb_resource.Table(table_name)
    
    # Transform records to DynamoDB format
    dynamodb_records = [transform_to_dynamodb_record(record) for record in records]
    
    # Configure retry logic
    retry_config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=8.0
    )
    
    # Split into batches of 25 (DynamoDB limit)
    batch_size = 25
    for i in range(0, len(dynamodb_records), batch_size):
        batch = dynamodb_records[i:i + batch_size]
        _write_batch(table, batch, retry_config)


def _write_batch(table: object, batch: List[DynamoDBRecord], retry_config: RetryConfig) -> None:
    """
    Write a batch of records to DynamoDB with retry logic.
    
    Args:
        table: DynamoDB table object
        batch: List of DynamoDBRecord objects (max 25)
        retry_config: Retry configuration
    """
    unprocessed_items = batch
    
    while unprocessed_items:
        # Prepare batch write request
        def batch_write():
            with table.batch_writer() as writer:
                for record in unprocessed_items:
                    # Convert to DynamoDB format (handle Decimal for numbers)
                    item = {
                        'pk': record.pk,
                        'sk': record.sk,
                        'date': record.date,
                        'service': record.service,
                        'blendedCost': Decimal(str(record.blended_cost)),
                        'unblendedCost': Decimal(str(record.unblended_cost)),
                        'currency': record.currency,
                        'unit': record.unit,
                        'timestamp': record.timestamp
                    }
                    
                    if record.ttl:
                        item['ttl'] = record.ttl
                    
                    writer.put_item(Item=item)
            
            return []  # If successful, no unprocessed items
        
        try:
            unprocessed_items = with_retry(batch_write, retry_config)
        except Exception as e:
            # If retry fails, log and re-raise
            raise


def query_cost_data(
    params: QueryParams,
    table_name: str = 'costguard-cost-data',
    dynamodb_resource: Optional[object] = None
) -> List[DynamoDBRecord]:
    """
    Query cost data from DynamoDB with filters.
    
    Args:
        params: Query parameters (start_date, end_date, service, limit)
        table_name: Name of the DynamoDB table
        dynamodb_resource: Optional boto3 DynamoDB resource (for testing)
        
    Returns:
        List of DynamoDBRecord objects matching the query
        
    Raises:
        ClientError: If DynamoDB operations fail after retries
    """
    # Initialize DynamoDB resource
    if dynamodb_resource is None:
        dynamodb_resource = boto3.resource('dynamodb')
    
    table = dynamodb_resource.Table(table_name)
    
    # Configure retry logic
    retry_config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=8.0
    )
    
    # Determine query strategy based on parameters
    results = []
    
    # If start_date is provided, use it to build partition keys
    if params.start_date:
        # Extract year-month from start_date
        start_parts = params.start_date.split('-')
        start_year_month = f"{start_parts[0]}-{start_parts[1]}"
        
        # If end_date is provided, query multiple months
        if params.end_date:
            end_parts = params.end_date.split('-')
            end_year_month = f"{end_parts[0]}-{end_parts[1]}"
            
            # Generate list of year-months to query
            year_months = _generate_year_months(start_year_month, end_year_month)
        else:
            year_months = [start_year_month]
        
        # Query each year-month
        for year_month in year_months:
            pk = f"COST#{year_month}"
            month_results = _query_partition(table, pk, params, retry_config)
            results.extend(month_results)
            
            # Check limit
            if params.limit and len(results) >= params.limit:
                results = results[:params.limit]
                break
    else:
        # No start_date provided - this would require a scan
        # For Phase 1, we'll return empty results or raise an error
        # In production, you might want to scan or require start_date
        return []
    
    # Apply additional filters
    if params.service:
        normalized_service = normalize_service_name(params.service)
        results = [r for r in results if normalize_service_name(r.service) == normalized_service]
    
    # Apply limit
    if params.limit:
        results = results[:params.limit]
    
    return results


def _query_partition(
    table: object,
    pk: str,
    params: QueryParams,
    retry_config: RetryConfig
) -> List[DynamoDBRecord]:
    """
    Query a single partition in DynamoDB.
    
    Args:
        table: DynamoDB table object
        pk: Partition key value
        params: Query parameters for additional filtering
        retry_config: Retry configuration
        
    Returns:
        List of DynamoDBRecord objects from this partition
    """
    def query_operation():
        # Build query parameters
        query_params = {
            'KeyConditionExpression': 'pk = :pk',
            'ExpressionAttributeValues': {
                ':pk': pk
            }
        }
        
        # Add sort key condition if service is specified
        if params.service:
            normalized_service = normalize_service_name(params.service)
            sk = f"SERVICE#{normalized_service}"
            query_params['KeyConditionExpression'] += ' AND sk = :sk'
            query_params['ExpressionAttributeValues'][':sk'] = sk
        
        # Execute query
        response = table.query(**query_params)
        return response.get('Items', [])
    
    items = with_retry(query_operation, retry_config)
    
    # Convert items to DynamoDBRecord objects
    records = []
    for item in items:
        record = DynamoDBRecord(
            pk=item['pk'],
            sk=item['sk'],
            date=item['date'],
            service=item['service'],
            blended_cost=float(item['blendedCost']),
            unblended_cost=float(item['unblendedCost']),
            currency=item['currency'],
            unit=item['unit'],
            timestamp=item['timestamp'],
            ttl=item.get('ttl')
        )
        records.append(record)
    
    return records


def _generate_year_months(start: str, end: str) -> List[str]:
    """
    Generate a list of year-month strings between start and end.
    
    Args:
        start: Start year-month in YYYY-MM format
        end: End year-month in YYYY-MM format
        
    Returns:
        List of year-month strings in YYYY-MM format
    """
    result = []
    
    start_year, start_month = map(int, start.split('-'))
    end_year, end_month = map(int, end.split('-'))
    
    current_year = start_year
    current_month = start_month
    
    while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
        result.append(f"{current_year:04d}-{current_month:02d}")
        
        # Increment month
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
    
    return result
