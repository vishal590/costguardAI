# Phase 1.5 Specification: Near-Real-Time Cost Estimation

## Executive Summary

Phase 1.5 extends the Cost Data Pipeline by adding near-real-time cost estimation capabilities. This enables users to see their AWS spending as it happens, without waiting for AWS Cost Explorer's 24-hour delay.

**Key Capabilities:**
- Estimate current costs for EC2, Lambda, DynamoDB, S3, and RDS
- Collect CloudWatch metrics and apply real-time pricing
- Provide confidence intervals for estimation accuracy
- Operate within AWS Free Tier limits
- Maintain full backward compatibility with Phase 1

## Requirements

For complete requirements, see [requirements.md](./requirements.md)

### Core Requirements Summary

1. **CloudWatch Metrics Collection** - Collect usage metrics from CloudWatch for all supported services
2. **Cost Estimation Algorithms** - Calculate accurate cost estimates based on metrics and pricing
3. **Pricing Data Management** - Fetch and cache AWS pricing data with 24-hour TTL
4. **Estimation API Endpoints** - Provide REST API for querying cost estimates
5. **Phase 1 Integration** - Seamlessly integrate with existing Phase 1 infrastructure
6. **Error Handling** - Robust error handling with retry logic
7. **Performance** - Complete requests within 2-5 seconds
8. **Data Validation** - Validate all metrics and pricing data
9. **Monitoring** - Comprehensive logging and observability
10. **Free Tier Compliance** - Operate within AWS Free Tier limits

## Design

For complete design, see [design.md](./design.md)

### Architecture Overview

```
API Gateway → Lambda Handler → CloudWatch Metrics Collector
                             → Cost Estimator
                             → Pricing Manager
                             ↓
                          DynamoDB (cache)
```

### Key Components

1. **CloudWatch Metrics Collector**
   - Collects usage metrics from CloudWatch
   - Supports EC2, Lambda, DynamoDB, S3, RDS
   - Batches requests to minimize API calls

2. **Cost Estimator**
   - Applies pricing formulas to metrics
   - Calculates confidence intervals
   - Aggregates costs across services

3. **Pricing Manager**
   - Fetches pricing from AWS Pricing API
   - Caches pricing in DynamoDB (24-hour TTL)
   - Refreshes stale pricing automatically

### Data Models

**MetricDataPoint:**
- timestamp: datetime
- value: Decimal
- unit: string
- metric_name: string

**CostEstimate:**
- service: string
- estimated_cost: Decimal
- currency: string
- confidence_lower: Decimal
- confidence_upper: Decimal
- timestamp: datetime
- period_start: datetime
- period_end: datetime
- metrics_count: int

**PricingData:**
- service: string
- region: string
- prices: Dict[str, Decimal]
- currency: string
- last_updated: datetime
- ttl: int

## Implementation

For complete implementation details, see [implementation-summary.md](./implementation-summary.md)

### Code Organization

```
src/
├── lambda_handler.py          # Extended with Phase 1.5 routes
├── services/
│   ├── cloudwatch_collector.py # NEW: CloudWatch metrics collection
│   ├── cost_estimator.py      # NEW: Cost estimation algorithms
│   ├── pricing_manager.py     # NEW: Pricing data management
│   ├── cost_explorer.py       # Phase 1 (unchanged)
│   └── dynamodb.py            # Phase 1 (unchanged)
└── utils/
    ├── types.py               # Extended with Phase 1.5 types
    ├── validation.py          # Extended with Phase 1.5 validation
    └── ...                    # Phase 1 utilities (unchanged)
```

### API Endpoints

**Phase 1 (Unchanged):**
- POST /api/cost-data/fetch
- GET /api/cost-data

**Phase 1.5 (New):**
- GET /api/cost-estimation/current
- GET /api/cost-estimation/service/{service}

### Infrastructure Changes

**IAM Permissions Added:**
- cloudwatch:GetMetricStatistics
- cloudwatch:ListMetrics
- pricing:GetProducts

**Environment Variables Added:**
- PRICING_CACHE_TTL_HOURS=24
- METRICS_COLLECTION_PERIOD=300
- ESTIMATION_CONFIDENCE_LEVEL=0.95

**API Gateway Routes Added:**
- GET /api/cost-estimation/current
- GET /api/cost-estimation/service/{service}

## Testing Strategy

### Test Coverage

- **Total Tests:** 236 (134 Phase 1 + 102 Phase 1.5)
- **Code Coverage:** 89%
- **Property-Based Tests:** 15 properties with 100+ iterations each

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
   - Verify Phase 1 compatibility
   - Test service interactions

### Key Properties Tested

1. Metric collection completeness
2. Non-negative cost estimates
3. Pricing data freshness
4. API response structure
5. Authentication enforcement
6. Phase 1 compatibility
7. Retry logic for rate limiting
8. Error isolation
9. Response time bounds
10. Metric validation
11. Pricing validation
12. Estimation bounds check
13. Batch metric collection
14. Pricing cache hit
15. Confidence interval validity

## Deployment

### Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Python 3.12+
- Node.js 18+ (for CDK)

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
   
   # Test Phase 1.5 endpoint (new)
   curl -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/cost-estimation/current"
   ```

### Rollback

To rollback Phase 1.5:
1. Revert infrastructure files to Phase 1 versions
2. Run `cdk deploy`
3. Phase 1 endpoints continue to work
4. Phase 1.5 endpoints return 404

## Cost Analysis

### Monthly Cost Breakdown

| Service | Usage | Free Tier | Cost |
|---------|-------|-----------|------|
| Lambda | ~2,000 invocations | 1M free | $0.00 |
| API Gateway | ~2,000 requests | 1M free | $0.00 |
| DynamoDB | ~50 MB storage | 25 GB free | $0.00 |
| CloudWatch API | ~50,000 requests | 1M free | $0.00 |
| Cost Explorer | ~100 calls | N/A | ~$1.00 |
| Pricing API | ~100 calls | N/A | ~$0.01 |

**Total Monthly Cost:** ~$1.01

### Cost Optimization

- **Pricing Cache:** 24-hour TTL reduces Pricing API calls by 95%
- **Metric Batching:** Batched CloudWatch requests minimize API calls
- **On-Demand DynamoDB:** Pay only for actual usage
- **Efficient Queries:** Optimized CloudWatch metric periods

## Performance Characteristics

### Response Times

- **Single Service Query:** < 2 seconds (95th percentile)
- **All Services Query:** < 5 seconds (95th percentile)
- **Cold Start:** ~1-2 seconds (first request)
- **Warm Start:** ~0.5-1 second (subsequent requests)

### Throughput

- **API Gateway:** 10,000 requests/second (default limit)
- **Lambda:** Concurrent executions scale automatically
- **CloudWatch API:** 1,000,000 requests/month (Free Tier)
- **DynamoDB:** On-demand scaling (no provisioned capacity)

### Caching

- **Pricing Cache Hit Rate:** > 95%
- **Pricing Cache TTL:** 24 hours
- **Metric Collection Period:** 5 minutes
- **Result Caching:** Not implemented (future enhancement)

## Monitoring and Observability

### CloudWatch Logs

Log group: `/aws/lambda/costguard-cost-data-handler`

**Log Events:**
- Metric collection operations
- Cost estimation calculations
- Pricing data fetches and cache operations
- API endpoint requests
- Errors and warnings

### CloudWatch Metrics

**Custom Metrics:**
- EstimationRequestCount
- EstimationLatency
- MetricCollectionErrors
- PricingCacheHitRate

**AWS Metrics:**
- Lambda invocations, duration, errors
- API Gateway requests, latency, errors
- DynamoDB read/write capacity

### Alarms (Recommended)

- High error rate (> 5%)
- High latency (> 5 seconds)
- CloudWatch API throttling
- Pricing API errors

## Security Considerations

### Authentication

- API key authentication (reuses Phase 1 mechanism)
- API keys managed via API Gateway
- Keys associated with usage plans

### Authorization

- Lambda execution role with least-privilege permissions
- Read-only access to CloudWatch and Pricing API
- No resource-level permissions (CloudWatch/Pricing require "*")

### Data Protection

- No sensitive data stored
- Cost data is business information (not PII)
- DynamoDB encryption at rest (default)
- HTTPS for all API communication

## Limitations and Known Issues

### Current Limitations

1. **Service Support:** Only EC2, Lambda, DynamoDB, S3, RDS
2. **Region Support:** Single region (us-east-1 by default)
3. **Time Range:** Maximum 168 hours (7 days)
4. **Estimation Accuracy:** ±5-10% compared to actual costs
5. **Metric Delay:** CloudWatch metrics have 1-5 minute delay

### Known Issues

None at this time.

### Future Improvements

1. **Additional Services:** CloudFront, API Gateway, ECS, EKS
2. **Multi-Region:** Aggregate costs across regions
3. **Cost Forecasting:** Predict future costs based on trends
4. **Anomaly Detection:** Alert on unusual cost spikes
5. **Result Caching:** Cache estimation results for 5-10 minutes
6. **Dashboard UI:** Visual cost monitoring interface

## References

### Internal Documentation

- [Requirements](./requirements.md)
- [Design](./design.md)
- [Implementation Summary](./implementation-summary.md)
- [Infrastructure Updates](./infrastructure-updates.md)
- [API Examples](../../API_EXAMPLES.md)
- [Phase 1 Documentation](../phase1-cost-pipeline/)

### AWS Documentation

- [CloudWatch GetMetricStatistics API](https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_GetMetricStatistics.html)
- [AWS Pricing API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html)
- [Cost Explorer API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)

### Competition Documentation

- [Competition Overview](../../competition/overview.md)
- [Submission Requirements](../../submission/requirements.md)
- [Judging Criteria](../../submission/judging-criteria.md)

## Appendix

### Glossary

- **Near-Real-Time:** Data available within 1-5 minutes (vs 24-hour delay)
- **Confidence Interval:** Statistical range indicating estimation accuracy
- **Pricing Cache:** Temporary storage of AWS pricing data
- **Metric Period:** Time window for metric aggregation (5 minutes)
- **Free Tier:** AWS services available at no cost up to usage limits

### Acronyms

- **API:** Application Programming Interface
- **CDK:** Cloud Development Kit
- **TTL:** Time To Live
- **IOPS:** Input/Output Operations Per Second
- **RCU:** Read Capacity Unit
- **WCU:** Write Capacity Unit
- **PBT:** Property-Based Testing

### Version History

- **v1.0 (2025-02-21):** Initial Phase 1.5 release
  - CloudWatch metrics collection
  - Cost estimation algorithms
  - Pricing data management
  - API endpoints
  - Comprehensive test suite
  - Infrastructure deployment
