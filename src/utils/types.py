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
    granularity: str = "UNKNOWN"
    period_end: Optional[str] = None
    is_estimated: Optional[bool] = None


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
    granularity: str = "UNKNOWN"
    period_end: Optional[str] = None
    is_estimated: Optional[bool] = None


@dataclass
class QueryParams:
    """Parameters for querying cost data."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    service: Optional[str] = None
    limit: Optional[int] = None
    granularity: str = "DAILY"
    before_date: Optional[str] = None
    before_service: Optional[str] = None


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
    billing_profile: str = "unknown"


@dataclass
class LambdaMetrics:
    """Lambda usage metrics from CloudWatch."""
    function_name: str
    invocations: int
    duration_ms: Decimal
    memory_mb: int
    errors: int
    billing_profile: str = "unknown"


@dataclass
class DynamoDBMetrics:
    """DynamoDB usage metrics from CloudWatch."""
    table_name: str
    consumed_read_capacity: Decimal
    consumed_write_capacity: Decimal
    billing_profile: str = "unknown"


@dataclass
class S3Metrics:
    """S3 usage metrics from CloudWatch."""
    bucket_name: str
    number_of_objects: int
    bucket_size_bytes: Decimal
    get_requests: int
    put_requests: int
    billing_profile: str = "unknown"


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
    billing_profile: str = "unknown"


@dataclass
class PricingData:
    """AWS service pricing information."""
    service: str
    region: str
    prices: Dict[str, Decimal]
    currency: str
    last_updated: datetime
    ttl: int
    source: str = "unknown"
    pricing_profile: str = "unspecified"


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
    estimated_cost: Optional[Decimal]
    currency: str
    confidence_lower: Optional[Decimal]
    confidence_upper: Optional[Decimal]
    timestamp: datetime
    period_start: datetime
    period_end: datetime
    metrics_count: int
    status: str = "estimated"
    pricing_source: str = "unknown"
    reason: Optional[str] = None
    pricing_profile: str = "unspecified"
    range_method: str = "unavailable"
    covered_components: Optional[List[str]] = None
    missing_components: Optional[List[str]] = None


@dataclass
class EstimationResponse:
    """API response for cost estimation."""
    success: bool
    estimates: List[CostEstimate]
    total_cost: Decimal
    currency: str
    timestamp: datetime
    period: str


# ============================================================================
# Phase 2: AI Cost Forecasting Data Models
# ============================================================================

@dataclass
class ForecastDataPoint:
    """Single forecast data point with confidence interval."""
    date: str  # ISO 8601 format (YYYY-MM-DD)
    predicted_cost: float  # Predicted cost in USD
    confidence_lower: float  # Lower uncalibrated uncertainty bound
    confidence_upper: float  # Upper uncalibrated uncertainty bound
    currency: str = "USD"


@dataclass
class ForecastMetadata:
    """Metadata for forecast response."""
    timestamp: str  # ISO 8601 timestamp
    forecast_horizon: int  # Days forecasted
    granularity: str  # "daily" or "weekly"
    model_used: str  # "amazon.nova-lite-v1:0"
    service: Optional[str]  # Service name or None for total
    services_included: Optional[List[str]]  # For total forecasts
    cache_hit: bool  # True if returned from cache
    historical_data_days: int  # Days of historical data used
    range_method: str = "unspecified"
    observed_history_days: Optional[int] = None
    missing_history_dates: Optional[List[str]] = None
    history_method: str = "observed_only"
    cost_metric: str = "unspecified"
    forecast_start_date: Optional[str] = None
    estimated_dates: Optional[List[str]] = None
    unknown_estimate_dates: Optional[List[str]] = None


@dataclass
class ForecastResponse:
    """Complete forecast response."""
    success: bool
    forecast_data: List[ForecastDataPoint]
    metadata: ForecastMetadata


@dataclass
class CachedForecast:
    """Cached forecast with TTL."""
    cache_key: str
    forecast_response: ForecastResponse
    created_at: datetime
    ttl: int  # Unix timestamp for expiration


@dataclass
class ProcessedData:
    """Preprocessed historical data for Bedrock."""
    timestamps: List[str]  # ISO 8601 dates
    costs: List[float]  # Corresponding costs
    service: Optional[str]  # Service name
    total_days: int  # Number of actual observed dates
    observed_days: Optional[int] = None
    missing_dates: Optional[List[str]] = None
    history_method: str = "observed_only"
    cost_metric: str = "unspecified"
    forecast_start_date: Optional[str] = None
    estimated_dates: Optional[List[str]] = None
    unknown_estimate_dates: Optional[List[str]] = None


@dataclass
class BedrockRequest:
    """Request format for Bedrock API."""
    historical_data: ProcessedData
    forecast_horizon: int
    confidence_level: float = 0.95


@dataclass
class BedrockResponse:
    """Response from Bedrock API."""
    predictions: List[float]  # Predicted costs
    confidence_lower: List[float]  # Lower bounds
    confidence_upper: List[float]  # Upper bounds
    dates: List[str]  # Forecast dates
    model_id: str
    latency_ms: int
    range_method: str = "unspecified"


# Custom exceptions for Phase 2
class InsufficientDataError(Exception):
    """Raised when historical data is insufficient for forecasting."""
    pass


class BedrockAPIError(Exception):
    """Raised when Bedrock API call fails."""
    pass


class BedrockRateLimitError(Exception):
    """Raised when Bedrock rate limit is exceeded."""
    pass


class BedrockInvalidResponseError(Exception):
    """Raised when Bedrock returns invalid JSON."""
    pass


# ============================================================================
# Phase 3: Automated Cost Prevention Data Models
# ============================================================================

@dataclass
class BudgetStatus:
    """AWS Budget status information."""
    budget_name: str
    limit: float
    actual_spend: float
    forecasted_spend: Optional[float]
    utilization_percent: float
    currency: str
    time_period: str


@dataclass
class ThresholdEvent:
    """Budget threshold breach event."""
    budget_name: str
    threshold_type: str  # "warning" or "action"
    utilization_percent: float
    timestamp: str
    budget_status: BudgetStatus


@dataclass
class Resource:
    """AWS resource information."""
    resource_id: str
    resource_type: str  # "instance", "db_instance", "function", etc.
    service: str  # "ec2", "rds", "lambda", etc.
    region: str
    tags: Dict[str, str]
    state: str
    creation_date: Optional[str]
    properties: Optional[Dict[str, Any]] = None


@dataclass
class ResourceMetadata:
    """Detailed resource metadata."""
    resource: Resource
    cost_per_hour: Optional[float]
    last_activity: Optional[str]
    metrics: Dict[str, float]


@dataclass
class IdleStatus:
    """Resource idle status."""
    resource_id: str
    is_idle: bool
    idle_duration: int  # minutes
    metrics_used: Dict[str, float]
    confidence: Optional[float]  # None without a calibrated confidence model
    observation_status: str = "unavailable"
    reason: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    confidence_method: str = "unavailable"


@dataclass
class IdleCriteria:
    """Idle detection criteria for a service."""
    service: str
    metric_name: str
    threshold: float
    duration_minutes: int


@dataclass
class SafetyCheck:
    """Safety check result."""
    is_safe: bool
    blocked_reason: Optional[str]
    checks_performed: List[str]


@dataclass
class SafetyConfig:
    """Safety guard configuration."""
    protected_tags: List[str]
    whitelist_ids: List[str]
    minimum_idle_minutes: Dict[str, int]
    dry_run_mode: bool


@dataclass
class ActionResult:
    """Result of an automated action."""
    resource_id: str
    action: str
    success: bool
    error_message: Optional[str]
    pre_action_state: Dict[str, Any]
    post_action_state: Dict[str, Any]
    estimated_savings: Optional[float]
    timestamp: str


@dataclass
class PlannedAction:
    """Planned action for approval."""
    resource_id: str
    resource_type: str
    action: str
    reason: str
    estimated_savings: Optional[float]


@dataclass
class ApprovalRequest:
    """Approval request for automated actions."""
    request_id: str
    actions: List[PlannedAction]
    total_estimated_savings: Optional[float]
    expires_at: str


@dataclass
class ApprovalResponse:
    """Response to approval request."""
    request_id: str
    approved: bool
    approved_by: Optional[str]
    timestamp: str


@dataclass
class RollbackResult:
    """Result of a rollback operation."""
    action_id: str
    resource_id: str
    success: bool
    restored_state: Dict[str, Any]
    timestamp: str
    error_message: Optional[str] = None


@dataclass
class NotificationConfig:
    """Notification service configuration."""
    warning_topic_arn: Optional[str]
    action_topic_arn: Optional[str]
    error_topic_arn: Optional[str]


# ============================================================================
# Phase 4: AI Cost Advisor Data Models
# ============================================================================

@dataclass
class QueryIntent:
    """Parsed natural language query intent."""
    intent_type: str  # "cost_analysis", "optimization", "trend_analysis", "forecast", "prevention"
    services: List[str]  # AWS service identifiers
    time_range: tuple  # (start_date, end_date)
    accounts: List[str]  # AWS account IDs
    entities: Dict[str, Any]  # Extracted entities (resource IDs, etc.)


@dataclass
class CostContext:
    """Cost data context for AI advisor."""
    historical_costs: Dict[str, List[Dict[str, Any]]]  # Service -> cost data
    forecast_data: Optional[Dict[str, List[Dict[str, Any]]]]
    prevention_actions: List[Dict[str, Any]]
    current_budget: Optional[BudgetStatus]
    anomalies: List[Dict[str, Any]]
    data_quality: Optional[Dict[str, Any]] = None
    prompt_metadata: Optional[Dict[str, Any]] = None


@dataclass
class ConversationTurn:
    """Single conversation turn."""
    query: str
    response: str
    timestamp: datetime
    context_used: Optional[CostContext]


@dataclass
class AdvisorResponse:
    """AI advisor response."""
    response_text: str  # Formatted markdown response
    recommendations: List['Recommendation']
    cost_data: Dict[str, Any]  # Structured cost data
    confidence: Optional[float]  # None unless an actual calibrated score is available
    cached: bool  # Whether response was cached
    confidence_method: str = "unavailable"
    status: str = "available"


@dataclass
class Recommendation:
    """Cost optimization recommendation."""
    action: str  # Description of recommended action
    rationale: str  # Why this is recommended
    estimated_savings: Optional[float]  # Unavailable without verified monetary attribution
    priority: Optional[int]  # Unavailable without an explicit ranking basis
    safe: Optional[bool]  # Unavailable without an actual safety assessment


@dataclass
class Insight:
    """Proactive cost insight."""
    insight_type: str  # "summary", "anomaly", "optimization", "forecast_alert"
    title: str
    description: str
    severity: str  # "info", "warning", "critical"
    action_required: bool
    related_services: List[str]
    estimated_impact: Optional[float]  # Cost impact
    method: Optional[str] = None
    data_quality: Optional[Dict[str, Any]] = None
