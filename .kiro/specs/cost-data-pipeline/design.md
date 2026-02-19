# Design Document

## Overview

The Cost Data Pipeline is a serverless system built on AWS Lambda, DynamoDB, and API Gateway that fetches historical AWS cost data from the Cost Explorer API and makes it available through REST endpoints. The system is designed to operate within AWS Free Tier limits while providing robust error handling, efficient data storage, and fast query capabilities.

The architecture follows AWS serverless best practices with clear separation of concerns: a Lambda function handles business logic, DynamoDB provides persistent storage with efficient access patterns, and API Gateway exposes REST endpoints with API key authentication.

**Implementation Language:** Python 3.11 with boto3 AWS SDK

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│   API Gateway   │
│   (REST API)    │
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────────────────────────┐
│     Lambda Function                 │
│  ┌──────────────────────────────┐  │
│  │  Handler                     │  │
│  │  - Parse & validate input    │  │
│  │  - Route to service layer    │  │
│  └──────────┬───────────────────┘  │
│             │                       │
│  ┌──────────┴───────────────────┐  │
│  │  Cost Explorer Service       │  │
│  │  - Fetch cost data           │  │
│  │  - Handle pagination         │  │
│  │  - Transform data            │  │
│  └──────────┬───────────────────┘  │
│             │                       │
│  ┌──────────┴───────────────────┐  │
│  │  DynamoDB Service            │  │
│  │  - Store cost data           │  │
│  │  - Query cost data           │  │
│  │  - Batch operations          │  │
│  └──────────┬───────────────────┘  │
│             │                       │
│  ┌──────────┴───────────────────┐  │
│  │  Error Handler               │  │
│  │  - Retry logic               │  │
│  │  - Error formatting          │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────┐      ┌─────────────────┐
│  Cost Explorer  │      │    DynamoDB     │
│      API        │      │     Table       │
└─────────────────┘      └─────────────────┘
```

### Request Flow

**Fetch Cost Data Flow:**
1. Client sends POST request to `/api/cost-data/fetch` with optional date range and granularity
2. API Gateway validates API key and forwards to Lambda
3. Lambda validates input parameters (dates, granularity)
4. Lambda calls Cost Explorer API with pagination handling
5. Lambda transforms API response to DynamoDB format
6. Lambda stores data using batch write operations with retry logic
7. Lambda calculates summary statistics (total cost, service count, record count)
8. Lambda returns success response with summary to client

**Query Cost Data Flow:**
1. Client sends GET request to `/api/cost-data` with optional filters
2. API Gateway validates API key and forwards to Lambda
3. Lambda validates query parameters
4. Lambda queries DynamoDB using partition key and sort key
5. Lambda applies filters (date range, service, limit)
6. Lambda returns filtered cost records to client

## Components and Interfaces

### Lambda Handler

**Purpose:** Entry point for all API requests, responsible for routing and orchestration

**Interface:**
```python
from typing import Dict, Any, Optional

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler function
    
    Args:
        event: Lambda event containing:
            - httpMethod: 'GET' or 'POST'
            - path: Request path
            - queryStringParameters: Optional query parameters
            - body: Optional request body (JSON string)
            - headers: Request headers including x-api-key
        context: Lambda context object
    
    Returns:
        Dict containing:
            - statusCode: HTTP status code
            - headers: Response headers
            - body: JSON string response
    """
    pass
```

**Responsibilities:**
- Parse incoming event (API Gateway or direct invocation)
- Validate input parameters
- Route to appropriate service (fetch or query)
- Handle errors and format responses
- Log execution details to CloudWatch

### Cost Explorer Service

**Purpose:** Interact with AWS Cost Explorer API to fetch historical cost data

**Interface:**
```python
from typing import List, Dict, Any
from datetime import date

class CostExplorerParams:
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    granularity: str  # 'DAILY' | 'MONTHLY' | 'HOURLY'

class CostRecord:
    date: str
    service: str
    blended_cost: float
    unblended_cost: float
    currency: str
    unit: str

def fetch_cost_data(params: CostExplorerParams) -> List[CostRecord]:
    """Fetch cost data from Cost Explorer API"""
    pass
```

**Responsibilities:**
- Call Cost Explorer API `getCostAndUsage` method
- Handle pagination (NextPageToken)
- Transform API response to internal format
- Implement retry logic with exponential backoff for rate limits
- Extract service names and cost metrics

**Implementation Details:**
- Use boto3 for Cost Explorer client
- Group by SERVICE dimension
- Retrieve BlendedCost and UnblendedCost metrics
- Handle up to 100 pages of results (configurable)
- Retry on 429 (rate limit) and 503 (service unavailable) errors
- Maximum 3 retry attempts with exponential backoff (1s, 2s, 4s)

### DynamoDB Service

**Purpose:** Store and retrieve cost data from DynamoDB table

**Interface:**
```python
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class DynamoDBRecord:
    pk: str              # "COST#YYYY-MM"
    sk: str              # "SERVICE#service-name"
    date: str            # YYYY-MM-DD
    service: str
    blended_cost: float
    unblended_cost: float
    currency: str
    unit: str
    timestamp: str       # ISO 8601
    ttl: Optional[int]   # Unix timestamp

@dataclass
class QueryParams:
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    service: Optional[str] = None
    limit: Optional[int] = None

def store_cost_data(records: List[CostRecord]) -> None:
    """Store cost records in DynamoDB"""
    pass

def query_cost_data(params: QueryParams) -> List[DynamoDBRecord]:
    """Query cost data from DynamoDB"""
    pass
```

**Responsibilities:**
- Transform cost records to DynamoDB format
- Batch write operations (25 items per batch)
- Handle partial batch failures and retry
- Query data using partition key and sort key
- Apply filters and limits
- Implement conditional writes to prevent duplicates

**Implementation Details:**
- Use boto3 for DynamoDB client (boto3.resource('dynamodb'))
- Batch size: 25 items (DynamoDB limit)
- Retry failed items from batch write
- Use Query operation for efficient access
- Partition key format: `COST#YYYY-MM`
- Sort key format: `SERVICE#{service-name-normalized}`
- TTL set to 1 year from current date (optional)

### Error Handler

**Purpose:** Centralized error handling and retry logic

**Interface:**
```python
from typing import Callable, TypeVar, List, Dict, Any
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class RetryConfig:
    max_retries: int
    base_delay: float  # seconds
    max_delay: float   # seconds

@dataclass
class ErrorResponse:
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

def with_retry(
    operation: Callable[[], T],
    config: RetryConfig,
    retryable_errors: List[str]
) -> T:
    """Execute operation with retry logic"""
    pass

def format_error(error: Exception) -> ErrorResponse:
    """Format exception as ErrorResponse"""
    pass
```

**Responsibilities:**
- Implement exponential backoff retry logic
- Determine if errors are retryable
- Format errors for API responses
- Log errors with context to CloudWatch

**Implementation Details:**
- Retryable errors: 429 (rate limit), 503 (service unavailable), ProvisionedThroughputExceededException
- Non-retryable errors: 400 (bad request), 403 (forbidden), validation errors
- Exponential backoff: delay = min(baseDelay * 2^attempt, maxDelay)
- Add jitter to prevent thundering herd: delay * (0.5 + random(0, 0.5))

### Utilities

**Purpose:** Helper functions for common operations

**Interface:**
```python
from datetime import datetime, date
from typing import Tuple, List, Dict

def validate_date_format(date_str: str) -> bool:
    """Validate date matches YYYY-MM-DD format"""
    pass

def validate_date_range(start_date: str, end_date: str) -> bool:
    """Validate start date is before or equal to end date"""
    pass

def validate_granularity(granularity: str) -> bool:
    """Validate granularity is DAILY, MONTHLY, or HOURLY"""
    pass

def format_date_for_api(dt: date) -> str:
    """Format date as YYYY-MM-DD"""
    pass

def calculate_default_date_range() -> Tuple[str, str]:
    """Calculate 12 months ago to today"""
    pass

def calculate_ttl(days: int) -> int:
    """Calculate Unix timestamp for TTL"""
    pass

def normalize_service_name(service: str) -> str:
    """Normalize service name for sort key"""
    pass

def calculate_cost_summary(records: List[CostRecord]) -> Dict[str, Any]:
    """Calculate total cost, service count, record count"""
    pass
```

## Data Models

### Cost Explorer API Response

```python
# Example response structure from boto3 Cost Explorer client
{
    'ResultsByTime': [
        {
            'TimePeriod': {
                'Start': '2025-01-01',
                'End': '2025-01-31'
            },
            'Groups': [
                {
                    'Keys': ['Amazon Elastic Compute Cloud - Compute'],
                    'Metrics': {
                        'BlendedCost': {
                            'Amount': '123.45',
                            'Unit': 'USD'
                        },
                        'UnblendedCost': {
                            'Amount': '123.45',
                            'Unit': 'USD'
                        }
                    }
                }
            ]
        }
    ],
    'NextPageToken': 'optional-token-for-pagination'
}
```

### DynamoDB Table Schema

**Table Name:** `costguard-cost-data`

**Primary Key:**
- Partition Key: `pk` (String) - Format: `COST#YYYY-MM`
- Sort Key: `sk` (String) - Format: `SERVICE#service-name`

**Attributes:**
- `date` (String) - Date in YYYY-MM-DD format
- `service` (String) - Full AWS service name
- `blendedCost` (Number) - Blended cost amount
- `unblendedCost` (Number) - Unblended cost amount
- `currency` (String) - Currency code (default: "USD")
- `unit` (String) - Unit of measurement (default: "USD")
- `timestamp` (String) - ISO 8601 timestamp of when data was fetched
- `ttl` (Number, optional) - Unix timestamp for automatic cleanup

**Access Patterns:**
1. Query all costs for a specific month: Query by `pk = "COST#YYYY-MM"`
2. Query specific service for a month: Query by `pk = "COST#YYYY-MM"` and `sk = "SERVICE#service-name"`
3. Query date range: Multiple queries across partition keys
4. Query specific service across months: Requires scan or GSI (not implemented in Phase 1)

**Indexes:**
- No GSI in Phase 1 (to stay within Free Tier limits)
- Future: Add GSI with `service` as partition key and `date` as sort key

### API Request/Response Models

**POST /api/cost-data/fetch Request:**
```python
{
    "startDate": "2025-01-01",    # Optional, defaults to 12 months ago
    "endDate": "2025-12-31",      # Optional, defaults to today
    "granularity": "MONTHLY"      # Optional: DAILY | MONTHLY | HOURLY, defaults to MONTHLY
}
```

**POST /api/cost-data/fetch Response:**
```python
{
    "success": True,
    "message": "Cost data fetched and stored successfully",
    "data": {
        "recordsProcessed": 120,
        "dateRange": {
            "start": "2025-01-01",
            "end": "2025-12-31"
        },
        "totalCost": 1234.56,
        "services": ["EC2", "S3", "Lambda", "DynamoDB"]
    }
}
```

**GET /api/cost-data Request:**
```python
# Query parameters:
# - startDate: Optional[str]  # YYYY-MM-DD
# - endDate: Optional[str]    # YYYY-MM-DD
# - service: Optional[str]    # Service name filter
# - limit: Optional[int]      # Max records, default 100
```

**GET /api/cost-data Response:**
```python
{
    "success": True,
    "data": [
        {
            "date": "2025-01-01",
            "service": "Amazon Elastic Compute Cloud - Compute",
            "blendedCost": 123.45,
            "unblendedCost": 123.45,
            "currency": "USD"
        }
    ],
    "count": 12
}
```

**Error Response:**
```python
{
    "success": False,
    "error": {
        "code": "ERROR_CODE",
        "message": "Error message",
        "details": {}  # Optional
    }
}
```


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property Reflection

After analyzing all acceptance criteria, I identified several areas where properties can be consolidated to avoid redundancy:

1. **Input Validation Properties**: Criteria 2.1, 2.2, 2.3, 2.4, and 2.5 all relate to input validation. These can be consolidated into comprehensive validation properties that cover all input types.

2. **Retry Logic Properties**: Criteria 4.1, 4.2, 4.5, 4.6, 5.1, and 5.3 all relate to retry behavior. These can be consolidated into general retry properties that apply to both Cost Explorer and DynamoDB operations.

3. **Response Structure Properties**: Criteria 8.1, 8.2, 8.3, 8.4, 8.5, and 8.6 all relate to response structure. These can be consolidated into properties that verify response completeness.

4. **Logging Properties**: Criteria 9.1-9.6 all relate to logging. These can be consolidated into properties that verify logging occurs at key points.

5. **DynamoDB Format Properties**: Criteria 3.2, 3.3, and 3.4 all relate to DynamoDB record format. These can be consolidated into a single property about record structure.

### Properties

Property 1: Date validation rejects invalid formats
*For any* string input, if it does not match the YYYY-MM-DD format, then the validation function should return false and the Lambda should return a 400 error
**Validates: Requirements 2.1, 2.2**

Property 2: Date range validation rejects invalid ranges
*For any* pair of valid dates, if the start date is after the end date, then the validation function should return false and the Lambda should return a 400 error
**Validates: Requirements 2.3**

Property 3: Granularity validation accepts only valid values
*For any* string input, the validation function should return true only if the input is exactly "DAILY", "MONTHLY", or "HOURLY", and return a 400 error otherwise
**Validates: Requirements 2.4, 2.5**

Property 4: Cost Explorer pagination fetches all pages
*For any* Cost Explorer API response with pagination, the fetch function should continue calling the API with NextPageToken until no token is returned, collecting all results
**Validates: Requirements 1.5**

Property 5: Cost data transformation produces valid DynamoDB records
*For any* cost record from Cost Explorer API, the transformation function should produce a DynamoDB record with partition key format "COST#YYYY-MM", sort key format "SERVICE#service-name", and all required fields (date, service, blendedCost, unblendedCost, currency, unit, timestamp)
**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

Property 6: Batch write operations handle partial failures
*For any* batch write operation that returns unprocessed items, the function should retry those specific items until they succeed or maximum retries are reached
**Validates: Requirements 3.6**

Property 7: Retryable errors trigger exponential backoff
*For any* API call that returns a retryable error (429, 503, or ProvisionedThroughputExceededException), the function should retry with exponential backoff, attempting a maximum of 3 retries with increasing delays
**Validates: Requirements 4.1, 4.2, 4.5, 5.1**

Property 8: Non-retryable errors return immediately
*For any* API call that returns a non-retryable error (400, 403), the function should not retry and should return an error response with the appropriate status code
**Validates: Requirements 4.3, 4.4, 5.2**

Property 9: Retry exhaustion returns detailed error
*For any* operation that fails after maximum retries, the function should return an error response containing success: false, error code, error message, and details about the failure
**Validates: Requirements 4.6, 5.3**

Property 10: Query operations support all filter combinations
*For any* combination of query filters (startDate, endDate, service, limit), the query function should correctly apply all provided filters and return only matching records
**Validates: Requirements 7.1, 7.2, 7.3, 7.4**

Property 11: Query operations use efficient DynamoDB access patterns
*For any* query operation, the function should use DynamoDB Query (not Scan) with partition key and sort key to efficiently retrieve data
**Validates: Requirements 7.6**

Property 12: Successful fetch responses contain complete summaries
*For any* successful fetch operation, the response should contain success: true, a message, and a data object with recordsProcessed, dateRange (start and end), totalCost, and services array
**Validates: Requirements 8.1, 8.2**

Property 13: Successful query responses contain cost records
*For any* successful query operation, the response should contain success: true, a data array with cost records, and a count field
**Validates: Requirements 8.3**

Property 14: Error responses contain structured error information
*For any* failed operation, the response should contain success: false and an error object with code, message, and optional details fields
**Validates: Requirements 8.4, 8.5**

Property 15: Cost records in responses contain all required fields
*For any* cost record returned in a query response, it should contain date, service, blendedCost, unblendedCost, and currency fields
**Validates: Requirements 8.6**

Property 16: All operations log key execution points
*For any* Lambda execution, logs should be written at key points: function start (with event), API calls (with parameters), errors (with stack trace), database operations (with record count), retries (with attempt number), and function completion (with summary)
**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**

Property 17: Duplicate records trigger upsert behavior
*For any* cost record being stored, if a record with the same partition key and sort key already exists, the function should update the existing record (including updating the timestamp) rather than creating a duplicate
**Validates: Requirements 11.1, 11.2, 11.3**

Property 18: Conditional writes prevent race conditions
*For any* write operation to DynamoDB, the function should use conditional write parameters to ensure data consistency even under concurrent access
**Validates: Requirements 11.4**

Property 19: Cost summaries calculate correct totals
*For any* set of cost records, the summary calculation should produce the correct total cost (sum of all blendedCost values), unique service count, and total record count
**Validates: Requirements 12.1, 12.2, 12.3, 12.5**

Property 20: API Gateway enforces authentication
*For any* request to any endpoint, if no valid API key is provided, the API Gateway should return a 401 error and not invoke the Lambda function
**Validates: Requirements 6.3, 6.4**

Property 21: API Gateway returns appropriate status codes
*For any* request, the API Gateway should return 200 for success, 400 for bad requests, 401 for authentication failures, 403 for authorization failures, and 500 for server errors
**Validates: Requirements 6.5, 6.6**

Property 22: Cost Explorer API calls include correct parameters
*For any* fetch operation, the Cost Explorer API call should include the correct TimePeriod (start and end dates), Granularity, Metrics (BlendedCost and UnblendedCost), and GroupBy (SERVICE dimension)
**Validates: Requirements 1.1, 1.3, 1.4**

Property 23: Batch operations split oversized batches
*For any* batch write operation where the total size exceeds DynamoDB limits, the function should automatically split the batch into smaller chunks of 25 items or less
**Validates: Requirements 3.5, 5.4**

## Error Handling

### Error Categories

**1. Client Errors (4xx)**
- Invalid input parameters (dates, granularity)
- Invalid date ranges (start after end)
- Missing required parameters
- Invalid API key

**Response:** Return 400 Bad Request with descriptive error message

**2. Authentication Errors (401)**
- Missing API key
- Invalid API key

**Response:** Return 401 Unauthorized

**3. Authorization Errors (403)**
- Cost Explorer API access denied
- DynamoDB access denied

**Response:** Return 403 Forbidden with error details

**4. Rate Limiting Errors (429)**
- Cost Explorer API rate limit exceeded

**Response:** Retry with exponential backoff (max 3 attempts), return 429 if all retries fail

**5. Server Errors (5xx)**
- Cost Explorer API unavailable (503)
- DynamoDB throttling
- Lambda timeout
- Unexpected errors

**Response:** Retry with exponential backoff for retryable errors, return 500 with error details

### Retry Strategy

**Retryable Errors:**
- HTTP 429 (Rate Limit)
- HTTP 503 (Service Unavailable)
- ProvisionedThroughputExceededException (DynamoDB)
- ThrottlingException (DynamoDB)

**Non-Retryable Errors:**
- HTTP 400 (Bad Request)
- HTTP 401 (Unauthorized)
- HTTP 403 (Forbidden)
- ValidationException (DynamoDB)

**Retry Configuration:**
- Maximum retries: 3
- Base delay: 1000ms
- Max delay: 8000ms
- Backoff formula: `delay = min(baseDelay * 2^attempt, maxDelay)`
- Jitter: `delay * (0.5 + random(0, 0.5))`

**Example Retry Sequence:**
- Attempt 1: Immediate
- Attempt 2: ~1000ms delay (with jitter: 500-1500ms)
- Attempt 3: ~2000ms delay (with jitter: 1000-3000ms)
- Attempt 4: ~4000ms delay (with jitter: 2000-6000ms)
- Fail: Return error after attempt 4

### Error Logging

All errors must be logged to CloudWatch with:
- Error type and code
- Error message
- Stack trace (for unexpected errors)
- Request context (event parameters, user info)
- Timestamp
- Retry attempt number (if applicable)

### Error Response Format

```python
{
    "success": False,
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable error message",
        "details": {
            # Additional context (optional)
            "requestId": "...",
            "timestamp": "...",
            "retryCount": 3
        }
    }
}
```

**Error Codes:**
- `INVALID_DATE_FORMAT`: Date parameter doesn't match YYYY-MM-DD
- `INVALID_DATE_RANGE`: Start date is after end date
- `INVALID_GRANULARITY`: Granularity is not DAILY, MONTHLY, or HOURLY
- `COST_EXPLORER_ERROR`: Error calling Cost Explorer API
- `COST_EXPLORER_RATE_LIMIT`: Rate limit exceeded on Cost Explorer API
- `COST_EXPLORER_ACCESS_DENIED`: No permission to access Cost Explorer
- `DYNAMODB_ERROR`: Error writing to or reading from DynamoDB
- `DYNAMODB_THROTTLING`: DynamoDB throttling error
- `VALIDATION_ERROR`: Input validation failed
- `INTERNAL_ERROR`: Unexpected server error

## Testing Strategy

### Dual Testing Approach

This system will use both unit tests and property-based tests to ensure comprehensive coverage:

**Unit Tests:** Verify specific examples, edge cases, and error conditions
- Test default behaviors (12-month range, MONTHLY granularity, 100 record limit)
- Test specific error scenarios (403, 400 responses)
- Test integration points between components
- Test edge cases (empty results, single record, maximum batch size)

**Property-Based Tests:** Verify universal properties across all inputs
- Test input validation with randomly generated strings and dates
- Test pagination with various page sizes and counts
- Test data transformation with random cost data
- Test retry logic with random failure patterns
- Test query filtering with random filter combinations
- Test summary calculations with random cost datasets

### Property-Based Testing Configuration

**Library:** Hypothesis (for Python)

**Configuration:**
- Minimum iterations per test: 100
- Seed: Random (for reproducibility, log seed on failure)
- Shrinking: Enabled (to find minimal failing case)

**Test Tagging:**
Each property test must include a comment referencing the design property:
```python
# Feature: cost-data-pipeline, Property 1: Date validation rejects invalid formats
@given(st.text())
@settings(max_examples=100)
def test_validates_date_format_for_all_inputs(input_str):
    # Test implementation
    pass
```

### Unit Test Coverage

**Input Validation:**
- Valid date formats (2025-01-01, 2025-12-31)
- Invalid date formats (01-01-2025, 2025/01/01, invalid)
- Valid date ranges (start before end)
- Invalid date ranges (start after end)
- Valid granularity values (DAILY, MONTHLY, HOURLY)
- Invalid granularity values (daily, Weekly, invalid)
- Default behaviors (no dates = 12 months, no granularity = MONTHLY)

**Cost Explorer Integration:**
- Successful API call with single page
- Successful API call with multiple pages
- API call with rate limit error (429)
- API call with service unavailable error (503)
- API call with access denied error (403)
- API call with invalid parameter error (400)

**DynamoDB Integration:**
- Successful batch write (< 25 items)
- Successful batch write (> 25 items, requires multiple batches)
- Batch write with partial failure
- Batch write with throttling error
- Successful query with filters
- Query with no results
- Upsert behavior (duplicate records)

**Error Handling:**
- Retry logic with exponential backoff
- Maximum retry limit (3 attempts)
- Non-retryable errors return immediately
- Error response format

**Response Formatting:**
- Successful fetch response structure
- Successful query response structure
- Error response structure
- Cost summary calculations

### Integration Tests

**End-to-End Fetch Flow:**
1. POST to /api/cost-data/fetch with valid parameters
2. Verify Lambda is invoked
3. Verify Cost Explorer API is called
4. Verify data is stored in DynamoDB
5. Verify response contains correct summary

**End-to-End Query Flow:**
1. Store test data in DynamoDB
2. GET from /api/cost-data with filters
3. Verify Lambda is invoked
4. Verify DynamoDB is queried
5. Verify response contains filtered data

**Authentication:**
1. Request without API key returns 401
2. Request with invalid API key returns 401
3. Request with valid API key succeeds

### Test Data

**Mock Cost Explorer Responses:**
- Single page with 10 services
- Multiple pages (3 pages, 30 services total)
- Empty results
- Large dataset (100+ services)

**Mock DynamoDB Data:**
- 12 months of cost data
- Multiple services per month
- Various cost amounts ($0.01 to $10,000)

**Test Fixtures:**
- Valid date ranges (last 30 days, last 12 months, custom range)
- Invalid inputs (malformed dates, invalid granularity)
- Error scenarios (rate limits, throttling, access denied)

### Testing Tools

- **Unit Testing:** pytest
- **Property-Based Testing:** Hypothesis
- **Mocking:** boto3 mocking (moto library or unittest.mock)
- **Integration Testing:** Local DynamoDB (DynamoDB Local) or mocked AWS services
- **Coverage:** pytest-cov (target: 80%+ coverage)

### Continuous Testing

- Run unit tests on every commit
- Run property-based tests on every commit
- Run integration tests before deployment
- Monitor test execution time (target: < 30 seconds for unit tests)
- Track test coverage and fail if below threshold
