# CostGuard AI - Production Deployment Guide

**Version:** 1.0  
**Date:** March 2026  
**Status:** Production Ready

---

## Overview

This guide provides step-by-step instructions for deploying CostGuard AI to production.

---

## Prerequisites

### Required AWS Services
- AWS Organizations (for multi-account support)
- AWS Lambda
- AWS DynamoDB
- AWS EventBridge
- AWS IAM
- AWS CloudWatch
- AWS Cost Explorer API
- AWS Pricing API
- AWS EC2 API
- AWS SageMaker API (for AI/ML workloads)

### Required Permissions
- CloudFormation deployment permissions
- IAM role creation permissions
- Lambda function deployment
- DynamoDB table creation
- EventBridge rule creation

### Required Tools
- AWS CLI configured
- AWS CDK CLI installed
- Python 3.9+ installed
- Node.js 18+ installed (for CDK)

---

## Deployment Steps

### Step 1: Pre-Deployment Verification

#### 1.1 Verify Prerequisites
```bash
# Check AWS CLI
aws --version

# Check CDK
cdk --version

# Check Python
python --version

# Verify AWS credentials
aws sts get-caller-identity
```

#### 1.2 Review Configuration
```bash
# Review CDK context
cat cdk.json

# Review environment variables
cat infrastructure/.env.example
```

#### 1.3 Verify Code Status
```bash
# Check git status
git status

# Verify all tests passing
python -m pytest tests/unit/ -q
```

---

### Step 2: Infrastructure Deployment

#### 2.1 Bootstrap CDK (First Time Only)
```bash
cd infrastructure
cdk bootstrap aws://ACCOUNT-ID/REGION
```

#### 2.2 Deploy Core Stack
```bash
# Deploy main stack
cdk deploy CostGuardStack

# Or deploy specific stacks
cdk deploy CostGuardStack --all
```

#### 2.3 Verify Deployment
```bash
# Check CloudFormation stack
aws cloudformation describe-stacks --stack-name CostGuardStack

# Check Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `CostGuard`)].FunctionName'

# Check DynamoDB tables
aws dynamodb list-tables --query 'TableNames[?contains(@, `costguard`)]'
```

---

### Step 3: Configuration

#### 3.1 Environment Variables
Set environment variables for Lambda functions:

```bash
# Main handler
aws lambda update-function-configuration \
  --function-name CostGuardMainHandler \
  --environment Variables='{
    "COST_TABLE":"costguard-costs",
    "INSIGHT_TABLE":"costguard-insights",
    "ACTION_TABLE":"costguard-actions"
  }'

# Multi-account handler
aws lambda update-function-configuration \
  --function-name CostGuardMultiAccountHandler \
  --environment Variables='{
    "MAX_PARALLEL_ACCOUNTS":"10",
    "ORG_SYNC_HOURS":"4"
  }'
```

#### 3.2 Cross-Account Roles
Set up cross-account roles for multi-account support:

```bash
# Create role in each member account
# See: docs/technical/phase5-multi-account/cross-account-setup.md
```

#### 3.3 EventBridge Schedules
Verify EventBridge rules are created:

```bash
# List rules
aws events list-rules --name-prefix CostGuard

# Check schedule
aws events describe-rule --name CostGuardDailyCostCollection
```

---

### Step 4: Initial Setup

#### 4.1 Organization Discovery
Trigger initial organization discovery:

```bash
# Invoke discovery handler
aws lambda invoke \
  --function-name CostGuardOrganizationDiscovery \
  --payload '{}' \
  response.json
```

#### 4.2 Verify Data Collection
Check DynamoDB tables for initial data:

```bash
# Check cost data
aws dynamodb scan --table-name costguard-costs --limit 5

# Check organization data
aws dynamodb scan --table-name organizations --limit 5
```

---

### Step 5: Smoke Tests

#### 5.1 Test Cost Collection
```bash
# Invoke cost collection
aws lambda invoke \
  --function-name CostGuardMainHandler \
  --payload '{"path":"/api/costs","httpMethod":"GET"}' \
  response.json

# Check response
cat response.json
```

#### 5.2 Test Multi-Account Collection
```bash
# Invoke multi-account collection
aws lambda invoke \
  --function-name CostGuardMultiAccountHandler \
  --payload '{}' \
  response.json
```

#### 5.3 Test API Endpoints
```bash
# Get API Gateway URL
API_URL=$(aws apigatewayv2 get-apis --query 'Items[?Name==`CostGuardAPI`].ApiEndpoint' --output text)

# Test health endpoint
curl $API_URL/health

# Test costs endpoint
curl $API_URL/api/costs
```

---

### Step 6: Monitoring Setup

#### 6.1 CloudWatch Dashboards
Create CloudWatch dashboard:

```bash
# See: infrastructure/monitoring/dashboard.json
aws cloudwatch put-dashboard \
  --dashboard-name CostGuardAI \
  --dashboard-body file://infrastructure/monitoring/dashboard.json
```

#### 6.2 Alarms
Set up CloudWatch alarms:

```bash
# Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name CostGuard-LambdaErrors \
  --alarm-description "Alert on Lambda function errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold

# Cost collection failures
aws cloudwatch put-metric-alarm \
  --alarm-name CostGuard-CostCollectionFailures \
  --alarm-description "Alert on cost collection failures" \
  --metric-name CostCollectionFailures \
  --namespace CostGuardAI \
  --statistic Sum \
  --period 3600 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold
```

---

## Post-Deployment Verification

### Verification Checklist

- [ ] All Lambda functions deployed
- [ ] All DynamoDB tables created
- [ ] EventBridge schedules active
- [ ] Cross-account roles configured
- [ ] Environment variables set
- [ ] Cost collection working
- [ ] Multi-account discovery working
- [ ] API endpoints responding
- [ ] CloudWatch metrics visible
- [ ] No critical errors in logs

### Verification Commands

```bash
# Check Lambda function status
aws lambda get-function --function-name CostGuardMainHandler

# Check DynamoDB table status
aws dynamodb describe-table --table-name costguard-costs

# Check EventBridge rules
aws events list-rules --name-prefix CostGuard

# Check CloudWatch logs
aws logs tail /aws/lambda/CostGuardMainHandler --follow

# Check API Gateway
aws apigatewayv2 get-apis --query 'Items[?Name==`CostGuardAPI`]'
```

---

## Troubleshooting

### Common Issues

#### Issue: Lambda Function Errors
**Solution:**
1. Check CloudWatch logs
2. Verify IAM permissions
3. Check environment variables
4. Verify dependencies

#### Issue: DynamoDB Throttling
**Solution:**
1. Check table capacity
2. Enable auto-scaling
3. Review query patterns
4. Add retry logic

#### Issue: Cost Collection Failures
**Solution:**
1. Verify Cost Explorer API permissions
2. Check date ranges
3. Verify account access
4. Review error logs

#### Issue: Multi-Account Discovery Fails
**Solution:**
1. Verify Organizations API access
2. Check cross-account roles
3. Verify role trust relationships
4. Check IAM permissions

---

## Rollback Procedure

### Rollback Steps

1. **Stop EventBridge Schedules**
```bash
aws events disable-rule --name CostGuardDailyCostCollection
```

2. **Revert Lambda Functions**
```bash
# Get previous version
PREV_VERSION=$(aws lambda list-versions-by-function \
  --function-name CostGuardMainHandler \
  --query 'Versions[-2].Version' --output text)

# Update alias
aws lambda update-alias \
  --function-name CostGuardMainHandler \
  --name PROD \
  --function-version $PREV_VERSION
```

3. **Restore DynamoDB (if needed)**
```bash
# Use point-in-time recovery
aws dynamodb restore-table-from-backup \
  --target-table-name costguard-costs-restored \
  --backup-arn BACKUP-ARN
```

4. **Verify Rollback**
```bash
# Check function version
aws lambda get-alias --function-name CostGuardMainHandler --name PROD

# Verify system stability
aws lambda invoke --function-name CostGuardMainHandler --payload '{}' test.json
```

---

## Maintenance

### Regular Maintenance Tasks

#### Weekly
- Review CloudWatch metrics
- Check error rates
- Review cost collection status
- Verify multi-account sync

#### Monthly
- Review cost data accuracy
- Check DynamoDB capacity
- Review Lambda function performance
- Update documentation

#### Quarterly
- Review and update dependencies
- Security audit
- Performance optimization
- Cost optimization review

---

## Support

### Documentation
- **Technical Docs:** `docs/technical/`
- **API Docs:** `docs/api/`
- **Deployment:** `docs/DEPLOYMENT_GUIDE.md`

### Monitoring
- **CloudWatch:** AWS Console → CloudWatch
- **Logs:** `/aws/lambda/CostGuard*`
- **Metrics:** `CostGuardAI` namespace

### Issues
- **Known Issues:** `docs/technical/REPOSITORY_TESTS_RECOMMENDATION.md`
- **Troubleshooting:** See Troubleshooting section above

---

**Document Version:** 1.0  
**Last Updated:** March 2026  
**Status:** Production Ready
