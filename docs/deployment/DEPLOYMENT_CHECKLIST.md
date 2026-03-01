# Phase 4 Deployment Checklist

**Keywords:** deployment, infrastructure, AWS, DynamoDB, Lambda, API Gateway, IAM, Bedrock, integration testing, monitoring, rollback, Phase 4, checklist, step-by-step, production deployment, CDK, CloudFormation

**Status:** ✅ Code Complete - Ready for AWS Deployment  
**Estimated Time:** 2-4 hours for infrastructure + 4-6 hours for integration testing  
**Last Updated:** January 2026

**Related Documentation:**
- [Phase 4 Infrastructure Guide](docs/technical/phase4-ai-advisor/infrastructure-updates.md) - Detailed deployment instructions
- [Phase 4 Status](docs/PHASE4_STATUS.md) - Current implementation status
- [API Examples](docs/API_EXAMPLES.md) - API usage examples for testing
- [Project Status](docs/PROJECT_STATUS.md) - Overall project status

---

## Prerequisites

- [ ] AWS account with appropriate permissions
- [ ] AWS CLI configured with credentials
- [ ] Access to Amazon Bedrock (Nova Lite model)
- [ ] CDK installed (if using CDK deployment)
- [ ] All 971 tests passing locally ✅ (Already verified)

---

## Task 17: Infrastructure Deployment

### Step 1: Create DynamoDB Tables (15 minutes)

#### Table 1: advisor-conversation-history
```bash
aws dynamodb create-table \
  --table-name advisor-conversation-history \
  --attribute-definitions \
    AttributeName=session_id,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
  --key-schema \
    AttributeName=session_id,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Project,Value=CostGuardAI Key=Phase,Value=4
```

#### Table 2: advisor-cache
```bash
aws dynamodb create-table \
  --table-name advisor-cache \
  --attribute-definitions \
    AttributeName=query_hash,AttributeType=S \
  --key-schema \
    AttributeName=query_hash,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --time-to-live-specification \
    Enabled=true,AttributeName=ttl \
  --tags Key=Project,Value=CostGuardAI Key=Phase,Value=4
```

**Verify:**
```bash
aws dynamodb list-tables | grep advisor
```

---

### Step 2: Update IAM Permissions (10 minutes)

Add these permissions to your Lambda execution role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:*:*:model/amazon.nova-lite-v1:0"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:DeleteItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/advisor-conversation-history",
        "arn:aws:dynamodb:*:*:table/advisor-cache"
      ]
    }
  ]
}
```

**Verify:**
```bash
aws iam get-role-policy --role-name <your-lambda-role> --policy-name <policy-name>
```

---

### Step 3: Update Lambda Configuration (10 minutes)

Add environment variables:

```bash
aws lambda update-function-configuration \
  --function-name <your-lambda-function-name> \
  --environment Variables="{
    BEDROCK_MODEL_ID=amazon.nova-lite-v1:0,
    ADVISOR_CACHE_TTL_HOURS=24,
    ADVISOR_CACHE_HIT_RATE_TARGET=40,
    <existing-env-vars>
  }"
```

**Verify:**
```bash
aws lambda get-function-configuration --function-name <your-lambda-function-name>
```

---

### Step 4: Deploy Lambda Code (30 minutes)

Package and deploy the updated Lambda code:

```bash
# Create deployment package
cd src
zip -r ../lambda_deployment.zip .
cd ..

# Upload to Lambda
aws lambda update-function-code \
  --function-name <your-lambda-function-name> \
  --zip-file fileb://lambda_deployment.zip
```

**Verify:**
```bash
aws lambda get-function --function-name <your-lambda-function-name>
```

---

### Step 5: Update API Gateway (30 minutes)

Add 4 new routes:

1. **POST /api/advisor/query**
   - Integration: Lambda function
   - Authorization: Same as existing endpoints

2. **GET /api/advisor/history**
   - Integration: Lambda function
   - Query parameters: session_id

3. **DELETE /api/advisor/history**
   - Integration: Lambda function
   - Request body: session_id

4. **GET /api/advisor/suggestions**
   - Integration: Lambda function
   - Query parameters: user_id

**Verify:**
```bash
aws apigatewayv2 get-routes --api-id <your-api-id>
```

---

### Step 6: Deploy API Gateway (5 minutes)

```bash
aws apigatewayv2 create-deployment \
  --api-id <your-api-id> \
  --stage-name prod
```

---

## Task 18: Integration Testing

### Test 1: End-to-End Advisor Workflow (30 minutes)

```bash
# Test query endpoint
curl -X POST https://<your-api-endpoint>/api/advisor/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What were my Lambda costs last month?",
    "user_id": "test-user",
    "session_id": "test-session-1"
  }'

# Expected: 200 OK with formatted response
```

**Verify:**
- [ ] Response contains cost data
- [ ] Response is markdown formatted
- [ ] Response time < 5s
- [ ] CloudWatch logs show Bedrock invocation

---

### Test 2: Cache Performance (20 minutes)

```bash
# Submit same query twice
curl -X POST https://<your-api-endpoint>/api/advisor/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What were my Lambda costs last month?",
    "user_id": "test-user",
    "session_id": "test-session-2"
  }'

# Wait 1 second, then repeat
```

**Verify:**
- [ ] First request: ~4-5s response time
- [ ] Second request: <500ms response time
- [ ] Cache hit logged in CloudWatch
- [ ] DynamoDB advisor-cache table has entry

---

### Test 3: Conversation History (15 minutes)

```bash
# Submit initial query
curl -X POST https://<your-api-endpoint>/api/advisor/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What were my costs yesterday?",
    "user_id": "test-user",
    "session_id": "test-session-3"
  }'

# Submit follow-up query
curl -X POST https://<your-api-endpoint>/api/advisor/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How does that compare to last week?",
    "user_id": "test-user",
    "session_id": "test-session-3"
  }'

# Get history
curl -X GET "https://<your-api-endpoint>/api/advisor/history?session_id=test-session-3"

# Clear history
curl -X DELETE https://<your-api-endpoint>/api/advisor/history \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session-3"}'
```

**Verify:**
- [ ] Follow-up query understands context
- [ ] History endpoint returns conversation turns
- [ ] Clear history succeeds
- [ ] DynamoDB conversation-history table updated

---

### Test 4: Proactive Insights (15 minutes)

```bash
curl -X GET "https://<your-api-endpoint>/api/advisor/suggestions?user_id=test-user"
```

**Verify:**
- [ ] Returns daily summary
- [ ] Includes anomaly detection
- [ ] Includes optimization suggestions
- [ ] Includes forecast alerts

---

### Test 5: Backward Compatibility (30 minutes)

Test all Phase 1, 1.5, 2, and 3 endpoints:

```bash
# Phase 1: Historical costs
curl -X GET "https://<your-api-endpoint>/api/costs?start_date=2026-01-01&end_date=2026-01-31"

# Phase 1.5: Real-time estimation
curl -X GET "https://<your-api-endpoint>/api/realtime/estimate?service=lambda"

# Phase 2: Forecasts
curl -X GET "https://<your-api-endpoint>/api/forecast?days=7"

# Phase 3: Prevention actions
curl -X GET "https://<your-api-endpoint>/api/prevention/actions"
```

**Verify:**
- [ ] All Phase 1 endpoints work
- [ ] All Phase 1.5 endpoints work
- [ ] All Phase 2 endpoints work
- [ ] All Phase 3 endpoints work
- [ ] No breaking changes

---

## Post-Deployment Monitoring

### CloudWatch Metrics to Track

1. **Bedrock API Usage**
   - Target: <500 calls/month
   - Monitor: `bedrock:InvokeModel` API calls

2. **Cache Hit Rate**
   - Target: 40%+
   - Monitor: Custom metric from advisor_cache_manager

3. **Response Times**
   - Cached: <500ms (P95)
   - Non-cached: <5s (P95)
   - Monitor: API Gateway latency metrics

4. **Error Rates**
   - Target: <1%
   - Monitor: Lambda errors, API Gateway 5xx responses

5. **DynamoDB Usage**
   - Storage: Should stay <100 MB
   - Reads/Writes: Should stay within free tier

---

## Cost Monitoring

### Expected Monthly Costs

```
Amazon Bedrock (Nova Lite): ~$0.50/month
├── API Calls: ~500/month
└── Cache Hit Rate: 40%+ (reduces calls by 60%)

DynamoDB: $0.00/month (within free tier)
├── Storage: ~60 MB
└── Reads/Writes: ~10,000/month

Lambda: $0.00/month (within free tier)
├── Invocations: ~1,000/month
└── Duration: ~2s average

Total Phase 4 Cost: ~$0.50/month
Total System Cost (Phases 1-4): ~$2.01/month
```

**Set up billing alerts:**
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name phase4-cost-alert \
  --alarm-description "Alert if Phase 4 costs exceed $1/month" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 1.0 \
  --comparison-operator GreaterThanThreshold
```

---

## Troubleshooting

### Issue: Bedrock Access Denied

**Solution:**
1. Verify Bedrock is enabled in your region
2. Check IAM permissions include `bedrock:InvokeModel`
3. Verify model ID is correct: `amazon.nova-lite-v1:0`

### Issue: DynamoDB Table Not Found

**Solution:**
1. Verify tables exist: `aws dynamodb list-tables`
2. Check table names match exactly
3. Verify Lambda has DynamoDB permissions

### Issue: Cache Not Working

**Solution:**
1. Check TTL is enabled on advisor-cache table
2. Verify query hashing is consistent
3. Check CloudWatch logs for cache errors

### Issue: Slow Response Times

**Solution:**
1. Check Bedrock API latency in CloudWatch
2. Verify cache hit rate is 40%+
3. Optimize prompt construction if needed

---

## Rollback Plan

If issues occur, rollback steps:

1. **Remove API Gateway routes** (5 minutes)
   ```bash
   aws apigatewayv2 delete-route --api-id <api-id> --route-id <route-id>
   ```

2. **Revert Lambda code** (10 minutes)
   ```bash
   aws lambda update-function-code \
     --function-name <function-name> \
     --s3-bucket <backup-bucket> \
     --s3-key lambda_backup.zip
   ```

3. **Remove environment variables** (5 minutes)
   ```bash
   aws lambda update-function-configuration \
     --function-name <function-name> \
     --environment Variables="{<original-vars>}"
   ```

4. **Keep DynamoDB tables** (no action needed)
   - Tables can remain without causing issues
   - Delete later if needed

---

## Success Criteria

- [ ] All infrastructure deployed successfully
- [ ] All 5 integration tests passing
- [ ] Cache hit rate >40%
- [ ] Response times meet targets
- [ ] No breaking changes to Phases 1-3
- [ ] Costs within budget (~$0.50/month)
- [ ] CloudWatch monitoring configured
- [ ] Billing alerts set up

---

## Documentation References

- **Deployment Guide:** `docs/technical/phase4-ai-advisor/infrastructure-updates.md`
- **API Examples:** `docs/API_EXAMPLES.md`
- **Phase 4 Status:** `docs/PHASE4_STATUS.md`
- **Project Status:** `docs/PROJECT_STATUS.md`

---

## Semantic Search Keywords

**Deployment Topics:**
- Infrastructure deployment, AWS deployment, production deployment, CDK deployment
- DynamoDB tables, IAM permissions, Lambda configuration, API Gateway routes
- Environment variables, Bedrock access, resource provisioning
- Step-by-step deployment, deployment checklist, deployment guide

**Testing Topics:**
- Integration testing, end-to-end testing, backward compatibility testing
- Cache performance testing, conversation flow testing, proactive insights testing
- Test verification, test automation, API testing

**Monitoring Topics:**
- CloudWatch monitoring, metrics tracking, cost monitoring, performance monitoring
- Cache hit rate, response times, error rates, API usage
- Billing alerts, cost alerts, budget monitoring

**Operations Topics:**
- Troubleshooting, debugging, rollback procedures, disaster recovery
- Production support, operational procedures, maintenance
- Performance optimization, cost optimization

**AWS Services:**
- Amazon Bedrock, Nova Lite, DynamoDB, Lambda, API Gateway
- IAM roles, CloudWatch, Cost Explorer, billing
- Free tier compliance, resource management

**Phase 4 Features:**
- AI advisor, conversational AI, natural language processing
- Query processing, context management, response caching
- Proactive insights, conversation history

---

## Cross-References

### Documentation
- **[Phase 4 README](docs/technical/phase4-ai-advisor/README.md)** - Feature overview and getting started
- **[Infrastructure Updates](docs/technical/phase4-ai-advisor/infrastructure-updates.md)** - Detailed deployment guide with CDK examples
- **[Implementation Summary](docs/technical/phase4-ai-advisor/implementation-summary.md)** - Test results and deliverables
- **[Phase 4 Status](docs/PHASE4_STATUS.md)** - Quick status reference
- **[Project Status](docs/PROJECT_STATUS.md)** - Complete project status across all phases
- **[API Examples](docs/API_EXAMPLES.md)** - Complete API usage examples for testing

### Related Phases
- **[Phase 1 Infrastructure](docs/technical/phase1-cost-pipeline/infrastructure-updates.md)** - Historical cost pipeline deployment
- **[Phase 2 Infrastructure](docs/technical/phase2-ai-forecasting/infrastructure-updates.md)** - AI forecasting deployment
- **[Phase 3 Infrastructure](docs/technical/phase3-automated-prevention/infrastructure-updates.md)** - Prevention system deployment

### Specifications
- **[Requirements](/.kiro/specs/ai-cost-advisor/requirements.md)** - Phase 4 requirements
- **[Design](/.kiro/specs/ai-cost-advisor/design.md)** - Phase 4 design document
- **[Tasks](/.kiro/specs/ai-cost-advisor/tasks.md)** - Implementation task list

---

**Next Steps After Deployment:**

1. Monitor for 24-48 hours
2. Optimize cache TTL if needed
3. Fine-tune Bedrock prompts
4. Collect user feedback
5. Iterate on features

---

**Status:** Ready to Deploy  
**Last Updated:** January 2026  
**For Support:** Review troubleshooting section above or check related documentation
