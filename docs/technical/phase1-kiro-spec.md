# Phase 1: Core Cost Data Pipeline - Kiro Specification

**Keywords:** Phase 1, Lambda, Cost Explorer API, DynamoDB, API Gateway, cost data pipeline, Kiro spec, AWS SDK, error handling, IAM permissions, Free Tier

## Related Files
- **[../submission/FORM-FIELD-RESPONSES.md](../submission/FORM-FIELD-RESPONSES.md)** - Original game plan
- **[../submission/SEMI-FINALIST-PHASE.md](../submission/SEMI-FINALIST-PHASE.md)** - Current phase requirements
- **[architecture.md](./architecture.md)** - System architecture
- **[aws-services.md](./aws-services.md)** - AWS services documentation
- **[database-design.md](./database-design.md)** - Database schema
- **[api-design.md](./api-design.md)** - API specifications
- **[../INDEX.md](../INDEX.md)** - Master documentation index

---

## Overview

**Phase:** Phase 1 - Core Cost Data Pipeline  
**Timeline:** Weeks 1-2  
**Kiro Usage Target:** 70% of development  
**Purpose:** Build the foundation for CostGuard AI by creating a Lambda function that fetches historical AWS cost data from Cost Explorer API, stores it in DynamoDB, and exposes it via API Gateway.

---

## Objectives

1. **Fetch Historical Cost Data:** Retrieve last 12 months of AWS cost data from Cost Explorer API
2. **Store Cost Data:** Persist cost data in DynamoDB for fast retrieval and analysis
3. **Expose via API:** Create REST API endpoints via API Gateway to access cost data
4. **Error Handling:** Implement robust error handling and retry logic
5. **Free Tier Compliance:** Ensure all operations stay within AWS Free Tier limits

---

## Technical Requirements

### AWS Services to Use

1. **AWS Lambda**
   - Runtime: Node.js 20.x or Python 3.11
   - Memory: 256 MB (sufficient for API calls and data processing)
   - Timeout: 30 seconds (Cost Explorer API can be slow)
   - Free Tier: 1M requests/month, 400K GB-seconds

2. **AWS Cost Explorer API**
   - Service: `ce` (Cost Explorer)
   - Primary API: `GetCostAndUsage`
   - Free Tier: API calls are free (data retrieval only)

3. **Amazon DynamoDB**
   - Billing Mode: On-demand (Free Tier: 25 GB storage, 25 RCU/WCU)
   - Table: `costguard-cost-data`
   - Purpose: Store historical cost data

4. **Amazon API Gateway**
   - Type: REST API
   - Authentication: API Key (simple for MVP)
   - Free Tier: 1M API calls/month

5. **AWS IAM**
   - Roles: Lambda execution role with permissions
   - Policies: Cost Explorer read access, DynamoDB read/write

---

## Lambda Function Specification

### Function Name
`CostDataFetcher`

### Function Purpose
Fetch historical AWS cost data from Cost Explorer API and store it in DynamoDB.

### Input Parameters

**Event Structure (API Gateway):**
```json
{
  "queryStringParameters": {
    "startDate": "2025-01-01",  // Optional, defaults to 12 months ago
    "endDate": "2025-12-31",    // Optional, defaults to today
    "granularity": "MONTHLY",   // Optional: DAILY, MONTHLY, HOURLY (default: MONTHLY)
    "metrics": "BlendedCost"    // Optional: BlendedCost, UnblendedCost, UsageQuantity
  }
}
```

**Direct Invocation (for scheduled runs):**
```json
{
  "action": "fetch",
  "startDate": "2025-01-01",
  "endDate": "2025-12-31",
  "granularity": "MONTHLY"
}
```

### Function Logic

1. **Parse Input Parameters**
   - Extract startDate, endDate, granularity from event
   - Default to last 12 months if not provided
   - Validate date format (YYYY-MM-DD)

2. **Fetch Cost Data from Cost Explorer API**
   - Use AWS SDK `ce.getCostAndUsage()` method
   - Parameters:
     - `TimePeriod`: Start and End dates
     - `Granularity`: MONTHLY (or from input)
     - `Metrics`: ["BlendedCost", "UnblendedCost"]
     - `GroupBy`: [{"Type": "DIMENSION", "Key": "SERVICE"}]
   - Handle pagination if results exceed single API call limit

3. **Transform Data for Storage**
   - Convert API response to DynamoDB-friendly format
   - Structure:
     ```json
     {
       "pk": "COST#2025-01",  // Partition key: COST#YYYY-MM
       "sk": "SERVICE#ec2",    // Sort key: SERVICE#service-name
       "date": "2025-01-01",
       "service": "Amazon Elastic Compute Cloud - Compute",
       "blendedCost": 123.45,
       "unblendedCost": 123.45,
       "currency": "USD",
       "unit": "USD",
       "timestamp": "2025-01-31T23:59:59Z",
       "ttl": 1735689599  // 1 year from now (optional, for data retention)
     }
     ```

4. **Store in DynamoDB**
   - Use batch write for efficiency (DynamoDB batchWriteItem)
   - Handle partial failures and retry logic
   - Check for existing records (avoid duplicates)

5. **Return Response**
   - Success: Return summary of fetched data
   - Error: Return error details with appropriate status code

### Output Format

**Success Response:**
```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "message": "Cost data fetched and stored successfully",
    "data": {
      "recordsProcessed": 120,
      "dateRange": {
        "start": "2025-01-01",
        "end": "2025-12-31"
      },
      "totalCost": 1234.56,
      "services": ["EC2", "S3", "Lambda", "DynamoDB"]
    }
  }
}
```

**Error Response:**
```json
{
  "statusCode": 500,
  "body": {
    "success": false,
    "error": {
      "code": "COST_EXPLORER_ERROR",
      "message": "Failed to fetch cost data from Cost Explorer API",
      "details": "Rate limit exceeded. Please retry after 60 seconds."
    }
  }
}
```

---

## DynamoDB Table Design

### Table Name
`costguard-cost-data`

### Table Schema

**Partition Key (PK):** `pk` (String)
- Format: `COST#YYYY-MM` (e.g., "COST#2025-01")
- Purpose: Group cost data by month

**Sort Key (SK):** `sk` (String)
- Format: `SERVICE#service-name` (e.g., "SERVICE#ec2")
- Purpose: Enable querying by service within a month

**Attributes:**
- `date` (String): Date in YYYY-MM-DD format
- `service` (String): Full AWS service name
- `blendedCost` (Number): Blended cost amount
- `unblendedCost` (Number): Unblended cost amount
- `currency` (String): Currency code (default: "USD")
- `unit` (String): Unit of measurement (default: "USD")
- `timestamp` (String): ISO 8601 timestamp
- `ttl` (Number): Time-to-live for automatic cleanup (optional)

### Global Secondary Index (GSI) - Optional

**Index Name:** `service-date-index`
- Partition Key: `service`
- Sort Key: `date`
- Purpose: Query cost data by service across all months

### Free Tier Considerations

- **Storage:** 25 GB free (estimate: ~1-2 GB for 12 months of data)
- **Read/Write:** 25 RCU/WCU free (on-demand mode handles bursts)
- **Optimization:** Use on-demand billing mode to avoid capacity planning

---

## API Gateway Endpoints

### Endpoint 1: Fetch and Store Cost Data

**Method:** `POST`  
**Path:** `/api/cost-data/fetch`  
**Description:** Trigger Lambda to fetch cost data from Cost Explorer API and store in DynamoDB

**Request:**
```json
{
  "startDate": "2025-01-01",
  "endDate": "2025-12-31",
  "granularity": "MONTHLY"
}
```

**Response:** See Lambda output format above

**Authentication:** API Key required

---

### Endpoint 2: Get Stored Cost Data

**Method:** `GET`  
**Path:** `/api/cost-data`  
**Description:** Retrieve stored cost data from DynamoDB

**Query Parameters:**
- `startDate` (optional): Start date filter (YYYY-MM-DD)
- `endDate` (optional): End date filter (YYYY-MM-DD)
- `service` (optional): Filter by service name
- `limit` (optional): Max records to return (default: 100)

**Example Request:**
```
GET /api/cost-data?startDate=2025-01-01&endDate=2025-12-31&service=EC2
```

**Response:**
```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "data": [
      {
        "date": "2025-01-01",
        "service": "Amazon Elastic Compute Cloud - Compute",
        "blendedCost": 123.45,
        "unblendedCost": 123.45,
        "currency": "USD"
      }
    ],
    "count": 12
  }
}
```

**Authentication:** API Key required

---

## IAM Permissions

### Lambda Execution Role

**Role Name:** `CostGuard-CostDataFetcher-Role`

**Policies Required:**

1. **Cost Explorer Read Access:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetDimensionValues",
        "ce:GetUsage"
      ],
      "Resource": "*"
    }
  ]
}
```

2. **DynamoDB Read/Write Access:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchWriteItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/costguard-cost-data"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/costguard-cost-data/index/*"
    }
  ]
}
```

3. **CloudWatch Logs (for Lambda):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

---

## Error Handling Requirements

### Error Types to Handle

1. **Cost Explorer API Errors:**
   - Rate limiting (429): Implement exponential backoff retry
   - Invalid date range (400): Validate dates before API call
   - Service unavailable (503): Retry with backoff
   - Access denied (403): Log and return clear error message

2. **DynamoDB Errors:**
   - Throttling (ProvisionedThroughputExceeded): Retry with backoff
   - Validation errors: Return clear error message
   - Item size limits: Split large batches

3. **Lambda Errors:**
   - Timeout: Increase timeout or optimize code
   - Memory limits: Monitor and adjust if needed
   - Invalid input: Validate and return 400 error

### Error Handling Implementation

- Use try-catch blocks for all AWS SDK calls
- Implement exponential backoff for retries (max 3 retries)
- Log all errors to CloudWatch Logs with context
- Return user-friendly error messages in API responses
- Include error codes for programmatic handling

---

## Code Structure (Kiro to Generate)

### File Structure

```
cost-data-fetcher/
├── index.js (or index.py)
├── package.json (or requirements.txt)
├── costExplorerService.js (or cost_explorer_service.py)
├── dynamoDbService.js (or dynamodb_service.py)
├── errorHandler.js (or error_handler.py)
├── utils.js (or utils.py)
└── tests/
    ├── unit/
    │   ├── costExplorerService.test.js
    │   └── dynamoDbService.test.js
    └── integration/
        └── lambda.test.js
```

### Key Functions to Generate

1. **Main Lambda Handler**
   - Parse event parameters
   - Orchestrate data fetching and storage
   - Handle errors and return response

2. **Cost Explorer Service**
   - `fetchCostData(startDate, endDate, granularity)`
   - Handle pagination
   - Transform API response

3. **DynamoDB Service**
   - `storeCostData(costDataArray)`
   - `getCostData(queryParams)`
   - Batch write with retry logic

4. **Error Handler**
   - `handleError(error, context)`
   - Format error responses
   - Log errors to CloudWatch

5. **Utils**
   - `validateDateRange(startDate, endDate)`
   - `formatDateForAPI(date)`
   - `calculateTTL(days)`

---

## Testing Requirements

### Unit Tests

1. **Cost Explorer Service Tests:**
   - Test successful API call
   - Test pagination handling
   - Test error handling (rate limits, invalid dates)
   - Mock AWS SDK responses

2. **DynamoDB Service Tests:**
   - Test batch write operations
   - Test query operations
   - Test error handling (throttling, validation)
   - Mock DynamoDB responses

3. **Lambda Handler Tests:**
   - Test successful execution flow
   - Test error scenarios
   - Test input validation
   - Mock all AWS services

### Integration Tests

1. **End-to-End Test:**
   - Invoke Lambda with test event
   - Verify data stored in DynamoDB
   - Verify API Gateway response

2. **API Gateway Test:**
   - Test POST /api/cost-data/fetch endpoint
   - Test GET /api/cost-data endpoint
   - Verify authentication (API key)
   - Test error responses

### Test Data

- Use mock Cost Explorer API responses
- Use local DynamoDB for testing (DynamoDB Local)
- Create test fixtures for various scenarios

---

## Free Tier Compliance

### Monitoring Requirements

1. **Lambda:**
   - Monitor invocation count (target: < 1000/month for testing)
   - Monitor execution time (optimize to stay under timeout)
   - Monitor memory usage (target: < 256 MB)

2. **DynamoDB:**
   - Monitor storage (target: < 5 GB for MVP)
   - Monitor read/write units (on-demand mode handles this)
   - Set up CloudWatch alarms for Free Tier limits

3. **API Gateway:**
   - Monitor API call count (target: < 10,000/month for testing)
   - Monitor data transfer (minimize response sizes)

### Optimization Strategies

1. **Batch Operations:** Use DynamoDB batch writes to reduce API calls
2. **Caching:** Cache Cost Explorer API responses (if allowed by terms)
3. **Pagination:** Handle Cost Explorer pagination efficiently
4. **Data Retention:** Use TTL to auto-delete old data (optional)

---

## Deployment Instructions

### Step 1: Create DynamoDB Table

```bash
aws dynamodb create-table \
  --table-name costguard-cost-data \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode ON_DEMAND
```

### Step 2: Create IAM Role

Create IAM role with policies specified above.

### Step 3: Deploy Lambda Function

Use Kiro-generated code and deploy via:
- AWS Console
- AWS CLI
- AWS SAM
- Serverless Framework

### Step 4: Create API Gateway

1. Create REST API
2. Create resources and methods
3. Integrate with Lambda
4. Deploy to stage
5. Create and attach API key

### Step 5: Test

1. Test Lambda directly with test event
2. Test via API Gateway endpoint
3. Verify data in DynamoDB
4. Check CloudWatch Logs for errors

---

## Kiro Generation Instructions

### Prompt Template for Kiro

**Use this prompt with Kiro:**

```
Create an AWS Lambda function (Node.js 20.x) that:

1. Fetches historical AWS cost data from Cost Explorer API using AWS SDK
   - Get last 12 months of cost data by default
   - Support custom date ranges via input parameters
   - Handle pagination for large datasets
   - Group by service (SERVICE dimension)
   - Retrieve BlendedCost and UnblendedCost metrics
   - Use MONTHLY granularity by default

2. Stores the fetched cost data in DynamoDB table "costguard-cost-data"
   - Use partition key: pk (format: "COST#YYYY-MM")
   - Use sort key: sk (format: "SERVICE#service-name")
   - Store: date, service, blendedCost, unblendedCost, currency, unit, timestamp
   - Use batch write operations for efficiency
   - Handle retries for throttling errors

3. Exposes data via API Gateway REST API
   - POST /api/cost-data/fetch: Trigger data fetch and storage
   - GET /api/cost-data: Retrieve stored cost data with optional filters
   - Include proper error handling and status codes
   - Support API key authentication

4. Includes comprehensive error handling:
   - Handle Cost Explorer API rate limits with exponential backoff
   - Handle DynamoDB throttling with retries
   - Validate input parameters
   - Return user-friendly error messages

5. Follows AWS best practices:
   - Proper IAM permissions (minimal required permissions)
   - CloudWatch logging
   - Free Tier compliance
   - Efficient data structures

6. Includes unit tests:
   - Test Cost Explorer integration (mocked)
   - Test DynamoDB operations (mocked)
   - Test error scenarios
   - Test input validation

Generate complete, production-ready code with:
- Lambda handler function
- AWS SDK integration (Cost Explorer and DynamoDB)
- Error handling utilities
- Input validation
- Unit tests
- README with deployment instructions
```

---

## Success Criteria

✅ Lambda function successfully fetches cost data from Cost Explorer API  
✅ Cost data stored correctly in DynamoDB  
✅ API Gateway endpoints return data correctly  
✅ Error handling works for common failure scenarios  
✅ Unit tests pass  
✅ Free Tier limits respected  
✅ Code is production-ready and follows AWS best practices  

---

## Next Steps After Phase 1

Once Phase 1 is complete:
- Phase 1.5: Near-real-time cost estimation (CloudWatch metrics)
- Phase 2: AI forecasting (Bedrock integration)
- Phase 3: Automated prevention
- Phase 4: AI cost advisor
- Phase 5: React frontend

---

## Related Documentation

- **[AWS Cost Explorer API Documentation](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html)**
- **[DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)**
- **[Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)**
- **[API Gateway Best Practices](https://docs.aws.amazon.com/apigateway/latest/developerguide/best-practices.html)**

---

**Last Updated:** February 2026  
**Status:** ✅ **COMPLETE** - Phase 1 successfully implemented and deployed  
**Implementation:** See [development-notes.md](./development-notes.md) for completion details  
**Test Coverage:** 91.51% (105 unit tests, 29 integration tests)  
**Deployment:** Production-ready, all tests passing
