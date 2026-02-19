# API Examples

This document provides comprehensive examples of API requests and responses for the Cost Data Pipeline.

## Table of Contents

- [Setup](#setup)
- [POST /api/cost-data/fetch Examples](#post-apicost-datafetch-examples)
- [GET /api/cost-data Examples](#get-apicost-data-examples)
- [Error Examples](#error-examples)

## Setup

### Environment Variables

Set these for easier testing:

```bash
export API_ENDPOINT="https://your-api-id.execute-api.us-east-1.amazonaws.com/prod"
export API_KEY="your-api-key-here"
```

### Test API Connection

```bash
curl -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/cost-data"
```

---

## POST /api/cost-data/fetch Examples

### Example 1: Fetch with All Parameters

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2025-01-01",
    "endDate": "2025-12-31",
    "granularity": "MONTHLY"
  }' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Cost data fetched and stored successfully",
  "data": {
    "recordsProcessed": 144,
    "dateRange": {
      "start": "2025-01-01",
      "end": "2025-12-31"
    },
    "totalCost": 1234.56,
    "services": [
      "Amazon Elastic Compute Cloud - Compute",
      "Amazon Simple Storage Service",
      "AWS Lambda",
      "Amazon DynamoDB",
      "Amazon CloudWatch",
      "AWS Cost Explorer",
      "Amazon API Gateway",
      "AWS Key Management Service",
      "Amazon Route 53",
      "Amazon CloudFront",
      "Amazon RDS Service",
      "Amazon ElastiCache"
    ]
  }
}
```

### Example 2: Fetch with Default Parameters

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Cost data fetched and stored successfully",
  "data": {
    "recordsProcessed": 96,
    "dateRange": {
      "start": "2024-02-19",
      "end": "2025-02-19"
    },
    "totalCost": 856.32,
    "services": [
      "Amazon Elastic Compute Cloud - Compute",
      "Amazon Simple Storage Service",
      "AWS Lambda",
      "Amazon DynamoDB"
    ]
  }
}
```

**Note:** Default parameters are:
- `startDate`: 12 months ago from today
- `endDate`: Today
- `granularity`: MONTHLY

### Example 3: Fetch Daily Granularity

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2025-01-01",
    "endDate": "2025-01-31",
    "granularity": "DAILY"
  }' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Cost data fetched and stored successfully",
  "data": {
    "recordsProcessed": 372,
    "dateRange": {
      "start": "2025-01-01",
      "end": "2025-01-31"
    },
    "totalCost": 98.45,
    "services": [
      "Amazon Elastic Compute Cloud - Compute",
      "Amazon Simple Storage Service",
      "AWS Lambda",
      "Amazon DynamoDB",
      "Amazon CloudWatch",
      "Amazon API Gateway"
    ]
  }
}
```

### Example 4: Fetch Hourly Granularity (Short Range)

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2025-02-18",
    "endDate": "2025-02-19",
    "granularity": "HOURLY"
  }' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Cost data fetched and stored successfully",
  "data": {
    "recordsProcessed": 288,
    "dateRange": {
      "start": "2025-02-18",
      "end": "2025-02-19"
    },
    "totalCost": 6.78,
    "services": [
      "Amazon Elastic Compute Cloud - Compute",
      "Amazon Simple Storage Service",
      "AWS Lambda"
    ]
  }
}
```

**Note:** Hourly granularity generates many records. Use short date ranges to avoid timeouts.

---

## GET /api/cost-data Examples

### Example 1: Query All Data

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-data"
```

**Response (Success):**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-01-01",
      "service": "Amazon Elastic Compute Cloud - Compute",
      "blendedCost": 45.67,
      "unblendedCost": 45.67,
      "currency": "USD"
    },
    {
      "date": "2025-01-01",
      "service": "Amazon Simple Storage Service",
      "blendedCost": 12.34,
      "unblendedCost": 12.34,
      "currency": "USD"
    },
    {
      "date": "2025-01-01",
      "service": "AWS Lambda",
      "blendedCost": 3.21,
      "unblendedCost": 3.21,
      "currency": "USD"
    }
  ],
  "count": 3
}
```

**Note:** Default limit is 100 records. Results are sorted by date and service.

### Example 2: Query with Date Range

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-data?startDate=2025-01-01&endDate=2025-03-31"
```

**Response (Success):**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-01-01",
      "service": "Amazon Elastic Compute Cloud - Compute",
      "blendedCost": 45.67,
      "unblendedCost": 45.67,
      "currency": "USD"
    },
    {
      "date": "2025-02-01",
      "service": "Amazon Elastic Compute Cloud - Compute",
      "blendedCost": 48.23,
      "unblendedCost": 48.23,
      "currency": "USD"
    },
    {
      "date": "2025-03-01",
      "service": "Amazon Elastic Compute Cloud - Compute",
      "blendedCost": 52.11,
      "unblendedCost": 52.11,
      "currency": "USD"
    }
  ],
  "count": 3
}
```

### Example 3: Query Specific Service

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-data?service=Amazon%20Simple%20Storage%20Service"
```

**Response (Success):**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-01-01",
      "service": "Amazon Simple Storage Service",
      "blendedCost": 12.34,
      "unblendedCost": 12.34,
      "currency": "USD"
    },
    {
      "date": "2025-02-01",
      "service": "Amazon Simple Storage Service",
      "blendedCost": 13.45,
      "unblendedCost": 13.45,
      "currency": "USD"
    },
    {
      "date": "2025-03-01",
      "service": "Amazon Simple Storage Service",
      "blendedCost": 14.56,
      "unblendedCost": 14.56,
      "currency": "USD"
    }
  ],
  "count": 3
}
```

**Note:** Service names must be URL-encoded. Use `%20` for spaces.

### Example 4: Query with Limit

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-data?limit=5"
```

**Response (Success):**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-01-01",
      "service": "Amazon API Gateway",
      "blendedCost": 1.23,
      "unblendedCost": 1.23,
      "currency": "USD"
    },
    {
      "date": "2025-01-01",
      "service": "Amazon CloudWatch",
      "blendedCost": 2.34,
      "unblendedCost": 2.34,
      "currency": "USD"
    },
    {
      "date": "2025-01-01",
      "service": "Amazon DynamoDB",
      "blendedCost": 0.56,
      "unblendedCost": 0.56,
      "currency": "USD"
    },
    {
      "date": "2025-01-01",
      "service": "Amazon Elastic Compute Cloud - Compute",
      "blendedCost": 45.67,
      "unblendedCost": 45.67,
      "currency": "USD"
    },
    {
      "date": "2025-01-01",
      "service": "Amazon Simple Storage Service",
      "blendedCost": 12.34,
      "unblendedCost": 12.34,
      "currency": "USD"
    }
  ],
  "count": 5
}
```

### Example 5: Query with Multiple Filters

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-data?startDate=2025-01-01&endDate=2025-06-30&service=AWS%20Lambda&limit=10"
```

**Response (Success):**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-01-01",
      "service": "AWS Lambda",
      "blendedCost": 3.21,
      "unblendedCost": 3.21,
      "currency": "USD"
    },
    {
      "date": "2025-02-01",
      "service": "AWS Lambda",
      "blendedCost": 3.45,
      "unblendedCost": 3.45,
      "currency": "USD"
    },
    {
      "date": "2025-03-01",
      "service": "AWS Lambda",
      "blendedCost": 3.67,
      "unblendedCost": 3.67,
      "currency": "USD"
    },
    {
      "date": "2025-04-01",
      "service": "AWS Lambda",
      "blendedCost": 3.89,
      "unblendedCost": 3.89,
      "currency": "USD"
    },
    {
      "date": "2025-05-01",
      "service": "AWS Lambda",
      "blendedCost": 4.12,
      "unblendedCost": 4.12,
      "currency": "USD"
    },
    {
      "date": "2025-06-01",
      "service": "AWS Lambda",
      "blendedCost": 4.34,
      "unblendedCost": 4.34,
      "currency": "USD"
    }
  ],
  "count": 6
}
```

### Example 6: Query with No Results

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-data?startDate=2030-01-01&endDate=2030-12-31"
```

**Response (Success):**
```json
{
  "success": true,
  "data": [],
  "count": 0
}
```

---

## Error Examples

### Error 1: Invalid Date Format

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "01-01-2025",
    "endDate": "2025-12-31",
    "granularity": "MONTHLY"
  }' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (400 Bad Request):**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_DATE_FORMAT",
    "message": "Invalid date format. Expected YYYY-MM-DD, got: 01-01-2025"
  }
}
```

### Error 2: Invalid Date Range

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2025-12-31",
    "endDate": "2025-01-01",
    "granularity": "MONTHLY"
  }' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (400 Bad Request):**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_DATE_RANGE",
    "message": "Start date must be before or equal to end date"
  }
}
```

### Error 3: Invalid Granularity

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2025-01-01",
    "endDate": "2025-12-31",
    "granularity": "WEEKLY"
  }' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (400 Bad Request):**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_GRANULARITY",
    "message": "Invalid granularity. Must be one of: DAILY, MONTHLY, HOURLY"
  }
}
```

### Error 4: Missing API Key

**Request:**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (401 Unauthorized):**
```json
{
  "message": "Unauthorized"
}
```

**Note:** This error is returned by API Gateway before reaching the Lambda function.

### Error 5: Invalid API Key

**Request:**
```bash
curl -X POST \
  -H "x-api-key: invalid-key-12345" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (403 Forbidden):**
```json
{
  "message": "Forbidden"
}
```

**Note:** This error is returned by API Gateway before reaching the Lambda function.

### Error 6: Cost Explorer Access Denied

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (403 Forbidden):**
```json
{
  "success": false,
  "error": {
    "code": "COST_EXPLORER_ACCESS_DENIED",
    "message": "Access denied to Cost Explorer API. Check IAM permissions.",
    "details": {
      "service": "Cost Explorer",
      "operation": "GetCostAndUsage"
    }
  }
}
```

**Solution:** Ensure the Lambda execution role has `ce:GetCostAndUsage` permission.

### Error 7: Rate Limit Exceeded

**Request:**
```bash
# Multiple rapid requests
for i in {1..10}; do
  curl -X POST \
    -H "x-api-key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{}' \
    "$API_ENDPOINT/api/cost-data/fetch"
done
```

**Response (429 Too Many Requests):**
```json
{
  "success": false,
  "error": {
    "code": "COST_EXPLORER_RATE_LIMIT",
    "message": "Rate limit exceeded on Cost Explorer API. Retries exhausted.",
    "details": {
      "retryCount": 3,
      "lastError": "ThrottlingException"
    }
  }
}
```

**Note:** The system automatically retries with exponential backoff. This error only occurs if all retries fail.

### Error 8: DynamoDB Error

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$API_ENDPOINT/api/cost-data/fetch"
```

**Response (500 Internal Server Error):**
```json
{
  "success": false,
  "error": {
    "code": "DYNAMODB_ERROR",
    "message": "Error writing to DynamoDB",
    "details": {
      "operation": "BatchWriteItem",
      "tableName": "costguard-cost-data"
    }
  }
}
```

**Solution:** Check DynamoDB table exists and Lambda has write permissions.

### Error 9: Unsupported HTTP Method

**Request:**
```bash
curl -X DELETE \
  -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-data"
```

**Response (400 Bad Request):**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Unsupported HTTP method: DELETE"
  }
}
```

**Note:** Only POST /api/cost-data/fetch and GET /api/cost-data are supported.

---

## Testing Tips

### 1. Start with Small Date Ranges

When testing, use small date ranges to avoid timeouts:

```bash
# Good: 1 month
curl -X POST -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"startDate":"2025-01-01","endDate":"2025-01-31","granularity":"MONTHLY"}' \
  "$API_ENDPOINT/api/cost-data/fetch"

# Avoid: 5 years with DAILY granularity (too many records)
```

### 2. Use jq for Pretty Output

Install jq for formatted JSON output:

```bash
curl -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/cost-data" | jq '.'
```

### 3. Save Responses for Analysis

```bash
curl -H "x-api-key: $API_KEY" "$API_ENDPOINT/api/cost-data" > costs.json
```

### 4. Monitor CloudWatch Logs

Watch logs in real-time:

```bash
aws logs tail /aws/lambda/costguard-cost-data-handler --follow
```

### 5. Check API Gateway Metrics

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=costguard-cost-data-api \
  --start-time 2025-02-19T00:00:00Z \
  --end-time 2025-02-19T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

---

## Postman Collection

You can import these examples into Postman:

1. Create a new collection: "Cost Data Pipeline"
2. Add environment variables:
   - `api_endpoint`: Your API Gateway URL
   - `api_key`: Your API key
3. Create requests using the examples above
4. Use `{{api_endpoint}}` and `{{api_key}}` in requests

---

## Python Examples

### Fetch Cost Data

```python
import requests
import json

API_ENDPOINT = "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod"
API_KEY = "your-api-key"

headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

payload = {
    "startDate": "2025-01-01",
    "endDate": "2025-12-31",
    "granularity": "MONTHLY"
}

response = requests.post(
    f"{API_ENDPOINT}/api/cost-data/fetch",
    headers=headers,
    json=payload
)

print(json.dumps(response.json(), indent=2))
```

### Query Cost Data

```python
import requests
import json

API_ENDPOINT = "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod"
API_KEY = "your-api-key"

headers = {
    "x-api-key": API_KEY
}

params = {
    "startDate": "2025-01-01",
    "endDate": "2025-12-31",
    "service": "Amazon Simple Storage Service",
    "limit": 50
}

response = requests.get(
    f"{API_ENDPOINT}/api/cost-data",
    headers=headers,
    params=params
)

print(json.dumps(response.json(), indent=2))
```

---

## Additional Resources

- [AWS Cost Explorer API Documentation](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html)
- [DynamoDB Query Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.html)
- [API Gateway Authentication](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-key-source.html)
