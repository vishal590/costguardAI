# Phase 6: AI/ML Workload Cost Management API Documentation

**Version:** 1.0  
**Last Updated:** February 2026  
**Base URL:** `https://api.costguard.ai` (or your API Gateway URL)

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Common Error Responses](#common-error-responses)
4. [Rate Limits](#rate-limits)
5. [GPU Cost Tracking Endpoints](#gpu-cost-tracking-endpoints)
6. [Workload Classification Endpoints](#workload-classification-endpoints)
7. [Cost-Per-Inference Endpoints](#cost-per-inference-endpoints)
8. [Cost-Per-Training Endpoints](#cost-per-training-endpoints)
9. [Spot Instance Recommendation Endpoints](#spot-instance-recommendation-endpoints)
10. [SageMaker Cost Endpoints](#sagemaker-cost-endpoints)
11. [Bedrock Cost Endpoints](#bedrock-cost-endpoints)
12. [GPU Prevention Endpoints](#gpu-prevention-endpoints)
13. [Multi-Account GPU Endpoints](#multi-account-gpu-endpoints)

---

## Overview

Phase 6 provides AI/ML-specific cost management capabilities for CostGuard AI, focusing on:

- **GPU Cost Tracking**: Track EC2 GPU instance costs by workload type (training, inference, idle)
- **Workload Classification**: Automatically classify GPU workloads using CloudWatch metrics
- **Cost-Per-Inference**: Calculate cost per inference request across multiple sources
- **Cost-Per-Training**: Calculate cost per training job including all cost components
- **Spot Instance Recommendations**: Identify training workloads suitable for spot instances
- **SageMaker Cost Tracking**: Track SageMaker training, inference, and notebook costs
- **Bedrock Cost Tracking**: Track Bedrock model invocation costs and token usage
- **GPU Prevention**: Automatically stop or terminate idle GPU instances
- **Multi-Account Support**: Aggregate GPU costs across AWS Organizations

**Key Differentiator:** NO competitor (CloudZero, nOps, Vantage) provides GPU-specific cost tracking by workload type.

---

## Authentication

All API endpoints require authentication using an API key.

### API Key Header

```http
X-API-Key: your-api-key-here
```

### Example Request

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```


---

## Common Error Responses

All endpoints return consistent error responses in the following format:

### Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "additional": "context"
    }
  }
}
```

### Common Error Codes

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 400 | `MISSING_PARAMETER` | Required parameter is missing |
| 400 | `INVALID_DATE_FORMAT` | Date must be in YYYY-MM-DD format |
| 400 | `INVALID_DATE_RANGE` | start_date must be before end_date |
| 400 | `INVALID_PARAMETER` | Parameter value is invalid |
| 401 | `UNAUTHORIZED` | API key is missing or invalid |
| 404 | `NOT_FOUND` | Resource not found |
| 404 | `NO_DATA` | No data found for the specified criteria |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Internal server error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

### Example Error Response

```json
{
  "error": {
    "code": "INVALID_DATE_FORMAT",
    "message": "Dates must be in YYYY-MM-DD format"
  }
}
```

---

## Rate Limits

- **Default Rate Limit**: 100 requests per minute per API key
- **Burst Limit**: 200 requests per minute
- **Daily Limit**: 10,000 requests per day

Rate limit headers are included in all responses:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

---

## GPU Cost Tracking Endpoints

### 1. Get GPU Costs

Track EC2 GPU instance costs by workload type.

**Endpoint:** `GET /api/ai-ml/gpu-costs`

**Requirements:** API-1.1, FR-1.1, FR-1.3, FR-1.6

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `workload_type` | string | No | Filter by workload type: `training`, `inference`, `idle` |
| `instance_type` | string | No | Filter by instance type (e.g., `p3.2xlarge`) |

**Response:**

```json
{
  "gpu_costs": [
    {
      "date": "2024-01-15",
      "instance_id": "i-1234567890abcdef0",
      "instance_type": "p3.2xlarge",
      "workload_type": "training",
      "cost": 245.50,
      "gpu_hours": 24.0,
      "cost_per_gpu_hour": 10.23,
      "utilization": 85.5,
      "classification_confidence": 0.95
    }
  ],
  "total_cost": 1234.56,
  "total_gpu_hours": 120.5,
  "average_cost_per_gpu_hour": 10.24
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31&workload_type=training" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:**
- Cached: < 2 seconds
- Uncached: < 10 seconds


### 2. Get GPU Utilization

Get GPU utilization metrics for specific instances.

**Endpoint:** `GET /api/ai-ml/gpu-utilization`

**Requirements:** API-1.2

**Status:** Not yet implemented (returns 501)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `instance_id` | string | No | Filter by instance ID |

---

### 3. Get Idle GPUs

Identify GPU instances with low utilization.

**Endpoint:** `GET /api/ai-ml/idle-gpus`

**Requirements:** API-1.3, FR-1.5

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `threshold` | float | No | Utilization threshold percentage (default: 10.0) |

**Response:**

```json
{
  "idle_gpus": [
    {
      "instance_id": "i-1234567890abcdef0",
      "instance_type": "p3.2xlarge",
      "average_utilization": 5.2,
      "idle_hours": 48.5,
      "wasted_cost": 495.75,
      "severity": "high",
      "recommendation": "Consider stopping or terminating this instance"
    }
  ],
  "count": 3,
  "total_wasted_cost": 1487.25,
  "total_idle_hours": 145.5,
  "threshold": 10.0,
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/idle-gpus?start_date=2024-01-01&end_date=2024-01-31&threshold=10" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds

---

## Workload Classification Endpoints

### 4. Get Workload Classification

Get workload classification for a GPU instance.

**Endpoint:** `GET /api/ai-ml/workload-classification`

**Requirements:** API-2.1, FR-2.1, FR-2.2, FR-2.4

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_id` | string | Yes | EC2 instance ID |
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |

**Response:**

```json
{
  "classification": {
    "instance_id": "i-1234567890abcdef0",
    "workload_type": "training",
    "confidence": 0.95,
    "classification_method": "cloudwatch-metrics",
    "gpu_utilization_avg": 85.5,
    "gpu_utilization_pattern": [82.1, 87.3, 85.9, 84.2],
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Classification Rules:**
- **Training**: GPU utilization > 70% continuously for > 1 hour
- **Inference**: GPU utilization 20-70% with frequent spikes
- **Idle**: GPU utilization < 10%

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/workload-classification?instance_id=i-1234567890abcdef0&start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 1 second


### 5. Set Manual Workload Classification

Manually override workload classification for a GPU instance.

**Endpoint:** `POST /api/ai-ml/workload-classification`

**Requirements:** API-2.2, FR-2.3, FR-2.5

**Request Body:**

```json
{
  "instance_id": "i-1234567890abcdef0",
  "workload_type": "training",
  "reason": "Manual classification via API"
}
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_id` | string | Yes | EC2 instance ID |
| `workload_type` | string | Yes | Workload type: `training`, `inference`, or `idle` |
| `reason` | string | No | Reason for manual classification |

**Response:**

```json
{
  "classification": {
    "instance_id": "i-1234567890abcdef0",
    "workload_type": "training",
    "confidence": 1.0,
    "classification_method": "manual-tag",
    "gpu_utilization_avg": 0.0,
    "gpu_utilization_pattern": [],
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "message": "Manual classification set to training for instance i-1234567890abcdef0"
}
```

**Example Request:**

```bash
curl -X POST "https://api.costguard.ai/api/ai-ml/workload-classification" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "i-1234567890abcdef0",
    "workload_type": "training",
    "reason": "Confirmed training workload by ML team"
  }'
```

**Response Time:** < 1 second

---

## Cost-Per-Inference Endpoints

### 6. Get Cost Per Inference

Calculate cost per inference request for a model/endpoint.

**Endpoint:** `GET /api/ai-ml/cost-per-inference`

**Requirements:** API-3.1, FR-3.1, FR-3.4

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `model` | string | No | Model name filter (default: `default-model`) |
| `endpoint` | string | No | Endpoint identifier (default: `default-endpoint`) |

**Response:**

```json
{
  "model": "bert-base-uncased",
  "endpoint": "inference-endpoint-1",
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  },
  "total_requests": 1000000,
  "total_cost": 1234.56,
  "cost_per_inference": 0.00123456,
  "cost_breakdown": {
    "compute_cost": 1000.00,
    "api_cost": 200.00,
    "data_transfer_cost": 34.56
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/cost-per-inference?start_date=2024-01-01&end_date=2024-01-31&model=bert-base-uncased&endpoint=inference-endpoint-1" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds


### 7. Get Inference Trends

Track cost-per-inference trends over time.

**Endpoint:** `GET /api/ai-ml/inference-trends`

**Requirements:** API-3.2, FR-3.5

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model name |
| `endpoint` | string | No | Endpoint identifier (default: `default-endpoint`) |
| `days` | integer | No | Number of days to track (default: 30, max: 90) |

**Response:**

```json
{
  "model": "bert-base-uncased",
  "endpoint": "inference-endpoint-1",
  "days": 30,
  "trends": [
    {
      "date": "2024-01-01",
      "cost_per_inference": 0.00125,
      "total_requests": 35000,
      "total_cost": 43.75
    },
    {
      "date": "2024-01-02",
      "cost_per_inference": 0.00123,
      "total_requests": 38000,
      "total_cost": 46.74
    }
  ]
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/inference-trends?model=bert-base-uncased&endpoint=inference-endpoint-1&days=30" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds

---

## Cost-Per-Training Endpoints

### 8. Get Cost Per Training

Calculate cost per training job.

**Endpoint:** `GET /api/ai-ml/cost-per-training`

**Requirements:** API-4.1, FR-4.1, FR-4.3

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | Yes | Training job identifier |

**Response:**

```json
{
  "job_id": "training-job-123",
  "model": "resnet-50",
  "dataset": "imagenet-1k",
  "date": "2024-01-15",
  "training_hours": 12.5,
  "total_cost": 125.75,
  "cost_per_hour": 10.06,
  "instance_type": "p3.2xlarge",
  "cost_breakdown": {
    "compute_cost": 100.00,
    "storage_cost": 20.00,
    "data_transfer_cost": 5.75
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/cost-per-training?job_id=training-job-123" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds

**Error Responses:**

- `404 JOB_NOT_FOUND`: Training job not found


### 9. Compare Training Costs

Compare training costs across different instance types.

**Endpoint:** `GET /api/ai-ml/training-comparison`

**Requirements:** API-4.2, FR-4.6

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model name |
| `instance_types` | string | Yes | Comma-separated list of instance types |
| `baseline_instance` | string | No | Baseline instance for savings calculation |

**Response:**

```json
{
  "model": "resnet-50",
  "baseline_instance": "p3.2xlarge",
  "comparisons": [
    {
      "instance_type": "p3.2xlarge",
      "estimated_duration_hours": 12.0,
      "estimated_cost": 122.40,
      "cost_per_hour": 10.20,
      "savings_vs_baseline": 0.00,
      "savings_percent": 0.0
    },
    {
      "instance_type": "p3.8xlarge",
      "estimated_duration_hours": 4.0,
      "estimated_cost": 98.80,
      "cost_per_hour": 24.70,
      "savings_vs_baseline": 23.60,
      "savings_percent": 19.28
    },
    {
      "instance_type": "g4dn.xlarge",
      "estimated_duration_hours": 24.0,
      "estimated_cost": 62.40,
      "cost_per_hour": 2.60,
      "savings_vs_baseline": 60.00,
      "savings_percent": 49.02
    }
  ]
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/training-comparison?model=resnet-50&instance_types=p3.2xlarge,p3.8xlarge,g4dn.xlarge&baseline_instance=p3.2xlarge" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds

---

## Spot Instance Recommendation Endpoints

### 10. Get Spot Recommendations

Get spot instance recommendations for a workload.

**Endpoint:** `GET /api/ai-ml/spot-recommendations`

**Requirements:** API-5.1, FR-5.1, FR-5.2, FR-5.4, FR-5.5

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workload_id` | string | Yes | Workload identifier (instance ID or job ID) |
| `include_scenarios` | boolean | No | Include what-if scenarios (default: false) |

**Response:**

```json
{
  "workload_id": "i-1234567890abcdef0",
  "recommendations": [
    {
      "current_instance": "p3.2xlarge",
      "recommended_spot_instance": "p3.2xlarge",
      "suitable": true,
      "reason": "Training workload suitable for spot instances",
      "current_cost": 10.20,
      "spot_cost": 3.06,
      "savings": 7.14,
      "savings_percent": 70.0,
      "interruption_risk": 0.15
    }
  ],
  "what_if_scenarios": [
    {
      "scenario_name": "100% Spot Usage",
      "instance_type": "p3.2xlarge",
      "spot_usage_percent": 100,
      "estimated_savings": 7140.00,
      "estimated_interruptions": 2,
      "recommendation": "High savings with acceptable interruption risk"
    },
    {
      "scenario_name": "50% Spot Usage",
      "instance_type": "p3.2xlarge",
      "spot_usage_percent": 50,
      "estimated_savings": 3570.00,
      "estimated_interruptions": 1,
      "recommendation": "Balanced approach with lower interruption risk"
    }
  ]
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/spot-recommendations?workload_id=i-1234567890abcdef0&include_scenarios=true" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds


### 11. Calculate Spot Savings

Calculate potential savings from switching to spot instances.

**Endpoint:** `GET /api/ai-ml/spot-savings`

**Requirements:** API-5.2, FR-5.2

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `current_instance` | string | Yes | Current instance type |
| `spot_instance` | string | No | Spot instance type (defaults to same as current) |

**Response:**

```json
{
  "current_instance": "p3.2xlarge",
  "spot_instance": "p3.2xlarge",
  "pricing": {
    "on_demand_price": 10.20,
    "spot_price": 3.06
  },
  "savings": {
    "savings_per_hour": 7.14,
    "savings_percent": 70.0,
    "estimated_monthly_savings": 5140.80
  },
  "interruption_risk": 0.15
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/spot-savings?current_instance=p3.2xlarge" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds

---

## SageMaker Cost Endpoints

### 12. Get SageMaker Costs

Track SageMaker costs by job type.

**Endpoint:** `GET /api/ai-ml/sagemaker-costs`

**Requirements:** API-6.1, FR-6.1, FR-6.2, FR-6.3, FR-6.4

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `job_type` | string | No | Filter by job type: `training`, `inference`, `notebook` |

**Response:**

```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "training_costs": 5000.00,
  "inference_costs": 2000.00,
  "notebook_costs": 500.00,
  "total_cost": 7500.00,
  "job_breakdown": [
    {
      "job_name": "training-job-123",
      "job_type": "training",
      "instance_type": "ml.p3.2xlarge",
      "start_time": "2024-01-15T10:00:00Z",
      "end_time": "2024-01-15T22:30:00Z",
      "duration_hours": 12.5,
      "compute_cost": 100.00,
      "storage_cost": 20.00,
      "data_transfer_cost": 5.00,
      "total_cost": 125.00
    }
  ]
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/sagemaker-costs?start_date=2024-01-01&end_date=2024-01-31&job_type=training" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds


### 13. Get SageMaker Idle Endpoints

Identify idle SageMaker inference endpoints.

**Endpoint:** `GET /api/ai-ml/sagemaker-idle-endpoints`

**Requirements:** API-6.2, FR-6.6

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `threshold` | integer | No | Minimum requests per hour (default: 10) |

**Response:**

```json
{
  "threshold": 10,
  "idle_endpoint_count": 3,
  "idle_endpoints": [
    {
      "endpoint_name": "inference-endpoint-1",
      "instance_type": "ml.m5.xlarge",
      "instance_count": 2,
      "requests_per_hour": 5,
      "avg_latency_ms": 150.5,
      "cost_per_hour": 0.384,
      "is_idle": true,
      "recommendation": "Consider scaling down or deleting this endpoint. Current cost: $0.38/hour"
    }
  ],
  "total_wasted_cost_per_hour": 1.152,
  "estimated_monthly_waste": 829.44
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/sagemaker-idle-endpoints?threshold=10" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds

---

## Bedrock Cost Endpoints

### 14. Get Bedrock Costs

Track Bedrock model invocation costs.

**Endpoint:** `GET /api/ai-ml/bedrock-costs`

**Requirements:** API-7.1, FR-7.1, FR-7.2

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `model` | string | No | Filter by model ID |

**Response:**

```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "model_filter": null,
  "total_models": 3,
  "models": [
    {
      "model_id": "anthropic.claude-v2",
      "invocations": 50000,
      "input_tokens": 5000000,
      "output_tokens": 2500000,
      "total_tokens": 7500000,
      "total_cost": 187.50,
      "cost_per_invocation": 0.00375,
      "cost_per_1k_tokens": 0.025
    },
    {
      "model_id": "amazon.titan-text-express-v1",
      "invocations": 100000,
      "input_tokens": 8000000,
      "output_tokens": 4000000,
      "total_tokens": 12000000,
      "total_cost": 120.00,
      "cost_per_invocation": 0.0012,
      "cost_per_1k_tokens": 0.01
    }
  ],
  "totals": {
    "total_cost": 307.50,
    "total_invocations": 150000,
    "total_input_tokens": 13000000,
    "total_output_tokens": 6500000,
    "total_tokens": 19500000,
    "avg_cost_per_invocation": 0.00205
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/bedrock-costs?start_date=2024-01-01&end_date=2024-01-31&model=anthropic.claude-v2" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds


### 15. Get Bedrock Cost Per Invocation

Calculate cost per invocation for a specific Bedrock model.

**Endpoint:** `GET /api/ai-ml/bedrock-cost-per-invocation`

**Requirements:** API-7.2, FR-7.3, FR-7.4

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `model` | string | Yes | Model ID |

**Response:**

```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "model_id": "anthropic.claude-v2",
  "cost_per_invocation": 0.00375,
  "total_invocations": 50000,
  "total_cost": 187.50,
  "token_usage": {
    "input_tokens": 5000000,
    "output_tokens": 2500000,
    "total_tokens": 7500000,
    "avg_input_tokens_per_invocation": 100.0,
    "avg_output_tokens_per_invocation": 50.0
  },
  "cost_breakdown": {
    "cost_per_1k_input_tokens": 0.0375,
    "cost_per_1k_output_tokens": 0.075,
    "cost_per_1k_tokens": 0.025
  },
  "recommendations": [
    {
      "recommended_model": "amazon.titan-text-express-v1",
      "current_cost_per_1k_tokens": 0.025,
      "recommended_cost_per_1k_tokens": 0.01,
      "savings_percent": 60.0,
      "estimated_monthly_savings": 3375.00,
      "reason": "Similar performance with lower cost for short responses"
    }
  ]
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/bedrock-cost-per-invocation?start_date=2024-01-01&end_date=2024-01-31&model=anthropic.claude-v2" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds

**Error Responses:**

- `404 NO_DATA`: No cost data found for the specified model and date range

---

## GPU Prevention Endpoints

### 16. Run GPU Prevention Cycle

Execute prevention cycle to stop or terminate idle GPU instances.

**Endpoint:** `POST /api/ai-ml/gpu-prevention`

**Requirements:** IR-2.3

**Request Body:**

```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "threshold": 10.0,
  "dry_run": true
}
```

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `threshold` | float | No | Utilization threshold percentage (default: 10.0) |
| `dry_run` | boolean | No | Dry run mode (default: true) |

**Response:**

```json
{
  "success": true,
  "idle_gpus_found": 5,
  "actions_planned": 3,
  "actions_executed": 0,
  "total_savings": 1500.00,
  "dry_run": true,
  "idle_gpus": [
    {
      "instance_id": "i-1234567890abcdef0",
      "instance_type": "p3.2xlarge",
      "average_utilization": 5.2,
      "idle_hours": 48.5,
      "wasted_cost": 495.75,
      "severity": "high",
      "action": "stop"
    }
  ]
}
```

**Example Request:**

```bash
curl -X POST "https://api.costguard.ai/api/ai-ml/gpu-prevention" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "threshold": 10.0,
    "dry_run": true
  }'
```

**Response Time:** < 5 seconds


### 17. Get GPU Cost Savings

Get GPU cost savings from prevention actions.

**Endpoint:** `GET /api/ai-ml/gpu-cost-savings`

**Requirements:** IR-2.3

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |

**Response:**

```json
{
  "period_start": "2024-01-01",
  "period_end": "2024-01-31",
  "total_savings": 5000.00,
  "actions_count": 10,
  "instances_stopped": 7,
  "instances_terminated": 3,
  "avg_idle_hours": 48.5,
  "breakdown_by_instance_type": {
    "p3.2xlarge": 1500.00,
    "g4dn.xlarge": 500.00,
    "g5.2xlarge": 3000.00
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-cost-savings?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 2 seconds

---

## Multi-Account GPU Endpoints

### 18. Get Multi-Account GPU Costs

Aggregate GPU costs across multiple AWS accounts in an organization.

**Endpoint:** `GET /api/ai-ml/multi-account/gpu-costs`

**Requirements:** IR-2.5, NFR-3.4

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `org_id` | string | Yes | Organization ID |
| `account_ids` | string | Yes | Comma-separated list of account IDs |
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `role_name` | string | No | Cross-account role name (default: `CostGuardCollectorRole`) |
| `external_id` | string | No | External ID for role assumption |

**Response:**

```json
{
  "org_id": "o-1234567890",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "total_gpu_cost": 25000.00,
  "account_count": 3,
  "costs_by_account": {
    "123456789012": 10000.00,
    "234567890123": 8000.00,
    "345678901234": 7000.00
  },
  "costs_by_workload_type": {
    "training": 15000.00,
    "inference": 8000.00,
    "idle": 2000.00
  },
  "costs_by_instance_type": {
    "p3.2xlarge": 8000.00,
    "p3.8xlarge": 12000.00,
    "g4dn.xlarge": 5000.00
  },
  "gpu_hours_by_account": {
    "123456789012": 1000.0,
    "234567890123": 800.0,
    "345678901234": 700.0
  },
  "utilization_by_account": {
    "123456789012": 75.5,
    "234567890123": 82.3,
    "345678901234": 68.9
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/multi-account/gpu-costs?org_id=o-1234567890&account_ids=123456789012,234567890123,345678901234&start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 15 seconds (depends on number of accounts)


### 19. Get Multi-Account GPU Utilization

Get organization-wide GPU utilization metrics.

**Endpoint:** `GET /api/ai-ml/multi-account/gpu-utilization`

**Requirements:** IR-2.5, NFR-3.4

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `org_id` | string | Yes | Organization ID |
| `account_ids` | string | Yes | Comma-separated list of account IDs |
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |

**Response:**

```json
{
  "org_id": "o-1234567890",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "organization_avg_utilization": 75.6,
  "total_gpu_hours": 2500.0,
  "accounts": [
    {
      "account_id": "123456789012",
      "avg_utilization": 75.5,
      "gpu_hours": 1000.0,
      "instance_count": 10
    },
    {
      "account_id": "234567890123",
      "avg_utilization": 82.3,
      "gpu_hours": 800.0,
      "instance_count": 8
    },
    {
      "account_id": "345678901234",
      "avg_utilization": 68.9,
      "gpu_hours": 700.0,
      "instance_count": 7
    }
  ],
  "utilization_by_workload_type": {
    "training": 85.2,
    "inference": 65.8,
    "idle": 5.3
  }
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/multi-account/gpu-utilization?org_id=o-1234567890&account_ids=123456789012,234567890123,345678901234&start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 15 seconds

---

### 20. Get Top GPU Spending Accounts

Get top GPU spending accounts in an organization.

**Endpoint:** `GET /api/ai-ml/multi-account/top-gpu-accounts`

**Requirements:** IR-2.5, NFR-3.4

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `org_id` | string | Yes | Organization ID |
| `account_ids` | string | Yes | Comma-separated list of account IDs |
| `start_date` | string | Yes | Start date (YYYY-MM-DD) |
| `end_date` | string | Yes | End date (YYYY-MM-DD) |
| `limit` | integer | No | Number of top accounts to return (default: 5) |

**Response:**

```json
{
  "top_accounts": [
    {
      "account_id": "123456789012",
      "account_name": "ML Production",
      "total_gpu_cost": 10000.00,
      "gpu_hours": 1000.0,
      "avg_utilization": 75.5,
      "cost_per_gpu_hour": 10.00,
      "workload_breakdown": {
        "training": 6000.00,
        "inference": 3500.00,
        "idle": 500.00
      }
    },
    {
      "account_id": "234567890123",
      "account_name": "ML Development",
      "total_gpu_cost": 8000.00,
      "gpu_hours": 800.0,
      "avg_utilization": 82.3,
      "cost_per_gpu_hour": 10.00,
      "workload_breakdown": {
        "training": 5000.00,
        "inference": 2500.00,
        "idle": 500.00
      }
    }
  ]
}
```

**Example Request:**

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/multi-account/top-gpu-accounts?org_id=o-1234567890&account_ids=123456789012,234567890123,345678901234&start_date=2024-01-01&end_date=2024-01-31&limit=5" \
  -H "X-API-Key: your-api-key-here"
```

**Response Time:** < 15 seconds

---

## Appendix

### Supported GPU Instance Types

Phase 6 tracks the following EC2 GPU instance types:

| Instance Family | Instance Types | Use Case |
|----------------|----------------|----------|
| **P3** | p3.2xlarge, p3.8xlarge, p3.16xlarge, p3dn.24xlarge | General-purpose GPU compute |
| **P4** | p4d.24xlarge | High-performance training |
| **P5** | p5.48xlarge | Latest generation training |
| **G4** | g4dn.xlarge, g4dn.2xlarge, g4dn.4xlarge, g4dn.8xlarge, g4dn.12xlarge, g4dn.16xlarge | Cost-effective inference |
| **G5** | g5.xlarge, g5.2xlarge, g5.4xlarge, g5.8xlarge, g5.12xlarge, g5.16xlarge, g5.24xlarge, g5.48xlarge | Graphics and ML inference |
| **G6** | g6.xlarge, g6.2xlarge, g6.4xlarge, g6.8xlarge, g6.12xlarge, g6.16xlarge | Latest generation inference |


### Supported Bedrock Models

Phase 6 tracks costs for the following Bedrock models:

| Model ID | Provider | Use Case |
|----------|----------|----------|
| `anthropic.claude-v2` | Anthropic | General-purpose text generation |
| `anthropic.claude-v2:1` | Anthropic | Improved Claude v2 |
| `anthropic.claude-3-sonnet` | Anthropic | Balanced performance |
| `anthropic.claude-3-opus` | Anthropic | Highest capability |
| `anthropic.claude-instant-v1` | Anthropic | Fast, cost-effective |
| `amazon.titan-text-express-v1` | Amazon | Cost-effective text generation |
| `amazon.titan-text-lite-v1` | Amazon | Lightweight text generation |
| `amazon.titan-embed-text-v1` | Amazon | Text embeddings |
| `meta.llama2-13b-chat-v1` | Meta | Open-source chat model |
| `meta.llama2-70b-chat-v1` | Meta | Large open-source model |
| `cohere.command-text-v14` | Cohere | Command and generation |
| `ai21.j2-ultra-v1` | AI21 Labs | Advanced text generation |

### Date Format

All date parameters must be in ISO 8601 format: `YYYY-MM-DD`

**Examples:**
- Valid: `2024-01-15`, `2024-12-31`
- Invalid: `01/15/2024`, `15-01-2024`, `2024-1-15`

### Caching

Phase 6 implements aggressive caching to minimize AWS API calls and stay within Free Tier limits:

- **Cache TTL**: 24 hours for GPU costs, SageMaker costs, and Bedrock costs
- **Cache Hit Rate Target**: 60%+
- **Cache Invalidation**: Automatic after TTL expiration

Cached responses include the same data as fresh responses. The system automatically manages cache invalidation.

### Pagination

Currently, Phase 6 endpoints do not support pagination. All results are returned in a single response. Future versions may add pagination for large result sets.

### Versioning

The API uses URL-based versioning. The current version is `v1` (implicit in the base URL).

Future versions will be accessible via:
- `https://api.costguard.ai/v2/api/ai-ml/...`

### Best Practices

1. **Use Caching**: Query the same date ranges within 24 hours to benefit from caching
2. **Batch Requests**: Combine multiple queries where possible to reduce API calls
3. **Filter Early**: Use query parameters to filter data at the API level rather than client-side
4. **Monitor Rate Limits**: Check rate limit headers and implement exponential backoff
5. **Handle Errors Gracefully**: Implement retry logic for 5xx errors with exponential backoff
6. **Use Appropriate Date Ranges**: Limit date ranges to 90 days or less for optimal performance
7. **Leverage What-If Scenarios**: Use `include_scenarios=true` for spot recommendations to get comprehensive analysis

### Support

For API support, documentation updates, or feature requests:

- **Email**: api-support@costguard.ai
- **Documentation**: https://docs.costguard.ai
- **Status Page**: https://status.costguard.ai
- **GitHub Issues**: https://github.com/costguard-ai/api/issues

---

**Document Version:** 1.0  
**Last Updated:** February 2026  
**API Version:** v1

