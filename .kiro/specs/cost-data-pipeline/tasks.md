# Implementation Plan: Cost Data Pipeline

## Overview

This implementation plan breaks down the Cost Data Pipeline into discrete, incremental tasks. Each task builds on previous work and includes testing to validate functionality early. The implementation uses Python 3.11 with boto3 AWS SDK, following the architecture and design specified in design.md.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create project directory with Python virtual environment
  - Install dependencies: boto3, pytest, hypothesis, moto (for AWS mocking), pytest-cov
  - Create requirements.txt file
  - Set up pytest configuration (pytest.ini or pyproject.toml)
  - Create directory structure: src/, src/services/, src/utils/, tests/unit/, tests/integration/
  - Create __init__.py files in all directories
  - _Requirements: All requirements (foundation)_

- [x] 2. Implement utility functions and types
  - [x] 2.1 Create Python type definitions and data classes
    - Define dataclasses for CostRecord, DynamoDBRecord, QueryParams, ErrorResponse
    - Define type aliases for Granularity, ErrorCode
    - Create RetryConfig dataclass
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 2.2 Implement date validation utilities
    - Write validate_date_format function (YYYY-MM-DD regex)
    - Write validate_date_range function (start <= end)
    - Write format_date_for_api function (date to YYYY-MM-DD)
    - Write calculate_default_date_range function (12 months ago to today)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.3 Write property tests for date validation
    - **Property 1: Date validation rejects invalid formats**
    - **Property 2: Date range validation rejects invalid ranges**
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x] 2.4 Implement granularity validation
    - Write validate_granularity function (DAILY | MONTHLY | HOURLY)
    - _Requirements: 2.4, 2.5_

  - [x] 2.5 Write property tests for granularity validation
    - **Property 3: Granularity validation accepts only valid values**
    - **Validates: Requirements 2.4, 2.5**

  - [x] 2.6 Implement helper utilities
    - Write calculate_ttl function (days to Unix timestamp)
    - Write normalize_service_name function (lowercase, replace spaces)
    - Write calculate_cost_summary function (sum costs, count services/records)
    - _Requirements: 3.1, 12.1, 12.2, 12.3, 12.5_

  - [x] 2.7 Write unit tests for helper utilities
    - Test calculate_ttl with various day values
    - Test normalize_service_name with various service names
    - Test calculate_cost_summary with various cost datasets
    - _Requirements: 12.1, 12.2, 12.3, 12.5_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement error handler with retry logic
  - [x] 4.1 Create error handler module
    - Write format_error function (Exception to ErrorResponse)
    - Write is_retryable_error function (check error codes)
    - Write calculate_backoff_delay function (exponential backoff with jitter)
    - Write with_retry decorator/function (generic retry wrapper with exponential backoff)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3_

  - [x] 4.2 Write property tests for retry logic
    - **Property 7: Retryable errors trigger exponential backoff**
    - **Property 8: Non-retryable errors return immediately**
    - **Property 9: Retry exhaustion returns detailed error**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3**

  - [x] 4.3 Write unit tests for error handler
    - Test format_error with various exception types
    - Test is_retryable_error with 429, 503, 400, 403 errors
    - Test calculate_backoff_delay produces increasing delays
    - Test with_retry attempts correct number of retries
    - _Requirements: 4.1, 4.2, 4.5, 4.6_

- [x] 5. Implement Cost Explorer service
  - [x] 5.1 Create Cost Explorer service module
    - Initialize Cost Explorer client using boto3.client('ce')
    - Write fetch_cost_data function with pagination handling
    - Implement Cost Explorer API call with correct parameters (TimePeriod, Granularity, Metrics, GroupBy)
    - Handle NextPageToken for pagination
    - Transform API response to CostRecord list
    - Integrate with_retry for error handling
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 4.1, 4.2_

  - [x] 5.2 Write property tests for Cost Explorer service
    - **Property 4: Cost Explorer pagination fetches all pages**
    - **Property 22: Cost Explorer API calls include correct parameters**
    - **Validates: Requirements 1.1, 1.3, 1.4, 1.5**

  - [x] 5.3 Write unit tests for Cost Explorer service
    - Test fetch_cost_data with mocked single-page response
    - Test fetch_cost_data with mocked multi-page response (3 pages)
    - Test fetch_cost_data with mocked empty response
    - Test fetch_cost_data with mocked rate limit error (429)
    - Test fetch_cost_data with mocked service unavailable error (503)
    - Test API call parameters include correct GroupBy and Metrics
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 4.1, 4.2_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement DynamoDB service
  - [x] 7.1 Create DynamoDB service module
    - Initialize DynamoDB resource using boto3.resource('dynamodb')
    - Write transform_to_dynamodb_record function (CostRecord to DynamoDBRecord)
    - Write store_cost_data function with batch write operations
    - Implement batch splitting (25 items per batch)
    - Handle unprocessed items and retry
    - Implement conditional writes for upsert behavior (put_item with ConditionExpression)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 5.4, 11.1, 11.2, 11.3, 11.4_

  - [x] 7.2 Write property tests for DynamoDB service
    - **Property 5: Cost data transformation produces valid DynamoDB records**
    - **Property 6: Batch write operations handle partial failures**
    - **Property 17: Duplicate records trigger upsert behavior**
    - **Property 18: Conditional writes prevent race conditions**
    - **Property 23: Batch operations split oversized batches**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6, 5.4, 11.1, 11.2, 11.3, 11.4**

  - [x] 7.3 Implement query functionality
    - Write query_cost_data function with filter support
    - Implement efficient Query operations (not Scan)
    - Support filtering by start_date, end_date, service, limit
    - Default limit to 100 records
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 7.4 Write property tests for query functionality
    - **Property 10: Query operations support all filter combinations**
    - **Property 11: Query operations use efficient DynamoDB access patterns**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.6**

  - [x] 7.5 Write unit tests for DynamoDB service
    - Test transform_to_dynamodb_record produces correct pk and sk formats
    - Test store_cost_data with < 25 items (single batch)
    - Test store_cost_data with > 25 items (multiple batches)
    - Test store_cost_data with mocked partial failure
    - Test store_cost_data with mocked throttling error
    - Test query_cost_data with various filter combinations
    - Test query_cost_data uses Query operation (not Scan)
    - Test upsert behavior (storing duplicate records)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 7.1, 7.2, 7.3, 7.4, 7.6, 11.1, 11.2_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement Lambda handler
  - [x] 9.1 Create main Lambda handler
    - Write handler function that parses LambdaEvent
    - Implement routing logic (POST /fetch vs GET /query)
    - Parse and validate input parameters
    - Call appropriate service functions
    - Format responses (success and error)
    - Implement CloudWatch logging at key points
    - _Requirements: 1.1, 1.2, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 9.2 Write property tests for Lambda handler
    - **Property 12: Successful fetch responses contain complete summaries**
    - **Property 13: Successful query responses contain cost records**
    - **Property 14: Error responses contain structured error information**
    - **Property 15: Cost records in responses contain all required fields**
    - **Property 16: All operations log key execution points**
    - **Property 19: Cost summaries calculate correct totals**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 12.1, 12.2, 12.3, 12.5**

  - [x] 9.3 Write unit tests for Lambda handler
    - Test handler with POST /fetch request (valid parameters)
    - Test handler with POST /fetch request (no parameters, uses defaults)
    - Test handler with GET /query request (with filters)
    - Test handler with GET /query request (no filters, uses defaults)
    - Test handler with invalid date format (returns 400)
    - Test handler with invalid date range (returns 400)
    - Test handler with invalid granularity (returns 400)
    - Test response format for successful fetch
    - Test response format for successful query
    - Test response format for errors
    - Test CloudWatch logging occurs at key points
    - _Requirements: 1.2, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.6_

- [x] 10. Create infrastructure configuration
  - [x] 10.1 Create DynamoDB table definition
    - Write AWS CDK (Python) or CloudFormation template for DynamoDB table
    - Configure table name: costguard-cost-data
    - Set partition key: pk (String)
    - Set sort key: sk (String)
    - Configure on-demand billing mode
    - Enable TTL on ttl attribute (optional)
    - _Requirements: 3.2, 3.3, 10.3_

  - [x] 10.2 Create Lambda function configuration
    - Write AWS CDK (Python) or CloudFormation template for Lambda function
    - Configure runtime: Python 3.11
    - Configure memory: 256 MB
    - Configure timeout: 30 seconds
    - Set environment variables (DynamoDB table name)
    - Package Lambda deployment with dependencies (boto3 is included by default)
    - _Requirements: 10.1, 10.2_

  - [x] 10.3 Create IAM role and policies
    - Write IAM role for Lambda execution
    - Attach policy for Cost Explorer read access (ce:GetCostAndUsage, ce:GetDimensionValues)
    - Attach policy for DynamoDB read/write access (dynamodb:PutItem, dynamodb:GetItem, dynamodb:Query, dynamodb:BatchWriteItem)
    - Attach policy for CloudWatch Logs (logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents)
    - _Requirements: 1.1, 3.5, 7.6, 9.1_

  - [x] 10.4 Create API Gateway configuration
    - Write AWS CDK (Python) or CloudFormation template for API Gateway
    - Create REST API
    - Create POST /api/cost-data/fetch endpoint
    - Create GET /api/cost-data endpoint
    - Configure Lambda integration
    - Configure API key authentication
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Create deployment scripts and documentation
  - [x] 12.1 Create deployment script
    - Write script to create Python virtual environment
    - Write script to install dependencies (pip install -r requirements.txt)
    - Write script to package Lambda function (zip with dependencies)
    - Write script to deploy infrastructure (CDK deploy or CloudFormation)
    - Write script to create API key
    - _Requirements: All requirements (deployment)_

  - [x] 12.2 Create README documentation
    - Document project structure
    - Document setup instructions (python -m venv, pip install, configure AWS credentials)
    - Document deployment instructions (run deployment script)
    - Document API usage examples (curl commands for both endpoints)
    - Document testing instructions (pytest)
    - Document environment variables
    - _Requirements: All requirements (documentation)_

  - [x] 12.3 Create example requests and responses
    - Create example POST /fetch request with various parameters
    - Create example GET /query request with various filters
    - Document expected responses for success and error cases
    - _Requirements: 6.1, 6.2, 8.1, 8.2, 8.3, 8.4_

- [x] 13. Integration testing
  - [x] 13.1 Write end-to-end fetch test
    - Deploy to AWS (or use local mocks)
    - Send POST request to /api/cost-data/fetch
    - Verify data is stored in DynamoDB
    - Verify response contains correct summary
    - _Requirements: 1.1, 3.5, 6.1, 8.1, 8.2_

  - [x] 13.2 Write end-to-end query test
    - Store test data in DynamoDB
    - Send GET request to /api/cost-data with filters
    - Verify response contains filtered data
    - _Requirements: 6.2, 7.1, 7.2, 7.3, 7.4, 8.3_

  - [x] 13.3 Write authentication tests
    - Test request without API key (should return 401)
    - Test request with invalid API key (should return 401)
    - Test request with valid API key (should succeed)
    - _Requirements: 6.3, 6.4_

  - [x] 13.4 Write property tests for API Gateway integration
    - **Property 20: API Gateway enforces authentication**
    - **Property 21: API Gateway returns appropriate status codes**
    - **Validates: Requirements 6.3, 6.4, 6.5, 6.6**

- [x] 14. Final checkpoint - Ensure all tests pass
  - Run all unit tests
  - Run all property-based tests
  - Run all integration tests
  - Verify test coverage is above 80%
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- All boto3 calls should be mocked in unit tests using moto or unittest.mock
- Use DynamoDB Local or moto for integration tests to avoid AWS charges during development
- boto3 is included in Lambda runtime by default, but other dependencies need to be packaged
