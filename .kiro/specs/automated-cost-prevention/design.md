# Design Document: Automated Cost Prevention

## Overview

The Automated Cost Prevention system (Phase 3) provides proactive cost management by monitoring AWS budgets and automatically stopping idle resources before budget thresholds are exceeded. The system supports 20+ AWS services with comprehensive safety mechanisms to protect production workloads.

### Key Design Principles

1. **Safety First**: Multiple layers of safety checks prevent accidental disruption of production resources
2. **Transparency**: Complete audit trail and notifications for all automated actions
3. **Configurability**: Flexible configuration for thresholds, idle criteria, and safety rules
4. **Reversibility**: All actions can be rolled back within 24 hours
5. **Efficiency**: Batch operations and caching minimize API calls and costs

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     EventBridge Schedule                         │
│              (Every 5 minutes - Budget Check)                    │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Prevention Lambda Function                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Budget Monitor → Resource Manager → Idle Detector       │  │
│  │       ↓                                                   │  │
│  │  Safety Guard → Action Executor → Notification Service   │  │
│  └──────────────────────────────────────────────────────────┘  │
└────┬────────────────┬────────────────┬────────────────┬────────┘
     │                │                │                │
     ▼                ▼                ▼                ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Budgets │   │ DynamoDB │   │CloudWatch│   │   SNS    │
│   API    │   │ (Config, │   │ Metrics  │   │ (Alerts) │
│          │   │  Audit)  │   │          │   │          │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
                     │
                     ▼
            ┌────────────────┐
            │  EC2, RDS, EBS │
            │  Lambda, S3,   │
            │  DynamoDB, etc │
            │  (20+ Services)│
            └────────────────┘
```

### Component Architecture

```
PreventionEngine
├── BudgetMonitor
│   ├── poll_budgets()
│   ├── check_thresholds()
│   └── calculate_utilization()
├── ResourceManager
│   ├── discover_resources()
│   ├── get_resource_metadata()
│   └── update_inventory()
├── IdleDetector
│   ├── check_ec2_idle()
│   ├── check_rds_idle()
│   ├── check_lambda_idle()
│   └── check_service_idle()
├── SafetyGuard
│   ├── check_tags()
│   ├── check_whitelist()
│   ├── check_active_usage()
│   └── validate_safe_state()
├── ActionExecutor
│   ├── stop_ec2_instance()
│   ├── stop_rds_instance()
│   ├── limit_lambda_concurrency()
│   └── execute_action()
├── ApprovalManager
│   ├── request_approval()
│   ├── wait_for_approval()
│   └── process_approval_response()
├── RollbackManager
│   ├── store_pre_action_state()
│   ├── execute_rollback()
│   └── restore_resource_state()
└── NotificationService
    ├── send_warning()
    ├── send_action_notification()
    └── send_error_notification()
```

## Components and Interfaces

### 1. BudgetMonitor

**Purpose**: Monitor AWS Budgets and detect threshold breaches

**Interface**:
```python
class BudgetMonitor:
    def __init__(self, budgets_client, cost_estimator):
        """Initialize with AWS Budgets client and cost estimator"""
        
    def poll_budgets(self) -> List[BudgetStatus]:
        """Poll all budgets and return current status"""
        
    def check_thresholds(self, budget_status: BudgetStatus) -> ThresholdEvent:
        """Check if budget has crossed warning (80%) or action (90%) thresholds"""
        
    def calculate_utilization(self, budget: Budget) -> float:
        """Calculate current budget utilization percentage"""
```

**Data Models**:
```python
@dataclass
class BudgetStatus:
    budget_name: str
    limit: float
    actual_spend: float
    forecasted_spend: float
    utilization_percent: float
    currency: str
    time_period: str

@dataclass
class ThresholdEvent:
    budget_name: str
    threshold_type: str  # "warning" or "action"
    utilization_percent: float
    timestamp: str
```

### 2. ResourceManager

**Purpose**: Discover and manage resources across 20+ AWS services

**Interface**:
```python
class ResourceManager:
    def __init__(self, aws_clients: Dict[str, Any], dynamodb_client):
        """Initialize with AWS service clients"""
        
    def discover_resources(self, services: List[str]) -> List[Resource]:
        """Discover all resources across specified services"""
        
    def get_resource_metadata(self, resource: Resource) -> ResourceMetadata:
        """Get detailed metadata for a resource including tags"""
        
    def update_inventory(self, resources: List[Resource]):
        """Update resource inventory in DynamoDB"""
```

**Supported Services**:
- Compute: EC2, Lambda, ECS, EKS
- Database: RDS, DynamoDB, ElastiCache, Redshift
- Storage: EBS, S3
- Networking: NAT Gateway, Elastic IP, Load Balancers
- Application: SNS, SQS, API Gateway, Step Functions
- Analytics: Glue, SageMaker
- CDN: CloudFront

**Data Models**:
```python
@dataclass
class Resource:
    resource_id: str
    resource_type: str  # "ec2", "rds", "lambda", etc.
    service: str
    region: str
    tags: Dict[str, str]
    state: str
    creation_date: str
    
@dataclass
class ResourceMetadata:
    resource: Resource
    cost_per_hour: float
    last_activity: str
    metrics: Dict[str, float]
```

### 3. IdleDetector

**Purpose**: Determine if resources are idle based on service-specific criteria

**Interface**:
```python
class IdleDetector:
    def __init__(self, cloudwatch_client):
        """Initialize with CloudWatch client"""
        
    def is_resource_idle(self, resource: Resource, metadata: ResourceMetadata) -> IdleStatus:
        """Determine if resource is idle based on service-specific criteria"""
        
    def get_idle_criteria(self, service: str) -> IdleCriteria:
        """Get idle detection criteria for a service"""
```

**Idle Criteria by Service**:
- EC2: CPU < 5% for 2 hours
- RDS: Connections = 0 for 1 hour
- Lambda: Invocations = 0 for 24 hours
- EBS: Unattached for 7 days
- S3: Requests = 0 for 30 days
- DynamoDB: Read/Write = 0 for 24 hours

**Data Models**:
```python
@dataclass
class IdleStatus:
    resource_id: str
    is_idle: bool
    idle_duration: int  # minutes
    metrics_used: Dict[str, float]
    confidence: float  # 0.0 to 1.0
    
@dataclass
class IdleCriteria:
    service: str
    metric_name: str
    threshold: float
    duration_minutes: int
```

### 4. SafetyGuard

**Purpose**: Enforce safety rules to protect production resources

**Interface**:
```python
class SafetyGuard:
    def __init__(self, config: SafetyConfig):
        """Initialize with safety configuration"""
        
    def is_action_safe(self, resource: Resource, action: str) -> SafetyCheck:
        """Check if action is safe to perform on resource"""
        
    def check_tags(self, resource: Resource) -> bool:
        """Check if resource has protected tags"""
        
    def check_whitelist(self, resource: Resource) -> bool:
        """Check if resource is in whitelist"""
        
    def check_active_usage(self, resource: Resource) -> bool:
        """Check if resource has active connections/traffic"""
```

**Safety Rules**:
1. Never touch resources with "Environment=production" tag
2. Never touch resources with "CostGuard=protected" tag
3. Never touch resources with "CostGuard=exclude" tag
4. Never touch resources in whitelist
5. Never touch resources with active connections
6. Require minimum idle duration before action

**Data Models**:
```python
@dataclass
class SafetyCheck:
    is_safe: bool
    blocked_reason: Optional[str]
    checks_performed: List[str]
    
@dataclass
class SafetyConfig:
    protected_tags: List[str]
    whitelist_ids: List[str]
    minimum_idle_minutes: Dict[str, int]
    dry_run_mode: bool
```

### 5. ActionExecutor

**Purpose**: Execute automated actions on resources

**Interface**:
```python
class ActionExecutor:
    def __init__(self, aws_clients: Dict[str, Any], audit_logger):
        """Initialize with AWS service clients"""
        
    def execute_action(self, resource: Resource, action: str) -> ActionResult:
        """Execute action on resource"""
        
    def stop_ec2_instance(self, instance_id: str) -> ActionResult:
        """Stop EC2 instance"""
        
    def stop_rds_instance(self, db_identifier: str) -> ActionResult:
        """Stop RDS database"""
        
    def limit_lambda_concurrency(self, function_name: str, limit: int) -> ActionResult:
        """Set Lambda concurrency limit"""
```

**Actions by Service**:
- EC2: Stop instance (not terminate)
- RDS: Stop database
- Lambda: Set concurrency to 0
- EBS: Snapshot then delete (if unattached)
- DynamoDB: Switch to on-demand mode
- NAT Gateway: Delete (with documentation)

**Data Models**:
```python
@dataclass
class ActionResult:
    resource_id: str
    action: str
    success: bool
    error_message: Optional[str]
    pre_action_state: Dict[str, Any]
    post_action_state: Dict[str, Any]
    estimated_savings: float
    timestamp: str
```

### 6. ApprovalManager

**Purpose**: Manage approval workflow for automated actions

**Interface**:
```python
class ApprovalManager:
    def __init__(self, sns_client, dynamodb_client):
        """Initialize with SNS and DynamoDB clients"""
        
    def request_approval(self, actions: List[PlannedAction]) -> ApprovalRequest:
        """Send approval request via SNS"""
        
    def wait_for_approval(self, request_id: str, timeout_minutes: int) -> ApprovalResponse:
        """Wait for approval response"""
        
    def process_approval_response(self, request_id: str, approved: bool):
        """Process approval response from API or email"""
```

**Data Models**:
```python
@dataclass
class PlannedAction:
    resource_id: str
    resource_type: str
    action: str
    reason: str
    estimated_savings: float
    
@dataclass
class ApprovalRequest:
    request_id: str
    actions: List[PlannedAction]
    total_estimated_savings: float
    expires_at: str
    
@dataclass
class ApprovalResponse:
    request_id: str
    approved: bool
    approved_by: Optional[str]
    timestamp: str
```

### 7. RollbackManager

**Purpose**: Rollback automated actions

**Interface**:
```python
class RollbackManager:
    def __init__(self, aws_clients: Dict[str, Any], dynamodb_client):
        """Initialize with AWS clients"""
        
    def store_pre_action_state(self, resource: Resource, action: str):
        """Store resource state before action"""
        
    def execute_rollback(self, action_id: str) -> RollbackResult:
        """Rollback a specific action"""
        
    def restore_resource_state(self, resource_id: str, state: Dict[str, Any]) -> bool:
        """Restore resource to previous state"""
```

**Data Models**:
```python
@dataclass
class RollbackResult:
    action_id: str
    resource_id: str
    success: bool
    restored_state: Dict[str, Any]
    timestamp: str
```

### 8. NotificationService

**Purpose**: Send notifications via SNS

**Interface**:
```python
class NotificationService:
    def __init__(self, sns_client, config: NotificationConfig):
        """Initialize with SNS client"""
        
    def send_warning(self, budget_status: BudgetStatus):
        """Send warning notification (80% threshold)"""
        
    def send_action_notification(self, actions: List[ActionResult]):
        """Send notification about automated actions"""
        
    def send_error_notification(self, error: Exception, context: Dict[str, Any]):
        """Send error notification"""
```

## Data Models

### DynamoDB Tables

**1. prevention-config**
- Partition Key: config_key (String)
- Attributes: config_value (Map), updated_at (String)
- Purpose: Store prevention configuration

**2. resource-inventory**
- Partition Key: resource_id (String)
- Sort Key: timestamp (String)
- Attributes: resource_type, service, region, tags, state, metadata
- Purpose: Track all discovered resources

**3. prevention-audit**
- Partition Key: action_id (String)
- Sort Key: timestamp (String)
- Attributes: event_type, resource_id, action, result, details
- TTL: 90 days
- Purpose: Complete audit trail

**4. approval-requests**
- Partition Key: request_id (String)
- Attributes: actions, status, expires_at, approved_by
- TTL: 7 days
- Purpose: Track approval requests

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Budget Threshold Detection
*For any* budget with utilization >= 80%, the Budget_Monitor should trigger a threshold event within 5 minutes of the threshold being crossed.
**Validates: Requirements 1.2, 1.3**

### Property 2: Protected Resource Safety
*For any* resource tagged with "Environment=production" or "CostGuard=protected", the Safety_Guard should never allow automated actions.
**Validates: Requirements 4.1, 4.2**

### Property 3: Idle Detection Consistency
*For any* resource, if the Idle_Detector determines it is idle, then the resource's metrics must meet the service-specific idle criteria for the required duration.
**Validates: Requirements 3.1-3.8**

### Property 4: Action Reversibility
*For any* automated action taken, there must exist a rollback operation that can restore the resource to its pre-action state within 24 hours.
**Validates: Requirements 9.1-9.7**

### Property 5: Dry Run Safety
*For any* execution in dry run mode, no actual resource management actions should be performed, only logged.
**Validates: Requirements 6.1, 6.2**

### Property 6: Audit Trail Completeness
*For any* automated action, there must be a corresponding audit log entry with complete details (resource, action, result, timestamp).
**Validates: Requirements 12.1-12.8**

### Property 7: Multi-Service Coverage
*For any* of the 20+ supported services, the Resource_Manager should be able to discover and manage resources of that service type.
**Validates: Requirements 2.1**

### Property 8: Safety Check Ordering
*For any* planned action, the Safety_Guard checks must be performed before the Action_Executor executes the action.
**Validates: Requirements 4.7**

### Property 9: Notification Delivery
*For any* threshold event or automated action, a notification should be sent via SNS within 1 minute.
**Validates: Requirements 8.1-8.6**

### Property 10: Configuration Validation
*For any* configuration change, the system should validate the configuration before applying it.
**Validates: Requirements 11.6**

### Property 11: Approval Timeout Handling
*For any* approval request, if no response is received within 30 minutes, the system should default to not taking action.
**Validates: Requirements 7.5**

### Property 12: Resource Inventory Freshness
*For any* resource in the inventory, the data should be no more than 15 minutes old.
**Validates: Requirements 2.5**

### Property 13: Action Prioritization
*For any* set of planned actions, they should be executed in order of cost impact (highest cost resources first).
**Validates: Requirements 5.7**

### Property 14: Error Isolation
*For any* action that fails, the system should continue processing remaining actions rather than stopping.
**Validates: Requirements 5.8**

### Property 15: Backward Compatibility
*For any* Phase 1, 1.5, or 2 API endpoint, it should continue to function unchanged after Phase 3 deployment.
**Validates: Requirements 15.1-15.5**

## Error Handling

### Error Categories

1. **Budget API Errors**
   - Retry with exponential backoff (3 attempts)
   - Fall back to Phase 1.5 cost estimates
   - Log error and notify administrators

2. **Resource Discovery Errors**
   - Skip failed service and continue with others
   - Log error with service details
   - Retry on next cycle

3. **Action Execution Errors**
   - Log error with full context
   - Continue with remaining actions
   - Notify administrators
   - Store failed action for manual review

4. **Safety Check Errors**
   - Default to blocking action (fail-safe)
   - Log error and reason
   - Notify administrators

5. **Approval Timeout**
   - Default to not taking action
   - Log timeout event
   - Notify administrators

## Testing Strategy

### Unit Tests
- Test each component independently with mocked dependencies
- Test safety checks with various tag combinations
- Test idle detection with different metric values
- Test action execution with mocked AWS APIs
- Test error handling for each error category

### Property-Based Tests
- Test all 15 correctness properties with 100+ iterations
- Generate random resources with various states
- Generate random budget scenarios
- Test safety mechanisms with random tag combinations
- Test rollback with random action sequences

### Integration Tests
- Test end-to-end prevention workflow
- Test with multiple services simultaneously
- Test approval workflow with timeouts
- Test rollback after actions
- Test backward compatibility with Phase 1/1.5/2

### Service-Specific Tests
- Test resource discovery for each of 20+ services
- Test idle detection for each service
- Test action execution for each service
- Test rollback for each service

## Deployment Strategy

### Phase 3 Deployment Steps

1. **Deploy DynamoDB Tables**
   - prevention-config
   - resource-inventory
   - prevention-audit
   - approval-requests

2. **Deploy Lambda Function**
   - Update existing Lambda with Phase 3 code
   - Add environment variables for configuration
   - Update IAM role with new permissions

3. **Deploy EventBridge Schedule**
   - Create schedule for budget monitoring (every 5 minutes)
   - Configure Lambda as target

4. **Deploy SNS Topics**
   - Create topics for warnings, actions, errors
   - Configure subscriptions

5. **Deploy API Gateway Routes**
   - Add Phase 3 endpoints
   - Maintain Phase 1/1.5/2 routes

6. **Enable Dry Run Mode**
   - Start with dry run enabled
   - Monitor for 24-48 hours
   - Review dry run reports
   - Disable dry run after validation

## Monitoring and Observability

### CloudWatch Metrics
- BudgetUtilization (per budget)
- ResourcesDiscovered (per service)
- ResourcesStopped (per service)
- SafetyCheckBlocks (count)
- CostSavings (estimated, per action)
- ActionExecutionTime (milliseconds)
- ApprovalRequestCount
- RollbackCount

### CloudWatch Logs
- Budget monitoring events
- Resource discovery results
- Idle detection results
- Safety check results
- Action execution results
- Approval workflow events
- Rollback operations
- Error events

### Alarms
- Budget utilization > 95%
- Action execution failures > 5 per hour
- Safety check blocks > 10 per hour
- Approval timeouts > 3 per day

## Security Considerations

1. **IAM Permissions**: Least privilege for resource management
2. **API Authentication**: API key required for all endpoints
3. **Audit Trail**: Complete logging of all actions
4. **Encryption**: DynamoDB encryption at rest
5. **Tag-Based Access Control**: Respect resource tags for protection
