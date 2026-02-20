# API Examples

This document provides comprehensive examples of API requests and responses for the Cost Data Pipeline (Phase 1) and Near-Real-Time Cost Estimation (Phase 1.5).

## Table of Contents

- [Setup](#setup)
- [Phase 1: Historical Cost Data](#phase-1-historical-cost-data)
  - [POST /api/cost-data/fetch Examples](#post-apicost-datafetch-examples)
  - [GET /api/cost-data Examples](#get-apicost-data-examples)
- [Phase 1.5: Near-Real-Time Cost Estimation](#phase-15-near-real-time-cost-estimation)
  - [GET /api/cost-estimation/current Examples](#get-apicost-estimationcurrent-examples)
  - [GET /api/cost-estimation/service/{service} Examples](#get-apicost-estimationserviceservice-examples)
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

## Phase 1: Historical Cost Data

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

## Phase 1.5: Near-Real-Time Cost Estimation

## GET /api/cost-estimation/current Examples

### Example 1: Get Current Estimates for All Services (Last 1 Hour)

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/current"
```

**Response (Success):**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "ec2",
      "estimated_cost": 0.0234,
      "currency": "USD",
      "confidence_lower": 0.0220,
      "confidence_upper": 0.0248,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-21T09:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 12
    },
    {
      "service": "lambda",
      "estimated_cost": 0.0012,
      "currency": "USD",
      "confidence_lower": 0.0011,
      "confidence_upper": 0.0013,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-21T09:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 45
    },
    {
      "service": "dynamodb",
      "estimated_cost": 0.0008,
      "currency": "USD",
      "confidence_lower": 0.0007,
      "confidence_upper": 0.0009,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-21T09:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 24
    },
    {
      "service": "s3",
      "estimated_cost": 0.0156,
      "currency": "USD",
      "confidence_lower": 0.0145,
      "confidence_upper": 0.0167,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-21T09:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 8
    },
    {
      "service": "rds",
      "estimated_cost": 0.0445,
      "currency": "USD",
      "confidence_lower": 0.0420,
      "confidence_upper": 0.0470,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-21T09:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 18
    }
  ],
  "total_cost": 0.0855,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "1 hour"
}
```

**Note:** Default time range is 1 hour. Confidence intervals indicate estimation accuracy.

### Example 2: Get Current Estimates for Last 24 Hours

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/current?hours=24"
```

**Response (Success):**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "ec2",
      "estimated_cost": 0.5616,
      "currency": "USD",
      "confidence_lower": 0.5280,
      "confidence_upper": 0.5952,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-20T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 288
    },
    {
      "service": "lambda",
      "estimated_cost": 0.0288,
      "currency": "USD",
      "confidence_lower": 0.0264,
      "confidence_upper": 0.0312,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-20T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 1080
    },
    {
      "service": "dynamodb",
      "estimated_cost": 0.0192,
      "currency": "USD",
      "confidence_lower": 0.0168,
      "confidence_upper": 0.0216,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-20T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 576
    },
    {
      "service": "s3",
      "estimated_cost": 0.3744,
      "currency": "USD",
      "confidence_lower": 0.3480,
      "confidence_upper": 0.4008,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-20T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 192
    },
    {
      "service": "rds",
      "estimated_cost": 1.0680,
      "currency": "USD",
      "confidence_lower": 1.0080,
      "confidence_upper": 1.1280,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-20T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 432
    }
  ],
  "total_cost": 2.0520,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "24 hours"
}
```

### Example 3: Get Current Estimates for Last 7 Days

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/current?hours=168"
```

**Response (Success):**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "ec2",
      "estimated_cost": 3.9312,
      "currency": "USD",
      "confidence_lower": 3.6960,
      "confidence_upper": 4.1664,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-14T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 2016
    },
    {
      "service": "lambda",
      "estimated_cost": 0.2016,
      "currency": "USD",
      "confidence_lower": 0.1848,
      "confidence_upper": 0.2184,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-14T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 7560
    },
    {
      "service": "dynamodb",
      "estimated_cost": 0.1344,
      "currency": "USD",
      "confidence_lower": 0.1176,
      "confidence_upper": 0.1512,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-14T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 4032
    },
    {
      "service": "s3",
      "estimated_cost": 2.6208,
      "currency": "USD",
      "confidence_lower": 2.4360,
      "confidence_upper": 2.8056,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-14T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 1344
    },
    {
      "service": "rds",
      "estimated_cost": 7.4760,
      "currency": "USD",
      "confidence_lower": 7.0560,
      "confidence_upper": 7.8960,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-14T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 3024
    }
  ],
  "total_cost": 14.3640,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "168 hours"
}
```

**Note:** Maximum time range is 168 hours (7 days).

---

## GET /api/cost-estimation/service/{service} Examples

### Example 1: Get EC2 Cost Estimate

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/service/ec2"
```

**Response (Success):**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "ec2",
      "estimated_cost": 0.0234,
      "currency": "USD",
      "confidence_lower": 0.0220,
      "confidence_upper": 0.0248,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-21T09:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 12
    }
  ],
  "total_cost": 0.0234,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "1 hour"
}
```

### Example 2: Get Lambda Cost Estimate (24 Hours)

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/service/lambda?hours=24"
```

**Response (Success):**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "lambda",
      "estimated_cost": 0.0288,
      "currency": "USD",
      "confidence_lower": 0.0264,
      "confidence_upper": 0.0312,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-20T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 1080
    }
  ],
  "total_cost": 0.0288,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "24 hours"
}
```

### Example 3: Get DynamoDB Cost Estimate

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/service/dynamodb?hours=6"
```

**Response (Success):**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "dynamodb",
      "estimated_cost": 0.0048,
      "currency": "USD",
      "confidence_lower": 0.0042,
      "confidence_upper": 0.0054,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-21T04:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 144
    }
  ],
  "total_cost": 0.0048,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "6 hours"
}
```

### Example 4: Get S3 Cost Estimate

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/service/s3?hours=12"
```

**Response (Success):**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "s3",
      "estimated_cost": 0.0936,
      "currency": "USD",
      "confidence_lower": 0.0870,
      "confidence_upper": 0.1002,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-20T22:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 96
    }
  ],
  "total_cost": 0.0936,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "12 hours"
}
```

### Example 5: Get RDS Cost Estimate

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/service/rds?hours=48"
```

**Response (Success):**
```json
{
  "success": true,
  "estimates": [
    {
      "service": "rds",
      "estimated_cost": 2.1360,
      "currency": "USD",
      "confidence_lower": 2.0160,
      "confidence_upper": 2.2560,
      "timestamp": "2025-02-21T10:30:00Z",
      "period_start": "2025-02-19T10:30:00Z",
      "period_end": "2025-02-21T10:30:00Z",
      "metrics_count": 864
    }
  ],
  "total_cost": 2.1360,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "48 hours"
}
```

### Example 6: Invalid Service Name

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/service/invalid-service"
```

**Response (400 Bad Request):**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid service name. Must be one of: ec2, lambda, dynamodb, s3, rds"
  }
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

### Error 10: Invalid Time Range (Phase 1.5)

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/current?hours=200"
```

**Response (400 Bad Request):**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid time range. Hours must be between 1 and 168 (7 days)"
  }
}
```

### Error 11: CloudWatch Metrics Collection Failed (Phase 1.5)

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/service/ec2"
```

**Response (500 Internal Server Error):**
```json
{
  "success": false,
  "error": {
    "code": "CLOUDWATCH_ERROR",
    "message": "Error collecting CloudWatch metrics",
    "details": {
      "service": "ec2",
      "operation": "GetMetricStatistics"
    }
  }
}
```

**Solution:** Check CloudWatch permissions and ensure resources exist.

### Error 12: Pricing Data Unavailable (Phase 1.5)

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/current"
```

**Response (500 Internal Server Error):**
```json
{
  "success": false,
  "error": {
    "code": "PRICING_ERROR",
    "message": "Pricing data unavailable for service",
    "details": {
      "service": "ec2",
      "region": "us-east-1"
    }
  }
}
```

**Solution:** Check Pricing API permissions and network connectivity.

### Error 13: No Metrics Available (Phase 1.5)

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$API_ENDPOINT/api/cost-estimation/service/lambda?hours=1"
```

**Response (200 OK):**
```json
{
  "success": true,
  "estimates": [],
  "total_cost": 0.00,
  "currency": "USD",
  "timestamp": "2025-02-21T10:30:00Z",
  "period": "1 hour"
}
```

**Note:** This is not an error. It indicates no resources were running during the time period.

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

### Get Current Cost Estimates (Phase 1.5)

```python
import requests
import json

API_ENDPOINT = "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod"
API_KEY = "your-api-key"

headers = {
    "x-api-key": API_KEY
}

# Get estimates for all services (last 1 hour)
response = requests.get(
    f"{API_ENDPOINT}/api/cost-estimation/current",
    headers=headers
)

print(json.dumps(response.json(), indent=2))

# Get estimates for last 24 hours
params = {"hours": 24}
response = requests.get(
    f"{API_ENDPOINT}/api/cost-estimation/current",
    headers=headers,
    params=params
)

print(json.dumps(response.json(), indent=2))
```

### Get Service-Specific Cost Estimate (Phase 1.5)

```python
import requests
import json

API_ENDPOINT = "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod"
API_KEY = "your-api-key"

headers = {
    "x-api-key": API_KEY
}

# Get EC2 cost estimate
service = "ec2"
params = {"hours": 6}

response = requests.get(
    f"{API_ENDPOINT}/api/cost-estimation/service/{service}",
    headers=headers,
    params=params
)

print(json.dumps(response.json(), indent=2))

# Get estimates for all supported services
services = ["ec2", "lambda", "dynamodb", "s3", "rds"]
for service in services:
    response = requests.get(
        f"{API_ENDPOINT}/api/cost-estimation/service/{service}",
        headers=headers,
        params={"hours": 1}
    )
    data = response.json()
    if data["success"] and data["estimates"]:
        estimate = data["estimates"][0]
        print(f"{service}: ${estimate['estimated_cost']:.4f}")
```

---

## Query Parameters Reference

### Phase 1: Historical Cost Data

| Parameter | Endpoint | Type | Description | Default | Example |
|-----------|----------|------|-------------|---------|---------|
| `startDate` | GET /api/cost-data | string | Start date (YYYY-MM-DD) | None | `2025-01-01` |
| `endDate` | GET /api/cost-data | string | End date (YYYY-MM-DD) | None | `2025-12-31` |
| `service` | GET /api/cost-data | string | Filter by service name | None | `Amazon Simple Storage Service` |
| `limit` | GET /api/cost-data | integer | Max records to return | 100 | `50` |
| `startDate` | POST /api/cost-data/fetch | string | Start date (YYYY-MM-DD) | 12 months ago | `2025-01-01` |
| `endDate` | POST /api/cost-data/fetch | string | End date (YYYY-MM-DD) | Today | `2025-12-31` |
| `granularity` | POST /api/cost-data/fetch | string | DAILY, MONTHLY, HOURLY | MONTHLY | `DAILY` |

### Phase 1.5: Near-Real-Time Cost Estimation

| Parameter | Endpoint | Type | Description | Default | Range | Example |
|-----------|----------|------|-------------|---------|-------|---------|
| `hours` | GET /api/cost-estimation/current | integer | Time range in hours | 1 | 1-168 | `24` |
| `hours` | GET /api/cost-estimation/service/{service} | integer | Time range in hours | 1 | 1-168 | `6` |

**Supported Services:** `ec2`, `lambda`, `dynamodb`, `s3`, `rds`

---

## Response Field Reference

### Phase 1: Historical Cost Data Response

```json
{
  "success": true,
  "data": [
    {
      "date": "string (YYYY-MM-DD)",
      "service": "string",
      "blendedCost": "number",
      "unblendedCost": "number",
      "currency": "string (USD)"
    }
  ],
  "count": "integer"
}
```

### Phase 1.5: Cost Estimation Response

```json
{
  "success": true,
  "estimates": [
    {
      "service": "string (ec2|lambda|dynamodb|s3|rds)",
      "estimated_cost": "number",
      "currency": "string (USD)",
      "confidence_lower": "number",
      "confidence_upper": "number",
      "timestamp": "string (ISO 8601)",
      "period_start": "string (ISO 8601)",
      "period_end": "string (ISO 8601)",
      "metrics_count": "integer"
    }
  ],
  "total_cost": "number",
  "currency": "string (USD)",
  "timestamp": "string (ISO 8601)",
  "period": "string"
}
```

**Field Descriptions:**
- `estimated_cost`: Estimated cost for the service in the time period
- `confidence_lower`: Lower bound of 95% confidence interval
- `confidence_upper`: Upper bound of 95% confidence interval
- `metrics_count`: Number of metric data points used for estimation
- `period`: Human-readable time period (e.g., "1 hour", "24 hours")

---

## Rate Limiting

### API Gateway Limits

- **Default:** 10,000 requests per second
- **Burst:** 5,000 requests

### AWS Service Limits

- **Cost Explorer:** 100 requests per second (with retry logic)
- **CloudWatch:** 1,000,000 requests per month (Free Tier)
- **Pricing API:** No documented limit (low usage expected)

**Best Practices:**
- Cache estimation results for 5-10 minutes
- Use appropriate time ranges (avoid very short periods with high frequency)
- Implement exponential backoff for retries

---

## Monitoring API Usage

### Check CloudWatch Logs

```bash
# Phase 1 operations
aws logs tail /aws/lambda/costguard-cost-data-handler --follow --filter-pattern "fetch"

# Phase 1.5 operations
aws logs tail /aws/lambda/costguard-cost-data-handler --follow --filter-pattern "estimation"
```

### Check API Gateway Metrics

```bash
# Request count
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=costguard-cost-data-api \
  --start-time 2025-02-21T00:00:00Z \
  --end-time 2025-02-21T23:59:59Z \
  --period 3600 \
  --statistics Sum

# Latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=costguard-cost-data-api \
  --start-time 2025-02-21T00:00:00Z \
  --end-time 2025-02-21T23:59:59Z \
  --period 3600 \
  --statistics Average,Maximum
```

---

## Troubleshooting

### Issue: Estimation returns zero cost

**Possible Causes:**
1. No resources running during time period
2. CloudWatch metrics not available yet (new resources)
3. Pricing data not cached

**Solutions:**
- Verify resources are running: `aws ec2 describe-instances`
- Wait 5-10 minutes for metrics to populate
- Check CloudWatch Logs for pricing errors

### Issue: High latency on estimation requests

**Possible Causes:**
1. Large time range (many metrics to process)
2. Cold start (Lambda initialization)
3. Pricing data refresh in progress

**Solutions:**
- Use smaller time ranges (1-6 hours)
- Implement result caching
- Pre-warm Lambda with scheduled invocations

### Issue: Authentication errors

**Possible Causes:**
1. Invalid API key
2. API key not associated with usage plan
3. API key expired

**Solutions:**
- Verify API key: `aws apigateway get-api-keys`
- Check usage plan association
- Regenerate API key if needed
```

---

## Additional Resources

- [AWS Cost Explorer API Documentation](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html)
- [DynamoDB Query Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.html)
- [API Gateway Authentication](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-key-source.html)
