# Phase 1.5 Infrastructure Updates

## Overview

This document summarizes the infrastructure changes made to support Phase 1.5 (Near-Real-Time Cost Estimation). All changes extend Phase 1 infrastructure without breaking existing functionality.

## Changes Summary

### 1. IAM Role Permissions (infrastructure/iam_roles.py)

Added two new IAM policy statements to the Lambda execution role:

#### CloudWatch Metrics Read Policy
```python
cloudwatch_metrics_policy = iam.PolicyStatement(
    effect=iam.Effect.ALLOW,
    actions=[
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
    ],
    resources=["*"],
)
```

**Purpose:** Allows Lambda to collect usage metrics from CloudWatch for cost estimation.

**Requirements:** Phase 1.5 Requirement 1.1

#### Pricing API Read Policy
```python
pricing_policy = iam.PolicyStatement(
    effect=iam.Effect.ALLOW,
    actions=[
        "pricing:GetProducts",
    ],
    resources=["*"],
)
```

**Purpose:** Allows Lambda to fetch current AWS pricing data for accurate cost calculations.

**Requirements:** Phase 1.5 Requirement 3.3

### 2. Lambda Environment Variables (infrastructure/lambda_function.py)

Added three new environment variables:

| Variable | Value | Purpose |
|----------|-------|---------|
| `PRICING_CACHE_TTL_HOURS` | `"24"` | Pricing data refresh interval (24 hours) |
| `METRICS_COLLECTION_PERIOD` | `"300"` | CloudWatch metrics aggregation period (5 minutes in seconds) |
| `ESTIMATION_CONFIDENCE_LEVEL` | `"0.95"` | Confidence interval for cost estimates (95%) |

**Requirements:** Phase 1.5 Requirements 3.2, 7.2

### 3. API Gateway Endpoints (infrastructure/api_gateway.py)

Added two new REST API endpoints:

#### GET /api/cost-estimation/current
- **Purpose:** Estimate current costs for all supported services
- **Query Parameters:** 
  - `hours` (optional): Time range in hours (default: 1, max: 168)
- **Authentication:** API key required (reuses Phase 1 API key)
- **Response:** JSON with cost estimates for EC2, Lambda, DynamoDB, S3, RDS

**Requirements:** Phase 1.5 Requirements 4.1, 4.2

#### GET /api/cost-estimation/service/{service}
- **Purpose:** Estimate current costs for a specific service
- **Path Parameters:**
  - `service`: Service name (ec2, lambda, dynamodb, s3, rds)
- **Query Parameters:**
  - `hours` (optional): Time range in hours (default: 1, max: 168)
- **Authentication:** API key required (reuses Phase 1 API key)
- **Response:** JSON with cost estimate for specified service

**Requirements:** Phase 1.5 Requirements 4.3, 4.4

### 4. Phase 1 Compatibility

All Phase 1 endpoints remain unchanged and fully functional:
- POST /api/cost-data/fetch
- GET /api/cost-data

**Requirements:** Phase 1.5 Requirement 5.4

## Deployment

No changes to deployment process. Use existing CDK commands:

```bash
# Synthesize CloudFormation template
cdk synth

# Deploy infrastructure
cdk deploy
```

The CDK will automatically update:
- IAM role with new permissions
- Lambda function with new environment variables
- API Gateway with new endpoints

## Free Tier Impact

Phase 1.5 adds minimal cost within Free Tier limits:

| Service | Phase 1.5 Usage | Free Tier Limit | Status |
|---------|-----------------|-----------------|--------|
| CloudWatch API | ~50,000 requests/month | 1M requests/month | ✅ Within limits |
| Pricing API | ~100 requests/month | N/A (~$0.01/month) | ✅ Minimal cost |
| DynamoDB | +10 MB storage | 25 GB free | ✅ Within limits |
| Lambda | +1,000 invocations/month | 1M free | ✅ Within limits |

**Total estimated cost:** $0.01/month (Pricing API only)

## Testing

All infrastructure changes have been validated:
- 236 tests passing (134 Phase 1 + 102 Phase 1.5)
- 89% code coverage
- Phase 1 backward compatibility verified
- All property-based tests passing

## Security Considerations

### New Permissions
- CloudWatch metrics are read-only (no write access)
- Pricing API is read-only (no write access)
- Both APIs don't support resource-level permissions (must use "*")

### Authentication
- Phase 1.5 endpoints reuse existing API key authentication
- No changes to authentication mechanism
- Same throttling and quota limits apply

## Monitoring

CloudWatch Logs will include new log entries for:
- Metric collection operations
- Pricing data fetches and cache operations
- Cost estimation calculations
- Phase 1.5 API endpoint requests

Log group: `/aws/lambda/costguard-cost-data-handler`

## Rollback

To rollback Phase 1.5 changes:

1. Revert infrastructure files to Phase 1 versions
2. Run `cdk deploy` to update infrastructure
3. Lambda will continue to work with Phase 1 functionality only

Note: Phase 1.5 endpoints will return 404, but Phase 1 endpoints remain functional.

## Next Steps

After infrastructure deployment:
1. Test Phase 1.5 endpoints with API key
2. Monitor CloudWatch Logs for errors
3. Verify pricing data caching works correctly
4. Check Free Tier usage in AWS Cost Explorer

## References

- Phase 1.5 Requirements: [requirements.md](./requirements.md)
- Phase 1.5 Design: [design.md](./design.md)
- Phase 1.5 Specification: [specification.md](./specification.md)
- Infrastructure README: `infrastructure/README.md`
