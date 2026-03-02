# Implementation Plan: Phase 5 Multi-Account Lambda Handlers

## Overview

This implementation plan breaks down the Phase 5 multi-account Lambda handlers into discrete, manageable tasks. The plan follows an incremental approach, building from foundational components (repositories and data models) through service layer implementation, handler implementation, and comprehensive testing.

The implementation covers:
- 3 Lambda handlers (API, Cost Collector, Main Handler)
- 7 service layer components
- 5 repository layer components
- 25 property-based tests for correctness validation
- Unit tests for 80%+ code coverage
- Integration tests for end-to-end flows

## Tasks

- [x] 1. Set up project structure and core data models
  - Create directory structure for handlers, services, repositories, and tests
  - Define core data models (Organization, Account, AccountCostData, AggregatedCosts, AllocationRule, AllocationResult, CollectionResult)
  - Set up shared utilities (date validation, error response formatting, retry logic with exponential backoff)
  - Configure logging with structured format
  - _Requirements: 5.7, 5.8, 6.1, 6.2, 17.1, 17.2, 17.3, 17.4, 17.5_

- [ ] 2. Implement repository layer for DynamoDB access
  - [ ] 2.1 Implement OrganizationRepository
    - Create save() method with TTL support
    - Create get() method for retrieving organization by ID
    - _Requirements: 3.2, 4.1, 4.6, 4.7_
  
  - [ ] 2.2 Implement AccountRepository
    - Create save() method for account metadata
    - Create get() method for retrieving account by ID
    - Create list_by_organization() method using GSI
    - _Requirements: 3.4, 3.5, 4.2, 4.6, 4.7_
  
  - [ ] 2.3 Implement MultiAccountCostRepository
    - Create save() method for cost data
    - Create get() method for account and date
    - Create list_by_date() method using GSI
    - _Requirements: 2.5, 4.3, 4.6, 4.7_
  
  - [ ] 2.4 Implement AllocationRuleRepository
    - Create save() method for allocation rules
    - Create list_by_organization() method using GSI with priority sorting
    - _Requirements: 4.4, 4.6, 4.7_
  
  - [ ] 2.5 Implement BudgetRepository
    - Create save() method for budgets
    - Create get() method for budget by ID
    - Create list_by_entity() method using GSI
    - _Requirements: 4.5, 4.6, 4.7_
  
  - [ ]* 2.6 Write unit tests for all repositories
    - Test CRUD operations with mocked DynamoDB
    - Test error handling and retry logic
    - Test GSI queries
    - _Requirements: 20.7_

- [ ] 3. Implement service layer components
  - [ ] 3.1 Implement OrganizationDiscoveryService
    - Create discover_organization() method calling AWS Organizations API
    - Create get_all_accounts() method with caching
    - Create get_ou_hierarchy() method
    - Create refresh_organization_cache() method
    - Implement error handling for Organizations API failures
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_
  
  - [ ]* 3.2 Write property test for OrganizationDiscoveryService
    - **Property 11: Organization Metadata Persistence**
    - **Validates: Requirements 3.2**
  
  - [ ]* 3.3 Write property test for account metadata operations
    - **Property 12: Account Metadata Persistence**
    - **Property 13: Account Metadata Update**
    - **Property 14: Inactive Account Marking**
    - **Validates: Requirements 3.4, 3.5, 3.6**
  
  - [ ] 3.4 Implement MultiAccountCostCollector
    - Create collect_account() method with cross-account role assumption
    - Create collect_parallel() method with max 10 concurrency
    - Create collect_all_accounts() method returning CollectionResult
    - Implement retry logic for Cost Explorer API calls
    - Implement cost data validation
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.9, 2.10, 16.1, 16.2, 16.3, 16.4, 16.5, 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [ ]* 3.5 Write property tests for MultiAccountCostCollector
    - **Property 5: Cross-Account Role Assumption Resilience**
    - **Property 6: Cost Data Persistence**
    - **Property 7: Collection Summary Completeness**
    - **Property 8: High Failure Rate Detection**
    - **Property 9: Parallel Processing Concurrency Limit**
    - **Property 10: Retry with Exponential Backoff**
    - **Property 24: Cost Data Validation**
    - **Property 25: Parallel Processing Result Aggregation**
    - **Validates: Requirements 2.3, 2.5, 2.6, 2.7, 2.9, 2.10, 16.2, 16.3, 16.4, 16.5, 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [ ] 3.6 Implement CostAggregationEngine
    - Create aggregate_organization_costs() method
    - Create aggregate_ou_costs() method
    - Create aggregate_by_service() method
    - Create get_top_spending_accounts() method
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  
  - [ ]* 3.7 Write property test for CostAggregationEngine
    - **Property 18: Cost Aggregation Completeness**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  
  - [ ] 3.8 Implement CostAllocationEngine
    - Create allocate_by_tags() method with configurable tag key
    - Create get_allocation_by_team() method (default Team tag)
    - Create calculate_unallocated_costs() method
    - Create apply_allocation_rules() method
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_
  
  - [ ]* 3.9 Write property test for CostAllocationEngine
    - **Property 19: Tag-Based Cost Allocation**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_
  
  - [ ] 3.10 Implement AllocationRulesEngine
    - Create create_rule() method with validation
    - Create get_rules_by_organization() method
    - Create apply_rules() method with priority ordering
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_
  
  - [ ]* 3.11 Write property test for AllocationRulesEngine
    - **Property 21: Allocation Rule Validation**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4_
  
  - [ ] 3.12 Implement OrganizationBudgetService
    - Create create_organization_budget() method with validation
    - Create create_ou_budget() method with OU existence check
    - Create get_budget_hierarchy() method
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_
  
  - [ ]* 3.13 Write property test for OrganizationBudgetService
    - **Property 20: Budget Validation**
    - **Validates: Requirements 9.4, 9.5_
  
  - [ ] 3.14 Implement PerAccountCostService
    - Create get_account_costs() method
    - Create get_costs_by_account() method for multiple accounts
    - _Requirements: 1.6, 1.7_
  
  - [ ]* 3.15 Write unit tests for all service layer components
    - Test business logic with mocked repositories
    - Test error handling paths
    - Test edge cases (empty lists, null values)
    - _Requirements: 20.1, 20.2, 20.3, 20.5, 20.6, 20.8_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Multi_Account_API_Handler
  - [ ] 5.1 Create handler entry point and request routing
    - Implement handler() function with API Gateway event parsing
    - Implement request routing based on HTTP method and path
    - Implement authentication using API key validation
    - Implement CORS headers
    - _Requirements: 1.1, 1.2, 14.5, 14.6_
  
  - [ ]* 5.2 Write property tests for authentication and error responses
    - **Property 1: Authentication Validation**
    - **Property 2: Error Response Standardization**
    - **Property 17: Response Format Consistency**
    - **Validates: Requirements 1.1, 1.2, 5.2, 5.3, 5.4, 5.5, 5.6, 14.1, 14.2, 14.5, 14.6, 14.7_
  
  - [ ] 5.3 Implement organization endpoints
    - Implement handle_list_organizations() for GET /api/organizations
    - Implement handle_list_accounts() for GET /api/organizations/{org_id}/accounts
    - _Requirements: 1.3, 1.4_
  
  - [ ] 5.4 Implement cost query endpoints
    - Implement handle_consolidated_costs() for GET /api/costs/consolidated
    - Implement handle_costs_by_account() for GET /api/costs/by-account
    - Implement handle_account_costs() for GET /api/costs/account/{account_id}
    - Implement date parameter validation
    - _Requirements: 1.5, 1.6, 1.7, 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ]* 5.5 Write property test for date validation
    - **Property 4: Date Format Validation**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ] 5.6 Implement cost allocation endpoints
    - Implement handle_allocation_by_tag() for GET /api/allocation/by-tag
    - Implement handle_unallocated_costs() for GET /api/allocation/unallocated
    - Implement handle_create_allocation_rule() for POST /api/allocation/rules
    - _Requirements: 1.8, 1.9, 1.10_
  
  - [ ] 5.7 Implement budget management endpoints
    - Implement handle_budget_hierarchy() for GET /api/budgets/hierarchy
    - Implement handle_create_organization_budget() for POST /api/budgets/organization
    - Implement handle_create_ou_budget() for POST /api/budgets/ou/{ou_id}
    - _Requirements: 1.11, 1.12, 1.13_
  
  - [ ] 5.8 Implement error handling and logging
    - Implement create_error_response() helper function
    - Implement request/response logging at INFO level
    - Implement exception logging with stack traces
    - _Requirements: 1.14, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_
  
  - [ ]* 5.9 Write property test for request/response logging
    - **Property 3: Request and Response Logging**
    - **Property 15: Exception Logging with Stack Trace**
    - **Validates: Requirements 5.1, 5.7, 5.8_
  
  - [ ] 5.10 Implement CloudWatch metrics
    - Implement record_api_response_time() function
    - Implement record_error_count() function with error type dimension
    - Use namespace "CostGuard/MultiAccount"
    - _Requirements: 1.15, 13.1, 13.2, 13.6_
  
  - [ ]* 5.11 Write property test for CloudWatch metrics
    - **Property 16: CloudWatch Metrics Recording** (API portion)
    - **Validates: Requirements 1.15, 13.1, 13.2, 13.6_
  
  - [ ]* 5.12 Write unit tests for all API endpoints
    - Test each endpoint with valid inputs
    - Test validation errors (400)
    - Test authentication errors (401)
    - Test not found errors (404)
    - Test internal errors (500)
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.8_

- [ ] 6. Implement Multi_Account_Cost_Collector_Handler
  - [ ] 6.1 Create lambda_handler for scheduled triggers
    - Implement lambda_handler() function for EventBridge events
    - Read configuration from environment variables (ORGANIZATION_ID, EXTERNAL_ID, DAYS_TO_COLLECT, LOG_LEVEL)
    - Implement organization discovery
    - Implement parallel cost collection with max 10 concurrency
    - Implement collection summary generation
    - _Requirements: 2.1, 2.2, 2.6, 2.9, 11.1, 11.3, 11.4, 11.5, 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [ ]* 6.2 Write property test for environment configuration
    - **Property 22: Environment Configuration Reading**
    - **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_
  
  - [ ] 6.3 Create manual_trigger_handler for manual invocations
    - Implement manual_trigger_handler() function
    - Support custom parameters (org_id, account_ids, start_date, end_date, external_id)
    - Implement selective account processing when account_ids provided
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_
  
  - [ ]* 6.4 Write property test for manual trigger parameters
    - **Property 23: Manual Trigger Parameter Support**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_
  
  - [ ] 6.5 Implement CloudWatch metrics for cost collection
    - Implement record_collection_duration() function
    - Implement record_successful_account_count() function
    - Implement record_failed_account_count() function
    - _Requirements: 2.8, 13.3, 13.4, 13.5, 13.6_
  
  - [ ]* 6.6 Write unit tests for cost collector handler
    - Test scheduled trigger handling
    - Test manual trigger handling
    - Test high failure rate (>20%) returns 207 status
    - Test environment variable validation
    - _Requirements: 2.7, 20.7, 20.8_

- [ ] 7. Implement Multi_Account_Main_Handler
  - [ ] 7.1 Create handler entry point with operation routing
    - Implement handler() function with operation-based routing
    - Implement handle_discover_organization() for organization discovery
    - Implement handle_collect_costs() for cost collection
    - Implement handle_aggregate_costs() for cost aggregation
    - Implement handle_allocate_costs() for cost allocation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_
  
  - [ ] 7.2 Implement error handling and response formatting
    - Implement standardized response format with success, data, message, timestamp
    - Implement error handling for Organizations API failures
    - _Requirements: 3.8, 5.1, 5.2_
  
  - [ ]* 7.3 Write unit tests for main handler
    - Test discover_organization operation
    - Test collect_costs operation
    - Test aggregate_costs operation
    - Test allocate_costs operation
    - Test error handling
    - _Requirements: 20.7, 20.8_

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Create Lambda deployment packages and configurations
  - [ ] 9.1 Create requirements.txt with dependencies
    - Add boto3, botocore for AWS SDK
    - Add hypothesis for property-based testing
    - Add pytest, pytest-cov for testing
    - Add moto for AWS service mocking
  
  - [ ] 9.2 Create Lambda configuration files
    - Create configuration for Multi_Account_API_Handler (512 MB, 30s timeout)
    - Create configuration for Multi_Account_Cost_Collector (1024 MB, 900s timeout, reserved concurrency 1)
    - Create configuration for Multi_Account_Main_Handler (512 MB, 300s timeout)
    - Document environment variables for each handler
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_
  
  - [ ] 9.3 Create IAM policy documents
    - Create policy for API handler (DynamoDB, Secrets Manager, CloudWatch)
    - Create policy for cost collector (Organizations, STS, Cost Explorer, DynamoDB, CloudWatch)
    - Create policy for main handler (Organizations, DynamoDB, CloudWatch)
    - Create cross-account role trust policy with external ID
  
  - [ ] 9.4 Create CDK stack for infrastructure deployment
    - Define Lambda functions with configurations
    - Define DynamoDB tables with GSIs
    - Define API Gateway with endpoints and API key
    - Define EventBridge rules for scheduled triggers
    - Define CloudWatch alarms for monitoring
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ]* 10. Write integration tests for end-to-end flows
  - [ ]* 10.1 Write integration test for API Gateway → Handler → Service → DynamoDB flow
    - Test complete request flow for each endpoint
    - Use mocked AWS services
    - Verify response format and data
  
  - [ ]* 10.2 Write integration test for EventBridge → Cost Collector → DynamoDB flow
    - Test scheduled cost collection
    - Verify cost data persistence
    - Verify collection summary
  
  - [ ]* 10.3 Write integration test for multi-handler workflow
    - Test organization discovery → cost collection → aggregation flow
    - Verify data consistency across handlers
  
  - [ ]* 10.4 Write integration test for cross-account role assumption
    - Test role assumption with external ID
    - Test Cost Explorer queries
    - Test error handling for failed role assumptions
    - _Requirements: 2.3, 20.7_

- [ ] 11. Create deployment and operational documentation
  - [ ] 11.1 Create deployment guide
    - Document prerequisites (AWS Organizations, cross-account roles)
    - Document deployment steps using CDK
    - Document verification procedures
    - Document rollback procedures
  
  - [ ] 11.2 Create operational runbook
    - Document monitoring procedures
    - Document common troubleshooting scenarios
    - Document maintenance tasks (weekly, monthly, quarterly)
    - Document disaster recovery procedures
  
  - [ ] 11.3 Create API documentation
    - Document all 11 API endpoints with request/response examples
    - Document authentication requirements
    - Document error codes and messages
    - Document rate limits and quotas

- [ ] 12. Final checkpoint - Comprehensive testing and validation
  - Run full test suite (unit, property, integration)
  - Verify 80%+ code coverage
  - Verify all 25 properties pass with 100+ iterations
  - Run smoke tests against deployed infrastructure
  - Verify CloudWatch metrics are being published
  - Verify CloudWatch alarms are configured correctly
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (25 total)
- Unit tests validate specific examples and edge cases (80%+ coverage target)
- Integration tests validate end-to-end flows
- All handlers use Python 3.11 runtime
- Follow existing patterns from Phases 1-4 for consistency
- Implement comprehensive error handling with retry logic
- Include CloudWatch metrics for all operations
- Support both scheduled and manual triggers
- Parallel processing with max 10 concurrent accounts
