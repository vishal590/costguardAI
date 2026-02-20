# Design Document: Near-Real-Time Cost Estimation

## Overview

Phase 1.5 extends the Cost Data Pipeline by adding near-real-time cost estimation capabilities. While Phase 1 provides historical cost data from AWS Cost Explorer (with 24-hour delay), Phase 1.5 estimates current costs by collecting CloudWatch metrics and applying pricing calculations.

The system collects metrics from CloudWatch for supported AWS services (EC2, Lambda, DynamoDB, S3, RDS), applies current pricing data, and calculates estimated costs. This enables users to see their AWS spending as it happens, providing immediate visibility into cost trends.

**Key Design Principles:**
- Reuse Phase 1 infrastructure (DynamoDB, API Gateway, Lambda, IAM)
- Minimize CloudWatch API calls to stay within Free Tier
- Cache pricing data to reduce Pricing API calls
- Provide accurate estimates with confidence indicators
- Maintain consistency with Phase 1 patterns

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway (Phase 1)                    │
│  /api/cost-data/fetch (Phase 1)                             │
│  /api/cost-data (Phase 1)                                   │
│  /api/cost-estimation/current (NEW)                         │
│  /api/cost-estimation/service/{service} (NEW)               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Function (Extended)                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Phase 1 Handlers:                                    │  │
│  │  - handle_fetch() - Cost Explorer integration        │  │
│  │  - handle_query() - Historical data queries          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Phase 1.5 Handlers (NEW):                           │  │
│  │  - handle_estimation_current() - All services        │  │
│  │  - handle_estimation_service() - Single service      │  │
│  └──────────────────────────────────────────────────────┘  │
└────┬────────────────────┬────────────────────┬─────────────┘
     │                    │                    │
     ▼                    ▼                    ▼
┌──────────┐      ┌──────────────┐    ┌─────────────────┐
│CloudWatch│      │   DynamoDB   │    │  Pricing API    │
│ Metrics  │      │  (Phase 1)   │    │  (AWS Price     │
│   API    │      │              │    │   List API)     │
└──────────┘      └──────────────┘    └─────────────────┘
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Lambda Handler                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Routing Layer              
                         │
│  │  - Route to Phase 1 handlers (fetch, query)           │ │
│  │  - Route to Phase 1.5 handlers (estimation)           │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  CloudWatch Metrics Collector                          │ │
│  │  - collect_ec2_metrics()                               │ │
│  │  - collect_lambda_metrics()                            │ │
│  │  - collect_dynamodb_metrics()                          │ │
│  │  - collect_s3_metrics()                                │ │
│  │  - collect_rds_metrics()                               │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Cost Estimator                                        │ │
│  │  - estimate_ec2_cost()                                 │ │
│  │  - estimate_lambda_cost()                              │ │
│  │  - estimate_dynamodb_cost()                            │ │
│  │  - estimate_s3_cost()                                  │ │
│  │  - estimate_rds_cost()                                 │ │
│  │  - calculate_total_estimate()                          │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Pricing Manager                                       │ │
│  │  - get_pricing_data()                                  │ │
│  │  - refresh_pricing_data()                              │ │
│  │  - cache_pricing_data()                                │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. CloudWatch Metrics Collector

**Purpose:** Collect usage metrics from CloudWatch for cost estimation.

**Interface:**
```python
class CloudWatchMetricsCollector:
    def collect_metrics(
        self,
        services: List[str],
        start_time: datetime,
        end_time: datetime,
        period: int = 300  # 5 minutes
    ) -> Dict[str, List[MetricDataPoint]]
    
    def collect_ec2_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[EC2Metrics]
    
    def collect_lambda_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[LambdaMetrics]
    
    def collect_dynamodb_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[DynamoDBMetrics]
    
    def collect_s3_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[S3Metrics]
    
    def collect_rds_metrics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[RDSMetrics]
```

**Key Responsibilities:**
- Fetch metrics from CloudWatch API
- Batch metric requests to minimize API calls
- Handle pagination for large metric datasets
- Validate metric data
- Transform CloudWatch responses to internal format

### 2. Cost Estimator

**Purpose:** Calculate cost estimates based on metrics and pricing data.

**Interface:**
```python
class CostEstimator:
    def estimate_cost(
        self,
        service: str,
        metrics: List[MetricDataPoint],
        pricing_data: PricingData
    ) -> CostEstimate
    
    def estimate_ec2_cost(
        self,
        metrics: List[EC2Metrics],
        pricing: EC2Pricing
    ) -> Decimal
    
    def estimate_lambda_cost(
        self,
        metrics: List[LambdaMetrics],
        pricing: LambdaPricing
    ) -> Decimal
    
    def estimate_dynamodb_cost(
        self,
        metrics: List[DynamoDBMetrics],
        pricing: DynamoDBPricing
    ) -> Decimal
    
    def estimate_s3_cost(
        self,
        metrics: List[S3Metrics],
        pricing: S3Pricing
    ) -> Decimal
    
    def estimate_rds_cost(
        self,
        metrics: List[RDSMetrics],
        pricing: RDSPricing
    ) -> Decimal
    
    def calculate_confidence_interval(
        self,
        estimate: Decimal,
        metrics_count: int
    ) -> Tuple[Decimal, Decimal]
```

**Key Responsibilities:**
- Apply pricing formulas to metrics
- Calculate costs per service
- Aggregate costs across services
- Calculate confidence intervals
- Handle edge cases (zero usage, missing data)

### 3. Pricing Manager

**Purpose:** Manage AWS pricing data with caching and refresh logic.

**Interface:**
```python
class PricingManager:
    def get_pricing_data(
        self,
        service: str,
        region: str
    ) -> PricingData
    
    def refresh_pricing_data(
        self,
        service: str,
        region: str
    ) -> PricingData
    
    def is_pricing_stale(
        self,
        pricing: PricingData,
        max_age_hours: int = 24
    ) -> bool
    
    def fetch_from_pricing_api(
        self,
        service: str,
        region: str
    ) -> PricingData
    
    def cache_pricing_data(
        self,
        service: str,
        region: str,
        pricing: PricingData
    ) -> None
```

**Key Responsibilities:**
- Fetch pricing from AWS Pricing API
- Cache pricing in DynamoDB
- Check pricing freshness
- Refresh stale pricing
- Handle pricing API errors

## Data Models

### MetricDataPoint
```python
@dataclass
class MetricDataPoint:
    timestamp: datetime
    value: Decimal
    unit: str
    metric_name: str
```

### EC2Metrics
```python
@dataclass
class EC2Metrics:
    instance_id: str
    instance_type: str
    cpu_utilization: Decimal
    network_in: Decimal
    network_out: Decimal
    disk_read_bytes: Decimal
    running_hours: Decimal
```

### LambdaMetrics
```python
@dataclass
class LambdaMetrics:
    function_name: str
    invocations: int
    duration_ms: Decimal
    memory_mb: int
    errors: int
```

### DynamoDBMetrics
```python
@dataclass
class DynamoDBMetrics:
    table_name: str
    consumed_read_capacity: Decimal
    consumed_write_capacity: Decimal
```

### S3Metrics
```python
@dataclass
class S3Metrics:
    bucket_name: str
    number_of_objects: int
    bucket_size_bytes: Decimal
    get_requests: int
    put_requests: int
```

### RDSMetrics
```python
@dataclass
class RDSMetrics:
    instance_id: str
    instance_type: str
    database_connections: int
    read_iops: Decimal
    write_iops: Decimal
    storage_gb: Decimal
    running_hours: Decimal
```

### PricingData
```python
@dataclass
class PricingData:
    service: str
    region: str
    prices: Dict[str, Decimal]
    currency: str
    last_updated: datetime
    ttl: int
```

### CostEstimate
```python
@dataclass
class CostEstimate:
    service: str
    estimated_cost: Decimal
    currency: str
    confidence_lower: Decimal
    confidence_upper: Decimal
    timestamp: datetime
    period_start: datetime
    period_end: datetime
    metrics_count: int
```

### EstimationResponse
```python
@dataclass
class EstimationResponse:
    success: bool
    estimates: List[CostEstimate]
    total_cost: Decimal
    currency: str
    timestamp: datetime
    period: str
```

## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Metric Collection Completeness
*For any* list of supported services and time range, collecting metrics should return data for all services that have resources running during that time range.

**Validates: Requirements 1.1, 1.7**

### Property 2: Non-Negative Cost Estimates
*For any* valid metrics and pricing data, estimated costs must be non-negative values.

**Validates: Requirements 2.1-2.5, 8.1**

### Property 3: Pricing Data Freshness
*For any* pricing data older than 24 hours, the system should refresh it before using it for estimation.

**Validates: Requirements 3.2, 3.3**

### Property 4: API Response Structure
*For any* successful estimation request, the response must include service name, estimated cost, currency, and timestamp.

**Validates: Requirements 4.7**

### Property 5: Authentication Enforcement
*For any* request without valid authentication, the API must return 401 Unauthorized.

**Validates: Requirements 4.8**

### Property 6: Phase 1 Compatibility
*For any* Phase 1 endpoint request, the system must continue to function identically to Phase 1 behavior.

**Validates: Requirements 5.4**

### Property 7: Retry Logic for Rate Limiting
*For any* CloudWatch API call that returns 429 rate limiting, the system must retry with exponential backoff.

**Validates: Requirements 6.1**

### Property 8: Error Isolation
*For any* service where metric collection fails, the system must continue collecting metrics for other services.

**Validates: Requirements 6.4**

### Property 9: Response Time Bounds
*For any* single service estimation request, the response time must be less than 2 seconds.

**Validates: Requirements 7.4**

### Property 10: Metric Validation
*For any* collected metric, the value must be non-negative.

**Validates: Requirements 8.1**

### Property 11: Pricing Validation
*For any* fetched pricing data, all prices must be positive numbers.

**Validates: Requirements 8.2**

### Property 12: Estimation Bounds Check
*For any* calculated estimate, the result must be within reasonable bounds (not infinity, not NaN).

**Validates: Requirements 8.3**

### Property 13: Batch Metric Collection
*For any* metric collection operation, the system must batch requests to minimize API calls.

**Validates: Requirements 7.1, 7.2**

### Property 14: Pricing Cache Hit
*For any* pricing request where cached data exists and is fresh, the system must use cached data instead of calling Pricing API.

**Validates: Requirements 7.3**

### Property 15: Confidence Interval Validity
*For any* cost estimate with confidence interval, the lower bound must be less than or equal to the estimate, and the estimate must be less than or equal to the upper bound.

**Validates: Requirements 2.8**

## Error Handling

### Error Categories

1. **CloudWatch API Errors**
   - Rate limiting (429) → Retry with exponential backoff
   - Service unavailable (503) → Retry up to 3 times
   - Invalid parameters (400) → Return error to user
   - Access denied (403) → Log error, return 500

2. **Pricing API Errors**
   - Service unavailable → Use cached pricing if available
   - Invalid service/region → Return error to user
   - Rate limiting → Retry with backoff

3. **Validation Errors**
   - Invalid service name → Return 400 with error message
   - Invalid time range → Return 400 with error message
   - Negative metric values → Log warning, skip data point

4. **Calculation Errors**
   - Division by zero → Handle gracefully, return zero cost
   - Overflow → Log error, return error response
   - Missing pricing data → Return error indicating unavailable pricing

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "service": "service_name",
      "operation": "operation_name"
    }
  }
}
```

### Error Codes

- `CLOUDWATCH_ERROR`: Error calling CloudWatch API
- `PRICING_ERROR`: Error fetching pricing data
- `VALIDATION_ERROR`: Input validation failed
- `CALCULATION_ERROR`: Error calculating estimate
- `INTERNAL_ERROR`: Unexpected server error
- `AUTHENTICATION_ERROR`: Authentication failed

## Testing Strategy

### Dual Testing Approach

The system will use both unit tests and property-based tests:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs using Hypothesis
- Both are complementary and necessary for comprehensive coverage

### Unit Testing

Unit tests will focus on:
- Specific metric collection scenarios
- Known pricing calculations
- Error handling paths
- Integration points with Phase 1
- Edge cases (zero usage, missing data)

### Property-Based Testing

Property tests will validate:
- All 15 correctness properties listed above
- Run minimum 100 iterations per property
- Use Hypothesis for Python
- Tag each test with feature name and property number

**Test Tag Format:**
```python
# Feature: near-realtime-cost-estimation, Property 1: Metric Collection Completeness
```

### Test Coverage Goals

- Minimum 80% code coverage
- All correctness properties tested
- All error paths tested
- Integration with Phase 1 tested

### Testing Tools

- **pytest**: Test framework
- **Hypothesis**: Property-based testing
- **moto**: AWS service mocking
- **pytest-cov**: Coverage reporting

## Deployment Considerations

### Infrastructure Changes

**No new infrastructure needed:**
- Reuse Phase 1 DynamoDB table
- Reuse Phase 1 API Gateway
- Reuse Phase 1 Lambda function (extend code)
- Add CloudWatch and Pricing API permissions to IAM role

### IAM Permissions

**Additional permissions needed:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "pricing:GetProducts"
      ],
      "Resource": "*"
    }
  ]
}
```

### Environment Variables

**New environment variables:**
- `PRICING_CACHE_TTL_HOURS`: Pricing cache TTL (default: 24)
- `METRICS_COLLECTION_PERIOD`: CloudWatch metrics period in seconds (default: 300)
- `ESTIMATION_CONFIDENCE_LEVEL`: Confidence level for intervals (default: 0.95)

### Free Tier Compliance

**CloudWatch API:**
- 1 million requests per month free
- Estimated usage: ~50,000 requests/month (well within limit)

**Pricing API:**
- No free tier, but very low cost ($0.0001 per request)
- Estimated usage: ~100 requests/month with caching
- Estimated cost: $0.01/month

**DynamoDB:**
- Reuses Phase 1 table (on-demand billing)
- Additional storage: ~10 MB for pricing cache
- Well within 25 GB free tier

**Lambda:**
- Reuses Phase 1 function
- Additional invocations: ~1,000/month
- Well within 1 million free tier

## Integration with Phase 1

### Code Organization

```
src/
├── lambda_handler.py          # Extended with Phase 1.5 routes
├── services/
│   ├── cost_explorer.py       # Phase 1 (unchanged)
│   ├── dynamodb.py            # Phase 1 (unchanged)
│   ├── cloudwatch_collector.py # Phase 1.5 (NEW)
│   ├── cost_estimator.py      # Phase 1.5 (NEW)
│   └── pricing_manager.py     # Phase 1.5 (NEW)
└── utils/
    ├── types.py               # Extended with Phase 1.5 types
    ├── validation.py          # Extended with Phase 1.5 validation
    ├── date_utils.py          # Phase 1 (unchanged)
    ├── helpers.py             # Phase 1 (unchanged)
    └── error_handler.py       # Phase 1 (unchanged)
```

### Routing Logic

```python
def handler(event, context):
    path = event.get('path', '')
    method = event.get('httpMethod', '')
    
    # Phase 1 routes
    if method == 'POST' and path.endswith('/cost-data/fetch'):
        return handle_fetch(event)
    elif method == 'GET' and path.endswith('/cost-data'):
        return handle_query(event)
    
    # Phase 1.5 routes (NEW)
    elif method == 'GET' and path.endswith('/cost-estimation/current'):
        return handle_estimation_current(event)
    elif method == 'GET' and '/cost-estimation/service/' in path:
        return handle_estimation_service(event)
    
    else:
        return create_error_response(400, 'INVALID_ENDPOINT', 'Endpoint not found')
```

### Backward Compatibility

- All Phase 1 endpoints continue to work unchanged
- Phase 1 tests continue to pass
- No breaking changes to Phase 1 functionality
- Phase 1.5 is purely additive

## Performance Optimization

### Caching Strategy

1. **Pricing Data Cache**
   - Store in DynamoDB with 24-hour TTL
   - Check cache before calling Pricing API
   - Refresh asynchronously when stale

2. **Metric Batching**
   - Collect metrics for multiple services in single API call when possible
   - Use CloudWatch GetMetricStatistics with appropriate periods
   - Minimize number of API calls

3. **Response Caching**
   - Consider caching estimation responses for 5 minutes
   - Reduce redundant calculations for frequent queries

### Scalability Considerations

- System designed for single AWS account monitoring
- Can scale to multiple accounts with minor modifications
- CloudWatch API has rate limits (handle with backoff)
- DynamoDB on-demand billing scales automatically

## Monitoring and Observability

### CloudWatch Logs

Log the following events:
- Metric collection operations (service, time range, result count)
- Cost estimation calculations (service, estimated cost)
- Pricing data updates (service, region, timestamp)
- Errors (all error types with details)

### CloudWatch Metrics

Emit the following custom metrics:
- `EstimationRequestCount`: Number of estimation requests
- `EstimationLatency`: Response time for estimation requests
- `MetricCollectionErrors`: Number of metric collection failures
- `PricingCacheHitRate`: Percentage of pricing requests served from cache

### Alarms

Consider setting alarms for:
- High error rate (> 5%)
- High latency (> 5 seconds)
- CloudWatch API throttling
- Pricing API errors

## Summary

Phase 1.5 adds near-real-time cost estimation by collecting CloudWatch metrics and applying pricing calculations. The design reuses Phase 1 infrastructure, maintains backward compatibility, and operates within AWS Free Tier limits. The system provides accurate cost estimates with confidence intervals, enabling users to monitor their AWS spending in near-real-time.

**Key Design Decisions:**
1. Reuse Phase 1 infrastructure (minimize new resources)
2. Cache pricing data (reduce API calls and costs)
3. Batch metric collection (stay within Free Tier)
4. Provide confidence intervals (indicate estimation accuracy)
5. Maintain Phase 1 compatibility (no breaking changes)
