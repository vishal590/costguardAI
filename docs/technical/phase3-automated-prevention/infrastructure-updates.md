# Phase 3: Infrastructure Updates

> **Current source boundary (October 14, 2026):** This file preserves an earlier design/review/report. Use the [current Phase 3 overview](README.md) and [active implementation contracts](../access-and-feature-contracts.md). Earlier completion, idle-coverage, confidence, execution and test claims do not validate the current source. All further validation is deferred.

**Status:** ✅ Complete  
**CDK Version:** 2.x  
**Python Version:** 3.11+

## Overview

Phase 3 adds significant infrastructure components to support automated cost prevention. All infrastructure is defined as code using AWS CDK (Python) and follows infrastructure-as-code best practices.

## New Infrastructure Components

### DynamoDB Tables (4 New)

#### 1. prevention-config

**Purpose:** Store prevention system configuration

**Schema:**
```python
{
  "config_key": "string",  # Partition key
  "config_value": "map",   # Configuration data
  "updated_at": "string",  # ISO 8601 timestamp
  "updated_by": "string"   # User/system identifier
}
```

**Configuration Keys:**
- `system` - Global system settings (enabled, dry_run, approval_required)
- `thresholds` - Budget threshold percentages (warning, action)
- `idle_criteria` - Service-specific idle detection criteria
- `safety_config` - Protected tags, whitelists, minimum idle durations
- `notification_topics` - SNS topic ARNs

**Billing Mode:** On-demand  
**Estimated Size:** ~10 MB  
**Free Tier:** Within 25 GB limit

#### 2. resource-inventory

**Purpose:** Track discovered AWS resources

**Schema:**
```python
{
  "resource_id": "string",      # Partition key (e.g., "i-1234567890abcdef0")
  "service": "string",          # Sort key (e.g., "ec2")
  "resource_type": "string",    # Resource type (e.g., "instance")
  "region": "string",           # AWS region
  "state": "string",            # Current state (running, stopped, etc.)
  "tags": "map",                # Resource tags
  "metadata": "map",            # Service-specific metadata
  "created_at": "string",       # Resource creation timestamp
  "discovered_at": "string",    # Discovery timestamp
  "last_updated": "string",     # Last update timestamp
  "idle_status": "map",         # Idle detection results
  "ttl": "number"               # TTL for automatic cleanup (30 days)
}
```

**Indexes:**
- GSI: `service-state-index` (service, state) - Query resources by service and state
- GSI: `region-index` (region) - Query resources by region

**Billing Mode:** On-demand  
**Estimated Size:** ~40 MB  
**Free Tier:** Within 25 GB limit  
**TTL:** 30 days (automatic cleanup of stale records)

#### 3. prevention-audit

**Purpose:** Audit log for all prevention actions

**Schema:**
```python
{
  "action_id": "string",        # Partition key (UUID)
  "timestamp": "string",        # Sort key (ISO 8601)
  "action_type": "string",      # Action type (stop_ec2, stop_rds, etc.)
  "resource_id": "string",      # Target resource ID
  "service": "string",          # AWS service
  "status": "string",           # success, failed, rolled_back
  "dry_run": "boolean",         # Whether this was a dry run
  "pre_action_state": "map",    # Resource state before action
  "post_action_state": "map",   # Resource state after action
  "estimated_savings": "number", # Estimated monthly savings
  "reason": "string",           # Reason for action
  "triggered_by": "string",     # budget_threshold, manual, scheduled
  "approved_by": "string",      # Approver (if applicable)
  "error_message": "string",    # Error details (if failed)
  "ttl": "number"               # TTL for automatic cleanup (90 days)
}
```

**Indexes:**
- GSI: `resource-index` (resource_id, timestamp) - Query actions by resource
- GSI: `service-index` (service, timestamp) - Query actions by service
- GSI: `status-index` (status, timestamp) - Query by status

**Billing Mode:** On-demand  
**Estimated Size:** ~30 MB  
**Free Tier:** Within 25 GB limit  
**TTL:** 90 days (automatic cleanup of old audit logs)

#### 4. approval-requests

**Purpose:** Track approval requests and responses

**Schema:**
```python
{
  "request_id": "string",       # Partition key (UUID)
  "created_at": "string",       # Request creation timestamp
  "expires_at": "string",       # Expiration timestamp (30 minutes)
  "status": "string",           # pending, approved, denied, expired
  "actions": "list",            # List of planned actions
  "total_savings": "number",    # Total estimated savings
  "requester": "string",        # System/user that requested
  "approver": "string",         # User who approved/denied
  "approved_at": "string",      # Approval timestamp
  "response_method": "string",  # api, email, manual
  "comments": "string",         # Approval/denial comments
  "ttl": "number"               # TTL for automatic cleanup (7 days)
}
```

**Indexes:**
- GSI: `status-index` (status, created_at) - Query by status

**Billing Mode:** On-demand  
**Estimated Size:** ~20 MB  
**Free Tier:** Within 25 GB limit  
**TTL:** 7 days (automatic cleanup of old requests)

### SNS Topics (3 New)

#### 1. prevention-warnings

**Purpose:** Notifications for 80% budget threshold warnings

**Subscription Protocol:** Email, SMS, Lambda  
**Message Format:**
```json
{
  "alert_type": "budget_warning",
  "budget_name": "Monthly AWS Budget",
  "current_utilization": 82.5,
  "threshold": 80.0,
  "current_cost": 825.00,
  "budget_limit": 1000.00,
  "currency": "USD",
  "timestamp": "2026-01-21T10:30:00Z",
  "message": "Budget 'Monthly AWS Budget' has reached 82.5% utilization"
}
```

**Estimated Messages:** ~100/month  
**Free Tier:** Within 1M publishes/month

#### 2. prevention-actions

**Purpose:** Notifications for 90% budget threshold actions

**Subscription Protocol:** Email, SMS, Lambda  
**Message Format:**
```json
{
  "alert_type": "prevention_action",
  "budget_name": "Monthly AWS Budget",
  "current_utilization": 92.0,
  "threshold": 90.0,
  "actions_taken": [
    {
      "action_id": "action-123",
      "resource_id": "i-1234567890abcdef0",
      "service": "ec2",
      "action_type": "stop_instance",
      "estimated_savings": 50.00,
      "status": "success"
    }
  ],
  "total_savings": 150.00,
  "dry_run": false,
  "timestamp": "2026-01-21T10:35:00Z"
}
```

**Estimated Messages:** ~50/month  
**Free Tier:** Within 1M publishes/month

#### 3. prevention-errors

**Purpose:** Notifications for prevention system errors

**Subscription Protocol:** Email, SMS, Lambda  
**Message Format:**
```json
{
  "alert_type": "prevention_error",
  "error_code": "ACTION_EXECUTION_FAILED",
  "error_message": "Failed to stop EC2 instance i-1234567890abcdef0",
  "resource_id": "i-1234567890abcdef0",
  "service": "ec2",
  "action_type": "stop_instance",
  "timestamp": "2026-01-21T10:40:00Z",
  "details": {
    "exception": "ClientError",
    "message": "Instance not found"
  }
}
```

**Estimated Messages:** ~10/month  
**Free Tier:** Within 1M publishes/month

### EventBridge Schedule

**Rule Name:** `costguard-budget-monitoring`  
**Schedule Expression:** `rate(5 minutes)`  
**Target:** Lambda function (costguard-cost-data-handler)  
**Input:** 
```json
{
  "source": "aws.events",
  "detail-type": "Scheduled Event",
  "detail": {
    "trigger": "budget_monitoring"
  }
}
```

**Purpose:** Trigger budget monitoring every 5 minutes  
**Estimated Invocations:** 8,640/month  
**Cost:** Free (rules are free, invocations count toward Lambda free tier)

### IAM Permissions (Extended)

#### Lambda Execution Role Updates

**New Permissions Added:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "budgets:DescribeBudgets",
        "budgets:ViewBudget"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:StopInstances",
        "ec2:StartInstances",
        "ec2:DescribeVolumes",
        "ec2:CreateSnapshot",
        "ec2:DeleteVolume",
        "ec2:DescribeNatGateways",
        "ec2:DeleteNatGateway"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:StopDBInstance",
        "rds:StartDBInstance"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:ListFunctions",
        "lambda:GetFunction",
        "lambda:PutFunctionConcurrency",
        "lambda:DeleteFunctionConcurrency"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeTable",
        "dynamodb:UpdateTable",
        "dynamodb:ListTables"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation",
        "s3:GetBucketTagging"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "elasticache:DescribeCacheClusters",
        "elasticache:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ListQueues",
        "sqs:GetQueueAttributes",
        "sqs:ListQueueTags"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:ListTopics",
        "sns:GetTopicAttributes",
        "sns:ListTagsForResource",
        "sns:Publish"
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
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/prevention-config",
        "arn:aws:dynamodb:*:*:table/resource-inventory",
        "arn:aws:dynamodb:*:*:table/prevention-audit",
        "arn:aws:dynamodb:*:*:table/approval-requests"
      ]
    }
  ]
}
```

**Security Considerations:**
- Least privilege principle applied
- Resource-level permissions where possible
- Read-only permissions for discovery
- Write permissions only for specific actions
- Audit logging for all actions

### Lambda Environment Variables (Extended)

**New Environment Variables:**

```python
{
  # Phase 3 Configuration
  "PREVENTION_ENABLED": "false",  # Start disabled for safety
  "DRY_RUN_MODE": "true",         # Start in dry run mode
  "APPROVAL_REQUIRED": "true",    # Require approval initially
  
  # DynamoDB Tables
  "PREVENTION_CONFIG_TABLE": "prevention-config",
  "RESOURCE_INVENTORY_TABLE": "resource-inventory",
  "PREVENTION_AUDIT_TABLE": "prevention-audit",
  "APPROVAL_REQUESTS_TABLE": "approval-requests",
  
  # SNS Topics
  "SNS_WARNINGS_TOPIC": "arn:aws:sns:us-east-1:123456789012:prevention-warnings",
  "SNS_ACTIONS_TOPIC": "arn:aws:sns:us-east-1:123456789012:prevention-actions",
  "SNS_ERRORS_TOPIC": "arn:aws:sns:us-east-1:123456789012:prevention-errors",
  
  # Thresholds
  "WARNING_THRESHOLD": "80",      # Percentage
  "ACTION_THRESHOLD": "90",       # Percentage
  
  # Timeouts
  "APPROVAL_TIMEOUT_MINUTES": "30",
  "ROLLBACK_WINDOW_HOURS": "24",
  
  # Refresh Intervals
  "INVENTORY_REFRESH_MINUTES": "15",
  "BUDGET_CHECK_MINUTES": "5"
}
```

### API Gateway Routes (Extended)

**New Routes:**

```python
{
  "/api/prevention/status": {
    "method": "GET",
    "integration": "Lambda",
    "auth": "API_KEY",
    "description": "Get prevention system status"
  },
  "/api/prevention/enable": {
    "method": "POST",
    "integration": "Lambda",
    "auth": "API_KEY",
    "description": "Enable prevention system"
  },
  "/api/prevention/disable": {
    "method": "POST",
    "integration": "Lambda",
    "auth": "API_KEY",
    "description": "Disable prevention system"
  },
  "/api/prevention/resources": {
    "method": "GET",
    "integration": "Lambda",
    "auth": "API_KEY",
    "description": "Get resource inventory"
  },
  "/api/prevention/rollback": {
    "method": "POST",
    "integration": "Lambda",
    "auth": "API_KEY",
    "description": "Rollback a prevention action"
  },
  "/api/prevention/history": {
    "method": "GET",
    "integration": "Lambda",
    "auth": "API_KEY",
    "description": "Get action history"
  }
}
```

## CDK Stack Implementation

### Complete CDK Stack

The complete CDK stack is available in `infrastructure/cdk_stack.py` (500+ lines).

**Key Features:**
- All Phase 3 resources defined
- Proper dependencies and references
- Environment variable configuration
- IAM role updates
- API Gateway route additions
- EventBridge schedule creation
- SNS topic creation with subscriptions
- DynamoDB table creation with indexes and TTL

### Deployment Commands

```bash
# Install dependencies
cd infrastructure
pip install -r requirements.txt

# Synthesize CloudFormation template
cdk synth

# Deploy stack
cdk deploy

# View outputs
cdk deploy --outputs-file outputs.json
```

### Stack Outputs

```json
{
  "CostGuardStack": {
    "ApiEndpoint": "https://abc123.execute-api.us-east-1.amazonaws.com/prod",
    "ApiKeyId": "abc123xyz",
    "WarningsTopicArn": "arn:aws:sns:us-east-1:123456789012:prevention-warnings",
    "ActionsTopicArn": "arn:aws:sns:us-east-1:123456789012:prevention-actions",
    "ErrorsTopicArn": "arn:aws:sns:us-east-1:123456789012:prevention-errors",
    "EventBridgeRuleName": "costguard-budget-monitoring"
  }
}
```

## Migration from Phase 2

### Backward Compatibility

- All Phase 1, 1.5, and 2 resources unchanged
- No breaking changes to existing APIs
- Existing DynamoDB tables unmodified
- Lambda function extended, not replaced

### Deployment Steps

1. **Update Lambda Code:**
   - New service modules added
   - Lambda handler extended
   - No changes to existing code

2. **Create New DynamoDB Tables:**
   - 4 new tables created
   - Existing tables unchanged

3. **Create SNS Topics:**
   - 3 new topics created
   - Subscribe to topics for notifications

4. **Create EventBridge Schedule:**
   - New schedule rule created
   - Targets existing Lambda function

5. **Update IAM Permissions:**
   - Additional permissions added
   - Existing permissions unchanged

6. **Update Environment Variables:**
   - New variables added
   - Existing variables unchanged

### Rollback Plan

If issues arise, rollback is straightforward:

1. **Disable Prevention:**
   ```bash
   curl -X POST -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/prevention/disable"
   ```

2. **Delete EventBridge Rule:**
   ```bash
   aws events delete-rule --name costguard-budget-monitoring
   ```

3. **Remove SNS Subscriptions:**
   ```bash
   aws sns unsubscribe --subscription-arn <subscription-arn>
   ```

4. **Optionally Delete Tables:**
   ```bash
   aws dynamodb delete-table --table-name prevention-config
   aws dynamodb delete-table --table-name resource-inventory
   aws dynamodb delete-table --table-name prevention-audit
   aws dynamodb delete-table --table-name approval-requests
   ```

## Cost Analysis

### Infrastructure Costs

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| DynamoDB (4 tables) | $0.00 | Within 25 GB free tier |
| SNS (3 topics) | $0.00 | Within 1M publishes free tier |
| EventBridge (1 rule) | $0.00 | Rules are free |
| Lambda (EventBridge) | $0.00 | Within 1M invocations free tier |
| CloudWatch Logs | $0.00 | Within 5 GB free tier |
| AWS Budgets | $0.00 | 2 budgets free |

**Total Phase 3 Infrastructure Cost:** $0.00

### Operational Costs

- **Lambda Invocations:** 8,640/month (EventBridge) + ~2,000/month (API) = 10,640/month
- **DynamoDB Operations:** ~100,000 read/write units/month
- **SNS Messages:** ~348/month
- **CloudWatch API Calls:** ~50,000/month

All within AWS Free Tier limits.

## Monitoring and Alarms

### Recommended CloudWatch Alarms

1. **High Error Rate:**
   ```bash
   aws cloudwatch put-metric-alarm \
     --alarm-name costguard-high-error-rate \
     --metric-name Errors \
     --namespace AWS/Lambda \
     --statistic Sum \
     --period 300 \
     --threshold 10 \
     --comparison-operator GreaterThanThreshold
   ```

2. **Budget Threshold Breach:**
   ```bash
   aws cloudwatch put-metric-alarm \
     --alarm-name costguard-budget-breach \
     --metric-name BudgetUtilization \
     --namespace CostGuard \
     --statistic Average \
     --period 300 \
     --threshold 90 \
     --comparison-operator GreaterThanThreshold
   ```

3. **Failed Rollbacks:**
   ```bash
   aws cloudwatch put-metric-alarm \
     --alarm-name costguard-rollback-failures \
     --metric-name RollbackFailures \
     --namespace CostGuard \
     --statistic Sum \
     --period 3600 \
     --threshold 1 \
     --comparison-operator GreaterThanThreshold
   ```

## Security Considerations

### Data Protection

- **Encryption at Rest:** All DynamoDB tables encrypted with AWS managed keys
- **Encryption in Transit:** All API calls use HTTPS
- **API Authentication:** API Gateway API keys required
- **IAM Permissions:** Least privilege principle applied

### Audit Trail

- All actions logged to `prevention-audit` table
- CloudWatch Logs for all Lambda executions
- SNS notifications for all significant events
- 90-day retention for audit logs

### Compliance

- **GDPR:** No PII stored in prevention tables
- **SOC 2:** Audit trail and access controls in place
- **HIPAA:** Not applicable (no health data)

## Related Documentation

- [README](./README.md) - Phase 3 overview
- [Specification](./specification.md) - Complete specification
- [Implementation Summary](./implementation-summary.md) - Implementation details
- [CDK Stack](../../../infrastructure/cdk_stack.py) - Complete CDK code
- [Infrastructure Configs](../../../infrastructure/) - JSON configuration files

## Keywords

infrastructure, CDK, CloudFormation, DynamoDB, SNS, EventBridge, IAM, API Gateway, Lambda, deployment, infrastructure-as-code, AWS resources, permissions, environment variables
