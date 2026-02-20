# Implementation Plan: Near-Real-Time Cost Estimation

## Overview

This implementation plan breaks down Phase 1.5 (Near-Real-Time Cost Estimation) into discrete, incremental tasks. Each task builds on Phase 1 and adds new capabilities for estimating AWS costs in near-real-time using CloudWatch metrics. The implementation extends the existing Phase 1 infrastructure without breaking changes.

## Tasks

- [ ] 1. Extend project structure for Phase 1.5
  - Add new service modules: `cloudwatch_collector.py`, `cost_estimator.py`, `pricing_manager.py`
  - Extend `types.py` with Phase 1.5 data models
  - Extend `validation.py` with Phase 1.5 validation functions
  - Update `requirements.txt` with any new dependencies
  - _Requirements: All requirements (foundation)_

- [ ] 2. Implement data models and types
  - [ ] 2.1 Create Phase 1.5 type definitions
    - Define dataclasses for MetricDataPoint, EC2Metrics, LambdaMetrics, DynamoDBMetrics, S3Metrics, RDSMetrics
    - Define dataclasses for PricingData, CostEstimate, EstimationResponse
    - Add type aliases for supported services
    - _Requirements: 1.1-1.7, 2.1-2.5_

  - [ ] 2.2 Write unit tests for data models
    - Test dataclass creation and validation
    - Test type conversions
    - _Requirements: 8.1, 8.2_

- [ ] 3. Implement CloudWatch Metrics Collector
  - [ ] 3.1 Create CloudWatch client wrapper
    - Initialize CloudWatch client using boto3.client('cloudwatch')
    - Implement connection handling and error wrapping
    - _Requirements: 1.1_

  - [ ] 3.2 Implement EC2 metrics collection
    - Write collect_ec2_metrics function
    - Fetch CPUUtilization, NetworkIn, NetworkOut, DiskReadBytes
    - Handle pagination and batching
    - _Requirements: 1.2_

  - [ ] 3.3 Implement Lambda metrics collection
    - Write collect_lambda_metrics function
    - Fetch Invocations, Duration, Errors
    - _Requirements: 1.3_

  - [ ] 3.4 Implement DynamoDB metrics collection
    - Write collect_dynamodb_metrics function
    - Fetch ConsumedReadCapacityUnits, ConsumedWriteCapacityUnits
    - _Requirements: 1.4_

  - [ ] 3.5 Implement S3 metrics collection
    - Write collect_s3_metrics function
    - Fetch NumberOfObjects, BucketSizeBytes
    - _Requirements: 1.5_

  - [ ] 3.6 Implement RDS metrics collection
    - Write collect_rds_metrics function
    - Fetch DatabaseConnections, ReadIOPS, WriteIOPS
    - _Requirements: 1.6_

  - [ ] 3.7 Implement batch metrics collection
    - Write collect_metrics function that collects for all services
    - Optimize API calls with batching
    - Store metrics in DynamoDB
    - _Requirements: 1.7, 1.8, 7.1, 7.2_

  - [ ] 3.8 Write property tests for metrics collector
    - **Property 1: Metric Collection Completeness**
    - **Property 10: Metric Validation**
    - **Property 13: Batch Metric Collection**
    - **Validates: Requirements 1.1, 1.7, 7.1, 7.2, 8.1**

  - [ ] 3.9 Write unit tests for metrics collector
    - Test each service's metric collection with mocked CloudWatch
    - Test error handling (rate limiting, service unavailable)
    - Test metric validation
    - _Requirements: 1.1-1.8, 6.1, 6.2_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Pricing Manager
  - [ ] 5.1 Create Pricing API client wrapper
    - Initialize Pricing client using boto3.client('pricing')
    - Implement connection handling
    - _Requirements: 3.1_

  - [ ] 5.2 Implement pricing data fetching
    - Write fetch_from_pricing_api function
    - Parse pricing API responses
    - Transform to internal PricingData format
    - _Requirements: 3.3, 3.4, 3.5_

  - [ ] 5.3 Implement pricing cache management
    - Write cache_pricing_data function (store in DynamoDB)
    - Write get_pricing_data function (check cache first)
    - Write is_pricing_stale function (check 24-hour TTL)
    - Write refresh_pricing_data function
    - _Requirements: 3.1, 3.2, 3.6, 7.3_

  - [ ] 5.4 Write property tests for pricing manager
    - **Property 3: Pricing Data Freshness**
    - **Property 11: Pricing Validation**
    - **Property 14: Pricing Cache Hit**
    - **Validates: Requirements 3.2, 3.3, 7.3, 8.2**

  - [ ] 5.5 Write unit tests for pricing manager
    - Test pricing API calls with mocked responses
    - Test cache hit/miss scenarios
    - Test pricing refresh logic
    - Test error handling (API failures)
    - _Requirements: 3.1-3.6, 6.3_

- [ ] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement Cost Estimator
  - [ ] 7.1 Implement EC2 cost estimation
    - Write estimate_ec2_cost function
    - Calculate costs based on instance type, running hours, data transfer
    - _Requirements: 2.1_

  - [ ] 7.2 Implement Lambda cost estimation
    - Write estimate_lambda_cost function
    - Calculate costs based on invocations, duration, memory
    - _Requirements: 2.2_

  - [ ] 7.3 Implement DynamoDB cost estimation
    - Write estimate_dynamodb_cost function
    - Calculate costs based on read/write capacity units
    - _Requirements: 2.3_

  - [ ] 7.4 Implement S3 cost estimation
    - Write estimate_s3_cost function
    - Calculate costs based on storage size and requests
    - _Requirements: 2.4_

  - [ ] 7.5 Implement RDS cost estimation
    - Write estimate_rds_cost function
    - Calculate costs based on instance type, running hours, storage
    - _Requirements: 2.5_

  - [ ] 7.6 Implement confidence interval calculation
    - Write calculate_confidence_interval function
    - Calculate upper and lower bounds based on metrics count
    - _Requirements: 2.8_

  - [ ] 7.7 Implement total cost aggregation
    - Write calculate_total_estimate function
    - Aggregate costs across all services
    - _Requirements: 2.6_

  - [ ] 7.8 Write property tests for cost estimator
    - **Property 2: Non-Negative Cost Estimates**
    - **Property 12: Estimation Bounds Check**
    - **Property 15: Confidence Interval Validity**
    - **Validates: Requirements 2.1-2.8, 8.1, 8.2, 8.3**

  - [ ] 7.9 Write unit tests for cost estimator
    - Test each service's cost calculation with known inputs
    - Test confidence interval calculations
    - Test total aggregation
    - Test error handling (missing pricing, zero usage)
    - _Requirements: 2.1-2.8, 2.7, 8.3_

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement Lambda handler extensions
  - [ ] 9.1 Extend routing logic
    - Add routes for /api/cost-estimation/current
    - Add routes for /api/cost-estimation/service/{service}
    - Maintain Phase 1 routes unchanged
    - _Requirements: 4.1, 4.3, 5.1, 5.2_

  - [ ] 9.2 Implement handle_estimation_current
    - Parse query parameters (time range)
    - Collect metrics for all services
    - Fetch pricing data
    - Calculate estimates
    - Format response
    - _Requirements: 4.2, 4.5, 4.6, 4.7_

  - [ ] 9.3 Implement handle_estimation_service
    - Parse service name from path
    - Parse query parameters (time range)
    - Collect metrics for specified service
    - Fetch pricing data
    - Calculate estimate
    - Format response
    - _Requirements: 4.4, 4.5, 4.6, 4.7_

  - [ ] 9.4 Implement input validation
    - Validate service names
    - Validate time ranges
    - Validate query parameters
    - _Requirements: 8.1, 8.2_

  - [ ] 9.5 Implement error handling
    - Handle CloudWatch errors
    - Handle Pricing API errors
    - Handle calculation errors
    - Format error responses
    - _Requirements: 6.1-6.6_

  - [ ] 9.6 Write property tests for Lambda handler
    - **Property 4: API Response Structure**
    - **Property 5: Authentication Enforcement**
    - **Property 6: Phase 1 Compatibility**
    - **Property 8: Error Isolation**
    - **Property 9: Response Time Bounds**
    - **Validates: Requirements 4.7, 4.8, 5.4, 6.4, 7.4**

  - [ ] 9.7 Write unit tests for Lambda handler
    - Test routing to Phase 1.5 endpoints
    - Test Phase 1 endpoints still work (backward compatibility)
    - Test estimation_current with various time ranges
    - Test estimation_service for each supported service
    - Test error responses
    - Test authentication
    - _Requirements: 4.1-4.8, 5.1-5.6, 6.5_

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Update infrastructure configuration
  - [ ] 11.1 Update IAM role permissions
    - Add CloudWatch GetMetricStatistics permission
    - Add CloudWatch ListMetrics permission
    - Add Pricing GetProducts permission
    - _Requirements: 1.1, 3.3_

  - [ ] 11.2 Update Lambda environment variables
    - Add PRICING_CACHE_TTL_HOURS
    - Add METRICS_COLLECTION_PERIOD
    - Add ESTIMATION_CONFIDENCE_LEVEL
    - _Requirements: 3.2, 7.2_

  - [ ] 11.3 Update API Gateway configuration
    - Add /api/cost-estimation/current endpoint
    - Add /api/cost-estimation/service/{service} endpoint
    - Configure Lambda integration
    - Reuse existing API key authentication
    - _Requirements: 4.1, 4.3, 5.5_

  - [ ] 11.4 Update CDK infrastructure code
    - Update IAM policies in CDK
    - Update Lambda environment variables in CDK
    - Update API Gateway routes in CDK
    - _Requirements: 5.3_

- [ ] 12. Integration testing
  - [ ] 12.1 Write end-to-end estimation test
    - Collect metrics from CloudWatch (mocked)
    - Fetch pricing data (mocked)
    - Calculate estimates
    - Verify response format
    - _Requirements: 4.1, 4.2, 4.7_

  - [ ] 12.2 Write Phase 1 compatibility test
    - Test Phase 1 /fetch endpoint still works
    - Test Phase 1 /query endpoint still works
    - Verify no breaking changes
    - _Requirements: 5.4_

  - [ ] 12.3 Write service-specific estimation tests
    - Test estimation for each supported service
    - Verify cost calculations
    - _Requirements: 2.1-2.5, 4.4_

  - [ ] 12.4 Write property tests for API integration
    - **Property 7: Retry Logic for Rate Limiting**
    - **Validates: Requirements 6.1**

- [ ] 13. Documentation updates
  - [ ] 13.1 Update README
    - Document new API endpoints
    - Add usage examples for estimation endpoints
    - Update architecture diagram
    - _Requirements: All requirements_

  - [ ] 13.2 Update API examples
    - Add curl examples for /cost-estimation/current
    - Add curl examples for /cost-estimation/service/{service}
    - Document query parameters
    - _Requirements: 4.1-4.7_

  - [ ] 13.3 Create Phase 1.5 documentation folder
    - Create docs/technical/phase1.5-near-realtime/
    - Move specification.md, implementation-summary.md, README.md
    - Update cross-references
    - _Requirements: All requirements_

- [ ] 14. Final checkpoint - Ensure all tests pass
  - Run all unit tests
  - Run all property-based tests
  - Run all integration tests
  - Verify test coverage is above 80%
  - Verify Phase 1 tests still pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows and Phase 1 compatibility
- All boto3 calls should be mocked in unit tests using moto or unittest.mock
- Phase 1 must continue to work without any breaking changes
- boto3 is included in Lambda runtime by default

## Testing Requirements

- Minimum 80% code coverage
- All 15 correctness properties must be tested
- Each property test must run minimum 100 iterations
- Phase 1 tests must continue to pass (backward compatibility)
- Tag format: `# Feature: near-realtime-cost-estimation, Property N: [property text]`

## Free Tier Compliance

- CloudWatch API: ~50,000 requests/month (within 1M free tier)
- Pricing API: ~100 requests/month with caching (~$0.01/month)
- DynamoDB: Additional ~10 MB storage (within 25 GB free tier)
- Lambda: Additional ~1,000 invocations/month (within 1M free tier)
