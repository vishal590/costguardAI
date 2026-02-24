# Implementation Tasks: Multi-Account Cost Management

## Overview

This document outlines the implementation tasks for Phase 5 of CostGuard AI: Multi-Account Cost Management. Tasks are organized into incremental milestones that build upon each other.

**Total Estimated Time:** 2-3 weeks  
**Approach:** Incremental development with testing at each stage  
**Testing:** Unit tests + Property-based tests for each component

---

## Tasks

### Milestone 1: Foundation & Organization Discovery

- [x] 1. Set up project structure for Phase 5
  - Create `src/services/multi_account/` directory
  - Create `tests/unit/multi_account/` directory
  - Create `tests/property/multi_account/` directory
  - Update `requirements.txt` with new dependencies (boto3 organizations, hypothesis)
  - _Requirements: All_

- [x] 2. Implement Organization Discovery Service
  - [x] 2.1 Create `OrganizationDiscoveryService` class
    - Implement `discover_organization()` method
    - Implement `get_all_accounts()` method
    - Implement `get_ou_hierarchy()` method
    - Implement `refresh_organization_cache()` method
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 2.2 Write unit tests for Organization Discovery
    - Test organization structure retrieval
    - Test account listing
    - Test OU hierarchy mapping
    - Mock Organizations API responses
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 2.3 Write property test for organization discovery completeness
    - **Property 1: Organization Discovery Completeness**
    - **Validates: Requirements 1.2**
    - Generate random organization structures
    - Verify all accounts are discovered
    - Verify no duplicates
    - _Requirements: 1.2_

- [x] 3. Create DynamoDB tables for multi-account data
  - [x] 3.1 Define CDK stack for new tables
    - Create `organizations` table
    - Create `accounts` table with GSI
    - Create `multi_account_costs` table with GSI
    - Create `allocation_rules` table
    - Create `budgets` table
    - _Requirements: All_

  - [x] 3.2 Implement DynamoDB client wrappers
    - Create `OrganizationRepository` class
    - Create `AccountRepository` class
    - Create `MultiAccountCostRepository` class
    - Create `AllocationRuleRepository` class
    - Create `BudgetRepository` class
    - _Requirements: All_

  - [x] 3.3 Write unit tests for DynamoDB repositories
    - Test CRUD operations for each repository
    - Mock DynamoDB responses
    - Test GSI queries
    - _Requirements: All_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

### Milestone 2: Cross-Account IAM Role Management

- [x] 5. Implement Cross-Account Role Manager
  - [x] 5.1 Create `CrossAccountRoleManager` class
    - Implement `generate_role_template()` method
    - Implement `get_role_arn()` method
    - Implement `assume_role()` method
    - Implement `validate_role_permissions()` method
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 5.2 Create CloudFormation templates for IAM roles
    - Create role template with read-only permissions
    - Create trust policy with external ID
    - Add Cost Explorer and CloudWatch permissions
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 5.3 Write unit tests for Cross-Account Role Manager
    - Test role template generation
    - Test role assumption with STS
    - Test permission validation
    - Mock STS AssumeRole responses
    - _Requirements: 2.5, 2.6, 2.7_

  - [x] 5.4 Write property test for role assumption idempotence
    - **Property 2: Cross-Account Role Assumption Idempotence**
    - **Validates: Requirements 2.5**
    - Generate random account IDs
    - Call assume_role() multiple times
    - Verify permissions are identical
    - _Requirements: 2.5_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

### Milestone 3: Multi-Account Cost Collection

- [x] 7. Implement Multi-Account Cost Collector
  - [x] 7.1 Create `MultiAccountCostCollector` class
    - Implement `collect_all_accounts()` method
    - Implement `collect_account()` method
    - Implement `collect_parallel()` method with ThreadPoolExecutor
    - Add retry logic with exponential backoff
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 7.2 Implement parallel processing logic
    - Use ThreadPoolExecutor for concurrent collection
    - Set max 10 concurrent workers
    - Set 60-second timeout per account
    - Handle failures gracefully
    - _Requirements: 3.2, 3.4, 17.4_

  - [x] 7.3 Write unit tests for Multi-Account Cost Collector
    - Test single account collection
    - Test parallel collection
    - Test failure handling
    - Test retry logic
    - Mock Cost Explorer API responses
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 7.4 Write property test for cost collection resilience
    - **Property 3: Cost Collection Resilience**
    - **Validates: Requirements 3.4, 18.1**
    - Generate random account lists with failures
    - Verify successful accounts have data
    - Verify failed accounts don't break collection
    - _Requirements: 3.4, 18.1_

  - [x] 7.5 Write property test for parallel collection equivalence
    - **Property 8: Parallel Collection Equivalence**
    - **Validates: Requirements 3.2**
    - Generate random account lists
    - Collect in parallel and sequentially
    - Verify results are equivalent
    - _Requirements: 3.2_

- [x] 8. Create Lambda function for cost collection
  - [x] 8.1 Create `multi_account_cost_collector_handler.py`
    - Implement Lambda handler
    - Add EventBridge trigger (daily)
    - Add error handling and logging
    - _Requirements: 3.1, 3.7_

  - [x] 8.2 Write integration tests for cost collection Lambda
    - Test Lambda invocation
    - Test EventBridge trigger
    - Test error scenarios
    - _Requirements: 3.1_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

### Milestone 4: Cost Aggregation & Consolidated Views

- [x] 10. Implement Cost Aggregation Engine
  - [x] 10.1 Create `CostAggregationEngine` class
    - Implement `aggregate_organization_costs()` method
    - Implement `aggregate_ou_costs()` method
    - Implement `aggregate_by_service()` method
    - Implement `get_top_spending_accounts()` method
    - Add caching logic (1-hour TTL)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 10.2 Write unit tests for Cost Aggregation Engine
    - Test organization-level aggregation
    - Test OU-level aggregation
    - Test service-level aggregation
    - Test top spending accounts
    - Test caching behavior
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 10.3 Write property test for cost aggregation consistency
    - **Property 4: Cost Aggregation Consistency**
    - **Validates: Requirements 4.1**
    - Generate random cost data for accounts
    - Verify sum of accounts = aggregated total
    - _Requirements: 4.1_

  - [x] 10.4 Write property test for cache consistency
    - **Property 9: Cache Consistency**
    - **Validates: Requirements 1.5**
    - Call aggregation twice within TTL
    - Verify second call uses cache
    - Verify data is identical
    - _Requirements: 1.5, 4.5_

- [x] 11. Implement per-account cost breakdown
  - [x] 11.1 Create `PerAccountCostService` class
    - Implement `get_account_costs()` method
    - Implement `compare_accounts()` method
    - Implement `detect_anomalies()` method
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 11.2 Write unit tests for per-account cost service
    - Test account cost retrieval
    - Test account comparison
    - Test anomaly detection
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

- [x] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

### Milestone 5: Cost Allocation & Chargeback

- [x] 13. Implement Cost Allocation Engine
  - [x] 13.1 Create `CostAllocationEngine` class
    - Implement `allocate_by_tags()` method
    - Implement `apply_allocation_rules()` method
    - Implement `calculate_unallocated_costs()` method
    - Implement `get_allocation_by_team()` method
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 13.2 Write unit tests for Cost Allocation Engine
    - Test tag-based allocation
    - Test rule application
    - Test unallocated cost calculation
    - Test team allocation
    - _Requirements: 6.1, 6.2, 6.3, 6.7_

  - [x] 13.3 Write property test for cost allocation conservation
    - **Property 5: Cost Allocation Conservation**
    - **Validates: Requirements 6.1, 7.1**
    - Generate random cost data with tags
    - Verify allocated + unallocated = total
    - _Requirements: 6.1, 7.1_

  - [x] 13.4 Write property test for allocation rule priority
    - **Property 6: Allocation Rule Priority**
    - **Validates: Requirements 8.6**
    - Generate rules with different priorities
    - Verify only highest-priority rule applied
    - _Requirements: 8.6_

  - [x] 13.5 Write property test for unallocated cost monotonicity
    - **Property 10: Unallocated Cost Monotonicity**
    - **Validates: Requirements 7.1, 8.1**
    - Add allocation rules incrementally
    - Verify unallocated costs decrease
    - _Requirements: 7.1, 8.1_

- [x] 14. Implement Allocation Rules Engine
  - [x] 14.1 Create `AllocationRulesEngine` class
    - Implement `create_rule()` method
    - Implement `validate_rule()` method
    - Implement `apply_rules_by_priority()` method
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 14.2 Write unit tests for Allocation Rules Engine
    - Test rule creation
    - Test rule validation
    - Test priority-based application
    - _Requirements: 8.1, 8.2, 8.6_

- [x] 15. Implement Showback & Chargeback Reports
  - [x] 15.1 Create `ShowbackReportService` class
    - Implement `generate_showback_report()` method
    - Implement report generation by team/project/environment
    - Add CSV export functionality
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [x] 15.2 Create `ChargebackReportService` class
    - Implement `generate_chargeback_report()` method
    - Add line item details
    - Add CSV and PDF export
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [x] 15.3 Write unit tests for report services
    - Test showback report generation
    - Test chargeback report generation
    - Test CSV/PDF export
    - _Requirements: 9.1, 9.7, 10.1, 10.7_

- [x] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

---

### Milestone 6: Organization-Wide Features

- [x] 17. Implement Organization-Wide Budgets
  - [x] 17.1 Create `OrganizationBudgetService` class
    - Implement `create_organization_budget()` method
    - Implement `create_ou_budget()` method
    - Implement `create_account_budget()` method
    - Implement budget monitoring and alerts
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [x] 17.2 Implement hierarchical budget rollup
    - Implement `calculate_ou_utilization()` method
    - Implement `calculate_org_utilization()` method
    - Implement budget hierarchy visualization
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [x] 17.3 Write unit tests for budget service
    - Test budget creation at all levels
    - Test budget utilization calculation
    - Test alert generation
    - _Requirements: 11.1, 11.6, 11.7_

  - [x] 17.4 Write property test for budget rollup consistency
    - **Property 7: Budget Rollup Consistency**
    - **Validates: Requirements 12.1, 12.2**
    - Generate random OU hierarchy with budgets
    - Verify account budgets ≤ OU budget
    - Verify OU budgets ≤ org budget
    - _Requirements: 12.1, 12.2_

- [x] 18. Implement Cross-Account Forecasting
  - [x] 18.1 Extend forecasting engine for multi-account
    - Implement `forecast_organization_costs()` method
    - Implement `forecast_ou_costs()` method
    - Implement `forecast_account_costs()` method
    - Integrate with existing Phase 2 forecasting engine
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

  - [x] 18.2 Write unit tests for cross-account forecasting
    - Test organization-level forecasts
    - Test OU-level forecasts
    - Test account-level forecasts
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 18.3 Write property test for forecast consistency
    - **Property 11: Cross-Account Forecast Consistency**
    - **Validates: Requirements 13.4**
    - Generate random historical data
    - Verify sum of account forecasts ≈ org forecast
    - _Requirements: 13.4_

- [x] 19. Implement Organization-Wide Prevention Policies
  - [x] 19.1 Extend prevention engine for multi-account
    - Implement `create_organization_policy()` method
    - Implement `create_ou_policy()` method
    - Implement policy inheritance logic
    - Integrate with existing Phase 3 prevention engine
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

  - [x] 19.2 Write unit tests for organization-wide prevention
    - Test policy creation at all levels
    - Test policy application across accounts
    - Test account-level overrides
    - _Requirements: 14.1, 14.3, 14.5_

  - [x] 19.3 Write property test for prevention policy inheritance
    - **Property 12: Prevention Policy Inheritance**
    - **Validates: Requirements 14.4, 14.5**
    - Generate OU hierarchy with policies
    - Verify accounts inherit OU policies
    - Verify overrides work correctly
    - _Requirements: 14.4, 14.5_

- [x] 20. Implement Cross-Account AI Advisor Context
  - [x] 20.1 Extend AI advisor for multi-account
    - Implement `get_organization_context()` method
    - Implement `get_account_context()` method
    - Enhance prompts with multi-account data
    - Integrate with existing Phase 4 AI advisor
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

  - [x] 20.2 Write unit tests for cross-account AI advisor
    - Test organization-wide queries
    - Test account-specific queries
    - Test cost allocation insights
    - _Requirements: 15.1, 15.2, 15.3_

- [x] 21. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - ✅ All 179 tests passing (146 unit + 30 property + 3 integration)

---

### Milestone 7: API Endpoints & Integration

- [x] 22. Implement Multi-Account API Endpoints
  - [x] 22.1 Create API Gateway endpoints
    - `GET /api/organizations` - List organizations
    - `GET /api/organizations/{org_id}/accounts` - List accounts
    - `GET /api/costs/consolidated` - Consolidated costs
    - `GET /api/costs/by-account` - Per-account costs
    - `GET /api/costs/account/{account_id}` - Account costs
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

  - [x] 22.2 Create allocation API endpoints
    - `GET /api/allocation/by-tag` - Allocated costs by tag
    - `GET /api/allocation/unallocated` - Unallocated costs
    - `POST /api/allocation/rules` - Create allocation rules
    - _Requirements: 16.6, 16.7, 16.8_

  - [x] 22.3 Create budget API endpoints
    - `GET /api/budgets/hierarchy` - Budget hierarchy
    - `POST /api/budgets/organization` - Create org budget
    - `POST /api/budgets/ou/{ou_id}` - Create OU budget
    - _Requirements: 16.9_

  - [x] 22.4 Add API authentication
    - Implement API key authentication
    - Add IAM-based authorization
    - Add rate limiting
    - _Requirements: 16.10, 17.6_

  - [x] 22.5 Write integration tests for API endpoints
    - Test all GET endpoints
    - Test all POST endpoints
    - Test authentication
    - Test error responses
    - _Requirements: 16.1-16.10_

  - [x] 22.6 Write property test for API response time
    - **Property 13: API Response Time Bound**
    - **Validates: Requirements 4.6, 17.3**
    - Generate random cost queries
    - Verify all responses within 5 seconds
    - _Requirements: 4.6, 17.3_

- [x] 23. Update Lambda handler for multi-account
  - [x] 23.1 Create `multi_account_handler.py`
    - Implement handler for all multi-account operations
    - Add routing logic for different operations
    - Add error handling and logging
    - _Requirements: All_

  - [x] 23.2 Write integration tests for Lambda handler
    - Test organization discovery
    - Test cost collection
    - Test cost aggregation
    - Test allocation
    - _Requirements: All_

- [x] 24. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - ✅ All 84 integration tests passing

---

### Milestone 8: Backward Compatibility & Migration

- [x] 25. Implement backward compatibility
  - [x] 25.1 Add single-account mode detection
    - Implement `is_multi_account_enabled()` method
    - Add fallback to Phase 1-4 functionality
    - Preserve existing API endpoints
    - _Requirements: 20.1, 20.2, 20.3, 20.6_

  - [x] 25.2 Implement migration path
    - Create `migrate_to_multi_account()` method
    - Preserve existing single-account data
    - Add migration validation
    - _Requirements: 20.4, 20.5_

  - [x] 25.3 Write property test for backward compatibility
    - **Property 14: Backward Compatibility**
    - **Validates: Requirements 20.2, 20.3**
    - Generate single-account cost data
    - Query with multi-account disabled
    - Query with multi-account enabled
    - Verify results are identical
    - _Requirements: 20.2, 20.3_

  - [x] 25.4 Write unit tests for migration
    - Test migration process
    - Test data preservation
    - Test rollback
    - _Requirements: 20.4, 20.5_

- [x] 26. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - ✅ All 84 integration tests passing
  - ✅ All 19 unit tests for backward compatibility passing
  - ✅ All 4 property tests for backward compatibility passing

---

### Milestone 9: Infrastructure & Deployment

- [x] 27. Create CDK infrastructure stack
  - [x] 27.1 Define `MultiAccountStack` in CDK
    - Add all Lambda functions
    - Add all DynamoDB tables
    - Add API Gateway configuration
    - Add IAM roles and policies
    - Add EventBridge rules
    - Add CloudWatch alarms
    - _Requirements: All_

  - [x] 27.2 Create CloudFormation templates for member accounts
    - Create cross-account role template
    - Add deployment instructions
    - Add StackSet configuration (optional)
    - _Requirements: 2.1_

  - [x] 27.3 Test infrastructure deployment
    - Deploy to test environment
    - Verify all resources created
    - Test resource connectivity
    - _Requirements: All_

- [x] 28. Implement monitoring and observability
  - [x] 28.1 Add CloudWatch metrics
    - `MultiAccountCostCollection.Duration`
    - `MultiAccountCostCollection.SuccessRate`
    - `CostAggregation.CacheHitRate`
    - `AllocationEngine.UnallocatedPercentage`
    - _Requirements: 17.1, 17.2, 17.3_

  - [x] 28.2 Add CloudWatch alarms
    - Cost collection failure rate > 10%
    - API response time > 5 seconds
    - DynamoDB throttling > 0
    - Lambda errors > 5 per hour
    - _Requirements: 18.6_

  - [x] 28.3 Configure CloudWatch Logs
    - Set up log groups for all Lambda functions
    - Add structured logging
    - Configure log retention
    - _Requirements: 19.6_

- [x] 29. Create deployment scripts
  - [x] 29.1 Create `deploy.sh` script
    - Deploy CDK stack
    - Deploy cross-account roles
    - Initialize organization discovery
    - Verify deployment
    - _Requirements: All_

  - [x] 29.2 Create `rollback.sh` script
    - Rollback CDK stack
    - Restore previous version
    - Verify rollback
    - _Requirements: All_

- [x] 30. Checkpoint - Ensure deployment successful
  - Ensure all infrastructure deployed, ask the user if questions arise.

---

### Milestone 10: Documentation & Testing

- [x] 31. Write comprehensive documentation
  - [x] 31.1 Create `README.md` for Phase 5
    - Overview of multi-account features
    - Setup instructions
    - API documentation
    - Troubleshooting guide
    - _Requirements: All_

  - [x] 31.2 Create setup guide for cross-account roles
    - Step-by-step instructions
    - CloudFormation template usage
    - Verification steps
    - _Requirements: 2.1_

  - [x] 31.3 Create API documentation
    - Document all new endpoints
    - Add request/response examples
    - Add authentication guide
    - _Requirements: 16.1-16.10_

  - [x] 31.4 Update main project documentation
    - Update `docs/technical/architecture.md`
    - Update `docs/API_EXAMPLES.md`
    - Update `docs/PROJECT_STATUS.md`
    - _Requirements: All_

- [x] 32. Run comprehensive test suite
  - [x] 32.1 Run all unit tests
    - Verify 85%+ code coverage
    - Fix any failing tests
    - _Requirements: All_

  - [x] 32.2 Run all property-based tests
    - Run with 100+ iterations per property
    - Verify all 15 properties pass
    - Fix any failing properties
    - _Requirements: All_

  - [x] 32.3 Run integration tests
    - Test with real AWS services
    - Test multi-account scenarios
    - Test error scenarios
    - _Requirements: All_

  - [x] 32.4 Run performance tests
    - Test 100-account collection time
    - Test API response times
    - Test parallel processing efficiency
    - _Requirements: 17.1, 17.2, 17.3_

- [x] 33. Final checkpoint - Phase 5 complete
  - Ensure all tests pass, all documentation complete, ask the user if questions arise.

---

## Summary

**Total Tasks:** 33 main tasks with 100+ sub-tasks  
**Estimated Time:** 2-3 weeks  
**Test Coverage Target:** 85%+  
**Property-Based Tests:** 15 properties with 100+ iterations each

**Key Milestones:**
1. ✅ Foundation & Organization Discovery (Tasks 1-4)
2. ✅ Cross-Account IAM Role Management (Tasks 5-6)
3. ✅ Multi-Account Cost Collection (Tasks 7-9)
4. ✅ Cost Aggregation & Consolidated Views (Tasks 10-12)
5. ✅ Cost Allocation & Chargeback (Tasks 13-16)
6. ✅ Organization-Wide Features (Tasks 17-21)
7. ✅ API Endpoints & Integration (Tasks 22-24)
8. ✅ Backward Compatibility & Migration (Tasks 25-26)
9. ✅ Infrastructure & Deployment (Tasks 27-30)
10. ✅ Documentation & Testing (Tasks 31-33)

**Next Steps:**
1. Review this task list
2. Start with Milestone 1 (Foundation)
3. Implement incrementally, testing at each checkpoint
4. Deploy to test environment
5. Verify all requirements met

---

**Document Status:** Complete  
**Last Updated:** February 2026  
**Ready for Implementation:** Yes
