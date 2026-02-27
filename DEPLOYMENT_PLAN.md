# CostGuard AI - Phase-by-Phase Deployment Plan

**Goal:** Deploy Phases 1-6 to AWS in sequential order, validating each phase before moving to the next.

**Timeline:** 2-4 hours per phase = 12-24 hours total

---

## Prerequisites

Before starting deployment:

1. **AWS CLI Setup**
   ```bash
   # Install AWS CLI (if not installed)
   # Windows: Download from https://aws.amazon.com/cli/
   
   # Configure AWS credentials
   aws configure
   # Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output format (json)
   ```

2. **AWS CDK Setup**
   ```bash
   # Install Node.js (required for CDK)
   # Download from https://nodejs.org/
   
   # Install AWS CDK globally
   npm install -g aws-cdk
   
   # Verify installation
   cdk --version
   ```

3. **Python Environment**
   ```bash
   # Activate virtual environment
   .\venv\Scripts\Activate.ps1
   
   # Install CDK dependencies
   cd infrastructure
   pip install -r requirements.txt
   cd ..
   ```

4. **Bootstrap CDK (First Time Only)**
   ```bash
   cd infrastructure
   cdk bootstrap aws://ACCOUNT-ID/us-east-1
   cd ..
   ```

---

## Phase 1: Historical Cost Data Pipeline

**Status:** Code Complete ✅ | Infrastructure Ready ✅ | Deployment Pending ⏸️

### What Gets Deployed

1. **DynamoDB Table:** `costguard-cost-data`
   - Partition key: `pk` (String)
   - Sort key: `sk` (String)
   - Billing: On-demand
   - TTL: Enabled on `ttl` attribute

2. **Lambda Function:** `CostGuardLambda`
   - Runtime: Python 3.11
   - Memory: 512 MB
   - Timeout: 15 minutes
   - Handler: `src.lambda_handler.handler`

3. **IAM Role:** Lambda execution role with:
   - Cost Explorer read access (`ce:GetCostAndUsage`)
   - DynamoDB read/write access
   - CloudWatch Logs access

4. **API Gateway:** REST API with endpoints:
   - `POST /api/fetch` - Fetch cost data from Cost Explorer
   - `GET /api/cost-data` - Query stored cost data

### Deployment Steps

```bash
# 1. Navigate to infrastructure directory
cd infrastructure

# 2. Synthesize CloudFormation template (verify no errors)
cdk synth

# 3. Deploy Phase 1 infrastructure
cdk deploy --require-approval never

# 4. Note the outputs (API Gateway URL, Lambda ARN, DynamoDB table name)
# Save these for testing

# 5. Return to project root
cd ..
```

### Validation

```bash
# Test Phase 1 endpoints
# Replace <API_URL> with the API Gateway URL from deployment output

# Test 1: Fetch cost data
curl -X POST <API_URL>/api/fetch \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2026-01-01", "end_date": "2026-02-01", "granularity": "DAILY"}'

# Test 2: Query stored data
curl -X GET "<API_URL>/api/cost-data?start_date=2026-01-01&end_date=2026-02-01"

# Verify DynamoDB table has data
aws dynamodb scan --table-name costguard-cost-data --limit 5
```

### Success Criteria

- ✅ API Gateway returns 200 status
- ✅ Cost data is fetched from Cost Explorer
- ✅ Data is stored in DynamoDB
- ✅ Query endpoint returns stored data
- ✅ No errors in CloudWatch Logs

### Estimated Cost

- **Monthly:** ~$1.00 (Cost Explorer API calls)
- **Free Tier:** DynamoDB, Lambda, API Gateway all within free tier

---

## Phase 1.5: Near-Real-Time Cost Estimation

**Status:** Code Complete ✅ | Infrastructure Ready ✅ | Deployment Pending ⏸️

### What Gets Deployed

1. **No new DynamoDB tables** (reuses Phase 1 table for caching)

2. **Lambda Updates:**
   - Add Phase 1.5 handler code
   - Add environment variables for pricing API

3. **IAM Updates:**
   - Add Pricing API permissions (`pricing:GetProducts`)
   - Add CloudWatch metrics read access

4. **API Gateway Updates:**
   - `GET /api/cost-estimation/current` - Current cost estimate
   - `GET /api/cost-estimation/service/{service}` - Service-specific estimate

### Deployment Steps

```bash
cd infrastructure

# Update CDK stack with Phase 1.5 resources
cdk diff  # Review changes

# Deploy Phase 1.5 updates
cdk deploy --require-approval never

cd ..
```

### Validation

```bash
# Test Phase 1.5 endpoints

# Test 1: Current cost estimation
curl -X GET "<API_URL>/api/cost-estimation/current"

# Test 2: Service-specific estimation
curl -X GET "<API_URL>/api/cost-estimation/service/ec2"

# Test 3: Verify Phase 1 still works (backward compatibility)
curl -X GET "<API_URL>/api/cost-data?start_date=2026-01-01&end_date=2026-02-01"
```

### Success Criteria

- ✅ Cost estimation endpoints return 200 status
- ✅ Real-time estimates are calculated from CloudWatch metrics
- ✅ Pricing data is cached
- ✅ Phase 1 endpoints still work (backward compatibility)

### Estimated Cost

- **Monthly:** ~$0.01 (Pricing API calls)

---

## Phase 2: AI-Powered Cost Forecasting

**Status:** Code Complete ✅ | Infrastructure Ready ✅ | Deployment Pending ⏸️

### What Gets Deployed

1. **DynamoDB Table:** `costguard-forecast-cache`
   - Partition key: `cache_key` (String)
   - TTL: Enabled on `ttl` attribute
   - Billing: On-demand

2. **Lambda Updates:**
   - Add Phase 2 handler code
   - Add Bedrock client integration
   - Add environment variables:
     - `BEDROCK_MODEL_ID=amazon.nova-lite-v1:0`
     - `FORECAST_CACHE_TABLE=costguard-forecast-cache`
     - `FORECAST_CACHE_TTL_HOURS=24`

3. **IAM Updates:**
   - Add Bedrock permissions (`bedrock:InvokeModel`)
   - Add DynamoDB access for forecast cache table

4. **API Gateway Updates:**
   - `GET /api/cost-forecast` - Generate cost forecast
   - `GET /api/cost-forecast/service/{service}` - Service-specific forecast

### Deployment Steps

```bash
cd infrastructure

# Update CDK stack with Phase 2 resources
cdk diff  # Review changes

# Deploy Phase 2 updates
cdk deploy --require-approval never

cd ..
```

### Validation

```bash
# Test Phase 2 endpoints

# Test 1: Generate 7-day forecast
curl -X GET "<API_URL>/api/cost-forecast?days=7&granularity=daily"

# Test 2: Service-specific forecast
curl -X GET "<API_URL>/api/cost-forecast/service/ec2?days=14"

# Test 3: Verify cache hit (run same query twice, second should be faster)
time curl -X GET "<API_URL>/api/cost-forecast?days=7"
time curl -X GET "<API_URL>/api/cost-forecast?days=7"

# Test 4: Verify Phase 1 & 1.5 still work
curl -X GET "<API_URL>/api/cost-data?start_date=2026-01-01&end_date=2026-02-01"
curl -X GET "<API_URL>/api/cost-estimation/current"
```

### Success Criteria

- ✅ Forecast endpoints return 200 status
- ✅ Bedrock generates forecasts with confidence intervals
- ✅ Forecasts are cached (second request is faster)
- ✅ Phase 1 & 1.5 endpoints still work

### Estimated Cost

- **Monthly:** ~$0.50 (Bedrock API calls, target <500 calls with 80%+ cache hit rate)

---

## Phase 3: Automated Cost Prevention

**Status:** Code Complete ✅ | Infrastructure Ready ✅ | Deployment Pending ⏸️

### What Gets Deployed

1. **DynamoDB Tables:**
   - `costguard-prevention-config` - Prevention configuration
   - `costguard-resource-inventory` - Resource inventory
   - `costguard-prevention-audit` - Action audit log
   - `costguard-approval-requests` - Approval tracking

2. **SNS Topics:**
   - `costguard-prevention-warnings` - Budget threshold warnings
   - `costguard-prevention-actions` - Prevention action notifications
   - `costguard-prevention-errors` - Error notifications

3. **EventBridge Schedule:**
   - Rule: `costguard-budget-monitor`
   - Schedule: Every 5 minutes
   - Target: CostGuardLambda

4. **Lambda Updates:**
   - Add Phase 3 handler code
   - Add environment variables:
     - `PREVENTION_ENABLED=false` (disabled by default for safety)
     - `DRY_RUN_MODE=true` (dry run by default)
     - `APPROVAL_REQUIRED=true` (require approval by default)

5. **IAM Updates:**
   - Add Budgets API permissions
   - Add EC2/RDS/Lambda/etc management permissions
   - Add SNS publish permissions
   - Add EventBridge permissions

6. **API Gateway Updates:**
   - `GET /api/prevention/status` - Prevention system status
   - `POST /api/prevention/enable` - Enable prevention
   - `POST /api/prevention/disable` - Disable prevention
   - `GET /api/prevention/resources` - List discovered resources
   - `POST /api/prevention/rollback` - Rollback an action
   - `GET /api/prevention/history` - Action history

### Deployment Steps

```bash
cd infrastructure

# Update CDK stack with Phase 3 resources
cdk diff  # Review changes (will be large)

# Deploy Phase 3 updates
cdk deploy --require-approval never

# Subscribe to SNS topics for notifications
aws sns subscribe --topic-arn <WARNINGS_TOPIC_ARN> --protocol email --notification-endpoint your-email@example.com
aws sns subscribe --topic-arn <ACTIONS_TOPIC_ARN> --protocol email --notification-endpoint your-email@example.com
aws sns subscribe --topic-arn <ERRORS_TOPIC_ARN> --protocol email --notification-endpoint your-email@example.com

cd ..
```

### Validation

```bash
# Test Phase 3 endpoints

# Test 1: Check prevention status
curl -X GET "<API_URL>/api/prevention/status"

# Test 2: List discovered resources
curl -X GET "<API_URL>/api/prevention/resources"

# Test 3: View action history (should be empty initially)
curl -X GET "<API_URL>/api/prevention/history"

# Test 4: Verify Phase 1, 1.5, 2 still work
curl -X GET "<API_URL>/api/cost-data?start_date=2026-01-01&end_date=2026-02-01"
curl -X GET "<API_URL>/api/cost-estimation/current"
curl -X GET "<API_URL>/api/cost-forecast?days=7"
```

### Safety Configuration

**IMPORTANT:** Phase 3 is deployed with safety-first defaults:
- `PREVENTION_ENABLED=false` - System is disabled
- `DRY_RUN_MODE=true` - Actions are logged but not executed
- `APPROVAL_REQUIRED=true` - All actions require approval

**To enable prevention (after 24-48 hours of monitoring):**
```bash
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables={PREVENTION_ENABLED=true,DRY_RUN_MODE=false,APPROVAL_REQUIRED=true}
```

### Success Criteria

- ✅ Prevention endpoints return 200 status
- ✅ Resources are discovered and inventoried
- ✅ EventBridge triggers budget monitoring every 5 minutes
- ✅ SNS notifications are received
- ✅ Dry run mode logs planned actions without executing
- ✅ Phase 1, 1.5, 2 endpoints still work

### Estimated Cost

- **Monthly:** ~$0.00 (within free tier)

---

## Phase 4: AI Cost Advisor

**Status:** Code Complete ✅ | Infrastructure Pending ⏸️ | Deployment Pending ⏸️

### What Gets Deployed

1. **DynamoDB Tables:**
   - `costguard-advisor-conversation-history` - Conversation history
   - `costguard-advisor-cache` - Response cache

2. **Lambda Updates:**
   - Add Phase 4 handler code
   - Add Bedrock advisor client
   - Add environment variables:
     - `BEDROCK_MODEL_ID=amazon.nova-lite-v1:0`
     - `ADVISOR_CACHE_TABLE=costguard-advisor-cache`
     - `ADVISOR_CACHE_TTL_HOURS=24`
     - `ADVISOR_CACHE_HIT_RATE_TARGET=40`

3. **IAM Updates:**
   - Bedrock permissions already added in Phase 2
   - Add DynamoDB access for advisor tables

4. **API Gateway Updates:**
   - `POST /api/advisor/query` - Submit natural language query
   - `GET /api/advisor/history` - Get conversation history
   - `DELETE /api/advisor/history` - Clear conversation history
   - `GET /api/advisor/suggestions` - Get proactive insights

### Deployment Steps

```bash
cd infrastructure

# Update CDK stack with Phase 4 resources
cdk diff  # Review changes

# Deploy Phase 4 updates
cdk deploy --require-approval never

cd ..
```

### Validation

```bash
# Test Phase 4 endpoints

# Test 1: Submit natural language query
curl -X POST "<API_URL>/api/advisor/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What were my costs last month?", "user_id": "test-user", "session_id": "test-session"}'

# Test 2: Get conversation history
curl -X GET "<API_URL>/api/advisor/history?session_id=test-session"

# Test 3: Get proactive insights
curl -X GET "<API_URL>/api/advisor/suggestions?user_id=test-user"

# Test 4: Test cache (run same query twice)
time curl -X POST "<API_URL>/api/advisor/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What were my costs last month?", "user_id": "test-user", "session_id": "test-session-2"}'

# Test 5: Verify Phase 1-3 still work
curl -X GET "<API_URL>/api/cost-data?start_date=2026-01-01&end_date=2026-02-01"
curl -X GET "<API_URL>/api/cost-forecast?days=7"
curl -X GET "<API_URL>/api/prevention/status"
```

### Success Criteria

- ✅ Advisor endpoints return 200 status
- ✅ Natural language queries are processed
- ✅ Bedrock generates context-aware responses
- ✅ Conversation history is maintained
- ✅ Responses are cached (40%+ hit rate target)
- ✅ Phase 1-3 endpoints still work

### Estimated Cost

- **Monthly:** ~$0.50 (Bedrock API calls, target <500 calls with 40%+ cache hit rate)

---

## Phase 5: Multi-Account Cost Management

**Status:** Code Complete ✅ | Infrastructure Ready ✅ | Deployment Pending ⏸️

### What Gets Deployed

1. **DynamoDB Tables:**
   - `costguard-organizations` - AWS Organizations data
   - `costguard-cross-account-costs` - Cross-account cost data
   - `costguard-allocation-rules` - Cost allocation rules
   - `costguard-chargeback-reports` - Chargeback/showback reports

2. **Lambda Updates:**
   - Add Phase 5 handler code
   - Add multi-account integration
   - Add environment variables for Organizations API

3. **IAM Updates:**
   - Add Organizations API permissions
   - Add cross-account assume role permissions

4. **API Gateway Updates:**
   - 15+ new multi-account endpoints

### Deployment Steps

```bash
cd infrastructure

# Update CDK stack with Phase 5 resources
cdk diff  # Review changes

# Deploy Phase 5 updates
cdk deploy --require-approval never

cd ..
```

### Validation

```bash
# Test Phase 5 endpoints (if multi-account setup exists)

# Test 1: List organization accounts
curl -X GET "<API_URL>/api/multi-account/accounts"

# Test 2: Get consolidated costs
curl -X GET "<API_URL>/api/multi-account/costs?start_date=2026-01-01&end_date=2026-02-01"

# Test 3: Verify Phase 1-4 still work
curl -X GET "<API_URL>/api/cost-data?start_date=2026-01-01&end_date=2026-02-01"
curl -X POST "<API_URL>/api/advisor/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me costs across all accounts", "user_id": "test-user"}'
```

### Success Criteria

- ✅ Multi-account endpoints return 200 status
- ✅ Organizations integration works (if configured)
- ✅ Cross-account cost collection works
- ✅ Phase 1-4 endpoints still work

### Estimated Cost

- **Monthly:** ~$0.50 (additional Cost Explorer API calls)

---

## Phase 6: AI/ML Workload Cost Management

**Status:** Code Complete ✅ | Infrastructure Ready ✅ | Deployment Pending ⏸️

### What Gets Deployed

1. **DynamoDB Tables:**
   - `costguard-gpu-workloads` - GPU workload tracking
   - `costguard-ml-metrics` - ML cost metrics

2. **Lambda Updates:**
   - Add Phase 6 handler code
   - Add GPU cost tracking
   - Add SageMaker/Bedrock integration

3. **IAM Updates:**
   - Add SageMaker permissions
   - Add EC2 GPU instance permissions

4. **API Gateway Updates:**
   - 20+ new GPU/ML cost endpoints

### Deployment Steps

```bash
cd infrastructure

# Update CDK stack with Phase 6 resources
cdk diff  # Review changes

# Deploy Phase 6 updates
cdk deploy --require-approval never

cd ..
```

### Validation

```bash
# Test Phase 6 endpoints

# Test 1: Get GPU cost summary
curl -X GET "<API_URL>/api/gpu/costs?start_date=2026-01-01&end_date=2026-02-01"

# Test 2: Get workload classification
curl -X GET "<API_URL>/api/gpu/workloads"

# Test 3: Get spot recommendations
curl -X GET "<API_URL>/api/gpu/spot-recommendations"

# Test 4: Verify Phase 1-5 still work
curl -X GET "<API_URL>/api/cost-data?start_date=2026-01-01&end_date=2026-02-01"
curl -X POST "<API_URL>/api/advisor/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are my GPU costs?", "user_id": "test-user"}'
```

### Success Criteria

- ✅ GPU cost endpoints return 200 status
- ✅ Workload classification works
- ✅ Spot recommendations are generated
- ✅ Phase 1-5 endpoints still work

### Estimated Cost

- **Monthly:** ~$0.50 (Cost Explorer + CloudWatch + Bedrock)

---

## Total System Cost After Full Deployment

```
Total Monthly Cost: ~$2.51
├── Phase 1: ~$1.00 (Cost Explorer API)
├── Phase 1.5: ~$0.01 (Pricing API)
├── Phase 2: ~$0.50 (Bedrock API)
├── Phase 3: ~$0.00 (within free tier)
├── Phase 4: ~$0.50 (Bedrock API)
├── Phase 5: ~$0.00 (within free tier)
└── Phase 6: ~$0.50 (Cost Explorer + CloudWatch + Bedrock)

Free Tier Usage:
├── Lambda: ~15,000 invocations/month (within 1M free tier)
├── API Gateway: ~3,000 requests/month (within 1M free tier)
├── DynamoDB: ~450 MB storage (within 25 GB free tier)
├── CloudWatch: ~75,000 API requests/month (within 1M free tier)
└── SNS: ~500 messages/month (within 1M free tier)
```

---

## Deployment Timeline

| Phase | Estimated Time | Cumulative Time |
|-------|---------------|-----------------|
| Prerequisites | 30 min | 30 min |
| Phase 1 | 2 hours | 2.5 hours |
| Phase 1.5 | 1 hour | 3.5 hours |
| Phase 2 | 2 hours | 5.5 hours |
| Phase 3 | 3 hours | 8.5 hours |
| Phase 4 | 2 hours | 10.5 hours |
| Phase 5 | 2 hours | 12.5 hours |
| Phase 6 | 2 hours | 14.5 hours |
| **Total** | **14.5 hours** | |

---

## Troubleshooting

**For detailed troubleshooting, see `DEPLOYMENT_TROUBLESHOOTING.md`**

This guide covers all issues encountered during deployment and their solutions, including:
- CDK recursive symlink issue
- CDK bootstrap requirements
- PowerShell curl alias issues
- Lambda runtime errors
- IAM user vs root user
- AWS region selection
- CDK lock file issues

### Quick Fixes

1. **CDK Bootstrap Error**
   ```
   Error: This stack uses assets, so the toolkit stack must be deployed
   ```
   **Solution:** Run `cdk bootstrap aws://ACCOUNT-ID/REGION`

2. **CDK Recursive Symlink Issue**
   ```
   Error: Path too long or "Could not find a part of the path"
   ```
   **Solution:** Delete `cdk.out` directory and ensure Lambda asset bundling excludes `infrastructure/*`, `cdk.out/*`, `.git/*`, etc. See `DEPLOYMENT_TROUBLESHOOTING.md` for details.

3. **IAM Permission Denied**
   ```
   Error: User is not authorized to perform: iam:CreateRole
   ```
   **Solution:** Ensure AWS credentials have admin permissions or required IAM permissions

4. **Lambda Deployment Package Too Large**
   ```
   Error: Unzipped size must be smaller than 262144000 bytes
   ```
   **Solution:** Use Lambda layers for large dependencies

5. **API Gateway 403 Forbidden**
   ```
   Error: Missing Authentication Token
   ```
   **Solution:** Check API Gateway URL and endpoint paths

6. **Bedrock Access Denied**
   ```
   Error: Could not resolve the foundation model from the model identifier
   ```
   **Solution:** Enable Bedrock model access in AWS Console (Bedrock > Model access)

### Rollback

If deployment fails or causes issues:

```bash
# Rollback to previous version
cd infrastructure
cdk deploy --rollback

# Or destroy all resources (WARNING: deletes all data)
cdk destroy
```

---

## Next Steps After Deployment

1. **Monitor CloudWatch Logs**
   - Check `/aws/lambda/CostGuardLambda` for errors
   - Set up CloudWatch alarms for errors

2. **Test All Endpoints**
   - Run integration tests
   - Verify backward compatibility

3. **Enable Phase 3 Prevention (After 24-48 hours)**
   - Review dry run reports
   - Enable prevention with approval workflow
   - Monitor for 1 week before disabling approval

4. **Create Demo**
   - Take screenshots of API responses
   - Record video of system in action
   - Show GPU cost tracking (Phase 6 differentiator)

5. **Build Frontend** (Optional, 3-5 days)
   - Minimal React dashboard
   - Visualize costs, forecasts, GPU tracking

6. **Write Article** (2-3 days)
   - Publish by March 6 for early visibility
   - Highlight GPU cost tracking as differentiator

---

## Success Metrics

After full deployment, verify:

- ✅ All 36+ API endpoints working
- ✅ 1376 tests passing
- ✅ 87% code coverage
- ✅ ~$2.51/month cost (within budget)
- ✅ All phases backward compatible
- ✅ CloudWatch logs show no errors
- ✅ Demo-ready system

---

**Ready to start deployment? Let's begin with Phase 1!**
