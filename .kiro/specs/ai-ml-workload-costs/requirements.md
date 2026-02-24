# Phase 6: AI/ML Workload Cost Management - Requirements

**Status:** Draft  
**Priority:** CRITICAL - Highest hackathon alignment  
**Estimated Effort:** 2-3 weeks  
**Created:** February 2026

---

## Overview

Phase 6 adds AI/ML-specific cost management capabilities to CostGuard AI, focusing on GPU cost tracking, cost-per-inference calculations, and ML workload optimization. This phase targets AI startups and ML platform engineers who spend 60-80% of their AWS budget on GPU compute.

**Key Differentiator:** NO competitor (CloudZero, nOps, Vantage) provides AI/ML-specific cost tracking and optimization.

---

## Business Context

### Problem Statement

AI startups face acute pain with GPU costs:
- **80% of funding** goes to compute (GPU costs)
- **$35K/month** for 8x H100 GPUs (typical AI startup)
- **No visibility** into cost-per-inference or cost-per-training
- **Can't optimize** without understanding workload costs
- **"Where is my GPU money going?"** is #1 question from AI founders

### Target Users

**Primary:** AI Startup CTOs/Founders
- Company size: 5-50 employees
- AWS spend: $10K-100K/month
- GPU spend: 60-80% of AWS spend
- Willingness to pay: $50-100/month

**Secondary:** ML Platform Engineers
- Company size: 50-500 employees
- AWS spend: $100K-1M/month
- GPU spend: 40-60% of AWS spend
- Willingness to pay: $100-500/month

**Tertiary:** SageMaker/Bedrock Users
- Any company size
- AWS spend: $5K-50K/month on SageMaker/Bedrock
- Willingness to pay: $50-200/month

### Success Metrics

- **Cost Savings:** 20-30% reduction in GPU costs ($7K-10K/month for typical AI startup)
- **Visibility:** 100% of GPU costs classified by workload type
- **Accuracy:** 90%+ accuracy in workload classification
- **Adoption:** 50+ AI startups using Phase 6 features within 3 months

---

## Functional Requirements

### FR-1: GPU Cost Tracking

**FR-1.1** The system SHALL track costs for EC2 GPU instance types (p3, p4, p4d, p5, g4, g5, g6)

**FR-1.2** The system SHALL classify GPU workloads as "training" or "inference"

**FR-1.3** The system SHALL calculate cost per GPU hour for each workload type

**FR-1.4** The system SHALL track GPU utilization percentage

**FR-1.5** The system SHALL identify idle GPU time (utilization < 10%)

**FR-1.6** The system SHALL provide daily, weekly, and monthly GPU cost breakdowns

**FR-1.7** The system SHALL support filtering by instance type, workload type, and date range

---

### FR-2: Workload Classification

**FR-2.1** The system SHALL automatically classify workloads using CloudWatch GPU metrics

**FR-2.2** The system SHALL provide classification confidence scores (0-100%)

**FR-2.3** The system SHALL allow manual workload classification via tags

**FR-2.4** The system SHALL use the following classification rules:
- Training: GPU utilization > 70% for > 1 hour continuously
- Inference: GPU utilization 20-70% with frequent spikes
- Idle: GPU utilization < 10%

**FR-2.5** The system SHALL re-classify workloads when tags are updated

**FR-2.6** The system SHALL store classification history for audit purposes

---

### FR-3: Cost-Per-Inference Calculations

**FR-3.1** The system SHALL calculate cost per inference request

**FR-3.2** The system SHALL track inference requests from:
- API Gateway endpoints
- Lambda function invocations
- SageMaker inference endpoints
- Bedrock model invocations

**FR-3.3** The system SHALL calculate total inference costs including:
- Compute costs (EC2, Lambda, SageMaker)
- API costs (Bedrock, SageMaker)
- Data transfer costs

**FR-3.4** The system SHALL provide cost-per-inference by model and endpoint

**FR-3.5** The system SHALL track cost-per-inference trends over time

**FR-3.6** The system SHALL alert when cost-per-inference exceeds threshold

---

### FR-4: Cost-Per-Training Calculations

**FR-4.1** The system SHALL calculate cost per training job

**FR-4.2** The system SHALL track training jobs from:
- SageMaker training jobs
- EC2 GPU instances with "training" classification
- Custom training workflows

**FR-4.3** The system SHALL calculate total training costs including:
- Compute costs (EC2, SageMaker)
- Storage costs (S3, EBS)
- Data transfer costs

**FR-4.4** The system SHALL provide cost-per-training by model and dataset

**FR-4.5** The system SHALL track training duration and cost per hour

**FR-4.6** The system SHALL compare training costs across different instance types

---

### FR-5: Spot Instance Recommendations

**FR-5.1** The system SHALL identify training workloads suitable for spot instances

**FR-5.2** The system SHALL calculate potential savings from spot instances (up to 90%)

**FR-5.3** The system SHALL recommend specific spot instance types

**FR-5.4** The system SHALL show interruption risk for spot recommendations

**FR-5.5** The system SHALL provide "what-if" scenarios for spot instance usage

**FR-5.6** The system SHALL track actual spot instance usage and savings

---

### FR-6: SageMaker Cost Tracking

**FR-6.1** The system SHALL track SageMaker training job costs

**FR-6.2** The system SHALL track SageMaker inference endpoint costs

**FR-6.3** The system SHALL track SageMaker notebook instance costs

**FR-6.4** The system SHALL provide cost breakdown by job type (training, inference, notebook)

**FR-6.5** The system SHALL recommend cost-optimized instance types for SageMaker

**FR-6.6** The system SHALL alert on idle SageMaker endpoints (< 10 requests/hour)

---

### FR-7: Bedrock Cost Tracking

**FR-7.1** The system SHALL track Bedrock model invocation costs

**FR-7.2** The system SHALL track costs by model (Claude, Titan, Llama, etc.)

**FR-7.3** The system SHALL calculate cost per invocation

**FR-7.4** The system SHALL track input and output token counts

**FR-7.5** The system SHALL provide cost breakdown by model and application

**FR-7.6** The system SHALL recommend cost-optimized models based on usage patterns

---

## Non-Functional Requirements

### NFR-1: Performance

**NFR-1.1** GPU cost queries SHALL return results within 2 seconds (cached)

**NFR-1.2** GPU cost queries SHALL return results within 10 seconds (uncached)

**NFR-1.3** Workload classification SHALL complete within 5 minutes for 100 instances

**NFR-1.4** Cost-per-inference calculations SHALL update every 15 minutes

**NFR-1.5** The system SHALL support up to 1,000 GPU instances per account

---

### NFR-2: Accuracy

**NFR-2.1** Workload classification SHALL achieve 90%+ accuracy

**NFR-2.2** Cost calculations SHALL be accurate within 2% of actual AWS bills

**NFR-2.3** Spot instance savings estimates SHALL be accurate within 5%

**NFR-2.4** Cost-per-inference calculations SHALL account for all cost components

---

### NFR-3: Scalability

**NFR-3.1** The system SHALL scale to 1,000 GPU instances per account

**NFR-3.2** The system SHALL scale to 10 million inference requests per day

**NFR-3.3** The system SHALL scale to 1,000 training jobs per month

**NFR-3.4** The system SHALL support multi-account deployments (Phase 5 integration)

---

### NFR-4: Reliability

**NFR-4.1** The system SHALL have 99.9% uptime

**NFR-4.2** Cost data collection SHALL retry up to 3 times on failure

**NFR-4.3** The system SHALL gracefully handle missing CloudWatch metrics

**NFR-4.4** The system SHALL continue operating if workload classification fails

---

### NFR-5: Cost Efficiency

**NFR-5.1** Phase 6 SHALL add no more than $1.00/month to AWS costs

**NFR-5.2** The system SHALL use aggressive caching (24-hour TTL for GPU costs)

**NFR-5.3** The system SHALL batch Cost Explorer API calls where possible

**NFR-5.4** The system SHALL stay within AWS Free Tier limits where possible

---

### NFR-6: Usability

**NFR-6.1** API responses SHALL include clear explanations of calculations

**NFR-6.2** Workload classifications SHALL include confidence scores

**NFR-6.3** Spot instance recommendations SHALL show risk/reward trade-offs

**NFR-6.4** Cost breakdowns SHALL be easy to understand for non-technical users

---

## API Requirements

### API-1: GPU Cost Tracking Endpoints

**API-1.1** `GET /api/ai-ml/gpu-costs`
- Query params: start_date, end_date, workload_type, instance_type
- Response: GPU costs by date, workload type, and instance type
- Response time: < 2 seconds (cached), < 10 seconds (uncached)

**API-1.2** `GET /api/ai-ml/gpu-utilization`
- Query params: start_date, end_date, instance_id
- Response: GPU utilization metrics by instance
- Response time: < 2 seconds

**API-1.3** `GET /api/ai-ml/idle-gpus`
- Query params: threshold (default: 10%)
- Response: List of idle GPU instances
- Response time: < 2 seconds

---

### API-2: Workload Classification Endpoints

**API-2.1** `GET /api/ai-ml/workload-classification`
- Query params: instance_id, start_date, end_date
- Response: Workload classification with confidence score
- Response time: < 1 second

**API-2.2** `POST /api/ai-ml/workload-classification`
- Request body: instance_id, workload_type (manual override)
- Response: Updated classification
- Response time: < 1 second

---

### API-3: Cost-Per-Inference Endpoints

**API-3.1** `GET /api/ai-ml/cost-per-inference`
- Query params: start_date, end_date, model, endpoint
- Response: Cost per inference by model and endpoint
- Response time: < 2 seconds

**API-3.2** `GET /api/ai-ml/inference-trends`
- Query params: start_date, end_date, model
- Response: Cost-per-inference trends over time
- Response time: < 2 seconds

---

### API-4: Cost-Per-Training Endpoints

**API-4.1** `GET /api/ai-ml/cost-per-training`
- Query params: start_date, end_date, model, dataset
- Response: Cost per training job
- Response time: < 2 seconds

**API-4.2** `GET /api/ai-ml/training-comparison`
- Query params: model, instance_types
- Response: Training cost comparison across instance types
- Response time: < 2 seconds

---

### API-5: Spot Instance Recommendation Endpoints

**API-5.1** `GET /api/ai-ml/spot-recommendations`
- Query params: workload_id
- Response: Spot instance recommendations with savings estimates
- Response time: < 2 seconds

**API-5.2** `GET /api/ai-ml/spot-savings`
- Query params: start_date, end_date
- Response: Actual spot instance savings
- Response time: < 2 seconds

---

### API-6: SageMaker Cost Endpoints

**API-6.1** `GET /api/ai-ml/sagemaker-costs`
- Query params: start_date, end_date, job_type
- Response: SageMaker costs by job type
- Response time: < 2 seconds

**API-6.2** `GET /api/ai-ml/sagemaker-idle-endpoints`
- Query params: threshold (default: 10 requests/hour)
- Response: List of idle SageMaker endpoints
- Response time: < 2 seconds

---

### API-7: Bedrock Cost Endpoints

**API-7.1** `GET /api/ai-ml/bedrock-costs`
- Query params: start_date, end_date, model
- Response: Bedrock costs by model
- Response time: < 2 seconds

**API-7.2** `GET /api/ai-ml/bedrock-cost-per-invocation`
- Query params: start_date, end_date, model
- Response: Cost per invocation by model
- Response time: < 2 seconds

---

## Data Requirements

### DR-1: GPU Cost Data Storage

**DR-1.1** The system SHALL store GPU cost data for at least 90 days

**DR-1.2** The system SHALL store workload classifications with timestamps

**DR-1.3** The system SHALL store GPU utilization metrics at 5-minute intervals

**DR-1.4** The system SHALL store cost-per-inference data for at least 30 days

**DR-1.5** The system SHALL store cost-per-training data for at least 90 days

---

### DR-2: Data Retention

**DR-2.1** GPU cost data SHALL be retained for 90 days

**DR-2.2** Workload classifications SHALL be retained for 90 days

**DR-2.3** Cost-per-inference data SHALL be retained for 30 days

**DR-2.4** Cost-per-training data SHALL be retained for 90 days

**DR-2.5** Spot instance recommendations SHALL be retained for 30 days

---

### DR-3: Data Privacy

**DR-3.1** The system SHALL NOT store model weights or training data

**DR-3.2** The system SHALL NOT store inference request payloads

**DR-3.3** The system SHALL store only metadata (costs, metrics, timestamps)

**DR-3.4** The system SHALL encrypt all data at rest

**DR-3.5** The system SHALL encrypt all data in transit (TLS 1.2+)

---

## Integration Requirements

### IR-1: AWS Service Integration

**IR-1.1** The system SHALL integrate with Cost Explorer API for GPU cost data

**IR-1.2** The system SHALL integrate with CloudWatch API for GPU metrics

**IR-1.3** The system SHALL integrate with EC2 API for instance metadata

**IR-1.4** The system SHALL integrate with SageMaker API for training/inference jobs

**IR-1.5** The system SHALL integrate with Bedrock API for model invocation metrics

**IR-1.6** The system SHALL integrate with Pricing API for spot instance prices

---

### IR-2: Phase Integration

**IR-2.1** The system SHALL integrate with Phase 1 (Cost Explorer data)

**IR-2.2** The system SHALL integrate with Phase 2 (Forecasting for GPU costs)

**IR-2.3** The system SHALL integrate with Phase 3 (Prevention for idle GPUs)

**IR-2.4** The system SHALL integrate with Phase 4 (AI Advisor for GPU optimization)

**IR-2.5** The system SHALL integrate with Phase 5 (Multi-account GPU cost tracking)

---

## Acceptance Criteria

### AC-1: GPU Cost Tracking

**GIVEN** an AWS account with GPU instances  
**WHEN** the user queries GPU costs  
**THEN** the system returns costs grouped by workload type (training, inference, idle)  
**AND** the response includes cost per GPU hour  
**AND** the response includes utilization percentage  
**AND** the response time is < 2 seconds (cached)

---

### AC-2: Workload Classification

**GIVEN** an EC2 GPU instance running for 24 hours  
**WHEN** the system classifies the workload  
**THEN** the classification is "training" if GPU utilization > 70% continuously  
**OR** the classification is "inference" if GPU utilization 20-70% with spikes  
**OR** the classification is "idle" if GPU utilization < 10%  
**AND** the confidence score is > 80%

---

### AC-3: Cost-Per-Inference

**GIVEN** an inference endpoint with 1 million requests  
**WHEN** the user queries cost-per-inference  
**THEN** the system returns total cost divided by request count  
**AND** the calculation includes compute, API, and data transfer costs  
**AND** the accuracy is within 2% of actual costs

---

### AC-4: Cost-Per-Training

**GIVEN** a SageMaker training job  
**WHEN** the user queries cost-per-training  
**THEN** the system returns total training cost  
**AND** the calculation includes compute, storage, and data transfer costs  
**AND** the response includes cost per hour  
**AND** the accuracy is within 2% of actual costs

---

### AC-5: Spot Instance Recommendations

**GIVEN** a training workload on on-demand instances  
**WHEN** the user requests spot recommendations  
**THEN** the system recommends suitable spot instance types  
**AND** the system shows potential savings (up to 90%)  
**AND** the system shows interruption risk  
**AND** the savings estimate is accurate within 5%

---

### AC-6: SageMaker Cost Tracking

**GIVEN** a SageMaker training job  
**WHEN** the user queries SageMaker costs  
**THEN** the system returns costs by job type (training, inference, notebook)  
**AND** the system identifies idle endpoints (< 10 requests/hour)  
**AND** the system recommends cost-optimized instance types

---

### AC-7: Bedrock Cost Tracking

**GIVEN** Bedrock model invocations  
**WHEN** the user queries Bedrock costs  
**THEN** the system returns costs by model  
**AND** the system calculates cost per invocation  
**AND** the system tracks input/output token counts  
**AND** the system recommends cost-optimized models

---

## Out of Scope

The following are explicitly OUT OF SCOPE for Phase 6:

1. **Multi-cloud support** (GCP, Azure) - AWS only
2. **Model optimization** (quantization, pruning) - Future phase
3. **Custom ML frameworks** (PyTorch, TensorFlow) - Only AWS services
4. **Real-time cost tracking** (< 15 minutes) - Near-real-time only
5. **Cost allocation by team/project** - Covered in Phase 5
6. **Budget management** - Covered in Phase 3
7. **Cost forecasting** - Covered in Phase 2 (can extend for GPU costs)
8. **Frontend dashboard** - Covered in Phase 10

---

## Dependencies

### Internal Dependencies

- **Phase 1:** Cost Explorer integration (required)
- **Phase 1.5:** CloudWatch metrics collection (required)
- **Phase 2:** Forecasting engine (optional - can extend for GPU forecasts)
- **Phase 3:** Prevention engine (optional - can extend for idle GPU detection)
- **Phase 4:** AI Advisor (optional - can extend for GPU optimization insights)
- **Phase 5:** Multi-account support (optional - can extend for multi-account GPU tracking)

### External Dependencies

- **AWS Cost Explorer API:** For GPU cost data
- **AWS CloudWatch API:** For GPU utilization metrics
- **AWS EC2 API:** For instance metadata
- **AWS SageMaker API:** For training/inference job data
- **AWS Bedrock API:** For model invocation metrics
- **AWS Pricing API:** For spot instance prices

---

## Risks & Mitigation

### Risk 1: Workload Classification Accuracy

**Risk:** Automated classification may be inaccurate (< 90%)

**Mitigation:**
- Start with CloudWatch metrics-based classification
- Allow manual tagging for override
- Provide confidence scores
- Improve accuracy over time with ML-based classification

---

### Risk 2: Cost-Per-Inference Accuracy

**Risk:** Request tracking may be incomplete

**Mitigation:**
- Use multiple data sources (CloudWatch, API Gateway, Lambda)
- Provide clear documentation on request tracking
- Allow manual request count input
- Show calculation methodology transparently

---

### Risk 3: Spot Instance Recommendations

**Risk:** Recommendations may not be suitable for all workloads

**Mitigation:**
- Only recommend for batch training jobs (not real-time inference)
- Show interruption risk and savings trade-off
- Provide "what-if" scenarios
- Add disclaimer that recommendations are guidance

---

### Risk 4: Cost

**Risk:** More Cost Explorer API calls = higher costs

**Mitigation:**
- Aggressive caching (24-hour TTL)
- Batch API calls where possible
- Rate limiting to stay within budget
- Monitor costs closely

---

## Success Criteria

Phase 6 is considered successful when:

1. ✅ All functional requirements (FR-1 through FR-7) are implemented
2. ✅ All non-functional requirements (NFR-1 through NFR-6) are met
3. ✅ All API endpoints (API-1 through API-7) are operational
4. ✅ All acceptance criteria (AC-1 through AC-7) pass
5. ✅ Test coverage is 90%+
6. ✅ Documentation is complete
7. ✅ Phase 6 adds < $1.00/month to AWS costs
8. ✅ 50+ AI startups adopt Phase 6 features within 3 months

---

## Related Documents

- [Phase 6 Recommendation](../../docs/project/phase6-recommendation.md) - Why Phase 6 is AI/ML workload costs
- [Hackathon Emphasis Analysis](../../docs/HACKATHON-EMPHASIS-ANALYSIS.md) - AWS hackathon priorities
- [Impact Assessment](../../docs/IMPACT-ASSESSMENT.md) - SMB/startup impact analysis
- [Competitive Analysis](../../docs/COMPETITIVE-ANALYSIS.md) - Market positioning
- [Project Planning](../../docs/project/planning.md) - Overall project plan

---

**Document Status:** Draft  
**Last Updated:** February 2026  
**Ready for Review:** Yes
