# Phase 6 Deployment Plan

**Date:** March 2, 2026  
**Status:** 📋 READY TO DEPLOY  
**Estimated Time:** 2-3 hours

---

## Pre-Deployment Checklist

### Code Readiness
- ✅ All 161 tests passing (100% pass rate)
- ✅ Edge case tests fixed
- ✅ Property-based testing validates correctness
- ✅ Integration tests passing
- ✅ Backward compatibility verified
- ✅ Code coverage: 60-96% on core modules

### Documentation
- ✅ API documentation complete
- ✅ Deployment guide complete
- ✅ User guide complete
- ✅ Testing documentation complete

### Infrastructure Requirements
- ⏸️ CDK stack updates needed
- ⏸️ 3 new DynamoDB tables
- ⏸️ Lambda function updates
- ⏸️ API Gateway routes (20+ endpoints)
- ⏸️ IAM permissions

---

## Deployment Steps

### Step 1: Update CDK Stack (30 minutes)

**Add 3 New DynamoDB Tables:**

1. **GPU Costs Table** (`costguard-gpu-costs`)
   - Partition key: `instance_id` (STRING)
   - Sort key: `timestamp` (STRING)
   - GSI: `workload-type-index` (partition: `workload_type`, sort: `timestamp`)
   - Billing: PAY_PER_REQUEST
   - TTL: enabled on `ttl` attribute

2. **Workload Classifications Table** (`costguard-workload-classifications`)
   - Partition key: `instance_id` (STRING)
   - Sort key: `date` (STRING)
   - Billing: PAY_PER_REQUEST
   - TTL: enabled on `ttl` attribute

3. **AI/ML Cache Table** (`costguard-aiml-cache`)
   - Partition key: `cache_key` (STRING)
   - Billing: PAY_PER_REQUEST
   - TTL: enabled on `ttl` attribute

**Update Lambda Function:**
- Add AI/ML handler code to existing Lambda
- Update memory to 512 MB (if not already)
- Update timeout to 30 seconds (if not already)
- Add environment variables

**Add IAM Permissions:**
- Cost Explorer: `ce:GetCostAndUsage`
- CloudWatch: `cloudwatch:GetMetricStatistics`
- EC2: `ec2:DescribeInstances`, `ec2:DescribeInstanceTypes`
- SageMaker: `sagemaker:ListTrainingJobs`, `sagemaker:ListEndpoints`
- Bedrock: `bedrock:ListModelInvocationJobs`
- Pricing: `pricing:GetProducts`

### Step 2: Deploy Infrastructure (15 minutes)

```bash
# Navigate to infrastructure directory
cd infrastructure

# Synthesize CDK stack
cdk synth

# Review changes
cdk diff

# Deploy (with approval)
cdk deploy --require-approval never

# Verify deployment
aws cloudformation describe-stacks --stack-name CostGuardStack
```

### Step 3: Verify DynamoDB Tables (5 minutes)

```bash
# Check new tables exist
aws dynamodb describe-table --table-name costguard-gpu-costs
aws dynamodb describe-table --table-name costguard-workload-classifications
aws dynamodb describe-table --table-name costguard-aiml-cache

# Verify GSI on gpu-costs table
aws dynamodb describe-table --table-name costguard-gpu-costs \
  --query 'Table.GlobalSecondaryIndexes[*].IndexName'
```

### Step 4: Update Lambda Environment Variables (5 minutes)

```bash
# Add Phase 6 environment variables
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{
    DYNAMODB_TABLE_NAME=costguard-cost-data,
    FORECAST_CACHE_TABLE=costguard-forecast-cache,
    PREVENTION_CONFIG_TABLE=costguard-prevention-config,
    RESOURCE_INVENTORY_TABLE=costguard-resource-inventory,
    AUDIT_LOG_TABLE=costguard-audit-log,
    APPROVAL_TABLE=costguard-approvals,
    GPU_COSTS_TABLE=costguard-gpu-costs,
    WORKLOAD_CLASSIFICATIONS_TABLE=costguard-workload-classifications,
    AIML_CACHE_TABLE=costguard-aiml-cache,
    SNS_TOPIC_ARN=<your-sns-topic-arn>,
    AWS_DEFAULT_REGION=us-east-1
  }"
```

### Step 5: Test API Endpoints (30 minutes)

**Test GPU Costs Endpoint:**
```bash
curl -X GET "https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/gpu-costs?startDate=2026-02-01&endDate=2026-02-28" \
  -H "x-api-key: <your-api-key>"
```

**Test Workload Classification:**
```bash
curl -X GET "https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/workload-classification?instanceId=i-1234567890abcdef0&startDate=2026-02-01&endDate=2026-02-28" \
  -H "x-api-key: <your-api-key>"
```

**Test Spot Recommendations:**
```bash
curl -X GET "https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/spot-recommendations?instanceType=p3.2xlarge&workloadType=training" \
  -H "x-api-key: <your-api-key>"
```

### Step 6: Monitor and Validate (15 minutes)

**Check CloudWatch Logs:**
```bash
# Get latest log stream
aws logs describe-log-streams \
  --log-group-name /aws/lambda/CostGuardLambda \
  --order-by LastEventTime \
  --descending \
  --max-items 1

# View logs
aws logs tail /aws/lambda/CostGuardLambda --follow
```

**Check DynamoDB Metrics:**
```bash
# Check table metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=costguard-gpu-costs \
  --start-time 2026-03-02T00:00:00Z \
  --end-time 2026-03-02T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

---

## Post-Deployment Verification

### Functional Tests

- [ ] GPU costs endpoint returns data
- [ ] Workload classification works
- [ ] Spot recommendations generated
- [ ] SageMaker costs tracked
- [ ] Bedrock costs tracked
- [ ] Multi-account GPU aggregation works
- [ ] Cache is functioning
- [ ] Error handling works correctly

### Performance Tests

- [ ] API response time < 2 seconds
- [ ] DynamoDB read/write latency acceptable
- [ ] Lambda cold start < 5 seconds
- [ ] Lambda warm start < 500ms

### Cost Verification

- [ ] DynamoDB costs within free tier
- [ ] Lambda invocations within free tier
- [ ] API Gateway requests within free tier
- [ ] Total Phase 6 cost ~$0.50/month

---

## Rollback Plan

If deployment fails or issues are discovered:

### Immediate Rollback (5 minutes)

```bash
# Rollback CDK deployment
cdk deploy --rollback

# Or use CloudFormation
aws cloudformation cancel-update-stack --stack-name CostGuardStack
```

### Manual Rollback (15 minutes)

1. **Delete new DynamoDB tables:**
```bash
aws dynamodb delete-table --table-name costguard-gpu-costs
aws dynamodb delete-table --table-name costguard-workload-classifications
aws dynamodb delete-table --table-name costguard-aiml-cache
```

2. **Revert Lambda function:**
```bash
# Get previous version
aws lambda list-versions-by-function --function-name CostGuardLambda

# Rollback to previous version
aws lambda update-alias \
  --function-name CostGuardLambda \
  --name PROD \
  --function-version <previous-version>
```

3. **Remove API Gateway routes:**
```bash
# List routes
aws apigatewayv2 get-routes --api-id <api-id>

# Delete Phase 6 routes
aws apigatewayv2 delete-route --api-id <api-id> --route-id <route-id>
```

---

## Known Issues and Mitigations

### Issue 1: Cold Start Latency
**Impact:** First API call may take 3-5 seconds  
**Mitigation:** Use Lambda provisioned concurrency or warm-up pings

### Issue 2: Cost Explorer API Limits
**Impact:** 100 requests per second limit  
**Mitigation:** Implement request throttling and caching

### Issue 3: CloudWatch Metrics Delay
**Impact:** GPU metrics may be delayed by 5-15 minutes  
**Mitigation:** Document expected delay in user guide

---

## Success Criteria

- ✅ All 20+ API endpoints responding
- ✅ DynamoDB tables created and accessible
- ✅ Lambda function updated successfully
- ✅ IAM permissions working correctly
- ✅ No errors in CloudWatch logs
- ✅ Backward compatibility maintained (Phases 1-5 still work)
- ✅ Cost within budget (~$0.50/month)
- ✅ All functional tests passing

---

## Next Steps After Deployment

1. **Monitor for 24 hours**
   - Watch CloudWatch logs for errors
   - Monitor DynamoDB metrics
   - Check API Gateway metrics

2. **Run integration tests**
   - Test all 20+ endpoints
   - Verify multi-account functionality
   - Test error handling

3. **Update documentation**
   - Document actual API endpoints
   - Update user guide with real examples
   - Create troubleshooting guide

4. **Notify stakeholders**
   - Send deployment notification
   - Share API documentation
   - Provide training materials

---

## Contact and Support

**Deployment Lead:** CostGuard AI Team  
**Escalation:** AWS Support (if needed)  
**Documentation:** See `docs/deployment/phase6-deployment-guide.md`

---

**Status:** Ready to proceed with deployment  
**Next Action:** Update CDK stack with Phase 6 infrastructure
