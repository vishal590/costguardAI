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
                    # Use date_service as partition key to match table schema
                    item = {
                        'date_service': f"{record.date}#{record.service}",
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
    
    # Since our table uses date_service as a single partition key (format: "2026-02-01#AWS Lambda"),
    # we need to scan with filters instead of querying by partition key
    
    def scan_operation():
        scan_params = {}
        filter_expressions = []
        expression_values = {}
        expression_names = {}
        
        # Add date range filter (date is a reserved keyword, so use expression attribute names)
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
        
        # Add expression attribute names if we used any
        if expression_names:
            scan_params['ExpressionAttributeNames'] = expression_names
        
        # Add limit
        if params.limit:
            scan_params['Limit'] = params.limit
        
        # Execute scan
        response = table.scan(**scan_params)
        return response.get('Items', [])
    
    items = with_retry(scan_operation, retry_config)
    
    # Convert items to DynamoDBRecord objects
    for item in items:
        record = DynamoDBRecord(
            pk=None,  # Not used in new schema
            sk=None,  # Not used in new schema
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
    
    return results

