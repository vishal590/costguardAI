# Phase 1.5: Near-Real-Time Cost Estimation

## Overview

Phase 1.5 extends the Cost Data Pipeline (Phase 1) by adding near-real-time cost estimation capabilities. While Phase 1 provides historical cost data from AWS Cost Explorer (with 24-hour delay), Phase 1.5 estimates current costs by collecting CloudWatch metrics and applying pricing calculations.

## Key Features

- **Real-Time Cost Visibility:** Estimate current AWS costs without waiting for Cost Explorer's 24-hour delay
- **Multi-Service Support:** EC2, Lambda, DynamoDB, S3, and RDS cost estimation
- **Confidence Intervals:** Statistical confidence bounds for estimation accuracy
- **Pricing Cache:** 24-hour pricing data cache to minimize API calls
- **Free Tier Compliant:** Designed to operate within AWS Free Tier limits
- **Backward Compatible:** Phase 1 functionality remains unchanged

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway                              │
│  Phase 1: /api/cost-data/fetch, /api/cost-data             │
│  Phase 1.5: /api/cost-estimation/current                    │
│             /api/cost-estimation/service/{service}          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Function                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  CloudWatch Metrics Collector                          │ │
│  │  - Collect EC2, Lambda, DynamoDB, S3, RDS metrics      │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Cost Estimator                                        │ │
│  │  - Apply pricing formulas to metrics                   │ │
│  │  - Calculate confidence intervals                      │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Pricing Manager                                       │ │
│  │  - Fetch and cache AWS pricing data                    │ │
│  │  - 24-hour TTL for pricing cache                       │ │
│  └────────────────────────────────────────────────────────┘ │
└────┬────────────────────┬────────────────────┬─────────────┘
     │                    │                    │
     ▼                    ▼                    ▼
┌──────────┐      ┌──────────────┐    ┌─────────────────┐
│CloudWatch│      │   DynamoDB   │    │  Pricing API    │
│ Metrics  │      │  (Phase 1)   │    │                 │
└──────────┘      └──────────────┘    └─────────────────┘
```

## Supported Services

| Service | Metrics Collected | Cost Factors |
|---------|-------------------|--------------|
| **EC2** | CPUUtilization, NetworkIn/Out, DiskReadBytes | Instance type, running hours, data transfer |
| **Lambda** | Invocations, Duration, Errors | Invocations, duration, memory allocation |
| **DynamoDB** | ConsumedReadCapacityUnits, ConsumedWriteCapacityUnits | Read/write capacity units |
| **S3** | NumberOfObjects, BucketSizeBytes | Storage size, request counts |
| **RDS** | DatabaseConnections, ReadIOPS, WriteIOPS | Instance type, running hours, storage |

## API Endpoints

### GET /api/cost-estimation/current

Estimate current costs for all supported services.

**Query Parameters:**
- `hours` (optional): Time range in hours (default: 1, max: 168)

**Example:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/current?hours=24"
```

**Response:**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "ec2",
      "estimated_cost": 0.5616,
      "currency": "USD",
      "confidence_lower": 0.5280,
      "confidence_upper": 0.5952,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-20T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 288
    }
  ],
  "total_cost": 2.0520,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "24 hours"
}
```

### GET /api/cost-estimation/service/{service}

Estimate current costs for a specific service.

**Path Parameters:**
- `service`: Service name (ec2, lambda, dynamodb, s3, rds)

**Query Parameters:**
- `hours` (optional): Time range in hours (default: 1, max: 168)

**Example:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/service/ec2?hours=6"
```

## Documentation

- **[Requirements](./requirements.md)** - Detailed requirements specification
- **[Design](./design.md)** - System design and architecture
- **[Implementation Summary](./implementation-summary.md)** - Implementation details and decisions
- **[Infrastructure Updates](./infrastructure-updates.md)** - CDK infrastructure changes
- **[API Examples](../../API_EXAMPLES.md)** - Complete API usage examples

## Implementation Status

✅ **Completed** - All Phase 1.5 features implemented and tested

- ✅ CloudWatch metrics collection for all supported services
- ✅ Cost estimation algorithms with confidence intervals
- ✅ Pricing data management with 24-hour caching
- ✅ API endpoints with authentication
- ✅ Error handling and retry logic
- ✅ Comprehensive test suite (236 tests, 89% coverage)
- ✅ Infrastructure deployment via CDK
- ✅ Phase 1 backward compatibility verified

## Testing

**Test Coverage:** 89% (236 tests passing)

**Test Types:**
- **Unit Tests:** 134 tests for individual components
- **Property-Based Tests:** 15 properties validated with Hypothesis (100+ iterations each)
- **Integration Tests:** 87 tests for end-to-end flows

**Key Properties Tested:**
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

## Cost Analysis

Phase 1.5 operates within AWS Free Tier:

| Service | Monthly Usage | Free Tier Limit | Cost |
|---------|---------------|-----------------|------|
| CloudWatch API | ~50,000 requests | 1M requests | $0.00 |
| Pricing API | ~100 requests | N/A | ~$0.01 |
| DynamoDB | +10 MB storage | 25 GB | $0.00 |
| Lambda | +1,000 invocations | 1M invocations | $0.00 |

**Total Monthly Cost:** ~$0.01

## Performance

- **Single Service Query:** < 2 seconds
- **All Services Query:** < 5 seconds
- **Pricing Cache Hit Rate:** > 95%
- **CloudWatch API Efficiency:** Batched requests minimize API calls

## Getting Started

1. **Deploy Infrastructure:**
   ```bash
   cd infrastructure
   cdk deploy
   ```

2. **Test Phase 1.5 Endpoints:**
   ```bash
   export API_KEY="your-api-key"
   export API_ENDPOINT="https://your-api-id.execute-api.us-east-1.amazonaws.com/prod"
   
   # Get current estimates
   curl -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/cost-estimation/current"
   ```

3. **Monitor Logs:**
   ```bash
   aws logs tail /aws/lambda/costguard-cost-data-handler --follow
   ```

## Limitations

### Estimation vs. Actual Costs
- **Not Real-Time Actual Costs:** Phase 1.5 provides cost **estimation** based on CloudWatch metrics, not actual billing data. Actual costs from AWS Cost Explorer have a 24-hour delay.
- **Estimation Accuracy:** Cost estimates have ±6% confidence intervals. Actual costs may differ due to:
  - Complex pricing models (tiered pricing, reserved instances, spot instances)
  - Data transfer costs not fully captured in metrics
  - Regional pricing variations
  - Discounts and credits not reflected in metrics

### Metric Collection Limitations
- **5-Minute Delay:** CloudWatch metrics have a 1-5 minute delay. The system uses 5-minute aggregation periods for efficiency.
- **Metric Availability:** New resources may not have metrics available immediately. Wait 5-10 minutes after resource creation.
- **Limited Services:** Currently supports only EC2, Lambda, DynamoDB, S3, and RDS. Other services require Phase 1 historical data.

### Pricing Data
- **24-Hour Cache:** Pricing data is cached for 24 hours to minimize API costs. Pricing changes may not be reflected immediately.
- **Regional Variations:** Pricing is fetched per region. Multi-region deployments require separate queries.
- **Complex Pricing:** Some services have complex pricing models (e.g., tiered storage, reserved capacity) that may not be fully captured.

### Performance
- **Response Time:** Single service queries: <2 seconds. All services: <5 seconds. Large time ranges may take longer.
- **Cold Starts:** Lambda cold starts can add 1-2 seconds to response time.
- **Metric Collection:** Collecting metrics for all services can take several seconds.

### Free Tier Considerations
- **CloudWatch API:** 1M requests/month free tier. The system uses ~50,000 requests/month for typical usage.
- **Pricing API:** No free tier. Costs ~$0.0001 per request. 24-hour caching reduces calls by 95%.
- **DynamoDB:** Pricing cache storage within 25 GB free tier.

## Troubleshooting

### Issue: Estimation returns zero cost

**Causes:**
- No resources running during time period
- CloudWatch metrics not available yet (new resources)
- Pricing data not cached

**Solutions:**
- Verify resources are running
- Wait 5-10 minutes for metrics to populate
- Check CloudWatch Logs for pricing errors

### Issue: High latency

**Causes:**
- Large time range (many metrics to process)
- Cold start (Lambda initialization)
- Pricing data refresh in progress

**Solutions:**
- Use smaller time ranges (1-6 hours)
- Implement result caching
- Pre-warm Lambda with scheduled invocations

## Future Enhancements

Potential improvements for future phases:

- **Additional Services:** CloudFront, API Gateway, ECS, EKS
- **Cost Forecasting:** Predict future costs based on trends
- **Anomaly Detection:** Alert on unusual cost spikes
- **Multi-Region Support:** Aggregate costs across regions
- **Cost Optimization Recommendations:** Suggest ways to reduce costs
- **Dashboard UI:** Visual cost monitoring interface

## References

- **Phase 1 Documentation:** [../phase1-cost-pipeline/](../phase1-cost-pipeline/)
- **API Examples:** [../../API_EXAMPLES.md](../../API_EXAMPLES.md)
- **Competition Docs:** [../../competition/](../../competition/)
- **Submission Guide:** [../../submission/SUBMISSION-GUIDE.md](../../submission/SUBMISSION-GUIDE.md)

## Support

For issues or questions:
1. Check CloudWatch Logs: `/aws/lambda/costguard-cost-data-handler`
2. Review test suite: `tests/unit/` and `tests/integration/`
3. Consult design document: `./design.md`
4. Check requirements: `./requirements.md`
