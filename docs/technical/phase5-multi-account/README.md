# Phase 5: Multi-Account Cost Management

## Overview

Phase 5 transforms CostGuard AI from a single-account tool into a production-ready multi-account platform capable of managing costs across AWS Organizations. This phase enables cost visibility, allocation, and management across multiple AWS accounts within an organization.

**Status**: ✅ Complete  
**Version**: 1.0.0  
**Last Updated**: February 2026

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Setup Guide](#setup-guide)
- [API Documentation](#api-documentation)
- [Cost Allocation](#cost-allocation)
- [Budgets and Forecasting](#budgets-and-forecasting)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## Features

### 🏢 Organization Management
- **Automatic Discovery**: Automatically discovers all AWS accounts in your organization
- **OU Hierarchy**: Maps organizational unit structure
- **Account Metadata**: Stores account names, emails, and status
- **Real-time Sync**: Refreshes organization structure every 4 hours

### 💰 Multi-Account Cost Collection
- **Parallel Processing**: Collects costs from up to 100 accounts simultaneously
- **Cross-Account Access**: Secure role-based access using AWS STS
- **Resilient Collection**: Continues even if individual accounts fail
- **Historical Data**: Collects last 90 days on initial setup
- **Daily Updates**: Automated daily cost collection at 6 AM UTC

### 📊 Consolidated Billing Views
- **Organization-Level**: Total costs across all accounts
- **OU-Level**: Costs aggregated by organizational unit
- **Account-Level**: Individual account cost breakdowns
- **Service Breakdown**: Costs by AWS service across accounts
- **Time Series**: Daily, weekly, and monthly cost trends
- **Performance**: Sub-5-second query response times

### 🏷️ Cost Allocation
- **Tag-Based Allocation**: Allocate costs by Team, Project, Environment tags
- **Custom Rules**: Create percentage-based or tag-based allocation rules
- **Unallocated Tracking**: Identify resources without allocation tags
- **Priority System**: Apply rules in priority order
- **Showback Reports**: Cost visibility without billing
- **Chargeback Reports**: Internal billing with line items

### 💵 Organization-Wide Budgets
- **Hierarchical Budgets**: Set budgets at organization, OU, and account levels
- **Budget Rollup**: Account budgets roll up to OU and organization budgets
- **Utilization Tracking**: Real-time budget utilization monitoring
- **Proactive Alerts**: Warnings at 80% and critical alerts at 100%
- **Budget Forecasting**: Predict when budgets will be exceeded

### 🔮 Cross-Account Forecasting
- **Organization Forecasts**: Predict total organizational spending
- **OU Forecasts**: Forecast costs for organizational units
- **Account Forecasts**: Individual account cost predictions
- **AI-Powered**: Uses existing Phase 2 forecasting engine
- **30-Day Horizon**: Forecasts for the next 30 days

### 🛡️ Organization-Wide Prevention
- **Policy Inheritance**: Policies cascade from organization to OUs to accounts
- **Account Overrides**: Allow account-level policy customization
- **Parallel Execution**: Apply policies across multiple accounts simultaneously
- **Integration**: Uses existing Phase 3 prevention engine

### 🤖 Cross-Account AI Advisor
- **Organization Context**: AI advisor understands multi-account structure
- **Account-Specific Insights**: Targeted recommendations per account
- **Allocation Insights**: Recommendations for improving cost allocation
- **Cross-Account Patterns**: Identifies cost patterns across accounts

### 🔄 Backward Compatibility
- **Single-Account Mode**: Works with existing single-account setups
- **Automatic Detection**: Detects and enables multi-account features
- **Data Preservation**: Migrates existing single-account data
- **API Compatibility**: Maintains existing API endpoints

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  AWS Organizations                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Management Account (CostGuard AI Deployed Here)     │  │
│  │  ├── OU: Production                                   │  │
│  │  │   ├── Account: prod-app (123456789012)           │  │
│  │  │   └── Account: prod-data (234567890123)          │  │
│  │  ├── OU: Development                                  │  │
│  │  │   ├── Account: dev-team-a (345678901234)         │  │
│  │  │   └── Account: dev-team-b (456789012345)         │  │
│  │  └── OU: Shared Services                             │  │
│  │      └── Account: shared-infra (567890123456)       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         CostGuard AI (Management Account)                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  API Gateway - Multi-Account Endpoints               │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────┴───────────────────────────────┐  │
│  │  Lambda Functions                                     │  │
│  │  • Organization Discovery                             │  │
│  │  • Multi-Account Cost Collector                       │  │
│  │  • Cost Aggregator                                    │  │
│  │  • Allocation Engine                                  │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────┴───────────────────────────────┐  │
│  │  DynamoDB Tables                                      │  │
│  │  • organizations (org structure cache)                │  │
│  │  • accounts (account metadata)                        │  │
│  │  • multi_account_costs (cost data by account)        │  │
│  │  • allocation_rules (cost allocation rules)          │  │
│  │  • budgets (organization/OU/account budgets)         │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Account A   │  │  Account B   │  │  Account C   │
│  (AssumeRole)│  │  (AssumeRole)│  │  (AssumeRole)│
│              │  │              │  │              │
│  IAM Role:   │  │  IAM Role:   │  │  IAM Role:   │
│  CostGuard   │  │  CostGuard   │  │  CostGuard   │
│  Collector   │  │  Collector   │  │  Collector   │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Components

1. **Organization Discovery Service**: Discovers and maps AWS Organizations structure
2. **Cross-Account Role Manager**: Manages IAM roles for cross-account access
3. **Multi-Account Cost Collector**: Collects cost data from all member accounts
4. **Cost Aggregation Engine**: Aggregates costs across accounts
5. **Cost Allocation Engine**: Allocates costs based on tags and rules
6. **Organization Budget Service**: Manages hierarchical budgets
7. **Cross-Account Forecast Service**: Generates multi-account forecasts
8. **Organization Prevention Service**: Applies policies across accounts
9. **Cross-Account AI Advisor**: Provides multi-account insights

---

## Prerequisites

### AWS Requirements
- **AWS Organization**: Must have AWS Organizations enabled
- **Management Account Access**: Deploy CostGuard in the management account
- **Cost Explorer**: Enabled in all accounts
- **IAM Permissions**: Organization admin permissions

### Software Requirements
- **AWS CLI**: Version 2.x or later
- **CDK CLI**: `npm install -g aws-cdk`
- **Python**: Version 3.11 or later
- **Git**: For cloning the repository

### AWS Free Tier Considerations
- DynamoDB: On-demand billing (stays within free tier for moderate use)
- Lambda: 15-minute timeout, 1GB memory (optimized for free tier)
- API Gateway: No usage plans (unlimited for testing)
- CloudWatch: 1-week log retention (cost-optimized)

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/costguard-ai.git
cd costguard-ai
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install CDK dependencies
cd infrastructure
npm install
cd ..
```

### 3. Deploy Infrastructure

```bash
# Deploy everything
./deploy.sh

# Or deploy only multi-account components
./deploy.sh --skip-single-account
```

### 4. Set Up Cross-Account Roles

See [Cross-Account Setup Guide](../../infrastructure/CROSS_ACCOUNT_SETUP.md) for detailed instructions.

### 5. Test Organization Discovery

```bash
# Invoke organization discovery
aws lambda invoke \
  --function-name CostGuard-MultiAccountHandler \
  --payload '{"operation": "discover_organization"}' \
  response.json

# Check response
cat response.json
```

### 6. Test Cost Collection

```bash
# Trigger cost collection
aws lambda invoke \
  --function-name CostGuard-MultiAccountCostCollector \
  --payload '{"type": "manual-collection"}' \
  response.json
```

---

## Setup Guide

### Step 1: Deploy Infrastructure

```bash
# Dry run to see what will be deployed
./deploy.sh --dry-run

# Deploy to production
./deploy.sh --region us-east-1 --profile production
```

The deployment script will:
1. Check prerequisites (AWS CLI, CDK, Python)
2. Bootstrap CDK if needed
3. Deploy DynamoDB tables
4. Deploy Lambda functions
5. Create API Gateway endpoints
6. Set up EventBridge rules
7. Configure CloudWatch monitoring
8. Verify deployment

### Step 2: Deploy Cross-Account Roles

**Option A: Using StackSets (Recommended)**

```bash
# Automatically deploy to all organization accounts
./deploy.sh
# (Cross-account roles are deployed automatically)
```

**Option B: Manual Deployment**

```bash
# Generate CloudFormation template
python infrastructure/deploy_multi_account.py --generate-template

# Deploy to each member account
aws cloudformation create-stack \
  --stack-name CostGuardCrossAccountRole \
  --template-body file://cross_account_role_template.yaml \
  --capabilities CAPABILITY_IAM \
  --profile member-account-profile
```

See [Member Account Deployment Guide](../../infrastructure/MEMBER_ACCOUNT_DEPLOYMENT.md) for detailed instructions.

### Step 3: Configure SNS Notifications

```bash
# Subscribe to notifications topic
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:costguard-multi-account-notifications \
  --protocol email \
  --notification-endpoint your-email@example.com
```

### Step 4: Initialize Organization Discovery

```bash
# Discover organization structure
aws lambda invoke \
  --function-name CostGuard-MultiAccountHandler \
  --payload '{"operation": "discover_organization"}' \
  response.json
```

### Step 5: Test Cost Collection

```bash
# Trigger manual cost collection
aws lambda invoke \
  --function-name CostGuard-MultiAccountCostCollector \
  --payload '{"type": "manual-collection", "days": 7}' \
  response.json
```

### Step 6: Verify Deployment

```bash
# Run verification tests
python infrastructure/deploy_multi_account.py --test-only
```

---

## API Documentation

### Base URL

```
https://{api-id}.execute-api.{region}.amazonaws.com/prod/api
```

### Authentication

All API requests require an API key:

```bash
curl -H "x-api-key: YOUR_API_KEY" \
  https://api.costguard.example.com/api/organizations
```

### Endpoints

#### Organizations

**List Organizations**
```http
GET /api/organizations
```

**List Accounts in Organization**
```http
GET /api/organizations/{org_id}/accounts
```

#### Costs

**Get Consolidated Costs**
```http
GET /api/costs/consolidated?start_date=2026-01-01&end_date=2026-01-31
```

**Get Costs by Account**
```http
GET /api/costs/by-account?start_date=2026-01-01&end_date=2026-01-31
```

**Get Account Costs**
```http
GET /api/costs/account/{account_id}?start_date=2026-01-01&end_date=2026-01-31
```

#### Allocation

**Get Allocated Costs by Tag**
```http
GET /api/allocation/by-tag?tag_key=Team&start_date=2026-01-01&end_date=2026-01-31
```

**Get Unallocated Costs**
```http
GET /api/allocation/unallocated?start_date=2026-01-01&end_date=2026-01-31
```

**Create Allocation Rule**
```http
POST /api/allocation/rules
Content-Type: application/json

{
  "name": "Split VPC Costs",
  "rule_type": "PERCENTAGE",
  "conditions": {"service": "VPC"},
  "allocation_target": "Infrastructure",
  "percentage": 50
}
```

#### Budgets

**Get Budget Hierarchy**
```http
GET /api/budgets/hierarchy
```

**Create Organization Budget**
```http
POST /api/budgets/organization
Content-Type: application/json

{
  "budget_amount": 10000,
  "period": "MONTHLY",
  "alert_thresholds": [80, 100]
}
```

**Create OU Budget**
```http
POST /api/budgets/ou/{ou_id}
Content-Type: application/json

{
  "budget_amount": 5000,
  "period": "MONTHLY",
  "alert_thresholds": [80, 100]
}
```

For complete API documentation with examples, see [API Examples](../../API_EXAMPLES.md).

---

## Cost Allocation

### Tag-Based Allocation

CostGuard automatically allocates costs based on resource tags:

**Supported Tags:**
- `Team`: Allocate to teams (e.g., "Engineering", "Marketing")
- `Project`: Allocate to projects (e.g., "ProjectA", "ProjectB")
- `Environment`: Allocate to environments (e.g., "Production", "Development")
- Custom tags: Configure additional allocation tags

**Example:**
```python
# Resources tagged with Team=Engineering will be allocated to Engineering team
resource_tags = {
    "Team": "Engineering",
    "Project": "CostGuard",
    "Environment": "Production"
}
```

### Allocation Rules

Create custom allocation rules for shared costs:

**Percentage-Based Rules:**
```json
{
  "name": "Split VPC Costs 50/50",
  "rule_type": "PERCENTAGE",
  "conditions": {"service": "VPC"},
  "allocations": [
    {"target": "Team-A", "percentage": 50},
    {"target": "Team-B", "percentage": 50}
  ]
}
```

**Tag-Based Rules:**
```json
{
  "name": "Allocate Shared Resources",
  "rule_type": "TAG_BASED",
  "conditions": {"tag": "shared"},
  "allocation_target": "Infrastructure"
}
```

### Showback vs Chargeback

**Showback Reports**: Cost visibility without billing
- View team/project costs
- No actual charges
- Encourages cost awareness

**Chargeback Reports**: Internal billing
- Line-item details
- Actual charges to teams
- CSV/PDF export for finance

---

## Budgets and Forecasting

### Hierarchical Budgets

Set budgets at three levels:

1. **Organization Budget**: Total AWS spending limit
2. **OU Budget**: Spending limit for organizational unit
3. **Account Budget**: Spending limit for individual account

**Budget Rollup:**
- Account budgets roll up to OU budgets
- OU budgets roll up to organization budget
- Alerts trigger at each level

### Budget Alerts

Configure alerts at different thresholds:

- **80% Warning**: Proactive notification
- **100% Critical**: Budget exceeded alert
- **Custom Thresholds**: Configure additional alerts

### Forecasting

AI-powered cost forecasting:

- **30-Day Horizon**: Predict costs for next 30 days
- **Organization-Level**: Total organizational spending
- **OU-Level**: Spending by organizational unit
- **Account-Level**: Individual account predictions
- **Proactive Alerts**: Warn when forecast exceeds budget

---

## Monitoring

### CloudWatch Metrics

**Custom Metrics:**
- `MultiAccountCostCollection.Duration`: Time to collect all accounts
- `MultiAccountCostCollection.SuccessRate`: Percentage of successful collections
- `CostAggregation.CacheHitRate`: Percentage of cache hits
- `AllocationEngine.UnallocatedPercentage`: Percentage of unallocated costs

**AWS Metrics:**
- Lambda invocations, errors, duration
- DynamoDB read/write capacity, throttles
- API Gateway requests, latency, errors

### CloudWatch Alarms

**Critical Alarms:**
- Cost collection failure rate > 10%
- API response time > 5 seconds
- DynamoDB throttling > 0
- Lambda errors > 5 per hour

**Warning Alarms:**
- Unallocated costs > 30%
- Cache miss rate > 50%
- Account collection duration > 8 minutes

### CloudWatch Logs

**Log Groups:**
- `/aws/lambda/CostGuard-OrganizationDiscovery`
- `/aws/lambda/CostGuard-MultiAccountCostCollector`
- `/aws/lambda/CostGuard-CostAggregator`
- `/aws/lambda/CostGuard-AllocationEngine`

**Structured Logging:**
All logs include:
- Timestamp
- Request ID
- Account ID
- Operation
- Duration
- Status

---

## Troubleshooting

### Common Issues

#### Organization Discovery Fails

**Symptom**: Organization discovery returns empty results

**Solution**:
1. Verify AWS Organizations is enabled
2. Check IAM permissions for Organizations API
3. Ensure Lambda role has `organizations:*` permissions
4. Check CloudWatch logs for detailed errors

#### Cost Collection Fails for Some Accounts

**Symptom**: Some accounts show "error" status

**Solution**:
1. Verify cross-account roles are deployed
2. Check external ID matches
3. Verify Cost Explorer is enabled in member accounts
4. Check CloudWatch logs for specific account errors

#### API Returns 403 Forbidden

**Symptom**: API requests return 403 errors

**Solution**:
1. Verify API key is included in request headers
2. Check API key is valid and not expired
3. Verify IAM permissions for API Gateway
4. Check rate limiting hasn't been exceeded

#### DynamoDB Throttling

**Symptom**: DynamoDB throttling errors in logs

**Solution**:
1. DynamoDB uses on-demand billing (auto-scales)
2. Check for hot partitions
3. Review query patterns
4. Consider adding caching

#### High Unallocated Costs

**Symptom**: >30% of costs are unallocated

**Solution**:
1. Review tagging strategy
2. Add allocation tags to resources
3. Create allocation rules for shared costs
4. Use showback reports to identify untagged resources

### Debug Mode

Enable debug logging:

```bash
# Update Lambda environment variable
aws lambda update-function-configuration \
  --function-name CostGuard-MultiAccountHandler \
  --environment Variables={LOG_LEVEL=DEBUG}
```

### Support

For additional support:
1. Check [FAQ](#faq) below
2. Review [API Examples](../../API_EXAMPLES.md)
3. See [Cross-Account Setup Guide](../../infrastructure/CROSS_ACCOUNT_SETUP.md)
4. Check CloudWatch logs for detailed errors

---

## FAQ

### General

**Q: Can I use CostGuard with a single AWS account?**  
A: Yes! CostGuard maintains backward compatibility. If no organization is configured, it operates in single-account mode using Phase 1-4 functionality.

**Q: How many accounts can CostGuard support?**  
A: CostGuard supports up to 100 AWS accounts per organization. Cost collection completes within 10 minutes for 100 accounts.

**Q: Does CostGuard work with AWS Free Tier?**  
A: Yes! CostGuard is optimized for AWS Free Tier with on-demand DynamoDB billing, optimized Lambda memory, and cost-effective log retention.

### Setup

**Q: Do I need to deploy CostGuard in every account?**  
A: No! Deploy CostGuard only in the management account. It uses cross-account roles to access member accounts.

**Q: How do I deploy cross-account roles?**  
A: Use StackSets for automatic deployment, or manually deploy CloudFormation templates to each member account. See [Cross-Account Setup Guide](../../infrastructure/CROSS_ACCOUNT_SETUP.md).

**Q: Can I use CostGuard without AWS Organizations?**  
A: Multi-account features require AWS Organizations. However, single-account mode works without Organizations.

### Cost Allocation

**Q: What tags does CostGuard use for allocation?**  
A: By default: Team, Project, Environment. You can configure custom allocation tags.

**Q: How do I handle shared costs?**  
A: Create allocation rules to split shared costs by percentage or allocate to specific teams.

**Q: What happens to unallocated costs?**  
A: Unallocated costs are tracked separately. CostGuard alerts when unallocated costs exceed 30%.

### Budgets

**Q: Can I set different budgets for different accounts?**  
A: Yes! Set budgets at organization, OU, and account levels. Account budgets roll up to OU and organization budgets.

**Q: How often are budgets updated?**  
A: Budget utilization is updated in real-time (within 15 minutes of cost collection).

**Q: Can I get alerts before exceeding budget?**  
A: Yes! Configure alert thresholds (e.g., 80%, 100%) to receive proactive notifications.

### Performance

**Q: How fast are API queries?**  
A: Consolidated cost queries return within 5 seconds. Results are cached for 1 hour.

**Q: How long does cost collection take?**  
A: Cost collection completes within 10 minutes for 100 accounts using parallel processing.

**Q: Can I collect costs more frequently?**  
A: Yes! Modify the EventBridge rule to trigger more frequently. Default is daily at 6 AM UTC.

### Security

**Q: How does CostGuard access member accounts?**  
A: CostGuard uses AWS STS AssumeRole with external IDs for secure cross-account access.

**Q: What permissions does CostGuard need?**  
A: Read-only permissions for Cost Explorer, CloudWatch, and Organizations API. No write permissions to member accounts.

**Q: Is cost data encrypted?**  
A: Yes! All data is encrypted at rest (DynamoDB) and in transit (TLS 1.2+).

---

## Next Steps

1. **Deploy Infrastructure**: Follow the [Setup Guide](#setup-guide)
2. **Configure Cross-Account Roles**: See [Cross-Account Setup](../../infrastructure/CROSS_ACCOUNT_SETUP.md)
3. **Set Up Cost Allocation**: Create allocation rules and tags
4. **Configure Budgets**: Set organization, OU, and account budgets
5. **Monitor Costs**: Use API or CloudWatch dashboards

---

## Related Documentation

- [Cross-Account Setup Guide](../../infrastructure/CROSS_ACCOUNT_SETUP.md)
- [Member Account Deployment](../../infrastructure/MEMBER_ACCOUNT_DEPLOYMENT.md)
- [API Examples](../../API_EXAMPLES.md)
- [Deployment Scripts](../../../DEPLOYMENT_SCRIPTS.md)
- [Project Status](../../PROJECT_STATUS.md)

---

**Version**: 1.0.0  
**Last Updated**: February 2026  
**Status**: ✅ Production Ready
