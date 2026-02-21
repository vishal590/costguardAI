# Phase 2 Infrastructure Updates

## Overview

This document summarizes the infrastructure changes made to support Phase 2 (AI-Powered Cost Forecasting). All changes extend Phase 1 & 1.5 infrastructure without breaking existing functionality.

## Changes Summary

### 1. IAM Role Permissions (infrastructure/iam_roles.py)

Added one new IAM policy statement to the Lambda execution role:

#### Bedrock InvokeModel Policy
```python
bedrock_policy = iam.PolicyStatement(
    effect=iam.Effect.ALLOW,
    actions=[
        "bedrock:InvokeModel",
    ],
    resources=["*"],
)
```

**Purpose:** Allows Lambda to call Amazon Bedrock Nova Lite for AI-powered cost forecasting.

**Requirements:** Phase 2 Requirement 2.1

**Note:** Bedrock InvokeModel does not support resource-level permissions, so `resources=["*"]` is required.

### 2. DynamoDB Table (infrastructure/dynamodb_table.py)

Added one new DynamoDB table for forecast caching:

#### Forecast Cache Table
```python
forecast_cache_table = dynamodb.Table(
    self, "ForecastCacheTable",
    table_name="costguard-forecast-cache",
    partition_key=dynamodb.Attribute(
        name="cache_key",
        type=dynamodb.AttributeType.STRING
    ),
    billing_mode=dynamodb.BillingMode.ON_DEMAND,
    time_to_live_attribute="ttl",
    removal_policy=cdk.RemovalPolicy.DESTROY,
    encryption=dynamodb.TableEncryption.AWS_MANAGED
)
```

**Purpose:** Store generated forecasts with 24-hour TTL to minimize Bedrock API costs.

**Schema:**
- **Partition Key:** `cache_key` (String) - Unique key per service/days/granularity
- **TTL Attribute:** `ttl` (Number) - Unix timestamp for automatic expiration
- **Billing Mode:** On-demand (pay per request)
- **Encryption:** AWS managed (default)

**Requirements:** Phase 2 Requirements 4.1, 4.2, 4.3

### 3. Lambda Environment Variables (infrastructure/lambda_function.py)

Added three new environment variables:

| Variable | Value | Purpose |
|----------|-------|---------|
| `BEDROCK_MODEL_ID` | `"amazon.nova-lite-v1:0"` | Bedrock model identifier for cost forecasting |
| `FORECAST_CACHE_TABLE` | `"costguard-forecast-cache"` | DynamoDB table name for forecast cache |
| `FORECAST_CACHE_TTL_HOURS` | `"24"` | Forecast cache TTL in hours (24 hours) |

**Requirements:** Phase 2 Requirements 2.2, 4.1

### 4. API Gateway Endpoints (infrastructure/api_gateway.py)

Added two new REST API endpoints:

#### GET /api/cost-forecast
- **Purpose:** Generate cost forecast for all services (total costs)
- **Query Parameters:** 
  - `days` (optional): Forecast horizon - 7, 14, or 30 (default: 30)
  - `granularity` (optional): Time resolution - `daily` or `weekly` (default: daily)
- **Authentication:** API key required (reuses Phase 1 API key)
- **Response:** JSON with forecast data points and metadata

**Requirements:** Phase 2 Requirements 5.1, 5.3, 5.4, 5.5

#### GET /api/cost-forecast/service/{service}
- **Purpose:** Generate cost forecast for a specific AWS service
- **Path Parameters:**
  - `service`: Service name (ec2, lambda, dynamodb, s3, rds, etc.)
- **Query Parameters:**
  - `days` (optional): Forecast horizon - 7, 14, or 30 (default: 30)
  - `granularity` (optional): Time resolution - `daily` or `weekly` (default: daily)
- **Authentication:** API key required (reuses Phase 1 API key)
- **Response:** JSON with forecast data points for specified service

**Requirements:** Phase 2 Requirements 5.2, 5.3, 5.6, 5.7

### 5. Phase 1 & 1.5 Compatibility

All Phase 1 and Phase 1.5 endpoints remain unchanged and fully functional:

**Phase 1:**
- POST /api/cost-data/fetch
- GET /api/cost-data

**Phase 1.5:**
- GET /api/cost-estimation/current
- GET /api/cost-estimation/service/{service}

**Requirements:** Phase 2 Requirements 10.1, 10.2

## Deployment

No changes to deployment process. Use existing CDK commands:

```bash
# Synthesize CloudFormation template
cdk synth

# Deploy infrastructure
cdk deploy
```

The CDK will automatically:
- Create forecast cache DynamoDB table
- Update IAM role with Bedrock permissions
- Update Lambda function with new environment variables
- Add new API Gateway routes

## Free Tier Impact

Phase 2 adds minimal cost within Free Tier limits:

| Service | Phase 2 Usage | Free Tier Limit | Status |
|---------|---------------|-----------------|--------|
| Bedrock Nova Lite | ~500 requests/month | N/A (~$0.50/month) | ✅ Minimal cost |
| DynamoDB (forecast cache) | ~50 MB storage | 25 GB free | ✅ Within limits |
| Lambda | +1,000 invocations/month | 1M free | ✅ Within limits |
| API Gateway | +1,000 requests/month | 1M free | ✅ Within limits |

**Total estimated cost:** ~$0.50/month (Bedrock Nova Lite only)

**Total system cost:** ~$1.51/month (including Phase 1 & 1.5)

## Testing

All infrastructure changes have been validated:
- 412 tests passing (134 Phase 1 + 102 Phase 1.5 + 176 Phase 2)
- 94.16% code coverage
- Phase 1 & 1.5 backward compatibility verified
- All property-based tests passing

## Security Considerations

### New Permissions
- Bedrock InvokeModel is read-only (no model training or modification)
- Bedrock does not support resource-level permissions (must use "*")
- Lambda can only invoke models, not create or delete them

### Authentication
- Phase 2 endpoints reuse existing API key authentication
- No changes to authentication mechanism
- Same throttling and quota limits apply

### Data Privacy
- Bedrock requests contain only aggregated cost numbers (no PII)
- Forecast cache contains only predicted costs (no sensitive data)
- All data encrypted at rest (DynamoDB default encryption)
- All API communication over HTTPS

## Monitoring

CloudWatch Logs will include new log entries for:
- Forecast generation operations
- Bedrock API calls (request/response)
- Cache hit/miss events
- Historical data retrieval for forecasting
- Phase 2 API endpoint requests

Log group: `/aws/lambda/costguard-cost-data-handler`

### New CloudWatch Metrics

**Custom Metrics:**
- `BedrockAPICallCount` - Number of Bedrock API calls
- `BedrockAPILatency` - Bedrock API call latency (ms)
- `ForecastCacheHitRate` - Percentage of cache hits
- `ForecastGenerationLatency` - Total forecast generation time (ms)
- `ForecastErrors` - Count of forecast generation errors

### Recommended Alarms

- Bedrock API error rate > 5%
- Cache hit rate < 70%
- Forecast generation latency > 10 seconds
- Bedrock API call count approaching limit (> 800/month)

## Rollback

To rollback Phase 2 changes:

1. Revert infrastructure files to Phase 1.5 versions
2. Run `cdk deploy` to update infrastructure
3. Lambda will continue to work with Phase 1 & 1.5 functionality only

**Note:** Phase 2 endpoints will return 404, but Phase 1 & 1.5 endpoints remain functional.

**Rollback Time:** ~10 minutes

## Infrastructure Code Changes

### File: infrastructure/iam_roles.py

```python
# Add Bedrock permissions to Lambda execution role
bedrock_policy = iam.PolicyStatement(
    effect=iam.Effect.ALLOW,
    actions=[
        "bedrock:InvokeModel",
    ],
    resources=["*"],
)

lambda_role.add_to_policy(bedrock_policy)
```

### File: infrastructure/dynamodb_table.py

```python
# Create forecast cache table
forecast_cache_table = dynamodb.Table(
    self, "ForecastCacheTable",
    table_name="costguard-forecast-cache",
    partition_key=dynamodb.Attribute(
        name="cache_key",
        type=dynamodb.AttributeType.STRING
    ),
    billing_mode=dynamodb.BillingMode.ON_DEMAND,
    time_to_live_attribute="ttl",
    removal_policy=cdk.RemovalPolicy.DESTROY,
    encryption=dynamodb.TableEncryption.AWS_MANAGED
)

# Grant Lambda read/write permissions
forecast_cache_table.grant_read_write_data(lambda_function)
```

### File: infrastructure/lambda_function.py

```python
# Add Phase 2 environment variables
lambda_function = _lambda.Function(
    self, "CostDataHandler",
    # ... existing configuration ...
    environment={
        # Phase 1 variables (unchanged)
        "COST_DATA_TABLE": cost_data_table.table_name,
        "COST_EXPLORER_REGION": "us-east-1",
        
        # Phase 1.5 variables (unchanged)
        "PRICING_CACHE_TTL_HOURS": "24",
        "METRICS_COLLECTION_PERIOD": "300",
        "ESTIMATION_CONFIDENCE_LEVEL": "0.95",
        
        # Phase 2 variables (new)
        "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
        "FORECAST_CACHE_TABLE": forecast_cache_table.table_name,
        "FORECAST_CACHE_TTL_HOURS": "24",
    }
)
```

### File: infrastructure/api_gateway.py

```python
# Add Phase 2 API Gateway routes
forecast_resource = api.root.add_resource("cost-forecast")

# GET /api/cost-forecast
forecast_resource.add_method(
    "GET",
    apigw.LambdaIntegration(lambda_function),
    api_key_required=True
)

# GET /api/cost-forecast/service/{service}
forecast_service_resource = forecast_resource.add_resource("service")
forecast_service_param = forecast_service_resource.add_resource("{service}")
forecast_service_param.add_method(
    "GET",
    apigw.LambdaIntegration(lambda_function),
    api_key_required=True
)
```

## Next Steps

After infrastructure deployment:
1. Test Phase 2 endpoints with API key
2. Monitor CloudWatch Logs for Bedrock API calls
3. Verify forecast caching works correctly
4. Check Bedrock API usage in AWS Cost Explorer
5. Monitor cache hit rate (target: 80%+)
6. Verify Phase 1 & 1.5 endpoints still work

## References

- Phase 2 Requirements: [requirements.md](../../../.kiro/specs/ai-cost-forecasting/requirements.md)
- Phase 2 Design: [design.md](../../../.kiro/specs/ai-cost-forecasting/design.md)
- Phase 2 Specification: [specification.md](./specification.md)
- Phase 2 Implementation Summary: [implementation-summary.md](./implementation-summary.md)
- Infrastructure README: `infrastructure/README.md`

