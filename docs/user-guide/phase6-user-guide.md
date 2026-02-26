# Phase 6: AI/ML Workload Cost Management - User Guide

**Version:** 1.0  
**Last Updated:** February 2026  
**Audience:** AI Startup CTOs/Founders, ML Platform Engineers, SageMaker/Bedrock Users

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [GPU Cost Tracking](#gpu-cost-tracking)
4. [Workload Classification](#workload-classification)
5. [Cost-Per-Inference](#cost-per-inference)
6. [Cost-Per-Training](#cost-per-training)
7. [Spot Instance Recommendations](#spot-instance-recommendations)
8. [SageMaker Cost Tracking](#sagemaker-cost-tracking)
9. [Bedrock Cost Tracking](#bedrock-cost-tracking)
10. [GPU Prevention](#gpu-prevention)
11. [Multi-Account GPU Tracking](#multi-account-gpu-tracking)
12. [Best Practices](#best-practices)
13. [Troubleshooting](#troubleshooting)
14. [FAQ](#faq)

---

## Introduction

Welcome to CostGuard AI Phase 6! This guide helps you track and optimize your AI/ML workload costs on AWS.

### What is Phase 6?

Phase 6 adds AI/ML-specific cost management to CostGuard AI, focusing on:

- **GPU Cost Tracking**: See exactly where your GPU money goes (training vs inference vs idle)
- **Workload Classification**: Automatically identify what your GPUs are doing
- **Unit Cost Calculations**: Know your cost-per-inference and cost-per-training
- **Spot Recommendations**: Save up to 70% on training workloads
- **Idle GPU Detection**: Stop wasting money on unused GPUs
- **SageMaker & Bedrock Tracking**: Track managed AI service costs

### Who Should Use This?

**AI Startup CTOs/Founders:**
- You're spending $10K-100K/month on AWS
- 60-80% of your budget goes to GPU compute
- You need to understand where your GPU money is going

**ML Platform Engineers:**
- You manage GPU infrastructure for your team
- You need to optimize GPU utilization and costs
- You want to recommend cost-effective instance types

**SageMaker/Bedrock Users:**
- You use AWS managed AI services
- You want to track model invocation costs
- You need to optimize model selection for cost

### Key Benefits

- **Save 20-30% on GPU costs** ($7K-10K/month for typical AI startup)
- **100% visibility** into GPU spending by workload type
- **Automated recommendations** for cost optimization
- **No competitor offers this** - unique GPU-specific tracking

### What You'll Learn

This guide teaches you how to:
1. Track GPU costs by workload type (training, inference, idle)
2. Calculate cost-per-inference and cost-per-training
3. Identify and stop idle GPU instances
4. Use spot instances to save up to 70% on training
5. Optimize SageMaker and Bedrock costs
6. Aggregate GPU costs across multiple AWS accounts

---

## Getting Started

### Prerequisites

Before using Phase 6, ensure you have:

- [ ] CostGuard AI deployed (Phases 1-5)
- [ ] API key for authentication
- [ ] AWS account with GPU instances, SageMaker, or Bedrock
- [ ] Basic understanding of AWS services

### Quick Start (5 minutes)

Let's check your GPU costs for the last 30 days:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

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
      "utilization": 85.5
    }
  ],
  "total_cost": 1234.56,
  "total_gpu_hours": 120.5
}
```

**What This Tells You:**
- You spent $1,234.56 on GPUs in January
- You used 120.5 GPU hours
- Your average cost per GPU hour is $10.24
- Your GPUs are classified by workload type (training, inference, idle)


### Understanding the Response

**Key Fields Explained:**

| Field | Description | Why It Matters |
|-------|-------------|----------------|
| `workload_type` | Training, inference, or idle | Shows what your GPUs are doing |
| `cost` | Total cost for this instance | Your actual spending |
| `gpu_hours` | Hours the GPU was running | Usage metric |
| `cost_per_gpu_hour` | Cost divided by hours | Unit cost for comparison |
| `utilization` | GPU usage percentage (0-100%) | Efficiency metric |
| `classification_confidence` | How sure we are (0-1) | Reliability indicator |

**Workload Types:**
- **Training**: GPU utilization > 70% continuously (model training)
- **Inference**: GPU utilization 20-70% with spikes (serving predictions)
- **Idle**: GPU utilization < 10% (wasting money!)

---

## GPU Cost Tracking

### Overview

GPU cost tracking shows you exactly where your GPU money goes. No more wondering "why is my AWS bill so high?"

### Use Cases

1. **Monthly GPU Budget Review**: See total GPU spending by workload type
2. **Cost Allocation**: Allocate GPU costs to teams or projects
3. **Trend Analysis**: Track GPU costs over time
4. **Instance Type Comparison**: Compare costs across different GPU types

### Basic Usage

#### Get GPU Costs for a Date Range

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

#### Filter by Workload Type

See only training costs:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31&workload_type=training" \
  -H "X-API-Key: your-api-key-here"
```

See only idle GPUs (wasted money):

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31&workload_type=idle" \
  -H "X-API-Key: your-api-key-here"
```

#### Filter by Instance Type

See costs for specific GPU type:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31&instance_type=p3.2xlarge" \
  -H "X-API-Key: your-api-key-here"
```


### Real-World Example

**Scenario**: You're an AI startup CTO. Your January AWS bill was $35K, and you suspect GPU costs are the culprit.

**Step 1**: Check total GPU costs

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Result**: Total GPU cost = $28,000 (80% of your AWS bill!)

**Step 2**: Break down by workload type

```json
{
  "costs_by_workload_type": {
    "training": 15000.00,
    "inference": 8000.00,
    "idle": 5000.00
  }
}
```

**Insight**: You're wasting $5,000/month on idle GPUs! That's 18% of your GPU budget.

**Step 3**: Identify idle GPUs (see [GPU Prevention](#gpu-prevention) section)

**Action**: Stop idle GPUs and save $5,000/month.

### Understanding GPU Utilization

**Utilization Percentage:**
- **90-100%**: Excellent! GPU is fully utilized
- **70-90%**: Good for training workloads
- **20-70%**: Normal for inference workloads (bursty traffic)
- **10-20%**: Low utilization - consider downsizing
- **< 10%**: Idle - stop or terminate immediately

**Why Utilization Matters:**

If you're paying $10/hour for a GPU but only using it 50% of the time, your effective cost is $20/hour of actual work. Low utilization = wasted money.

### Performance Tips

**Response Times:**
- Cached queries: < 2 seconds
- Uncached queries: < 10 seconds
- Cache TTL: 24 hours

**Tip**: Query the same date range within 24 hours to get cached results (faster response).

---

## Workload Classification

### Overview

Workload classification automatically identifies what your GPUs are doing: training models, serving inference, or sitting idle.

### How It Works

CostGuard AI uses CloudWatch GPU metrics to classify workloads:

1. **Collect GPU utilization data** from CloudWatch (5-minute intervals)
2. **Analyze utilization patterns** over time
3. **Apply classification rules**:
   - Training: GPU utilization > 70% continuously for > 1 hour
   - Inference: GPU utilization 20-70% with frequent spikes
   - Idle: GPU utilization < 10%
4. **Calculate confidence score** (0-100%)

### Use Cases

1. **Automatic Cost Allocation**: Allocate GPU costs to training vs inference teams
2. **Optimization Opportunities**: Identify idle GPUs for termination
3. **Spot Instance Candidates**: Find training workloads suitable for spot instances
4. **Audit Trail**: Track workload classification history


### Basic Usage

#### Get Workload Classification

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/workload-classification?instance_id=i-1234567890abcdef0&start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "classification": {
    "instance_id": "i-1234567890abcdef0",
    "workload_type": "training",
    "confidence": 0.95,
    "classification_method": "cloudwatch-metrics",
    "gpu_utilization_avg": 85.5,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Understanding Confidence Scores:**
- **0.9-1.0**: Very confident (clear utilization pattern)
- **0.8-0.9**: Confident (typical pattern)
- **0.6-0.8**: Moderate confidence (mixed pattern)
- **< 0.6**: Low confidence (unclear pattern - consider manual classification)

#### Manual Classification Override

Sometimes automatic classification is wrong. You can manually override it:

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

**When to Use Manual Classification:**
- Automatic classification has low confidence (< 0.6)
- You know the workload type from your application
- GPU utilization pattern is unusual but valid

**Best Practice**: Use EC2 tags for persistent manual classification:

```bash
aws ec2 create-tags \
  --resources i-1234567890abcdef0 \
  --tags Key=CostGuard:WorkloadType,Value=training
```

CostGuard AI will automatically detect this tag and use it for classification.

### Real-World Example

**Scenario**: You have 10 GPU instances running. You want to know which ones are training vs inference.

**Step 1**: Get classifications for all instances

```bash
# Loop through all instances
for instance_id in i-111 i-222 i-333 i-444 i-555 i-666 i-777 i-888 i-999 i-000; do
  curl -X GET "https://api.costguard.ai/api/ai-ml/workload-classification?instance_id=$instance_id&start_date=2024-01-01&end_date=2024-01-31" \
    -H "X-API-Key: your-api-key-here"
done
```

**Result**:
- 6 instances: Training (high confidence)
- 2 instances: Inference (high confidence)
- 2 instances: Idle (high confidence)

**Action**:
- Training instances: Consider spot instances (see [Spot Recommendations](#spot-instance-recommendations))
- Inference instances: Keep as-is (need on-demand for reliability)
- Idle instances: Stop immediately (see [GPU Prevention](#gpu-prevention))


---

## Cost-Per-Inference

### Overview

Cost-per-inference tells you how much each prediction costs. This is critical for:
- Pricing your AI product correctly
- Optimizing model efficiency
- Comparing different models or instance types

### How It Works

CostGuard AI calculates cost-per-inference by:

1. **Tracking inference requests** from API Gateway, Lambda, SageMaker, or Bedrock
2. **Calculating total costs** (compute + API + data transfer)
3. **Dividing total cost by request count**

**Formula**: Cost per inference = Total cost / Total requests

### Use Cases

1. **Product Pricing**: Know your unit economics to price your AI product
2. **Model Comparison**: Compare cost efficiency of different models
3. **Optimization Tracking**: Measure impact of model optimizations
4. **Budget Planning**: Forecast costs based on expected request volume

### Basic Usage

#### Get Cost-Per-Inference

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/cost-per-inference?start_date=2024-01-01&end_date=2024-01-31&model=bert-base-uncased&endpoint=inference-endpoint-1" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "model": "bert-base-uncased",
  "endpoint": "inference-endpoint-1",
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

**Understanding the Numbers:**
- **Cost per inference**: $0.00123 (about 1/10th of a cent per prediction)
- **Total requests**: 1 million predictions
- **Total cost**: $1,234.56

**Is This Good?** It depends on your product:
- If you charge $0.01 per prediction, your margin is 87% (excellent!)
- If you charge $0.002 per prediction, your margin is 38% (okay)
- If you charge $0.001 per prediction, you're losing money (bad!)

#### Track Cost Trends Over Time

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/inference-trends?model=bert-base-uncased&endpoint=inference-endpoint-1&days=30" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "trends": [
    {
      "date": "2024-01-01",
      "cost_per_inference": 0.00125,
      "total_requests": 35000
    },
    {
      "date": "2024-01-02",
      "cost_per_inference": 0.00123,
      "total_requests": 38000
    }
  ]
}
```

**What to Look For:**
- **Decreasing cost per inference**: Good! Your optimizations are working
- **Increasing cost per inference**: Bad! Investigate what changed
- **Stable cost per inference**: Normal - your system is consistent


### Real-World Example

**Scenario**: You're building an AI-powered chatbot. You need to know if you can afford to offer a free tier.

**Step 1**: Calculate cost-per-inference

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/cost-per-inference?start_date=2024-01-01&end_date=2024-01-31&model=gpt-3.5-turbo&endpoint=chatbot-api" \
  -H "X-API-Key: your-api-key-here"
```

**Result**: Cost per inference = $0.002 (2/10ths of a cent)

**Step 2**: Calculate free tier cost

- Free tier: 100 messages per user per month
- Expected users: 10,000
- Total free messages: 1,000,000
- **Free tier cost**: 1,000,000 × $0.002 = $2,000/month

**Decision**: You can afford a free tier! $2,000/month is reasonable for customer acquisition.

### Optimization Tips

**How to Reduce Cost-Per-Inference:**

1. **Use smaller models**: GPT-3.5 instead of GPT-4 (if accuracy allows)
2. **Batch requests**: Process multiple requests together
3. **Cache results**: Cache common queries to avoid recomputation
4. **Use cheaper instance types**: g4dn instead of p3 (if performance allows)
5. **Optimize model**: Quantization, pruning, distillation

**Example**: Switching from p3.2xlarge to g4dn.xlarge:
- Before: $0.00123 per inference
- After: $0.00045 per inference
- **Savings**: 63% reduction!

---

## Cost-Per-Training

### Overview

Cost-per-training tells you how much it costs to train a model. This helps you:
- Budget for model training
- Compare training costs across instance types
- Optimize training efficiency

### How It Works

CostGuard AI calculates cost-per-training by:

1. **Tracking training jobs** from SageMaker or EC2
2. **Calculating total costs** (compute + storage + data transfer)
3. **Tracking training duration**

**Formula**: Cost per training = Compute cost + Storage cost + Data transfer cost

### Use Cases

1. **Budget Planning**: Estimate training costs for new models
2. **Instance Type Selection**: Choose the most cost-effective GPU
3. **Training Optimization**: Measure impact of training optimizations
4. **Cost Allocation**: Allocate training costs to teams or projects

### Basic Usage

#### Get Cost-Per-Training

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/cost-per-training?job_id=training-job-123" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "job_id": "training-job-123",
  "model": "resnet-50",
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

**Understanding the Numbers:**
- **Total cost**: $125.75 to train this model
- **Training hours**: 12.5 hours
- **Cost per hour**: $10.06/hour
- **Compute cost**: $100 (80% of total)
- **Storage cost**: $20 (16% of total)
- **Data transfer**: $5.75 (4% of total)


#### Compare Training Costs Across Instance Types

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/training-comparison?model=resnet-50&instance_types=p3.2xlarge,p3.8xlarge,g4dn.xlarge&baseline_instance=p3.2xlarge" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "comparisons": [
    {
      "instance_type": "p3.2xlarge",
      "estimated_duration_hours": 12.0,
      "estimated_cost": 122.40,
      "savings_vs_baseline": 0.00
    },
    {
      "instance_type": "p3.8xlarge",
      "estimated_duration_hours": 4.0,
      "estimated_cost": 98.80,
      "savings_vs_baseline": 23.60,
      "savings_percent": 19.28
    },
    {
      "instance_type": "g4dn.xlarge",
      "estimated_duration_hours": 24.0,
      "estimated_cost": 62.40,
      "savings_vs_baseline": 60.00,
      "savings_percent": 49.02
    }
  ]
}
```

**What This Tells You:**
- **p3.2xlarge**: Baseline (12 hours, $122.40)
- **p3.8xlarge**: Faster but more expensive per hour (4 hours, $98.80) - **Save 19%**
- **g4dn.xlarge**: Slower but cheaper per hour (24 hours, $62.40) - **Save 49%**

**Decision Guide:**
- Need results fast? Use p3.8xlarge (4 hours)
- Want to save money? Use g4dn.xlarge (24 hours)
- Balanced approach? Use p3.2xlarge (12 hours)

### Real-World Example

**Scenario**: You train models weekly. You want to reduce training costs.

**Step 1**: Check current training costs

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/cost-per-training?job_id=weekly-training-job" \
  -H "X-API-Key: your-api-key-here"
```

**Result**: $500/week on p3.2xlarge instances

**Step 2**: Compare instance types

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/training-comparison?model=your-model&instance_types=p3.2xlarge,g4dn.xlarge,p3.8xlarge" \
  -H "X-API-Key: your-api-key-here"
```

**Result**:
- p3.2xlarge: $500/week (current)
- g4dn.xlarge: $250/week (50% savings!)
- p3.8xlarge: $400/week (20% savings)

**Step 3**: Test g4dn.xlarge

Run one training job on g4dn.xlarge to verify accuracy is acceptable.

**Step 4**: Switch to g4dn.xlarge

**Savings**: $250/week × 52 weeks = **$13,000/year**

### Optimization Tips

**How to Reduce Training Costs:**

1. **Use spot instances**: Save up to 70% (see [Spot Recommendations](#spot-instance-recommendations))
2. **Use cheaper instance types**: g4dn instead of p3 (if training time allows)
3. **Optimize training code**: Reduce training time = reduce cost
4. **Use mixed precision training**: Train faster with same accuracy
5. **Resume from checkpoints**: Don't restart training from scratch

---

## Spot Instance Recommendations

### Overview

Spot instances can save you up to 70% on training costs. But they can be interrupted. CostGuard AI helps you identify which workloads are suitable for spot instances and estimates your savings.


### How It Works

CostGuard AI recommends spot instances by:

1. **Identifying training workloads** (not inference - too risky for interruption)
2. **Calculating potential savings** (on-demand price - spot price)
3. **Assessing interruption risk** (historical spot interruption data)
4. **Generating what-if scenarios** (50% spot, 100% spot, etc.)

### Use Cases

1. **Training Cost Optimization**: Save 70% on training workloads
2. **Batch Processing**: Use spot for non-time-sensitive jobs
3. **Experimentation**: Use spot for model experiments
4. **Budget Stretching**: Do more training with the same budget

### Basic Usage

#### Get Spot Recommendations

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/spot-recommendations?workload_id=i-1234567890abcdef0&include_scenarios=true" \
  -H "X-API-Key: your-api-key-here"
```

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
      "spot_usage_percent": 100,
      "estimated_savings": 7140.00,
      "estimated_interruptions": 2,
      "recommendation": "High savings with acceptable interruption risk"
    },
    {
      "scenario_name": "50% Spot Usage",
      "spot_usage_percent": 50,
      "estimated_savings": 3570.00,
      "estimated_interruptions": 1,
      "recommendation": "Balanced approach with lower interruption risk"
    }
  ]
}
```

**Understanding the Numbers:**
- **Current cost**: $10.20/hour (on-demand)
- **Spot cost**: $3.06/hour (70% discount!)
- **Savings**: $7.14/hour
- **Interruption risk**: 15% (low risk)

**What-If Scenarios:**
- **100% spot**: Save $7,140/month, expect 2 interruptions
- **50% spot**: Save $3,570/month, expect 1 interruption

#### Calculate Spot Savings

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/spot-savings?current_instance=p3.2xlarge" \
  -H "X-API-Key: your-api-key-here"
```

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

### Real-World Example

**Scenario**: You train models 24/7 on p3.2xlarge instances. Current cost: $7,344/month.

**Step 1**: Get spot recommendations

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/spot-recommendations?workload_id=i-training-instance" \
  -H "X-API-Key: your-api-key-here"
```

**Result**: Spot instances recommended with 70% savings

**Step 2**: Evaluate risk

- Interruption risk: 15% (low)
- Expected interruptions: 2 per month
- Your training has checkpointing: Can resume from last checkpoint

**Decision**: Spot instances are suitable!

**Step 3**: Switch to spot instances

**Savings**: $7,344 × 70% = **$5,140/month** or **$61,680/year**


### When to Use Spot Instances

**Good for Spot:**
- ✅ Training workloads with checkpointing
- ✅ Batch processing jobs
- ✅ Model experiments and hyperparameter tuning
- ✅ Non-time-sensitive workloads
- ✅ Workloads that can tolerate interruptions

**Bad for Spot:**
- ❌ Real-time inference (customer-facing)
- ❌ Production services requiring high availability
- ❌ Time-sensitive jobs without checkpointing
- ❌ Workloads that can't resume from interruption

### Best Practices

1. **Always use checkpointing**: Save training state every 15-30 minutes
2. **Monitor interruption rates**: Track actual interruptions vs estimates
3. **Use spot instance pools**: Diversify across multiple instance types
4. **Set max price**: Limit spot price to avoid cost spikes
5. **Test first**: Run one training job on spot before switching all workloads

### Handling Interruptions

**What happens when spot instance is interrupted?**

1. AWS sends 2-minute warning
2. Your training job should save checkpoint
3. Instance is terminated
4. New spot instance is launched (or on-demand fallback)
5. Training resumes from last checkpoint

**Example Checkpoint Code (PyTorch):**

```python
import torch

def save_checkpoint(model, optimizer, epoch, path):
    torch.save({
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
    }, path)

def load_checkpoint(model, optimizer, path):
    checkpoint = torch.load(path)
    model.load_state_dict(checkpoint['model_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    return checkpoint['epoch']
```

---

## SageMaker Cost Tracking

### Overview

If you use Amazon SageMaker for training or inference, CostGuard AI tracks your SageMaker costs and identifies optimization opportunities.

### How It Works

CostGuard AI tracks:

1. **Training job costs**: Compute, storage, and data transfer for training
2. **Inference endpoint costs**: Real-time endpoint hosting costs
3. **Notebook instance costs**: SageMaker notebook usage
4. **Idle endpoints**: Endpoints with < 10 requests/hour

### Use Cases

1. **SageMaker Budget Management**: Track total SageMaker spending
2. **Idle Endpoint Detection**: Find and delete unused endpoints
3. **Instance Type Optimization**: Recommend cheaper instance types
4. **Cost Allocation**: Allocate SageMaker costs by job type

### Basic Usage

#### Get SageMaker Costs

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/sagemaker-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "training_costs": 5000.00,
  "inference_costs": 2000.00,
  "notebook_costs": 500.00,
  "total_cost": 7500.00,
  "job_breakdown": [
    {
      "job_name": "training-job-123",
      "job_type": "training",
      "instance_type": "ml.p3.2xlarge",
      "duration_hours": 12.5,
      "total_cost": 125.00
    }
  ]
}
```

**Understanding the Numbers:**
- **Training costs**: $5,000 (67% of SageMaker spend)
- **Inference costs**: $2,000 (27% of SageMaker spend)
- **Notebook costs**: $500 (7% of SageMaker spend)


#### Find Idle SageMaker Endpoints

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/sagemaker-idle-endpoints?threshold=10" \
  -H "X-API-Key: your-api-key-here"
```

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
      "cost_per_hour": 0.384,
      "is_idle": true,
      "recommendation": "Consider scaling down or deleting this endpoint. Current cost: $0.38/hour"
    }
  ],
  "total_wasted_cost_per_hour": 1.152,
  "estimated_monthly_waste": 829.44
}
```

**What This Tells You:**
- You have 3 idle endpoints
- They're costing you $1.15/hour ($829/month)
- They're getting < 10 requests/hour

**Action**: Delete or scale down these endpoints to save $829/month.

### Real-World Example

**Scenario**: Your SageMaker bill is $10K/month. You want to reduce it.

**Step 1**: Check SageMaker costs

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/sagemaker-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Result**:
- Training: $6,000
- Inference: $3,500
- Notebooks: $500

**Step 2**: Find idle endpoints

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/sagemaker-idle-endpoints" \
  -H "X-API-Key: your-api-key-here"
```

**Result**: 5 idle endpoints costing $1,200/month

**Step 3**: Delete idle endpoints

```bash
aws sagemaker delete-endpoint --endpoint-name inference-endpoint-1
aws sagemaker delete-endpoint --endpoint-name inference-endpoint-2
# ... delete all idle endpoints
```

**Savings**: $1,200/month or **$14,400/year**

### Optimization Tips

**How to Reduce SageMaker Costs:**

1. **Delete idle endpoints**: Check for endpoints with < 10 requests/hour
2. **Use auto-scaling**: Scale down during low traffic periods
3. **Use serverless inference**: Pay per request instead of per hour
4. **Use spot instances for training**: Save up to 70%
5. **Right-size instance types**: Don't over-provision

**Example**: Switching from ml.m5.xlarge to ml.m5.large:
- Before: $0.192/hour
- After: $0.096/hour
- **Savings**: 50% reduction

---

## Bedrock Cost Tracking

### Overview

If you use Amazon Bedrock for AI model invocations, CostGuard AI tracks your Bedrock costs by model and provides optimization recommendations.

### How It Works

CostGuard AI tracks:

1. **Model invocation costs**: Cost per model (Claude, Titan, Llama, etc.)
2. **Token usage**: Input and output token counts
3. **Cost per invocation**: Average cost per API call
4. **Model recommendations**: Suggest cheaper models with similar performance


### Use Cases

1. **Bedrock Budget Management**: Track total Bedrock spending
2. **Model Cost Comparison**: Compare costs across different models
3. **Token Usage Optimization**: Reduce token usage to save money
4. **Model Selection**: Choose the most cost-effective model

### Basic Usage

#### Get Bedrock Costs

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/bedrock-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "models": [
    {
      "model_id": "anthropic.claude-v2",
      "invocations": 50000,
      "input_tokens": 5000000,
      "output_tokens": 2500000,
      "total_cost": 187.50,
      "cost_per_invocation": 0.00375
    },
    {
      "model_id": "amazon.titan-text-express-v1",
      "invocations": 100000,
      "input_tokens": 8000000,
      "output_tokens": 4000000,
      "total_cost": 120.00,
      "cost_per_invocation": 0.0012
    }
  ],
  "totals": {
    "total_cost": 307.50,
    "total_invocations": 150000,
    "avg_cost_per_invocation": 0.00205
  }
}
```

**Understanding the Numbers:**
- **Claude v2**: $0.00375 per invocation (more expensive but higher quality)
- **Titan Express**: $0.0012 per invocation (cheaper but lower quality)
- **Average**: $0.00205 per invocation

#### Get Cost-Per-Invocation with Recommendations

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/bedrock-cost-per-invocation?start_date=2024-01-01&end_date=2024-01-31&model=anthropic.claude-v2" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "model_id": "anthropic.claude-v2",
  "cost_per_invocation": 0.00375,
  "total_invocations": 50000,
  "total_cost": 187.50,
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

**What This Tells You:**
- You're spending $187.50/month on Claude v2
- Switching to Titan Express could save 60% ($3,375/month)
- But consider quality trade-offs!

### Real-World Example

**Scenario**: You use Bedrock for a chatbot. Your Bedrock bill is $5K/month.

**Step 1**: Check Bedrock costs by model

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/bedrock-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Result**:
- Claude v2: $3,000 (60%)
- Claude Instant: $1,500 (30%)
- Titan Express: $500 (10%)

**Step 2**: Get recommendations for Claude v2

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/bedrock-cost-per-invocation?model=anthropic.claude-v2" \
  -H "X-API-Key: your-api-key-here"
```

**Result**: Recommendation to use Claude Instant for simple queries (save 50%)

**Step 3**: Implement routing logic

- Complex queries → Claude v2 (high quality)
- Simple queries → Claude Instant (lower cost)

**Savings**: $1,500/month or **$18,000/year**


### Optimization Tips

**How to Reduce Bedrock Costs:**

1. **Use cheaper models for simple tasks**: Titan Express for basic queries
2. **Reduce token usage**: Shorter prompts and responses
3. **Cache responses**: Cache common queries to avoid re-invocation
4. **Batch requests**: Process multiple requests together
5. **Use streaming**: Stream responses to reduce perceived latency

**Token Usage Tips:**
- **Input tokens**: Keep prompts concise, remove unnecessary context
- **Output tokens**: Set max_tokens limit to prevent long responses
- **System prompts**: Optimize system prompts to be shorter

**Example**: Reducing prompt from 500 tokens to 200 tokens:
- Before: $0.0125 per invocation
- After: $0.005 per invocation
- **Savings**: 60% reduction

---

## GPU Prevention

### Overview

GPU prevention automatically stops or terminates idle GPU instances to prevent wasted spending. This is integrated with Phase 3 (Prevention System).

### How It Works

1. **Detect idle GPUs**: Identify GPUs with < 10% utilization
2. **Calculate wasted cost**: Estimate money wasted on idle GPUs
3. **Recommend actions**: Stop or terminate based on severity
4. **Execute actions**: Automatically stop/terminate (if enabled)

### Use Cases

1. **Cost Savings**: Stop wasting money on idle GPUs
2. **Resource Cleanup**: Automatically clean up forgotten instances
3. **Budget Enforcement**: Prevent GPU cost overruns
4. **Compliance**: Ensure GPUs are used efficiently

### Basic Usage

#### Run GPU Prevention (Dry Run)

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

**What This Tells You:**
- 5 idle GPUs found
- 3 actions planned (stop or terminate)
- Potential savings: $1,500/month
- Dry run mode: No actions executed (safe to test)

#### Get GPU Cost Savings

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-cost-savings?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "total_savings": 5000.00,
  "actions_count": 10,
  "instances_stopped": 7,
  "instances_terminated": 3,
  "avg_idle_hours": 48.5
}
```

### Real-World Example

**Scenario**: You suspect you have idle GPUs wasting money.

**Step 1**: Run dry run to see what would happen

```bash
curl -X POST "https://api.costguard.ai/api/ai-ml/gpu-prevention" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"start_date": "2024-01-01", "end_date": "2024-01-31", "dry_run": true}'
```

**Result**: 8 idle GPUs found, potential savings: $3,200/month

**Step 2**: Review idle GPUs

Check the list of idle GPUs and verify they're truly idle (not running important workloads).

**Step 3**: Enable GPU prevention

Update Lambda environment variable: `GPU_PREVENTION_ENABLED=true`

**Step 4**: Run prevention cycle

```bash
curl -X POST "https://api.costguard.ai/api/ai-ml/gpu-prevention" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"start_date": "2024-01-01", "end_date": "2024-01-31", "dry_run": false}'
```

**Result**: 8 idle GPUs stopped, **$3,200/month saved**


### Safety Features

**Protection Mechanisms:**

1. **Dry run mode**: Test without executing actions (default: enabled)
2. **Tag-based protection**: Instances with `CostGuard:Protected=true` are never stopped
3. **Environment protection**: Production instances are protected by default
4. **Approval workflow**: Require manual approval before stopping instances
5. **Audit logging**: All actions are logged for review

**Protected Instances:**

Instances are protected if they have any of these tags:
- `Environment=production`
- `CostGuard=protected`
- `CostGuard:Protected=true`

**Example**: Protect a production instance

```bash
aws ec2 create-tags \
  --resources i-1234567890abcdef0 \
  --tags Key=CostGuard:Protected,Value=true
```

### Best Practices

1. **Start with dry run**: Always test with `dry_run=true` first
2. **Review idle GPUs**: Manually verify idle GPUs before enabling prevention
3. **Use tags for protection**: Tag important instances as protected
4. **Monitor savings**: Track actual savings vs estimates
5. **Set up alerts**: Get notified when GPUs are stopped

---

## Multi-Account GPU Tracking

### Overview

If you have multiple AWS accounts (e.g., dev, staging, prod), you can aggregate GPU costs across all accounts.

### How It Works

1. **Set up cross-account roles**: Allow CostGuard to access member accounts
2. **Query multi-account endpoints**: Aggregate GPU costs across accounts
3. **View organization-wide metrics**: Total GPU costs, utilization, and trends

### Use Cases

1. **Organization-wide GPU Budget**: Track total GPU spending across all accounts
2. **Account Comparison**: Compare GPU costs across dev, staging, and prod
3. **Cost Allocation**: Allocate GPU costs to business units or teams
4. **Utilization Monitoring**: Track GPU utilization across organization

### Basic Usage

#### Get Multi-Account GPU Costs

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/multi-account/gpu-costs?org_id=o-1234567890&account_ids=123456789012,234567890123,345678901234&start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "org_id": "o-1234567890",
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
  }
}
```

**What This Tells You:**
- Total GPU cost across all accounts: $25,000
- Account 123456789012 has highest GPU spend: $10,000
- $2,000 wasted on idle GPUs across all accounts

#### Get Multi-Account GPU Utilization

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/multi-account/gpu-utilization?org_id=o-1234567890&account_ids=123456789012,234567890123,345678901234&start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "organization_avg_utilization": 75.6,
  "accounts": [
    {
      "account_id": "123456789012",
      "avg_utilization": 75.5,
      "gpu_hours": 1000.0
    },
    {
      "account_id": "234567890123",
      "avg_utilization": 82.3,
      "gpu_hours": 800.0
    }
  ]
}
```

### Real-World Example

**Scenario**: You have 3 AWS accounts (dev, staging, prod). You want to see total GPU spending.

**Step 1**: Get multi-account GPU costs

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/multi-account/gpu-costs?org_id=o-myorg&account_ids=111,222,333&start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

**Result**:
- Dev account: $5,000
- Staging account: $3,000
- Prod account: $20,000
- **Total**: $28,000

**Step 2**: Identify optimization opportunities

- Dev account has $1,000 in idle GPUs (20% waste)
- Staging account has $500 in idle GPUs (17% waste)
- Prod account is well-optimized (5% idle)

**Action**: Focus on dev and staging accounts for cost optimization

**Savings**: $1,500/month or **$18,000/year**


---

## Best Practices

### Cost Optimization

**1. Track GPU Costs Weekly**

Set up a weekly review of GPU costs:

```bash
# Get last 7 days of GPU costs
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=$(date -d '7 days ago' +%Y-%m-%d)&end_date=$(date +%Y-%m-%d)" \
  -H "X-API-Key: your-api-key-here"
```

**2. Stop Idle GPUs Immediately**

Check for idle GPUs daily:

```bash
# Get idle GPUs
curl -X GET "https://api.costguard.ai/api/ai-ml/idle-gpus?start_date=$(date -d '1 day ago' +%Y-%m-%d)&end_date=$(date +%Y-%m-%d)" \
  -H "X-API-Key: your-api-key-here"
```

**3. Use Spot Instances for Training**

Always check spot recommendations before starting training:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/spot-recommendations?workload_id=my-training-instance" \
  -H "X-API-Key: your-api-key-here"
```

**4. Right-Size Instance Types**

Compare instance types before choosing:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/training-comparison?model=my-model&instance_types=p3.2xlarge,p3.8xlarge,g4dn.xlarge" \
  -H "X-API-Key: your-api-key-here"
```

**5. Monitor Cost-Per-Inference**

Track cost-per-inference trends to catch cost increases early:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/inference-trends?model=my-model&days=30" \
  -H "X-API-Key: your-api-key-here"
```

### Workload Classification

**1. Use Manual Classification for Critical Workloads**

For production workloads, use manual classification to ensure accuracy:

```bash
curl -X POST "https://api.costguard.ai/api/ai-ml/workload-classification" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"instance_id": "i-prod-instance", "workload_type": "inference"}'
```

**2. Tag Instances for Automatic Classification**

Use EC2 tags for persistent classification:

```bash
aws ec2 create-tags \
  --resources i-1234567890abcdef0 \
  --tags Key=CostGuard:WorkloadType,Value=training
```

**3. Review Low-Confidence Classifications**

Check classifications with confidence < 0.8 and manually verify:

```bash
# Get classification
curl -X GET "https://api.costguard.ai/api/ai-ml/workload-classification?instance_id=i-123" \
  -H "X-API-Key: your-api-key-here"

# If confidence < 0.8, manually classify
curl -X POST "https://api.costguard.ai/api/ai-ml/workload-classification" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"instance_id": "i-123", "workload_type": "training"}'
```

### GPU Prevention

**1. Start with Dry Run**

Always test prevention with dry run first:

```bash
curl -X POST "https://api.costguard.ai/api/ai-ml/gpu-prevention" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"dry_run": true}'
```

**2. Protect Production Instances**

Tag production instances to prevent accidental termination:

```bash
aws ec2 create-tags \
  --resources i-prod-instance \
  --tags Key=Environment,Value=production
```

**3. Review Prevention Actions**

Check prevention audit logs regularly:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-cost-savings?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here"
```

### Spot Instances

**1. Always Use Checkpointing**

Save training state every 15-30 minutes:

```python
# Save checkpoint every 100 steps
if step % 100 == 0:
    save_checkpoint(model, optimizer, step, 'checkpoint.pt')
```

**2. Monitor Interruption Rates**

Track actual interruptions vs estimates and adjust strategy:

```bash
# Check spot savings and interruptions
curl -X GET "https://api.costguard.ai/api/ai-ml/spot-savings?current_instance=p3.2xlarge" \
  -H "X-API-Key: your-api-key-here"
```

**3. Use Spot for Non-Critical Workloads First**

Start with experiments and hyperparameter tuning, then expand to production training.


### SageMaker & Bedrock

**1. Delete Idle Endpoints Weekly**

Check for idle SageMaker endpoints every week:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/sagemaker-idle-endpoints" \
  -H "X-API-Key: your-api-key-here"
```

**2. Use Auto-Scaling for Inference**

Configure SageMaker auto-scaling to scale down during low traffic:

```bash
aws application-autoscaling register-scalable-target \
  --service-namespace sagemaker \
  --resource-id endpoint/my-endpoint/variant/AllTraffic \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --min-capacity 1 \
  --max-capacity 10
```

**3. Optimize Bedrock Model Selection**

Use cheaper models for simple tasks:

- Simple queries → Titan Express ($0.0002/1K tokens)
- Medium complexity → Claude Instant ($0.0008/1K tokens)
- Complex queries → Claude v2 ($0.008/1K tokens)

**4. Cache Bedrock Responses**

Cache common queries to avoid re-invocation:

```python
import hashlib
import json

def get_cached_response(prompt, cache):
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
    if prompt_hash in cache:
        return cache[prompt_hash]
    
    response = bedrock.invoke_model(prompt)
    cache[prompt_hash] = response
    return response
```

### Multi-Account Management

**1. Set Up Cross-Account Roles**

Use CloudFormation StackSets to deploy roles to all accounts:

```bash
aws cloudformation create-stack-set \
  --stack-set-name CostGuardPhase6MemberRole \
  --template-body file://member_account_role.yaml
```

**2. Monitor Organization-Wide Metrics**

Check organization-wide GPU costs monthly:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/multi-account/gpu-costs?org_id=o-myorg&account_ids=111,222,333" \
  -H "X-API-Key: your-api-key-here"
```

**3. Allocate Costs to Business Units**

Use account structure to allocate costs:

- Account 111 (Dev) → Engineering team
- Account 222 (Staging) → QA team
- Account 333 (Prod) → Product team

---

## Troubleshooting

### Common Issues

#### Issue 1: No GPU Cost Data

**Symptom**: API returns empty `gpu_costs` array

**Possible Causes:**
1. No GPU instances in the account
2. Date range is outside available data
3. IAM permissions missing

**Solution:**

```bash
# Check if you have GPU instances
aws ec2 describe-instances --filters "Name=instance-type,Values=p3.*,p4.*,g4.*,g5.*"

# Check IAM permissions
aws iam get-role-policy --role-name CostGuardLambdaExecutionRole --policy-name CostGuardPhase6Policy

# Try a wider date range
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-12-31" \
  -H "X-API-Key: your-api-key-here"
```

#### Issue 2: Low Classification Confidence

**Symptom**: Workload classification has confidence < 0.6

**Possible Causes:**
1. Insufficient CloudWatch metrics data
2. Unusual GPU utilization pattern
3. Instance recently started

**Solution:**

```bash
# Use manual classification
curl -X POST "https://api.costguard.ai/api/ai-ml/workload-classification" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"instance_id": "i-123", "workload_type": "training"}'

# Or use EC2 tags
aws ec2 create-tags \
  --resources i-123 \
  --tags Key=CostGuard:WorkloadType,Value=training
```

#### Issue 3: Spot Recommendations Not Suitable

**Symptom**: Spot recommendations show `suitable: false`

**Possible Causes:**
1. Workload is inference (not suitable for spot)
2. Workload is idle (no recommendation needed)
3. Interruption risk too high

**Solution:**

Check workload type:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/workload-classification?instance_id=i-123" \
  -H "X-API-Key: your-api-key-here"
```

If workload is inference, spot instances are not recommended (too risky for customer-facing services).


#### Issue 4: Cost-Per-Inference is Zero

**Symptom**: API returns `cost_per_inference: 0.0`

**Possible Causes:**
1. No inference requests tracked
2. Request tracking not configured
3. Endpoint name mismatch

**Solution:**

```bash
# Check if requests are being tracked
curl -X GET "https://api.costguard.ai/api/ai-ml/cost-per-inference?start_date=2024-01-01&end_date=2024-01-31&model=my-model&endpoint=my-endpoint" \
  -H "X-API-Key: your-api-key-here"

# Verify endpoint name
aws sagemaker list-endpoints
aws apigateway get-rest-apis
```

If requests are not being tracked, ensure CloudWatch metrics are enabled for your endpoint.

#### Issue 5: GPU Prevention Not Working

**Symptom**: Idle GPUs are not being stopped

**Possible Causes:**
1. GPU prevention disabled (`GPU_PREVENTION_ENABLED=false`)
2. Dry run mode enabled (`GPU_PREVENTION_DRY_RUN=true`)
3. Instances are protected by tags

**Solution:**

```bash
# Check Lambda environment variables
aws lambda get-function-configuration --function-name CostGuardLambda --query 'Environment.Variables'

# Enable GPU prevention
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{GPU_PREVENTION_ENABLED=true,GPU_PREVENTION_DRY_RUN=false}"

# Check if instances are protected
aws ec2 describe-tags --filters "Name=resource-id,Values=i-123"
```

#### Issue 6: Multi-Account Access Denied

**Symptom**: Multi-account endpoints return "Access Denied" error

**Possible Causes:**
1. Cross-account role not set up
2. External ID mismatch
3. IAM permissions missing

**Solution:**

```bash
# Test role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::MEMBER_ACCOUNT:role/CostGuardCollectorRole \
  --role-session-name test \
  --external-id your-external-id

# Check trust relationship
aws iam get-role --role-name CostGuardCollectorRole --query 'Role.AssumeRolePolicyDocument'
```

### Performance Issues

#### Slow API Response Times

**Symptom**: API responses take > 10 seconds

**Possible Causes:**
1. Cache miss (first query)
2. Large date range
3. Many GPU instances

**Solution:**

```bash
# Use smaller date ranges
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-07" \
  -H "X-API-Key: your-api-key-here"

# Query same data within 24 hours to use cache
# Second query will be < 2 seconds
```

**Cache Behavior:**
- First query: < 10 seconds (uncached)
- Subsequent queries (within 24 hours): < 2 seconds (cached)

### Getting Help

If you encounter issues not covered here:

1. **Check CloudWatch Logs**: View Lambda function logs for errors
2. **Review API Documentation**: See [API Documentation](../api/phase6-api-documentation.md)
3. **Check Deployment Guide**: See [Deployment Guide](../deployment/phase6-deployment-guide.md)
4. **Contact Support**: Email support@costguard.ai with:
   - Error message
   - API endpoint and parameters
   - CloudWatch log excerpt
   - AWS account ID (last 4 digits only)

---

## FAQ

### General Questions

**Q: How much does Phase 6 cost to run?**

A: Phase 6 adds approximately $0.50/month to your AWS costs (Cost Explorer API calls). All other services (Lambda, DynamoDB, CloudWatch) stay within AWS Free Tier limits.

**Q: Does Phase 6 work with existing CostGuard infrastructure?**

A: Yes! Phase 6 is fully backward compatible with Phases 1-5. No changes to existing infrastructure required.

**Q: Can I use Phase 6 without Phases 1-5?**

A: No. Phase 6 requires Phase 1 (Cost Explorer integration) and Phase 1.5 (CloudWatch metrics) as prerequisites.

**Q: Which GPU instance types are supported?**

A: Phase 6 supports all AWS GPU instance types:
- P3 family (p3.2xlarge, p3.8xlarge, p3.16xlarge, p3dn.24xlarge)
- P4 family (p4d.24xlarge, p4de.24xlarge)
- P5 family (p5.48xlarge)
- G4 family (g4dn.xlarge, g4dn.2xlarge, etc.)
- G5 family (g5.xlarge, g5.2xlarge, etc.)
- G6 family (g6.xlarge, g6.2xlarge, etc.)


### GPU Cost Tracking

**Q: How accurate are GPU cost calculations?**

A: GPU cost calculations are accurate within 2% of actual AWS bills. We use Cost Explorer API data, which is the same data AWS uses for billing.

**Q: How often is GPU cost data updated?**

A: GPU cost data is updated every 24 hours. Cost Explorer API provides data with a 24-hour delay.

**Q: Can I track GPU costs in real-time?**

A: No. Cost Explorer API has a 24-hour delay. The fastest you can see GPU costs is 24 hours after usage.

**Q: Why are my GPU costs different from my AWS bill?**

A: Small differences (< 2%) are normal due to:
- Rounding in calculations
- Data transfer costs not fully attributed
- Timing differences in data collection

If differences are > 2%, contact support.

### Workload Classification

**Q: How accurate is automatic workload classification?**

A: Automatic classification achieves 90%+ accuracy for typical workloads. Confidence scores indicate reliability:
- 0.9-1.0: Very confident (90%+ accuracy)
- 0.8-0.9: Confident (80-90% accuracy)
- 0.6-0.8: Moderate (60-80% accuracy)
- < 0.6: Low confidence (manual verification recommended)

**Q: Can I override automatic classification?**

A: Yes! Use manual classification via API or EC2 tags:

```bash
# Via API
curl -X POST "https://api.costguard.ai/api/ai-ml/workload-classification" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"instance_id": "i-123", "workload_type": "training"}'

# Via EC2 tags
aws ec2 create-tags --resources i-123 --tags Key=CostGuard:WorkloadType,Value=training
```

**Q: What if my workload doesn't fit training/inference/idle categories?**

A: Use manual classification to assign the closest category. For example:
- Data preprocessing → Training
- Model serving → Inference
- Development/testing → Idle (or create custom tag)

**Q: How long does classification take?**

A: Classification is instant for cached results (< 1 second). First-time classification takes 5-10 seconds to analyze CloudWatch metrics.

### Cost-Per-Inference

**Q: How are inference requests tracked?**

A: CostGuard AI tracks inference requests from:
- API Gateway (CloudWatch metrics)
- Lambda function invocations (CloudWatch metrics)
- SageMaker inference endpoints (CloudWatch metrics)
- Bedrock model invocations (CloudWatch Logs)

**Q: What if my inference requests aren't tracked?**

A: Ensure CloudWatch metrics are enabled for your endpoint. For custom endpoints, you may need to manually log request counts.

**Q: Does cost-per-inference include all costs?**

A: Yes! Cost-per-inference includes:
- Compute costs (EC2, Lambda, SageMaker)
- API costs (Bedrock, SageMaker)
- Data transfer costs (ingress/egress)

**Q: Can I track cost-per-inference for multiple models?**

A: Yes! Use the `model` and `endpoint` parameters to filter by specific models:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/cost-per-inference?model=bert&endpoint=api-1" \
  -H "X-API-Key: your-api-key-here"
```

### Spot Instances

**Q: How much can I save with spot instances?**

A: Spot instances typically save 60-70% compared to on-demand instances. Savings vary by instance type and region:
- P3 instances: 60-70% savings
- G4 instances: 50-60% savings
- P4 instances: 65-75% savings

**Q: What is interruption risk?**

A: Interruption risk is the probability that your spot instance will be interrupted by AWS (reclaimed for on-demand capacity). Risk levels:
- 0-10%: Very low risk (< 1 interruption per month)
- 10-20%: Low risk (1-2 interruptions per month)
- 20-30%: Moderate risk (2-4 interruptions per month)
- 30%+: High risk (> 4 interruptions per month)

**Q: What happens when a spot instance is interrupted?**

A: AWS sends a 2-minute warning, then terminates the instance. Your training job should:
1. Save checkpoint when warning is received
2. Resume from checkpoint on new instance

**Q: Are spot instances suitable for inference?**

A: No! Spot instances are NOT recommended for inference (customer-facing services) due to interruption risk. Use spot only for:
- Training workloads
- Batch processing
- Experiments and hyperparameter tuning

**Q: How do I handle spot interruptions?**

A: Use checkpointing to save training state every 15-30 minutes:

```python
import torch

# Save checkpoint
torch.save({
    'epoch': epoch,
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
}, 'checkpoint.pt')

# Resume from checkpoint
checkpoint = torch.load('checkpoint.pt')
model.load_state_dict(checkpoint['model_state_dict'])
optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
epoch = checkpoint['epoch']
```


### GPU Prevention

**Q: Will GPU prevention stop my production instances?**

A: No! GPU prevention has multiple safety mechanisms:
- Instances tagged with `Environment=production` are protected
- Instances tagged with `CostGuard:Protected=true` are protected
- Dry run mode is enabled by default (no actions executed)
- Approval workflow can be enabled for manual review

**Q: How do I enable GPU prevention?**

A: Update Lambda environment variables:

```bash
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables="{GPU_PREVENTION_ENABLED=true,GPU_PREVENTION_DRY_RUN=false}"
```

**Q: Can I test GPU prevention without stopping instances?**

A: Yes! Use dry run mode:

```bash
curl -X POST "https://api.costguard.ai/api/ai-ml/gpu-prevention" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"dry_run": true}'
```

This shows what would happen without executing actions.

**Q: What's the difference between stop and terminate?**

A: 
- **Stop**: Instance is stopped but not deleted. You can restart it later. EBS volumes are preserved (you pay for storage).
- **Terminate**: Instance is permanently deleted. EBS volumes are deleted (no storage costs).

CostGuard AI uses severity-based actions:
- Low severity (< 24 hours idle): No action
- Medium severity (24-48 hours idle): Stop
- High severity (48-72 hours idle): Stop
- Critical severity (> 72 hours idle): Terminate

**Q: Can I customize idle thresholds?**

A: Yes! Use the `threshold` parameter:

```bash
curl -X POST "https://api.costguard.ai/api/ai-ml/gpu-prevention" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"threshold": 5.0}'  # 5% utilization threshold instead of 10%
```

### SageMaker & Bedrock

**Q: Does Phase 6 work with SageMaker Studio?**

A: Yes! Phase 6 tracks all SageMaker services:
- Training jobs
- Inference endpoints
- Notebook instances
- Studio notebooks

**Q: Can I track Bedrock costs by application?**

A: Yes! Use CloudWatch Logs to tag Bedrock invocations by application, then filter by application in the API.

**Q: How do I reduce Bedrock costs?**

A: 
1. Use cheaper models for simple tasks (Titan Express instead of Claude)
2. Reduce token usage (shorter prompts and responses)
3. Cache common responses
4. Batch requests when possible

**Q: What's the difference between SageMaker and self-hosted inference?**

A: 
- **SageMaker**: Managed service, easier to use, higher cost per inference
- **Self-hosted (EC2)**: More control, lower cost per inference, requires more management

Use cost-per-inference calculations to compare and choose the best option.

### Multi-Account

**Q: How many accounts can I track?**

A: Phase 6 supports up to 100 AWS accounts per organization. For larger organizations, contact support.

**Q: Do I need to deploy Phase 6 to each account?**

A: No! Deploy Phase 6 once in your management account. Use cross-account roles to access member accounts.

**Q: What permissions are needed for cross-account access?**

A: Member accounts need a role with:
- Cost Explorer read access
- CloudWatch read access
- EC2 describe access
- SageMaker describe access

See [Deployment Guide](../deployment/phase6-deployment-guide.md) for detailed setup instructions.

**Q: Can I exclude certain accounts from tracking?**

A: Yes! Simply don't include them in the `account_ids` parameter:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/multi-account/gpu-costs?org_id=o-myorg&account_ids=111,222" \
  -H "X-API-Key: your-api-key-here"
```

### Pricing & Billing

**Q: How much does CostGuard AI Phase 6 cost?**

A: Phase 6 adds approximately $0.50/month to your AWS costs:
- Cost Explorer API: ~$0.50/month (50 additional calls)
- CloudWatch API: $0 (within free tier)
- Lambda: $0 (within free tier)
- DynamoDB: $0 (within free tier)

**Q: Will Phase 6 increase my AWS bill?**

A: Yes, by approximately $0.50/month. But you'll save 20-30% on GPU costs ($7K-10K/month for typical AI startup), so the ROI is 14,000x!

**Q: Is there a free trial?**

A: Phase 6 is part of CostGuard AI. Contact sales for pricing and trial information.

**Q: Can I use Phase 6 with AWS Free Tier?**

A: Yes! Phase 6 is designed to stay within AWS Free Tier limits for Lambda, DynamoDB, and CloudWatch. Only Cost Explorer API calls incur charges (~$0.50/month).

### Technical Questions

**Q: What programming languages are supported?**

A: Phase 6 is language-agnostic. It tracks GPU costs regardless of what language your ML code is written in (Python, R, Julia, etc.).

**Q: Does Phase 6 work with Kubernetes?**

A: Yes! Phase 6 tracks EC2 GPU instances regardless of orchestration (Kubernetes, ECS, bare EC2).

**Q: Can I integrate Phase 6 with my CI/CD pipeline?**

A: Yes! Use the API to integrate with your CI/CD:

```bash
# In your CI/CD pipeline
COST=$(curl -X GET "https://api.costguard.ai/api/ai-ml/cost-per-training?job_id=$JOB_ID" \
  -H "X-API-Key: $API_KEY" | jq '.total_cost')

if [ $COST -gt 100 ]; then
  echo "Training cost exceeded budget: $COST"
  exit 1
fi
```

**Q: Does Phase 6 support custom metrics?**

A: Phase 6 uses standard CloudWatch metrics. For custom metrics, you can publish them to CloudWatch and Phase 6 will use them for classification.

**Q: Can I export data to CSV or JSON?**

A: Yes! API responses are in JSON format. Use `jq` or similar tools to convert to CSV:

```bash
curl -X GET "https://api.costguard.ai/api/ai-ml/gpu-costs?start_date=2024-01-01&end_date=2024-01-31" \
  -H "X-API-Key: your-api-key-here" | jq -r '.gpu_costs[] | [.date, .instance_id, .cost] | @csv'
```

---

## Next Steps

Congratulations! You've learned how to use CostGuard AI Phase 6 to track and optimize your AI/ML workload costs.

### Quick Wins (Do These First)

1. **Find idle GPUs**: Save $5K/month by stopping idle GPUs
   ```bash
   curl -X GET "https://api.costguard.ai/api/ai-ml/idle-gpus?start_date=2024-01-01&end_date=2024-01-31" \
     -H "X-API-Key: your-api-key-here"
   ```

2. **Use spot instances**: Save 70% on training costs
   ```bash
   curl -X GET "https://api.costguard.ai/api/ai-ml/spot-recommendations?workload_id=my-training-instance" \
     -H "X-API-Key: your-api-key-here"
   ```

3. **Delete idle SageMaker endpoints**: Save $1K/month
   ```bash
   curl -X GET "https://api.costguard.ai/api/ai-ml/sagemaker-idle-endpoints" \
     -H "X-API-Key: your-api-key-here"
   ```

### Additional Resources

- **API Documentation**: [Phase 6 API Documentation](../api/phase6-api-documentation.md)
- **Deployment Guide**: [Phase 6 Deployment Guide](../deployment/phase6-deployment-guide.md)
- **Requirements**: [Phase 6 Requirements](.kiro/specs/ai-ml-workload-costs/requirements.md)
- **Design Document**: [Phase 6 Design](.kiro/specs/ai-ml-workload-costs/design.md)

### Get Support

- **Email**: support@costguard.ai
- **Documentation**: https://docs.costguard.ai
- **GitHub**: https://github.com/costguard-ai/costguard

### Share Your Success

We'd love to hear how much you're saving with Phase 6! Share your success story:
- Twitter: @costguardai
- LinkedIn: CostGuard AI
- Email: success@costguard.ai

---

**Happy Cost Optimizing! 🚀**

*Last Updated: February 2026*  
*Version: 1.0*
