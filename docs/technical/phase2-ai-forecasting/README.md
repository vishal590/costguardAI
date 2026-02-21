# Phase 2: AI-Powered Cost Forecasting

**Status:** ✅ Complete  
**Implementation Date:** January 2026  
**Test Coverage:** 94%+ (412 tests passing)

## Overview

Phase 2 adds AI-powered cost forecasting capabilities to CostGuard using Amazon Bedrock Nova Lite. The system generates 7-30 day cost forecasts with 95% confidence intervals based on historical cost data.

## Key Features

- **AI-Powered Predictions:** Uses Amazon Bedrock Nova Lite for time series forecasting
- **Confidence Intervals:** Provides 95% confidence intervals (upper/lower bounds) for all predictions
- **Flexible Horizons:** Supports 7, 14, or 30-day forecasts
- **Multiple Granularities:** Daily or weekly aggregation
- **Service-Specific Forecasts:** Generate forecasts for individual AWS services or total costs
- **Intelligent Caching:** 24-hour forecast cache with 80%+ hit rate target
- **Historical Data Processing:** Retrieves 90 days of historical data with gap interpolation
- **Backward Compatible:** Maintains full compatibility with Phase 1 & 1.5 endpoints

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  API Gateway                                 │
│  GET /api/cost-forecast                                     │
│  GET /api/cost-forecast/service/{service}                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Handler                                  │
│  - Route forecast requests                                  │
│  - Validate parameters (days, granularity)                  │
│  - Format responses                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Forecast Engine                                   │
│  - Orchestrate forecast generation                          │
│  - Check cache first                                        │
│  - Retrieve & validate historical data                      │
│  - Call Bedrock for predictions                             │
│  - Aggregate to weekly if needed                            │
│  - Store in cache                                           │
└─┬───────────────┬───────────────┬───────────────┬──────────┘
  │               │               │               │
  ▼               ▼               ▼               ▼
┌────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐
│Bedrock │  │Historical│  │Forecast Cache│  │DynamoDB  │
│Client  │  │Data      │  │Manager       │  │(Cost Data│
│        │  │Retriever │  │              │  │& Cache)  │
└────────┘  └──────────┘  └──────────────┘  └──────────┘
```

## Components

### 1. Forecast Engine (`forecast_engine.py`)
**Purpose:** Orchestrates the entire forecast generation process

**Key Methods:**
- `generate_forecast()` - Main entry point for forecast generation
- `aggregate_to_weekly()` - Aggregates daily forecasts to weekly totals
- `validate_historical_data()` - Ensures sufficient data quality

**Responsibilities:**
- Check cache for existing forecasts
- Retrieve and validate historical data
- Call Bedrock for AI predictions
- Aggregate forecasts if needed
- Store results in cache
- Return formatted responses

### 2. Bedrock Client (`bedrock_client.py`)
**Purpose:** Interfaces with Amazon Bedrock Nova Lite for AI predictions

**Key Methods:**
- `invoke_forecast()` - Calls Bedrock API with historical data
- `build_prompt()` - Constructs time series forecasting prompt
- `parse_response()` - Extracts predictions from Bedrock response
- `retry_with_backoff()` - Handles rate limiting with exponential backoff

**Features:**
- Structured prompts for time series forecasting
- JSON response parsing with validation
- Exponential backoff retry logic (1s, 2s, 4s)
- Non-negative cost enforcement
- Confidence interval validation

### 3. Historical Data Retriever (`historical_data.py`)
**Purpose:** Retrieves and processes historical cost data from DynamoDB

**Key Methods:**
- `get_historical_data()` - Fetches historical costs (90 days)
- `aggregate_by_service_and_date()` - Groups costs by service and date
- `interpolate_gaps()` - Fills missing dates with linear interpolation
- `validate_completeness()` - Ensures minimum 30 days of data

**Features:**
- Retrieves up to 90 days of historical data
- Aggregates multiple records per day
- Linear interpolation for missing dates
- Service-specific filtering
- Data quality validation

### 4. Forecast Cache Manager (`forecast_cache.py`)
**Purpose:** Manages forecast caching in DynamoDB

**Key Methods:**
- `get_cached_forecast()` - Retrieves cached forecast if valid
- `store_forecast()` - Stores forecast with 24-hour TTL
- `invalidate_all()` - Clears all cached forecasts
- `track_cache_hit_rate()` - Monitors cache performance

**Features:**
- 24-hour TTL for forecasts
- Unique cache keys per service/days/granularity
- Automatic TTL expiration
- Cache hit rate tracking
- Separate DynamoDB table

## API Endpoints

### GET /api/cost-forecast

Generate cost forecast for all services (total costs).

**Query Parameters:**
- `days` - Forecast horizon: 7, 14, or 30 (default: 30)
- `granularity` - Time resolution: `daily` or `weekly` (default: daily)

**Example Request:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api-id.execute-api.us-east-1.amazonaws.com/prod/api/cost-forecast?days=30&granularity=daily"
```

**Example Response:**
```json
{
  "success": true,
  "forecast": [
    {
      "date": "2026-01-22",
      "predicted_cost": 15.50,
      "confidence_lower": 12.00,
      "confidence_upper": 19.00,
      "currency": "USD"
    }
  ],
  "metadata": {
    "days": 30,
    "granularity": "daily",
    "service": "total",
    "generated_at": "2026-01-21T10:30:00Z",
    "model_used": "amazon.nova-lite-v1:0",
    "cache_hit": false,
    "historical_data_days": 90
  }
}
```

### GET /api/cost-forecast/service/{service}

Generate cost forecast for a specific AWS service.

**Path Parameters:**
- `service` - Service name: `ec2`, `lambda`, `dynamodb`, `s3`, `rds`

**Query Parameters:**
- `days` - Forecast horizon: 7, 14, or 30 (default: 30)
- `granularity` - Time resolution: `daily` or `weekly` (default: daily)

**Example Request:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api-id.execute-api.us-east-1.amazonaws.com/prod/api/cost-forecast/service/ec2?days=14&granularity=weekly"
```

## Data Flow

1. **Request Received** → Lambda handler validates parameters
2. **Cache Check** → ForecastCacheManager checks for existing forecast
3. **Cache Hit** → Return cached forecast immediately (fast path)
4. **Cache Miss** → Continue to forecast generation
5. **Historical Data** → HistoricalDataRetriever fetches 90 days from DynamoDB
6. **Data Validation** → Ensure minimum 30 days, interpolate gaps
7. **Bedrock Call** → BedrockClient sends prompt to Nova Lite
8. **Parse Response** → Extract predictions and confidence intervals
9. **Aggregation** → Aggregate to weekly if requested
10. **Cache Store** → ForecastCacheManager stores with 24-hour TTL
11. **Response** → Return formatted forecast to client

## Error Handling

### InsufficientDataError (400)
**Cause:** Less than 30 days of historical data available  
**Response:**
```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_DATA",
    "message": "Insufficient historical data. Need at least 30 days, found 15 days."
  }
}
```

### BedrockRateLimitError (429)
**Cause:** Bedrock API rate limit exceeded  
**Retry Logic:** Exponential backoff (1s, 2s, 4s) with max 3 retries  
**Response:**
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Bedrock API rate limit exceeded. Please try again later."
  }
}
```

### BedrockAPIError (503)
**Cause:** Bedrock service unavailable or API error  
**Response:**
```json
{
  "success": false,
  "error": {
    "code": "BEDROCK_API_ERROR",
    "message": "Bedrock API error: Service temporarily unavailable"
  }
}
```

### ValidationError (400)
**Cause:** Invalid parameters (days not in [7,14,30], invalid granularity, etc.)  
**Response:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid days parameter. Must be 7, 14, or 30."
  }
}
```

## Testing

**Test Coverage:** 94%+ across all Phase 2 modules

### Unit Tests
- `test_forecast_engine.py` - Forecast orchestration logic
- `test_bedrock_client.py` - Bedrock API integration
- `test_historical_data.py` - Data retrieval and processing
- `test_forecast_cache.py` - Cache management
- `test_lambda_handler_phase2.py` - API endpoint routing

### Property-Based Tests
- Historical data validation (100 iterations)
- Data interpolation completeness (100 iterations)
- Cache key uniqueness (100 iterations)
- Cache TTL enforcement (100 iterations)
- Retry logic for rate limiting (100 iterations)
- Bedrock prompt structure (100 iterations)

### Integration Tests
- Phase 1 & 1.5 backward compatibility
- End-to-end forecast generation
- Cache hit/miss scenarios
- Error handling flows

## Infrastructure

### DynamoDB Tables

**costguard-forecast-cache**
- Partition Key: `cache_key` (String)
- TTL Attribute: `ttl` (Number, 24 hours)
- Billing Mode: On-demand
- Purpose: Store forecast results with automatic expiration

**costguard-cost-data** (existing)
- Used for historical data retrieval
- No changes from Phase 1

### IAM Permissions

Added to Lambda execution role:
```json
{
  "Effect": "Allow",
  "Action": ["bedrock:InvokeModel"],
  "Resource": "*"
}
```

### Lambda Environment Variables

- `BEDROCK_MODEL_ID` - Model identifier (amazon.nova-lite-v1:0)
- `FORECAST_CACHE_TABLE` - Cache table name (costguard-forecast-cache)
- `FORECAST_CACHE_TTL_HOURS` - Cache TTL in hours (24)

### API Gateway Routes

- `GET /api/cost-forecast` - Total cost forecasts
- `GET /api/cost-forecast/service/{service}` - Service-specific forecasts

## Cost Optimization

### Bedrock Usage
- **Target:** <500 requests/month
- **Strategy:** 80%+ cache hit rate with 24-hour TTL
- **Cost:** ~$0.50/month (Nova Lite pricing)

### DynamoDB
- **Forecast Cache:** ~50 MB storage
- **Billing:** On-demand (within Free Tier)
- **Cost:** $0 (within 25 GB free tier)

### Total Phase 2 Cost
- **Estimated:** ~$0.50/month additional
- **Total System:** ~$1.51/month (including Phase 1 & 1.5)

## Performance

### Response Times
- **Cache Hit:** <200ms (DynamoDB lookup only)
- **Cache Miss:** 2-5 seconds (includes Bedrock API call)
- **Target Cache Hit Rate:** 80%+

### Bedrock API
- **Model:** Amazon Nova Lite (fast, cost-effective)
- **Timeout:** 30 seconds
- **Retry:** 3 attempts with exponential backoff

## Monitoring

### CloudWatch Metrics
- Bedrock API call count
- Bedrock API latency
- Cache hit/miss ratio
- Forecast generation errors
- Historical data retrieval time

### Logs
- All Bedrock API calls logged
- Cache operations logged
- Error details with stack traces
- Request/response payloads (debug level)

## Related Documentation

- [Requirements](../../../.kiro/specs/ai-cost-forecasting/requirements.md) - Detailed requirements
- [Design](../../../.kiro/specs/ai-cost-forecasting/design.md) - System design and correctness properties
- [Tasks](../../../.kiro/specs/ai-cost-forecasting/tasks.md) - Implementation task list
- [Phase 1 Docs](../phase1-cost-pipeline/) - Historical cost data pipeline
- [Phase 1.5 Docs](../phase1.5-near-realtime/) - Near-real-time cost estimation
- [API Examples](../../API_EXAMPLES.md) - Complete API usage examples

## Code References

### Source Files
- `src/services/forecast_engine.py` - Main orchestration
- `src/services/bedrock_client.py` - Bedrock integration
- `src/services/historical_data.py` - Data retrieval
- `src/services/forecast_cache.py` - Cache management
- `src/lambda_handler.py` - API routing (lines 735-897)

### Test Files
- `tests/unit/test_forecast_engine.py`
- `tests/unit/test_bedrock_client.py`
- `tests/unit/test_historical_data.py`
- `tests/unit/test_forecast_cache.py`
- `tests/unit/test_lambda_handler_phase2.py`

### Infrastructure
- `infrastructure/dynamodb_table.py` - Forecast cache table
- `infrastructure/iam_roles.py` - Bedrock permissions
- `infrastructure/lambda_function.py` - Environment variables
- `infrastructure/api_gateway.py` - Forecast endpoints

## Keywords

AI, forecasting, prediction, machine learning, Amazon Bedrock, Nova Lite, time series, confidence intervals, cache, historical data, interpolation, cost prediction, AWS costs, future costs, budget planning
