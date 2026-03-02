# Requirements Document: Phase 5 Multi-Account Lambda Handlers

## Introduction

This document specifies the requirements for implementing three Lambda handler functions that provide multi-account AWS cost management capabilities. The handlers integrate with existing Phase 5 infrastructure including DynamoDB tables, API Gateway endpoints, and EventBridge rules to enable organization-wide cost visibility, collection, and management.

## Glossary

- **Multi_Account_API_Handler**: Lambda function that processes API Gateway requests for multi-account cost operations
- **Multi_Account_Cost_Collector**: Lambda function that collects cost data from multiple AWS accounts on a scheduled basis
- **Multi_Account_Main_Handler**: Lambda function that discovers and manages AWS Organization metadata
- **Organization**: AWS Organizations entity representing a collection of AWS accounts
- **Cost_Explorer**: AWS service providing cost and usage data
- **Cross_Account_Role**: IAM role that allows access to resources in another AWS account
- **DynamoDB_Repository**: Data access layer for DynamoDB table operations
- **API_Gateway**: AWS service that routes HTTP requests to Lambda functions
- **EventBridge_Rule**: Scheduled trigger for Lambda function execution
- **Cost_Aggregation**: Process of combining cost data from multiple accounts
- **Cost_Allocation**: Process of distributing costs based on tags or rules
- **Budget_Hierarchy**: Nested structure of budgets at organization, OU, and account levels

## Requirements

### Requirement 1: Multi-Account API Handler Implementation

**User Story:** As a cost management user, I want to query multi-account cost data through API endpoints, so that I can analyze costs across my entire organization.

#### Acceptance Criteria

1. WHEN an HTTP request is received, THE Multi_Account_API_Handler SHALL authenticate the request using API key validation
2. WHEN authentication fails, THE Multi_Account_API_Handler SHALL return a 401 status code with an error message
3. WHEN a GET request is made to /api/organizations, THE Multi_Account_API_Handler SHALL return a list of all organizations
4. WHEN a GET request is made to /api/organizations/{org_id}/accounts, THE Multi_Account_API_Handler SHALL return all accounts in the specified organization
5. WHEN a GET request is made to /api/costs/consolidated, THE Multi_Account_API_Handler SHALL return aggregated costs for all accounts
6. WHEN a GET request is made to /api/costs/by-account, THE Multi_Account_API_Handler SHALL return per-account cost breakdowns
7. WHEN a GET request is made to /api/costs/account/{account_id}, THE Multi_Account_API_Handler SHALL return costs for the specified account
8. WHEN a GET request is made to /api/allocation/by-tag, THE Multi_Account_API_Handler SHALL return costs allocated by the specified tag key
9. WHEN a GET request is made to /api/allocation/unallocated, THE Multi_Account_API_Handler SHALL return costs that have no tag allocation
10. WHEN a POST request is made to /api/allocation/rules, THE Multi_Account_API_Handler SHALL create a new cost allocation rule
11. WHEN a GET request is made to /api/budgets/hierarchy, THE Multi_Account_API_Handler SHALL return the budget hierarchy for the organization
12. WHEN a POST request is made to /api/budgets/organization, THE Multi_Account_API_Handler SHALL create an organization-level budget
13. WHEN a POST request is made to /api/budgets/ou/{ou_id}, THE Multi_Account_API_Handler SHALL create an OU-level budget
14. WHEN an error occurs during request processing, THE Multi_Account_API_Handler SHALL log the error to CloudWatch and return a standardized error response
15. WHEN a request completes, THE Multi_Account_API_Handler SHALL record response time metrics to CloudWatch

### Requirement 2: Cross-Account Cost Collection

**User Story:** As a cost management system, I want to collect cost data from all accounts in my organization, so that I can provide consolidated cost reporting.

#### Acceptance Criteria

1. WHEN the Multi_Account_Cost_Collector is triggered by EventBridge, THE Multi_Account_Cost_Collector SHALL discover all accounts in the organization
2. WHEN accounts are discovered, THE Multi_Account_Cost_Collector SHALL assume a cross-account role in each account
3. IF a cross-account role assumption fails, THEN THE Multi_Account_Cost_Collector SHALL log the failure and continue with remaining accounts
4. WHEN a cross-account role is assumed, THE Multi_Account_Cost_Collector SHALL query Cost Explorer for the account's cost data
5. WHEN cost data is retrieved, THE Multi_Account_Cost_Collector SHALL store the data in the costguard-multi-account-costs DynamoDB table
6. WHEN all accounts are processed, THE Multi_Account_Cost_Collector SHALL return a summary including successful count, failed count, and total cost
7. IF more than 20% of accounts fail, THEN THE Multi_Account_Cost_Collector SHALL return a 207 Multi-Status response code
8. WHEN collection completes, THE Multi_Account_Cost_Collector SHALL record collection duration metrics to CloudWatch
9. THE Multi_Account_Cost_Collector SHALL process accounts in parallel with a maximum concurrency of 10
10. WHEN a Cost Explorer API call fails, THE Multi_Account_Cost_Collector SHALL retry up to 3 times with exponential backoff

### Requirement 3: Organization Discovery and Metadata Management

**User Story:** As a cost management system, I want to maintain current organization metadata, so that I can accurately track account membership and structure.

#### Acceptance Criteria

1. WHEN the Multi_Account_Main_Handler is triggered by EventBridge, THE Multi_Account_Main_Handler SHALL call AWS Organizations API to discover the organization
2. WHEN organization data is retrieved, THE Multi_Account_Main_Handler SHALL store organization metadata in the costguard-organizations DynamoDB table
3. WHEN organization data is retrieved, THE Multi_Account_Main_Handler SHALL discover all member accounts
4. WHEN member accounts are discovered, THE Multi_Account_Main_Handler SHALL store account metadata in the costguard-accounts DynamoDB table
5. WHEN an account already exists in the table, THE Multi_Account_Main_Handler SHALL update the account metadata with current values
6. WHEN an account no longer exists in the organization, THE Multi_Account_Main_Handler SHALL mark the account as inactive
7. WHEN discovery completes, THE Multi_Account_Main_Handler SHALL log the count of discovered accounts
8. IF the Organizations API call fails, THEN THE Multi_Account_Main_Handler SHALL log the error and return a 500 status code

### Requirement 4: DynamoDB Integration

**User Story:** As a Lambda handler, I want to interact with DynamoDB tables using repository patterns, so that I can maintain clean separation of concerns.

#### Acceptance Criteria

1. THE Multi_Account_API_Handler SHALL use OrganizationRepository to access the costguard-organizations table
2. THE Multi_Account_API_Handler SHALL use AccountRepository to access the costguard-accounts table
3. THE Multi_Account_API_Handler SHALL use MultiAccountCostRepository to access the costguard-multi-account-costs table
4. THE Multi_Account_API_Handler SHALL use AllocationRuleRepository to access the costguard-allocation-rules table
5. THE Multi_Account_API_Handler SHALL use BudgetRepository to access the costguard-budgets table
6. WHEN a DynamoDB operation fails, THE handler SHALL log the error with the table name and operation type
7. WHEN a DynamoDB throttling error occurs, THE handler SHALL retry the operation with exponential backoff up to 3 times

### Requirement 5: Error Handling and Logging

**User Story:** As a system operator, I want comprehensive error logging, so that I can troubleshoot issues effectively.

#### Acceptance Criteria

1. WHEN an exception occurs in any handler, THE handler SHALL log the exception with stack trace to CloudWatch
2. WHEN an error response is returned, THE handler SHALL include a standardized error structure with code, message, and optional details
3. WHEN a validation error occurs, THE handler SHALL return a 400 status code with a descriptive error message
4. WHEN an authentication error occurs, THE handler SHALL return a 401 status code
5. WHEN a resource is not found, THE handler SHALL return a 404 status code
6. WHEN an internal error occurs, THE handler SHALL return a 500 status code
7. THE handler SHALL log all incoming requests at INFO level with sanitized parameters
8. THE handler SHALL log all outgoing responses at INFO level with status code and duration

### Requirement 6: Date Range Validation

**User Story:** As an API user, I want date parameters to be validated, so that I receive clear error messages for invalid inputs.

#### Acceptance Criteria

1. WHEN a start_date parameter is provided, THE Multi_Account_API_Handler SHALL validate the date format is YYYY-MM-DD
2. WHEN an end_date parameter is provided, THE Multi_Account_API_Handler SHALL validate the date format is YYYY-MM-DD
3. IF a date format is invalid, THEN THE Multi_Account_API_Handler SHALL return a 400 status code with error code INVALID_DATE_FORMAT
4. WHEN both start_date and end_date are provided, THE Multi_Account_API_Handler SHALL validate that start_date is before or equal to end_date
5. IF the date range is invalid, THEN THE Multi_Account_API_Handler SHALL return a 400 status code with error code INVALID_DATE_RANGE

### Requirement 7: Cost Aggregation

**User Story:** As a cost analyst, I want to view consolidated costs across multiple dimensions, so that I can understand spending patterns.

#### Acceptance Criteria

1. WHEN consolidated costs are requested, THE Multi_Account_API_Handler SHALL aggregate costs by service
2. WHEN consolidated costs are requested, THE Multi_Account_API_Handler SHALL aggregate costs by account
3. WHEN consolidated costs are requested, THE Multi_Account_API_Handler SHALL aggregate costs by time period
4. WHEN consolidated costs are requested, THE Multi_Account_API_Handler SHALL calculate total cost across all accounts
5. THE Multi_Account_API_Handler SHALL return costs in USD currency
6. THE Multi_Account_API_Handler SHALL include period_start and period_end in the response
7. THE Multi_Account_API_Handler SHALL include a timestamp indicating when the aggregation was performed

### Requirement 8: Cost Allocation by Tags

**User Story:** As a finance manager, I want to allocate costs based on resource tags, so that I can perform chargeback to teams.

#### Acceptance Criteria

1. WHEN allocation by tag is requested, THE Multi_Account_API_Handler SHALL accept a tag_key parameter
2. WHEN tag_key is not provided, THE Multi_Account_API_Handler SHALL default to "Team" as the tag key
3. WHEN allocation is performed, THE Multi_Account_API_Handler SHALL group costs by unique tag values
4. WHEN allocation is performed, THE Multi_Account_API_Handler SHALL calculate total cost for each tag value
5. WHEN allocation is performed, THE Multi_Account_API_Handler SHALL identify resources without the specified tag
6. WHEN unallocated costs are requested, THE Multi_Account_API_Handler SHALL return total unallocated cost
7. WHEN unallocated costs are requested, THE Multi_Account_API_Handler SHALL return percentage of total that is unallocated
8. WHEN unallocated costs are requested, THE Multi_Account_API_Handler SHALL return a list of untagged resources with their costs

### Requirement 9: Budget Management

**User Story:** As a financial controller, I want to create and manage budgets at different organizational levels, so that I can control spending.

#### Acceptance Criteria

1. WHEN a budget hierarchy is requested, THE Multi_Account_API_Handler SHALL return organization-level budgets
2. WHEN a budget hierarchy is requested, THE Multi_Account_API_Handler SHALL return OU-level budgets
3. WHEN a budget hierarchy is requested, THE Multi_Account_API_Handler SHALL return account-level budgets
4. WHEN an organization budget is created, THE Multi_Account_API_Handler SHALL validate that budget_amount is a positive number
5. WHEN an organization budget is created, THE Multi_Account_API_Handler SHALL validate that time_period is one of MONTHLY, QUARTERLY, or ANNUALLY
6. WHEN an OU budget is created, THE Multi_Account_API_Handler SHALL validate that the OU exists in the organization
7. WHEN a budget is created, THE Multi_Account_API_Handler SHALL store the budget in the costguard-budgets DynamoDB table
8. WHEN a budget is created, THE Multi_Account_API_Handler SHALL return the created budget with a generated budget_id

### Requirement 10: Allocation Rules Engine

**User Story:** As a cost allocation administrator, I want to define custom allocation rules, so that I can implement complex cost distribution logic.

#### Acceptance Criteria

1. WHEN an allocation rule is created, THE Multi_Account_API_Handler SHALL validate that rule_name is provided
2. WHEN an allocation rule is created, THE Multi_Account_API_Handler SHALL validate that rule_type is one of TAG_BASED, PERCENTAGE, or FIXED
3. WHEN an allocation rule is created, THE Multi_Account_API_Handler SHALL validate that conditions is a valid JSON object
4. WHEN an allocation rule is created, THE Multi_Account_API_Handler SHALL validate that allocation_target is provided
5. WHEN an allocation rule is created, THE Multi_Account_API_Handler SHALL assign a default priority of 100 if not specified
6. WHEN an allocation rule is created, THE Multi_Account_API_Handler SHALL store the rule in the costguard-allocation-rules DynamoDB table
7. WHEN an allocation rule is created, THE Multi_Account_API_Handler SHALL return the created rule with a generated rule_id

### Requirement 11: EventBridge Integration

**User Story:** As a cost management system, I want handlers to be triggered automatically on schedule, so that data stays current without manual intervention.

#### Acceptance Criteria

1. THE Multi_Account_Cost_Collector SHALL be triggered daily at 00:00 UTC by an EventBridge rule
2. THE Multi_Account_Main_Handler SHALL be triggered every 4 hours by an EventBridge rule
3. WHEN triggered by EventBridge, THE handler SHALL recognize the event source as "aws.events"
4. WHEN triggered by EventBridge, THE handler SHALL extract configuration from environment variables
5. WHEN triggered by EventBridge, THE handler SHALL use default date ranges if not specified in the event

### Requirement 12: Manual Trigger Support

**User Story:** As a system administrator, I want to manually trigger cost collection with custom parameters, so that I can perform ad-hoc data collection.

#### Acceptance Criteria

1. THE Multi_Account_Cost_Collector SHALL support manual invocation with custom parameters
2. WHEN manually triggered, THE Multi_Account_Cost_Collector SHALL accept org_id in the event payload
3. WHEN manually triggered, THE Multi_Account_Cost_Collector SHALL accept account_ids array in the event payload
4. WHEN manually triggered, THE Multi_Account_Cost_Collector SHALL accept start_date in the event payload
5. WHEN manually triggered, THE Multi_Account_Cost_Collector SHALL accept end_date in the event payload
6. WHEN manually triggered with account_ids, THE Multi_Account_Cost_Collector SHALL collect costs only for specified accounts
7. WHEN manually triggered without account_ids, THE Multi_Account_Cost_Collector SHALL discover and collect costs for all accounts

### Requirement 13: CloudWatch Metrics

**User Story:** As a system operator, I want operational metrics published to CloudWatch, so that I can monitor handler performance and health.

#### Acceptance Criteria

1. WHEN an API request completes, THE Multi_Account_API_Handler SHALL publish response time metric to CloudWatch
2. WHEN an error occurs, THE handler SHALL publish error count metric to CloudWatch with error type dimension
3. WHEN cost collection completes, THE Multi_Account_Cost_Collector SHALL publish collection duration metric to CloudWatch
4. WHEN cost collection completes, THE Multi_Account_Cost_Collector SHALL publish successful account count metric to CloudWatch
5. WHEN cost collection completes, THE Multi_Account_Cost_Collector SHALL publish failed account count metric to CloudWatch
6. THE handler SHALL use the namespace "CostGuard/MultiAccount" for all custom metrics

### Requirement 14: Response Format Standardization

**User Story:** As an API consumer, I want consistent response formats, so that I can reliably parse responses.

#### Acceptance Criteria

1. THE Multi_Account_API_Handler SHALL include a "success" boolean field in all responses
2. WHEN a request succeeds, THE Multi_Account_API_Handler SHALL set success to true and include a "data" field
3. WHEN a request fails, THE Multi_Account_API_Handler SHALL set success to false and include an "error" field
4. THE error field SHALL contain "code" and "message" subfields
5. THE Multi_Account_API_Handler SHALL include "Content-Type: application/json" header in all responses
6. THE Multi_Account_API_Handler SHALL include "Access-Control-Allow-Origin: *" header for CORS support
7. THE Multi_Account_API_Handler SHALL return valid JSON in the response body

### Requirement 15: Environment Configuration

**User Story:** As a deployment engineer, I want handlers to read configuration from environment variables, so that I can deploy to different environments without code changes.

#### Acceptance Criteria

1. THE Multi_Account_Cost_Collector SHALL read ORGANIZATION_ID from environment variables
2. THE Multi_Account_Cost_Collector SHALL read EXTERNAL_ID from environment variables for cross-account role assumption
3. THE Multi_Account_Cost_Collector SHALL read DAYS_TO_COLLECT from environment variables with a default of 7
4. THE handler SHALL read LOG_LEVEL from environment variables with a default of INFO
5. THE handler SHALL read DynamoDB table names from environment variables
6. IF a required environment variable is missing, THEN THE handler SHALL log an error and return a 500 status code

### Requirement 16: Parallel Processing

**User Story:** As a cost management system, I want to collect costs from multiple accounts in parallel, so that collection completes in reasonable time.

#### Acceptance Criteria

1. THE Multi_Account_Cost_Collector SHALL process multiple accounts concurrently
2. THE Multi_Account_Cost_Collector SHALL limit concurrent account processing to 10 accounts
3. WHEN processing accounts in parallel, THE Multi_Account_Cost_Collector SHALL collect results from all concurrent operations
4. WHEN processing accounts in parallel, THE Multi_Account_Cost_Collector SHALL not fail the entire operation if individual accounts fail
5. WHEN all parallel operations complete, THE Multi_Account_Cost_Collector SHALL aggregate results into a summary

### Requirement 17: Retry Logic

**User Story:** As a cost management system, I want automatic retries for transient failures, so that temporary issues do not cause data collection failures.

#### Acceptance Criteria

1. WHEN a Cost Explorer API call fails with a throttling error, THE handler SHALL retry the operation
2. WHEN a DynamoDB operation fails with a throttling error, THE handler SHALL retry the operation
3. THE handler SHALL retry failed operations up to 3 times
4. THE handler SHALL use exponential backoff with base delay of 1 second for retries
5. WHEN all retries are exhausted, THE handler SHALL log the final error and continue with remaining operations

### Requirement 18: Cost Data Validation

**User Story:** As a cost management system, I want to validate cost data before storage, so that I maintain data quality.

#### Acceptance Criteria

1. WHEN cost data is retrieved from Cost Explorer, THE Multi_Account_Cost_Collector SHALL validate that cost values are non-negative
2. WHEN cost data is retrieved, THE Multi_Account_Cost_Collector SHALL validate that date fields are in valid format
3. WHEN cost data is retrieved, THE Multi_Account_Cost_Collector SHALL validate that account_id matches the expected account
4. IF cost data validation fails, THEN THE Multi_Account_Cost_Collector SHALL log a warning and skip the invalid record
5. THE Multi_Account_Cost_Collector SHALL include validation error count in the collection summary

### Requirement 19: Service Integration Patterns

**User Story:** As a developer, I want handlers to follow existing service integration patterns, so that the codebase remains consistent and maintainable.

#### Acceptance Criteria

1. THE handler SHALL use repository classes for all DynamoDB operations
2. THE handler SHALL use service classes for business logic
3. THE handler SHALL use utility functions from utils module for common operations
4. THE handler SHALL follow the error handling patterns established in Phase 1-4 handlers
5. THE handler SHALL use the same logging format as existing handlers
6. THE handler SHALL use type hints for all function parameters and return values

### Requirement 20: Unit Test Coverage

**User Story:** As a developer, I want comprehensive unit tests for all handlers, so that I can confidently make changes without breaking functionality.

#### Acceptance Criteria

1. THE test suite SHALL include unit tests for each API endpoint handler function
2. THE test suite SHALL include unit tests for authentication and authorization logic
3. THE test suite SHALL include unit tests for error handling paths
4. THE test suite SHALL include unit tests for date validation logic
5. THE test suite SHALL include unit tests for cost aggregation logic
6. THE test suite SHALL include unit tests for cost allocation logic
7. THE test suite SHALL mock all AWS service calls in unit tests
8. THE test suite SHALL achieve at least 80% code coverage for handler functions
