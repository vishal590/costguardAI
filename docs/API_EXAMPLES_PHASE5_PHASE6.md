# API Examples - Phase 5 & Phase 6

This document provides comprehensive examples for Phase 5 (Multi-Account Cost Management) and Phase 6 (AI/ML Workload Cost Management).

## Table of Contents

- [Phase 5: Multi-Account Cost Management](#phase-5-multi-account-cost-management)
- [Phase 6: AI/ML Workload Cost Management](#phase-6-aiml-workload-cost-management)

---

## Phase 5: Multi-Account Cost Management

Phase 5 provides enterprise-grade multi-account cost management with AWS Organizations integration, cross-account cost aggregation, and tag-based allocation.

**Base URL:** `https://your-multi-account-api-id.execute-api.us-east-1.amazonaws.com/prod/api/multi-account`

### Setup

```bash
export MULTI_ACCOUNT_API_ENDPOINT="https://your-multi-account-api-id.execute-api.us-east-1.amazonaws.com/prod"
export API_KEY="your-api-key-here"
```

---

### GET /api/multi-account/organizations

Get AWS Organizations details including organization ID, master account, and feature set.

#### Example 1: Get Organization Details

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/multi-account/organizations"
```

**Response (Success):**
```json
{
  "success": true,
  "organization": {
    "id": "o-abc123def456",
    "arn": "arn:aws:organizations::123456789012:organization/o-abc123def456",
    "master_account_id": "123456789012",
    "master_account_email": "admin@example.com",
    "feature_set": "ALL",
    "available_policy_types": [
      "SERVICE_CONTROL_POLICY",
      "TAG_POLICY",
      "BACKUP_POLICY",
      "AISERVICES_OPT_OUT_POLICY"
    ]
  }
}
```

**Response (No Organization):**
```json
{
  "success": false,
  "error": {
    "code": "NO_ORGANIZATION",
    "message": "AWS account is not part of an organization"
  }
}
```

---

### GET /api/multi-account/accounts

List all accounts in the organization with their status and metadata.

#### Example 1: List All Accounts

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/multi-account/accounts"
```

**Response (Success):**
```json
{
  "success": true,
  "accounts": [
    {
      "id": "123456789012",
      "arn": "arn:aws:organizations::123456789012:account/o-abc123def456/123456789012",
      "email": "admin@example.com",
      "name": "Master Account",
      "status": "ACTIVE",
      "joined_method": "INVITED",
      "joined_timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "id": "234567890123",
      "arn": "arn:aws:organizations::123456789012:account/o-abc123def456/234567890123",
      "email": "dev@example.com",
      "name": "Development Account",
      "status": "ACTIVE",
      "joined_method": "CREATED",
      "joined_timestamp": "2024-02-20T14:15:00Z"
    },
    {
      "id": "345678901234",
      "arn": "arn:aws:organizations::123456789012:account/o-abc123def456/345678901234",
      "email": "prod@example.com",
      "name": "Production Account",
      "status": "ACTIVE",
      "joined_method": "CREATED",
      "joined_timestamp": "2024-03-10T09:45:00Z"
    }
  ],
  "count": 3
}
```

---

### GET /api/multi-account/costs

Get aggregated costs across all accounts in the organization.

#### Example 1: Get Total Organizational Costs

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/multi-account/costs?start_date=2026-03-01&end_date=2026-03-31"
```

**Response (Success):**
```json
{
  "success": true,
  "costs": {
    "total_cost": 15234.56,
    "currency": "USD",
    "period": {
      "start": "2026-03-01",
      "end": "2026-03-31"
    },
    "by_account": [
      {
        "account_id": "123456789012",
        "account_name": "Master Account",
        "cost": 2345.67,
        "percentage": 15.4
      },
      {
        "account_id": "234567890123",
        "account_name": "Development Account",
        "cost": 4567.89,
        "percentage": 30.0
      },
      {
        "account_id": "345678901234",
        "account_name": "Production Account",
        "cost": 8321.00,
        "percentage": 54.6
      }
    ],
    "by_service": [
      {
        "service": "Amazon EC2",
        "cost": 6789.12,
        "percentage": 44.6
      },
      {
        "service": "Amazon RDS",
        "cost": 3456.78,
        "percentage": 22.7
      },
      {
        "service": "Amazon S3",
        "cost": 2345.67,
        "percentage": 15.4
      }
    ]
  }
}
```

---

### GET /api/multi-account/allocation

Get tag-based cost allocation across accounts.

#### Example 1: Allocate by Team Tag

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/multi-account/allocation?tag_key=Team&start_date=2026-03-01&end_date=2026-03-31"
```

**Response (Success):**
```json
{
  "success": true,
  "allocation": {
    "tag_key": "Team",
    "total_cost": 15234.56,
    "currency": "USD",
    "period": {
      "start": "2026-03-01",
      "end": "2026-03-31"
    },
    "by_tag_value": [
      {
        "tag_value": "Engineering",
        "cost": 8765.43,
        "percentage": 57.5,
        "accounts": ["234567890123", "345678901234"]
      },
      {
        "tag_value": "Data",
        "cost": 4321.09,
        "percentage": 28.4,
        "accounts": ["234567890123"]
      },
      {
        "tag_value": "Operations",
        "cost": 2148.04,
        "percentage": 14.1,
        "accounts": ["123456789012", "345678901234"]
      }
    ],
    "untagged_cost": 0.00
  }
}
```

---

### GET /api/multi-account/reports/chargeback

Generate chargeback report for cost allocation.

#### Example 1: Monthly Chargeback Report

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/multi-account/reports/chargeback?start_date=2026-03-01&end_date=2026-03-31&group_by=Team"
```

**Response (Success):**
```json
{
  "success": true,
  "report": {
    "report_type": "chargeback",
    "period": {
      "start": "2026-03-01",
      "end": "2026-03-31"
    },
    "group_by": "Team",
    "total_cost": 15234.56,
    "currency": "USD",
    "line_items": [
      {
        "group": "Engineering",
        "total_cost": 8765.43,
        "breakdown": [
          {
            "service": "Amazon EC2",
            "cost": 5432.10,
            "usage_hours": 4320
          },
          {
            "service": "Amazon RDS",
            "cost": 2345.67,
            "usage_hours": 720
          },
          {
            "service": "Amazon S3",
            "cost": 987.66,
            "storage_gb": 5000
          }
        ]
      },
      {
        "group": "Data",
        "total_cost": 4321.09,
        "breakdown": [
          {
            "service": "Amazon Redshift",
            "cost": 3210.00,
            "usage_hours": 720
          },
          {
            "service": "AWS Glue",
            "cost": 1111.09,
            "dpus": 100
          }
        ]
      }
    ]
  }
}
```

---

## Phase 6: AI/ML Workload Cost Management

Phase 6 provides GPU cost tracking, workload classification, and AI/ML cost optimization.

**Base URL:** `https://your-aiml-api-id.execute-api.us-east-1.amazonaws.com/prod/api/ai-ml`

### Setup

```bash
export AIML_API_ENDPOINT="https://your-aiml-api-id.execute-api.us-east-1.amazonaws.com/prod"
export API_KEY="your-api-key-here"
```

---

### GET /api/ai-ml/gpu-costs

Get GPU costs broken down by workload type (training, inference, idle).

#### Example 1: Get GPU Costs for March 2026

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$AIML_API_ENDPOINT/api/ai-ml/gpu-costs?start_date=2026-03-01&end_date=2026-03-31"
```

**Response (Success):**
```json
{
  "success": true,
  "gpu_costs": {
    "total_cost": 4567.89,
    "currency": "USD",
    "period": {
      "start": "2026-03-01",
      "end": "2026-03-31"
    },
    "by_workload_type": [
      {
        "workload_type": "training",
        "cost": 2345.67,
        "percentage": 51.3,
        "instance_hours": 1200,
        "instances": ["i-abc123", "i-def456"]
      },
      {
        "workload_type": "inference",
        "cost": 1876.54,
        "percentage": 41.1,
        "instance_hours": 2160,
        "instances": ["i-ghi789", "i-jkl012"]
      },
      {
        "workload_type": "idle",
        "cost": 345.68,
        "percentage": 7.6,
        "instance_hours": 240,
        "instances": ["i-mno345"]
      }
    ],
    "by_instance_type": [
      {
        "instance_type": "p3.2xlarge",
        "cost": 2345.67,
        "instance_hours": 1200
      },
      {
        "instance_type": "g4dn.xlarge",
        "cost": 1876.54,
        "instance_hours": 2160
      },
      {
        "instance_type": "p3.8xlarge",
        "cost": 345.68,
        "instance_hours": 240
      }
    ]
  }
}
```

---

### POST /api/ai-ml/workload-classification

Manually classify a workload type for an instance.

#### Example 1: Classify Instance as Training Workload

**Request:**
```bash
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "i-abc123def456",
    "workload_type": "training",
    "confidence": 1.0
  }' \
  "$AIML_API_ENDPOINT/api/ai-ml/workload-classification"
```

**Response (Success):**
```json
{
  "success": true,
  "classification": {
    "instance_id": "i-abc123def456",
    "workload_type": "training",
    "confidence": 1.0,
    "classification_method": "manual-tag",
    "gpu_utilization_avg": 0.0,
    "gpu_utilization_pattern": [],
    "timestamp": "2026-03-03T10:30:00Z"
  },
  "message": "Manual classification set to training for instance i-abc123def456"
}
```

---

### GET /api/ai-ml/cost-per-inference

Calculate cost per inference for ML models.

#### Example 1: Get Cost Per Inference for March

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$AIML_API_ENDPOINT/api/ai-ml/cost-per-inference?start_date=2026-03-01&end_date=2026-03-31&model=bert-base"
```

**Response (Success):**
```json
{
  "success": true,
  "cost_per_inference": {
    "model": "bert-base",
    "period": {
      "start": "2026-03-01",
      "end": "2026-03-31"
    },
    "total_cost": 1876.54,
    "total_inferences": 2500000,
    "cost_per_inference": 0.00075,
    "currency": "USD",
    "breakdown": {
      "compute_cost": 1500.00,
      "storage_cost": 200.00,
      "network_cost": 176.54
    },
    "instances": [
      {
        "instance_id": "i-ghi789",
        "instance_type": "g4dn.xlarge",
        "inferences": 1500000,
        "cost": 1125.92,
        "cost_per_inference": 0.00075
      },
      {
        "instance_id": "i-jkl012",
        "instance_type": "g4dn.xlarge",
        "inferences": 1000000,
        "cost": 750.62,
        "cost_per_inference": 0.00075
      }
    ]
  }
}
```

---

### GET /api/ai-ml/spot-recommendations

Get spot instance recommendations for cost savings.

#### Example 1: Get Spot Recommendations for Training Workload

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$AIML_API_ENDPOINT/api/ai-ml/spot-recommendations?workload_id=training-job-123&current_instance=p3.2xlarge"
```

**Response (Success):**
```json
{
  "success": true,
  "recommendations": {
    "workload_id": "training-job-123",
    "current_instance": {
      "type": "p3.2xlarge",
      "on_demand_price": 3.06,
      "current_cost_per_hour": 3.06
    },
    "spot_recommendations": [
      {
        "instance_type": "p3.2xlarge",
        "spot_price": 0.918,
        "savings_percentage": 70.0,
        "savings_per_hour": 2.142,
        "availability_zone": "us-east-1a",
        "interruption_rate": "5-10%"
      },
      {
        "instance_type": "p3.2xlarge",
        "spot_price": 1.224,
        "savings_percentage": 60.0,
        "savings_per_hour": 1.836,
        "availability_zone": "us-east-1b",
        "interruption_rate": "<5%"
      }
    ],
    "estimated_monthly_savings": 1542.24,
    "recommendation": "Use spot instances in us-east-1b for best balance of cost and availability"
  }
}
```

---

### GET /api/ai-ml/sagemaker-idle-endpoints

Detect idle SageMaker endpoints to reduce costs.

#### Example 1: Find Idle SageMaker Endpoints

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$AIML_API_ENDPOINT/api/ai-ml/sagemaker-idle-endpoints?threshold=10"
```

**Response (Success):**
```json
{
  "success": true,
  "idle_endpoints": {
    "threshold": 10,
    "idle_endpoint_count": 2,
    "idle_endpoints": [
      {
        "endpoint_name": "bert-inference-endpoint",
        "endpoint_arn": "arn:aws:sagemaker:us-east-1:123456789012:endpoint/bert-inference-endpoint",
        "instance_type": "ml.m5.xlarge",
        "instance_count": 2,
        "invocations_last_hour": 3,
        "cost_per_hour": 0.384,
        "estimated_monthly_waste": 276.48,
        "created_time": "2026-02-15T10:30:00Z",
        "last_invocation": "2026-03-01T08:15:00Z"
      },
      {
        "endpoint_name": "gpt2-inference-endpoint",
        "endpoint_arn": "arn:aws:sagemaker:us-east-1:123456789012:endpoint/gpt2-inference-endpoint",
        "instance_type": "ml.g4dn.xlarge",
        "instance_count": 1,
        "invocations_last_hour": 5,
        "cost_per_hour": 0.736,
        "estimated_monthly_waste": 530.88,
        "created_time": "2026-01-20T14:45:00Z",
        "last_invocation": "2026-03-02T16:30:00Z"
      }
    ],
    "total_wasted_cost_per_hour": 1.12,
    "estimated_monthly_waste": 807.36
  }
}
```

---

### GET /api/ai-ml/bedrock-costs

Get Bedrock cost breakdown by model and token usage.

#### Example 1: Get Bedrock Costs for March

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$AIML_API_ENDPOINT/api/ai-ml/bedrock-costs?start_date=2026-03-01&end_date=2026-03-31"
```

**Response (Success):**
```json
{
  "success": true,
  "bedrock_costs": {
    "total_cost": 234.56,
    "currency": "USD",
    "period": {
      "start": "2026-03-01",
      "end": "2026-03-31"
    },
    "by_model": [
      {
        "model_id": "amazon.nova-lite-v1:0",
        "cost": 123.45,
        "invocations": 50000,
        "input_tokens": 5000000,
        "output_tokens": 2500000,
        "cost_per_invocation": 0.002469
      },
      {
        "model_id": "amazon.nova-pro-v1:0",
        "cost": 111.11,
        "invocations": 10000,
        "input_tokens": 2000000,
        "output_tokens": 1000000,
        "cost_per_invocation": 0.011111
      }
    ],
    "total_invocations": 60000,
    "total_input_tokens": 7000000,
    "total_output_tokens": 3500000
  }
}
```

---

### GET /api/ai-ml/multi-account/gpu-costs

Get GPU costs aggregated across multiple accounts.

#### Example 1: Get Multi-Account GPU Costs

**Request:**
```bash
curl -H "x-api-key: $API_KEY" \
  "$AIML_API_ENDPOINT/api/ai-ml/multi-account/gpu-costs?org_id=o-abc123&account_ids=123456789012,234567890123&start_date=2026-03-01&end_date=2026-03-31"
```

**Response (Success):**
```json
{
  "success": true,
  "multi_account_gpu_costs": {
    "organization_id": "o-abc123",
    "total_cost": 12345.67,
    "currency": "USD",
    "period": {
      "start": "2026-03-01",
      "end": "2026-03-31"
    },
    "by_account": [
      {
        "account_id": "123456789012",
        "account_name": "ML Training Account",
        "total_cost": 8765.43,
        "percentage": 71.0,
        "by_workload": {
          "training": 7654.32,
          "inference": 987.65,
          "idle": 123.46
        }
      },
      {
        "account_id": "234567890123",
        "account_name": "ML Inference Account",
        "total_cost": 3580.24,
        "percentage": 29.0,
        "by_workload": {
          "training": 456.78,
          "inference": 3012.34,
          "idle": 111.12
        }
      }
    ],
    "total_by_workload": {
      "training": 8111.10,
      "inference": 3999.99,
      "idle": 234.58
    }
  }
}
```

---

## Python Examples

### Phase 5: Multi-Account Cost Management

```python
import requests
import json

# Configuration
MULTI_ACCOUNT_API_ENDPOINT = "https://your-multi-account-api-id.execute-api.us-east-1.amazonaws.com/prod"
API_KEY = "your-api-key-here"

headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

# Example 1: Get organization details
response = requests.get(
    f"{MULTI_ACCOUNT_API_ENDPOINT}/api/multi-account/organizations",
    headers=headers
)
org = response.json()
print(f"Organization ID: {org['organization']['id']}")
print(f"Master Account: {org['organization']['master_account_id']}")

# Example 2: List all accounts
response = requests.get(
    f"{MULTI_ACCOUNT_API_ENDPOINT}/api/multi-account/accounts",
    headers=headers
)
accounts = response.json()
print(f"\nTotal Accounts: {accounts['count']}")
for account in accounts['accounts']:
    print(f"  - {account['name']} ({account['id']}): {account['status']}")

# Example 3: Get aggregated costs
response = requests.get(
    f"{MULTI_ACCOUNT_API_ENDPOINT}/api/multi-account/costs",
    headers=headers,
    params={
        "start_date": "2026-03-01",
        "end_date": "2026-03-31"
    }
)
costs = response.json()
print(f"\nTotal Organizational Cost: ${costs['costs']['total_cost']:.2f}")
print("\nCost by Account:")
for account in costs['costs']['by_account']:
    print(f"  - {account['account_name']}: ${account['cost']:.2f} ({account['percentage']:.1f}%)")

# Example 4: Get tag-based allocation
response = requests.get(
    f"{MULTI_ACCOUNT_API_ENDPOINT}/api/multi-account/allocation",
    headers=headers,
    params={
        "tag_key": "Team",
        "start_date": "2026-03-01",
        "end_date": "2026-03-31"
    }
)
allocation = response.json()
print(f"\nCost Allocation by Team:")
for item in allocation['allocation']['by_tag_value']:
    print(f"  - {item['tag_value']}: ${item['cost']:.2f} ({item['percentage']:.1f}%)")

# Example 5: Generate chargeback report
response = requests.get(
    f"{MULTI_ACCOUNT_API_ENDPOINT}/api/multi-account/reports/chargeback",
    headers=headers,
    params={
        "start_date": "2026-03-01",
        "end_date": "2026-03-31",
        "group_by": "Team"
    }
)
report = response.json()
print(f"\nChargeback Report:")
for line_item in report['report']['line_items']:
    print(f"  {line_item['group']}: ${line_item['total_cost']:.2f}")
    for service in line_item['breakdown']:
        print(f"    - {service['service']}: ${service['cost']:.2f}")
```

---

### Phase 6: AI/ML Workload Cost Management

```python
import requests
import json

# Configuration
AIML_API_ENDPOINT = "https://your-aiml-api-id.execute-api.us-east-1.amazonaws.com/prod"
API_KEY = "your-api-key-here"

headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

# Example 1: Get GPU costs by workload type
response = requests.get(
    f"{AIML_API_ENDPOINT}/api/ai-ml/gpu-costs",
    headers=headers,
    params={
        "start_date": "2026-03-01",
        "end_date": "2026-03-31"
    }
)
gpu_costs = response.json()
print(f"Total GPU Cost: ${gpu_costs['gpu_costs']['total_cost']:.2f}")
print("\nCost by Workload Type:")
for workload in gpu_costs['gpu_costs']['by_workload_type']:
    print(f"  - {workload['workload_type']}: ${workload['cost']:.2f} ({workload['percentage']:.1f}%)")

# Example 2: Classify workload manually
classification_data = {
    "instance_id": "i-abc123def456",
    "workload_type": "training",
    "confidence": 1.0
}
response = requests.post(
    f"{AIML_API_ENDPOINT}/api/ai-ml/workload-classification",
    headers=headers,
    json=classification_data
)
result = response.json()
print(f"\nClassification: {result['message']}")

# Example 3: Calculate cost per inference
response = requests.get(
    f"{AIML_API_ENDPOINT}/api/ai-ml/cost-per-inference",
    headers=headers,
    params={
        "start_date": "2026-03-01",
        "end_date": "2026-03-31",
        "model": "bert-base"
    }
)
cpi = response.json()
print(f"\nCost Per Inference (bert-base):")
print(f"  Total Cost: ${cpi['cost_per_inference']['total_cost']:.2f}")
print(f"  Total Inferences: {cpi['cost_per_inference']['total_inferences']:,}")
print(f"  Cost Per Inference: ${cpi['cost_per_inference']['cost_per_inference']:.6f}")

# Example 4: Get spot instance recommendations
response = requests.get(
    f"{AIML_API_ENDPOINT}/api/ai-ml/spot-recommendations",
    headers=headers,
    params={
        "workload_id": "training-job-123",
        "current_instance": "p3.2xlarge"
    }
)
recommendations = response.json()
print(f"\nSpot Instance Recommendations:")
print(f"  Current Cost: ${recommendations['recommendations']['current_instance']['on_demand_price']:.2f}/hour")
for rec in recommendations['recommendations']['spot_recommendations']:
    print(f"  - {rec['instance_type']} in {rec['availability_zone']}: ${rec['spot_price']:.3f}/hour ({rec['savings_percentage']:.0f}% savings)")

# Example 5: Find idle SageMaker endpoints
response = requests.get(
    f"{AIML_API_ENDPOINT}/api/ai-ml/sagemaker-idle-endpoints",
    headers=headers,
    params={"threshold": 10}
)
idle = response.json()
print(f"\nIdle SageMaker Endpoints: {idle['idle_endpoints']['idle_endpoint_count']}")
print(f"Estimated Monthly Waste: ${idle['idle_endpoints']['estimated_monthly_waste']:.2f}")
for endpoint in idle['idle_endpoints']['idle_endpoints']:
    print(f"  - {endpoint['endpoint_name']}: ${endpoint['estimated_monthly_waste']:.2f}/month")

# Example 6: Get Bedrock costs
response = requests.get(
    f"{AIML_API_ENDPOINT}/api/ai-ml/bedrock-costs",
    headers=headers,
    params={
        "start_date": "2026-03-01",
        "end_date": "2026-03-31"
    }
)
bedrock = response.json()
print(f"\nBedrock Costs: ${bedrock['bedrock_costs']['total_cost']:.2f}")
print(f"Total Invocations: {bedrock['bedrock_costs']['total_invocations']:,}")
for model in bedrock['bedrock_costs']['by_model']:
    print(f"  - {model['model_id']}: ${model['cost']:.2f} ({model['invocations']:,} invocations)")

# Example 7: Get multi-account GPU costs
response = requests.get(
    f"{AIML_API_ENDPOINT}/api/ai-ml/multi-account/gpu-costs",
    headers=headers,
    params={
        "org_id": "o-abc123",
        "account_ids": "123456789012,234567890123",
        "start_date": "2026-03-01",
        "end_date": "2026-03-31"
    }
)
multi_gpu = response.json()
print(f"\nMulti-Account GPU Costs: ${multi_gpu['multi_account_gpu_costs']['total_cost']:.2f}")
for account in multi_gpu['multi_account_gpu_costs']['by_account']:
    print(f"  - {account['account_name']}: ${account['total_cost']:.2f} ({account['percentage']:.1f}%)")
```

---

## Complete Documentation

For complete API documentation, see:

**Phase 5:**
- [Phase 5 API Documentation](./technical/phase5-multi-account/API_DOCUMENTATION.md)
- [Phase 5 README](./technical/phase5-multi-account/README.md)
- [Cross-Account Setup Guide](../infrastructure/CROSS_ACCOUNT_SETUP.md)

**Phase 6:**
- [Phase 6 API Documentation](./api/phase6-api-documentation.md)
- [Phase 6 User Guide](./user-guide/PHASE6_AI_ML_USER_GUIDE.md)
- [Phase 6 Deployment Guide](./deployment/phase6-deployment-guide.md)

