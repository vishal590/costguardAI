# Phase 6 Separate Stack Architecture

**Date:** March 3, 2026  
**Status:** ✅ **READY FOR DEPLOYMENT**

---

## Problem Solved

The initial Phase 6 deployment failed because we were adding Phase 6 infrastructure to the existing `CostGuardStack` (Phases 1-4), which already had a large Lambda package. This caused the Lambda deployment package to exceed AWS's 250MB limit.

---

## Solution: Separate Stack Architecture

Following the same pattern as Phase 5, Phase 6 now has its own dedicated CDK stack:

### Stack Architecture

```
CostGuard Infrastructure (3 Stacks)
├── CostGuardStack (Phases 1-4)
│   ├── DynamoDB: 8 tables (cost-data, forecasts, prevention, advisor, etc.)
│   ├── Lambda: CostGuardLambda (main handler)
│   ├── API Gateway: CostGuardAPI (Phases 1-4 endpoints)
│   └── SNS, EventBridge, CloudWatch
│
├── CostGuardMultiAccountStack (Phase 5)
│   ├── DynamoDB: 5 tables (organizations, accounts, multi-account-costs, etc.)
│   ├── Lambda: 3 functions (cost collector, API handler, main handler)
│   ├── API Gateway: MultiAccountAPI (Phase 5 endpoints)
│   └── SNS, EventBridge, CloudWatch
│
└── CostGuardAIMLStack (Phase 6) ← NEW
    ├── DynamoDB: 3 tables (gpu-costs, workload-classifications, aiml-cache)
    ├── Lambda: CostGuard-AIMLHandler (AI/ML handler)
    ├── API Gateway: AIMLAPI (Phase 6 endpoints)
    └── SNS, CloudWatch
```

### Deployment Order

```
1. CostGuardStack (Phases 1-4)
   ↓
2. CostGuardMultiAccountStack (Phase 5) ← depends on #1
   ↓
3. CostGuardAIMLStack (Phase 6) ← depends on #1 and #2
```

---

## Changes Made

### 1. Created New Stack File
**File:** `infrastructure/aiml_stack.py`

- New `AIMLStack` class following the same pattern as `MultiAccountStack`
- Contains only Phase 6 infrastructure:
  - 3 DynamoDB tables
  - 1 Lambda function (CostGuard-AIMLHandler)
  - 1 API Gateway with 20+ endpoints
  - IAM roles with GPU/SageMaker/Bedrock permissions
  - CloudWatch alarms
  - SNS notifications

### 2. Updated CDK App
**File:** `infrastructure/app.py`

- Added import for `AIMLStack`
- Instantiated `CostGuardAIMLStack`
- Added dependencies:
  - `aiml_stack.add_dependency(costguard_stack)` - Phase 6 depends on Phases 1-4
  - `aiml_stack.add_dependency(multi_account_stack)` - Phase 6 uses multi-account tables

### 3. Cleaned Up Main Stack
**File:** `infrastructure/cdk_stack.py`

- Removed Phase 6 DynamoDB tables (moved to `aiml_stack.py`)
- Removed Phase 6 API endpoints (moved to `aiml_stack.py`)
- Removed Phase 6 IAM permissions (moved to `aiml_stack.py`)
- Removed Phase 6 environment variables (moved to `aiml_stack.py`)

---

## Benefits of Separate Stack

### 1. Smaller Lambda Packages
- Each stack has its own Lambda function with only the code it needs
- No more 250MB package size issues
- Faster deployments

### 2. Independent Deployment
- Can deploy/update Phase 6 without touching Phases 1-5
- Reduces risk of breaking existing functionality
- Faster iteration during development

### 3. Better Resource Organization
- Clear separation of concerns
- Easier to understand and maintain
- Follows AWS best practices

### 4. Scalability
- Can add more phases as separate stacks
- Each phase can scale independently
- Better cost tracking per phase

---

## Deployment Instructions

### Deploy Only Phase 6 (Recommended)

Since Phases 1-5 are already deployed, you only need to deploy the new Phase 6 stack:

```bash
cd infrastructure
cdk deploy CostGuardAIMLStack --require-approval never
```

### Deploy All Stacks (If Needed)

If you need to deploy everything from scratch:

```bash
cd infrastructure
cdk deploy --all --require-approval never
```

### Check What Will Be Deployed

```bash
cd infrastructure
cdk diff CostGuardAIMLStack
```

---

## Expected Deployment Output

### Resources to be Created

1. **DynamoDB Tables (3)**
   - `costguard-gpu-costs` (with workload-type-index GSI)
   - `costguard-workload-classifications`
   - `costguard-aiml-cache`

2. **Lambda Function (1)**
   - `CostGuard-AIMLHandler`
   - Runtime: Python 3.11
   - Memory: 512 MB
   - Timeout: 5 minutes

3. **API Gateway (1)**
   - `CostGuard-AIMLAPI`
   - 20+ endpoints under `/api/ai-ml/`

4. **IAM Role (1)**
   - `AIMLLambdaRole` with permissions for:
     - EC2 (GPU instances)
     - SageMaker
     - Bedrock
     - CloudWatch
     - Cost Explorer
     - Organizations (multi-account)

5. **CloudWatch Alarms (2)**
   - Lambda errors alarm
   - API response time alarm

6. **SNS Topic (1)**
   - `costguard-aiml-notifications`

7. **CloudWatch Log Group (1)**
   - `/aws/lambda/CostGuard-AIMLHandler`

### Stack Outputs

After deployment, you'll see:

```
CostGuardAIMLStack.AIMLAPIEndpoint = https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/
CostGuardAIMLStack.AIMLHandlerFunctionName = CostGuard-AIMLHandler
CostGuardAIMLStack.NotificationsTopicArn = arn:aws:sns:us-east-1:xxxxxxxxxxxx:costguard-aiml-notifications
CostGuardAIMLStack.GPUCostsTableName = costguard-gpu-costs
CostGuardAIMLStack.WorkloadClassificationsTableName = costguard-workload-classifications
CostGuardAIMLStack.AIMLCacheTableName = costguard-aiml-cache
```

---

## Testing After Deployment

### 1. Verify Tables Exist

```bash
aws dynamodb list-tables --query 'TableNames[?contains(@, `gpu`) || contains(@, `workload`) || contains(@, `aiml-cache`)]'
```

Expected output:
```json
[
    "costguard-aiml-cache",
    "costguard-gpu-costs",
    "costguard-workload-classifications"
]
```

### 2. Verify Lambda Function

```bash
aws lambda get-function --function-name CostGuard-AIMLHandler --query 'Configuration.[FunctionName,Runtime,MemorySize,Timeout]'
```

### 3. Test API Endpoints

```bash
# Get API endpoint from stack outputs
API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name CostGuardAIMLStack --query 'Stacks[0].Outputs[?OutputKey==`AIMLAPIEndpoint`].OutputValue' --output text)

# Test GPU costs endpoint
curl "${API_ENDPOINT}api/ai-ml/gpu-costs"

# Test workload classification endpoint
curl "${API_ENDPOINT}api/ai-ml/workload-classification"
```

---

## Rollback Plan

If deployment fails or issues arise:

### Delete Phase 6 Stack Only

```bash
cd infrastructure
cdk destroy CostGuardAIMLStack
```

This will:
- Delete the Lambda function
- Delete the API Gateway
- Delete CloudWatch alarms and log groups
- **RETAIN** DynamoDB tables (due to `RemovalPolicy.RETAIN`)

### Manual Table Cleanup (If Needed)

```bash
aws dynamodb delete-table --table-name costguard-gpu-costs
aws dynamodb delete-table --table-name costguard-workload-classifications
aws dynamodb delete-table --table-name costguard-aiml-cache
```

---

## Estimated Deployment Time

- **Phase 6 Stack Only:** 3-5 minutes
- **All Stacks:** 10-15 minutes

---

## Cost Impact

### New Resources
- 3 DynamoDB tables (PAY_PER_REQUEST): ~$0.25/million requests
- 1 Lambda function: ~$0.20 per 1M requests + compute time
- 1 API Gateway: ~$3.50 per million requests
- CloudWatch Logs: ~$0.50/GB ingested

### Estimated Monthly Cost (Low Usage)
- **DynamoDB:** $1-5/month
- **Lambda:** $1-3/month
- **API Gateway:** $1-2/month
- **CloudWatch:** $1-2/month
- **Total:** ~$5-15/month

---

## Next Steps

1. ✅ Deploy Phase 6 stack: `cdk deploy CostGuardAIMLStack`
2. ✅ Verify tables and Lambda function
3. ✅ Test API endpoints
4. ✅ Monitor CloudWatch logs for any errors
5. ✅ Update documentation with API endpoint URL

---

## Success Criteria

- ✅ All 3 DynamoDB tables created
- ✅ Lambda function deployed successfully
- ✅ API Gateway accessible
- ✅ All 20+ endpoints responding
- ✅ No CloudWatch alarms triggered
- ✅ Phase 6 tests still passing (161 tests)

---

**Status:** Ready for deployment! 🚀
