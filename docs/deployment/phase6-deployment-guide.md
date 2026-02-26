# Phase 6: AI/ML Workload Cost Management - Deployment Guide

**Version:** 1.0  
**Last Updated:** February 2026  
**Status:** Ready for Deployment  
**Estimated Deployment Time:** 3-4 hours

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Architecture Overview](#architecture-overview)
4. [Infrastructure Setup](#infrastructure-setup)
5. [IAM Permissions](#iam-permissions)
6. [Lambda Configuration](#lambda-configuration)
7. [DynamoDB Tables](#dynamodb-tables)
8. [API Gateway Routes](#api-gateway-routes)
9. [Environment Variables](#environment-variables)
10. [Multi-Account Setup](#multi-account-setup)
11. [Deployment Checklist](#deployment-checklist)
12. [Testing & Validation](#testing--validation)
13. [Monitoring & Alerts](#monitoring--alerts)
14. [Cost Management](#cost-management)
15. [Troubleshooting](#troubleshooting)
16. [Rollback Procedures](#rollback-procedures)

---

## Overview

Phase 6 adds AI/ML-specific cost management capabilities to CostGuard AI, focusing on GPU cost tracking, workload classification, and ML optimization. This deployment guide provides step-by-step instructions for deploying Phase 6 infrastructure on AWS.

**Key Features:**
- GPU cost tracking by workload type (training, inference, idle)
- Automated workload classification using CloudWatch metrics
- Cost-per-inference and cost-per-training calculations
- Spot instance recommendations for training workloads
- SageMaker and Bedrock cost tracking
- Multi-account GPU cost aggregation

**Deployment Approach:**
- Incremental deployment with backward compatibility
- No changes to existing Phase 1-5 infrastructure
- Free Tier compliant (~$0.50/month additional cost)
- Safety-first with dry-run mode enabled by default

---

## Prerequisites


### Required Access

- [ ] AWS account with administrator access
- [ ] AWS CLI configured with appropriate credentials
- [ ] Access to Cost Explorer API
- [ ] Access to CloudWatch API
- [ ] Access to EC2, SageMaker, and Bedrock APIs
- [ ] Access to Pricing API
- [ ] Existing CostGuard infrastructure (Phases 1-5) deployed

### Required Tools

- [ ] AWS CLI v2.x or higher
- [ ] Python 3.11 or higher
- [ ] AWS CDK CLI (optional, for CDK deployment)
- [ ] Git (for version control)
- [ ] jq (for JSON processing in scripts)

### Existing Infrastructure

Phase 6 builds on existing CostGuard infrastructure:

- **Phase 1**: Cost Explorer integration, DynamoDB tables, Lambda function
- **Phase 2**: AI forecasting with Bedrock
- **Phase 3**: Automated prevention system
- **Phase 4**: AI Advisor
- **Phase 5**: Multi-account support

**Verify existing infrastructure:**

```bash
# Check Lambda function exists
aws lambda get-function --function-name CostGuardLambda

# Check existing DynamoDB tables
aws dynamodb list-tables | grep costguard

# Check API Gateway
aws apigatewayv2 get-apis | grep CostGuard
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  API Gateway                                 │
│  Phase 6 Routes:                                            │
│  - GET  /api/ai-ml/gpu-costs                                │
│  - GET  /api/ai-ml/workload-classification                  │
│  - POST /api/ai-ml/workload-classification                  │
│  - GET  /api/ai-ml/cost-per-inference                       │
│  - GET  /api/ai-ml/cost-per-training                        │
│  - GET  /api/ai-ml/spot-recommendations                     │
│  - GET  /api/ai-ml/sagemaker-costs                          │
│  - GET  /api/ai-ml/bedrock-costs                            │
│  - POST /api/ai-ml/gpu-prevention                           │
│  - GET  /api/ai-ml/multi-account/gpu-costs                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Function (CostGuardLambda)               │
│  - Existing handler extended with AI/ML routes              │
│  - Memory: 512 MB                                           │
│  - Timeout: 30 seconds                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            AI/ML Cost Services                               │
│  - GPUCostTracker                                           │
│  - WorkloadClassifier                                       │
│  - CostPerInferenceCalculator                               │
│  - CostPerTrainingCalculator                                │
│  - SpotInstanceRecommender                                  │
│  - SageMakerCostTracker                                     │
│  - BedrockCostTracker                                       │
└─┬───────┬────────┬────────┬────────┬────────┬──────────────┘
  │       │        │        │        │        │
  ▼       ▼        ▼        ▼        ▼        ▼
┌────────────────────────────────────────────────────────────┐
│  AWS Services:                                              │
│  - Cost Explorer (GPU costs)                                │
│  - CloudWatch (GPU metrics)                                 │
│  - EC2 API (instance metadata)                              │
│  - SageMaker API (training/inference jobs)                  │
│  - Bedrock API (model invocations)                          │
│  - Pricing API (spot prices)                                │
│  - DynamoDB (3 new tables)                                  │
└────────────────────────────────────────────────────────────┘
```

### New Components

**DynamoDB Tables (3 new):**
1. `costguard-gpu-costs` - GPU cost data with workload classifications
2. `costguard-workload-classifications` - Workload classification history
3. `costguard-spot-recommendations` - Spot instance recommendations

**Lambda Services (7 new):**
1. `GPUCostTracker` - Track GPU instance costs
2. `WorkloadClassifier` - Classify workloads (training/inference/idle)
3. `CostPerInferenceCalculator` - Calculate cost per inference
4. `CostPerTrainingCalculator` - Calculate cost per training job
5. `SpotInstanceRecommender` - Generate spot instance recommendations
6. `SageMakerCostTracker` - Track SageMaker costs
7. `BedrockCostTracker` - Track Bedrock costs

**API Gateway Routes (10+ new):**
- GPU cost tracking endpoints (3)
- Workload classification endpoints (2)
- Cost-per-inference endpoints (2)
- Cost-per-training endpoints (2)
- Spot recommendation endpoints (2)
- SageMaker cost endpoints (2)
- Bedrock cost endpoints (2)
- GPU prevention endpoints (2)
- Multi-account GPU endpoints (3)

---

## Infrastructure Setup

### Step 1: Create DynamoDB Tables (20 minutes)

Phase 6 requires 3 new DynamoDB tables for storing GPU cost data, workload classifications, and spot recommendations.

#### Table 1: costguard-gpu-costs

Stores GPU cost data with workload classifications.

```bash
aws dynamodb create-table \
  --table-name costguard-gpu-costs \
  --attribute-definitions \
    AttributeName=date,AttributeType=S \
    AttributeName=instance_id,AttributeType=S \
  --key-schema \
    AttributeName=date,KeyType=HASH \
    AttributeName=instance_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Project,Value=CostGuardAI Key=Phase,Value=6
```

**Verify:**
```bash
aws dynamodb describe-table --table-name costguard-gpu-costs
```

#### Table 2: costguard-workload-classifications

Stores workload classification history for audit purposes.

```bash
aws dynamodb create-table \
  --table-name costguard-workload-classifications \
  --attribute-definitions \
    AttributeName=instance_id,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
  --key-schema \
    AttributeName=instance_id,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Project,Value=CostGuardAI Key=Phase,Value=6
```

**Verify:**
```bash
aws dynamodb describe-table --table-name costguard-workload-classifications
```

#### Table 3: costguard-spot-recommendations

Stores spot instance recommendations with savings estimates.

```bash
aws dynamodb create-table \
  --table-name costguard-spot-recommendations \
  --attribute-definitions \
    AttributeName=workload_id,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
  --key-schema \
    AttributeName=workload_id,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --time-to-live-specification \
    Enabled=true,AttributeName=ttl \
  --tags Key=Project,Value=CostGuardAI Key=Phase,Value=6
```

**Verify:**
```bash
aws dynamodb describe-table --table-name costguard-spot-recommendations
```

**Verify all tables created:**
```bash
aws dynamodb list-tables | grep costguard
```

Expected output should include:
- costguard-cost-data (Phase 1)
- costguard-forecast-cache (Phase 2)
- costguard-prevention-config (Phase 3)
- costguard-resource-inventory (Phase 3)
- costguard-prevention-audit (Phase 3)
- costguard-approval-requests (Phase 3)
- costguard-gpu-costs (Phase 6 - NEW)
- costguard-workload-classifications (Phase 6 - NEW)
- costguard-spot-recommendations (Phase 6 - NEW)

---

## IAM Permissions

Phase 6 requires additional IAM permissions for GPU cost tracking, CloudWatch metrics, and AWS service APIs.

### Step 2: Update Lambda Execution Role (15 minutes)

Add the following permissions to your existing Lambda execution role (`CostGuardLambdaExecutionRole`).


#### Create IAM Policy Document

Create a file named `phase6-iam-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CostExplorerGPUAccess",
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast"
      ],
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "ce:InstanceType": [
            "p3.*",
            "p4.*",
            "p4d.*",
            "p5.*",
            "g4.*",
            "g5.*",
            "g6.*"
          ]
        }
      }
    },
    {
      "Sid": "CloudWatchGPUMetrics",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EC2GPUInstanceAccess",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeTags",
        "ec2:StopInstances",
        "ec2:TerminateInstances"
      ],
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "ec2:ResourceTag/Environment": "production",
          "ec2:ResourceTag/CostGuard": "protected"
        }
      }
    },
    {
      "Sid": "SageMakerAccess",
      "Effect": "Allow",
      "Action": [
        "sagemaker:DescribeTrainingJob",
        "sagemaker:ListTrainingJobs",
        "sagemaker:DescribeEndpoint",
        "sagemaker:ListEndpoints",
        "sagemaker:DescribeNotebookInstance",
        "sagemaker:ListNotebookInstances"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BedrockAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:GetModelInvocationLoggingConfiguration",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PricingAPIAccess",
      "Effect": "Allow",
      "Action": [
        "pricing:GetProducts",
        "pricing:DescribeServices"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DynamoDBPhase6Access",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/costguard-gpu-costs",
        "arn:aws:dynamodb:*:*:table/costguard-workload-classifications",
        "arn:aws:dynamodb:*:*:table/costguard-spot-recommendations",
        "arn:aws:dynamodb:*:*:table/costguard-gpu-costs/index/*",
        "arn:aws:dynamodb:*:*:table/costguard-workload-classifications/index/*",
        "arn:aws:dynamodb:*:*:table/costguard-spot-recommendations/index/*"
      ]
    }
  ]
}
```

#### Attach Policy to Lambda Role

```bash
# Create the policy
aws iam create-policy \
  --policy-name CostGuardPhase6Policy \
  --policy-document file://phase6-iam-policy.json \
  --description "Phase 6 AI/ML workload cost management permissions"

# Get the policy ARN (replace ACCOUNT_ID with your AWS account ID)
POLICY_ARN="arn:aws:iam::ACCOUNT_ID:policy/CostGuardPhase6Policy"

# Attach policy to Lambda execution role
aws iam attach-role-policy \
  --role-name CostGuardLambdaExecutionRole \
  --policy-arn $POLICY_ARN
```

**Verify:**
```bash
aws iam list-attached-role-policies --role-name CostGuardLambdaExecutionRole
```

### IAM Permission Summary

| Service | Permissions | Purpose |
|---------|-------------|---------|
| **Cost Explorer** | `ce:GetCostAndUsage`, `ce:GetCostForecast` | Retrieve GPU instance costs |
| **CloudWatch** | `cloudwatch:GetMetricStatistics`, `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics` | Retrieve GPU utilization metrics |
| **EC2** | `ec2:DescribeInstances`, `ec2:DescribeInstanceTypes`, `ec2:DescribeTags` | Get GPU instance metadata |
| **EC2 (Actions)** | `ec2:StopInstances`, `ec2:TerminateInstances` | Stop/terminate idle GPU instances |
| **SageMaker** | `sagemaker:Describe*`, `sagemaker:List*` | Track SageMaker training and inference costs |
| **Bedrock** | `bedrock:GetModelInvocationLoggingConfiguration`, `bedrock:ListFoundationModels` | Track Bedrock model invocation costs |
| **Pricing API** | `pricing:GetProducts`, `pricing:DescribeServices` | Get spot instance pricing |
| **DynamoDB** | Full access to Phase 6 tables | Store GPU costs, classifications, recommendations |

**Security Notes:**
- EC2 stop/terminate actions include conditions to protect production resources
- All permissions follow least-privilege principle
- Cost Explorer access is scoped to GPU instance types only
- CloudWatch metrics access is read-only

---

## Lambda Configuration

### Step 3: Update Lambda Function (30 minutes)

Phase 6 extends the existing Lambda function with new AI/ML cost tracking services.

#### Package Lambda Code

```bash
# Navigate to project root
cd /path/to/costguard-ai

# Create deployment package
cd src
zip -r ../lambda_deployment_phase6.zip . -x "*.pyc" -x "__pycache__/*"
cd ..

# Verify package size (should be < 50 MB)
ls -lh lambda_deployment_phase6.zip
```

#### Update Lambda Function Code

```bash
# Upload new code to Lambda
aws lambda update-function-code \
  --function-name CostGuardLambda \
  --zip-file fileb://lambda_deployment_phase6.zip

# Wait for update to complete
aws lambda wait function-updated \
  --function-name CostGuardLambda
```

**Verify:**
```bash
aws lambda get-function --function-name CostGuardLambda
```

#### Update Lambda Configuration

Ensure Lambda has sufficient resources for Phase 6:

```bash
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --timeout 30 \
  --memory-size 512
```

**Configuration Requirements:**
- **Timeout**: 30 seconds (allows for Cost Explorer API calls with retries)
- **Memory**: 512 MB (sufficient for GPU cost calculations)
- **Runtime**: Python 3.11 (already configured in Phase 1)

---

## DynamoDB Tables

### Step 4: Verify Table Configuration (5 minutes)

Verify that all Phase 6 DynamoDB tables are properly configured.

#### Check Table Status

```bash
# Check all Phase 6 tables
for table in costguard-gpu-costs costguard-workload-classifications costguard-spot-recommendations; do
  echo "Checking $table..."
  aws dynamodb describe-table --table-name $table --query 'Table.[TableName,TableStatus,BillingModeSummary.BillingMode]' --output table
done
```

Expected output:
- TableStatus: ACTIVE
- BillingMode: PAY_PER_REQUEST

#### Enable TTL on Spot Recommendations Table

```bash
aws dynamodb update-time-to-live \
  --table-name costguard-spot-recommendations \
  --time-to-live-specification "Enabled=true, AttributeName=ttl"
```

**Verify TTL:**
```bash
aws dynamodb describe-time-to-live --table-name costguard-spot-recommendations
```

#### Table Schema Summary

**costguard-gpu-costs:**
- Partition Key: `date` (String, YYYY-MM-DD)
- Sort Key: `instance_id` (String)
- Attributes: `instance_type`, `workload_type`, `cost`, `gpu_hours`, `utilization`, `classification_confidence`

**costguard-workload-classifications:**
- Partition Key: `instance_id` (String)
- Sort Key: `timestamp` (Number, Unix timestamp)
- Attributes: `workload_type`, `confidence`, `classification_method`, `gpu_utilization_avg`, `gpu_utilization_pattern`

**costguard-spot-recommendations:**
- Partition Key: `workload_id` (String)
- Sort Key: `timestamp` (Number, Unix timestamp)
- TTL Attribute: `ttl` (Number, Unix timestamp)
- Attributes: `current_instance`, `recommended_spot_instance`, `savings`, `savings_percent`, `interruption_risk`

---

## API Gateway Routes

### Step 5: Configure API Gateway (30 minutes)

Add Phase 6 routes to your existing API Gateway.

#### Get API Gateway ID

```bash
# List APIs and find CostGuard API
aws apigatewayv2 get-apis --query 'Items[?Name==`CostGuardAPI`].[ApiId,Name]' --output table

# Save API ID
API_ID="your-api-gateway-id"
```

#### Get Lambda Integration ID

```bash
# Get existing Lambda integration
aws apigatewayv2 get-integrations --api-id $API_ID --query 'Items[0].IntegrationId' --output text

# Save integration ID
INTEGRATION_ID="your-integration-id"
```

#### Create Phase 6 Routes

Create a script `create-phase6-routes.sh`:

```bash
#!/bin/bash

API_ID="your-api-gateway-id"
INTEGRATION_ID="your-integration-id"

# GPU Cost Tracking Routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/gpu-costs" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/gpu-utilization" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/idle-gpus" \
  --target "integrations/$INTEGRATION_ID"

# Workload Classification Routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/workload-classification" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "POST /api/ai-ml/workload-classification" \
  --target "integrations/$INTEGRATION_ID"

# Cost-Per-Inference Routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/cost-per-inference" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/inference-trends" \
  --target "integrations/$INTEGRATION_ID"

# Cost-Per-Training Routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/cost-per-training" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/training-comparison" \
  --target "integrations/$INTEGRATION_ID"

# Spot Instance Recommendation Routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/spot-recommendations" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/spot-savings" \
  --target "integrations/$INTEGRATION_ID"

# SageMaker Cost Routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/sagemaker-costs" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/sagemaker-idle-endpoints" \
  --target "integrations/$INTEGRATION_ID"

# Bedrock Cost Routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/bedrock-costs" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/bedrock-cost-per-invocation" \
  --target "integrations/$INTEGRATION_ID"

# GPU Prevention Routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "POST /api/ai-ml/gpu-prevention" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/gpu-cost-savings" \
  --target "integrations/$INTEGRATION_ID"

# Multi-Account GPU Routes
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/multi-account/gpu-costs" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/multi-account/gpu-utilization" \
  --target "integrations/$INTEGRATION_ID"

aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key "GET /api/ai-ml/multi-account/top-gpu-accounts" \
  --target "integrations/$INTEGRATION_ID"

echo "Phase 6 routes created successfully!"
```

Run the script:

```bash
chmod +x create-phase6-routes.sh
./create-phase6-routes.sh
```

**Verify routes:**
```bash
aws apigatewayv2 get-routes --api-id $API_ID --query 'Items[?contains(RouteKey, `ai-ml`)].RouteKey' --output table
```

#### Deploy API Gateway

```bash
# Create new deployment
aws apigatewayv2 create-deployment \
  --api-id $API_ID \
  --stage-name prod \
  --description "Phase 6: AI/ML Workload Cost Management"

# Get API endpoint
aws apigatewayv2 get-api --api-id $API_ID --query 'ApiEndpoint' --output text
```

---

## Environment Variables

### Step 6: Configure Lambda Environment Variables (10 minutes)

Add Phase 6-specific environment variables to Lambda function.


#### Phase 6 Environment Variables

```bash
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{
    COST_DATA_TABLE=costguard-cost-data,
    FORECAST_CACHE_TABLE=costguard-forecast-cache,
    PREVENTION_CONFIG_TABLE=costguard-prevention-config,
    RESOURCE_INVENTORY_TABLE=costguard-resource-inventory,
    PREVENTION_AUDIT_TABLE=costguard-prevention-audit,
    APPROVAL_REQUESTS_TABLE=costguard-approval-requests,
    GPU_COSTS_TABLE=costguard-gpu-costs,
    WORKLOAD_CLASSIFICATIONS_TABLE=costguard-workload-classifications,
    SPOT_RECOMMENDATIONS_TABLE=costguard-spot-recommendations,
    CACHE_TTL_HOURS=24,
    CLASSIFICATION_CONFIDENCE_THRESHOLD=0.8,
    IDLE_GPU_THRESHOLD_PERCENT=10.0,
    SPOT_INTERRUPTION_RISK_THRESHOLD=0.2,
    GPU_PREVENTION_ENABLED=false,
    GPU_PREVENTION_DRY_RUN=true,
    PREVENTION_ENABLED=false,
    DRY_RUN_MODE=true,
    APPROVAL_REQUIRED=true,
    AWS_REGION=$AWS_REGION,
    LOG_LEVEL=INFO
  }"
```

#### Environment Variable Descriptions

| Variable | Default | Description |
|----------|---------|-------------|
| `GPU_COSTS_TABLE` | `costguard-gpu-costs` | DynamoDB table for GPU cost data |
| `WORKLOAD_CLASSIFICATIONS_TABLE` | `costguard-workload-classifications` | DynamoDB table for workload classifications |
| `SPOT_RECOMMENDATIONS_TABLE` | `costguard-spot-recommendations` | DynamoDB table for spot recommendations |
| `CACHE_TTL_HOURS` | `24` | Cache TTL for GPU cost queries (hours) |
| `CLASSIFICATION_CONFIDENCE_THRESHOLD` | `0.8` | Minimum confidence for automated classification |
| `IDLE_GPU_THRESHOLD_PERCENT` | `10.0` | GPU utilization threshold for idle detection (%) |
| `SPOT_INTERRUPTION_RISK_THRESHOLD` | `0.2` | Maximum acceptable spot interruption risk |
| `GPU_PREVENTION_ENABLED` | `false` | Enable GPU prevention actions (stop/terminate idle GPUs) |
| `GPU_PREVENTION_DRY_RUN` | `true` | Dry run mode for GPU prevention (log actions without executing) |

**Safety Defaults:**
- `GPU_PREVENTION_ENABLED=false` - Prevention disabled by default
- `GPU_PREVENTION_DRY_RUN=true` - Dry run mode enabled by default
- `APPROVAL_REQUIRED=true` - Approval required for all actions

**Verify:**
```bash
aws lambda get-function-configuration --function-name CostGuardLambda --query 'Environment.Variables' --output json
```

---

## Multi-Account Setup

### Step 7: Configure Multi-Account GPU Tracking (Optional, 30 minutes)

If you want to aggregate GPU costs across multiple AWS accounts, follow these steps.

#### Prerequisites

- AWS Organizations configured
- Member accounts with GPU instances
- Cross-account IAM roles set up (from Phase 5)

#### Create Cross-Account Role in Member Accounts

Use the existing `CostGuardCollectorRole` from Phase 5, or create a new role with GPU-specific permissions.

**Member Account Role Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:GetMetricData",
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceTypes",
        "sagemaker:DescribeTrainingJob",
        "sagemaker:ListTrainingJobs",
        "sagemaker:DescribeEndpoint",
        "sagemaker:ListEndpoints"
      ],
      "Resource": "*"
    }
  ]
}
```

**Trust Relationship:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::MANAGEMENT_ACCOUNT_ID:role/CostGuardLambdaExecutionRole"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "your-external-id"
        }
      }
    }
  ]
}
```

#### Deploy Role to Member Accounts

```bash
# Deploy using CloudFormation StackSet (from Phase 5)
aws cloudformation create-stack-set \
  --stack-set-name CostGuardPhase6MemberRole \
  --template-body file://infrastructure/member_account_role_template.yaml \
  --parameters \
    ParameterKey=ManagementAccountId,ParameterValue=MANAGEMENT_ACCOUNT_ID \
    ParameterKey=ExternalId,ParameterValue=your-external-id \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy to member accounts
aws cloudformation create-stack-instances \
  --stack-set-name CostGuardPhase6MemberRole \
  --accounts 123456789012 234567890123 345678901234 \
  --regions us-east-1
```

#### Test Multi-Account Access

```bash
# Test cross-account role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::MEMBER_ACCOUNT_ID:role/CostGuardCollectorRole \
  --role-session-name test-session \
  --external-id your-external-id
```

---

## Deployment Checklist

### Pre-Deployment Checklist

- [ ] AWS CLI configured with appropriate credentials
- [ ] Existing CostGuard infrastructure (Phases 1-5) deployed and tested
- [ ] IAM permissions reviewed and approved
- [ ] DynamoDB table names verified (no conflicts)
- [ ] Lambda function has sufficient resources (512 MB memory, 30s timeout)
- [ ] API Gateway has capacity for additional routes
- [ ] Cost budget allocated for Phase 6 (~$0.50/month)

### Deployment Steps Checklist

- [ ] **Step 1**: Create 3 DynamoDB tables (costguard-gpu-costs, costguard-workload-classifications, costguard-spot-recommendations)
- [ ] **Step 2**: Update Lambda IAM role with Phase 6 permissions
- [ ] **Step 3**: Package and deploy Lambda code with Phase 6 services
- [ ] **Step 4**: Verify DynamoDB table configuration and enable TTL
- [ ] **Step 5**: Create 20+ API Gateway routes for Phase 6 endpoints
- [ ] **Step 6**: Configure Lambda environment variables
- [ ] **Step 7**: (Optional) Configure multi-account GPU tracking

### Post-Deployment Checklist

- [ ] All DynamoDB tables in ACTIVE status
- [ ] Lambda function updated successfully
- [ ] API Gateway routes created and deployed
- [ ] Environment variables configured correctly
- [ ] IAM permissions attached to Lambda role
- [ ] CloudWatch logs showing successful Lambda invocations
- [ ] Test API endpoints return expected responses
- [ ] Backward compatibility verified (Phases 1-5 still work)
- [ ] Cost monitoring configured
- [ ] Documentation updated

---

## Testing & Validation

### Step 8: Test Phase 6 Endpoints (45 minutes)

After deployment, test all Phase 6 endpoints to ensure they work correctly.

#### Get API Endpoint URL

```bash
API_ENDPOINT=$(aws apigatewayv2 get-api --api-id $API_ID --query 'ApiEndpoint' --output text)
echo "API Endpoint: $API_ENDPOINT"
```

#### Test 1: GPU Costs Endpoint

```bash
curl -X GET "$API_ENDPOINT/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Expected Response:**
```json
{
  "gpu_costs": [...],
  "total_cost": 1234.56,
  "total_gpu_hours": 120.5,
  "average_cost_per_gpu_hour": 10.24
}
```

#### Test 2: Idle GPUs Endpoint

```bash
curl -X GET "$API_ENDPOINT/api/ai-ml/idle-gpus?start_date=2024-01-01&end_date=2024-01-31&threshold=10" \
  -H "X-API-Key: your-api-key-here"
```

**Expected Response:**
```json
{
  "idle_gpus": [...],
  "count": 3,
  "total_wasted_cost": 1487.25,
  "threshold": 10.0
}
```

#### Test 3: Workload Classification Endpoint

```bash
curl -X GET "$API_ENDPOINT/api/ai-ml/workload-classification?instance_id=i-1234567890abcdef0&start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Expected Response:**
```json
{
  "classification": {
    "instance_id": "i-1234567890abcdef0",
    "workload_type": "training",
    "confidence": 0.95,
    "classification_method": "cloudwatch-metrics"
  }
}
```

#### Test 4: Cost-Per-Inference Endpoint

```bash
curl -X GET "$API_ENDPOINT/api/ai-ml/cost-per-inference?start_date=2024-01-01&end_date=2024-01-31&model=bert-base-uncased" \
  -H "X-API-Key: your-api-key-here"
```

**Expected Response:**
```json
{
  "model": "bert-base-uncased",
  "total_requests": 1000000,
  "total_cost": 1234.56,
  "cost_per_inference": 0.00123456
}
```

#### Test 5: Spot Recommendations Endpoint

```bash
curl -X GET "$API_ENDPOINT/api/ai-ml/spot-recommendations?workload_id=i-1234567890abcdef0" \
  -H "X-API-Key: your-api-key-here"
```

**Expected Response:**
```json
{
  "workload_id": "i-1234567890abcdef0",
  "recommendations": [
    {
      "current_instance": "p3.2xlarge",
      "recommended_spot_instance": "p3.2xlarge",
      "savings": 7.14,
      "savings_percent": 70.0
    }
  ]
}
```

#### Test 6: SageMaker Costs Endpoint

```bash
curl -X GET "$API_ENDPOINT/api/ai-ml/sagemaker-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Expected Response:**
```json
{
  "training_costs": 5000.00,
  "inference_costs": 2000.00,
  "notebook_costs": 500.00,
  "total_cost": 7500.00
}
```

#### Test 7: Bedrock Costs Endpoint

```bash
curl -X GET "$API_ENDPOINT/api/ai-ml/bedrock-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Expected Response:**
```json
{
  "models": [
    {
      "model_id": "anthropic.claude-v2",
      "invocations": 50000,
      "total_cost": 187.50
    }
  ],
  "totals": {
    "total_cost": 307.50,
    "total_invocations": 150000
  }
}
```

#### Test 8: Backward Compatibility

Test existing Phase 1-5 endpoints to ensure no breaking changes:

```bash
# Phase 1: Historical costs
curl -X GET "$API_ENDPOINT/api/costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"

# Phase 2: Forecasts
curl -X GET "$API_ENDPOINT/api/forecast?days=7" \
  -H "X-API-Key: your-api-key-here"

# Phase 3: Prevention actions
curl -X GET "$API_ENDPOINT/api/prevention/actions" \
  -H "X-API-Key: your-api-key-here"

# Phase 4: AI Advisor
curl -X POST "$API_ENDPOINT/api/advisor/query" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"query": "What were my costs yesterday?"}'
```

**Verify:**
- [ ] All Phase 1-5 endpoints return expected responses
- [ ] No errors in CloudWatch logs
- [ ] Response times within acceptable limits

### Automated Testing

Run the integration test suite:

```bash
# Run Phase 6 integration tests
pytest tests/integration/ai_ml/ -v

# Run backward compatibility tests
pytest tests/integration/test_backward_compatibility.py -v
```

**Expected Results:**
- All tests passing
- No breaking changes to existing functionality
- Phase 6 features working as expected

---

## Monitoring & Alerts

### Step 9: Configure CloudWatch Monitoring (20 minutes)

Set up CloudWatch dashboards and alarms for Phase 6.

#### Create CloudWatch Dashboard

```bash
aws cloudwatch put-dashboard \
  --dashboard-name CostGuardPhase6Dashboard \
  --dashboard-body file://phase6-dashboard.json
```

**phase6-dashboard.json:**

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "label": "Lambda Invocations"}],
          [".", "Errors", {"stat": "Sum", "label": "Lambda Errors"}],
          [".", "Duration", {"stat": "Average", "label": "Avg Duration (ms)"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Phase 6 Lambda Metrics",
        "yAxis": {
          "left": {
            "min": 0
          }
        }
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/DynamoDB", "ConsumedReadCapacityUnits", {"stat": "Sum"}],
          [".", "ConsumedWriteCapacityUnits", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Phase 6 DynamoDB Usage"
      }
    },
    {
      "type": "log",
      "properties": {
        "query": "SOURCE '/aws/lambda/CostGuardLambda'\n| fields @timestamp, @message\n| filter @message like /ai-ml/\n| sort @timestamp desc\n| limit 20",
        "region": "us-east-1",
        "title": "Phase 6 Lambda Logs"
      }
    }
  ]
}
```

#### Create CloudWatch Alarms

**Alarm 1: High Lambda Error Rate**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name phase6-lambda-errors \
  --alarm-description "Alert when Phase 6 Lambda errors exceed threshold" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=CostGuardLambda
```

**Alarm 2: High API Gateway Latency**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name phase6-api-latency \
  --alarm-description "Alert when API Gateway latency exceeds 10 seconds" \
  --metric-name IntegrationLatency \
  --namespace AWS/ApiGateway \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10000 \
  --comparison-operator GreaterThanThreshold
```

**Alarm 3: DynamoDB Throttling**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name phase6-dynamodb-throttling \
  --alarm-description "Alert when DynamoDB requests are throttled" \
  --metric-name UserErrors \
  --namespace AWS/DynamoDB \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold
```

#### Configure Log Insights Queries

Save useful queries for troubleshooting:

**Query 1: GPU Cost Queries**
```
fields @timestamp, @message
| filter @message like /gpu-costs/
| stats count() by bin(5m)
```

**Query 2: Workload Classification Errors**
```
fields @timestamp, @message
| filter @message like /workload-classification/ and @message like /ERROR/
| sort @timestamp desc
```

**Query 3: API Response Times**
```
fields @timestamp, @message
| filter @message like /ai-ml/
| parse @message /duration: (?<duration>\d+)ms/
| stats avg(duration), max(duration), min(duration) by bin(5m)
```

---

## Cost Management

### Step 10: Monitor Phase 6 Costs (15 minutes)

Set up cost monitoring to ensure Phase 6 stays within budget.


#### Expected Monthly Costs

```
Phase 6 Cost Breakdown:
├── Cost Explorer API: ~$0.50/month
│   ├── GPU cost queries: ~50 calls/month
│   └── Rate: $0.01 per call
├── CloudWatch API: $0.00/month (within free tier)
│   ├── Metrics retrieval: ~10,000 API requests/month
│   └── Free tier: 1M API requests/month
├── Lambda: $0.00/month (within free tier)
│   ├── Invocations: ~2,000/month
│   └── Free tier: 1M invocations/month
├── DynamoDB: $0.00/month (within free tier)
│   ├── Storage: ~50 MB
│   └── Free tier: 25 GB storage
├── API Gateway: $0.00/month (within free tier)
│   ├── Requests: ~2,000/month
│   └── Free tier: 1M requests/month
└── Total Phase 6 Cost: ~$0.50/month

Total System Cost (Phases 1-6): ~$4.51/month
```

#### Set Up Cost Alerts

**Alert 1: Phase 6 Cost Exceeds $1/month**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name phase6-cost-alert \
  --alarm-description "Alert if Phase 6 costs exceed $1/month" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 1.0 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ServiceName,Value=AWSCostExplorer
```

**Alert 2: Total System Cost Exceeds $5/month**

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name total-system-cost-alert \
  --alarm-description "Alert if total system costs exceed $5/month" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 5.0 \
  --comparison-operator GreaterThanThreshold
```

#### Monitor Cost Explorer API Usage

Track Cost Explorer API calls to stay within budget:

```bash
# Create custom metric for Cost Explorer API calls
aws cloudwatch put-metric-data \
  --namespace CostGuard/Phase6 \
  --metric-name CostExplorerAPICalls \
  --value 1 \
  --timestamp $(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

Add this to your Lambda function to track API calls automatically.

#### Cost Optimization Tips

1. **Aggressive Caching**: Use 24-hour cache TTL for GPU cost queries
2. **Batch API Calls**: Batch Cost Explorer queries where possible
3. **Rate Limiting**: Limit API calls to 50/month for GPU costs
4. **Monitor Usage**: Review CloudWatch metrics weekly
5. **Optimize Queries**: Use date range filters to reduce data volume

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: DynamoDB Table Not Found

**Symptoms:**
- Lambda function returns "Table not found" error
- CloudWatch logs show DynamoDB errors

**Solution:**
```bash
# Verify table exists
aws dynamodb describe-table --table-name costguard-gpu-costs

# Check Lambda environment variables
aws lambda get-function-configuration --function-name CostGuardLambda --query 'Environment.Variables.GPU_COSTS_TABLE'

# Update environment variable if incorrect
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{GPU_COSTS_TABLE=costguard-gpu-costs,...}"
```

#### Issue 2: IAM Permission Denied

**Symptoms:**
- Lambda function returns "Access Denied" error
- CloudWatch logs show IAM permission errors

**Solution:**
```bash
# Verify IAM policy attached to Lambda role
aws iam list-attached-role-policies --role-name CostGuardLambdaExecutionRole

# Check policy document
aws iam get-policy-version \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/CostGuardPhase6Policy \
  --version-id v1

# Re-attach policy if missing
aws iam attach-role-policy \
  --role-name CostGuardLambdaExecutionRole \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/CostGuardPhase6Policy
```

#### Issue 3: Cost Explorer API Rate Limit

**Symptoms:**
- Lambda function returns "Rate limit exceeded" error
- CloudWatch logs show throttling errors

**Solution:**
```bash
# Implement exponential backoff in Lambda code
# Reduce API call frequency
# Use caching more aggressively

# Check current API call rate
aws cloudwatch get-metric-statistics \
  --namespace CostGuard/Phase6 \
  --metric-name CostExplorerAPICalls \
  --start-time $(date -u -d '1 day ago' +"%Y-%m-%dT%H:%M:%SZ") \
  --end-time $(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --period 3600 \
  --statistics Sum
```

#### Issue 4: CloudWatch Metrics Not Available

**Symptoms:**
- Workload classification returns "Insufficient data" error
- GPU utilization metrics missing

**Solution:**
```bash
# Verify CloudWatch agent installed on EC2 instances
# Check CloudWatch metrics exist
aws cloudwatch list-metrics --namespace AWS/EC2 --metric-name GPUUtilization

# Enable detailed monitoring on EC2 instances
aws ec2 monitor-instances --instance-ids i-1234567890abcdef0

# Wait 5-10 minutes for metrics to appear
```

#### Issue 5: API Gateway 502 Bad Gateway

**Symptoms:**
- API requests return 502 error
- Lambda function not invoked

**Solution:**
```bash
# Check Lambda function status
aws lambda get-function --function-name CostGuardLambda --query 'Configuration.State'

# Check API Gateway integration
aws apigatewayv2 get-integration --api-id $API_ID --integration-id $INTEGRATION_ID

# Test Lambda function directly
aws lambda invoke \
  --function-name CostGuardLambda \
  --payload '{"path": "/api/ai-ml/gpu-costs", "httpMethod": "GET"}' \
  response.json

# Check response
cat response.json
```

#### Issue 6: Slow Response Times

**Symptoms:**
- API requests take > 10 seconds
- Lambda function times out

**Solution:**
```bash
# Increase Lambda timeout
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --timeout 30

# Increase Lambda memory (improves CPU performance)
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --memory-size 1024

# Enable caching with longer TTL
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{CACHE_TTL_HOURS=48,...}"

# Check CloudWatch logs for bottlenecks
aws logs tail /aws/lambda/CostGuardLambda --follow
```

#### Issue 7: Multi-Account Access Denied

**Symptoms:**
- Multi-account GPU cost queries fail
- Cross-account role assumption fails

**Solution:**
```bash
# Verify cross-account role exists in member account
aws sts assume-role \
  --role-arn arn:aws:iam::MEMBER_ACCOUNT_ID:role/CostGuardCollectorRole \
  --role-session-name test-session \
  --external-id your-external-id

# Check trust relationship
aws iam get-role --role-name CostGuardCollectorRole --query 'Role.AssumeRolePolicyDocument'

# Update trust relationship if incorrect
aws iam update-assume-role-policy \
  --role-name CostGuardCollectorRole \
  --policy-document file://trust-policy.json
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{LOG_LEVEL=DEBUG,...}"
```

View debug logs:

```bash
aws logs tail /aws/lambda/CostGuardLambda --follow --filter-pattern "DEBUG"
```

### Health Check

Run a comprehensive health check:

```bash
#!/bin/bash

echo "=== Phase 6 Health Check ==="

# Check DynamoDB tables
echo "Checking DynamoDB tables..."
for table in costguard-gpu-costs costguard-workload-classifications costguard-spot-recommendations; do
  status=$(aws dynamodb describe-table --table-name $table --query 'Table.TableStatus' --output text 2>/dev/null)
  if [ "$status" == "ACTIVE" ]; then
    echo "✓ $table: ACTIVE"
  else
    echo "✗ $table: $status"
  fi
done

# Check Lambda function
echo "Checking Lambda function..."
state=$(aws lambda get-function --function-name CostGuardLambda --query 'Configuration.State' --output text 2>/dev/null)
if [ "$state" == "Active" ]; then
  echo "✓ Lambda function: Active"
else
  echo "✗ Lambda function: $state"
fi

# Check IAM permissions
echo "Checking IAM permissions..."
policies=$(aws iam list-attached-role-policies --role-name CostGuardLambdaExecutionRole --query 'AttachedPolicies[?PolicyName==`CostGuardPhase6Policy`].PolicyName' --output text 2>/dev/null)
if [ -n "$policies" ]; then
  echo "✓ IAM policy attached"
else
  echo "✗ IAM policy not attached"
fi

# Check API Gateway routes
echo "Checking API Gateway routes..."
routes=$(aws apigatewayv2 get-routes --api-id $API_ID --query 'Items[?contains(RouteKey, `ai-ml`)].RouteKey' --output text 2>/dev/null | wc -w)
if [ "$routes" -ge 20 ]; then
  echo "✓ API Gateway routes: $routes"
else
  echo "✗ API Gateway routes: $routes (expected 20+)"
fi

echo "=== Health Check Complete ==="
```

---

## Rollback Procedures

### Emergency Rollback

If Phase 6 deployment causes issues, follow these steps to rollback.

#### Step 1: Remove API Gateway Routes (5 minutes)

```bash
# Get all Phase 6 routes
aws apigatewayv2 get-routes --api-id $API_ID --query 'Items[?contains(RouteKey, `ai-ml`)].RouteId' --output text | \
while read route_id; do
  echo "Deleting route $route_id..."
  aws apigatewayv2 delete-route --api-id $API_ID --route-id $route_id
done

# Deploy API Gateway
aws apigatewayv2 create-deployment --api-id $API_ID --stage-name prod
```

#### Step 2: Revert Lambda Code (10 minutes)

```bash
# Restore previous Lambda version
PREVIOUS_VERSION=$(aws lambda list-versions-by-function --function-name CostGuardLambda --query 'Versions[-2].Version' --output text)

aws lambda update-function-code \
  --function-name CostGuardLambda \
  --s3-bucket your-backup-bucket \
  --s3-key lambda_backup_phase5.zip

# Wait for update
aws lambda wait function-updated --function-name CostGuardLambda
```

#### Step 3: Remove Environment Variables (5 minutes)

```bash
# Remove Phase 6 environment variables
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{
    COST_DATA_TABLE=costguard-cost-data,
    FORECAST_CACHE_TABLE=costguard-forecast-cache,
    PREVENTION_CONFIG_TABLE=costguard-prevention-config,
    RESOURCE_INVENTORY_TABLE=costguard-resource-inventory,
    PREVENTION_AUDIT_TABLE=costguard-prevention-audit,
    APPROVAL_REQUESTS_TABLE=costguard-approval-requests,
    PREVENTION_ENABLED=false,
    DRY_RUN_MODE=true,
    APPROVAL_REQUIRED=true,
    AWS_REGION=$AWS_REGION,
    LOG_LEVEL=INFO
  }"
```

#### Step 4: Detach IAM Policy (5 minutes)

```bash
# Detach Phase 6 IAM policy
aws iam detach-role-policy \
  --role-name CostGuardLambdaExecutionRole \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/CostGuardPhase6Policy
```

#### Step 5: Keep DynamoDB Tables (Optional)

DynamoDB tables can remain without causing issues. Delete only if necessary:

```bash
# Delete Phase 6 tables (CAUTION: Data loss!)
aws dynamodb delete-table --table-name costguard-gpu-costs
aws dynamodb delete-table --table-name costguard-workload-classifications
aws dynamodb delete-table --table-name costguard-spot-recommendations
```

#### Step 6: Verify Rollback

```bash
# Test Phase 1-5 endpoints
curl -X GET "$API_ENDPOINT/api/costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"

# Verify no Phase 6 routes
aws apigatewayv2 get-routes --api-id $API_ID --query 'Items[?contains(RouteKey, `ai-ml`)].RouteKey'

# Check Lambda logs for errors
aws logs tail /aws/lambda/CostGuardLambda --since 5m
```

### Partial Rollback

If only specific features are problematic, disable them without full rollback:

```bash
# Disable GPU prevention
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{GPU_PREVENTION_ENABLED=false,...}"

# Disable workload classification
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{CLASSIFICATION_CONFIDENCE_THRESHOLD=1.0,...}"
```

---

## Success Criteria

Phase 6 deployment is successful when:

- [ ] All 3 DynamoDB tables created and in ACTIVE status
- [ ] Lambda function updated with Phase 6 code
- [ ] IAM permissions attached to Lambda role
- [ ] 20+ API Gateway routes created and deployed
- [ ] Environment variables configured correctly
- [ ] All Phase 6 endpoints return expected responses
- [ ] Backward compatibility verified (Phases 1-5 work)
- [ ] CloudWatch monitoring configured
- [ ] Cost alerts set up
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] Phase 6 costs within budget (~$0.50/month)

---

## Next Steps

After successful deployment:

1. **Monitor for 24-48 hours**
   - Watch CloudWatch logs for errors
   - Monitor API response times
   - Track Cost Explorer API usage

2. **Optimize Performance**
   - Adjust cache TTL based on usage patterns
   - Fine-tune workload classification thresholds
   - Optimize Cost Explorer query batching

3. **Enable GPU Prevention (Optional)**
   - Monitor dry run reports for 1 week
   - Validate idle GPU detection accuracy
   - Enable prevention with approval required
   - Gradually disable approval after confidence built

4. **Collect User Feedback**
   - Test with real GPU workloads
   - Validate cost calculations accuracy
   - Gather feedback on API usability

5. **Iterate on Features**
   - Add new workload types if needed
   - Improve classification accuracy
   - Extend multi-account support

---

## Related Documentation

- **[Phase 6 Requirements](/.kiro/specs/ai-ml-workload-costs/requirements.md)** - Detailed requirements
- **[Phase 6 Design](/.kiro/specs/ai-ml-workload-costs/design.md)** - Architecture and design decisions
- **[Phase 6 API Documentation](../api/phase6-api-documentation.md)** - Complete API reference
- **[Phase 6 Tasks](/.kiro/specs/ai-ml-workload-costs/tasks.md)** - Implementation task list
- **[Infrastructure README](../../infrastructure/README.md)** - General infrastructure guide
- **[Deployment Checklist](../../DEPLOYMENT_CHECKLIST.md)** - Phase 4 deployment reference

---

## Support

For deployment issues or questions:

1. Check [Troubleshooting](#troubleshooting) section
2. Review CloudWatch logs: `/aws/lambda/CostGuardLambda`
3. Check [GitHub Issues](https://github.com/your-org/costguard-ai/issues)
4. Contact support: support@costguard.ai

---

**Document Status:** Ready for Deployment  
**Last Updated:** February 2026  
**Version:** 1.0

