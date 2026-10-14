"""
DynamoDB service for storing and querying AWS cost data.
"""
import boto3
from datetime import datetime, timezone, date
from typing import List, Optional, Dict, Any
from decimal import Decimal

from ..utils.types import CostRecord, DynamoDBRecord, QueryParams, RetryConfig
from ..utils.error_handler import with_retry
from ..utils.helpers import calculate_ttl, normalize_service_name, cost_explorer_service_to_short


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
    
    # Sort key must be unique per (month, service, date) to avoid DynamoDB "duplicate keys" in batch write.
    # Map Cost Explorer long name to short (ec2, lambda, ...) so Phase 1 query and Phase 2 forecast by service find data.
    canonical_service = cost_explorer_service_to_short(record.service)
    sk = f"SERVICE#{canonical_service}#{record.date}#{record.granularity}"
    
    # Calculate TTL
    ttl = calculate_ttl(ttl_days)
    
    # Get current timestamp
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    return DynamoDBRecord(
        pk=pk,
        sk=sk,
        date=record.date,
        service=canonical_service,
        blended_cost=record.blended_cost,
        unblended_cost=record.unblended_cost,
        currency=record.currency,
        unit=record.unit,
        timestamp=timestamp,
        ttl=ttl, granularity=record.granularity, period_end=record.period_end, is_estimated=record.is_estimated
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
                        'timestamp': record.timestamp,
                        'granularity': record.granularity,
                        'is_estimated': record.is_estimated,
                        **({'period_end': record.period_end} if record.period_end else {})
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
    """Read one granularity; prefer canonical records over pre-migration keys.

    Date-filtered reads use monthly partitions. Undated legacy callers retain
    the scan fallback. The limit applies after deduplication and newest sorting.
    """
    if params.granularity not in ('DAILY', 'MONTHLY', 'HOURLY', 'UNKNOWN'):
        raise ValueError('Unsupported cost history granularity')
    table = (dynamodb_resource or boto3.resource('dynamodb')).Table(table_name)
    retry = RetryConfig(max_retries=3, base_delay=1.0, max_delay=8.0)
    names = {'#grain': 'granularity'}
    values = {':grain': params.granularity}
    filters = ['#grain = :grain']
    if params.granularity == 'UNKNOWN':
        filters = ['(attribute_not_exists(#grain) OR #grain = :grain)']
    end = params.end_date or (date.today().isoformat() if params.start_date else None)
    if params.start_date:
        names['#dt'] = 'date'
        values[':start'] = params.start_date
        filters.append('#dt >= :start')
    if end:
        names['#dt'] = 'date'
        values[':end'] = end + 'T23:59:59.999999Z' if params.granularity == 'HOURLY' else end
        filters.append('#dt <= :end')
    if params.service:
        names['#service'] = 'service'
        values[':service'] = cost_explorer_service_to_short(params.service)
        filters.append('#service = :service')
    months = _generate_year_months(params.start_date[:7], end[:7]) if params.start_date else [None]
    unique = {}
    for month in months:
        request = {'FilterExpression': ' AND '.join(filters),
                   'ExpressionAttributeNames': dict(names),
                   'ExpressionAttributeValues': dict(values)}
        if month:
            request['KeyConditionExpression'] = 'pk = :pk'
            request['ExpressionAttributeValues'][':pk'] = f'COST#{month}'
            if params.service:
                request['KeyConditionExpression'] += ' AND begins_with(sk, :prefix)'
                request['ExpressionAttributeValues'][':prefix'] = f'SERVICE#{cost_explorer_service_to_short(params.service)}#'
        while True:
            response = with_retry(lambda: table.query(**request) if month else table.scan(**request), retry)
            for item in response.get('Items', []):
                identity = (item['service'], item['date'], item.get('granularity', 'UNKNOWN'))
                previous = unique.get(identity)
                canonical = item.get('sk', '').endswith('#' + identity[2])
                if previous is None or canonical:
                    unique[identity] = item
            cursor = response.get('LastEvaluatedKey')
            if not cursor:
                break
            request['ExclusiveStartKey'] = cursor
    items = sorted(unique.values(), key=lambda item: (item['date'], item['service']), reverse=True)
    if params.before_date is not None:
        items = [item for item in items if (item['date'], item['service']) < (params.before_date, params.before_service)]
    if params.limit is not None:
        items = items[:params.limit]
    return [DynamoDBRecord(
        pk=item['pk'], sk=item['sk'], date=item['date'], service=item['service'],
        blended_cost=float(item['blendedCost']), unblended_cost=float(item['unblendedCost']),
        currency=item['currency'], unit=item['unit'], timestamp=item['timestamp'],
        ttl=item.get('ttl'), granularity=item.get('granularity', 'UNKNOWN'), period_end=item.get('period_end', item.get('periodEnd')), is_estimated=item.get('is_estimated')
    ) for item in items]
