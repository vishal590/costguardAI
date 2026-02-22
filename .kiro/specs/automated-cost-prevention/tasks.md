# Implementation Plan: Automated Cost Prevention

## Overview

This implementation plan breaks down Phase 3 (Automated Cost Prevention) into discrete, incremental tasks. Each task builds on Phase 1, 1.5, and 2, adding automated cost prevention capabilities with comprehensive safety mechanisms. The implementation extends the existing infrastructure without breaking changes.

## Tasks

- [x] 1. Extend project structure for Phase 3 ✓ COMPLETE
  - ✓ Add new service modules: `prevention_engine.py`, `budget_monitor.py`, `resource_manager.py`, `idle_detector.py`, `safety_guard.py`, `action_executor.py`, `approval_manager.py`, `rollback_manager.py`
  - ✓ Extend `types.py` with Phase 3 data models
  - ✓ Extend `validation.py` with Phase 3 validation functions
  - _Requirements: All requirements (foundation)_

- [x] 2. Implement data models and types
  - [x] 2.1 Create Phase 3 type definitions
    - Define dataclasses for BudgetStatus, ThresholdEvent, Resource, ResourceMetadata
    - Define dataclasses for IdleStatus, IdleCriteria, SafetyCheck, SafetyConfig
    - Define dataclasses for ActionResult, PlannedAction, ApprovalRequest, ApprovalResponse
    - Define dataclasses for RollbackResult
    - Add type aliases for prevention-related types
    - _Requirements: All data model requirements_

  - [x] 2.2 Write unit tests for data models
    - Test dataclass creation and validation
    - Test type conversions
    - _Requirements: 16.1_

- [x] 3. Implement Budget Monitor
  - [x] 3.1 Create BudgetMonitor class
    - Initialize with AWS Budgets client and cost estimator
    - Implement poll_budgets method
    - _Requirements: 1.1_

  - [x] 3.2 Implement threshold checking
    - Write check_thresholds function
    - Detect 80% warning threshold
    - Detect 90% action threshold
    - _Requirements: 1.2, 1.3_

  - [x] 3.3 Implement budget utilization calculation
    - Write calculate_utilization function
    - Support actual costs from Cost Explorer
    - Support estimated costs from Phase 1.5
    - _Requirements: 1.4, 1.6_

  - [x] 3.4 Implement multi-budget support
    - Handle service-specific budgets
    - Handle total account budgets
    - Handle time-period budgets
    - _Requirements: 1.5_

  - [x] 3.5 Write property tests for budget monitor
    - **Property 1: Budget Threshold Detection**
    - **Validates: Requirements 1.2, 1.3**

  - [x] 3.6 Write unit tests for budget monitor
    - Test budget polling with various scenarios
    - Test threshold detection at 80% and 90%
    - Test utilization calculation
    - Test fallback to cost estimates
    - _Requirements: 1.1-1.6_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Resource Manager ✓ COMPLETE
  - [x] 5.1 Create ResourceManager class
    - Initialize with AWS service clients
    - Implement discover_resources method
    - _Requirements: 2.1_

  - [x] 5.2 Implement service-specific resource discovery
    - Write discovery logic for EC2, RDS, EBS
    - Write discovery logic for Lambda, S3, DynamoDB
    - Write discovery logic for SNS, SQS, ElastiCache
    - Write discovery logic for remaining 11+ services
    - _Requirements: 2.1_

  - [x] 5.3 Implement resource metadata retrieval
    - Write get_resource_metadata function
    - Retrieve tags, creation date, state
    - Query CloudWatch metrics
    - _Requirements: 2.2, 2.3_

  - [x] 5.4 Implement resource inventory management
    - Write update_inventory function
    - Store resources in DynamoDB
    - Implement 15-minute refresh cycle
    - _Requirements: 2.4, 2.5_

  - [x] 5.5 Write property tests for resource manager
    - **Property 7: Multi-Service Coverage**
    - **Property 12: Resource Inventory Freshness**
    - **Validates: Requirements 2.1, 2.5**

  - [x] 5.6 Write unit tests for resource manager
    - Test resource discovery for each service
    - Test metadata retrieval
    - Test inventory updates
    - Test error handling for failed services
    - _Requirements: 2.1-2.5_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement Idle Detector ✓ COMPLETE
  - [x] 7.1 Create IdleDetector class
    - Initialize with CloudWatch client
    - Implement is_resource_idle method
    - _Requirements: 3.1-3.8_

  - [x] 7.2 Implement service-specific idle detection
    - Write check_ec2_idle (CPU < 5% for 2 hours)
    - Write check_rds_idle (connections = 0 for 1 hour)
    - Write check_lambda_idle (invocations = 0 for 24 hours)
    - Write check_ebs_idle (unattached for 7 days)
    - Write check_s3_idle (requests = 0 for 30 days)
    - Write check_dynamodb_idle (read/write = 0 for 24 hours)
    - _Requirements: 3.1-3.6_

  - [x] 7.3 Implement configurable idle criteria
    - Write get_idle_criteria function
    - Support per-service threshold configuration
    - _Requirements: 3.7, 3.8_

  - [x] 7.4 Write property tests for idle detector
    - **Property 3: Idle Detection Consistency**
    - **Validates: Requirements 3.1-3.8**

  - [x] 7.5 Write unit tests for idle detector
    - Test idle detection for each service
    - Test with various metric values
    - Test configurable thresholds
    - _Requirements: 3.1-3.8_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement Safety Guard ✓ COMPLETE
  - [x] 9.1 Create SafetyGuard class
    - Initialize with safety configuration
    - Implement is_action_safe method
    - _Requirements: 4.1-4.7_

  - [x] 9.2 Implement tag-based protection
    - Write check_tags function
    - Block "Environment=production" resources
    - Block "CostGuard=protected" resources
    - Block "CostGuard=exclude" resources
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 9.3 Implement whitelist checking
    - Write check_whitelist function
    - Support resource ID whitelist
    - _Requirements: 4.4_

  - [x] 9.4 Implement active usage checking
    - Write check_active_usage function
    - Check for active connections
    - Check for recent traffic
    - _Requirements: 4.3_

  - [x] 9.5 Implement minimum idle duration check
    - Validate resources meet minimum idle time
    - _Requirements: 4.5_

  - [x] 9.6 Implement safety logging
    - Log all blocked actions with reasons
    - Send notifications for blocked actions
    - _Requirements: 4.6_

  - [x] 9.7 Write property tests for safety guard
    - **Property 2: Protected Resource Safety**
    - **Property 8: Safety Check Ordering**
    - **Validates: Requirements 4.1-4.7**

  - [x] 9.8 Write unit tests for safety guard
    - Test tag-based protection
    - Test whitelist checking
    - Test active usage detection
    - Test minimum idle duration
    - Test with various resource combinations
    - _Requirements: 4.1-4.7_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Action Executor ✓ COMPLETE
  - [x] 11.1 Create ActionExecutor class
    - Initialize with AWS service clients
    - Implement execute_action method
    - _Requirements: 5.1-5.9_

  - [x] 11.2 Implement EC2 actions
    - Write stop_ec2_instance function
    - Store pre-action state
    - _Requirements: 5.1_

  - [x] 11.3 Implement RDS actions
    - Write stop_rds_instance function
    - Store pre-action state
    - _Requirements: 5.2_

  - [x] 11.4 Implement Lambda actions
    - Write limit_lambda_concurrency function
    - Set concurrency to 0
    - _Requirements: 5.3_

  - [x] 11.5 Implement EBS actions
    - Write snapshot_and_delete_volume function
    - Create snapshot before deletion
    - _Requirements: 5.4_

  - [x] 11.6 Implement DynamoDB actions
    - Write switch_to_ondemand function
    - Switch billing mode
    - _Requirements: 5.5_

  - [x] 11.7 Implement NAT Gateway actions
    - Write delete_nat_gateway function
    - Create documentation before deletion
    - _Requirements: 5.6_

  - [x] 11.8 Implement action prioritization
    - Sort actions by cost impact
    - Execute highest cost first
    - _Requirements: 5.7_

  - [x] 11.9 Implement error handling
    - Continue on individual action failures
    - Log all errors with context
    - _Requirements: 5.8_

  - [x] 11.10 Implement audit logging
    - Record all actions in DynamoDB
    - Include before/after state
    - _Requirements: 5.9_

  - [x] 11.11 Write property tests for action executor
    - **Property 13: Action Prioritization**
    - **Property 14: Error Isolation**
    - **Validates: Requirements 5.7, 5.8**

  - [x] 11.12 Write unit tests for action executor
    - Test each service-specific action
    - Test action prioritization
    - Test error handling
    - Test audit logging
    - _Requirements: 5.1-5.9_

- [x] 12. Checkpoint - Ensure all tests pass ✓ COMPLETE
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Implement Approval Manager ✓ COMPLETE
  - [x] 13.1 Create ApprovalManager class
    - Initialize with SNS and DynamoDB clients
    - Implement request_approval method
    - _Requirements: 7.1-7.6_

  - [x] 13.2 Implement approval request
    - Write request_approval function
    - Send SNS notification with action details
    - Store request in DynamoDB
    - _Requirements: 7.1_

  - [x] 13.3 Implement approval waiting
    - Write wait_for_approval function
    - Poll DynamoDB for response
    - Implement 30-minute timeout
    - _Requirements: 7.2, 7.5_

  - [x] 13.4 Implement approval processing
    - Write process_approval_response function
    - Handle approval via API endpoint
    - Handle approval via email response
    - _Requirements: 7.3, 7.4, 7.6_

  - [x] 13.5 Write property tests for approval manager
    - **Property 11: Approval Timeout Handling**
    - **Validates: Requirements 7.5**

  - [x] 13.6 Write unit tests for approval manager
    - Test approval request creation
    - Test approval waiting with timeout
    - Test approval processing
    - Test denial handling
    - _Requirements: 7.1-7.6_

- [x] 14. Checkpoint - Ensure all tests pass ✓ COMPLETE
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement Rollback Manager ✓ COMPLETE
  - [x] 15.1 Create RollbackManager class
    - Initialize with AWS clients and DynamoDB
    - Implement execute_rollback method
    - _Requirements: 9.1-9.7_

  - [x] 15.2 Implement state storage
    - Write store_pre_action_state function
    - Store complete resource state
    - _Requirements: 9.1_

  - [x] 15.3 Implement rollback execution
    - Write execute_rollback function
    - Support rollback within 24 hours
    - _Requirements: 9.2, 9.3_

  - [x] 15.4 Implement service-specific rollback
    - Write rollback for EC2 (restart instances)
    - Write rollback for RDS (restart databases)
    - Write rollback for Lambda (restore concurrency)
    - _Requirements: 9.4, 9.5, 9.6_

  - [x] 15.5 Implement rollback logging
    - Log all rollback operations
    - _Requirements: 9.7_

  - [x] 15.6 Write property tests for rollback manager
    - **Property 4: Action Reversibility**
    - **Validates: Requirements 9.1-9.7**

  - [x] 15.7 Write unit tests for rollback manager
    - Test state storage
    - Test rollback execution
    - Test service-specific rollback
    - Test 24-hour expiration
    - _Requirements: 9.1-9.7_

- [x] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Implement Notification Service ✓ COMPLETE
  - [x] 17.1 Create NotificationService class
    - Initialize with SNS client
    - Implement notification methods
    - _Requirements: 8.1-8.6_

  - [x] 17.2 Implement warning notifications
    - Write send_warning function
    - Trigger at 80% threshold
    - _Requirements: 8.1_

  - [x] 17.3 Implement action notifications
    - Write send_action_notification function
    - Include resource details and savings
    - _Requirements: 8.3, 8.5_

  - [x] 17.4 Implement error notifications
    - Write send_error_notification function
    - Include error context
    - _Requirements: 8.4_

  - [x] 17.5 Implement multi-topic support
    - Support separate topics for warnings, actions, errors
    - _Requirements: 8.6_

  - [x] 17.6 Write property tests for notification service
    - **Property 9: Notification Delivery**
    - **Validates: Requirements 8.1-8.6**

  - [x] 17.7 Write unit tests for notification service
    - Test warning notifications
    - Test action notifications
    - Test error notifications
    - Test multi-topic routing
    - _Requirements: 8.1-8.6_

- [x] 18. Checkpoint - Ensure all tests pass ✓ COMPLETE
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19. Implement Prevention Engine (Orchestration)
  - [x] 19.1 Create PreventionEngine class
    - Initialize with all components
    - Implement main orchestration logic
    - _Requirements: All requirements_

  - [x] 19.2 Implement budget monitoring workflow
    - Poll budgets every 5 minutes
    - Detect threshold breaches
    - Trigger prevention actions
    - _Requirements: 1.1-1.6_

  - [x] 19.3 Implement prevention workflow
    - Discover resources
    - Detect idle resources
    - Check safety guards
    - Execute actions (or request approval)
    - Send notifications
    - _Requirements: All requirements_

  - [x] 19.4 Implement dry run mode
    - Log planned actions without execution
    - Generate dry run reports
    - _Requirements: 6.1-6.5_

  - [x] 19.5 Implement configuration management
    - Load configuration from DynamoDB
    - Support runtime configuration updates
    - Validate configuration
    - _Requirements: 11.1-11.7_

  - [x] 19.6 Write property tests for prevention engine
    - **Property 5: Dry Run Safety**
    - **Property 6: Audit Trail Completeness**
    - **Property 10: Configuration Validation**
    - **Validates: Requirements 6.1-6.5, 11.6, 12.1-12.8**

  - [x] 19.7 Write unit tests for prevention engine
    - Test budget monitoring workflow
    - Test prevention workflow
    - Test dry run mode
    - Test configuration management
    - _Requirements: All requirements_

- [x] 20. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 21. Implement Lambda handler extensions
  - [x] 21.1 Extend routing logic
    - Add routes for /api/prevention/status
    - Add routes for /api/prevention/enable
    - Add routes for /api/prevention/disable
    - Add routes for /api/prevention/resources
    - Add routes for /api/prevention/rollback
    - Add routes for /api/prevention/history
    - Maintain Phase 1, 1.5, and 2 routes unchanged
    - _Requirements: 10.1-10.7, 15.1-15.5_

  - [x] 21.2 Implement prevention status endpoint
    - Parse request parameters
    - Call PreventionEngine.get_status
    - Format response
    - _Requirements: 10.1_

  - [x] 21.3 Implement enable/disable endpoints
    - Validate request
    - Update configuration
    - Return status
    - _Requirements: 10.2, 10.3_

  - [x] 21.4 Implement resources endpoint
    - Query resource inventory
    - Filter by service/state
    - Return resource list
    - _Requirements: 10.4_

  - [x] 21.5 Implement rollback endpoint
    - Parse action ID
    - Call RollbackManager.execute_rollback
    - Return rollback result
    - _Requirements: 10.5_

  - [x] 21.6 Implement history endpoint
    - Query audit logs
    - Filter by date range
    - Return action history
    - _Requirements: 10.6_

  - [x] 21.7 Implement error handling
    - Handle all Phase 3 error types
    - Format error responses
    - _Requirements: All error handling requirements_

  - [x] 21.8 Write property tests for Lambda handler
    - **Property 15: Backward Compatibility**
    - **Validates: Requirements 15.1-15.5**

  - [x] 21.9 Write unit tests for Lambda handler
    - Test routing to Phase 3 endpoints
    - Test Phase 1, 1.5, and 2 endpoints still work
    - Test all Phase 3 endpoints
    - Test error responses
    - Test authentication
    - _Requirements: 10.1-10.7, 15.1-15.5_

- [x] 22. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 23. Implement EventBridge integration
  - [x] 23.1 Create EventBridge schedule
    - Configure 5-minute schedule
    - Set Lambda as target
    - _Requirements: 1.1_

  - [x] 23.2 Implement event handler
    - Parse EventBridge events
    - Trigger budget monitoring
    - _Requirements: 1.1_

  - [x] 23.3 Write unit tests for EventBridge integration
    - Test event parsing
    - Test schedule triggering
    - _Requirements: 1.1_

- [x] 24. Update infrastructure configuration
  - [x] 24.1 Create DynamoDB tables
    - Table: prevention-config
    - Table: resource-inventory
    - Table: prevention-audit
    - Table: approval-requests
    - _Requirements: All DynamoDB requirements_

  - [x] 24.2 Update IAM role permissions
    - Add Budgets API permissions
    - Add EC2/RDS/Lambda/etc management permissions
    - Add SNS publish permissions
    - Add EventBridge permissions
    - _Requirements: All IAM requirements_

  - [x] 24.3 Update Lambda environment variables
    - Add PREVENTION_ENABLED
    - Add DRY_RUN_MODE
    - Add APPROVAL_REQUIRED
    - Add configuration table names
    - _Requirements: 11.7_

  - [x] 24.4 Create SNS topics
    - Topic: prevention-warnings
    - Topic: prevention-actions
    - Topic: prevention-errors
    - _Requirements: 8.6_

  - [x] 24.5 Update API Gateway configuration
    - Add Phase 3 endpoints
    - Maintain Phase 1/1.5/2 routes
    - _Requirements: 10.1-10.7_

  - [x] 24.6 Update CDK infrastructure code
    - Update IAM policies in CDK
    - Create DynamoDB tables in CDK
    - Create SNS topics in CDK
    - Create EventBridge schedule in CDK
    - Update Lambda configuration in CDK
    - Update API Gateway routes in CDK
    - _Requirements: All infrastructure requirements_

- [ ] 25. Integration testing
  - [ ] 25.1 Write end-to-end prevention test
    - Mock budget threshold breach
    - Verify resource discovery
    - Verify idle detection
    - Verify safety checks
    - Verify action execution (dry run)
    - _Requirements: All requirements_

  - [ ] 25.2 Write Phase 1/1.5/2 compatibility test
    - Test all Phase 1 endpoints still work
    - Test all Phase 1.5 endpoints still work
    - Test all Phase 2 endpoints still work
    - Verify no breaking changes
    - _Requirements: 15.1-15.5_

  - [ ] 25.3 Write multi-service test
    - Test resource discovery for all 20+ services
    - Test idle detection for multiple services
    - Test action execution for multiple services
    - _Requirements: 2.1, 3.1-3.8, 5.1-5.9_

  - [ ] 25.4 Write approval workflow test
    - Test approval request
    - Test approval granted
    - Test approval denied
    - Test approval timeout
    - _Requirements: 7.1-7.6_

  - [ ] 25.5 Write rollback test
    - Execute actions
    - Verify rollback restores state
    - Test rollback expiration
    - _Requirements: 9.1-9.7_

- [x] 26. Documentation updates
  - [x] 26.1 Update README
    - Document Phase 3 features
    - Add prevention API examples
    - Update architecture diagram
    - _Requirements: All requirements_

  - [x] 26.2 Update API examples
    - Add curl examples for prevention endpoints
    - Document configuration options
    - Add Python code examples
    - _Requirements: 10.1-10.7_

  - [x] 26.3 Create Phase 3 documentation folder
    - Create docs/technical/phase3-automated-prevention/
    - Create specification.md
    - Create implementation-summary.md
    - Create infrastructure-updates.md
    - Update cross-references
    - _Requirements: All requirements_

- [x] 27. Final checkpoint - Ensure all tests pass ✓ COMPLETE
  - Run all unit tests
  - Run all property-based tests
  - Run all integration tests
  - Verify test coverage is above 80%
  - Verify Phase 1, 1.5, and 2 tests still pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows and backward compatibility
- All AWS calls should be mocked in unit tests using moto or unittest.mock
- Phase 1, 1.5, and 2 must continue to work without any breaking changes
- Start with dry run mode enabled for safety

## Testing Requirements

- Minimum 80% code coverage for Phase 3 code
- All 15 correctness properties must be tested
- Each property test must run minimum 100 iterations
- Phase 1, 1.5, and 2 tests must continue to pass (backward compatibility)
- Tag format: `# Feature: automated-cost-prevention, Property N: [property text]`
- Test all 20+ supported services

## Free Tier Compliance

- AWS Budgets API: 2 budgets per account (free)
- Lambda: Additional invocations (within 1M free tier)
- DynamoDB: Additional tables and storage (within 25 GB free tier)
- SNS: Notifications (within 1M publishes/month free tier)
- EventBridge: Schedule (free)
- CloudWatch: Metrics and logs (within free tier)

## Safety First Approach

- Start with dry run mode enabled
- Monitor dry run reports for 24-48 hours
- Validate safety mechanisms
- Enable approval workflow initially
- Gradually disable approval after confidence is built
- Never disable safety guards

## Property-Based Testing

Each correctness property from the design document must be implemented as a property-based test:

1. Property 1: Budget Threshold Detection
2. Property 2: Protected Resource Safety
3. Property 3: Idle Detection Consistency
4. Property 4: Action Reversibility
5. Property 5: Dry Run Safety
6. Property 6: Audit Trail Completeness
7. Property 7: Multi-Service Coverage
8. Property 8: Safety Check Ordering
9. Property 9: Notification Delivery
10. Property 10: Configuration Validation
11. Property 11: Approval Timeout Handling
12. Property 12: Resource Inventory Freshness
13. Property 13: Action Prioritization
14. Property 14: Error Isolation
15. Property 15: Backward Compatibility
