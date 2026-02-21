# Design Document: AI Cost Forecasting

## Overview

Phase 2 extends CostGuard with AI-powered cost forecasting using Amazon Bedrock. The system retrieves historical cost data from Phase 1, sends it to Bedrock Nova models for time series prediction, and returns 30-day cost forecasts with confidence intervals. Forecasts are cached in DynamoDB to minimize Bedrock API costs while maintaining fast response times.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway                              │
│  Phase 1: /api/cost-data/*                                  │
│  Phase 1.5: /api/cost-estimation/*                          │
│  Phase 2: /api/cost-forecast                                │
│           /api/cost-forecast/service/{service}              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Function                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Existing: Cost Explorer, CloudWatch, Pricing       │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  NEW: Forecast Engine                                │  │
│  │  - Historical data retrieval                         │  │
│  │  - Bedrock integration                               │  │
│  │  - Forecast generation                               │  │
│  │  - Cache management                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└────┬────────────────────┬────────────────────┬─────────────┘
     │                    │                    │
     ▼                    ▼                    ▼
┌──────────┐      ┌──────────────┐    ┌─────────────────┐
│ DynamoDB │      │   Bedrock    │    │   CloudWatch    │
│          │      │  Nova Models │    │     Logs        │
│ Tables:  │      │              │    │                 │
│ - cost   │      │ - Nova Lite  │    │ - API calls     │
│ - cache  │      │ - Nova Micro │    │ - Latency       │
└──────────┘      └──────────────┘    │ - Cache hits    │
                                       └─────────────────┘
```

### Data Flow

1. **Request**: Client calls `/api/cost-forecast` with API key
2. **Cache Check**: Lambda checks DynamoDB forecast cache
3. **Cache Hit**: Return cached forecast (< 500ms)
4. **Cache Miss**: 
   - Retrieve historical data from DynamoDB (Phase 1 data)
   - Validate and preprocess data (interpolation, aggregation)
   - Format data for Bedrock (JSON with timestamps/costs)
   - Call Bedrock Nova model with forecasting prompt
   - Parse Bedrock response (predictions + confidence intervals)
   - Store forecast in cache (24-hour TTL)
   - Return forecast to client
5. **Monitoring**: Log metrics to CloudWatch

## Components and Interfaces

### 1. Forecast Engine (`src/services/forecast_engine.py`)

Main orchestrator for forecast generation.

**Interface:**
```python
class ForecastEngine:
    def __init__(self, bedrock_client, dynamodb_client, cache_manager):
        """Initialize forecast engine with dependencies."""
        
    def generate_forecast(
        self,
        service: Optional[str] = None,
        days: int = 30,
        granularity: str = "daily"
    ) -> ForecastResponse:
        """
        Generate cost forecast for specified parameters.
        
        Args:
            service: Service name (None for total forecast)
            days: Forecast horizon (7, 14, or 30)
            granularity: Time resolution ("daily" or "weekly")
            
        Returns:
            ForecastResponse with predictions and metadata
            
        Raises:
            InsufficientDataError: Less than 30 days of historical data
            BedrockError: Bedrock API failure
            ValidationError: Invalid parameters
        """
        
    def validate_historical_data(self, data: List[CostDataPoint]) -> bool:
        """Validate historical data completeness and quality."""
        
    def preprocess_data(self, data: List[CostDataPoint]) -> ProcessedData:
        """Aggregate, interpolate, and prepare data for Bedrock."""
```

### 2. Bedrock Client (`src/services/bedrock_client.py`)

Handles all Bedrock API interactions.

**Interface:**
```python
class BedrockClient:
    def __init__(self):
        """Initialize Bedrock runtime client."""
        self.client = boto3.client('bedrock-runtime')
        self.model_id = "amazon.nova-lite-v1:0"  # or nova-micro
        
    def invoke_forecast(
        self,
        historical_data: Dict,
        forecast_horizon: int
    ) -> BedrockResponse:
        """
        Invoke Bedrock model for cost forecasting.
        
        Args:
            historical_data: JSON with timestamps and costs
            forecast_horizon: Number of days to forecast
            
        Returns:
            BedrockResponse with predictions and confidence intervals
            
        Raises:
            BedrockAPIError: API call failed
            BedrockRateLimitError: Rate limit exceeded
            BedrockInvalidResponseError: Invalid JSON response
        """
        
    def build_prompt(
        self,
        historical_data: Dict,
        forecast_horizon: int
    ) -> str:
        """Build prompt for time series forecasting."""
        
    def parse_response(self, response: Dict) -> List[ForecastDataPoint]:
        """Parse Bedrock JSON response into forecast data points."""
        
    def retry_with_backoff(self, func, max_retries: int = 3):
        """Retry function with exponential backoff."""
```

### 3. Cache Manager (`src/services/forecast_cache.py`)

Manages forecast caching in DynamoDB.

**Interface:**
```python
class ForecastCacheManager:
    def __init__(self, dynamodb_client, table_name: str):
        """Initialize cache manager."""
        
    def get_cached_forecast(
        self,
        service: Optional[str],
        days: int,
        granularity: str
    ) -> Optional[CachedForecast]:
        """
        Retrieve cached forecast if exists and not expired.
        
        Returns:
            CachedForecast if found and valid, None otherwise
        """
        
    def store_forecast(
        self,
        forecast: ForecastResponse,
        service: Optional[str],
        days: int,
        granularity: str
    ) -> None:
        """Store forecast in cache with 24-hour TTL."""
        
    def invalidate_all(self) -> None:
        """Invalidate all cached forecasts (called when new data fetched)."""
        
    def get_cache_key(
        self,
        service: Optional[str],
        days: int,
        granularity: str
    ) -> str:
        """Generate cache key from parameters."""
        
    def track_cache_hit_rate(self) -> float:
        """Calculate and return cache hit rate."""
```

### 4. Historical Data Retriever (`src/services/historical_data.py`)

Retrieves and preprocesses historical cost data.

**Interface:**
```python
class HistoricalDataRetriever:
    def __init__(self, dynamodb_client):
        """Initialize data retriever."""
        
    def get_historical_data(
        self,
        service: Optional[str] = None,
        days_back: int = 90
    ) -> List[CostDataPoint]:
        """
        Retrieve historical cost data from DynamoDB.
        
        Args:
            service: Service name (None for all services)
            days_back: Number of days of history to retrieve
            
        Returns:
            List of cost data points sorted by date
            
        Raises:
            InsufficientDataError: Less than minimum required data
        """
        
    def aggregate_by_service_and_date(
        self,
        data: List[CostDataPoint]
    ) -> Dict[str, List[CostDataPoint]]:
        """Aggregate costs by service and date."""
        
    def interpolate_gaps(
        self,
        data: List[CostDataPoint]
    ) -> List[CostDataPoint]:
        """Fill missing dates using linear interpolation."""
        
    def validate_completeness(self, data: List[CostDataPoint]) -> bool:
        """Check if data meets minimum requirements."""
```

### 5. Lambda Handler Extension (`src/lambda_handler.py`)

Extends existing handler with forecast endpoints.

**New Routes:**
```python
def handle_forecast_request(event, context):
    """Handle GET /api/cost-forecast"""
    
def handle_forecast_service_request(event, context):
    """Handle GET /api/cost-forecast/service/{service}"""
```

## Data Models

### ForecastDataPoint
```python
@dataclass
class ForecastDataPoint:
    date: str  # ISO 8601 format (YYYY-MM-DD)
    predicted_cost: float  # Predicted cost in USD
    confidence_lower: float  # Lower bound of 95% confidence interval
    confidence_upper: float  # Upper bound of 95% confidence interval
    currency: str = "USD"
```

### ForecastResponse
```python
@dataclass
class ForecastResponse:
    success: bool
    forecast_data: List[ForecastDataPoint]
    metadata: ForecastMetadata
```

### ForecastMetadata
```python
@dataclass
class ForecastMetadata:
    timestamp: str  # ISO 8601 timestamp
    forecast_horizon: int  # Days forecasted
    granularity: str  # "daily" or "weekly"
    model_used: str  # "amazon.nova-lite-v1:0"
    service: Optional[str]  # Service name or None for total
    services_included: Optional[List[str]]  # For total forecasts
    cache_hit: bool  # True if returned from cache
    historical_data_days: int  # Days of historical data used
```

### CachedForecast
```python
@dataclass
class CachedForecast:
    cache_key: str
    forecast_response: ForecastResponse
    created_at: datetime
    ttl: int  # Unix timestamp for expiration
```

### ProcessedData
```python
@dataclass
class ProcessedData:
    timestamps: List[str]  # ISO 8601 dates
    costs: List[float]  # Corresponding costs
    service: Optional[str]  # Service name
    total_days: int  # Number of data points
```

### BedrockRequest
```python
@dataclass
class BedrockRequest:
    historical_data: ProcessedData
    forecast_horizon: int
    confidence_level: float = 0.95
```

### BedrockResponse
```python
@dataclass
class BedrockResponse:
    predictions: List[float]  # Predicted costs
    confidence_lower: List[float]  # Lower bounds
    confidence_upper: List[float]  # Upper bounds
    dates: List[str]  # Forecast dates
    model_id: str
    latency_ms: int
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Historical Data Validation
*For any* historical data set, if it contains fewer than 30 days of data, the system should reject it with an InsufficientDataError.
**Validates: Requirements 1.2**

### Property 2: Data Interpolation Completeness
*For any* historical data with gaps, after interpolation, there should be no missing dates between the start and end dates.
**Validates: Requirements 1.4**

### Property 3: Forecast Length Consistency
*For any* forecast request with horizon H days and daily granularity, the returned forecast should contain exactly H data points.
**Validates: Requirements 3.1**

### Property 4: Confidence Interval Validity
*For any* forecast data point, the confidence_lower should be less than or equal to predicted_cost, and predicted_cost should be less than or equal to confidence_upper.
**Validates: Requirements 3.4**

### Property 5: Non-Negative Cost Predictions
*For any* forecast data point, the predicted_cost, confidence_lower, and confidence_upper should all be non-negative.
**Validates: Requirements 3.1, 3.4**

### Property 6: Weekly Aggregation Consistency
*For any* forecast with daily predictions, aggregating to weekly should produce weekly totals that sum to the same total as the daily predictions.
**Validates: Requirements 3.3**

### Property 7: Service-Specific Data Filtering
*For any* service-specific forecast request, the historical data used should contain only that service's cost data.
**Validates: Requirements 3.5**

### Property 8: Total Forecast Aggregation
*For any* total forecast, the predicted costs should equal the sum of all individual service forecasts for the same period.
**Validates: Requirements 3.6**

### Property 9: Cache Key Uniqueness
*For any* two forecast requests with different parameters (service, days, or granularity), they should generate different cache keys.
**Validates: Requirements 4.5**

### Property 10: Cache TTL Enforcement
*For any* cached forecast, if the current time exceeds the TTL, the cache should return None (cache miss).
**Validates: Requirements 4.3**

### Property 11: Cache Invalidation Completeness
*For any* cache state, after calling invalidate_all(), all subsequent cache lookups should return None (cache miss).
**Validates: Requirements 4.4**

### Property 12: Response Structure Completeness
*For any* forecast response, it should contain all required fields: success, forecast_data, and metadata with timestamp, forecast_horizon, granularity, and model_used.
**Validates: Requirements 6.1, 6.2**

### Property 13: Forecast Data Point Structure
*For any* forecast data point in the response, it should contain date, predicted_cost, confidence_lower, confidence_upper, and currency fields.
**Validates: Requirements 6.3**

### Property 14: Retry Logic for Rate Limiting
*For any* Bedrock API call that returns a rate limit error, the system should retry up to 3 times with exponential backoff before failing.
**Validates: Requirements 2.5, 7.2**

### Property 15: Backward Compatibility
*For any* Phase 1 or Phase 1.5 API endpoint, after Phase 2 deployment, the endpoint should still return the same response structure and pass all existing tests.
**Validates: Requirements 10.1, 10.2, 10.5**

### Property 16: Historical Data Limit
*For any* Bedrock request, the historical data payload should not exceed 180 days of data.
**Validates: Requirements 8.4**

### Property 17: Response Time for Cached Forecasts
*For any* forecast request that hits the cache, the response time should be less than 500ms.
**Validates: Requirements 8.1**

### Property 18: Bedrock Prompt Structure
*For any* Bedrock request, the prompt should include instructions for time series forecasting and confidence interval calculation.
**Validates: Requirements 2.6**

### Property 19: Error Response Structure
*For any* error condition (insufficient data, invalid parameters, Bedrock failure), the system should return a properly formatted error response with success=false and an error message.
**Validates: Requirements 7.1, 7.3, 7.4, 7.5**

### Property 20: Metrics Emission
*For any* forecast generation, the system should emit CloudWatch metrics for Bedrock API call count, latency, and cache hit rate.
**Validates: Requirements 12.4, 12.5, 12.6**

## Error Handling

### Error Types

1. **InsufficientDataError**: Less than 30 days of historical data
   - HTTP 400
   - Message: "Insufficient historical data. Minimum 30 days required, found X days."

2. **BedrockAPIError**: Bedrock API call failed
   - HTTP 503 (Service Unavailable)
   - Retry-After header: 60 seconds
   - Message: "AI forecasting service temporarily unavailable. Please try again later."

3. **BedrockRateLimitError**: Rate limit exceeded
   - Retry with exponential backoff (1s, 2s, 4s)
   - After 3 retries: HTTP 429 (Too Many Requests)
   - Message: "Rate limit exceeded. Please try again in X seconds."

4. **BedrockInvalidResponseError**: Invalid JSON from Bedrock
   - HTTP 500 (Internal Server Error)
   - Log full response for debugging
   - Message: "Error processing forecast. Please try again."

5. **ValidationError**: Invalid request parameters
   - HTTP 400 (Bad Request)
   - Message: Specific validation error (e.g., "Invalid days value. Must be 7, 14, or 30.")

6. **DynamoDBError**: Database operation failed
   - HTTP 500 (Internal Server Error)
   - Log error details
   - Message: "Error accessing forecast data. Please try again."

### Error Handling Strategy

- **Retry Logic**: Exponential backoff for transient errors (rate limits, network issues)
- **Graceful Degradation**: Return cached forecast if Bedrock fails (if available)
- **Detailed Logging**: Log all errors with context (request parameters, stack traces)
- **User-Friendly Messages**: Don't expose internal errors to API users
- **Monitoring**: Emit CloudWatch metrics for error rates

## Testing Strategy

### Unit Tests

Test individual components in isolation:

- **ForecastEngine**: Data validation, preprocessing, orchestration logic
- **BedrockClient**: Prompt building, response parsing, retry logic
- **CacheManager**: Cache key generation, TTL enforcement, hit rate tracking
- **HistoricalDataRetriever**: Data retrieval, aggregation, interpolation
- **Lambda Handler**: Request routing, parameter validation, response formatting

### Property-Based Tests

Test universal properties across many generated inputs:

- **Property 1-20**: Implement each correctness property as a property-based test
- Use Hypothesis library for test case generation
- Minimum 100 iterations per property
- Tag format: `# Feature: ai-cost-forecasting, Property N: [property text]`

### Integration Tests

Test end-to-end flows:

- **Forecast Generation**: Full flow from API request to response
- **Cache Hit/Miss**: Verify caching behavior
- **Backward Compatibility**: Run all Phase 1 & 1.5 tests
- **Error Scenarios**: Test error handling with mocked failures
- **Bedrock Integration**: Test with mocked Bedrock responses

### Backtesting

Validate forecast accuracy:

- Use historical data to generate forecasts
- Compare predictions against actual costs
- Calculate accuracy metrics (MAPE, RMSE)
- Target: MAPE < 20% for 7-day forecasts

### Test Coverage

- Target: 80%+ code coverage for Phase 2 code
- Focus on critical paths: forecast generation, caching, error handling
- Mock external dependencies: Bedrock, DynamoDB

## Performance Considerations

### Response Times

- **Cached Forecast**: < 500ms (DynamoDB read + JSON serialization)
- **New Forecast**: < 5 seconds (data retrieval + Bedrock call + caching)
- **Bedrock Processing**: < 2 seconds (model inference)

### Optimization Strategies

1. **Aggressive Caching**: 24-hour TTL, 80%+ hit rate target
2. **Data Limiting**: Max 180 days of historical data to Bedrock
3. **Parallel Processing**: Fetch historical data while checking cache
4. **Connection Pooling**: Reuse Bedrock and DynamoDB connections
5. **Payload Compression**: Compress large JSON payloads to Bedrock

### Scalability

- **Serverless**: Lambda auto-scales with request volume
- **DynamoDB**: On-demand billing, auto-scales with load
- **Bedrock**: Managed service, handles scaling automatically
- **Bottleneck**: Bedrock API rate limits (mitigated by caching)

## Security Considerations

### Authentication

- Reuse existing API Gateway API key authentication
- No changes to Phase 1/1.5 authentication

### Authorization

- All forecast endpoints require valid API key
- No additional authorization logic needed (single-tenant MVP)

### Data Privacy

- No PII in cost data
- Bedrock requests contain only aggregated cost numbers
- No sensitive data logged

### IAM Permissions

Lambda execution role needs:
- `bedrock:InvokeModel` - Call Bedrock Nova models
- `dynamodb:GetItem` - Read historical data and cache
- `dynamodb:PutItem` - Write forecast cache
- `dynamodb:Query` - Query historical data by date range
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` - CloudWatch logging

## Deployment Considerations

### Infrastructure Changes

1. **Lambda Environment Variables**:
   - `BEDROCK_MODEL_ID`: "amazon.nova-lite-v1:0"
   - `FORECAST_CACHE_TABLE`: "costguard-forecast-cache"
   - `FORECAST_CACHE_TTL_HOURS`: "24"

2. **DynamoDB Table** (new):
   - Table: `costguard-forecast-cache`
   - Partition Key: `cache_key` (String)
   - TTL Attribute: `ttl` (Number)
   - Billing: On-demand
   - Encryption: AWS managed

3. **IAM Policy Updates**:
   - Add Bedrock permissions to Lambda role
   - Add DynamoDB permissions for forecast cache table

4. **API Gateway Routes** (new):
   - GET `/api/cost-forecast`
   - GET `/api/cost-forecast/service/{service}`
   - Both require API key authentication

### Deployment Steps

1. Create forecast cache DynamoDB table
2. Update Lambda IAM role with Bedrock permissions
3. Deploy updated Lambda function code
4. Add new API Gateway routes
5. Run integration tests
6. Verify Phase 1 & 1.5 still work
7. Monitor CloudWatch logs and metrics

### Rollback Plan

If issues arise:
1. Remove new API Gateway routes
2. Revert Lambda function to previous version
3. Phase 1 & 1.5 continue working (no breaking changes)
4. Forecast cache table can remain (no impact)

## Monitoring and Observability

### CloudWatch Metrics

- `BedrockAPICallCount`: Number of Bedrock API calls
- `BedrockAPILatency`: Bedrock API call latency (ms)
- `ForecastCacheHitRate`: Percentage of cache hits
- `ForecastGenerationLatency`: Total forecast generation time (ms)
- `ForecastErrors`: Count of forecast generation errors

### CloudWatch Logs

- All Bedrock API calls (request/response)
- Cache hit/miss events
- Error details with stack traces
- Performance metrics (latency breakdown)

### Alarms

- Bedrock API error rate > 5%
- Cache hit rate < 70%
- Forecast generation latency > 10 seconds
- Bedrock API call count approaching Free Tier limit (800/month)

## Future Enhancements

1. **Multiple Models**: Support for different Bedrock models (Nova Pro for better accuracy)
2. **Custom Forecast Horizons**: Support for 60, 90-day forecasts
3. **Anomaly Detection**: Flag unusual cost patterns in forecasts
4. **Forecast Explanations**: Include reasoning for predictions
5. **Multi-Region**: Aggregate forecasts across AWS regions
6. **Forecast Comparison**: Compare forecasts over time to track accuracy
7. **Budget Integration**: Combine forecasts with budget thresholds for alerts
