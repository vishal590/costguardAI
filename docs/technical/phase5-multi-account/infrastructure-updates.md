# Phase 5: Multi-Account Cost Management - Infrastructure Updates

**Last Updated:** February 2026  
**Status:** ✅ **READY FOR DEPLOYMENT**

---

## Overview

This document describes the infrastructure changes required for Phase 5 multi-account cost management. Phase 5 adds support for AWS Organizations with cross-account cost collection, consolidated billing views, cost allocation, and organization-wide policies.

---

## Prerequisites

Before deploying Phase 5, ensure:
- ✅ Phases 1-4 are deployed and working
- ✅ AWS Organizations is enabled in your AWS account
- ✅ You have access to the management account
- ✅ Member accounts are part of the organization
- ✅ AWS CLI and CDK are configured

---

## Infrastructure Components

### 1. DynamoDB Tables

**New Tables Required:** 8

#### organizations
```json
{
  "TableName": "costguard-organizations",
  "KeySchema": [
    { "AttributeName": "organization_id", "KeyType": "HASH" }
  ],
  "AttributeDefinitions": [
    { "AttributeName": "organization_id", "AttributeType": "S" }
  ],
  "BillingMode": "PAY_PER_REQUEST",
  "Tags": [
    { "Key": "Phase", "Value": "5" },
    { "Key": "Component", "Value": "MultiAccount" }
  ]
}
```

#### organizational_units
```json
{
  "TableName": "costguard-organizational-units",
  "KeySchema": [
    { "AttributeName": "ou_id", "KeyType": "HASH" }
  ],
  "AttributeDefinitions": [
    { "AttributeName": "ou_id", "AttributeType": "S" },
    { "AttributeName": "organization_id", "AttributeType": "S" }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "organization-index",
      "KeySchema": [
        { "AttributeName": "organization_id", "KeyType": "HASH" }
      ],
      "Projection": { "ProjectionType": "ALL" }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### accounts
```json
{
  "TableName": "costguard-accounts",
  "KeySchema": [
    { "AttributeName": "account_id", "KeyType": "HASH" }
  ],
  "AttributeDefinitions": [
    { "AttributeName": "account_id", "AttributeType": "S" },
    { "AttributeName": "organization_id", "AttributeType": "S" }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "organization-index",
      "KeySchema": [
        { "AttributeName": "organization_id", "KeyType": "HASH" }
      ],
      "Projection": { "ProjectionType": "ALL" }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### cross_account_roles
```json
{
  "TableName": "costguard-cross-account-roles",
  "KeySchema": [
    { "AttributeName": "account_id", "KeyType": "HASH" }
  ],
  "AttributeDefinitions": [
    { "AttributeName": "account_id", "AttributeType": "S" }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### cost_allocation_rules
```json
{
  "TableName": "costguard-cost-allocation-rules",
  "KeySchema": [
    { "AttributeName": "rule_id", "KeyType": "HASH" }
  ],
  "AttributeDefinitions": [
    { "AttributeName": "rule_id", "AttributeType": "S" },
    { "AttributeName": "organization_id", "AttributeType": "S" }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "organization-index",
      "KeySchema": [
        { "AttributeName": "organization_id", "KeyType": "HASH" }
      ],
      "Projection": { "ProjectionType": "ALL" }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### multi_account_budgets
```json
{
  "TableName": "costguard-multi-account-budgets",
  "KeySchema": [
    { "AttributeName": "budget_id", "KeyType": "HASH" }
  ],
  "AttributeDefinitions": [
    { "AttributeName": "budget_id", "AttributeType": "S" },
    { "AttributeName": "organization_id", "AttributeType": "S" }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "organization-index",
      "KeySchema": [
        { "AttributeName": "organization_id", "KeyType": "HASH" }
      ],
      "Projection": { "ProjectionType": "ALL" }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### multi_account_forecasts
```json
{
  "TableName": "costguard-multi-account-forecasts",
  "KeySchema": [
    { "AttributeName": "cache_key", "KeyType": "HASH" }
  ],
  "AttributeDefinitions": [
    { "AttributeName": "cache_key", "AttributeType": "S" }
  ],
  "TimeToLiveSpecification": {
    "AttributeName": "ttl",
    "Enabled": true
  },
  "BillingMode": "PAY_PER_REQUEST"
}
```

#### prevention_policies
```json
{
  "TableName": "costguard-prevention-policies",
  "KeySchema": [
    { "AttributeName": "policy_id", "KeyType": "HASH" }
  ],
  "AttributeDefinitions": [
    { "AttributeName": "policy_id", "AttributeType": "S" },
    { "AttributeName": "organization_id", "AttributeType": "S" }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "organization-index",
      "KeySchema": [
        { "AttributeName": "organization_id", "KeyType": "HASH" }
      ],
      "Projection": { "ProjectionType": "ALL" }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

**Deployment Command:**
```bash
cd infrastructure
python deploy_multi_account.py --create-tables
```

---

### 2. IAM Roles & Permissions

#### Management Account Role

**Role Name:** `CostGuardManagementRole`

**Permissions Required:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "organizations:DescribeOrganization",
        "organizations:ListAccounts",
        "organizations:ListOrganizationalUnitsForParent",
        "organizations:ListRoots",
        "organizations:DescribeOrganizationalUnit",
        "organizations:DescribeAccount"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sts:AssumeRole"
      ],
      "Resource": "arn:aws:iam::*:role/CostGuardMemberRole"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/costguard-organizations",
        "arn:aws:dynamodb:*:*:table/costguard-organizational-units",
        "arn:aws:dynamodb:*:*:table/costguard-accounts",
        "arn:aws:dynamodb:*:*:table/costguard-cross-account-roles",
        "arn:aws:dynamodb:*:*:table/costguard-cost-allocation-rules",
        "arn:aws:dynamodb:*:*:table/costguard-multi-account-budgets",
        "arn:aws:dynamodb:*:*:table/costguard-multi-account-forecasts",
        "arn:aws:dynamodb:*:*:table/costguard-prevention-policies",
        "arn:aws:dynamodb:*:*:table/costguard-*/index/*"
      ]
    }
  ]
}
```

#### Member Account Role

**Role Name:** `CostGuardMemberRole`

**Trust Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::<MANAGEMENT_ACCOUNT_ID>:role/CostGuardManagementRole"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "<EXTERNAL_ID>"
        }
      }
    }
  ]
}
```

**Permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    }
  ]
}
```

**Deployment:**
See [CROSS_ACCOUNT_SETUP.md](../../infrastructure/CROSS_ACCOUNT_SETUP.md) for detailed setup instructions.

---

### 3. Lambda Functions

#### New Lambda Handlers

**1. multi_account_handler.py**
- **Purpose:** Main multi-account API handler
- **Memory:** 512 MB
- **Timeout:** 30 seconds
- **Trigger:** API Gateway

**2. multi_account_api_handler.py**
- **Purpose:** Extended multi-account API endpoints
- **Memory:** 512 MB
- **Timeout:** 30 seconds
- **Trigger:** API Gateway

**3. multi_account_cost_collector_handler.py**
- **Purpose:** Scheduled cross-account cost collection
- **Memory:** 1024 MB
- **Timeout:** 5 minutes
- **Trigger:** EventBridge (every 6 hours)

#### Environment Variables

**Add to all Lambda functions:**
```json
{
  "MULTI_ACCOUNT_ENABLED": "true",
  "MANAGEMENT_ACCOUNT_ID": "<YOUR_MANAGEMENT_ACCOUNT_ID>",
  "CROSS_ACCOUNT_ROLE_NAME": "CostGuardMemberRole",
  "EXTERNAL_ID": "<YOUR_EXTERNAL_ID>",
  "MAX_PARALLEL_COLLECTIONS": "10",
  "COLLECTION_TIMEOUT_SECONDS": "300"
}
```

---

### 4. API Gateway

#### New Routes

**Organization Management:**
```
GET    /api/multi-account/organizations
GET    /api/multi-account/organizations/{org_id}
GET    /api/multi-account/organizations/{org_id}/accounts
```

**Cost Queries:**
```
GET    /api/multi-account/organizations/{org_id}/costs
GET    /api/multi-account/organizations/{org_id}/ous/{ou_id}/costs
GET    /api/multi-account/accounts/{account_id}/costs
GET    /api/multi-account/costs/consolidated
GET    /api/multi-account/costs/by-account
```

**Cost Allocation:**
```
POST   /api/multi-account/allocation/rules
GET    /api/multi-account/allocation/rules
GET    /api/multi-account/allocation/by-tag
GET    /api/multi-account/allocation/unallocated
```

**Reports:**
```
GET    /api/multi-account/reports/chargeback
GET    /api/multi-account/reports/showback
GET    /api/multi-account/reports/allocation
```

**Budgets:**
```
POST   /api/multi-account/budgets
GET    /api/multi-account/budgets/{budget_id}
GET    /api/multi-account/budgets/{budget_id}/status
```

**Total New Routes:** 15+

**Integration:** All routes integrate with `multi_account_handler` or `multi_account_api_handler`

---

### 5. EventBridge

#### New Scheduled Rules

**Cost Collection Schedule:**
```json
{
  "Name": "costguard-multi-account-collection",
  "ScheduleExpression": "rate(6 hours)",
  "State": "ENABLED",
  "Targets": [
    {
      "Arn": "arn:aws:lambda:REGION:ACCOUNT:function:costguard-multi-account-cost-collector",
      "Id": "1"
    }
  ]
}
```

**Organization Discovery Schedule:**
```json
{
  "Name": "costguard-organization-discovery",
  "ScheduleExpression": "rate(1 day)",
  "State": "ENABLED",
  "Targets": [
    {
      "Arn": "arn:aws:lambda:REGION:ACCOUNT:function:costguard-multi-account-handler",
      "Id": "1",
      "Input": "{\"action\": \"discover_organization\"}"
    }
  ]
}
```

---

### 6. CloudFormation StackSets

#### Member Account Role Deployment

**StackSet Name:** `CostGuardMemberRoles`

**Template:** `infrastructure/member_account_role_template.yaml`

**Deployment:**
```bash
aws cloudformation create-stack-set \
  --stack-set-name CostGuardMemberRoles \
  --template-body file://infrastructure/member_account_role_template.yaml \
  --parameters \
    ParameterKey=ManagementAccountId,ParameterValue=<MGMT_ACCOUNT_ID> \
    ParameterKey=ExternalId,ParameterValue=<EXTERNAL_ID> \
  --capabilities CAPABILITY_NAMED_IAM \
  --permission-model SERVICE_MANAGED \
  --auto-deployment Enabled=true,RetainStacksOnAccountRemoval=false

aws cloudformation create-stack-instances \
  --stack-set-name CostGuardMemberRoles \
  --deployment-targets OrganizationalUnitIds=<OU_ID> \
  --regions us-east-1
```

**See:** [MEMBER_ACCOUNT_DEPLOYMENT.md](../../infrastructure/MEMBER_ACCOUNT_DEPLOYMENT.md)

---

## Deployment Steps

### Step 1: Verify Prerequisites

```bash
# Check AWS Organizations
aws organizations describe-organization

# Check current account is management account
aws sts get-caller-identity

# List member accounts
aws organizations list-accounts
```

### Step 2: Deploy DynamoDB Tables

```bash
cd infrastructure
python deploy_multi_account.py --create-tables
```

**Expected Output:**
```
Creating DynamoDB tables for Phase 5...
✓ Created table: costguard-organizations
✓ Created table: costguard-organizational-units
✓ Created table: costguard-accounts
✓ Created table: costguard-cross-account-roles
✓ Created table: costguard-cost-allocation-rules
✓ Created table: costguard-multi-account-budgets
✓ Created table: costguard-multi-account-forecasts
✓ Created table: costguard-prevention-policies
All tables created successfully!
```

### Step 3: Deploy Cross-Account Roles

```bash
# Deploy to all member accounts using StackSets
./infrastructure/deploy_cross_account_roles.sh

# Or manually deploy to specific accounts
aws cloudformation create-stack \
  --stack-name CostGuardMemberRole \
  --template-body file://infrastructure/member_account_role_template.yaml \
  --parameters \
    ParameterKey=ManagementAccountId,ParameterValue=<MGMT_ACCOUNT_ID> \
    ParameterKey=ExternalId,ParameterValue=<EXTERNAL_ID> \
  --capabilities CAPABILITY_NAMED_IAM
```

### Step 4: Update Lambda Functions

```bash
# Deploy Phase 5 Lambda functions
cd infrastructure
cdk deploy --all

# Or use deployment script
../deploy.sh
```

### Step 5: Initialize Organization Discovery

```bash
# Trigger initial organization discovery
aws lambda invoke \
  --function-name costguard-multi-account-handler \
  --payload '{"action": "discover_organization"}' \
  response.json

cat response.json
```

### Step 6: Verify Deployment

```bash
# Test organization endpoint
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/multi-account/organizations"

# Test account listing
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/multi-account/organizations/YOUR_ORG_ID/accounts"
```

---

## Rollback Procedure

If you need to rollback Phase 5:

```bash
# Use rollback script
./rollback.sh

# Or manually:
# 1. Delete EventBridge rules
aws events delete-rule --name costguard-multi-account-collection
aws events delete-rule --name costguard-organization-discovery

# 2. Delete API Gateway routes
# (Done via CDK rollback)

# 3. Delete Lambda functions
# (Done via CDK rollback)

# 4. Delete DynamoDB tables (optional - keeps data)
python deploy_multi_account.py --delete-tables

# 5. Delete StackSet instances
aws cloudformation delete-stack-instances \
  --stack-set-name CostGuardMemberRoles \
  --accounts <ACCOUNT_IDS> \
  --regions us-east-1 \
  --no-retain-stacks

# 6. Delete StackSet
aws cloudformation delete-stack-set \
  --stack-set-name CostGuardMemberRoles
```

---

## Monitoring & Troubleshooting

### CloudWatch Metrics

**Custom Metrics:**
- `MultiAccountCostCollection.Duration` - Collection time
- `MultiAccountCostCollection.SuccessRate` - Success percentage
- `CostAggregation.CacheHitRate` - Cache performance
- `AllocationEngine.UnallocatedPercentage` - Allocation coverage

### CloudWatch Logs

**Log Groups:**
- `/aws/lambda/costguard-multi-account-handler`
- `/aws/lambda/costguard-multi-account-api-handler`
- `/aws/lambda/costguard-multi-account-cost-collector`

### Common Issues

**Issue:** Cross-account role assumption fails
**Solution:** Verify trust policy and external ID in member account role

**Issue:** Organization discovery returns empty
**Solution:** Ensure management account has Organizations permissions

**Issue:** Cost collection times out
**Solution:** Increase Lambda timeout or reduce MAX_PARALLEL_COLLECTIONS

**Issue:** High DynamoDB costs
**Solution:** Review query patterns and add caching

---

## Cost Estimate

### Monthly Costs

**DynamoDB:**
- Storage: ~500 MB × $0.25/GB = ~$0.13
- Requests: ~100K reads/writes × $0.25/million = ~$0.03
- **Subtotal:** ~$0.16

**Lambda:**
- Invocations: ~15,000/month (within free tier)
- Duration: ~50,000 GB-seconds (within free tier)
- **Subtotal:** ~$0.00

**Cost Explorer API:**
- Calls: ~3,000/month × $0.01 = ~$30.00
- With caching: ~1,000/month × $0.01 = ~$10.00
- **Subtotal:** ~$10.00 (optimized)

**STS AssumeRole:**
- Calls: ~10,000/month (free)
- **Subtotal:** ~$0.00

**EventBridge:**
- Rules: 2 rules (free)
- Invocations: Count toward Lambda free tier
- **Subtotal:** ~$0.00

**API Gateway:**
- Requests: ~3,000/month (within 1M free tier)
- **Subtotal:** ~$0.00

**Total Monthly Cost:** ~$10.16 for 100 accounts
**Cost per Account:** ~$0.10/month

**Note:** Costs scale with number of accounts and API usage. Aggressive caching reduces Cost Explorer API costs significantly.

---

## Security Considerations

### IAM Best Practices
- ✅ Use external ID for cross-account role assumption
- ✅ Principle of least privilege for all roles
- ✅ Regular rotation of external ID
- ✅ Audit cross-account access logs

### Data Protection
- ✅ Encrypt DynamoDB tables at rest
- ✅ Use HTTPS for all API calls
- ✅ API key authentication required
- ✅ No sensitive data in logs

### Compliance
- ✅ Cost data stays within AWS
- ✅ No data exported to third parties
- ✅ Audit trail for all actions
- ✅ Role-based access control

---

## Additional Resources

- **[README.md](./README.md)** - Phase 5 overview
- **[API_DOCUMENTATION.md](./API_DOCUMENTATION.md)** - Complete API reference
- **[CROSS_ACCOUNT_SETUP.md](../../infrastructure/CROSS_ACCOUNT_SETUP.md)** - Cross-account setup guide
- **[MEMBER_ACCOUNT_DEPLOYMENT.md](../../infrastructure/MEMBER_ACCOUNT_DEPLOYMENT.md)** - Member account setup
- **[DEPLOYMENT_SCRIPTS.md](../../DEPLOYMENT_SCRIPTS.md)** - Deployment scripts
- **[implementation-summary.md](./implementation-summary.md)** - Implementation details

---

**Status:** ✅ **READY FOR DEPLOYMENT**  
**Last Updated:** February 2026  
**Maintained By:** CostGuard AI Team

