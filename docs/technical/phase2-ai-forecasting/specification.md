# Phase 2 Specification: AI-Powered Cost Forecasting

## Executive Summary

Phase 2 extends CostGuard with AI-powered cost forecasting capabilities using Amazon Bedrock Nova Lite. This enables users to predict future AWS spending for 7-30 days with 95% confidence intervals, supporting proactive budget management and cost optimization.

**Key Capabilities:**
- AI-powered cost predictions using Amazon Bedrock Nova Lite
- 7, 14, or 30-day forecast horizons
- Daily or weekly granularity
- 95% confidence intervals for all predictions
- Service-specific and total cost forecasts
- Intelligent 24-hour forecast caching (80%+ hit rate)
- Full backward compatibility with Phase 1 & 1.5

## Requirements

For complete requirements, see [requirements.md](../../../.kiro/specs/ai-cost-forecasting/requirements.md)

### Core Requirements Summary

1. **Historical Data Retrieval** - Retrieve 90 days of historical cost data with gap interpolation
2. **Bedrock Integration** - Integrate with Amazon Bedrock Nova Lite for AI predictions
3. **Forecast Generation** - Generate 7-30 day forecasts with confidence intervals
4. **Forecast Caching** - Cache forecasts for 24 hours to minimize Bedrock costs
5. **API Endpoints** - Provide REST API for total and service-specific forecasts
6. **Response Format** - Consistent JSON responses with metadata
7. **Error Handling** - Robust error handling with retry logic
8. **Performance** - <500ms for cached, <5s for new forecasts
9. **Free Tier Compliance** - <500 Bedrock calls/month with 80%+ cache hit rate
10. **Backward Compatibility** - Phase 1 & 1.5 endpoints unchanged
11. **Testing** - 80%+ coverage with property-based tests
12. **Monitoring** - CloudWatch metrics for Bedrock calls, cache hits, latency

## Design

For complete design, see [design.md](../../../.kiro/specs/ai-cost-forecasting/design.md)

### Architecture Overview

```
API Gateway → Lambda Handler → Forecast Engine
                             → Bedrock Client (Nova Lite)
                             → Historical Data Retriever
                             → Forecast Cache Manager
                             ↓
                          DynamoDB (cost data + forecast cache)
```

### Key Components

1. **Forecast Engine** (`forecast_engine.py`)
   - Orchestrates forecast generation
   - Checks cache first
   - Retrieves and validates historical data
   - Calls Bedrock for predictions
   - Aggregates to weekly if needed
   - Stores in cache

2. **Bedrock Client** (`bedrock_client.py`)
   - Interfaces with Amazon Bedrock Nova Lite
   - Builds time series forecasting prompts
   - Parses JSON responses
   - Implements exponential backoff retry logic

3. **Historical Data Retriever** (`historical_data.py`)
   - Retrieves 90 days of historical cost data
   - Aggregates by service and date
   - Interpolates missing dates
   - Validates data completeness (minimum 30 days)

4. **Forecast Cache Manager** (`forecast_cache.py`)
   - Manages forecast caching in DynamoDB
   - 24-hour TTL for forecasts
   - Unique cache keys per service/days/granularity
   - Tracks cache hit rate

### Data Models

**ForecastDataPoint:**
- date: string (YYYY-MM-DD)
- predicted_cost: float
- confidence_lower: float (95% CI lower bound)
- confidence_upper: float (95% CI upper bound)
- currency: string (USD)

**ForecastResponse:**
- success: bool
- forecast: List[ForecastDataPoint]
- metadata: ForecastMetadata

**ForecastMetadata:**
- days: int (7, 14, or 30)
- granularity: string (daily or weekly)
- service: Optional[string]
- generated_at: string (ISO 8601)
- model_used: string (amazon.nova-lite-v1:0)
- cache_hit: bool
- historical_data_days: int

## Implementation

For complete implementation details, see [implementation-summary.md](./implementation-summary.md)

### Code Organization

```
src/
├── lambda_handler.py          # Extended with Phase 2 routes
├── services/
│   ├── forecast_engine.py     # NEW: Forecast orchestration
│   ├── bedrock_client.py      # NEW: Bedrock integration
│   ├── historical_data.py     # NEW: Historical data retrieval
│   ├── forecast_cache.py      # NEW: Forecast caching
│   ├── cost_explorer.py       # Phase 1 (unchanged)
│   ├── cloudwatch_collector.py # Phase 1.5 (unchanged)
│   └── ...                    # Other Phase 1/1.5 services
└── utils/
    ├── types.py               # Extended with Phase 2 types
    ├── validation.py          # Extended with Phase 2 validation
    └── ...                    # Phase 1/1.5 utilities (unchanged)
```

### API Endpoints

**Phase 1 (Unchanged):**
- POST /api/cost-data/fetch
- GET /api/cost-data

**Phase 1.5 (Unchanged):**
- GET /api/cost-estimation/current
- GET /api/cost-estimation/service/{service}

**Phase 2 (New):**
- GET /api/cost-forecast
- GET /api/cost-forecast/service/{service}

### Infrastructure Changes

**IAM Permissions Added:**
- bedrock:InvokeModel

**DynamoDB Tables Added:**
- costguard-forecast-cache (partition key: cache_key, TTL: ttl)

**Environment Variables Added:**
- BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
- FORECAST_CACHE_TABLE=costguard-forecast-cache
- FORECAST_CACHE_TTL_HOURS=24

**API Gateway Routes Added:**
- GET /api/cost-forecast
- GET /api/cost-forecast/service/{service}

## Testing Strategy

### Test Coverage

- **Total Tests:** 412 (134 Phase 1 + 102 Phase 1.5 + 176 Phase 2)
- **Code Coverage:** 94.16%
- **Property-Based Tests:** 20 properties with 100+ iterations each

### Test Types

1. **Unit Tests**
   - Test individual components with mocked dependencies
   - Verify specific examples and edge cases
   - Test error handling paths

2. **Property-Based Tests**
   - Validate universal properties using Hypothesis
   - Test with randomly generated inputs
   - Ensure correctness across all valid inputs

3. **Integration Tests**
   - Test end-to-end flows
   - Verify Phase 1 & 1.5 compatibility
   - Test service interactions

### Key Properties Tested

1. Historical data validation (minimum 30 days)
2. Data interpolation completeness (no gaps)
3. Forecast length consistency (H days = H data points)
4. Confidence interval validity (lower ≤ predicted ≤ upper)
5. Non-negative cost predictions
6. Weekly aggregation consistency
7. Service-specific data filtering
8. Total forecast aggregation
9. Cache key uniqueness
10. Cache TTL enforcement
11. Cache invalidation completeness
12. Response structure completeness
13. Forecast data point structure
14. Retry logic for rate limiting
15. Backward compatibility
16. Historical data limit (max 180 days)
17. Response time for cached forecasts (<500ms)
18. Bedrock prompt structure
19. Error response structure
20. Metrics emission

## Deployment

### Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Python 3.12+
- Node.js 18+ (for CDK)
- Phase 1 & 1.5 already deployed

### Deployment Steps

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   cd infrastructure
   npm install
   ```

2. **Deploy Infrastructure:**
   ```bash
   cdk deploy
   ```

3. **Verify Deployment:**
   ```bash
   # Test Phase 1 endpoint (should still work)
   curl -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/cost-data"
   
   # Test Phase 1.5 endpoint (should still work)
   curl -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/cost-estimation/current"
   
   # Test Phase 2 endpoint (new)
   curl -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/cost-forecast?days=7"
   ```

### Rollback

To rollback Phase 2:
1. Revert infrastructure files to Phase 1.5 versions
2. Run `cdk deploy`
3. Phase 1 & 1.5 endpoints continue to work
4. Phase 2 endpoints return 404

## Cost Analysis

### Monthly Cost Breakdown

| Service | Usage | Free Tier | Cost |
|---------|-------|-----------|------|
| Lambda | ~3,000 invocations | 1M free | $0.00 |
| API Gateway | ~3,000 requests | 1M free | $0.00 |
| DynamoDB | ~100 MB storage | 25 GB free | $0.00 |
| CloudWatch API | ~50,000 requests | 1M free | $0.00 |
| Cost Explorer | ~100 calls | N/A | ~$1.00 |
| Pricing API | ~100 calls | N/A | ~$0.01 |
| Bedrock Nova Lite | ~500 calls | N/A | ~$0.50 |

**Total Monthly Cost:** ~$1.51

### Cost Optimization

- **Forecast Cache:** 24-hour TTL with 80%+ hit rate reduces Bedrock calls by 80%
- **Nova Lite Model:** Most cost-effective Bedrock model for time series forecasting
- **On-Demand DynamoDB:** Pay only for actual usage
- **Efficient Queries:** Optimized historical data retrieval

## Performance Characteristics

### Response Times

- **Cached Forecast:** < 500ms (95th percentile)
- **New Forecast:** < 5 seconds (95th percentile)
- **Bedrock API Call:** 2-3 seconds average
- **Historical Data Retrieval:** < 1 second

### Throughput

- **API Gateway:** 10,000 requests/second (default limit)
- **Lambda:** Concurrent executions scale automatically
- **Bedrock:** Rate limits managed with exponential backoff
- **DynamoDB:** On-demand scaling (no provisioned capacity)

### Caching

- **Forecast Cache Hit Rate:** > 80% target
- **Forecast Cache TTL:** 24 hours
- **Historical Data:** Retrieved fresh for each forecast generation
- **Pricing Data:** Cached from Phase 1.5 (24-hour TTL)

## Monitoring and Observability

### CloudWatch Logs

Log group: `/aws/lambda/costguard-cost-data-handler`

**Log Events:**
- Forecast generation operations
- Bedrock API calls (request/response)
- Cache hit/miss events
- Historical data retrieval
- Errors and warnings

### CloudWatch Metrics

**Custom Metrics:**
- BedrockAPICallCount
- BedrockAPILatency
- ForecastCacheHitRate
- ForecastGenerationLatency
- ForecastErrors

**AWS Metrics:**
- Lambda invocations, duration, errors
- API Gateway requests, latency, errors
- DynamoDB read/write capacity

### Alarms (Recommended)

- Bedrock API error rate (> 5%)
- Cache hit rate (< 70%)
- Forecast generation latency (> 10 seconds)
- Bedrock API call count approaching limit (> 800/month)

## Security Considerations

### Authentication

- API key authentication (reuses Phase 1 mechanism)
- API keys managed via API Gateway
- Keys associated with usage plans

### Authorization

- Lambda execution role with least-privilege permissions
- Read-only access to historical cost data
- Bedrock InvokeModel permission (model-level, not resource-level)

### Data Protection

- No sensitive data stored
- Cost data is business information (not PII)
- DynamoDB encryption at rest (default)
- HTTPS for all API communication
- Bedrock requests contain only aggregated cost numbers

## Limitations and Known Issues

### Current Limitations

1. **Forecast Horizons:** Only 7, 14, or 30 days supported
2. **Service Support:** Same services as Phase 1 (EC2, Lambda, DynamoDB, S3, RDS, etc.)
3. **Region Support:** Single region (us-east-1 by default)
4. **Historical Data:** Requires minimum 30 days of data
5. **Forecast Accuracy:** ±5-10% compared to actual costs (typical for AI forecasting)

### Known Issues

None at this time.

### Future Improvements

1. **Custom Horizons:** Support 60, 90-day forecasts
2. **Multiple Models:** Support Nova Pro for better accuracy
3. **Anomaly Detection:** Flag unusual cost patterns in forecasts
4. **Forecast Explanations:** Include reasoning for predictions
5. **Multi-Region:** Aggregate forecasts across regions
6. **Forecast Comparison:** Track forecast accuracy over time
7. **Budget Integration:** Combine forecasts with budget thresholds for alerts

## References

### Internal Documentation

- [Requirements](../../../.kiro/specs/ai-cost-forecasting/requirements.md)
- [Design](../../../.kiro/specs/ai-cost-forecasting/design.md)
- [Implementation Summary](./implementation-summary.md)
- [Infrastructure Updates](./infrastructure-updates.md)
- [README](./README.md)
- [API Examples](../../API_EXAMPLES.md)
- [Phase 1 Documentation](../phase1-cost-pipeline/)
- [Phase 1.5 Documentation](../phase1.5-near-realtime/)

### AWS Documentation

- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Amazon Nova Models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-nova.html)
- [Bedrock InvokeModel API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html)
- [DynamoDB TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)
- [Cost Explorer API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html)

### Competition Documentation

- [Competition Overview](../../competition/overview.md)
- [Submission Requirements](../../submission/requirements.md)
- [Judging Criteria](../../submission/judging-criteria.md)

## Appendix

### Glossary

- **Forecast Horizon:** The time period for predictions (7, 14, or 30 days)
- **Granularity:** Time resolution of forecasts (daily or weekly)
- **Confidence Interval:** Statistical range indicating forecast uncertainty (95% CI)
- **Nova Lite:** Amazon's cost-effective Bedrock model for time series forecasting
- **Cache Hit Rate:** Percentage of forecast requests served from cache
- **TTL:** Time To Live - expiration time for cached forecasts (24 hours)
- **Interpolation:** Filling missing dates with estimated values (linear interpolation)
- **Backtesting:** Validating forecast accuracy against historical data

### Acronyms

- **API:** Application Programming Interface
- **CDK:** Cloud Development Kit
- **TTL:** Time To Live
- **CI:** Confidence Interval
- **MAPE:** Mean Absolute Percentage Error
- **RMSE:** Root Mean Square Error
- **PBT:** Property-Based Testing

### Version History

- **v1.0 (January 2026):** Initial Phase 2 release
  - AI-powered cost forecasting with Bedrock Nova Lite
  - 7, 14, 30-day forecast horizons
  - Daily and weekly granularity
  - 95% confidence intervals
  - 24-hour forecast caching
  - Service-specific and total forecasts
  - Comprehensive test suite (412 tests, 94.16% coverage)
  - Infrastructure deployment via CDK
  - Full backward compatibility with Phase 1 & 1.5

