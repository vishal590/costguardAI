# Requirements Document: Multi-Account Cost Management

## Introduction

This document specifies the requirements for Phase 5 of CostGuard AI: Multi-Account Cost Management. This phase transforms CostGuard AI from a single-account tool into a production-ready multi-account platform capable of managing costs across AWS Organizations.

**Purpose:** Enable cost visibility, allocation, and management across multiple AWS accounts within an organization.

**Scope:** AWS Organizations integration, cross-account cost aggregation, cost allocation, consolidated billing, and organization-wide cost management features.

**Target Users:**
- Startups with 2-10 AWS accounts (dev, staging, prod)
- SMBs with 5-50 AWS accounts (per-team, per-environment)
- Finance teams requiring chargeback/showback
- Engineering teams needing cross-account cost visibility

## Glossary

- **System**: The Multi-Account Cost Management system (Phase 5 of CostGuard AI)
- **Organization**: An AWS Organization containing multiple AWS accounts
- **Management_Account**: The AWS account that manages the organization (formerly "master account")
- **Member_Account**: An AWS account that belongs to an organization
- **OU**: Organizational Unit - a container for accounts within an organization
- **Consolidated_Billing**: Aggregated billing across all accounts in an organization
- **Cost_Allocation**: The process of attributing costs to specific teams, projects, or business units
- **Chargeback**: Internal billing where teams are charged for their AWS usage
- **Showback**: Cost visibility reports without actual billing
- **Cross_Account_Role**: An IAM role that allows the Management_Account to access resources in Member_Accounts
- **Tag**: A key-value pair attached to AWS resources for categorization
- **Unallocated_Cost**: Costs that cannot be attributed to any team or project

## Requirements

### Requirement 1: AWS Organizations Discovery

**User Story:** As a system administrator, I want to automatically discover all AWS accounts in my organization, so that I don't have to manually configure each account.

#### Acceptance Criteria

1. WHEN THE System connects to AWS Organizations API, THE System SHALL retrieve the organization structure
2. WHEN THE System retrieves organization structure, THE System SHALL identify all Member_Accounts within the organization
3. WHEN THE System retrieves organization structure, THE System SHALL identify all OUs and their hierarchy
4. WHEN THE System discovers a new Member_Account, THE System SHALL store account metadata (account ID, name, email, status)
5. THE System SHALL refresh organization structure at least once per day
6. WHEN an account is removed from the organization, THE System SHALL mark it as inactive within 24 hours

---

### Requirement 2: Cross-Account IAM Role Management

**User Story:** As a system administrator, I want to securely access cost data from all member accounts, so that I can aggregate costs without compromising security.

#### Acceptance Criteria

1. THE System SHALL provide CloudFormation templates for creating Cross_Account_Roles in Member_Accounts
2. WHEN a Cross_Account_Role is created, THE System SHALL grant read-only permissions for Cost Explorer API
3. WHEN a Cross_Account_Role is created, THE System SHALL grant read-only permissions for CloudWatch metrics
4. WHEN a Cross_Account_Role is created, THE System SHALL require an external ID for security
5. THE System SHALL use AWS STS AssumeRole to access Member_Accounts
6. WHEN assuming a role fails, THE System SHALL log the error and continue with other accounts
7. THE System SHALL validate Cross_Account_Role permissions before collecting data

---

### Requirement 3: Multi-Account Cost Collection

**User Story:** As a finance manager, I want to collect cost data from all accounts automatically, so that I have complete visibility into organizational spending.

#### Acceptance Criteria

1. THE System SHALL collect cost data from all active Member_Accounts daily
2. WHEN collecting cost data, THE System SHALL use parallel processing for multiple accounts
3. WHEN collecting cost data from a Member_Account, THE System SHALL assume the Cross_Account_Role
4. WHEN cost data collection fails for an account, THE System SHALL retry up to 3 times
5. THE System SHALL store collected cost data with account_id as partition key
6. THE System SHALL collect cost data for the last 90 days on initial setup
7. THE System SHALL collect incremental cost data for the last 7 days on daily runs

---

### Requirement 4: Consolidated Billing Views

**User Story:** As a finance manager, I want to see aggregated costs across all accounts, so that I understand total organizational spending.

#### Acceptance Criteria

1. WHEN a user requests consolidated costs, THE System SHALL aggregate costs from all active Member_Accounts
2. WHEN displaying consolidated costs, THE System SHALL show total costs by time period (daily, weekly, monthly)
3. WHEN displaying consolidated costs, THE System SHALL show costs by service across all accounts
4. WHEN displaying consolidated costs, THE System SHALL show costs by account
5. THE System SHALL cache consolidated cost views for 1 hour
6. WHEN consolidated costs are requested for a date range, THE System SHALL return costs within 5 seconds
7. THE System SHALL support filtering consolidated costs by account, service, or date range

---

### Requirement 5: Per-Account Cost Breakdown

**User Story:** As an engineering manager, I want to see costs for my team's accounts, so that I can track my team's spending.

#### Acceptance Criteria

1. WHEN a user requests costs for a specific Member_Account, THE System SHALL return costs for that account only
2. WHEN displaying per-account costs, THE System SHALL show costs by service
3. WHEN displaying per-account costs, THE System SHALL show costs by time period
4. WHEN displaying per-account costs, THE System SHALL compare costs to previous period
5. THE System SHALL identify the top 5 highest-spending accounts
6. WHEN an account's costs increase by more than 50% week-over-week, THE System SHALL flag it as anomalous
7. THE System SHALL support comparing costs across multiple accounts

---

### Requirement 6: Tag-Based Cost Allocation

**User Story:** As a finance manager, I want to allocate costs based on resource tags, so that I can attribute spending to teams and projects.

#### Acceptance Criteria

1. THE System SHALL extract cost allocation tags from all Member_Accounts
2. WHEN a resource has a "Team" tag, THE System SHALL allocate its costs to that team
3. WHEN a resource has a "Project" tag, THE System SHALL allocate its costs to that project
4. WHEN a resource has a "Environment" tag, THE System SHALL allocate its costs to that environment
5. THE System SHALL support custom cost allocation tag keys
6. WHEN a resource has multiple allocation tags, THE System SHALL allocate costs to all applicable categories
7. THE System SHALL calculate allocated costs daily

---

### Requirement 7: Unallocated Cost Tracking

**User Story:** As a finance manager, I want to identify costs that cannot be allocated, so that I can improve my tagging strategy.

#### Acceptance Criteria

1. WHEN calculating allocated costs, THE System SHALL identify resources without allocation tags
2. THE System SHALL calculate total unallocated costs per account
3. THE System SHALL calculate total unallocated costs across the organization
4. WHEN unallocated costs exceed 30% of total costs, THE System SHALL generate a warning
5. THE System SHALL provide a list of untagged resources contributing to unallocated costs
6. THE System SHALL show unallocated cost trends over time
7. THE System SHALL support filtering unallocated costs by account or service

---

### Requirement 8: Cost Allocation Rules Engine

**User Story:** As a finance manager, I want to create custom allocation rules, so that I can handle shared costs and special cases.

#### Acceptance Criteria

1. THE System SHALL support creating cost allocation rules via API
2. WHEN a rule is created, THE System SHALL validate the rule syntax
3. THE System SHALL support percentage-based allocation rules (e.g., split VPC costs 50/50 between teams)
4. THE System SHALL support tag-based allocation rules (e.g., allocate all "shared" resources to "Infrastructure" team)
5. THE System SHALL apply allocation rules in priority order
6. WHEN multiple rules match a resource, THE System SHALL apply the highest-priority rule
7. THE System SHALL store allocation rules in DynamoDB

---

### Requirement 9: Showback Reports

**User Story:** As a team lead, I want to see my team's AWS costs, so that I understand our spending without being charged.

#### Acceptance Criteria

1. THE System SHALL generate showback reports by team
2. THE System SHALL generate showback reports by project
3. THE System SHALL generate showback reports by environment
4. WHEN generating a showback report, THE System SHALL include allocated costs only
5. WHEN generating a showback report, THE System SHALL show cost breakdown by service
6. WHEN generating a showback report, THE System SHALL show cost trends over time
7. THE System SHALL support exporting showback reports to CSV

---

### Requirement 10: Chargeback Reports

**User Story:** As a finance manager, I want to generate internal billing reports, so that I can charge teams for their AWS usage.

#### Acceptance Criteria

1. THE System SHALL generate chargeback reports by team
2. THE System SHALL generate chargeback reports by project
3. WHEN generating a chargeback report, THE System SHALL include line items for each service
4. WHEN generating a chargeback report, THE System SHALL include account IDs and names
5. WHEN generating a chargeback report, THE System SHALL calculate total charges per team
6. THE System SHALL support exporting chargeback reports to CSV
7. THE System SHALL support exporting chargeback reports to PDF

---

### Requirement 11: Organization-Wide Budgets

**User Story:** As a CFO, I want to set budgets at the organization level, so that I can control total AWS spending.

#### Acceptance Criteria

1. THE System SHALL support creating budgets at the organization level
2. THE System SHALL support creating budgets at the OU level
3. THE System SHALL support creating budgets at the account level
4. WHEN a budget is set at the organization level, THE System SHALL aggregate costs from all accounts
5. WHEN a budget is set at the OU level, THE System SHALL aggregate costs from all accounts in that OU
6. WHEN actual costs exceed 80% of budget, THE System SHALL send a warning alert
7. WHEN actual costs exceed 100% of budget, THE System SHALL send a critical alert

---

### Requirement 12: Hierarchical Budget Rollup

**User Story:** As a finance manager, I want account budgets to roll up to OU and organization budgets, so that I can track spending at all levels.

#### Acceptance Criteria

1. WHEN calculating OU budget utilization, THE System SHALL sum costs from all accounts in that OU
2. WHEN calculating organization budget utilization, THE System SHALL sum costs from all accounts
3. WHEN an account exceeds its budget, THE System SHALL reflect this in OU budget utilization
4. WHEN an OU exceeds its budget, THE System SHALL reflect this in organization budget utilization
5. THE System SHALL show budget hierarchy (organization → OU → account)
6. THE System SHALL support drilling down from organization budget to account budgets
7. THE System SHALL update budget utilization in real-time (within 15 minutes)

---

### Requirement 13: Cross-Account Forecasting

**User Story:** As a finance manager, I want to forecast costs across all accounts, so that I can predict future organizational spending.

#### Acceptance Criteria

1. THE System SHALL generate cost forecasts at the organization level
2. THE System SHALL generate cost forecasts at the OU level
3. THE System SHALL generate cost forecasts at the account level
4. WHEN generating organization-level forecasts, THE System SHALL aggregate historical data from all accounts
5. WHEN generating forecasts, THE System SHALL use the existing AI forecasting engine (Phase 2)
6. THE System SHALL forecast costs for the next 30 days
7. WHEN forecasted costs exceed budget, THE System SHALL generate a proactive alert

---

### Requirement 14: Organization-Wide Prevention Policies

**User Story:** As a cloud governance lead, I want to apply cost prevention policies across all accounts, so that I can enforce consistent cost controls.

#### Acceptance Criteria

1. THE System SHALL support creating prevention policies at the organization level
2. THE System SHALL support creating prevention policies at the OU level
3. WHEN a policy is created at the organization level, THE System SHALL apply it to all Member_Accounts
4. WHEN a policy is created at the OU level, THE System SHALL apply it to all accounts in that OU
5. THE System SHALL support account-level policy overrides
6. WHEN applying a policy, THE System SHALL use the existing prevention engine (Phase 3)
7. THE System SHALL execute prevention actions across multiple accounts in parallel

---

### Requirement 15: Cross-Account AI Advisor Context

**User Story:** As a developer, I want to ask the AI advisor about costs across all accounts, so that I can get organization-wide insights.

#### Acceptance Criteria

1. WHEN a user asks about organizational costs, THE System SHALL provide context from all accounts
2. WHEN a user asks about a specific account, THE System SHALL provide context from that account only
3. WHEN a user asks about cost allocation, THE System SHALL provide insights on allocated vs unallocated costs
4. THE System SHALL use the existing AI advisor engine (Phase 4)
5. THE System SHALL enhance AI advisor prompts with multi-account context
6. WHEN generating insights, THE System SHALL consider cross-account cost patterns
7. THE System SHALL provide recommendations for cost optimization across accounts

---

### Requirement 16: Multi-Account API Endpoints

**User Story:** As a developer, I want to access multi-account cost data via API, so that I can integrate with other tools.

#### Acceptance Criteria

1. THE System SHALL provide API endpoint GET /api/organizations to list all organizations
2. THE System SHALL provide API endpoint GET /api/organizations/{org_id}/accounts to list accounts
3. THE System SHALL provide API endpoint GET /api/costs/consolidated to get consolidated costs
4. THE System SHALL provide API endpoint GET /api/costs/by-account to get per-account costs
5. THE System SHALL provide API endpoint GET /api/costs/account/{account_id} to get costs for specific account
6. THE System SHALL provide API endpoint GET /api/allocation/by-tag to get allocated costs by tag
7. THE System SHALL provide API endpoint GET /api/allocation/unallocated to get unallocated costs
8. THE System SHALL provide API endpoint POST /api/allocation/rules to create allocation rules
9. THE System SHALL provide API endpoint GET /api/budgets/hierarchy to get budget hierarchy
10. THE System SHALL authenticate all API requests using API keys

---

### Requirement 17: Performance and Scalability

**User Story:** As a system administrator, I want the system to handle large organizations efficiently, so that performance remains acceptable.

#### Acceptance Criteria

1. THE System SHALL support organizations with up to 100 Member_Accounts
2. WHEN collecting cost data from 100 accounts, THE System SHALL complete within 10 minutes
3. WHEN generating consolidated cost views, THE System SHALL return results within 5 seconds
4. THE System SHALL use parallel processing for multi-account operations
5. THE System SHALL cache frequently accessed data for 1 hour
6. WHEN API request rate exceeds 100 requests/minute, THE System SHALL implement rate limiting
7. THE System SHALL use DynamoDB on-demand billing for automatic scaling

---

### Requirement 18: Error Handling and Resilience

**User Story:** As a system administrator, I want the system to handle account failures gracefully, so that one failing account doesn't break the entire system.

#### Acceptance Criteria

1. WHEN cost collection fails for one account, THE System SHALL continue collecting from other accounts
2. WHEN an account is inaccessible, THE System SHALL log the error and mark the account as "error" status
3. WHEN generating consolidated costs, THE System SHALL exclude accounts with collection errors
4. WHEN generating consolidated costs, THE System SHALL display a warning about excluded accounts
5. THE System SHALL retry failed operations up to 3 times with exponential backoff
6. WHEN an account consistently fails (3+ consecutive failures), THE System SHALL send an alert
7. THE System SHALL provide detailed error messages for troubleshooting

---

### Requirement 19: Security and Compliance

**User Story:** As a security officer, I want to ensure cross-account access is secure, so that we don't compromise account security.

#### Acceptance Criteria

1. THE System SHALL use IAM roles with least-privilege permissions for cross-account access
2. THE System SHALL require external IDs for all Cross_Account_Roles
3. THE System SHALL use AWS STS temporary credentials (valid for 1 hour maximum)
4. THE System SHALL encrypt all cost data at rest in DynamoDB
5. THE System SHALL encrypt all cost data in transit using TLS 1.2+
6. THE System SHALL log all cross-account access attempts to CloudWatch
7. THE System SHALL support IAM policies for restricting access to specific accounts or OUs

---

### Requirement 20: Backward Compatibility

**User Story:** As an existing user, I want Phase 5 to work with my single-account setup, so that I don't lose existing functionality.

#### Acceptance Criteria

1. WHEN no organization is configured, THE System SHALL operate in single-account mode
2. WHEN operating in single-account mode, THE System SHALL use existing Phase 1-4 functionality
3. WHEN an organization is configured, THE System SHALL automatically enable multi-account features
4. THE System SHALL support migrating from single-account to multi-account mode
5. WHEN migrating to multi-account mode, THE System SHALL preserve existing cost data
6. THE System SHALL support both single-account and multi-account API endpoints
7. THE System SHALL maintain backward compatibility with existing API clients

---

## Non-Functional Requirements

### Performance
- Cost data collection: Complete within 10 minutes for 100 accounts
- API response time: < 5 seconds for consolidated cost queries
- Forecast generation: < 30 seconds for organization-level forecasts

### Scalability
- Support up to 100 AWS accounts per organization
- Support up to 1,000 cost allocation rules
- Support up to 10,000 API requests per day

### Reliability
- System availability: 99.5% uptime
- Data accuracy: 99.9% accuracy for cost data
- Error recovery: Automatic retry with exponential backoff

### Security
- Encryption at rest: AES-256 for DynamoDB
- Encryption in transit: TLS 1.2+
- Access control: IAM-based authentication and authorization
- Audit logging: All cross-account access logged to CloudWatch

### Maintainability
- Code coverage: Minimum 85% test coverage
- Documentation: Complete API documentation
- Monitoring: CloudWatch metrics for all Lambda functions
- Alerting: SNS notifications for critical errors

---

## Assumptions and Constraints

### Assumptions
1. Users have AWS Organizations enabled in their Management_Account
2. Users can create IAM roles in Member_Accounts
3. Users have Cost Explorer API enabled in all accounts
4. Users have appropriate IAM permissions to access Organizations API

### Constraints
1. AWS Free Tier: Must stay within Lambda, DynamoDB, and API Gateway free tier limits
2. Cost Explorer API: Limited to 4 requests per second per account
3. Organizations API: Limited to 20 requests per second
4. DynamoDB: 25 GB storage limit on free tier

---

## Dependencies

### External Dependencies
- AWS Organizations API
- AWS Cost Explorer API
- AWS STS (Security Token Service)
- AWS IAM (Identity and Access Management)
- AWS CloudFormation (for role deployment)

### Internal Dependencies
- Phase 1: Cost Data Pipeline (for single-account cost collection)
- Phase 2: AI Forecasting Engine (for cross-account forecasting)
- Phase 3: Automated Prevention (for organization-wide policies)
- Phase 4: AI Advisor (for cross-account insights)

---

## Success Criteria

Phase 5 will be considered successful when:

1. ✅ System can discover and map AWS Organizations structure
2. ✅ System can collect cost data from multiple accounts in parallel
3. ✅ System can generate consolidated cost views across all accounts
4. ✅ System can allocate costs based on tags
5. ✅ System can generate showback and chargeback reports
6. ✅ System can set and monitor organization-wide budgets
7. ✅ System can apply prevention policies across all accounts
8. ✅ System maintains backward compatibility with single-account mode
9. ✅ System achieves 85%+ test coverage
10. ✅ System stays within AWS Free Tier limits

---

**Document Status:** Draft  
**Last Updated:** February 2026  
**Next Steps:** Create design.md with architecture and correctness properties
