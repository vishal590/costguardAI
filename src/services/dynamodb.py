"""
DynamoDB service for storing and querying AWS cost data.
"""
import boto3
from datetime import datetime, timezone, date
from typing import List, Optional, Dict, Any
from decimal import Decimal

from ..utils.types import CostRecord, DynamoDBRecord, QueryParams, RetryConfig
from ..utils.error_handler import with_retry
from ..utils.helpers import calculate_ttl, normalize_service_name


def _generate_year_months(start_year_month: str, end_year_month: str) -> List[str]:
    """
    Generate a list of year-month strings between start and end (inclusive).
    
    Args:
        start_year_month: Start year-month in YYYY-MM format
        end_year_month: End year-month in YYYY-MM format
        
    Returns:
        List of year-month strings in YYYY-MM format
        
    Example:
        _generate_year_months('2024-11', '2025-02') -> ['2024-11', '2024-12', '2025-01', '2025-02']
    """
    result = []
    
    # Parse start and end dates
    start_year, start_month = map(int, start_year_month.split('-'))
    end_year, end_month = map(int, end_year_month.split('-'))
    
    current_year = start_year
    current_month = start_month
    
    while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
        result.append(f"{current_year:04d}-{current_month:02d}")
        
        # Move to next month
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
    
    return result


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
                    # Use pk/sk as partition and sort keys per table schema
                    item = {
                        'pk': record.pk,  # COST#YYYY-MM
                        'sk': record.sk,  # SERVICE#service-name
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
    Query cost data from DynamoDB using efficient Query operations.
    
    Uses partition key (pk) for date range queries and sort key (sk) for service filtering.
    Falls back to Scan only when no start_date is provided (requires date range for efficient Query).
    
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
    
    results = []
    
    # Determine query strategy based on parameters
    # Strategy 1: Query by date range (using pk = COST#YYYY-MM)
    # Strategy 2: If service filter provided, use sort key begins_with filter
    # Strategy 3: If no date range provided, use Scan (fallback)
    
    # If only start_date provided, use today as end_date for Query operations
    effective_end_date = params.end_date
    if params.start_date and not params.end_date:
        effective_end_date = date.today().strftime('%Y-%m-%d')
    
    if params.start_date:
        # Extract year-months from date range
        start_parts = params.start_date.split('-')
        end_parts = effective_end_date.split('-')
        start_year_month = f"{start_parts[0]}-{start_parts[1]}"
        end_year_month = f"{end_parts[0]}-{end_parts[1]}"
        
        # Generate list of year-months to query
        year_months = _generate_year_months(start_year_month, end_year_month)
        
        # Query each month partition
        for year_month in year_months:
            pk_value = f"COST#{year_month}"
            
            def query_operation():
                query_params = {
                    'KeyConditionExpression': 'pk = :pk',
                    'ExpressionAttributeValues': {
                        ':pk': pk_value
                    }
                }
                
                # Add service filter using sort key begins_with
                if params.service:
                    normalized_service = normalize_service_name(params.service)
                    sk_prefix = f"SERVICE#{normalized_service}"
                    query_params['KeyConditionExpression'] += ' AND begins_with(sk, :sk_prefix)'
                    query_params['ExpressionAttributeValues'][':sk_prefix'] = sk_prefix
                
                # Add date range filter on date attribute (for daily granularity)
                filter_expressions = []
                expression_values = query_params['ExpressionAttributeValues'].copy()
                expression_names = {}
                
                if params.start_date:
                    filter_expressions.append('#dt >= :start_date')
                    expression_values[':start_date'] = params.start_date
                    expression_names['#dt'] = 'date'
                
                if effective_end_date:
                    filter_expressions.append('#dt <= :end_date')
                    expression_values[':end_date'] = effective_end_date
                    if '#dt' not in expression_names:
                        expression_names['#dt'] = 'date'
                
                if filter_expressions:
                    query_params['FilterExpression'] = ' AND '.join(filter_expressions)
                    query_params['ExpressionAttributeValues'] = expression_values
                    if expression_names:
                        query_params['ExpressionAttributeNames'] = expression_names
                
                # Handle pagination
                all_items = []
                last_evaluated_key = None
                
                while True:
                    if last_evaluated_key:
                        query_params['ExclusiveStartKey'] = last_evaluated_key
                    
                    response = table.query(**query_params)
                    all_items.extend(response.get('Items', []))
                    
                    last_evaluated_key = response.get('LastEvaluatedKey')
                    if not last_evaluated_key:
                        break
                
                return all_items
            
            items = with_retry(query_operation, retry_config)
            
            # Convert items to DynamoDBRecord objects
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
                results.append(record)
    else:
        # No date range provided - fall back to Scan (inefficient but necessary)
        # This should be rare in practice
        def scan_operation():
            scan_params = {}
            filter_expressions = []
            expression_values = {}
            expression_names = {}
            
            # Add date range filter
            if params.start_date:
                filter_expressions.append('#dt >= :start_date')
                expression_values[':start_date'] = params.start_date
                expression_names['#dt'] = 'date'
            
            if params.end_date:
                filter_expressions.append('#dt <= :end_date')
                expression_values[':end_date'] = params.end_date
                expression_names['#dt'] = 'date'
            
            # Add service filter
            if params.service:
                filter_expressions.append('service = :service')
                expression_values[':service'] = params.service
            
            # Build filter expression
            if filter_expressions:
                scan_params['FilterExpression'] = ' AND '.join(filter_expressions)
                scan_params['ExpressionAttributeValues'] = expression_values
                if expression_names:
                    scan_params['ExpressionAttributeNames'] = expression_names
            
            # Add limit
            if params.limit:
                scan_params['Limit'] = params.limit
            
            # Execute scan with pagination
            all_items = []
            last_evaluated_key = None
            
            while True:
                if last_evaluated_key:
                    scan_params['ExclusiveStartKey'] = last_evaluated_key
                
                response = table.scan(**scan_params)
                all_items.extend(response.get('Items', []))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
                
                # Respect limit across pagination
                if params.limit and len(all_items) >= params.limit:
                    break
            
            return all_items[:params.limit] if params.limit else all_items
        
        items = with_retry(scan_operation, retry_config)
        
        # Convert items to DynamoDBRecord objects
        for item in items:
            record = DynamoDBRecord(
                pk=item.get('pk'),
                sk=item.get('sk'),
                date=item['date'],
                service=item['service'],
                blended_cost=float(item['blendedCost']),
                unblended_cost=float(item['unblendedCost']),
                currency=item['currency'],
                unit=item['unit'],
                timestamp=item['timestamp'],
                ttl=item.get('ttl')
            )
            results.append(record)
    
    # Apply limit if specified (for Query operations across multiple partitions)
    if params.limit and len(results) > params.limit:
        results = results[:params.limit]
    
    return results

