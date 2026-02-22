# Phase 3: Automated Cost Prevention

> **Part of CostGuard AI** - AWS Cost Management & Optimization Platform  
> **Documentation Location:** `docs/technical/phase3-automated-prevention/`  
> **Related:** [Project README](../../../README.md) | [Docs Index](../../INDEX.md) | [Phase 1](../phase1-cost-pipeline/) | [Phase 1.5](../phase1.5-near-realtime/) | [Phase 2](../phase2-ai-forecasting/)

**Status:** ✅ Complete  
**Implementation Date:** January 2026  
**Test Coverage:** 724 tests passing (579 unit + 75 property + 70 integration)  
**Note:** Overall project coverage is 25% due to lambda_handler.py (11% coverage). Phase 3 service modules have 80%+ coverage.

## Overview

Phase 3 adds automated cost prevention capabilities to CostGuard, enabling proactive cost management through budget monitoring, idle resource detection, and automated cost-saving actions. The system continuously monitors AWS budgets and automatically takes action when thresholds are breached, with comprehensive safety mechanisms to prevent unintended disruptions.

## Key Features

- **Budget Threshold Monitoring:** Automatic monitoring every 5 minutes via EventBridge
  - 80% threshold: Warning notifications
  - 90% threshold: Automated prevention actions
- **Idle Resource Detection:** Detect idle resources across 20+ AWS services
  - EC2: CPU < 5% for 2 hours
  - RDS: Connections = 0 for 1 hour
  - Lambda: Invocations = 0 for 24 hours
  - EBS: Unattached for 7 days
  - S3: Requests = 0 for 30 days
  - DynamoDB: Read/Write = 0 for 24 hours
  - And 14+ more services
- **Automated Cost-Saving Actions:**
  - Stop EC2 instances
  - Stop RDS databases
  - Limit Lambda concurrency to 0
  - Snapshot and delete EBS volumes
  - Switch DynamoDB to on-demand billing
  - Delete NAT gateways
- **Safety Guards:**
  - Tag-based protection (Environment=production, CostGuard=protected)
  - Resource whitelists
  - Active usage checks
  - Minimum idle duration validation
  - Dry run mode (enabled by default)
- **Approval Workflows:**
  - SNS notifications for approval requests
  - 30-minute timeout for responses
  - API endpoint for approval/denial
- **Rollback Capability:**
  - 24-hour rollback window
  - Complete state restoration
  - Service-specific rollback logic
- **Comprehensive Audit Logging:**
  - All actions logged to DynamoDB
  - Before/after state captured
  - Timestamps and metadata
- **Backward Compatible:** Maintains full compatibility with Phase 1, 1.5, and 2 endpoints

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  EventBridge Schedule                        │
│  (5-minute intervals for budget monitoring)                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  API Gateway                                 │
│  Phase 3: /api/prevention/*                                 │
│  - GET /status, POST /enable, POST /disable                 │
│  - GET /resources, POST /rollback, GET /history             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Handler                                  │
│  - Route prevention requests                                │
│  - Handle EventBridge events                                │
│  - Validate parameters                                      │
│  - Format responses                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Prevention Engine                                 │
│  - Orchestrate prevention workflow                          │
│  - Monitor budgets every 5 minutes                          │
│  - Discover and analyze resources                           │
│  - Execute or request approval for actions                  │
│  - Send notifications                                       │
└─┬───────┬────────┬────────┬────────┬────────┬──────────┬───┘
  │       │        │        │        │        │          │
  ▼       ▼        ▼        ▼        ▼        ▼          ▼
┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────────┐
│Budg│ │Res │ │Idle│ │Safe│ │Actn│ │Appr│ │Rollbck │
│Mon │ │Mgr │ │Det │ │Grd │ │Exec│ │Mgr │ │Manager │
└────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────────┘
  │       │        │        │        │        │          │
  ▼       ▼        ▼        ▼        ▼        ▼          ▼
┌──────────────────────────────────────────────────────────┐
│  AWS Services: Budgets, EC2, RDS, Lambda, CloudWatch,   │
│  DynamoDB (6 tables), SNS (3 topics), EventBridge       │
└──────────────────────────────────────────────────────────┘
```

## Components

### 1. Budget Monitor (`budget_monitor.py`)
**Purpose:** Monitors AWS Budgets and detects threshold breaches

**Key Methods:**
- `poll_budgets()` - Retrieves all configured budgets
- `check_thresholds()` - Detects 80% warning and 90% action thresholds
- `calculate_utilization()` - Computes budget utilization percentage

**Features:**
- Supports service-specific and total budgets
- Fallback to Phase 1.5 cost estimates
- Multi-budget monitoring
- Time-period budget support

### 2. Resource Manager (`resource_manager.py`)
**Purpose:** Discovers and tracks AWS resources across services

**Key Methods:**
- `discover_resources()` - Discovers resources for all supported services
- `get_resource_metadata()` - Retrieves tags, state, creation date
- `update_inventory()` - Stores resources in DynamoDB

**Supported Services:**
EC2, RDS, Lambda, EBS, S3, DynamoDB, SNS, SQS, ElastiCache, NAT Gateway, ELB, ALB, NLB, CloudFront, API Gateway, Kinesis, Redshift, EMR, SageMaker, Glue

### 3. Idle Detector (`idle_detector.py`)
**Purpose:** Detects idle resources using CloudWatch metrics

**Service-Specific Criteria:**
- **EC2:** CPU < 5% for 2 hours
- **RDS:** Connections = 0 for 1 hour
- **Lambda:** Invocations = 0 for 24 hours
- **EBS:** Unattached for 7 days
- **S3:** Requests = 0 for 30 days
- **DynamoDB:** Read/Write = 0 for 24 hours

**Features:**
- Configurable thresholds per service
- CloudWatch metrics integration
- Idle duration tracking

### 4. Safety Guard (`safety_guard.py`)
**Purpose:** Prevents actions on protected resources

**Protection Mechanisms:**
- Tag-based: `Environment=production`, `CostGuard=protected`, `CostGuard=exclude`
- Whitelist: Resource IDs that should never be touched
- Active usage: Check for active connections/traffic
- Minimum idle duration: Ensure resources meet minimum idle time

**Features:**
- Multiple protection layers
- Comprehensive logging
- Notification on blocked actions

### 5. Action Executor (`action_executor.py`)
**Purpose:** Executes cost-saving actions on resources

**Supported Actions:**
- **EC2:** Stop instances (save ~$50-200/month per instance)
- **RDS:** Stop databases (save ~$100-500/month per database)
- **Lambda:** Limit concurrency to 0 (save ~$10-50/month per function)
- **EBS:** Snapshot and delete volumes (save ~$8-80/month per volume)
- **DynamoDB:** Switch to on-demand billing (save ~$10-100/month per table)
- **NAT Gateway:** Delete with documentation (save ~$32/month per gateway)

**Features:**
- Action prioritization by cost impact
- Error isolation (continue on failures)
- Pre-action state capture
- Audit logging

### 6. Approval Manager (`approval_manager.py`)
**Purpose:** Manages approval workflows for actions

**Key Methods:**
- `request_approval()` - Creates approval request and sends SNS notification
- `wait_for_approval()` - Polls for approval response with 30-minute timeout
- `process_approval_response()` - Handles approval/denial

**Features:**
- SNS notifications with action details
- DynamoDB-based tracking
- 30-minute timeout
- API endpoint for responses

### 7. Rollback Manager (`rollback_manager.py`)
**Purpose:** Enables rollback of prevention actions

**Key Methods:**
- `store_pre_action_state()` - Captures resource state before action
- `execute_rollback()` - Restores resource to previous state
- `check_rollback_window()` - Validates 24-hour window

**Features:**
- 24-hour rollback window
- Service-specific rollback logic
- State restoration from audit logs
- Automatic expiration

### 8. Notification Service (`notification_service.py`)
**Purpose:** Sends notifications via SNS

**Notification Types:**
- **Warnings:** 80% budget threshold (prevention-warnings topic)
- **Actions:** 90% budget threshold (prevention-actions topic)
- **Errors:** System errors (prevention-errors topic)

**Features:**
- Multi-topic routing
- Structured message templates
- Savings calculations
- Timestamp tracking

### 9. Prevention Engine (`prevention_engine.py`)
**Purpose:** Orchestrates the entire prevention workflow

**Workflow:**
1. Monitor budgets every 5 minutes
2. Detect threshold breaches
3. Discover resources
4. Detect idle resources
5. Check safety guards
6. Execute actions (or request approval)
7. Send notifications
8. Log to audit trail

**Features:**
- Dry run mode support
- Configuration management
- Status reporting
- Error handling

### 10. EventBridge Scheduler (`eventbridge_scheduler.py`)
**Purpose:** Handles EventBridge scheduled events

**Key Methods:**
- `parse_event()` - Parses EventBridge event payload
- `is_scheduled_event()` - Detects scheduled vs API events

**Features:**
- 5-minute schedule support
- Event type detection
- Budget monitoring trigger

## API Endpoints

### GET /api/prevention/status

Get prevention system status and configuration.

**Example:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api-id.execute-api.us-east-1.amazonaws.com/prod/api/prevention/status"
```

**Response:**
```json
{
  "success": true,
  "status": {
    "enabled": true,
    "dry_run": false,
    "approval_required": true,
    "last_check": "2026-01-21T10:30:00Z",
    "budgets_monitored": 2,
    "resources_tracked": 150,
    "actions_taken_today": 5,
    "estimated_savings_today": 250.00
  }
}
```

### POST /api/prevention/enable

Enable the prevention system.

**Example:**
```bash
curl -X POST -H "x-api-key: YOUR_API_KEY" \
  "https://api-id.execute-api.us-east-1.amazonaws.com/prod/api/prevention/enable"
```

### POST /api/prevention/disable

Disable the prevention system.

**Example:**
```bash
curl -X POST -H "x-api-key: YOUR_API_KEY" \
  "https://api-id.execute-api.us-east-1.amazonaws.com/prod/api/prevention/disable"
```

### GET /api/prevention/resources

Get resource inventory with optional filters.

**Query Parameters:**
- `service` - Filter by service (ec2, rds, lambda, etc.)
- `state` - Filter by state (running, stopped, etc.)
- `limit` - Maximum records to return (default: 100)

**Example:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api-id.execute-api.us-east-1.amazonaws.com/prod/api/prevention/resources?service=ec2&state=running&limit=50"
```

### POST /api/prevention/rollback

Rollback a prevention action (within 24 hours).

**Request Body:**
```json
{
  "action_id": "action-123"
}
```

**Example:**
```bash
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action_id":"action-123"}' \
  "https://api-id.execute-api.us-east-1.amazonaws.com/prod/api/prevention/rollback"
```

### GET /api/prevention/history

Get action history with optional filters.

**Query Parameters:**
- `start_date` - Filter by start date (YYYY-MM-DD)
- `end_date` - Filter by end date (YYYY-MM-DD)
- `service` - Filter by service
- `status` - Filter by status (success, failed, rolled_back)
- `limit` - Maximum records to return (default: 100)

**Example:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api-id.execute-api.us-east-1.amazonaws.com/prod/api/prevention/history?start_date=2026-01-01&limit=100"
```

## Documentation

- **[Specification](./specification.md)** - Complete Phase 3 specification
- **[Implementation Summary](./implementation-summary.md)** - Implementation details and decisions
- **[Infrastructure Updates](./infrastructure-updates.md)** - CDK infrastructure changes
- **[Requirements](../../../.kiro/specs/automated-cost-prevention/requirements.md)** - Detailed requirements
- **[Design](../../../.kiro/specs/automated-cost-prevention/design.md)** - System design and correctness properties
- **[Tasks](../../../.kiro/specs/automated-cost-prevention/tasks.md)** - Implementation task list
- **[API Examples](../../API_EXAMPLES.md)** - Complete API usage examples

## Testing

**Test Coverage:** 724 tests passing (579 unit + 75 property + 70 integration)

**Note:** Overall project coverage is 25% due to lambda_handler.py having low coverage (11%). Phase 3 service modules individually have 80%+ coverage when tested in isolation.

**Test Types:**
- **Unit Tests:** 579 tests for individual components
- **Property-Based Tests:** 75 tests (15 properties × 100+ iterations each)
- **Integration Tests:** 70 tests for end-to-end flows

**Key Properties Tested:**
1. Budget Threshold Detection
2. Protected Resource Safety
3. Idle Detection Consistency
4. Action Reversibility
5. Dry Run Safety
6. Audit Trail Completeness
7. Multi-Service Coverage
8. Safety Check Ordering
9. Notification Delivery
10. Configuration Validation
11. Approval Timeout Handling
12. Resource Inventory Freshness
13. Action Prioritization
14. Error Isolation
15. Backward Compatibility

## Cost Analysis

### Infrastructure Costs

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| AWS Budgets | $0.00 | 2 budgets free |
| Lambda (EventBridge) | $0.00 | Within 1M free tier |
| DynamoDB (4 tables) | $0.00 | Within 25 GB free tier |
| SNS (3 topics) | $0.00 | Within 1M publishes free tier |
| EventBridge | $0.00 | Rules are free |
| CloudWatch | $0.00 | Within free tier |

**Total Phase 3 Cost:** ~$0.00 (within Free Tier)  
**Total System Cost:** ~$1.51/month (including Phase 1, 1.5, 2, and 3)

### Cost Savings Potential

- **Idle EC2 Instances:** $50-200/month per instance
- **Idle RDS Databases:** $100-500/month per database
- **Unused NAT Gateways:** $32/month per gateway
- **Idle EBS Volumes:** $8-80/month per volume
- **Over-provisioned DynamoDB:** $10-100/month per table

**Estimated Monthly Savings:** $200-1000+ depending on resource usage

## Getting Started

### Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Python 3.11+
- Node.js 18+ (for CDK)
- Existing Phase 1, 1.5, and 2 deployment

### Deployment

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   cd infrastructure
   npm install
   ```

2. **Run Tests:**
   ```bash
   pytest --cov=src --cov-report=html
   ```

3. **Deploy Infrastructure:**
   ```bash
   cd infrastructure
   cdk deploy
   ```

4. **Configure SNS Topics:**
   ```bash
   # Subscribe to notification topics
   aws sns subscribe --topic-arn <warnings-topic-arn> --protocol email --notification-endpoint your-email@example.com
   aws sns subscribe --topic-arn <actions-topic-arn> --protocol email --notification-endpoint your-email@example.com
   aws sns subscribe --topic-arn <errors-topic-arn> --protocol email --notification-endpoint your-email@example.com
   ```

5. **Create Budgets:**
   ```bash
   # Create budgets in AWS Budgets console or via CLI
   aws budgets create-budget --account-id <account-id> --budget file://budget.json
   ```

6. **Test Prevention System:**
   ```bash
   # Check status
   curl -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/prevention/status"
   
   # Enable prevention (starts in dry run mode)
   curl -X POST -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/prevention/enable"
   ```

### Initial Configuration

1. **Start with Dry Run Mode:**
   - System starts in dry run mode by default
   - Monitor dry run reports for 24-48 hours
   - Validate safety mechanisms

2. **Enable Approval Workflow:**
   - Keep approval required initially
   - Review approval requests carefully
   - Gradually disable after confidence is built

3. **Configure Protected Resources:**
   - Tag production resources: `Environment=production`
   - Tag critical resources: `CostGuard=protected`
   - Add resource IDs to whitelist

4. **Monitor and Adjust:**
   - Review action history daily
   - Adjust idle detection thresholds as needed
   - Update budgets based on actual usage

## Performance

### Response Times

- **Status Endpoint:** < 500ms
- **Resources Endpoint:** < 1s
- **History Endpoint:** < 1s
- **Enable/Disable:** < 300ms
- **Rollback:** 2-5s

### Budget Monitoring

- **Frequency:** Every 5 minutes via EventBridge
- **Duration:** 5-10 seconds per execution
- **Threshold Detection:** Real-time

### Resource Discovery

- **Frequency:** Every 15 minutes (configurable)
- **Duration:** 30-60 seconds for 20+ services
- **Inventory Size:** ~40 MB in DynamoDB

## Monitoring

### CloudWatch Metrics

- Budget utilization percentage
- Number of idle resources detected
- Actions executed (dry run vs actual)
- Approval request response time
- Rollback success rate
- Error rate by service
- Cost savings achieved

### CloudWatch Logs

- All Lambda executions logged
- Budget monitoring events
- Resource discovery results
- Action execution details
- Error details with stack traces

## Troubleshooting

### Issue: No actions being taken

**Causes:**
- Prevention system disabled
- Dry run mode enabled
- Budgets not configured
- Threshold not reached

**Solutions:**
- Check status endpoint
- Verify configuration in DynamoDB
- Confirm budgets exist
- Review budget utilization

### Issue: Resources not being discovered

**Causes:**
- IAM permissions missing
- Services not running in region
- Resource discovery errors

**Solutions:**
- Check CloudWatch Logs
- Verify IAM permissions
- Review resource inventory table
- Check service availability

### Issue: Approvals timing out

**Causes:**
- SNS topic not subscribed
- Email not delivered
- Approval not submitted within 30 minutes

**Solutions:**
- Verify SNS subscriptions
- Check email delivery
- Review approval request table
- Adjust timeout if needed

### Issue: Rollbacks failing

**Causes:**
- 24-hour window expired
- IAM permissions missing
- Resource no longer exists

**Solutions:**
- Check action timestamp
- Verify IAM permissions
- Review audit log
- Confirm resource exists

## Related Documentation

- **Phase 1:** [Historical Cost Data Pipeline](../phase1-cost-pipeline/)
- **Phase 1.5:** [Near-Real-Time Cost Estimation](../phase1.5-near-realtime/)
- **Phase 2:** [AI-Powered Cost Forecasting](../phase2-ai-forecasting/)
- **API Examples:** [Complete API Usage Examples](../../API_EXAMPLES.md)
- **Competition Docs:** [Competition Information](../../competition/)
- **Submission Guide:** [Submission Requirements](../../submission/SUBMISSION-GUIDE.md)

## Code References

### Source Files
- `src/services/prevention_engine.py` - Main orchestration
- `src/services/budget_monitor.py` - Budget monitoring
- `src/services/resource_manager.py` - Resource discovery
- `src/services/idle_detector.py` - Idle detection
- `src/services/safety_guard.py` - Safety checks
- `src/services/action_executor.py` - Action execution
- `src/services/approval_manager.py` - Approval workflows
- `src/services/rollback_manager.py` - Rollback management
- `src/services/notification_service.py` - SNS notifications
- `src/services/eventbridge_scheduler.py` - EventBridge integration
- `src/lambda_handler.py` - API routing (Phase 3 endpoints)

### Test Files
- `tests/unit/test_prevention_engine.py`
- `tests/unit/test_budget_monitor.py`
- `tests/unit/test_resource_manager.py`
- `tests/unit/test_idle_detector.py`
- `tests/unit/test_safety_guard.py`
- `tests/unit/test_action_executor.py`
- `tests/unit/test_approval_manager.py`
- `tests/unit/test_rollback_manager.py`
- `tests/unit/test_notification_service.py`
- `tests/unit/test_eventbridge_scheduler.py`
- `tests/property/test_*_properties.py` (15 property test files)

### Infrastructure
- `infrastructure/cdk_stack.py` - Complete CDK stack
- `infrastructure/dynamodb_tables.json` - Table configurations
- `infrastructure/iam_permissions.json` - IAM policies
- `infrastructure/lambda_environment.json` - Environment variables
- `infrastructure/sns_topics.json` - SNS topic configurations
- `infrastructure/api_gateway.json` - API Gateway routes
- `infrastructure/eventbridge_schedule.json` - EventBridge schedule

## Keywords

automated prevention, cost prevention, budget monitoring, idle detection, resource management, safety guards, approval workflows, rollback, EventBridge, AWS Budgets, cost optimization, proactive cost management, automated actions, audit trail, SNS notifications, EC2, RDS, Lambda, EBS, DynamoDB, NAT Gateway, CloudWatch metrics, property-based testing, backward compatibility

## Support

For issues or questions:
1. Check CloudWatch Logs: `/aws/lambda/costguard-cost-data-handler`
2. Review test suite: `tests/unit/` and `tests/property/`
3. Consult specification: `./specification.md`
4. Check requirements: `../../../.kiro/specs/automated-cost-prevention/requirements.md`
5. Review design: `../../../.kiro/specs/automated-cost-prevention/design.md`
