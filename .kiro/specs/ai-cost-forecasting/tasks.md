# Implementation Plan: AI Cost Forecasting

## Overview

This implementation plan breaks down Phase 2 (AI Cost Forecasting) into discrete, incremental tasks. Each task builds on Phase 1 & 1.5 and adds AI-powered forecasting capabilities using Amazon Bedrock. The implementation extends the existing infrastructure without breaking changes.

## Tasks

- [x] 1. Extend project structure for Phase 2
  - Add new service modules: `forecast_engine.py`, `bedrock_client.py`, `forecast_cache.py`, `historical_data.py`
  - Extend `types.py` with Phase 2 data models
  - Extend `validation.py` with Phase 2 validation functions
  - Update `requirements.txt` with boto3 bedrock-runtime support
  - _Requirements: All requirements (foundation)_

- [x] 2. Implement data models and types
  - [x] 2.1 Create Phase 2 type definitions
    - Define dataclasses for ForecastDataPoint, ForecastResponse, ForecastMetadata
    - Define dataclasses for CachedForecast, ProcessedData, BedrockRequest, BedrockResponse
    - Add type aliases for forecast-related types
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 2.2 Write unit tests for data models
    - Test dataclass creation and validation
    - Test type conversions
    - 18 tests passing in tests/unit/test_forecast_types.py
    - _Requirements: 11.1_

- [x] 3. Implement Historical Data Retriever
  - [x] 3.1 Create HistoricalDataRetriever class
    - Initialize with DynamoDB client
    - Implement get_historical_data method
    - _Requirements: 1.1_

  - [x] 3.2 Implement data aggregation
    - Write aggregate_by_service_and_date function
    - Handle multiple services and date ranges
    - _Requirements: 1.3_

  - [x] 3.3 Implement gap interpolation
    - Write interpolate_gaps function using linear interpolation
    - Fill missing dates between start and end
    - _Requirements: 1.4_

  - [x] 3.4 Implement data validation
    - Write validate_completeness function
    - Check minimum 30 days of data
    - Raise InsufficientDataError if needed
    - _Requirements: 1.2, 1.5_

  - [x] 3.5 Write property tests for historical data retriever
    - **Property 1: Historical Data Validation** (100 examples)
    - **Property 2: Data Interpolation Completeness** (100 examples)
    - **Property 7: Service-Specific Data Filtering** (100 examples)
    - **Property 16: Historical Data Limit** (100 examples)
    - **Validates: Requirements 1.1, 1.2, 1.4, 3.5, 8.4**

  - [x] 3.6 Write unit tests for historical data retriever
    - Test data retrieval with various date ranges
    - Test aggregation logic
    - Test interpolation with gaps
    - Test validation with insufficient data
    - 18 unit tests passing
    - _Requirements: 1.1-1.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - All tests passing: 335 tests, 91.38% coverage ✅

- [x] 5. Implement Bedrock Client
  - [x] 5.1 Create BedrockClient class
    - Initialize boto3 bedrock-runtime client
    - Set model_id to Nova Lite or Nova Micro
    - _Requirements: 2.1, 2.2, 9.3_

  - [x] 5.2 Implement prompt building
    - Write build_prompt function
    - Include time series forecasting instructions
    - Include confidence interval requirements
    - Format historical data as JSON
    - _Requirements: 2.3, 2.6_

  - [x] 5.3 Implement Bedrock invocation
    - Write invoke_forecast function
    - Call bedrock-runtime InvokeModel API
    - Handle request/response formatting
    - _Requirements: 2.1, 2.2_

  - [x] 5.4 Implement response parsing
    - Write parse_response function
    - Extract predictions and confidence intervals
    - Convert to ForecastDataPoint objects
    - Handle invalid JSON responses
    - _Requirements: 2.4, 7.4_

  - [x] 5.5 Implement retry logic
    - Write retry_with_backoff function
    - Exponential backoff: 1s, 2s, 4s
    - Max 3 retries
    - Handle rate limiting errors
    - _Requirements: 2.5, 7.2_

  - [x] 5.6 Write property tests for Bedrock client
    - **Property 14: Retry Logic for Rate Limiting**
    - **Property 18: Bedrock Prompt Structure**
    - **Validates: Requirements 2.5, 2.6, 7.2**

  - [x] 5.7 Write unit tests for Bedrock client
    - Test prompt building with various data
    - Test Bedrock invocation with mocked responses
    - Test response parsing with valid/invalid JSON
    - Test retry logic with rate limit errors
    - Test error handling (API failures)
    - _Requirements: 2.1-2.6, 7.2, 7.4_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement Forecast Cache Manager
  - [x] 7.1 Create ForecastCacheManager class
    - Initialize with DynamoDB client and table name
    - Implement cache key generation
    - _Requirements: 4.5_

  - [x] 7.2 Implement cache retrieval
    - Write get_cached_forecast function
    - Check TTL expiration
    - Return None if expired or not found
    - _Requirements: 4.2, 4.3_

  - [x] 7.3 Implement cache storage
    - Write store_forecast function
    - Set 24-hour TTL
    - Store with generated cache key
    - _Requirements: 4.1_

  - [x] 7.4 Implement cache invalidation
    - Write invalidate_all function
    - Clear all cached forecasts
    - _Requirements: 4.4_

  - [x] 7.5 Implement cache metrics
    - Write track_cache_hit_rate function
    - Track hits and misses
    - Calculate hit rate percentage
    - _Requirements: 4.6_

  - [x] 7.6 Write property tests for cache manager
    - **Property 9: Cache Key Uniqueness**
    - **Property 10: Cache TTL Enforcement**
    - **Property 11: Cache Invalidation Completeness**
    - **Validates: Requirements 4.1, 4.3, 4.4, 4.5**

  - [x] 7.7 Write unit tests for cache manager
    - Test cache key generation
    - Test cache hit/miss scenarios
    - Test TTL expiration
    - Test invalidation
    - Test hit rate tracking
    - _Requirements: 4.1-4.6_

- [x] 8. Checkpoint - Ensure all tests pass
  - All tests passing: 391 tests, 94.55% coverage ✅

- [x] 9. Implement Forecast Engine
  - [ ] 9.1 Create ForecastEngine class
    - Initialize with dependencies (Bedrock, DynamoDB, Cache)
    - Implement orchestration logic
    - _Requirements: 3.1_

  - [ ] 9.2 Implement forecast generation
    - Write generate_forecast function
    - Check cache first
    - Retrieve historical data
    - Validate and preprocess data
    - Call Bedrock for predictions
    - Store in cache
    - Return ForecastResponse
    - _Requirements: 3.1, 3.2, 4.2_

  - [ ] 9.3 Implement weekly aggregation
    - Write aggregate_to_weekly function
    - Sum daily predictions into weekly totals
    - Aggregate confidence intervals
    - _Requirements: 3.3_

  - [ ] 9.4 Implement service-specific forecasts
    - Filter historical data by service
    - Generate forecast for single service
    - _Requirements: 3.5_

  - [ ] 9.5 Implement total forecasts
    - Aggregate forecasts across all services
    - Sum predictions and confidence intervals
    - _Requirements: 3.6_

  - [ ] 9.6 Implement accuracy metrics
    - Write calculate_accuracy_metrics function
    - Calculate MAPE and RMSE
    - Use backtesting approach
    - _Requirements: 3.7, 11.4_

  - [ ] 9.7 Write property tests for forecast engine
    - **Property 3: Forecast Length Consistency**
    - **Property 4: Confidence Interval Validity**
    - **Property 5: Non-Negative Cost Predictions**
    - **Property 6: Weekly Aggregation Consistency**
    - **Property 8: Total Forecast Aggregation**
    - **Validates: Requirements 3.1, 3.3, 3.4, 3.6**

  - [x] 9.8 Write unit tests for forecast engine
    - Test forecast generation with various parameters
    - Test cache hit/miss flows
    - Test weekly aggregation
    - Test service-specific forecasts
    - Test total forecasts
    - Test accuracy metrics calculation
    - Test error handling (insufficient data, Bedrock failures)
    - _Requirements: 3.1-3.7_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Lambda handler extensions
  - [x] 11.1 Extend routing logic
    - Add routes for /api/cost-forecast
    - Add routes for /api/cost-forecast/service/{service}
    - Maintain Phase 1 & 1.5 routes unchanged
    - _Requirements: 5.1, 5.2, 10.1, 10.2_

  - [x] 11.2 Implement handle_forecast_request
    - Parse query parameters (days, granularity)
    - Validate parameters
    - Call ForecastEngine.generate_forecast
    - Format response
    - _Requirements: 5.3, 5.4, 5.5, 6.1, 6.2_

  - [x] 11.3 Implement handle_forecast_service_request
    - Parse service name from path
    - Parse query parameters (days, granularity)
    - Validate service name
    - Call ForecastEngine.generate_forecast with service
    - Format response
    - _Requirements: 5.2, 5.3, 5.6, 6.4_

  - [x] 11.4 Implement input validation
    - Validate days parameter (7, 14, 30)
    - Validate granularity parameter (daily, weekly)
    - Validate service names
    - Return 400 errors for invalid inputs
    - _Requirements: 5.6, 5.7, 8.1_

  - [x] 11.5 Implement error handling
    - Handle InsufficientDataError (400)
    - Handle BedrockAPIError (503)
    - Handle BedrockRateLimitError (429)
    - Handle ValidationError (400)
    - Handle DynamoDBError (500)
    - Format error responses
    - _Requirements: 7.1-7.6_

  - [x] 11.6 Implement monitoring
    - Log all Bedrock API calls
    - Log cache hit/miss events
    - Emit CloudWatch metrics
    - Track latency metrics
    - _Requirements: 12.1-12.6_

  - [x] 11.7 Write property tests for Lambda handler
    - **Property 12: Response Structure Completeness**
    - **Property 13: Forecast Data Point Structure**
    - **Property 15: Backward Compatibility**
    - **Property 17: Response Time for Cached Forecasts**
    - **Property 19: Error Response Structure**
    - **Property 20: Metrics Emission**
    - **Validates: Requirements 6.1, 6.2, 6.3, 8.1, 10.1, 10.2, 10.5, 12.4, 12.5, 12.6**

  - [x] 11.8 Write unit tests for Lambda handler
    - Test routing to Phase 2 endpoints
    - Test Phase 1 & 1.5 endpoints still work (backward compatibility)
    - Test forecast_request with various parameters
    - Test forecast_service_request for each service
    - Test error responses
    - Test authentication
    - Test monitoring/logging
    - _Requirements: 5.1-5.8, 6.1-6.6, 7.1-7.6, 10.1-10.5, 12.1-12.6_

- [x] 12. Checkpoint - Ensure all tests pass
  - All tests passing: 412 tests, 94.16% coverage ✅

- [x] 13. Update infrastructure configuration
  - [x] 13.1 Create forecast cache DynamoDB table
    - Table name: costguard-forecast-cache
    - Partition key: cache_key (String)
    - TTL attribute: ttl (Number)
    - On-demand billing
    - _Requirements: 4.1, 9.4_

  - [x] 13.2 Update IAM role permissions
    - Add bedrock:InvokeModel permission
    - Add DynamoDB permissions for forecast cache table
    - _Requirements: 2.1_

  - [x] 13.3 Update Lambda environment variables
    - Add BEDROCK_MODEL_ID
    - Add FORECAST_CACHE_TABLE
    - Add FORECAST_CACHE_TTL_HOURS
    - _Requirements: 2.2, 4.1_

  - [x] 13.4 Update API Gateway configuration
    - Add /api/cost-forecast endpoint
    - Add /api/cost-forecast/service/{service} endpoint
    - Configure Lambda integration
    - Reuse existing API key authentication
    - _Requirements: 5.1, 5.2, 5.8_

  - [x] 13.5 Update CDK infrastructure code
    - Update IAM policies in CDK
    - Create forecast cache table in CDK
    - Update Lambda environment variables in CDK
    - Update API Gateway routes in CDK
    - _Requirements: All infrastructure requirements_

- [x] 14. Integration testing
  - [x] 14.1 Write end-to-end forecast test
    - Retrieve historical data (mocked)
    - Call Bedrock (mocked)
    - Generate forecast
    - Verify response format
    - _Requirements: 3.1, 6.1, 6.2_

  - [x] 14.2 Write Phase 1 & 1.5 compatibility test
    - Test Phase 1 /fetch endpoint still works
    - Test Phase 1 /query endpoint still works
    - Test Phase 1.5 /cost-estimation endpoints still work
    - Verify no breaking changes
    - _Requirements: 10.1, 10.2, 10.5_

  - [x] 14.3 Write cache behavior tests
    - Test cache hit scenario
    - Test cache miss scenario
    - Test cache invalidation
    - Verify cache hit rate tracking
    - _Requirements: 4.1-4.6_

  - [x] 14.4 Write error scenario tests
    - Test insufficient data error
    - Test Bedrock API failure
    - Test rate limiting with retries
    - Test invalid parameters
    - _Requirements: 7.1-7.6_

  - [x] 14.5 Write backtesting validation
    - Use historical data for forecasts
    - Compare predictions against actual costs
    - Calculate MAPE and RMSE
    - Verify accuracy metrics
    - _Requirements: 3.7, 11.4_

- [x] 15. Documentation updates
  - [x] 15.1 Update README
    - Document new API endpoints
    - Add usage examples for forecast endpoints
    - Update architecture diagram
    - _Requirements: All requirements_

  - [x] 15.2 Update API examples
    - Add curl examples for /cost-forecast
    - Add curl examples for /cost-forecast/service/{service}
    - Document query parameters
    - Add Python code examples
    - _Requirements: 5.1-5.7_

  - [x] 15.3 Create Phase 2 documentation folder
    - Create docs/technical/phase2-ai-forecasting/
    - Move specification.md, implementation-summary.md, README.md
    - Update cross-references
    - _Requirements: All requirements_

- [x] 16. Final checkpoint - Ensure all tests pass
  - Run all unit tests
  - Run all property-based tests
  - Run all integration tests
  - Run backtesting validation
  - Verify test coverage is above 80%
  - Verify Phase 1 & 1.5 tests still pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows and backward compatibility
- All boto3 calls should be mocked in unit tests using moto or unittest.mock
- Phase 1 & 1.5 must continue to work without any breaking changes
- boto3 bedrock-runtime is included in Lambda runtime by default

## Testing Requirements

- Minimum 80% code coverage for Phase 2 code
- All 20 correctness properties must be tested
- Each property test must run minimum 100 iterations
- Phase 1 & 1.5 tests must continue to pass (backward compatibility)
- Tag format: `# Feature: ai-cost-forecasting, Property N: [property text]`
- Backtesting validation for forecast accuracy

## Free Tier Compliance

- Bedrock API: <1000 requests/month (target: <500 with 80%+ cache hit rate)
- DynamoDB: Forecast cache ~50 MB storage (within 25 GB free tier)
- Lambda: Additional ~2,000 invocations/month (within 1M free tier)
- CloudWatch: Additional metrics and logs (within free tier)

## Property-Based Testing

Each correctness property from the design document must be implemented as a property-based test:

1. Property 1: Historical Data Validation
2. Property 2: Data Interpolation Completeness
3. Property 3: Forecast Length Consistency
4. Property 4: Confidence Interval Validity
5. Property 5: Non-Negative Cost Predictions
6. Property 6: Weekly Aggregation Consistency
7. Property 7: Service-Specific Data Filtering
8. Property 8: Total Forecast Aggregation
9. Property 9: Cache Key Uniqueness
10. Property 10: Cache TTL Enforcement
11. Property 11: Cache Invalidation Completeness
12. Property 12: Response Structure Completeness
13. Property 13: Forecast Data Point Structure
14. Property 14: Retry Logic for Rate Limiting
15. Property 15: Backward Compatibility
16. Property 16: Historical Data Limit
17. Property 17: Response Time for Cached Forecasts
18. Property 18: Bedrock Prompt Structure
19. Property 19: Error Response Structure
20. Property 20: Metrics Emission
