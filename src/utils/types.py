"""
Type definitions and data classes for the Cost Data Pipeline.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Literal

# Type aliases
Granularity = Literal['DAILY', 'MONTHLY', 'HOURLY']
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
    'INTERNAL_ERROR'
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
