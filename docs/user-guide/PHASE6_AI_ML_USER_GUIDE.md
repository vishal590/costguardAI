# Phase 6: AI/ML Workload Cost Management - User Guide

> **Source review note (October 3, 2026):** Use [current API contracts](../technical/api-design.md) and [known limitations](../technical/documentation-code-sync.md) for stack URLs, routing and current behavior. Sample responses, timing and savings below are illustrative or historical; this pass did not execute requests or verify frontend/live AWS behavior.

**Last Updated:** March 3, 2026  
**API Endpoint:** https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/  
**Status:** ✅ DEPLOYED & OPERATIONAL

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [GPU Cost Tracking](#gpu-cost-tracking)
4. [Workload Classification](#workload-classification)
5. [Cost Per Inference](#cost-per-inference)
6. [Cost Per Training](#cost-per-training)
7. [Spot Instance Recommendations](#spot-instance-recommendations)
8. [SageMaker Cost Tracking](#sagemaker-cost-tracking)
9. [Bedrock Cost Tracking](#bedrock-cost-tracking)
10. [Multi-Account GPU Costs](#multi-account-gpu-costs)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)

---

## Overview

Phase 6 provides specialized cost management for AI/ML workloads, including:

- **GPU Cost Tracking** - Monitor GPU instance costs by workload type
- **Workload Classification** - Automatically classify training vs inference workloads
- **Cost Per Inference** - Calculate cost per model inference
- **Cost Per Training** - Track training job costs
- **Spot Recommendations** - Get spot instance recommendations (up to 70% savings)
- **SageMaker Tracking** - Monitor SageMaker training, inference, and notebooks
- **Bedrock Tracking** - Track Bedrock model invocations and token usage
- **Multi-Account Support** - Aggregate GPU costs across AWS accounts

---

## Getting Started

### Prerequisites

- AWS account with GPU instances or AI/ML services
- API access to CostGuard Phase 6 endpoints
- Basic understanding of AWS Cost Explorer

### Base URL

```
https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/
```

### Authentication

Currently uses AWS IAM authentication. Ensure your AWS credentials are configured.

---

## GPU Cost Tracking

### Get GPU Costs

Track GPU instance costs over a date range.

**Endpoint:** `GET /gpu-costs`

**Parameters:**
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `instance_type` (optional): Filter by instance type (e.g., "p3.2xlarge")
- `workload_type` (optional): Filter by workload (training, inference, idle)

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/gpu-costs?start_date=2026-03-01&end_date=2026-03-31"
```

**Response:**
```json
{
  "total_cost": 1250.50,
  "gpu_hours": 500,
  "cost_per_gpu_hour": 2.50,
  "breakdown_by_workload": {
    "training": 800.00,
    "inference": 350.50,
    "idle": 100.00
  },
  "breakdown_by_instance_type": {
    "p3.2xlarge": 600.00,
    "p3.8xlarge": 650.50
  }
}
```

### Get Idle GPUs

Identify GPU instances with low utilization.

**Endpoint:** `GET /idle-gpus`

**Parameters:**
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `threshold` (optional): Utilization threshold (default: 10%)

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/idle-gpus?start_date=2026-03-01&end_date=2026-03-31&threshold=15"
```

**Response:**
```json
{
  "idle_gpus": [
    {
      "instance_id": "i-1234567890abcdef0",
      "instance_type": "p3.2xlarge",
      "avg_utilization": 5.2,
      "cost": 120.00,
      "potential_savings": 120.00,
      "recommendation": "Stop or terminate instance"
    }
  ],
  "total_wasted_cost": 120.00,
  "total_potential_savings": 120.00
}
```

### GPU Prevention

Stop or terminate idle GPU instances.

**Endpoint:** `POST /gpu-prevention`

**Parameters:**
- `start_date` (required): Start date for analysis
- `end_date` (required): End date for analysis
- `action` (required): "stop" or "terminate"
- `dry_run` (optional): Preview actions without executing (default: true)

**Example:**
```bash
curl -X POST "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/gpu-prevention" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-03-01",
    "end_date": "2026-03-31",
    "action": "stop",
    "dry_run": true
  }'
```

---

## Workload Classification

### Get Workload Classification

Retrieve classification for a specific instance.

**Endpoint:** `GET /workload-classification`

**Parameters:**
- `instance_id` (required): EC2 instance ID

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/workload-classification?instance_id=i-1234567890abcdef0"
```

**Response:**
```json
{
  "instance_id": "i-1234567890abcdef0",
  "workload_type": "training",
  "confidence": 0.95,
  "classification_method": "cloudwatch-metrics",
  "gpu_utilization_avg": 85.5,
  "timestamp": "2026-03-03T10:00:00Z"
}
```

### Set Manual Classification

Manually classify a workload.

**Endpoint:** `POST /workload-classification`

**Body:**
```json
{
  "instance_id": "i-1234567890abcdef0",
  "workload_type": "training",
  "model_name": "bert-large"
}
```

**Example:**
```bash
curl -X POST "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/workload-classification" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "i-1234567890abcdef0",
    "workload_type": "training",
    "model_name": "bert-large"
  }'
```

---

## Cost Per Inference

### Get Cost Per Inference

Calculate cost per model inference.

**Endpoint:** `GET /cost-per-inference`

**Parameters:**
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `model` (optional): Filter by model name

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/cost-per-inference?start_date=2026-03-01&end_date=2026-03-31&model=bert-large"
```

**Response:**
```json
{
  "model": "bert-large",
  "total_inferences": 1000000,
  "total_cost": 500.00,
  "cost_per_inference": 0.0005,
  "cost_per_1000_inferences": 0.50,
  "breakdown_by_instance_type": {
    "p3.2xlarge": {
      "inferences": 600000,
      "cost": 300.00,
      "cost_per_inference": 0.0005
    },
    "g4dn.xlarge": {
      "inferences": 400000,
      "cost": 200.00,
      "cost_per_inference": 0.0005
    }
  }
}
```

### Get Inference Trends

Track inference cost trends over time.

**Endpoint:** `GET /inference-trends`

**Parameters:**
- `model` (required): Model name
- `days` (optional): Number of days (default: 30)

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/inference-trends?model=bert-large&days=30"
```

---

## Cost Per Training

### Get Cost Per Training

Calculate cost for a specific training job.

**Endpoint:** `GET /cost-per-training`

**Parameters:**
- `job_id` (required): Training job ID

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/cost-per-training?job_id=training-job-123"
```

**Response:**
```json
{
  "job_id": "training-job-123",
  "model": "bert-large",
  "total_cost": 1250.00,
  "duration_hours": 24,
  "cost_per_hour": 52.08,
  "instance_type": "p3.8xlarge",
  "gpu_hours": 192,
  "cost_per_gpu_hour": 6.51
}
```

### Compare Training Costs

Compare training costs across different runs.

**Endpoint:** `GET /training-comparison`

**Parameters:**
- `model` (required): Model name
- `limit` (optional): Number of jobs to compare (default: 10)

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/training-comparison?model=bert-large&limit=5"
```

---

## Spot Instance Recommendations

### Get Spot Recommendations

Get spot instance recommendations for cost savings.

**Endpoint:** `GET /spot-recommendations`

**Parameters:**
- `workload_id` (required): Workload identifier
- `instance_type` (optional): Current instance type

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/spot-recommendations?workload_id=training-job-123&instance_type=p3.2xlarge"
```

**Response:**
```json
{
  "current_instance": "p3.2xlarge",
  "current_cost_per_hour": 3.06,
  "recommendations": [
    {
      "instance_type": "p3.2xlarge",
      "spot_price": 0.92,
      "savings_percent": 70,
      "savings_per_hour": 2.14,
      "interruption_rate": "5-10%",
      "recommendation": "Highly recommended for training workloads"
    }
  ]
}
```

### Calculate Spot Savings

Calculate potential savings from spot instances.

**Endpoint:** `GET /spot-savings`

**Parameters:**
- `current_instance` (required): Current instance type
- `hours_per_month` (optional): Usage hours (default: 730)

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/spot-savings?current_instance=p3.2xlarge&hours_per_month=500"
```

---

## SageMaker Cost Tracking

### Get SageMaker Costs

Track SageMaker costs across all services.

**Endpoint:** `GET /sagemaker-costs`

**Parameters:**
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/sagemaker-costs?start_date=2026-03-01&end_date=2026-03-31"
```

**Response:**
```json
{
  "total_cost": 2500.00,
  "breakdown": {
    "training": 1500.00,
    "inference": 800.00,
    "notebooks": 200.00
  },
  "top_endpoints": [
    {
      "endpoint_name": "bert-inference",
      "cost": 500.00,
      "invocations": 1000000
    }
  ]
}
```

### Get Idle SageMaker Endpoints

Identify idle SageMaker endpoints.

**Endpoint:** `GET /sagemaker-idle-endpoints`

**Parameters:**
- `threshold` (optional): Invocation threshold (default: 10 per hour)

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/sagemaker-idle-endpoints?threshold=5"
```

**Response:**
```json
{
  "threshold": 5,
  "idle_endpoint_count": 2,
  "idle_endpoints": [
    {
      "endpoint_name": "old-model-endpoint",
      "instance_type": "ml.m5.xlarge",
      "cost_per_hour": 0.23,
      "avg_invocations_per_hour": 2,
      "monthly_waste": 167.90,
      "recommendation": "Delete endpoint"
    }
  ],
  "total_wasted_cost_per_hour": 0.46,
  "estimated_monthly_waste": 335.80
}
```

---

## Bedrock Cost Tracking

### Get Bedrock Costs

Track Bedrock model invocation costs.

**Endpoint:** `GET /bedrock-costs`

**Parameters:**
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `model` (optional): Filter by model ID

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/bedrock-costs?start_date=2026-03-01&end_date=2026-03-31"
```

**Response:**
```json
{
  "total_cost": 150.00,
  "total_invocations": 100000,
  "cost_per_invocation": 0.0015,
  "breakdown_by_model": {
    "amazon.nova-lite-v1:0": {
      "invocations": 60000,
      "cost": 90.00,
      "cost_per_invocation": 0.0015
    },
    "anthropic.claude-3-sonnet": {
      "invocations": 40000,
      "cost": 60.00,
      "cost_per_invocation": 0.0015
    }
  }
}
```

### Get Bedrock Cost Per Invocation

Calculate cost per invocation for a specific model.

**Endpoint:** `GET /bedrock-cost-per-invocation`

**Parameters:**
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `model` (required): Model ID

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/bedrock-cost-per-invocation?start_date=2026-03-01&end_date=2026-03-31&model=amazon.nova-lite-v1:0"
```

---

## Multi-Account GPU Costs

### Get Multi-Account GPU Costs

Aggregate GPU costs across multiple AWS accounts.

**Endpoint:** `GET /multi-account/gpu-costs`

**Parameters:**
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `account_ids` (optional): Comma-separated account IDs

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/multi-account/gpu-costs?start_date=2026-03-01&end_date=2026-03-31"
```

**Response:**
```json
{
  "total_cost": 5000.00,
  "account_count": 3,
  "breakdown_by_account": {
    "123456789012": {
      "cost": 2000.00,
      "gpu_hours": 800
    },
    "234567890123": {
      "cost": 2000.00,
      "gpu_hours": 800
    },
    "345678901234": {
      "cost": 1000.00,
      "gpu_hours": 400
    }
  }
}
```

### Get Top GPU Accounts

Identify accounts with highest GPU costs.

**Endpoint:** `GET /multi-account/top-gpu-accounts`

**Parameters:**
- `org_id` (required): Organization ID
- `account_ids` (required): Comma-separated account IDs
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `limit` (optional): Number of accounts (default: 10)

**Example:**
```bash
curl "https://chcymuh4qi.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml/multi-account/top-gpu-accounts?org_id=o-123456&account_ids=123456789012,234567890123&start_date=2026-03-01&end_date=2026-03-31&limit=5"
```

---

## Best Practices

### 1. Regular Cost Monitoring

- Check GPU costs weekly
- Monitor idle GPU instances daily
- Review workload classifications monthly

### 2. Workload Optimization

- Use spot instances for training (up to 70% savings)
- Classify workloads accurately for better cost tracking
- Stop idle GPUs immediately

### 3. SageMaker Optimization

- Delete idle endpoints
- Use auto-scaling for inference endpoints
- Monitor invocation rates

### 4. Bedrock Optimization

- Cache responses when possible
- Use appropriate models for tasks
- Monitor token usage

### 5. Multi-Account Management

- Aggregate costs across accounts
- Identify high-cost accounts
- Implement cost allocation tags

---

## Troubleshooting

### Common Issues

#### 1. 400 Bad Request - Missing Parameters

**Error:**
```json
{
  "error": {
    "code": "MISSING_PARAMETER",
    "message": "start_date and end_date are required"
  }
}
```

**Solution:** Ensure all required parameters are provided in the correct format (YYYY-MM-DD for dates).

#### 2. GPU Utilization Has No Metrics

The current GPU-utilization endpoint is implemented. Supply `start_date` and `end_date`, optionally filtering by `instance_id` or `instance_type`. Missing metrics return null `avg_utilization` and an empty `gpu_utilization_pattern`; check the instance and available CloudWatch metrics rather than treating it as a future endpoint.

#### 3. No Data Returned

**Issue:** Endpoint returns empty results.

**Solution:**
- Verify date range includes actual usage
- Check if GPU instances were running during the period
- Ensure workload classification is set

#### 4. High Costs Detected

**Issue:** Unexpected high GPU costs.

**Solution:**
1. Check for idle GPUs: `GET /idle-gpus`
2. Review workload classifications
3. Consider spot instances: `GET /spot-recommendations`
4. Stop unused instances: `POST /gpu-prevention`

---

## Support

For issues or questions:
- Check [PHASE6_ENDPOINT_TEST_REPORT.md](../PHASE6_ENDPOINT_TEST_REPORT.md) for endpoint status
- Review [DEPLOYMENT_ISSUES_AND_FIXES.md](../deployment/DEPLOYMENT_BUGS_AND_FIXES.md) for common problems
- See [PROJECT_STATUS.md](../PROJECT_STATUS.md) for overall system status

---

**Last Updated:** March 3, 2026  
**Version:** 1.0  
**Status:** Production Ready
