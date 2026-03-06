# Phase 3: Automated Cost Prevention - Specification

## Overview

Phase 3 adds automated cost prevention capabilities to CostGuard, enabling proactive cost management through budget monitoring, idle resource detection, and automated remediation actions with comprehensive safety mechanisms.

## Goals

1. **Prevent Cost Overruns:** Automatically detect and respond to budget threshold breaches
2. **Eliminate Waste:** Identify and remediate idle resources across 22 AWS services (20 with idle detection)
3. **Maintain Safety:** Comprehensive safety guards to prevent accidental disruption
4. **Enable Rollback:** 24-hour rollback capability for all automated actions
5. **Provide Visibility:** Complete audit trail and notification system

## Architecture

### Components

1. **Budget Monitor** - Polls AWS Budgets API every 5 minutes
2. **Resource Manager** - Discovers resources across 22 AWS services
3. **Idle Detector** - Detects idle resources using CloudWatch metrics
4. **Safety Guard** - Validates actions against safety rules
5. **Action Executor** - Executes prevention actions on resources
6. **Approval Manager** - Manages approval workflows with timeout
7. **Rollback Manager** - Handles action rollback within 24 hours
8. **Notification Service** - Sends SNS notifications for warnings, actions, and errors
9. **Prevention Engine** - Orchestrates all components
10. **EventBridge Scheduler** - Triggers budget monitoring every 5 minutes

### Data Flow

```
EventBridge (5 min) → Lambda → Prevention Engine
                                      ↓
                              Budget Monitor
                                      ↓
                          Check Thresholds (80%, 90%)
                                      ↓
                              Resource Manager
                                      ↓
                          Discover Resources (22 services)
                                      ↓
                              Idle Detector
                                      ↓
                          Check Idle Status (CloudWatch)
                                      ↓
                              Safety Guard
                                      ↓
                    Validate (tags, whitelist, active usage)
                                      ↓
                          Approval Manager (if required)
                                      ↓
                              Action Executor
                                      ↓
                    Execute Actions (stop, limit, delete)
                                      ↓
                          Notification Service
                                      ↓
                              SNS Topics
```

## Features

### Budget Monitoring

- **Polling Frequency:** Every 5 minutes via EventBridge
- **Thresholds:**
  - 80% utilization: Warning notification
  - 90% utilization: Trigger prevention actions
- **Budget Types Supported:**
  - Service-specific budgets
  - Total account budgets
  - Time-period budgets
- **Cost Sources:**
  - Actual costs from Cost Explorer
  - Estimated costs from Phase 1.5 (fallback)

### Resource Discovery

- **Services Supported:** 22 AWS services (fully implemented)
  - **Compute (4):** EC2, Lambda, ECS, EKS
  - **Database (4):** RDS, DynamoDB, ElastiCache, Redshift
  - **Storage (2):** EBS, S3
  - **Networking (4):** NAT Gateway, Elastic IP, Application Load Balancer (ALB), Network Load Balancer (NLB), Classic Load Balancer (ELB)
  - **Messaging (2):** SNS, SQS
  - **Application (3):** API Gateway, Step Functions, CloudFront
  - **Analytics (2):** Glue, SageMaker
- **Metadata Collected:**
  - Resource ID, type, service, region
  - Tags, creation date, state
  - CloudWatch metrics
- **Refresh Cycle:** Every 15 minutes
- **Storage:** DynamoDB with TTL

### Idle Detection

Service-specific idle criteria (20 services with idle detection):

| Service | Idle Criteria | Duration |
|---------|--------------|----------|
| EC2 | CPU < 5% | 2 hours |
| EC2 GPU | GPU < 10% | 2 hours |
| RDS | Connections = 0 | 1 hour |
| Lambda | Invocations = 0 | 24 hours |
| EBS | Unattached | 7 days |
| S3 | Requests = 0 | 30 days |
| DynamoDB | Read/Write = 0 | 24 hours |
| ElastiCache | CPU < 5% | 2 hours |
| Redshift | Connections = 0 | 1 hour |
| ECS | No running tasks | 2 hours |
| EKS | No active pods | 2 hours |
| NAT Gateway | Bytes processed = 0 | 1 hour |
| Elastic IP | Unattached | 7 days |
| Load Balancers (ALB/NLB/ELB) | Requests = 0 | 1 hour |
| SNS | Messages published = 0 | 24 hours |
| SQS | Messages sent = 0 | 24 hours |
| API Gateway | Requests = 0 | 24 hours |
| Step Functions | Executions = 0 | 24 hours |
| Glue | No runs | 7 days |
| SageMaker | Invocations = 0 | 24 hours |
| CloudFront | Requests = 0 | 7 days |

- **Configurable:** Per-service thresholds can be adjusted
- **CloudWatch Integration:** Real-time metrics for detection

### Safety Guards

Multiple layers of protection:

1. **Tag-Based Protection**
   - `Environment=production` → Protected
   - `CostGuard=protected` → Protected
   - `CostGuard=exclude` → Excluded from discovery

2. **Whitelist**
   - Specific resource IDs can be whitelisted
   - Whitelisted resources never modified

3. **Active Usage Checks**
   - Active connections → Protected
   - Recent traffic → Protected

4. **Minimum Idle Duration**
   - Resources must meet minimum idle time
   - Prevents premature action on temporarily idle resources

5. **Safety Logging**
   - All blocked actions logged with reasons
   - Notifications sent for blocked actions

### Automated Actions

| Service | Action | Description |
|---------|--------|-------------|
| EC2 | Stop Instance | Stop idle EC2 instances |
| RDS | Stop Database | Stop idle RDS instances/clusters |
| Lambda | Limit Concurrency | Set concurrency to 0 |
| EBS | Snapshot & Delete | Create snapshot, then delete volume |
| DynamoDB | Switch to On-Demand | Change billing mode |
| NAT Gateway | Delete | Delete unused NAT gateways |

- **Prioritization:** Actions sorted by cost impact (highest first)
- **Error Isolation:** Individual action failures don't stop others
- **Audit Logging:** All actions recorded in DynamoDB

### Approval Workflows

- **Configurable:** Can be enabled/disabled
- **Timeout:** 30 minutes (configurable)
- **Channels:**
  - API endpoint for programmatic approval
  - Email response via SNS
- **Notifications:** SNS message with approve/deny URLs
- **Expiration:** Requests expire after timeout

### Rollback Capability

- **Window:** 24 hours from action execution
- **State Storage:** Complete pre-action state stored
- **Supported Actions:**
  - EC2: Restart stopped instances
  - RDS: Restart stopped databases
  - Lambda: Restore concurrency limits
  - EBS: Restore from snapshot (manual)
- **Logging:** All rollback operations logged

### Dry Run Mode

- **Purpose:** Test prevention logic without executing actions
- **Default:** Enabled for safety
- **Behavior:**
  - All logic executes normally
  - Actions logged but not executed
  - Notifications sent with "DRY RUN" prefix
- **Reports:** Detailed dry run reports in audit log

### Notifications

Three SNS topics for different notification types:

1. **Warnings Topic**
   - Budget threshold warnings (80%)
   - Estimated time to action threshold

2. **Actions Topic**
   - Prevention actions executed
   - Approval requests
   - Rollback notifications

3. **Errors Topic**
   - System errors
   - Action failures
   - Configuration issues

**Message Format:**
- Subject: Clear, actionable
- Body: Resource details, reason, estimated savings
- Links: Approve/deny URLs, rollback URLs

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PREVENTION_ENABLED` | `false` | Master switch for prevention system |
| `DRY_RUN_MODE` | `true` | Enable dry run mode |
| `APPROVAL_REQUIRED` | `true` | Require approval for actions |
| `APPROVAL_TIMEOUT_MINUTES` | `30` | Approval timeout |
| `BUDGET_POLL_INTERVAL_MINUTES` | `5` | Budget polling frequency |
| `RESOURCE_REFRESH_INTERVAL_MINUTES` | `15` | Resource inventory refresh |
| `WARNING_THRESHOLD_PERCENT` | `80` | Warning threshold |
| `ACTION_THRESHOLD_PERCENT` | `90` | Action threshold |
| `ROLLBACK_WINDOW_HOURS` | `24` | Rollback window |

### DynamoDB Tables

1. **prevention-config** - System configuration
2. **resource-inventory** - Discovered resources
3. **prevention-audit** - Action audit log
4. **approval-requests** - Approval tracking

### IAM Permissions

Required permissions:
- Budgets: `ViewBudget`, `DescribeBudget`
- Resource Discovery: Read/describe for 22 services
- CloudWatch: `GetMetricStatistics`, `GetMetricData`
- Resource Management: Stop, start, delete, modify
- SNS: `Publish`
- DynamoDB: Full access to CostGuard tables

## Safety-First Approach

1. **Start with Dry Run**
   - Monitor dry run reports for 24-48 hours
   - Validate safety mechanisms
   - Review planned actions

2. **Enable Approval Workflow**
   - Require approval initially
   - Build confidence through manual review
   - Gradually disable after validation

3. **Never Disable Safety Guards**
   - Tag-based protection always active
   - Whitelist always enforced
   - Active usage checks always performed

4. **Monitor Continuously**
   - CloudWatch Logs for all operations
   - SNS notifications for all actions
   - Audit log for complete history

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/prevention/status` | Get system status |
| POST | `/api/prevention/enable` | Enable prevention |
| POST | `/api/prevention/disable` | Disable prevention |
| GET | `/api/prevention/resources` | Get resource inventory |
| POST | `/api/prevention/rollback` | Rollback an action |
| GET | `/api/prevention/history` | Get action history |

## Testing

### Property-Based Tests

15 correctness properties validated:

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

### Unit Tests

- 579 unit tests covering all components
- 87%+ code coverage
- Mocked AWS services using moto

### Integration Tests

- End-to-end prevention workflow
- Multi-service resource discovery
- Approval workflow testing
- Rollback testing
- Backward compatibility with Phases 1, 1.5, and 2

## Cost Analysis

Phase 3 adds minimal cost while providing significant savings:

**Additional Costs:**
- Lambda: +8,640 invocations/month (EventBridge schedule)
- DynamoDB: +4 tables, ~100 MB storage
- SNS: ~348 messages/month
- AWS Budgets: 2 budgets (free)
- EventBridge: Rules are free

**Total Additional Cost:** ~$0.00 (within free tier)

**Potential Savings:**
- Idle EC2 instances: $50-200/month per instance
- Unattached EBS volumes: $8-80/month per volume
- Idle RDS databases: $100-500/month per database
- Unused NAT Gateways: $32/month per gateway

**ROI:** Extremely high - minimal cost, significant savings potential

## Backward Compatibility

Phase 3 maintains 100% backward compatibility:

- All Phase 1, 1.5, and 2 endpoints unchanged
- No breaking changes to existing functionality
- Additive-only architecture
- Independent operation (can be disabled)

## Future Enhancements

Potential Phase 4 features:

1. **Machine Learning:** Predict idle resources before they become idle
2. **Cost Anomaly Detection:** Detect unusual spending patterns
3. **Multi-Account Support:** Manage costs across AWS Organizations
4. **Custom Actions:** User-defined prevention actions
5. **Scheduling:** Schedule actions for specific times
6. **Reporting:** Detailed cost savings reports
7. **Integration:** Slack, Teams, PagerDuty integrations

## References

- [Requirements Document](../../../.kiro/specs/automated-cost-prevention/requirements.md)
- [Design Document](../../../.kiro/specs/automated-cost-prevention/design.md)
- [Implementation Tasks](../../../.kiro/specs/automated-cost-prevention/tasks.md)
- [API Examples](../../API_EXAMPLES.md)
- [Infrastructure Configuration](../../../infrastructure/)
