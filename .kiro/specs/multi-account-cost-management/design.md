# Design Document: Multi-Account Cost Management

## Overview

This document describes the design for Phase 5 of CostGuard AI: Multi-Account Cost Management. This phase extends CostGuard AI from a single-account tool to a production-ready multi-account platform capable of managing costs across AWS Organizations.

**Purpose:** Enable cost visibility, allocation, and management across multiple AWS accounts within an organization.

**Key Design Principles:**
1. **Secure by Default:** Use IAM roles with least-privilege permissions
2. **Resilient:** Handle account failures gracefully without breaking the system
3. **Scalable:** Support up to 100 accounts with parallel processing
4. **Backward Compatible:** Maintain single-account functionality
5. **Performance:** Cache aggressively, process in parallel

**Technology Stack:**
- **Language:** Python 3.11
- **Compute:** AWS Lambda (serverless)
- **Storage:** Amazon DynamoDB
- **APIs:** AWS Organizations, Cost Explorer, STS
- **Infrastructure:** AWS CDK (Python)

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
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         CostGuard AI (Management Account)                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  API Gateway                                          │  │
│  │  /api/organizations, /api/costs/consolidated, etc.   │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────┴───────────────────────────────┐  │
│  │  Lambda Functions                                     │  │
│  │  ┌────────────────┐  ┌────────────────┐             │  │
│  │  │ Organization   │  │ Multi-Account  │             │  │
│  │  │ Discovery      │  │ Cost Collector │             │  │
│  │  └────────────────┘  └────────────────┘             │  │
│  │  ┌────────────────┐  ┌────────────────┐             │  │
│  │  │ Cost           │  │ Allocation     │             │  │
│  │  │ Aggregator     │  │ Engine         │             │  │
│  │  └────────────────┘  └────────────────┘             │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────┴───────────────────────────────┐  │
│  │  DynamoDB Tables                                      │  │
│  │  - organizations (org structure cache)                │  │
│  │  - accounts (account metadata)                        │  │
│  │  - multi_account_costs (cost data by account)        │  │
│  │  - allocation_rules (cost allocation rules)          │  │
│  │  - budgets (organization/OU/account budgets)         │  │
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
│              │  │              │  │              │
│  Cost Data   │  │  Cost Data   │  │  Cost Data   │
│  CloudWatch  │  │  CloudWatch  │  │  CloudWatch  │
└──────────────┘  └──────────────┘  └──────────────┘
```


### System Flow

1. **Organization Discovery:**
   - Lambda function calls Organizations API
   - Retrieves organization structure (OUs, accounts)
   - Caches structure in DynamoDB (24-hour TTL)

2. **Cross-Account Role Setup:**
   - CloudFormation templates deployed to member accounts
   - IAM roles created with read-only permissions
   - External ID configured for security

3. **Cost Collection:**
   - Lambda function triggered daily (EventBridge)
   - Assumes role in each member account (parallel)
   - Collects cost data from Cost Explorer API
   - Stores in DynamoDB with account_id partition key

4. **Cost Aggregation:**
   - Lambda function aggregates costs across accounts
   - Generates consolidated views
   - Caches results for 1 hour

5. **Cost Allocation:**
   - Lambda function processes cost data
   - Applies tag-based allocation rules
   - Calculates allocated vs unallocated costs

6. **API Queries:**
   - API Gateway receives requests
   - Lambda functions query DynamoDB
   - Returns consolidated or per-account data

---

## Components and Interfaces

### Component 1: Organization Discovery Service

**Purpose:** Discover and map AWS Organizations structure

**Responsibilities:**
- Call AWS Organizations API to retrieve organization structure
- Map organization hierarchy (Management → OUs → Member Accounts)
- Store organization structure in DynamoDB
- Refresh organization structure daily
- Detect new/removed accounts

**Interfaces:**

```python
class OrganizationDiscoveryService:
    def discover_organization(self) -> Organization:
        """Discover organization structure from AWS Organizations API"""
        
    def get_all_accounts(self, org_id: str) -> List[Account]:
        """Get all accounts in organization"""
        
    def get_ou_hierarchy(self, org_id: str) -> OUHierarchy:
        """Get organizational unit hierarchy"""
        
    def refresh_organization_cache(self, org_id: str) -> None:
        """Refresh cached organization structure"""
```

**Data Models:**

```python
@dataclass
class Organization:
    id: str
    arn: str
    master_account_id: str
    feature_set: str  # "ALL" or "CONSOLIDATED_BILLING"
    
@dataclass
class Account:
    id: str
    arn: str
    name: str
    email: str
    status: str  # "ACTIVE", "SUSPENDED", "PENDING_CLOSURE"
    joined_method: str
    joined_timestamp: datetime
    
@dataclass
class OrganizationalUnit:
    id: str
    arn: str
    name: str
    parent_id: Optional[str]
```

**AWS APIs Used:**
- `organizations:DescribeOrganization`
- `organizations:ListAccounts`
- `organizations:ListOrganizationalUnitsForParent`
- `organizations:ListAccountsForParent`

---

### Component 2: Cross-Account Role Manager

**Purpose:** Manage IAM roles for cross-account access

**Responsibilities:**
- Generate CloudFormation templates for IAM roles
- Validate role permissions
- Provide role ARN for each account
- Handle role assumption errors

**Interfaces:**

```python
class CrossAccountRoleManager:
    def generate_role_template(self, management_account_id: str, external_id: str) -> str:
        """Generate CloudFormation template for cross-account role"""
        
    def get_role_arn(self, account_id: str) -> str:
        """Get IAM role ARN for account"""
        
    def assume_role(self, account_id: str, role_name: str, external_id: str) -> Credentials:
        """Assume role in member account"""
        
    def validate_role_permissions(self, account_id: str) -> bool:
        """Validate role has required permissions"""
```

**IAM Role Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    }
  ]
}
```

**Trust Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::{management_account_id}:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "{external_id}"
        }
      }
    }
  ]
}
```

---

### Component 3: Multi-Account Cost Collector

**Purpose:** Collect cost data from all member accounts

**Responsibilities:**
- Assume roles in member accounts
- Call Cost Explorer API for each account
- Handle collection failures gracefully
- Store cost data in DynamoDB
- Process accounts in parallel

**Interfaces:**

```python
class MultiAccountCostCollector:
    def collect_all_accounts(self, org_id: str, start_date: date, end_date: date) -> CollectionResult:
        """Collect cost data from all accounts in organization"""
        
    def collect_account(self, account_id: str, start_date: date, end_date: date) -> AccountCostData:
        """Collect cost data from single account"""
        
    def collect_parallel(self, account_ids: List[str], start_date: date, end_date: date) -> List[AccountCostData]:
        """Collect cost data from multiple accounts in parallel"""
```

**Data Models:**

```python
@dataclass
class AccountCostData:
    account_id: str
    start_date: date
    end_date: date
    total_cost: Decimal
    costs_by_service: Dict[str, Decimal]
    costs_by_day: Dict[date, Decimal]
    collection_timestamp: datetime
    status: str  # "SUCCESS", "FAILED", "PARTIAL"
    
@dataclass
class CollectionResult:
    total_accounts: int
    successful: int
    failed: int
    failed_accounts: List[str]
    collection_duration: float
```

**Parallel Processing:**
- Use `concurrent.futures.ThreadPoolExecutor`
- Max 10 concurrent account collections
- Timeout: 60 seconds per account
- Retry failed accounts up to 3 times

---

### Component 4: Cost Aggregation Engine

**Purpose:** Aggregate costs across multiple accounts

**Responsibilities:**
- Aggregate costs by organization
- Aggregate costs by OU
- Aggregate costs by time period
- Generate consolidated views
- Cache aggregated results

**Interfaces:**

```python
class CostAggregationEngine:
    def aggregate_organization_costs(self, org_id: str, start_date: date, end_date: date) -> AggregatedCosts:
        """Aggregate costs for entire organization"""
        
    def aggregate_ou_costs(self, ou_id: str, start_date: date, end_date: date) -> AggregatedCosts:
        """Aggregate costs for organizational unit"""
        
    def aggregate_by_service(self, account_ids: List[str], start_date: date, end_date: date) -> Dict[str, Decimal]:
        """Aggregate costs by service across accounts"""
        
    def get_top_spending_accounts(self, org_id: str, limit: int = 5) -> List[AccountSpending]:
        """Get top spending accounts"""
```

**Data Models:**

```python
@dataclass
class AggregatedCosts:
    entity_id: str  # org_id or ou_id
    entity_type: str  # "ORGANIZATION" or "OU"
    start_date: date
    end_date: date
    total_cost: Decimal
    account_count: int
    costs_by_account: Dict[str, Decimal]
    costs_by_service: Dict[str, Decimal]
    costs_by_day: Dict[date, Decimal]
    
@dataclass
class AccountSpending:
    account_id: str
    account_name: str
    total_cost: Decimal
    percentage_of_total: float
```

---

### Component 5: Cost Allocation Engine

**Purpose:** Allocate costs based on tags and rules

**Responsibilities:**
- Extract cost allocation tags
- Apply allocation rules
- Calculate allocated vs unallocated costs
- Generate allocation reports

**Interfaces:**

```python
class CostAllocationEngine:
    def allocate_by_tags(self, account_id: str, start_date: date, end_date: date) -> AllocationResult:
        """Allocate costs based on resource tags"""
        
    def apply_allocation_rules(self, costs: AccountCostData, rules: List[AllocationRule]) -> AllocationResult:
        """Apply custom allocation rules"""
        
    def calculate_unallocated_costs(self, account_id: str, start_date: date, end_date: date) -> Decimal:
        """Calculate costs that cannot be allocated"""
        
    def get_allocation_by_team(self, org_id: str, start_date: date, end_date: date) -> Dict[str, Decimal]:
        """Get costs allocated by team"""
```

**Data Models:**

```python
@dataclass
class AllocationRule:
    rule_id: str
    name: str
    priority: int
    rule_type: str  # "TAG_BASED", "PERCENTAGE", "FIXED"
    conditions: Dict[str, Any]
    allocation_target: str
    
@dataclass
class AllocationResult:
    total_cost: Decimal
    allocated_cost: Decimal
    unallocated_cost: Decimal
    allocation_percentage: float
    allocations_by_category: Dict[str, Decimal]
```

**Allocation Logic:**
1. Extract tags from cost data
2. Match tags against allocation rules (by priority)
3. Apply first matching rule
4. Track unallocated costs (no matching rule)



---

## Data Models

### DynamoDB Tables

#### Table 1: `organizations`

**Purpose:** Cache organization structure

**Schema:**
```python
{
    "org_id": str,  # Partition key
    "arn": str,
    "master_account_id": str,
    "feature_set": str,
    "last_updated": int,  # Unix timestamp
    "ttl": int  # 24 hours from last_updated
}
```

#### Table 2: `accounts`

**Purpose:** Store account metadata

**Schema:**
```python
{
    "account_id": str,  # Partition key
    "org_id": str,  # GSI partition key
    "name": str,
    "email": str,
    "status": str,
    "ou_id": str,
    "role_arn": str,
    "external_id": str,
    "last_collection": int,  # Unix timestamp
    "collection_status": str  # "SUCCESS", "FAILED", "PENDING"
}
```

**GSI:** `org_id-index` (for querying all accounts in organization)

#### Table 3: `multi_account_costs`

**Purpose:** Store cost data by account

**Schema:**
```python
{
    "account_id": str,  # Partition key
    "date": str,  # Sort key (YYYY-MM-DD)
    "total_cost": Decimal,
    "costs_by_service": Map[str, Decimal],
    "costs_by_tag": Map[str, Decimal],
    "collection_timestamp": int
}
```

**GSI:** `date-index` (for querying costs by date across accounts)

#### Table 4: `allocation_rules`

**Purpose:** Store cost allocation rules

**Schema:**
```python
{
    "rule_id": str,  # Partition key
    "org_id": str,  # GSI partition key
    "name": str,
    "priority": int,
    "rule_type": str,
    "conditions": Map,
    "allocation_target": str,
    "created_at": int,
    "updated_at": int
}
```

#### Table 5: `budgets`

**Purpose:** Store organization/OU/account budgets

**Schema:**
```python
{
    "budget_id": str,  # Partition key
    "entity_id": str,  # org_id, ou_id, or account_id
    "entity_type": str,  # "ORGANIZATION", "OU", "ACCOUNT"
    "budget_amount": Decimal,
    "period": str,  # "MONTHLY", "QUARTERLY", "ANNUAL"
    "current_spend": Decimal,
    "utilization_percentage": float,
    "alert_thresholds": List[int],  # [80, 100]
    "last_updated": int
}
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Organization Discovery Completeness

*For any* organization, when the system discovers the organization structure, all active accounts in the organization should be included in the discovered account list.

**Validates: Requirements 1.2**

**Test Strategy:**
- Generate random organization structures
- Call discover_organization()
- Verify all accounts from Organizations API are in result
- Verify no duplicate accounts

---

### Property 2: Cross-Account Role Assumption Idempotence

*For any* account with a valid cross-account role, assuming the role multiple times should return equivalent credentials (same permissions, different session tokens).

**Validates: Requirements 2.5**

**Test Strategy:**
- Generate random account IDs
- Call assume_role() twice
- Verify both calls succeed
- Verify permissions are identical

---

### Property 3: Cost Collection Resilience

*For any* set of accounts where some accounts fail collection, the system should successfully collect costs from all non-failing accounts and continue operation.

**Validates: Requirements 3.4, 18.1**

**Test Strategy:**
- Generate random account lists with some failing accounts
- Call collect_all_accounts()
- Verify successful accounts have cost data
- Verify failed accounts are logged but don't break collection
- Verify CollectionResult accurately reflects success/failure counts

---

### Property 4: Cost Aggregation Consistency

*For any* set of accounts, the sum of per-account costs should equal the aggregated organization cost for the same time period.

**Validates: Requirements 4.1**

**Test Strategy:**
- Generate random cost data for multiple accounts
- Calculate sum of individual account costs
- Call aggregate_organization_costs()
- Verify aggregated total equals sum of individual costs

---

### Property 5: Cost Allocation Conservation

*For any* account's costs, the sum of allocated costs plus unallocated costs should equal the total account cost.

**Validates: Requirements 6.1, 7.1**

**Test Strategy:**
- Generate random cost data with mixed tagged/untagged resources
- Call allocate_by_tags()
- Verify: allocated_cost + unallocated_cost = total_cost
- Verify no costs are lost or double-counted

---

### Property 6: Allocation Rule Priority

*For any* resource that matches multiple allocation rules, the system should apply only the highest-priority rule.

**Validates: Requirements 8.6**

**Test Strategy:**
- Generate random allocation rules with different priorities
- Generate cost data matching multiple rules
- Call apply_allocation_rules()
- Verify only highest-priority rule is applied
- Verify no double allocation

---

### Property 7: Budget Rollup Consistency

*For any* organizational unit, the sum of account budgets within that OU should not exceed the OU budget.

**Validates: Requirements 12.1, 12.2**

**Test Strategy:**
- Generate random OU hierarchy with budgets
- Calculate sum of account budgets in OU
- Verify sum ≤ OU budget
- Verify organization budget ≥ sum of all OU budgets

---

### Property 8: Parallel Collection Equivalence

*For any* set of accounts, collecting costs in parallel should produce the same results as collecting sequentially.

**Validates: Requirements 3.2**

**Test Strategy:**
- Generate random account list
- Collect costs in parallel
- Collect costs sequentially
- Verify results are equivalent (same costs, same accounts)

---

### Property 9: Cache Consistency

*For any* cached organization structure, if the cache is valid (not expired), subsequent queries should return the cached data without calling Organizations API.

**Validates: Requirements 1.5**

**Test Strategy:**
- Call discover_organization() to populate cache
- Call discover_organization() again within TTL
- Verify second call uses cache (no API call)
- Verify data is identical

---

### Property 10: Unallocated Cost Monotonicity

*For any* account, as more allocation rules are added, the unallocated cost should decrease or stay the same (never increase).

**Validates: Requirements 7.1, 8.1**

**Test Strategy:**
- Generate random cost data
- Calculate unallocated costs with N rules
- Add one more allocation rule
- Calculate unallocated costs with N+1 rules
- Verify: unallocated(N+1) ≤ unallocated(N)

---

### Property 11: Cross-Account Forecast Consistency

*For any* organization, the sum of per-account forecasts should approximately equal the organization-level forecast (within 10% margin).

**Validates: Requirements 13.4**

**Test Strategy:**
- Generate random historical cost data for multiple accounts
- Generate per-account forecasts
- Generate organization-level forecast
- Verify: |sum(account_forecasts) - org_forecast| / org_forecast < 0.10

---

### Property 12: Prevention Policy Inheritance

*For any* account in an OU with an OU-level prevention policy, the account should inherit the policy unless it has an account-level override.

**Validates: Requirements 14.4, 14.5**

**Test Strategy:**
- Generate random OU hierarchy with policies
- Generate accounts with and without overrides
- Call get_effective_policies() for each account
- Verify accounts without overrides inherit OU policy
- Verify accounts with overrides use account policy

---

### Property 13: API Response Time Bound

*For any* consolidated cost query, the system should return results within 5 seconds.

**Validates: Requirements 4.6, 17.3**

**Test Strategy:**
- Generate random cost queries
- Measure response time for each query
- Verify all queries complete within 5 seconds
- Use property-based testing to test many query variations

---

### Property 14: Backward Compatibility

*For any* single-account operation, the system should produce the same results whether multi-account mode is enabled or disabled.

**Validates: Requirements 20.2, 20.3**

**Test Strategy:**
- Generate random single-account cost data
- Query costs with multi-account mode disabled
- Query costs with multi-account mode enabled (single account)
- Verify results are identical

---

### Property 15: Error Recovery

*For any* account that fails collection, retrying the collection should eventually succeed if the account becomes accessible.

**Validates: Requirements 18.5**

**Test Strategy:**
- Simulate account collection failure
- Retry collection with exponential backoff
- Verify system retries up to 3 times
- Verify system eventually succeeds when account becomes accessible

---

## Error Handling

### Error Categories

1. **AWS API Errors:**
   - Organizations API throttling
   - Cost Explorer API throttling
   - STS AssumeRole failures
   - Invalid credentials

2. **Data Errors:**
   - Missing cost data
   - Invalid account IDs
   - Malformed responses

3. **System Errors:**
   - DynamoDB throttling
   - Lambda timeout
   - Memory exhaustion

### Error Handling Strategy

**Retry Logic:**
```python
def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except RetryableError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
```

**Graceful Degradation:**
- If one account fails, continue with others
- If cache is stale, fall back to API call
- If aggregation fails, return per-account data

**Error Logging:**
- Log all errors to CloudWatch
- Include account_id, error type, stack trace
- Set CloudWatch alarms for critical errors

---

## Testing Strategy

### Unit Tests

**Purpose:** Test individual components in isolation

**Coverage:**
- Organization discovery logic
- Role assumption logic
- Cost aggregation calculations
- Allocation rule matching
- Budget calculations

**Tools:** pytest, moto (AWS mocking)

**Example:**
```python
def test_aggregate_organization_costs():
    # Given: Cost data for 3 accounts
    account_costs = [
        AccountCostData(account_id="111", total_cost=Decimal("100")),
        AccountCostData(account_id="222", total_cost=Decimal("200")),
        AccountCostData(account_id="333", total_cost=Decimal("300"))
    ]
    
    # When: Aggregating costs
    result = aggregator.aggregate_organization_costs(account_costs)
    
    # Then: Total should be sum of all accounts
    assert result.total_cost == Decimal("600")
```

### Property-Based Tests

**Purpose:** Test universal properties across many inputs

**Coverage:**
- All 15 correctness properties defined above
- Each property tested with 100+ random inputs

**Tools:** Hypothesis (Python property-based testing library)

**Configuration:**
- Minimum 100 iterations per property
- Each test tagged with property number and requirement

**Example:**
```python
from hypothesis import given, strategies as st

@given(
    accounts=st.lists(st.text(min_size=12, max_size=12), min_size=1, max_size=10),
    costs=st.lists(st.decimals(min_value=0, max_value=10000), min_size=1, max_size=10)
)
def test_property_4_cost_aggregation_consistency(accounts, costs):
    """
    Property 4: Cost Aggregation Consistency
    For any set of accounts, sum of per-account costs = aggregated org cost
    Validates: Requirements 4.1
    """
    # Given: Random account costs
    account_data = [
        AccountCostData(account_id=acc, total_cost=cost)
        for acc, cost in zip(accounts, costs)
    ]
    
    # When: Aggregating costs
    aggregated = aggregator.aggregate_organization_costs(account_data)
    expected_total = sum(costs)
    
    # Then: Aggregated total should equal sum
    assert abs(aggregated.total_cost - expected_total) < Decimal("0.01")
```

### Integration Tests

**Purpose:** Test end-to-end flows with real AWS services

**Coverage:**
- Organization discovery with real Organizations API
- Cost collection with real Cost Explorer API
- Cross-account role assumption with real STS

**Environment:** Test AWS account with Organizations enabled

**Example:**
```python
def test_integration_multi_account_cost_collection():
    # Given: Real AWS organization with 3 accounts
    org_id = "o-123456789"
    
    # When: Collecting costs from all accounts
    result = collector.collect_all_accounts(org_id, start_date, end_date)
    
    # Then: All accounts should have cost data
    assert result.successful == 3
    assert result.failed == 0
```

### Performance Tests

**Purpose:** Verify system meets performance requirements

**Coverage:**
- Cost collection time for 100 accounts
- API response time for consolidated queries
- Parallel processing efficiency

**Tools:** pytest-benchmark

**Example:**
```python
def test_performance_100_account_collection(benchmark):
    # Given: 100 accounts
    accounts = [f"account-{i}" for i in range(100)]
    
    # When: Collecting costs (benchmark)
    result = benchmark(collector.collect_parallel, accounts, start_date, end_date)
    
    # Then: Should complete within 10 minutes
    assert benchmark.stats.mean < 600  # 600 seconds = 10 minutes
```

---

## Deployment Strategy

### Infrastructure as Code

**Tool:** AWS CDK (Python)

**Resources:**
- Lambda functions (6 functions)
- DynamoDB tables (5 tables)
- API Gateway (REST API)
- IAM roles and policies
- EventBridge rules (daily triggers)
- CloudWatch alarms

### Deployment Steps

1. **Deploy Infrastructure:**
   ```bash
   cd infrastructure
   cdk deploy CostGuardMultiAccountStack
   ```

2. **Deploy Cross-Account Roles:**
   ```bash
   # Generate CloudFormation template
   python scripts/generate_role_template.py > role-template.yaml
   
   # Deploy to each member account
   aws cloudformation create-stack \
     --stack-name CostGuardCollectorRole \
     --template-body file://role-template.yaml \
     --capabilities CAPABILITY_IAM
   ```

3. **Initialize Organization:**
   ```bash
   # Discover organization structure
   aws lambda invoke \
     --function-name CostGuard-OrganizationDiscovery \
     --payload '{"action": "discover"}' \
     response.json
   ```

4. **Verify Deployment:**
   ```bash
   # Test API endpoints
   curl https://api.costguard.example.com/api/organizations
   curl https://api.costguard.example.com/api/costs/consolidated
   ```

### Rollback Strategy

- Use CDK rollback on deployment failure
- Maintain previous Lambda versions
- Blue/green deployment for API Gateway

---

## Monitoring and Observability

### CloudWatch Metrics

**Custom Metrics:**
- `MultiAccountCostCollection.Duration` - Time to collect all accounts
- `MultiAccountCostCollection.SuccessRate` - Percentage of successful collections
- `CostAggregation.CacheHitRate` - Percentage of cache hits
- `AllocationEngine.UnallocatedPercentage` - Percentage of unallocated costs

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

### Logging

**Log Groups:**
- `/aws/lambda/CostGuard-OrganizationDiscovery`
- `/aws/lambda/CostGuard-MultiAccountCostCollector`
- `/aws/lambda/CostGuard-CostAggregator`
- `/aws/lambda/CostGuard-AllocationEngine`

**Log Format:**
```json
{
  "timestamp": "2026-02-24T10:30:00Z",
  "level": "INFO",
  "component": "MultiAccountCostCollector",
  "account_id": "123456789012",
  "action": "collect_costs",
  "status": "SUCCESS",
  "duration_ms": 1234,
  "cost_data_points": 90
}
```

---

## Security Considerations

### IAM Permissions

**Management Account Lambda Role:**
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
        "sts:AssumeRole"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/costguard-*"
    }
  ]
}
```

### Data Encryption

- **At Rest:** DynamoDB encryption with AWS managed keys
- **In Transit:** TLS 1.2+ for all API calls
- **Credentials:** Temporary STS credentials (1-hour expiry)

### Access Control

- API Gateway with API key authentication
- IAM-based authorization for Lambda functions
- External ID required for cross-account roles

### Audit Logging

- All cross-account access logged to CloudWatch
- All API calls logged with request/response
- Failed authentication attempts alerted

---

## Performance Optimization

### Caching Strategy

**Organization Structure:**
- Cache TTL: 24 hours
- Invalidate on manual refresh
- Store in DynamoDB

**Aggregated Costs:**
- Cache TTL: 1 hour
- Invalidate on new cost data
- Store in DynamoDB

**Allocation Results:**
- Cache TTL: 1 hour
- Invalidate on rule changes
- Store in DynamoDB

### Parallel Processing

**Cost Collection:**
- Use ThreadPoolExecutor
- Max 10 concurrent accounts
- Timeout: 60 seconds per account

**Cost Aggregation:**
- Process accounts in batches of 10
- Use DynamoDB batch operations
- Parallel query execution

### Database Optimization

**DynamoDB:**
- Use on-demand billing for auto-scaling
- Create GSIs for common query patterns
- Use batch operations where possible
- Implement pagination for large result sets

---

## Backward Compatibility

### Single-Account Mode

**Detection:**
- If no organization configured, operate in single-account mode
- Use existing Phase 1-4 functionality
- No changes to existing API endpoints

**Migration Path:**
1. User configures organization
2. System discovers accounts
3. System enables multi-account features
4. Existing single-account data preserved

### API Compatibility

**Existing Endpoints:** Unchanged
- `GET /api/costs` - Returns costs for current account
- `GET /api/forecast` - Returns forecast for current account
- `GET /api/budgets` - Returns budgets for current account

**New Endpoints:** Additive
- `GET /api/organizations` - List organizations
- `GET /api/costs/consolidated` - Consolidated costs
- `GET /api/costs/by-account` - Per-account costs

---

## Future Enhancements

### Phase 5.5 (Post-MVP)

1. **Advanced Chargeback:**
   - Custom billing periods
   - Invoice generation
   - Payment tracking

2. **Cost Anomaly Detection:**
   - Cross-account anomaly detection
   - Organization-wide patterns
   - Predictive alerts

3. **Resource Tagging Automation:**
   - Auto-tag resources based on account/OU
   - Tag compliance enforcement
   - Tag propagation

4. **Multi-Organization Support:**
   - Manage multiple organizations
   - Cross-organization reporting
   - Consolidated multi-org views

---

**Document Status:** Draft  
**Last Updated:** February 2026  
**Next Steps:** Create tasks.md with implementation plan
