# Phase 4: AI Cost Advisor - Infrastructure Updates

**Keywords:** infrastructure, deployment, AWS, DynamoDB, IAM, Lambda, API Gateway, Bedrock, permissions, environment variables, CDK, CloudFormation, infrastructure as code, deployment guide, Phase 4

**Status:** ⏸️ **PENDING DEPLOYMENT** - Code Complete, Infrastructure Not Deployed  
**Prerequisites:** AWS Account with Bedrock access, Phases 1-3 deployed

## Related Documentation

- **[README.md](./README.md)** - Phase 4 overview and features
- **[implementation-summary.md](./implementation-summary.md)** - Test results and deliverables
- **[specification.md](./specification.md)** - Complete Phase 4 Kiro specification
- **[../../API_EXAMPLES.md](../../API_EXAMPLES.md)** - API usage examples
- **[../architecture.md](../architecture.md)** - System architecture

---

## Overview

This document describes the AWS infrastructure changes required to deploy Phase 4 (AI Cost Advisor). All code is complete and tested; only infrastructure deployment remains.

### Infrastructure Changes Summary

- **2 New DynamoDB Tables:** advisor-conversation-history, advisor-cache
- **IAM Permission Updates:** Add Bedrock InvokeModel permission
- **3 New Lambda Environment Variables:** BEDROCK_MODEL_ID, ADVISOR_CACHE_TTL_HOURS, ADVISOR_CACHE_HIT_RATE_TARGET
- **4 New API Gateway Routes:** POST /api/advisor/query, GET /api/advisor/history, DELETE /api/advisor/history, GET /api/advisor/suggestions
- **CDK Stack Updates:** Add Phase 4 resources to existing CDK stack

---

## Task 17.1: Create DynamoDB Tables

### Table 1: advisor-conversation-history

**Purpose:** Store conversation history for context-aware follow-up questions

**Configuration:**
```json
{
  "TableName": "advisor-conversation-history",
  "BillingMode": "PAY_PER_REQUEST",
  "AttributeDefinitions": [
    {
      "AttributeName": "session_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "timestamp",
      "AttributeType": "N"
    }
  ],
  "KeySchema": [
    {
      "AttributeName": "session_id",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "timestamp",
      "KeyType": "RANGE"
    }
  ],
  "TimeToLiveSpecification": {
    "Enabled": true,
    "AttributeName": "ttl"
  },
  "Tags": [
    {
      "Key": "Project",
      "Value": "CostGuard"
    },
    {
      "Key": "Phase",
      "Value": "4"
    },
    {
      "Key": "Component",
      "Value": "AIAdvisor"
    }
  ]
}
```

**Item Structure:**
```json
{
  "session_id": "session-123",
  "timestamp": 1704067200,
  "query": "What were my costs last month?",
  "response": "Your total costs last month were $123.45...",
  "context": {
    "historical_costs": [...],
    "forecast_data": [...],
    "prevention_actions": [...]
  },
  "ttl": 1704153600
}
```

**Estimated Storage:** ~10 MB/month  
**Estimated Reads:** ~500/month  
**Estimated Writes:** ~500/month  
**Cost:** $0.00/month (within free tier)

### Table 2: advisor-cache

**Purpose:** Cache AI advisor responses to reduce Bedrock API calls

**Configuration:**
```json
{
  "TableName": "advisor-cache",
  "BillingMode": "PAY_PER_REQUEST",
  "AttributeDefinitions": [
    {
      "AttributeName": "query_hash",
      "AttributeType": "S"
    }
  ],
  "KeySchema": [
    {
      "AttributeName": "query_hash",
      "KeyType": "HASH"
    }
  ],
  "TimeToLiveSpecification": {
    "Enabled": true,
    "AttributeName": "ttl"
  },
  "Tags": [
    {
      "Key": "Project",
      "Value": "CostGuard"
    },
    {
      "Key": "Phase",
      "Value": "4"
    },
    {
      "Key": "Component",
      "Value": "AIAdvisor"
    }
  ]
}
```

**Item Structure:**
```json
{
  "query_hash": "a1b2c3d4e5f6...",
  "response": "Your total costs last month were $123.45...",
  "cached_at": 1704067200,
  "ttl": 1704153600,
  "confidence": 0.95,
  "recommendations": [...]
}
```

**Estimated Storage:** ~50 MB/month  
**Estimated Reads:** ~1,000/month  
**Estimated Writes:** ~600/month  
**Cost:** $0.00/month (within free tier)

### AWS Console Deployment

**Step 1: Navigate to DynamoDB**
1. Open AWS Console
2. Navigate to DynamoDB service
3. Click "Create table"

**Step 2: Create advisor-conversation-history**
1. Table name: `advisor-conversation-history`
2. Partition key: `session_id` (String)
3. Sort key: `timestamp` (Number)
4. Table settings: "Customize settings"
5. Capacity mode: "On-demand"
6. Enable TTL: Yes, attribute name: `ttl`
7. Add tags: Project=CostGuard, Phase=4, Component=AIAdvisor
8. Click "Create table"

**Step 3: Create advisor-cache**
1. Table name: `advisor-cache`
2. Partition key: `query_hash` (String)
3. Table settings: "Customize settings"
4. Capacity mode: "On-demand"
5. Enable TTL: Yes, attribute name: `ttl`
6. Add tags: Project=CostGuard, Phase=4, Component=AIAdvisor
7. Click "Create table"

### CDK Deployment

**Add to infrastructure/cdk_stack.py:**

```python
from aws_cdk import (
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    Duration
)

# Advisor Conversation History Table
conversation_history_table = dynamodb.Table(
    self, "AdvisorConversationHistory",
    table_name="advisor-conversation-history",
    partition_key=dynamodb.Attribute(
        name="session_id",
        type=dynamodb.AttributeType.STRING
    ),
    sort_key=dynamodb.Attribute(
        name="timestamp",
        type=dynamodb.AttributeType.NUMBER
    ),
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    time_to_live_attribute="ttl",
    removal_policy=RemovalPolicy.DESTROY,  # Change to RETAIN for production
    point_in_time_recovery=False  # Enable for production
)

# Advisor Cache Table
advisor_cache_table = dynamodb.Table(
    self, "AdvisorCache",
    table_name="advisor-cache",
    partition_key=dynamodb.Attribute(
        name="query_hash",
        type=dynamodb.AttributeType.STRING
    ),
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    time_to_live_attribute="ttl",
    removal_policy=RemovalPolicy.DESTROY,  # Change to RETAIN for production
    point_in_time_recovery=False  # Enable for production
)
```

---

## Task 17.2: Update IAM Role Permissions

### Required Permissions

**Add to Lambda Execution Role:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": [
        "arn:aws:bedrock:*:*:model/amazon.nova-lite-v1:0"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:DeleteItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/advisor-conversation-history",
        "arn:aws:dynamodb:*:*:table/advisor-cache"
      ]
    }
  ]
}
```

### AWS Console Deployment

**Step 1: Find Lambda Execution Role**
1. Open AWS Console
2. Navigate to Lambda service
3. Find your CostGuard Lambda function
4. Click "Configuration" tab
5. Click "Permissions" in left sidebar
6. Note the "Execution role" name (e.g., `CostGuardLambdaRole`)

**Step 2: Update IAM Role**
1. Navigate to IAM service
2. Click "Roles" in left sidebar
3. Search for your Lambda execution role
4. Click the role name
5. Click "Add permissions" → "Create inline policy"
6. Click "JSON" tab
7. Paste the policy JSON above
8. Click "Review policy"
9. Name: `Phase4AdvisorPolicy`
10. Click "Create policy"

### CDK Deployment

**Add to infrastructure/cdk_stack.py:**

```python
from aws_cdk import (
    aws_iam as iam
)

# Add Bedrock permissions to Lambda role
lambda_function.add_to_role_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        actions=["bedrock:InvokeModel"],
        resources=[
            "arn:aws:bedrock:*:*:model/amazon.nova-lite-v1:0"
        ]
    )
)

# Add DynamoDB permissions for Phase 4 tables
lambda_function.add_to_role_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        actions=[
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:Query",
            "dynamodb:DeleteItem"
        ],
        resources=[
            conversation_history_table.table_arn,
            advisor_cache_table.table_arn
        ]
    )
)
```

---

## Task 17.3: Update Lambda Environment Variables

### Required Environment Variables

**Add to Lambda Configuration:**

```json
{
  "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
  "ADVISOR_CACHE_TTL_HOURS": "24",
  "ADVISOR_CACHE_HIT_RATE_TARGET": "40"
}
```

### Variable Descriptions

| Variable | Value | Description |
|----------|-------|-------------|
| `BEDROCK_MODEL_ID` | `amazon.nova-lite-v1:0` | Bedrock model for AI advisor |
| `ADVISOR_CACHE_TTL_HOURS` | `24` | Cache TTL in hours (24 = 1 day) |
| `ADVISOR_CACHE_HIT_RATE_TARGET` | `40` | Target cache hit rate percentage |

### AWS Console Deployment

**Step 1: Update Lambda Environment Variables**
1. Open AWS Console
2. Navigate to Lambda service
3. Find your CostGuard Lambda function
4. Click "Configuration" tab
5. Click "Environment variables" in left sidebar
6. Click "Edit"
7. Add the 3 new environment variables
8. Click "Save"

### CDK Deployment

**Add to infrastructure/cdk_stack.py:**

```python
# Add Phase 4 environment variables
lambda_function.add_environment("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
lambda_function.add_environment("ADVISOR_CACHE_TTL_HOURS", "24")
lambda_function.add_environment("ADVISOR_CACHE_HIT_RATE_TARGET", "40")
```

---

## Task 17.4: Update API Gateway Configuration

### New API Routes

**Add 4 new routes to API Gateway:**

| Method | Path | Lambda Integration | Description |
|--------|------|-------------------|-------------|
| POST | `/api/advisor/query` | CostGuardLambda | Process natural language queries |
| GET | `/api/advisor/history` | CostGuardLambda | Retrieve conversation history |
| DELETE | `/api/advisor/history` | CostGuardLambda | Clear conversation history |
| GET | `/api/advisor/suggestions` | CostGuardLambda | Get proactive insights |

### AWS Console Deployment

**Step 1: Navigate to API Gateway**
1. Open AWS Console
2. Navigate to API Gateway service
3. Find your CostGuard API
4. Click the API name

**Step 2: Create /api/advisor Resource**
1. Click "Resources" in left sidebar
2. Select `/api` resource
3. Click "Actions" → "Create Resource"
4. Resource Name: `advisor`
5. Resource Path: `advisor`
6. Enable CORS: Yes
7. Click "Create Resource"

**Step 3: Create POST /api/advisor/query**
1. Select `/api/advisor` resource
2. Click "Actions" → "Create Resource"
3. Resource Name: `query`
4. Resource Path: `query`
5. Click "Create Resource"
6. Select `/api/advisor/query` resource
7. Click "Actions" → "Create Method"
8. Select "POST" from dropdown
9. Click checkmark
10. Integration type: Lambda Function
11. Lambda Function: Select your CostGuard Lambda
12. Click "Save"
13. Click "OK" to grant permissions

**Step 4: Create GET /api/advisor/history**
1. Select `/api/advisor` resource
2. Click "Actions" → "Create Resource"
3. Resource Name: `history`
4. Resource Path: `history`
5. Click "Create Resource"
6. Select `/api/advisor/history` resource
7. Click "Actions" → "Create Method"
8. Select "GET" from dropdown
9. Click checkmark
10. Integration type: Lambda Function
11. Lambda Function: Select your CostGuard Lambda
12. Click "Save"

**Step 5: Create DELETE /api/advisor/history**
1. Select `/api/advisor/history` resource
2. Click "Actions" → "Create Method"
3. Select "DELETE" from dropdown
4. Click checkmark
5. Integration type: Lambda Function
6. Lambda Function: Select your CostGuard Lambda
7. Click "Save"

**Step 6: Create GET /api/advisor/suggestions**
1. Select `/api/advisor` resource
2. Click "Actions" → "Create Resource"
3. Resource Name: `suggestions`
4. Resource Path: `suggestions`
5. Click "Create Resource"
6. Select `/api/advisor/suggestions` resource
7. Click "Actions" → "Create Method"
8. Select "GET" from dropdown
9. Click checkmark
10. Integration type: Lambda Function
11. Lambda Function: Select your CostGuard Lambda
12. Click "Save"

**Step 7: Deploy API**
1. Click "Actions" → "Deploy API"
2. Deployment stage: Select your stage (e.g., `prod`)
3. Click "Deploy"

### CDK Deployment

**Add to infrastructure/cdk_stack.py:**

```python
from aws_cdk import (
    aws_apigateway as apigateway
)

# Get existing API
api = apigateway.RestApi.from_rest_api_attributes(
    self, "ExistingAPI",
    rest_api_id="YOUR_API_ID",
    root_resource_id="YOUR_ROOT_RESOURCE_ID"
)

# Create /api/advisor resource
advisor_resource = api.root.add_resource("advisor")

# Create /api/advisor/query endpoint
query_resource = advisor_resource.add_resource("query")
query_resource.add_method(
    "POST",
    apigateway.LambdaIntegration(lambda_function),
    api_key_required=True
)

# Create /api/advisor/history endpoint
history_resource = advisor_resource.add_resource("history")
history_resource.add_method(
    "GET",
    apigateway.LambdaIntegration(lambda_function),
    api_key_required=True
)
history_resource.add_method(
    "DELETE",
    apigateway.LambdaIntegration(lambda_function),
    api_key_required=True
)

# Create /api/advisor/suggestions endpoint
suggestions_resource = advisor_resource.add_resource("suggestions")
suggestions_resource.add_method(
    "GET",
    apigateway.LambdaIntegration(lambda_function),
    api_key_required=True
)
```

---

## Task 17.5: Update CDK Infrastructure Code

### Complete CDK Stack Update

**File: infrastructure/cdk_stack.py**

```python
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_apigateway as apigateway,
    RemovalPolicy,
    Duration
)
from constructs import Construct

class CostGuardStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ... existing Phase 1-3 resources ...

        # ===== PHASE 4: AI COST ADVISOR =====

        # DynamoDB Tables
        conversation_history_table = dynamodb.Table(
            self, "AdvisorConversationHistory",
            table_name="advisor-conversation-history",
            partition_key=dynamodb.Attribute(
                name="session_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY
        )

        advisor_cache_table = dynamodb.Table(
            self, "AdvisorCache",
            table_name="advisor-cache",
            partition_key=dynamodb.Attribute(
                name="query_hash",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY
        )

        # Update Lambda permissions
        lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=[
                    "arn:aws:bedrock:*:*:model/amazon.nova-lite-v1:0"
                ]
            )
        )

        lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:Query",
                    "dynamodb:DeleteItem"
                ],
                resources=[
                    conversation_history_table.table_arn,
                    advisor_cache_table.table_arn
                ]
            )
        )

        # Update Lambda environment variables
        lambda_function.add_environment("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
        lambda_function.add_environment("ADVISOR_CACHE_TTL_HOURS", "24")
        lambda_function.add_environment("ADVISOR_CACHE_HIT_RATE_TARGET", "40")

        # API Gateway routes
        advisor_resource = api.root.add_resource("advisor")

        query_resource = advisor_resource.add_resource("query")
        query_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(lambda_function),
            api_key_required=True
        )

        history_resource = advisor_resource.add_resource("history")
        history_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(lambda_function),
            api_key_required=True
        )
        history_resource.add_method(
            "DELETE",
            apigateway.LambdaIntegration(lambda_function),
            api_key_required=True
        )

        suggestions_resource = advisor_resource.add_resource("suggestions")
        suggestions_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(lambda_function),
            api_key_required=True
        )
```

### Deployment Commands

```bash
# Navigate to infrastructure directory
cd infrastructure

# Install dependencies (if not already done)
npm install

# Synthesize CloudFormation template
cdk synth

# Review changes
cdk diff

# Deploy stack
cdk deploy

# Confirm deployment
# Type 'y' when prompted
```

---

## Verification Steps

### 1. Verify DynamoDB Tables

```bash
# List tables
aws dynamodb list-tables

# Describe advisor-conversation-history table
aws dynamodb describe-table --table-name advisor-conversation-history

# Describe advisor-cache table
aws dynamodb describe-table --table-name advisor-cache
```

**Expected Output:**
- Both tables should exist
- Billing mode: PAY_PER_REQUEST
- TTL enabled on `ttl` attribute

### 2. Verify IAM Permissions

```bash
# Get Lambda function configuration
aws lambda get-function-configuration --function-name CostGuardLambda

# Get IAM role policies
aws iam list-role-policies --role-name CostGuardLambdaRole
aws iam get-role-policy --role-name CostGuardLambdaRole --policy-name Phase4AdvisorPolicy
```

**Expected Output:**
- Bedrock InvokeModel permission present
- DynamoDB permissions for Phase 4 tables present

### 3. Verify Lambda Environment Variables

```bash
# Get Lambda environment variables
aws lambda get-function-configuration --function-name CostGuardLambda --query 'Environment.Variables'
```

**Expected Output:**
```json
{
  "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
  "ADVISOR_CACHE_TTL_HOURS": "24",
  "ADVISOR_CACHE_HIT_RATE_TARGET": "40",
  ...
}
```

### 4. Verify API Gateway Routes

```bash
# Get API Gateway resources
aws apigateway get-resources --rest-api-id YOUR_API_ID
```

**Expected Output:**
- `/api/advisor` resource exists
- `/api/advisor/query` resource with POST method
- `/api/advisor/history` resource with GET and DELETE methods
- `/api/advisor/suggestions` resource with GET method

### 5. Test API Endpoints

```bash
# Test POST /api/advisor/query
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "What were my costs last month?"}' \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/advisor/query"

# Test GET /api/advisor/history
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/advisor/history"

# Test GET /api/advisor/suggestions
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/advisor/suggestions"
```

**Expected Output:**
- All endpoints return 200 OK
- Responses contain expected JSON structure
- No 403 Forbidden or 500 Internal Server Error

---

## Rollback Plan

### If Deployment Fails

**Step 1: Identify Issue**
- Check CloudWatch Logs for Lambda errors
- Review API Gateway execution logs
- Verify DynamoDB table creation

**Step 2: Rollback CDK Stack**
```bash
# Rollback to previous version
cdk deploy --rollback

# Or destroy Phase 4 resources
cdk destroy --exclusively CostGuardStack/AdvisorConversationHistory
cdk destroy --exclusively CostGuardStack/AdvisorCache
```

**Step 3: Manual Cleanup (if needed)**
```bash
# Delete DynamoDB tables
aws dynamodb delete-table --table-name advisor-conversation-history
aws dynamodb delete-table --table-name advisor-cache

# Remove IAM policy
aws iam delete-role-policy --role-name CostGuardLambdaRole --policy-name Phase4AdvisorPolicy

# Remove Lambda environment variables
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables={...}  # Remove Phase 4 variables

# Delete API Gateway resources
aws apigateway delete-resource --rest-api-id YOUR_API_ID --resource-id ADVISOR_RESOURCE_ID
```

---

## Cost Monitoring

### CloudWatch Metrics to Monitor

**Bedrock API Usage:**
- Metric: `bedrock:InvokeModel`
- Alarm: > 500 calls/month
- Action: SNS notification

**DynamoDB Usage:**
- Metric: `ConsumedReadCapacityUnits`, `ConsumedWriteCapacityUnits`
- Alarm: Approaching free tier limits
- Action: SNS notification

**Lambda Invocations:**
- Metric: `Invocations`
- Alarm: > 1,000 Phase 4 invocations/month
- Action: SNS notification

### Cost Alerts

**Create Budget Alert:**
```bash
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget file://phase4-budget.json \
  --notifications-with-subscribers file://phase4-notifications.json
```

**phase4-budget.json:**
```json
{
  "BudgetName": "Phase4-AI-Advisor",
  "BudgetLimit": {
    "Amount": "1.00",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}
```

---

## Troubleshooting

### Issue: Bedrock Permission Denied

**Error:** `AccessDeniedException: User is not authorized to perform: bedrock:InvokeModel`

**Solution:**
1. Verify IAM role has Bedrock InvokeModel permission
2. Check resource ARN matches model ID
3. Ensure Bedrock is enabled in your AWS account
4. Verify region supports Bedrock Nova Lite

### Issue: DynamoDB Table Not Found

**Error:** `ResourceNotFoundException: Requested resource not found`

**Solution:**
1. Verify table names match exactly (case-sensitive)
2. Check tables exist in correct region
3. Verify Lambda has DynamoDB permissions
4. Check table status is ACTIVE

### Issue: API Gateway 403 Forbidden

**Error:** `{"message":"Forbidden"}`

**Solution:**
1. Verify API key is correct
2. Check API key is associated with usage plan
3. Verify Lambda has correct permissions
4. Check API Gateway resource policy

### Issue: Lambda Timeout

**Error:** `Task timed out after 30.00 seconds`

**Solution:**
1. Increase Lambda timeout (Configuration → General → Timeout)
2. Optimize Bedrock prompt length
3. Check network connectivity to Bedrock
4. Review CloudWatch Logs for bottlenecks

---

## Next Steps

After completing infrastructure deployment:

1. **Run Integration Tests (Task 18)**
   - Test end-to-end advisor workflow
   - Verify backward compatibility
   - Validate cache performance
   - Test proactive insights

2. **Monitor Performance**
   - Track Bedrock API usage
   - Monitor cache hit rates
   - Review response times
   - Analyze user query patterns

3. **Optimize Costs**
   - Tune cache TTL
   - Optimize Bedrock prompts
   - Adjust cache hit rate target
   - Review DynamoDB usage

---

## See Also

- **[README.md](./README.md)** - Phase 4 overview and features
- **[implementation-summary.md](./implementation-summary.md)** - Test results and deliverables
- **[specification.md](./specification.md)** - Complete Phase 4 Kiro specification
- **[../../API_EXAMPLES.md](../../API_EXAMPLES.md)** - API usage examples
- **[../architecture.md](../architecture.md)** - System architecture

---

**Last Updated:** January 2026  
**Status:** Pending Deployment  
**Next Milestone:** Integration Testing (Task 18)
