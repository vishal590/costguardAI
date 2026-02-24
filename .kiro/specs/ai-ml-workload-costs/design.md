# Design Document: AI/ML Workload Cost Management

## Overview

Phase 6 implements AI/ML-specific cost management capabilities for CostGuard AI, focusing on GPU cost tracking, workload classification, and ML optimization. The system automatically tracks EC2 GPU instances, SageMaker jobs, and Bedrock invocations, classifying workloads as training or inference and calculating unit costs (cost-per-inference, cost-per-training).

The design extends the existing CostGuard AI architecture with new Lambda functions for GPU cost collection, CloudWatch-based workload classification, and spot instance recommendation engines. All components are optimized for Free Tier compliance with aggressive caching and batched API calls.

**Key Differentiator:** NO competitor (CloudZero, nOps, Vantage) provides GPU-specific cost tracking by workload type or cost-per-inference calculations for self-hosted models.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  API Gateway                                 │
│  GET  /api/ai-ml/gpu-costs                                  │
│  GET  /api/ai-ml/workload-classification                    │
│  POST /api/ai-ml/workload-classification                    │
│  GET  /api/ai-ml/cost-per-inference                         │
│  GET  /api/ai-ml/cost-per-training                          │
│  GET  /api/ai-ml/spot-recommendations                       │
│  GET  /api/ai-ml/sagemaker-costs                            │
│  GET  /api/ai-ml/bedrock-costs                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Handler                                  │
│  - Route AI/ML cost requests                                │
│  - Validate parameters                                      │
│  - Format responses                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            AI/ML Cost Engine                                 │
│  - Collect GPU cost data                                    │
│  - Classify workloads (training vs inference)               │
│  - Calculate unit costs                                     │
│  - Generate spot instance recommendations                   │
└─┬───────┬────────┬────────┬────────┬────────┬──────────────┘
  │       │        │        │        │        │
  ▼       ▼        ▼        ▼        ▼        ▼
┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────────┐
│GPU │ │Wrkl│ │Cost│ │Cost│ │Spot│ │SageMkr │
│Cost│ │Clsf│ │/Inf│ │/Trn│ │Rec │ │Tracker │
│Trkr│ │    │ │    │ │    │ │    │ │        │
└────┘ └────┘ └────┘ └────┘ └────┘ └────────┘
  │       │        │        │        │        │
  ▼       ▼        ▼        ▼        ▼        ▼
┌──────────────────────────────────────────────────────────┐
│  Data Sources: Cost Explorer (GPU costs),                │
│  CloudWatch (GPU metrics), EC2 API (metadata),           │
│  SageMaker API (jobs), Bedrock API (invocations),        │
│  Pricing API (spot prices), DynamoDB (storage)           │
└──────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. GPU Cost Tracker (`gpu_cost_tracker.py`)

**Purpose:** Track EC2 GPU instance costs by workload type

**Key Methods:**
```python
def collect_gpu_costs(start_date: datetime, end_date: datetime) -> List[GPUCostData]:
    """Collect GPU costs from Cost Explorer for specified date range."""
    
def filter_gpu_instances(cost_data: List[CostData]) -> List[GPUCostData]:
    """Filter cost data to only GPU instance types (p3, p4, p5, g4, g5, g6)."""
    
def calculate_cost_per_gpu_hour(cost_data: GPUCostData) -> float:
    """Calculate cost per GPU hour for a workload."""
    
def identify_idle_gpus(utilization_data: List[GPUUtilization]) -> List[str]:
    """Identify GPU instances with <10% utilization."""
```

**Responsibilities:**
- Query Cost Explorer for GPU instance costs
- Filter by GPU instance types
- Calculate cost per GPU hour
- Identify idle GPU instances

### 2. Workload Classifier (`workload_classifier.py`)

**Purpose:** Classify GPU workloads as training or inference

**Key Methods:**
```python
def classify_workload(instance_id: str, start_date: datetime, end_date: datetime) -> WorkloadClassification:
    """Classify workload based on CloudWatch GPU metrics."""
    
def get_gpu_utilization_pattern(instance_id: str, start_date: datetime, end_date: datetime) -> List[float]:
    """Retrieve GPU utilization metrics from CloudWatch."""
    
def apply_classification_rules(utilization_pattern: List[float]) -> Tuple[str, float]:
    """Apply rules to determine workload type and confidence score."""
    
def get_manual_classification(instance_id: str) -> Optional[str]:
    """Check for manual classification via EC2 tags."""
    
def store_classification(instance_id: str, classification: WorkloadClassification) -> None:
    """Store classification in DynamoDB with timestamp."""
```

**Responsibilities:**
- Retrieve GPU utilization from CloudWatch
- Apply classification rules (training: >70% continuous, inference: 20-70% spikes)
- Calculate confidence scores
- Support manual overrides via tags
- Store classification history

### 3. Cost-Per-Inference Calculator (`cost_per_inference_calculator.py`)

**Purpose:** Calculate cost per inference request

**Key Methods:**
```python
def calculate_cost_per_inference(model: str, endpoint: str, start_date: datetime, end_date: datetime) -> CostPerInference:
    """Calculate cost per inference for a model/endpoint."""
    
def get_inference_request_count(endpoint: str, start_date: datetime, end_date: datetime) -> int:
    """Get inference request count from CloudWatch/API Gateway."""
    
def get_inference_costs(endpoint: str, start_date: datetime, end_date: datetime) -> InferenceCosts:
    """Get total inference costs (compute + API + data transfer)."""
    
def track_cost_trends(model: str, endpoint: str) -> List[CostTrend]:
    """Track cost-per-inference trends over time."""
```

**Responsibilities:**
- Track inference requests from multiple sources
- Calculate total inference costs
- Compute cost per inference
- Track trends over time

### 4. Cost-Per-Training Calculator (`cost_per_training_calculator.py`)

**Purpose:** Calculate cost per training job

**Key Methods:**
```python
def calculate_cost_per_training(job_id: str) -> CostPerTraining:
    """Calculate cost per training job."""
    
def get_training_job_metadata(job_id: str) -> TrainingJobMetadata:
    """Get training job metadata from SageMaker or EC2 tags."""
    
def get_training_costs(job_id: str) -> TrainingCosts:
    """Get total training costs (compute + storage + data transfer)."""
    
def compare_instance_types(model: str, instance_types: List[str]) -> List[InstanceComparison]:
    """Compare training costs across different instance types."""
```

**Responsibilities:**
- Track training jobs from SageMaker and EC2
- Calculate total training costs
- Compute cost per training job
- Compare costs across instance types

### 5. Spot Instance Recommender (`spot_instance_recommender.py`)

**Purpose:** Recommend spot instances for training workloads

**Key Methods:**
```python
def recommend_spot_instances(workload_id: str) -> List[SpotRecommendation]:
    """Recommend spot instances for a training workload."""
    
def identify_spot_suitable_workloads() -> List[str]:
    """Identify training workloads suitable for spot instances."""
    
def calculate_spot_savings(current_instance: str, spot_instance: str) -> SpotSavings:
    """Calculate potential savings from switching to spot."""
    
def get_spot_interruption_risk(instance_type: str, az: str) -> float:
    """Get spot instance interruption risk from historical data."""
    
def generate_what_if_scenarios(workload_id: str) -> List[WhatIfScenario]:
    """Generate what-if scenarios for spot instance usage."""
```

**Responsibilities:**
- Identify spot-suitable workloads
- Calculate potential savings
- Assess interruption risk
- Generate what-if scenarios

### 6. SageMaker Cost Tracker (`sagemaker_cost_tracker.py`)

**Purpose:** Track SageMaker training and inference costs

**Key Methods:**
```python
def track_sagemaker_costs(start_date: datetime, end_date: datetime) -> SageMakerCosts:
    """Track SageMaker costs by job type."""
    
def get_training_job_costs(job_name: str) -> TrainingJobCost:
    """Get costs for a specific training job."""
    
def get_endpoint_costs(endpoint_name: str) -> EndpointCost:
    """Get costs for a specific inference endpoint."""
    
def identify_idle_endpoints(threshold: int = 10) -> List[str]:
    """Identify endpoints with <threshold requests/hour."""
    
def recommend_instance_types(job_type: str, current_instance: str) -> List[InstanceRecommendation]:
    """Recommend cost-optimized instance types."""
```

**Responsibilities:**
- Track SageMaker training and inference costs
- Identify idle endpoints
- Recommend cost-optimized instances

### 7. Bedrock Cost Tracker (`bedrock_cost_tracker.py`)

**Purpose:** Track Bedrock model invocation costs

**Key Methods:**
```python
def track_bedrock_costs(start_date: datetime, end_date: datetime) -> BedrockCosts:
    """Track Bedrock costs by model."""
    
def get_model_invocation_costs(model_id: str) -> ModelInvocationCost:
    """Get costs for a specific model."""
    
def calculate_cost_per_invocation(model_id: str) -> float:
    """Calculate cost per invocation for a model."""
    
def track_token_usage(model_id: str) -> TokenUsage:
    """Track input/output token counts."""
    
def recommend_cost_optimized_models(usage_pattern: UsagePattern) -> List[ModelRecommendation]:
    """Recommend cost-optimized models based on usage."""
```

**Responsibilities:**
- Track Bedrock invocation costs
- Calculate cost per invocation
- Track token usage
- Recommend cost-optimized models

## Data Models

### GPUCostData
```python
@dataclass
class GPUCostData:
    date: datetime
    instance_id: str
    instance_type: str  # p3.2xlarge, p4d.24xlarge, etc.
    workload_type: str  # "training", "inference", "idle"
    cost: float
    gpu_hours: float
    cost_per_gpu_hour: float
    utilization: float  # 0-100%
    classification_confidence: float  # 0-1
```

### WorkloadClassification
```python
@dataclass
class WorkloadClassification:
    instance_id: str
    workload_type: str  # "training", "inference", "idle"
    confidence: float  # 0-1
    classification_method: str  # "cloudwatch-metrics", "manual-tag"
    gpu_utilization_avg: float
    gpu_utilization_pattern: List[float]
    timestamp: datetime
```

### CostPerInference
```python
@dataclass
class CostPerInference:
    model: str
    endpoint: str
    date: datetime
    total_requests: int
    total_cost: float
    cost_per_inference: float
    compute_cost: float
    api_cost: float
    data_transfer_cost: float
```

### CostPerTraining
```python
@dataclass
class CostPerTraining:
    job_id: str
    model: str
    dataset: str
    date: datetime
    training_hours: float
    total_cost: float
    cost_per_hour: float
    compute_cost: float
    storage_cost: float
    data_transfer_cost: float
    instance_type: str
```

### SpotRecommendation
```python
@dataclass
class SpotRecommendation:
    workload_id: str
    current_instance: str
    current_cost: float
    recommended_spot_instance: str
    spot_cost: float
    savings: float
    savings_percent: float
    interruption_risk: float  # 0-1
    suitable: bool
```

### SageMakerCosts
```python
@dataclass
class SageMakerCosts:
    date: datetime
    training_costs: float
    inference_costs: float
    notebook_costs: float
    total_cost: float
    job_breakdown: List[JobCost]
```

### BedrockCosts
```python
@dataclass
class BedrockCosts:
    date: datetime
    model_id: str
    invocations: int
    input_tokens: int
    output_tokens: int
    total_cost: float
    cost_per_invocation: float
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: GPU Instance Type Filtering
*For any* Cost Explorer response containing mixed instance types, filtering for GPU instances should return only instances matching GPU patterns (p3, p4, p4d, p5, g4, g5, g6) and exclude all non-GPU instances.

**Validates: Requirements FR-1.1**

### Property 2: Workload Classification Consistency
*For any* GPU instance with consistent utilization patterns, classifying the workload multiple times should produce the same workload type (training/inference/idle) with confidence scores within 5% of each other.

**Validates: Requirements FR-2.1, FR-2.2**

### Property 3: Cost Per GPU Hour Calculation
*For any* GPU instance with known cost and runtime hours, the calculated cost per GPU hour should equal total cost divided by GPU hours, accurate within 0.01%.

**Validates: Requirements FR-1.3**

### Property 4: Idle GPU Detection
*For any* GPU instance with average utilization below 10%, the system should classify it as idle; for any instance with average utilization above 10%, it should not be classified as idle.

**Validates: Requirements FR-1.5**

### Property 5: Cost-Per-Inference Accuracy
*For any* inference endpoint with known total cost and request count, the calculated cost per inference should equal total cost divided by request count, accurate within 0.01%.

**Validates: Requirements FR-3.1, FR-3.4**

### Property 6: Cost-Per-Training Accuracy
*For any* training job with known total cost, the calculated cost per training should include all cost components (compute + storage + data transfer) and sum to the total cost within 2%.

**Validates: Requirements FR-4.1, FR-4.3**

### Property 7: Spot Savings Calculation
*For any* on-demand instance and equivalent spot instance, the calculated savings should equal the difference in hourly costs multiplied by runtime hours, accurate within 5%.

**Validates: Requirements FR-5.2**

### Property 8: Workload Classification Rules
*For any* GPU utilization pattern where average utilization exceeds 70% continuously for over 1 hour, the workload should be classified as "training"; for patterns with 20-70% utilization and frequent spikes, it should be classified as "inference"; for patterns below 10%, it should be classified as "idle".

**Validates: Requirements FR-2.4**

### Property 9: Manual Classification Override
*For any* GPU instance with a manual classification tag, the system should use the manual classification instead of the automated classification, regardless of utilization patterns.

**Validates: Requirements FR-2.3, FR-2.5**

### Property 10: Classification History Preservation
*For any* workload classification change, the system should store both the old and new classifications with timestamps, preserving the complete classification history.

**Validates: Requirements FR-2.6**

### Property 11: Spot Suitability Criteria
*For any* workload classified as "training" with batch processing characteristics, the system should recommend spot instances; for any workload classified as "inference" with real-time requirements, it should not recommend spot instances.

**Validates: Requirements FR-5.1**

### Property 12: SageMaker Cost Breakdown
*For any* SageMaker account, the sum of training costs, inference costs, and notebook costs should equal the total SageMaker cost within 1%.

**Validates: Requirements FR-6.4**

### Property 13: Bedrock Token Tracking
*For any* Bedrock model invocation, the system should track both input and output token counts, and the total cost should be calculable from token counts and model pricing.

**Validates: Requirements FR-7.4**

### Property 14: Cache Consistency
*For any* GPU cost query with a 24-hour cache TTL, querying the same data within 24 hours should return cached results; querying after 24 hours should fetch fresh data.

**Validates: Requirements NFR-5.2**

### Property 15: Response Time Bounds
*For any* cached GPU cost query, response time should be under 2 seconds; for any uncached query, response time should be under 10 seconds (95th percentile).

**Validates: Requirements NFR-1.1, NFR-1.2**

## Error Handling

### Cost Explorer API Errors
- **Rate Limit Exceeded (429):** Retry with exponential backoff (1s, 2s, 4s), max 3 attempts
- **Service Unavailable (503):** Return cached data if available, otherwise user-friendly error
- **Invalid Request (400):** Log error, return "Unable to retrieve GPU costs" message
- **Timeout:** Return partial data if available, indicate incomplete results

### CloudWatch API Errors
- **Missing Metrics:** Use default classification based on instance type, mark confidence as low
- **Insufficient Data:** Require minimum 1 hour of data for classification, otherwise mark as "unknown"
- **API Failure:** Fall back to manual classification tags if available

### SageMaker API Errors
- **Job Not Found:** Return error indicating job doesn't exist
- **Access Denied:** Log permission error, return user-friendly message
- **API Timeout:** Retry once, then return cached data if available

### Bedrock API Errors
- **Model Not Found:** Return error indicating model doesn't exist
- **Invocation Failure:** Log error, continue with other models
- **Rate Limit:** Implement request throttling to stay within limits

### Spot Pricing API Errors
- **Pricing Data Unavailable:** Use last known prices with staleness indicator
- **Region Not Supported:** Return error indicating spot not available in region

## Testing Strategy

### Unit Tests
- GPU instance type filtering
- Workload classification rules
- Cost per GPU hour calculations
- Cost-per-inference calculations
- Cost-per-training calculations
- Spot savings calculations
- Idle GPU detection
- Manual classification override
- Cache operations

### Property-Based Tests (100 iterations each)
- Property 1: GPU instance type filtering
- Property 2: Workload classification consistency
- Property 3: Cost per GPU hour calculation
- Property 4: Idle GPU detection
- Property 5: Cost-per-inference accuracy
- Property 6: Cost-per-training accuracy
- Property 7: Spot savings calculation
- Property 8: Workload classification rules
- Property 9: Manual classification override
- Property 10: Classification history preservation
- Property 11: Spot suitability criteria
- Property 12: SageMaker cost breakdown
- Property 13: Bedrock token tracking
- Property 14: Cache consistency
- Property 15: Response time bounds

### Integration Tests
- End-to-end GPU cost tracking
- Cost Explorer integration
- CloudWatch metrics integration
- SageMaker API integration
- Bedrock API integration
- Pricing API integration
- Multi-workload classification
- Spot recommendation generation
- Phase 1-5 backward compatibility

### Performance Tests
- Response time under load (100 concurrent queries)
- GPU cost collection for 1000 instances
- Workload classification for 100 instances
- Cache hit rate measurement
- API call frequency monitoring

## Free Tier Compliance

### Cost Explorer API Usage
- **Current:** ~50 calls/month (Phases 1-5)
- **Phase 6 Addition:** +50 calls/month (GPU cost queries)
- **Total:** ~100 calls/month
- **Cost:** ~$1.00/month ($0.01 per call)

### CloudWatch API Usage
- **Metrics Retrieval:** Within free tier (1M API requests/month)
- **Custom Metrics:** Not used (using standard EC2 metrics)

### Lambda Invocations
- **Current:** ~5000 invocations/month
- **Phase 6 Addition:** +2000 invocations/month
- **Total:** ~7000 invocations/month (within 1M free tier)

### DynamoDB Storage
- **Current:** ~110 MB
- **Phase 6 Addition:** +50 MB (GPU cost data, classifications)
- **Total:** ~160 MB (within 25 GB free tier)

### Total Phase 6 Cost
- **Cost Explorer:** +$0.50/month
- **CloudWatch:** $0 (within free tier)
- **Lambda:** $0 (within free tier)
- **DynamoDB:** $0 (within free tier)
- **Total Phase 6 Cost:** ~$0.50/month
- **Total System Cost (Phases 1-6):** ~$4.51/month

## Performance Targets

- **Cached GPU Cost Query:** <2s (P95)
- **Uncached GPU Cost Query:** <10s (P95)
- **Workload Classification:** <5 minutes for 100 instances
- **Cost-Per-Inference Calculation:** <2s
- **Spot Recommendation Generation:** <2s
- **Cache Hit Rate:** 60%+ target (24-hour TTL)
- **Concurrent Queries:** 100 without degradation

## Security Considerations

- **API Authentication:** API key required for all endpoints
- **Data Privacy:** No model weights or training data stored
- **Encryption:** All data encrypted at rest (DynamoDB) and in transit (TLS 1.2+)
- **IAM Permissions:** Least privilege for Lambda roles
- **Tag-Based Access:** Respect EC2 resource tags for access control
- **Audit Logging:** Log all classification changes and manual overrides

## Deployment Considerations

- **Lambda Memory:** 512 MB (sufficient for Cost Explorer calls)
- **Lambda Timeout:** 30 seconds (allows for API retries)
- **DynamoDB Tables:** 3 new tables (gpu-costs, workload-classifications, spot-recommendations)
- **API Gateway Routes:** 8 new endpoints
- **Environment Variables:** CACHE_TTL_HOURS, CLASSIFICATION_CONFIDENCE_THRESHOLD
- **Backward Compatibility:** No changes to existing Phase 1-5 infrastructure
- **Gradual Rollout:** Deploy GPU tracking first, then add advanced features

## Integration with Existing Phases

### Phase 1 Integration
- Extend Cost Explorer queries to filter GPU instances
- Reuse existing DynamoDB client and error handling
- Leverage existing caching infrastructure

### Phase 2 Integration
- Extend forecasting to predict GPU costs
- Use GPU cost trends for forecast training
- Alert on GPU cost forecast overruns

### Phase 3 Integration
- Extend prevention to stop idle GPU instances
- Respect safety guards for GPU resources
- Track GPU cost savings from prevention actions

### Phase 4 Integration
- Extend AI Advisor to answer GPU cost questions
- Provide GPU optimization recommendations
- Explain workload classifications in natural language

### Phase 5 Integration
- Support multi-account GPU cost tracking
- Aggregate GPU costs across organization
- Allocate GPU costs to business units

