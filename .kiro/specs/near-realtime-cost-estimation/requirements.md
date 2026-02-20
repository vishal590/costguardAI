# Requirements Document: Near-Real-Time Cost Estimation

## Introduction

Phase 1.5 extends the Cost Data Pipeline (Phase 1) by adding near-real-time cost estimation capabilities. While Phase 1 provides historical cost data from AWS Cost Explorer (with 24-hour delay), Phase 1.5 estimates current costs by collecting CloudWatch metrics and applying pricing calculations. This enables users to see their AWS spending as it happens, not just after the fact.

## Glossary

- **System**: The Near-Real-Time Cost Estimation service
- **CloudWatch_Metrics_Collector**: Component that fetches metrics from CloudWatch
- **Cost_Estimator**: Component that calculates estimated costs from metrics
- **Metrics_Store**: DynamoDB table storing collected metrics
- **Estimation_API**: API Gateway endpoints for cost estimation queries
- **Supported_Service**: AWS service with cost estimation support (EC2, Lambda, DynamoDB, S3, RDS)
- **Metric_Period**: Time window for metric aggregation (1 minute, 5 minutes, 1 hour)
- **Pricing_Data**: AWS service pricing information
- **Estimation_Accuracy**: Percentage accuracy of cost estimates compared to actual costs

## Requirements

### Requirement 1: CloudWatch Metrics Collection

**User Story:** As a developer, I want to collect CloudWatch metrics from my AWS services, so that I can estimate current costs based on actual usage.

#### Acceptance Criteria

1. WHEN the System collects metrics, THE CloudWatch_Metrics_Collector SHALL fetch metrics for all Supported_Services
2. WHEN collecting EC2 metrics, THE CloudWatch_Metrics_Collector SHALL retrieve CPUUtilization, NetworkIn, NetworkOut, and DiskReadBytes metrics
3. WHEN collecting Lambda metrics, THE CloudWatch_Metrics_Collector SHALL retrieve Invocations, Duration, and Errors metrics
4. WHEN collecting DynamoDB metrics, THE CloudWatch_Metrics_Collector SHALL retrieve ConsumedReadCapacityUnits and ConsumedWriteCapacityUnits metrics
5. WHEN collecting S3 metrics, THE CloudWatch_Metrics_Collector SHALL retrieve NumberOfObjects and BucketSizeBytes metrics
6. WHEN collecting RDS metrics, THE CloudWatch_Metrics_Collector SHALL retrieve DatabaseConnections, ReadIOPS, and WriteIOPS metrics
7. WHEN metrics are collected, THE System SHALL store them in the Metrics_Store with timestamps
8. WHEN collecting metrics, THE System SHALL use efficient CloudWatch API calls to minimize costs

### Requirement 2: Cost Estimation Algorithms

**User Story:** As a developer, I want accurate cost estimates based on current usage, so that I can understand my spending in near-real-time.

#### Acceptance Criteria

1. WHEN estimating EC2 costs, THE Cost_Estimator SHALL calculate costs based on instance type, running hours, and data transfer
2. WHEN estimating Lambda costs, THE Cost_Estimator SHALL calculate costs based on invocations, duration, and memory allocation
3. WHEN estimating DynamoDB costs, THE Cost_Estimator SHALL calculate costs based on read/write capacity units consumed
4. WHEN estimating S3 costs, THE Cost_Estimator SHALL calculate costs based on storage size and request counts
5. WHEN estimating RDS costs, THE Cost_Estimator SHALL calculate costs based on instance type, running hours, and storage
6. WHEN calculating costs, THE Cost_Estimator SHALL use current AWS pricing data for the configured region
7. WHEN pricing data is unavailable, THE System SHALL return an error indicating missing pricing information
8. WHEN estimates are generated, THE System SHALL include confidence intervals or accuracy indicators

### Requirement 3: Pricing Data Management

**User Story:** As a system administrator, I want up-to-date AWS pricing data, so that cost estimates are accurate.

#### Acceptance Criteria

1. THE System SHALL store Pricing_Data in DynamoDB for fast retrieval
2. WHEN Pricing_Data is older than 24 hours, THE System SHALL refresh it from AWS Pricing API
3. WHEN Pricing_Data is unavailable, THE System SHALL fetch it from AWS Pricing API before estimation
4. THE System SHALL support pricing for all Supported_Services
5. THE System SHALL store pricing per region (us-east-1, us-west-2, eu-west-1, etc.)
6. WHEN Pricing_Data is updated, THE System SHALL log the update timestamp

### Requirement 4: Estimation API Endpoints

**User Story:** As a frontend developer, I want API endpoints to query cost estimates, so that I can display near-real-time costs to users.

#### Acceptance Criteria

1. THE Estimation_API SHALL provide a GET endpoint at /api/cost-estimation/current
2. WHEN querying current estimates, THE Estimation_API SHALL return costs for all Supported_Services
3. THE Estimation_API SHALL provide a GET endpoint at /api/cost-estimation/service/{service_name}
4. WHEN querying service-specific estimates, THE Estimation_API SHALL return costs for the specified service only
5. THE Estimation_API SHALL support query parameters for time range (last 1 hour, last 24 hours, last 7 days)
6. WHEN time range is not specified, THE Estimation_API SHALL default to last 1 hour
7. THE Estimation_API SHALL return estimates in JSON format with service name, estimated cost, currency, and timestamp
8. WHEN authentication fails, THE Estimation_API SHALL return 401 Unauthorized

### Requirement 5: Integration with Phase 1

**User Story:** As a developer, I want Phase 1.5 to integrate seamlessly with Phase 1, so that I have both historical and near-real-time cost data.

#### Acceptance Criteria

1. THE System SHALL reuse the existing DynamoDB table from Phase 1 for storing metrics
2. THE System SHALL reuse the existing API Gateway from Phase 1 for new endpoints
3. THE System SHALL reuse the existing IAM roles from Phase 1 with additional CloudWatch permissions
4. WHEN Phase 1 endpoints are called, THE System SHALL continue to function without disruption
5. THE System SHALL use the same authentication mechanism as Phase 1 (API key)
6. THE System SHALL follow the same error handling patterns as Phase 1

### Requirement 6: Error Handling and Retry Logic

**User Story:** As a system administrator, I want robust error handling, so that temporary failures don't disrupt cost estimation.

#### Acceptance Criteria

1. WHEN CloudWatch API calls fail with rate limiting (429), THE System SHALL retry with exponential backoff
2. WHEN CloudWatch API calls fail with service unavailable (503), THE System SHALL retry up to 3 times
3. WHEN Pricing API calls fail, THE System SHALL use cached pricing data if available
4. WHEN metrics collection fails for a service, THE System SHALL continue collecting for other services
5. WHEN estimation fails, THE System SHALL return a structured error response with error code and message
6. THE System SHALL log all errors to CloudWatch Logs for debugging

### Requirement 7: Performance and Scalability

**User Story:** As a system architect, I want efficient metric collection and estimation, so that the system scales within Free Tier limits.

#### Acceptance Criteria

1. THE System SHALL collect metrics in batches to minimize CloudWatch API calls
2. WHEN collecting metrics, THE System SHALL use CloudWatch GetMetricStatistics with appropriate periods
3. THE System SHALL cache pricing data to avoid repeated Pricing API calls
4. THE System SHALL complete cost estimation requests within 2 seconds for single service queries
5. THE System SHALL complete cost estimation requests within 5 seconds for all services queries
6. THE System SHALL operate within AWS Free Tier limits (1 million CloudWatch API requests per month)

### Requirement 8: Data Validation and Quality

**User Story:** As a developer, I want validated and accurate data, so that cost estimates are reliable.

#### Acceptance Criteria

1. WHEN metrics are collected, THE System SHALL validate metric values are non-negative
2. WHEN pricing data is fetched, THE System SHALL validate prices are positive numbers
3. WHEN estimates are calculated, THE System SHALL validate results are within reasonable bounds
4. WHEN invalid data is detected, THE System SHALL log a warning and skip the invalid data point
5. THE System SHALL track estimation accuracy by comparing estimates to actual costs from Phase 1

### Requirement 9: Monitoring and Observability

**User Story:** As a system administrator, I want visibility into system health, so that I can troubleshoot issues quickly.

#### Acceptance Criteria

1. THE System SHALL log metric collection operations to CloudWatch Logs
2. THE System SHALL log cost estimation operations to CloudWatch Logs
3. THE System SHALL log pricing data updates to CloudWatch Logs
4. WHEN errors occur, THE System SHALL log error details including service, operation, and error message
5. THE System SHALL emit CloudWatch metrics for estimation request count and latency
6. THE System SHALL emit CloudWatch metrics for estimation accuracy

### Requirement 10: Free Tier Compliance

**User Story:** As a cost-conscious developer, I want the system to operate within AWS Free Tier, so that I don't incur unexpected charges.

#### Acceptance Criteria

1. THE System SHALL use CloudWatch API efficiently to stay within 1 million requests per month
2. THE System SHALL use DynamoDB on-demand billing to avoid provisioned capacity charges
3. THE System SHALL use Lambda functions with appropriate memory and timeout settings
4. THE System SHALL minimize data transfer costs by using same-region resources
5. THE System SHALL document expected Free Tier usage in deployment documentation

## Summary

Phase 1.5 adds near-real-time cost estimation by collecting CloudWatch metrics and applying pricing calculations. It integrates seamlessly with Phase 1's infrastructure while adding new capabilities for current cost visibility. The system is designed to operate within AWS Free Tier limits and provide accurate, timely cost estimates for supported AWS services.
