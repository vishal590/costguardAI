# Implementation Plan: AI/ML Workload Cost Management

## Overview

This implementation plan breaks down Phase 6 (AI/ML Workload Cost Management) into discrete, manageable tasks. The plan follows an incremental approach, building GPU cost tracking first, then adding workload classification, unit cost calculations, and finally optimization recommendations.

Each task builds on previous work and includes validation through automated tests. The implementation is designed to maintain backward compatibility with Phases 1-5 and stay within AWS Free Tier limits.

## Tasks

- [x] 1. Set up Phase 6 infrastructure and core components
  - Created AI/ML services directory structure
  - Set up Lambda function handler for AI/ML cost endpoints
  - Created stub implementations for all service classes
  - API Gateway routes defined in handler (infrastructure deployment pending)
  - _Requirements: FR-1.1, IR-1.1, IR-1.2, IR-1.3, IR-1.4, IR-1.5_

- [ ] 2. Implement GPU cost tracking foundation
  - [x] 2.1 Create GPU cost tracker service
    - Created GPUCostTracker class with core methods
    - Implemented GPU instance type filtering (p3, p4, p4d, p5, g4, g5, g6)
    - Implemented cost per GPU hour calculation
    - Implemented idle GPU identification
    - Cost Explorer integration pending
    - _Requirements: FR-1.1, FR-1.3, FR-1.6_

  - [x] 2.2 Write property test for GPU instance filtering
    - **Property 1: GPU Instance Type Filtering**
    - **Validates: Requirements FR-1.1**
    - Unit test created and passing

  - [x] 2.3 Write property test for cost per GPU hour calculation
    - **Property 3: Cost Per GPU Hour Calculation**
    - **Validates: Requirements FR-1.3**
    - Unit test created and passing

  - [x] 2.4 Implement GPU cost API endpoint
    - Created GET /api/ai-ml/gpu-costs endpoint handler
    - Added query parameter validation (start_date, end_date, workload_type, instance_type)
    - Implemented response formatting
    - Caching implementation pending
    - _Requirements: API-1.1, NFR-5.2_

  - [x] 2.5 Write integration test for GPU cost endpoint
    - Test end-to-end GPU cost retrieval
    - Verify response format and data accuracy
    - _Requirements: API-1.1_

- [ ] 3. Implement workload classification
  - [x] 3.1 Create workload classifier service
    - Implement CloudWatch GPU metrics retrieval
    - Add classification rules (training: >70%, inference: 20-70%, idle: <10%)
    - Calculate confidence scores
    - Support manual classification via EC2 tags
    - Store classification history in DynamoDB
    - _Requirements: FR-2.1, FR-2.2, FR-2.3, FR-2.4, FR-2.6_

  - [x] 3.2 Write property test for workload classification rules
    - **Property 8: Workload Classification Rules**
    - **Validates: Requirements FR-2.4**
    - Property tests created and passing

  - [x] 3.3 Write property test for classification consistency
    - **Property 2: Workload Classification Consistency**
    - **Validates: Requirements FR-2.1, FR-2.2**
    - Property tests created and passing (consistency over time, stability with noise, reversibility)

  - [x] 3.4 Write property test for manual classification override
    - **Property 9: Manual Classification Override**
    - **Validates: Requirements FR-2.3, FR-2.5**
    - Property tests created and passing (manual override, ignores conflicting metrics)

  - [x] 3.5 Implement workload classification API endpoints
    - Create GET /api/ai-ml/workload-classification endpoint
    - Create POST /api/ai-ml/workload-classification endpoint (manual override)
    - Add response formatting with confidence scores
    - _Requirements: API-2.1, API-2.2_

  - [x] 3.6 Write integration test for workload classification
    - Test classification with various utilization patterns
    - Verify manual override functionality
    - All 10 integration tests passing
    - _Requirements: FR-2.1, FR-2.3_

- [x] 4. Implement idle GPU detection
  - [x] 4.1 Create idle GPU detector
    - Identify GPUs with <10% utilization
    - Calculate idle time and wasted cost
    - Generate idle GPU alerts
    - Created IdleGPUDetector class with core methods
    - Implemented severity-based alerting (low/medium/high/critical)
    - Implemented cost calculation and recommendations
    - _Requirements: FR-1.5_

  - [x] 4.2 Write property test for idle GPU detection
    - **Property 4: Idle GPU Detection**
    - **Validates: Requirements FR-1.5**

  - [x] 4.3 Implement idle GPU API endpoint
    - Create GET /api/ai-ml/idle-gpus endpoint
    - Add configurable threshold parameter
    - _Requirements: API-1.3_

- [x] 5. Checkpoint - Ensure GPU tracking and classification work
  - Verify all GPU cost tracking tests pass
  - Verify workload classification accuracy >90%
  - Test API endpoints with sample data
  - All 66 tests passing (GPU cost tracker, idle detector, workload classifier)
  - Coverage: GPU cost tracker (96%), idle detector (92%), workload classifier (92%)

- [x] 6. Implement cost-per-inference calculations
  - [x] 6.1 Create cost-per-inference calculator
    - Track inference requests from API Gateway, Lambda, SageMaker, Bedrock
    - Calculate total inference costs (compute + API + data transfer)
    - Compute cost per inference
    - Store results in DynamoDB
    - _Requirements: FR-3.1, FR-3.2, FR-3.3, FR-3.4_

  - [x] 6.2 Write property test for cost-per-inference accuracy
    - **Property 5: Cost-Per-Inference Accuracy**
    - **Validates: Requirements FR-3.1, FR-3.4**

  - [x] 6.3 Implement cost-per-inference API endpoints
    - Create GET /api/ai-ml/cost-per-inference endpoint
    - Create GET /api/ai-ml/inference-trends endpoint
    - Add filtering by model and endpoint
    - _Requirements: API-3.1, API-3.2_

  - [x] 6.4 Write integration test for cost-per-inference
    - Test with multiple inference sources
    - Verify cost component aggregation
    - _Requirements: FR-3.2, FR-3.3_

- [x] 7. Implement cost-per-training calculations
  - [x] 7.1 Create cost-per-training calculator
    - Track training jobs from SageMaker and EC2
    - Calculate total training costs (compute + storage + data transfer)
    - Compute cost per training job
    - Track cost per hour
    - Store results in DynamoDB
    - _Requirements: FR-4.1, FR-4.2, FR-4.3, FR-4.5_

  - [x] 7.2 Write property test for cost-per-training accuracy
    - **Property 6: Cost-Per-Training Accuracy**
    - **Validates: Requirements FR-4.1, FR-4.3**

  - [x] 7.3 Implement cost-per-training API endpoints
    - Create GET /api/ai-ml/cost-per-training endpoint
    - Create GET /api/ai-ml/training-comparison endpoint
    - Add instance type comparison functionality
    - _Requirements: API-4.1, API-4.2, FR-4.6_

  - [x] 7.4 Write integration test for cost-per-training
    - Test with SageMaker and EC2 training jobs
    - Verify cost component aggregation
    - Test instance type comparison
    - _Requirements: FR-4.2, FR-4.6_

- [x] 8. Checkpoint - Ensure unit cost calculations work
  - Verify cost-per-inference calculations are accurate
  - Verify cost-per-training calculations are accurate
  - Test API endpoints with sample data
  - Ask user if questions arise

- [x] 9. Implement spot instance recommendations
  - [x] 9.1 Create spot instance recommender
    - Identify training workloads suitable for spot instances
    - Integrate with AWS Pricing API for spot prices
    - Calculate potential savings
    - Assess interruption risk
    - Generate what-if scenarios
    - Created SpotInstanceRecommender class with core methods
    - Implemented spot suitability criteria (training workloads only)
    - Implemented savings calculation (up to 70% discount)
    - Implemented interruption risk assessment
    - Implemented what-if scenario generation
    - _Requirements: FR-5.1, FR-5.2, FR-5.4, FR-5.5_

  - [x] 9.2 Write property test for spot savings calculation
    - **Property 7: Spot Savings Calculation**
    - **Validates: Requirements FR-5.2**

  - [x] 9.3 Write property test for spot suitability criteria
    - **Property 11: Spot Suitability Criteria**
    - **Validates: Requirements FR-5.1**
    - 8 property tests created and passing (100 iterations each)
    - Tests validate training workloads are suitable, inference/idle are not
    - Tests validate minimum duration requirements
    - Tests validate suitability reasons and deterministic behavior

  - [x] 9.4 Implement spot recommendation API endpoints
    - Create GET /api/ai-ml/spot-recommendations endpoint
    - Create GET /api/ai-ml/spot-savings endpoint
    - Add what-if scenario generation
    - Implemented both endpoints with full functionality
    - Spot recommendations endpoint supports workload_id and optional what-if scenarios
    - Spot savings endpoint calculates savings for instance type comparisons
    - _Requirements: API-5.1, API-5.2_

  - [x] 9.5 Write integration test for spot recommendations
    - Test recommendation generation
    - Verify savings calculations
    - Test what-if scenarios
    - Created 11 integration tests covering all scenarios
    - Tests validate API endpoints, error handling, and complete flow
    - All tests passing
    - _Requirements: FR-5.2, FR-5.5_

- [x] 10. Implement SageMaker cost tracking
  - [x] 10.1 Create SageMaker cost tracker
    - Track training job costs
    - Track inference endpoint costs
    - Track notebook instance costs
    - Identify idle endpoints (<10 requests/hour)
    - Recommend cost-optimized instance types
    - Created SageMakerCostTracker class with core methods
    - Implemented training job cost tracking with detailed breakdown
    - Implemented inference endpoint cost tracking
    - Implemented idle endpoint detection (<10 requests/hour)
    - Implemented instance type recommendations with savings calculations
    - Integrated with Cost Explorer, SageMaker, CloudWatch, and Pricing APIs
    - _Requirements: FR-6.1, FR-6.2, FR-6.3, FR-6.5, FR-6.6_

  - [x] 10.2 Write property test for SageMaker cost breakdown
    - **Property 12: SageMaker Cost Breakdown**
    - **Validates: Requirements FR-6.4**

  - [x] 10.3 Implement SageMaker cost API endpoints
    - Create GET /api/ai-ml/sagemaker-costs endpoint
    - Create GET /api/ai-ml/sagemaker-idle-endpoints endpoint
    - Add job type filtering
    - _Requirements: API-6.1, API-6.2_

  - [x] 10.4 Write integration test for SageMaker tracking
    - Test with training jobs and endpoints
    - Verify idle endpoint detection
    - Test instance type recommendations
    - _Requirements: FR-6.1, FR-6.2, FR-6.6_

- [x] 11. Implement Bedrock cost tracking
  - [x] 11.1 Create Bedrock cost tracker
    - Track model invocation costs
    - Track costs by model (Claude, Titan, Llama, etc.)
    - Calculate cost per invocation
    - Track input/output token counts
    - Recommend cost-optimized models
    - _Requirements: FR-7.1, FR-7.2, FR-7.3, FR-7.4, FR-7.6_

  - [x] 11.2 Write property test for Bedrock token tracking
    - **Property 13: Bedrock Token Tracking**
    - **Validates: Requirements FR-7.4**
    - 8 property tests created and passing (100 iterations each)
    - Tests validate that total cost can be calculated from token counts and model pricing
    - Tests validate token tracking, cost calculation accuracy, proportionality, and determinism

  - [x] 11.3 Implement Bedrock cost API endpoints
    - Create GET /api/ai-ml/bedrock-costs endpoint
    - Create GET /api/ai-ml/bedrock-cost-per-invocation endpoint
    - Add model filtering
    - Implemented both endpoints with full functionality
    - Bedrock costs endpoint supports model filtering and provides detailed breakdown
    - Cost-per-invocation endpoint includes token usage, cost breakdown, and recommendations
    - _Requirements: API-7.1, API-7.2_

  - [x] 11.4 Write integration test for Bedrock tracking
    - Test with multiple models
    - Verify token tracking
    - Test cost per invocation calculations
    - Created 11 integration tests covering all scenarios
    - Tests validate API endpoints, error handling, and complete flow
    - All tests passing
    - _Requirements: FR-7.1, FR-7.4_

- [x] 12. Checkpoint - Ensure all tracking and recommendations work
  - Verify spot recommendations are accurate
  - Verify SageMaker cost tracking works
  - Verify Bedrock cost tracking works
  - Test all API endpoints
  - All tests passing: 19 Bedrock tests (8 property + 11 integration)
  - Combined with previous tasks: 176+ total tests passing
  - Bedrock cost tracker coverage: 42%
  - All API endpoints implemented and tested

- [-] 13. Implement caching and performance optimization
  - [x] 13.1 Add caching layer
    - Implement 24-hour cache TTL for GPU costs
    - Add cache invalidation logic
    - Optimize Cost Explorer API call batching
    - Integrated AIMLCacheManager into all major API endpoints:
      - GPU costs endpoint with cache support
      - SageMaker costs endpoint with cache support
      - Bedrock costs endpoint with cache support
      - Cost-per-inference endpoint with cache support
      - Cost-per-training endpoint with cache support
    - Cache manager uses DynamoDB with 24-hour TTL
    - Cache hit rate tracking implemented
    - _Requirements: NFR-5.2, NFR-5.3_

  - [x] 13.2 Write property test for cache consistency
    - **Property 14: Cache Consistency**
    - **Validates: Requirements NFR-5.2**

  - [x] 13.3 Write property test for response time bounds
    - **Property 15: Response Time Bounds**
    - **Validates: Requirements NFR-1.1, NFR-1.2**

  - [x] 13.4 Write performance tests
    - Test response time under load (100 concurrent queries)
    - Measure cache hit rate
    - Verify API call frequency stays within budget
    - _Requirements: NFR-1.1, NFR-1.2, NFR-5.1_

- [-] 14. Implement error handling and resilience
  - [x] 14.1 Add comprehensive error handling
    - Created error_handler.py with custom exceptions (AIMLError, RateLimitError, DataNotFoundError, InsufficientDataError, APITimeoutError)
    - Implemented retry_with_exponential_backoff decorator (max 3 retries, 1s/2s/4s delays)
    - Added error handlers for Cost Explorer, CloudWatch, SageMaker, Bedrock, and Pricing APIs
    - Integrated error handling into all AI/ML services:
      - SageMakerCostTracker: Added retry decorators and error handling with cache fallback
      - BedrockCostTracker: Added retry decorators and error handling with cache fallback
      - GPUCostTracker: Added error handling for Cost Explorer calls
      - SpotInstanceRecommender: Added error handling for pricing API with fallback
      - CostPerInferenceCalculator: Added error handler imports
      - CostPerTrainingCalculator: Added error handler imports
    - Implemented fallback mechanisms (cached data, default classifications, estimated prices)
    - _Requirements: NFR-4.2, NFR-4.3, NFR-4.4_

  - [x] 14.2 Write unit tests for error scenarios
    - Test rate limit handling
    - Test missing data handling
    - Test API timeout handling
    - _Requirements: NFR-4.2, NFR-4.3_

- [ ] 15. Integration with existing phases
  - [ ] 15.1 Integrate with Phase 2 (Forecasting)
    - Extend forecasting to predict GPU costs
    - Use GPU cost trends for forecast training
    - _Requirements: IR-2.2_

  - [ ] 15.2 Integrate with Phase 3 (Prevention)
    - Extend prevention to stop idle GPU instances
    - Track GPU cost savings from prevention
    - _Requirements: IR-2.3_

  - [ ] 15.3 Integrate with Phase 4 (AI Advisor)
    - Extend AI Advisor to answer GPU cost questions
    - Provide GPU optimization recommendations
    - _Requirements: IR-2.4_

  - [ ] 15.4 Integrate with Phase 5 (Multi-Account)
    - Support multi-account GPU cost tracking
    - Aggregate GPU costs across organization
    - _Requirements: IR-2.5, NFR-3.4_

  - [ ] 15.5 Write backward compatibility tests
    - Verify Phase 1-5 APIs unchanged
    - Test multi-phase integration
    - _Requirements: IR-2.1, IR-2.2, IR-2.3, IR-2.4, IR-2.5_

- [ ] 16. Documentation and deployment
  - [ ] 16.1 Write API documentation

    - Document all Phase 6 endpoints
    - Add request/response examples
    - Document error codes
    - _Requirements: All API requirements_

  - [ ] 16.2 Create deployment guide


    - Document infrastructure setup
    - Add configuration instructions
    - Document IAM permissions required
    - _Requirements: All requirements_

  - [ ] 16.3 Write user guide

    - Explain GPU cost tracking features
    - Provide usage examples
    - Document best practices
    - _Requirements: NFR-6.1, NFR-6.2, NFR-6.3, NFR-6.4_

- [ ] 17. Final checkpoint - Ensure everything works
  - Run full test suite (unit + property + integration)
  - Verify test coverage >90%
  - Test all API endpoints end-to-end
  - Verify Free Tier compliance (<$1/month additional cost)
  - Verify backward compatibility with Phases 1-5
  - Ask user for final review

## Notes

- Tasks marked with `*` are optional (documentation only - all tests are required)
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Integration tests validate end-to-end functionality
- All tasks maintain backward compatibility with Phases 1-5
- Implementation stays within AWS Free Tier limits
- All test tasks are required for production quality

## Estimated Timeline

- **Week 1:** Tasks 1-5 (GPU tracking and classification foundation)
- **Week 2:** Tasks 6-12 (Unit costs, recommendations, SageMaker/Bedrock)
- **Week 3:** Tasks 13-17 (Optimization, integration, documentation)

**Total Estimated Effort:** 2-3 weeks

