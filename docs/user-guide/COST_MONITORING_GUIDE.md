# Cost Monitoring Guide - Free Tier Compliance

**Goal:** Monitor AWS costs after each phase deployment to ensure we stay within free tier limits.

**Target:** ~$2.51/month total (mostly Cost Explorer API, everything else free tier)

---

## Cost Monitoring Commands

### Check Current Month Costs

```bash
# Get current month costs by service
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date -d "tomorrow" +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --group-by Type=SERVICE

# Get today's costs
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-%d),End=$(date -d "tomorrow" +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --group-by Type=SERVICE
```

### Check Free Tier Usage

```bash
# Check Lambda invocations (free tier: 1M requests/month)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=CostGuardLambda \
  --start-time $(date -d "$(date +%Y-%m-01)" +%Y-%m-%dT00:00:00Z) \
  --end-time $(date +%Y-%m-%dT23:59:59Z) \
  --period 2592000 \
  --statistics Sum

# Check DynamoDB storage (free tier: 25 GB)
aws dynamodb describe-table --table-name costguard-cost-data --query 'Table.TableSizeBytes'

# Check API Gateway requests (free tier: 1M requests/month)
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --start-time $(date -d "$(date +%Y-%m-01)" +%Y-%m-%dT00:00:00Z) \
  --end-time $(date +%Y-%m-%dT23:59:59Z) \
  --period 2592000 \
  --statistics Sum
```

---

## Phase 1: Cost Checkpoint

**Expected Costs:**
- Cost Explorer API: ~$0.03/day = ~$1.00/month
- DynamoDB: $0.00 (within 25 GB free tier)
- Lambda: $0.00 (within 1M requests free tier)
- API Gateway: $0.00 (within 1M requests free tier)
- CloudWatch: $0.00 (within 5 GB free tier)

**Total Phase 1:** ~$1.00/month

### Verification Steps

```bash
# 1. Check Cost Explorer API usage
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-%d),End=$(date -d "tomorrow" +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter file://cost-explorer-filter.json

# cost-explorer-filter.json:
# {
#   "Dimensions": {
#     "Key": "SERVICE",
#     "Values": ["AWS Cost Explorer"]
#   }
# }

# 2. Check DynamoDB usage
aws dynamodb describe-table --table-name costguard-cost-data \
  --query 'Table.[TableSizeBytes,ItemCount]'

# 3. Check Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=CostGuardLambda \
  --start-time $(date -d "1 day ago" +%Y-%m-%dT00:00:00Z) \
  --end-time $(date +%Y-%m-%dT23:59:59Z) \
  --period 86400 \
  --statistics Sum
```

**Decision:** ✅ If costs ≤ $1.00/month, proceed to Phase 1.5

---

## Phase 1.5: Cost Checkpoint

**Expected Additional Costs:**
- Pricing API: ~$0.01/month (caching reduces calls)
- No new infrastructure costs

**Total After Phase 1.5:** ~$1.01/month

### Verification Steps

```bash
# Check Pricing API usage
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-%d),End=$(date -d "tomorrow" +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter file://pricing-api-filter.json

# pricing-api-filter.json:
# {
#   "Dimensions": {
#     "Key": "SERVICE",
#     "Values": ["AWS Price List Service"]
#   }
# }
```

**Decision:** ✅ If costs ≤ $1.01/month, proceed to Phase 2

---

## Phase 2: Cost Checkpoint

**Expected Additional Costs:**
- Bedrock API: ~$0.50/month (target <500 calls with 80%+ cache hit rate)
- DynamoDB forecast cache: $0.00 (within free tier)

**Total After Phase 2:** ~$1.51/month

### Verification Steps

```bash
# Check Bedrock API usage
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-%d),End=$(date -d "tomorrow" +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter file://bedrock-filter.json

# bedrock-filter.json:
# {
#   "Dimensions": {
#     "Key": "SERVICE",
#     "Values": ["Amazon Bedrock"]
#   }
# }

# Check Bedrock invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Bedrock \
  --metric-name Invocations \
  --start-time $(date -d "1 day ago" +%Y-%m-%dT00:00:00Z) \
  --end-time $(date +%Y-%m-%dT23:59:59Z) \
  --period 86400 \
  --statistics Sum

# Check forecast cache hit rate (should be 80%+)
# This is tracked in application logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/CostGuardLambda \
  --filter-pattern "cache_hit_rate" \
  --start-time $(date -d "1 day ago" +%s)000
```

**Decision:** ✅ If costs ≤ $1.51/month AND cache hit rate ≥ 80%, proceed to Phase 3

**⚠️ WARNING:** If Bedrock costs > $0.50/month, increase cache TTL or reduce forecast frequency

---

## Phase 3: Cost Checkpoint

**Expected Additional Costs:**
- AWS Budgets API: $0.00 (2 budgets free)
- SNS: $0.00 (within 1M publishes/month free tier)
- EventBridge: $0.00 (rules are free)
- Additional Lambda invocations: $0.00 (within free tier)
- Additional DynamoDB tables: $0.00 (within 25 GB free tier)

**Total After Phase 3:** ~$1.51/month (no increase)

### Verification Steps

```bash
# Check SNS usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/SNS \
  --metric-name NumberOfMessagesPublished \
  --start-time $(date -d "$(date +%Y-%m-01)" +%Y-%m-%dT00:00:00Z) \
  --end-time $(date +%Y-%m-%dT23:59:59Z) \
  --period 2592000 \
  --statistics Sum

# Check EventBridge invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Events \
  --metric-name Invocations \
  --dimensions Name=RuleName,Value=costguard-budget-monitor \
  --start-time $(date -d "1 day ago" +%Y-%m-%dT00:00:00Z) \
  --end-time $(date +%Y-%m-%dT23:59:59Z) \
  --period 86400 \
  --statistics Sum

# Check total DynamoDB storage across all tables
aws dynamodb list-tables --query 'TableNames' --output text | \
  xargs -I {} aws dynamodb describe-table --table-name {} --query 'Table.TableSizeBytes' --output text | \
  awk '{sum+=$1} END {print "Total DynamoDB storage:", sum/1024/1024/1024, "GB"}'
```

**Decision:** ✅ If costs ≤ $1.51/month AND DynamoDB < 25 GB, proceed to Phase 4

---

## Phase 4: Cost Checkpoint

**Expected Additional Costs:**
- Bedrock API: ~$0.50/month (target <500 calls with 40%+ cache hit rate)
- DynamoDB advisor tables: $0.00 (within free tier)

**Total After Phase 4:** ~$2.01/month

### Verification Steps

```bash
# Check total Bedrock usage (Phase 2 + Phase 4)
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-%d),End=$(date -d "tomorrow" +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter file://bedrock-filter.json

# Check advisor cache hit rate (should be 40%+)
aws logs filter-log-events \
  --log-group-name /aws/lambda/CostGuardLambda \
  --filter-pattern "advisor_cache_hit_rate" \
  --start-time $(date -d "1 day ago" +%s)000

# Check total Bedrock invocations (should be <1000/month combined)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Bedrock \
  --metric-name Invocations \
  --start-time $(date -d "$(date +%Y-%m-01)" +%Y-%m-%dT00:00:00Z) \
  --end-time $(date +%Y-%m-%dT23:59:59Z) \
  --period 2592000 \
  --statistics Sum
```

**Decision:** ✅ If costs ≤ $2.01/month AND Bedrock calls < 1000/month, proceed to Phase 5

**⚠️ WARNING:** If Bedrock costs > $1.00/month total, optimize caching or reduce usage

---

## Phase 5: Cost Checkpoint

**Expected Additional Costs:**
- Cost Explorer API: ~$0.00 (cross-account calls within existing budget)
- Organizations API: $0.00 (free)
- Additional DynamoDB tables: $0.00 (within free tier)

**Total After Phase 5:** ~$2.01/month (no increase)

### Verification Steps

```bash
# Check Organizations API usage (should be $0.00)
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-%d),End=$(date -d "tomorrow" +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter file://organizations-filter.json

# Check total DynamoDB storage
aws dynamodb list-tables --query 'TableNames' --output text | \
  xargs -I {} aws dynamodb describe-table --table-name {} --query 'Table.TableSizeBytes' --output text | \
  awk '{sum+=$1} END {print "Total DynamoDB storage:", sum/1024/1024/1024, "GB"}'
```

**Decision:** ✅ If costs ≤ $2.01/month AND DynamoDB < 25 GB, proceed to Phase 6

---

## Phase 6: Cost Checkpoint

**Expected Additional Costs:**
- Cost Explorer API: ~$0.50/month (GPU instance cost queries)
- CloudWatch API: $0.00 (within free tier)
- Bedrock API: $0.00 (reuses Phase 2/4 budget)

**Total After Phase 6:** ~$2.51/month

### Verification Steps

```bash
# Check total Cost Explorer API usage
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-%d),End=$(date -d "tomorrow" +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter file://cost-explorer-filter.json

# Check CloudWatch API calls (should be within free tier)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Usage \
  --metric-name CallCount \
  --dimensions Name=Service,Value=CloudWatch Name=Type,Value=API \
  --start-time $(date -d "$(date +%Y-%m-01)" +%Y-%m-%dT00:00:00Z) \
  --end-time $(date +%Y-%m-%dT23:59:59Z) \
  --period 2592000 \
  --statistics Sum

# Check total system costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date -d "tomorrow" +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics UnblendedCost
```

**Decision:** ✅ If costs ≤ $2.51/month, deployment complete!

---

## Free Tier Limits Reference

| Service | Free Tier Limit | Our Usage | Status |
|---------|----------------|-----------|--------|
| Lambda | 1M requests/month | ~15,000/month | ✅ 1.5% |
| API Gateway | 1M requests/month | ~3,000/month | ✅ 0.3% |
| DynamoDB | 25 GB storage | ~450 MB | ✅ 1.8% |
| DynamoDB | 25 WCU, 25 RCU | On-demand | ✅ Free |
| CloudWatch Logs | 5 GB ingestion | ~100 MB/month | ✅ 2% |
| SNS | 1M publishes/month | ~500/month | ✅ 0.05% |
| Cost Explorer | N/A | ~$1.50/month | 💰 Paid |
| Bedrock | N/A | ~$1.00/month | 💰 Paid |

**Total Paid Services:** ~$2.51/month
**Total Free Tier Services:** $0.00/month

---

## Cost Optimization Tips

### If Costs Exceed Budget

1. **Bedrock Costs Too High (> $1.00/month)**
   - Increase cache TTL from 24h to 48h
   - Increase cache hit rate target from 40% to 60%
   - Reduce forecast frequency
   - Use shorter prompts

2. **Cost Explorer Costs Too High (> $1.50/month)**
   - Reduce query frequency
   - Increase data caching
   - Use longer time ranges (monthly vs daily)

3. **Lambda Approaching Free Tier Limit**
   - Optimize Lambda code for faster execution
   - Reduce cold starts
   - Increase memory (faster execution = lower cost)

4. **DynamoDB Approaching 25 GB Limit**
   - Enable TTL on old records
   - Archive old data to S3
   - Reduce data retention period

### Cost Alerts

Set up billing alerts to notify when costs exceed thresholds:

```bash
# Create billing alarm for $3/month threshold
aws cloudwatch put-metric-alarm \
  --alarm-name costguard-billing-alert \
  --alarm-description "Alert when CostGuard costs exceed $3/month" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 21600 \
  --evaluation-periods 1 \
  --threshold 3.0 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD
```

---

## Monthly Cost Review Checklist

At the end of each month, review:

- [ ] Total AWS bill ≤ $2.51
- [ ] Cost Explorer API ≤ $1.50
- [ ] Bedrock API ≤ $1.00
- [ ] Lambda invocations < 1M
- [ ] API Gateway requests < 1M
- [ ] DynamoDB storage < 25 GB
- [ ] CloudWatch logs < 5 GB
- [ ] SNS publishes < 1M
- [ ] No unexpected charges

**If all checks pass:** System is cost-optimized and within budget! ✅

**If any check fails:** Investigate and optimize before next month.

---

**Remember:** Monitor costs after EACH phase deployment. Don't proceed to the next phase if costs are higher than expected!
