# Requirements Document

## Introduction

This document specifies the requirements for Phase 1 of CostGuard AI: the Core Cost Data Pipeline. This system will fetch historical AWS cost data from the Cost Explorer API, store it in DynamoDB for fast retrieval, and expose it via API Gateway REST endpoints. The system must operate within AWS Free Tier limits and implement robust error handling for production use.

## Glossary

- **Cost_Explorer_API**: AWS service that provides programmatic access to AWS cost and usage data
- **Lambda_Function**: AWS serverless compute service that runs code in response to events
- **DynamoDB**: AWS NoSQL database service for storing structured data
- **API_Gateway**: AWS service for creating, publishing, and managing REST APIs
- **Cost_Data**: Historical AWS spending information grouped by service and time period
- **Granularity**: Time interval for cost data aggregation (DAILY, MONTHLY, HOURLY)
- **Blended_Cost**: AWS cost metric that averages costs across accounts
- **Unblended_Cost**: AWS cost metric showing actual costs without averaging
- **Batch_Write**: DynamoDB operation that writes multiple items in a single request
- **Exponential_Backoff**: Retry strategy that increases wait time between retries
- **Free_Tier**: AWS usage limits that incur no charges

## Requirements

### Requirement 1: Fetch Historical Cost Data

**User Story:** As a system administrator, I want to fetch historical AWS cost data from the Cost Explorer API, so that I can analyze spending patterns and trends.

#### Acceptance Criteria

1. WHEN the Lambda_Function receives a fetch request, THE Lambda_Function SHALL retrieve cost data from the Cost_Explorer_API for the specified date range
2. WHEN no date range is provided, THE Lambda_Function SHALL default to fetching the last 12 months of cost data
3. WHEN fetching cost data, THE Lambda_Function SHALL group results by AWS service using the SERVICE dimension
4. WHEN fetching cost data, THE Lambda_Function SHALL retrieve both Blended_Cost and Unblended_Cost metrics
5. WHEN the Cost_Explorer_API returns paginated results, THE Lambda_Function SHALL fetch all pages until the complete dataset is retrieved
6. WHEN using Granularity parameter, THE Lambda_Function SHALL default to MONTHLY if not specified

### Requirement 2: Validate Input Parameters

**User Story:** As a developer, I want input parameters to be validated before processing, so that invalid requests fail fast with clear error messages.

#### Acceptance Criteria

1. WHEN a date parameter is provided, THE Lambda_Function SHALL validate it matches YYYY-MM-DD format
2. WHEN an invalid date format is provided, THE Lambda_Function SHALL return a 400 error with a descriptive message
3. WHEN the start date is after the end date, THE Lambda_Function SHALL return a 400 error
4. WHEN the Granularity parameter is provided, THE Lambda_Function SHALL validate it is one of DAILY, MONTHLY, or HOURLY
5. WHEN an invalid Granularity value is provided, THE Lambda_Function SHALL return a 400 error

### Requirement 3: Store Cost Data in DynamoDB

**User Story:** As a system, I want to store fetched cost data in DynamoDB, so that it can be quickly retrieved without repeated API calls to Cost Explorer.

#### Acceptance Criteria

1. WHEN cost data is fetched, THE Lambda_Function SHALL transform it into DynamoDB-compatible format
2. WHEN storing cost data, THE Lambda_Function SHALL use partition key format "COST#YYYY-MM"
3. WHEN storing cost data, THE Lambda_Function SHALL use sort key format "SERVICE#service-name"
4. WHEN storing cost data, THE Lambda_Function SHALL include date, service, blendedCost, unblendedCost, currency, unit, and timestamp fields
5. WHEN storing multiple cost records, THE Lambda_Function SHALL use DynamoDB Batch_Write operations for efficiency
6. WHEN a Batch_Write operation partially fails, THE Lambda_Function SHALL retry the failed items

### Requirement 4: Handle Cost Explorer API Errors

**User Story:** As a system operator, I want the system to handle Cost Explorer API errors gracefully, so that temporary failures do not cause data loss or system crashes.

#### Acceptance Criteria

1. WHEN the Cost_Explorer_API returns a rate limit error (429), THE Lambda_Function SHALL retry the request using Exponential_Backoff
2. WHEN the Cost_Explorer_API returns a service unavailable error (503), THE Lambda_Function SHALL retry the request using Exponential_Backoff
3. WHEN the Cost_Explorer_API returns an access denied error (403), THE Lambda_Function SHALL log the error and return a 403 response
4. WHEN the Cost_Explorer_API returns an invalid parameter error (400), THE Lambda_Function SHALL log the error and return a 400 response
5. WHEN retrying a failed request, THE Lambda_Function SHALL attempt a maximum of 3 retries before failing
6. WHEN all retries are exhausted, THE Lambda_Function SHALL return an error response with details about the failure

### Requirement 5: Handle DynamoDB Errors

**User Story:** As a system operator, I want the system to handle DynamoDB errors gracefully, so that temporary database issues do not cause data loss.

#### Acceptance Criteria

1. WHEN DynamoDB returns a throttling error, THE Lambda_Function SHALL retry the operation using Exponential_Backoff
2. WHEN DynamoDB returns a validation error, THE Lambda_Function SHALL log the error and return a 400 response
3. WHEN a DynamoDB operation fails after maximum retries, THE Lambda_Function SHALL return an error response with details
4. WHEN a Batch_Write operation exceeds item size limits, THE Lambda_Function SHALL split the batch into smaller chunks

### Requirement 6: Expose Data via API Gateway

**User Story:** As a frontend developer, I want to access cost data through REST API endpoints, so that I can display cost information in the user interface.

#### Acceptance Criteria

1. WHEN a POST request is made to /api/cost-data/fetch, THE API_Gateway SHALL invoke the Lambda_Function to fetch and store cost data
2. WHEN a GET request is made to /api/cost-data, THE API_Gateway SHALL invoke the Lambda_Function to retrieve stored cost data
3. WHEN accessing any endpoint, THE API_Gateway SHALL require a valid API key for authentication
4. WHEN an invalid API key is provided, THE API_Gateway SHALL return a 401 error
5. WHEN a request is successful, THE API_Gateway SHALL return a 200 status code with the response body
6. WHEN a request fails, THE API_Gateway SHALL return an appropriate error status code (400, 401, 403, 500)

### Requirement 7: Query Stored Cost Data

**User Story:** As a frontend developer, I want to query stored cost data with filters, so that I can display specific cost information based on user selections.

#### Acceptance Criteria

1. WHEN querying cost data, THE Lambda_Function SHALL support filtering by start date
2. WHEN querying cost data, THE Lambda_Function SHALL support filtering by end date
3. WHEN querying cost data, THE Lambda_Function SHALL support filtering by service name
4. WHEN querying cost data, THE Lambda_Function SHALL support limiting the number of results returned
5. WHEN no limit is specified, THE Lambda_Function SHALL default to returning a maximum of 100 records
6. WHEN querying DynamoDB, THE Lambda_Function SHALL use the partition key and sort key for efficient queries

### Requirement 8: Return Structured Responses

**User Story:** As a frontend developer, I want API responses to follow a consistent structure, so that I can reliably parse and display the data.

#### Acceptance Criteria

1. WHEN a fetch operation succeeds, THE Lambda_Function SHALL return a response containing success status, message, and data summary
2. WHEN a fetch operation succeeds, THE data summary SHALL include recordsProcessed, dateRange, totalCost, and services list
3. WHEN a query operation succeeds, THE Lambda_Function SHALL return a response containing success status and an array of cost records
4. WHEN any operation fails, THE Lambda_Function SHALL return a response containing success status false and an error object
5. WHEN an error occurs, THE error object SHALL include code, message, and details fields
6. WHEN returning cost data, THE Lambda_Function SHALL include date, service, blendedCost, unblendedCost, and currency for each record

### Requirement 9: Implement CloudWatch Logging

**User Story:** As a system operator, I want all operations to be logged to CloudWatch, so that I can troubleshoot issues and monitor system health.

#### Acceptance Criteria

1. WHEN the Lambda_Function starts execution, THE Lambda_Function SHALL log the incoming event parameters
2. WHEN calling the Cost_Explorer_API, THE Lambda_Function SHALL log the request parameters
3. WHEN an error occurs, THE Lambda_Function SHALL log the error with full context including stack trace
4. WHEN storing data in DynamoDB, THE Lambda_Function SHALL log the number of records being written
5. WHEN a retry occurs, THE Lambda_Function SHALL log the retry attempt number and reason
6. WHEN the Lambda_Function completes, THE Lambda_Function SHALL log the execution summary

### Requirement 10: Comply with AWS Free Tier Limits

**User Story:** As a cost-conscious developer, I want the system to operate within AWS Free Tier limits, so that I can run the system without incurring charges.

#### Acceptance Criteria

1. WHEN configuring the Lambda_Function, THE Lambda_Function SHALL use a maximum of 256 MB memory allocation
2. WHEN configuring the Lambda_Function, THE Lambda_Function SHALL use a maximum timeout of 30 seconds
3. WHEN storing data in DynamoDB, THE DynamoDB SHALL use on-demand billing mode to avoid capacity planning
4. WHEN creating the DynamoDB table, THE DynamoDB SHALL not exceed 25 GB of storage
5. WHEN making API calls, THE system SHALL target fewer than 1 million Lambda invocations per month
6. WHEN making API calls, THE system SHALL target fewer than 1 million API Gateway requests per month

### Requirement 11: Prevent Duplicate Data Storage

**User Story:** As a system operator, I want to prevent duplicate cost records from being stored, so that storage space is used efficiently and data remains accurate.

#### Acceptance Criteria

1. WHEN storing cost data, THE Lambda_Function SHALL check if a record with the same partition key and sort key already exists
2. WHEN a duplicate record is detected, THE Lambda_Function SHALL update the existing record instead of creating a new one
3. WHEN updating an existing record, THE Lambda_Function SHALL update the timestamp field to reflect the latest fetch time
4. WHEN storing cost data, THE Lambda_Function SHALL use DynamoDB conditional writes to prevent race conditions

### Requirement 12: Calculate and Return Cost Summaries

**User Story:** As a frontend developer, I want to receive cost summaries in the API response, so that I can display aggregate information without additional calculations.

#### Acceptance Criteria

1. WHEN fetching cost data, THE Lambda_Function SHALL calculate the total cost across all services
2. WHEN fetching cost data, THE Lambda_Function SHALL count the number of unique services
3. WHEN fetching cost data, THE Lambda_Function SHALL count the total number of records processed
4. WHEN returning a fetch response, THE Lambda_Function SHALL include these calculated summaries in the response
5. WHEN calculating totals, THE Lambda_Function SHALL use Blended_Cost as the default cost metric
