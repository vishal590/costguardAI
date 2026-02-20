"""
Type definitions and data classes for the Cost Data Pipeline.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from decimal import Decimal

# Type aliases
Granularity = Literal['DAILY', 'MONTHLY', 'HOURLY']
SupportedService = Literal['ec2', 'lambda', 'dynamodb', 's3', 'rds']

ErrorCode = Literal[
    'INVALID_DATE_FORMAT',
    'INVALID_DATE_RANGE',
    'INVALID_GRANULARITY',
    'COST_EXPLORER_ERROR',
    'COST_EXPLORER_RATE_LIMIT',
    'COST_EXPLORER_ACCESS_DENIED',
    'DYNAMODB_ERROR',
    'DYNAMODB_THROTTLING',
    'VALIDATION_ERROR',
    'INTERNAL_ERROR',
    'CLOUDWATCH_ERROR',
    'PRICING_ERROR',
    'CALCULATION_ERROR',
    'AUTHENTICATION_ERROR'
]


@dataclass
class CostRecord:
    """Cost record from Cost Explorer API."""
    date: str
    service: str
    blended_cost: float
    unblended_cost: float
    currency: str
    unit: str


@dataclass
class DynamoDBRecord:
    """DynamoDB record format for cost data."""
    pk: str              # "COST#YYYY-MM"
    sk: str              # "SERVICE#service-name"
    date: str            # YYYY-MM-DD
    service: str
    blended_cost: float
    unblended_cost: float
    currency: str
    unit: str
    timestamp: str       # ISO 8601
    ttl: Optional[int] = None   # Unix timestamp


@dataclass
class QueryParams:
    """Parameters for querying cost data."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    service: Optional[str] = None
    limit: Optional[int] = None


@dataclass
class ErrorResponse:
    """Structured error response."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_retries: int
    base_delay: float  # seconds
    max_delay: float   # seconds


# ============================================================================
# Phase 1.5 Data Models - Near-Real-Time Cost Estimation
# ============================================================================

@dataclass
class MetricDataPoint:
    """CloudWatch metric data point."""
    timestamp: datetime
    value: Decimal
    unit: str
    metric_name: str


@dataclass
class EC2Metrics:
    """EC2 usage metrics from CloudWatch."""
    instance_id: str
    instance_type: str
    cpu_utilization: Decimal
    network_in: Decimal
    network_out: Decimal
    disk_read_bytes: Decimal
    running_hours: Decimal


@dataclass
class LambdaMetrics:
    """Lambda usage metrics from CloudWatch."""
    function_name: str
    invocations: int
    duration_ms: Decimal
    memory_mb: int
    errors: int


@dataclass
class DynamoDBMetrics:
    """DynamoDB usage metrics from CloudWatch."""
    table_name: str
    consumed_read_capacity: Decimal
    consumed_write_capacity: Decimal


@dataclass
class S3Metrics:
    """S3 usage metrics from CloudWatch."""
    bucket_name: str
    number_of_objects: int
    bucket_size_bytes: Decimal
    get_requests: int
    put_requests: int


@dataclass
class RDSMetrics:
    """RDS usage metrics from CloudWatch."""
    instance_id: str
    instance_type: str
    database_connections: int
    read_iops: Decimal
    write_iops: Decimal
    storage_gb: Decimal
    running_hours: Decimal


@dataclass
class PricingData:
    """AWS service pricing information."""
    service: str
    region: str
    prices: Dict[str, Decimal]
    currency: str
    last_updated: datetime
    ttl: int


@dataclass
class EC2Pricing:
    """EC2 pricing information."""
    instance_prices: Dict[str, Decimal]  # instance_type -> price_per_hour
    data_transfer_out: Decimal  # price per GB
    currency: str


@dataclass
class LambdaPricing:
    """Lambda pricing information."""
    price_per_request: Decimal
    price_per_gb_second: Decimal
    currency: str


@dataclass
class DynamoDBPricing:
    """DynamoDB pricing information."""
    price_per_read_unit: Decimal
    price_per_write_unit: Decimal
    currency: str


@dataclass
class S3Pricing:
    """S3 pricing information."""
    price_per_gb_storage: Decimal
    price_per_get_request: Decimal
    price_per_put_request: Decimal
    currency: str


@dataclass
class RDSPricing:
    """RDS pricing information."""
    instance_prices: Dict[str, Decimal]  # instance_type -> price_per_hour
    storage_price_per_gb: Decimal
    iops_price: Decimal
    currency: str


@dataclass
class CostEstimate:
    """Cost estimate for a service."""
    service: str
    estimated_cost: Decimal
    currency: str
    confidence_lower: Decimal
    confidence_upper: Decimal
    timestamp: datetime
    period_start: datetime
    period_end: datetime
    metrics_count: int


@dataclass
class EstimationResponse:
    """API response for cost estimation."""
    success: bool
    estimates: List[CostEstimate]
    total_cost: Decimal
    currency: str
    timestamp: datetime
    period: str
