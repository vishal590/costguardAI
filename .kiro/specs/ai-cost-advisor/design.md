# Design Document

## Overview

Phase 4 implements an AI-powered conversational cost advisor using Amazon Bedrock Nova Lite. The system provides natural language explanations of AWS costs, analyzes spending patterns, and recommends optimization actions. It integrates with Phases 1-3 to provide comprehensive cost insights based on historical data, forecasts, and prevention actions.

The design follows a serverless architecture with Lambda functions handling query processing, Bedrock integration for AI responses, and DynamoDB for conversation history and caching. The system is optimized for Free Tier compliance with aggressive caching (40%+ hit rate target) to minimize Bedrock API costs.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  API Gateway                                 │
│  POST /api/advisor/query                                    │
│  GET  /api/advisor/history                                  │
│  DELETE /api/advisor/history                                │
│  GET  /api/advisor/suggestions                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Handler                                  │
│  - Route advisor requests                                   │
│  - Validate parameters                                      │
│  - Format responses                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            AI Advisor Engine                                 │
│  - Process natural language queries                         │
│  - Manage conversation context                              │
│  - Orchestrate data retrieval and AI invocation             │
│  - Generate proactive insights                              │
└─┬───────┬────────┬────────┬────────┬────────┬──────────────┘
  │       │        │        │        │        │
  ▼       ▼        ▼        ▼        ▼        ▼
┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────────┐
│Qry │ │Ctx │ │Bedr│ │Resp│ │Cach│ │Insight │
│Proc│ │Mgr │ │Clnt│ │Fmt │ │Mgr │ │Gen     │
└────┘ └────┘ └────┘ └────┘ └────┘ └────────┘
  │       │        │        │        │        │
  ▼       ▼        ▼        ▼        ▼        ▼
┌──────────────────────────────────────────────────────────┐
│  Data Sources: Cost Explorer, Phase 2 Forecasts,        │
│  Phase 3 Prevention, DynamoDB (history & cache)          │
└──────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. AI Advisor Engine (`advisor_engine.py`)

**Purpose:** Main orchestrator for AI advisor functionality

**Key Methods:**
```python
def process_query(query: str, user_id: str, session_id: str) -> AdvisorResponse:
    """Process a natural language query and return AI-generated response."""
    
def get_conversation_history(session_id: str) -> List[ConversationTurn]:
    """Retrieve conversation history for a session."""
    
def clear_conversation_history(session_id: str) -> None:
    """Clear conversation history for a session."""
    
def generate_proactive_insights(user_id: str) -> List[Insight]:
    """Generate proactive cost insights for a user."""
```

**Responsibilities:**
- Orchestrate query processing workflow
- Manage conversation sessions
- Coordinate between components
- Generate proactive insights

### 2. Query Processor (`query_processor.py`)

**Purpose:** Parse and understand natural language queries

**Key Methods:**
```python
def parse_query(query: str) -> QueryIntent:
    """Parse query and extract intent, entities, and time ranges."""
    
def extract_time_range(query: str) -> Tuple[datetime, datetime]:
    """Extract time period from query (e.g., 'last month')."""
    
def extract_services(query: str) -> List[str]:
    """Extract AWS service names from query."""
    
def normalize_service_names(services: List[str]) -> List[str]:
    """Map common names to AWS service identifiers."""
```

**Responsibilities:**
- Parse natural language queries
- Extract intent (cost analysis, optimization, trend analysis)
- Identify time ranges and services
- Normalize service names

### 3. Context Manager (`context_manager.py`)

**Purpose:** Retrieve relevant cost data for queries

**Key Methods:**
```python
def get_cost_context(intent: QueryIntent) -> CostContext:
    """Retrieve relevant cost data based on query intent."""
    
def get_historical_costs(services: List[str], start_date: datetime, end_date: datetime) -> Dict:
    """Fetch historical cost data from Cost Explorer."""
    
def get_forecast_data(services: List[str], days: int) -> Dict:
    """Fetch forecast data from Phase 2."""
    
def get_prevention_actions(start_date: datetime, end_date: datetime) -> List[PreventionAction]:
    """Fetch prevention actions from Phase 3."""
```

**Responsibilities:**
- Retrieve historical cost data
- Fetch forecast data from Phase 2
- Fetch prevention actions from Phase 3
- Aggregate data for AI context

### 4. Bedrock Client (`bedrock_advisor_client.py`)

**Purpose:** Interface with Amazon Bedrock for AI responses

**Key Methods:**
```python
def invoke_advisor(query: str, context: CostContext, conversation_history: List[ConversationTurn]) -> str:
    """Invoke Bedrock Nova Lite with query and context."""
    
def build_prompt(query: str, context: CostContext, history: List[ConversationTurn]) -> str:
    """Construct prompt for Bedrock."""
    
def parse_response(response: str) -> AdvisorResponse:
    """Parse Bedrock response and extract structured data."""
    
def retry_with_backoff(func: Callable, max_retries: int = 3) -> Any:
    """Retry Bedrock calls with exponential backoff."""
```

**Responsibilities:**
- Invoke Bedrock Nova Lite API
- Construct prompts with query + context + history
- Parse AI responses
- Handle rate limiting and errors

### 5. Response Formatter (`response_formatter.py`)

**Purpose:** Format AI responses for display

**Key Methods:**
```python
def format_response(raw_response: str, context: CostContext) -> FormattedResponse:
    """Format response with markdown, tables, and highlights."""
    
def create_cost_table(costs: Dict[str, float]) -> str:
    """Create markdown table for cost comparisons."""
    
def highlight_numbers(text: str) -> str:
    """Highlight costs and percentages in text."""
    
def truncate_response(text: str, max_words: int = 500) -> str:
    """Truncate long responses while preserving meaning."""
```

**Responsibilities:**
- Format responses in markdown
- Create tables for cost comparisons
- Highlight important numbers
- Ensure responses are concise

### 6. Cache Manager (`advisor_cache_manager.py`)

**Purpose:** Cache frequently asked questions

**Key Methods:**
```python
def get_cached_response(query_hash: str) -> Optional[AdvisorResponse]:
    """Retrieve cached response if available and fresh."""
    
def store_response(query_hash: str, response: AdvisorResponse, ttl_hours: int = 24) -> None:
    """Store response in cache with TTL."""
    
def invalidate_cache(pattern: str) -> None:
    """Invalidate cache entries matching pattern."""
    
def get_cache_hit_rate() -> float:
    """Calculate cache hit rate percentage."""
```

**Responsibilities:**
- Cache query responses
- Manage cache TTL (24 hours)
- Invalidate stale cache entries
- Track cache hit rate

### 7. Insight Generator (`insight_generator.py`)

**Purpose:** Generate proactive cost insights

**Key Methods:**
```python
def generate_daily_summary(user_id: str) -> Insight:
    """Generate daily cost summary."""
    
def detect_anomalies(user_id: str) -> List[Insight]:
    """Detect cost anomalies and generate alerts."""
    
def suggest_optimizations(user_id: str) -> List[Insight]:
    """Suggest cost optimization opportunities."""
    
def check_forecast_alerts(user_id: str) -> List[Insight]:
    """Check forecasts for budget overrun predictions."""
```

**Responsibilities:**
- Generate daily cost summaries
- Detect cost anomalies
- Suggest optimizations
- Alert on forecast predictions

## Data Models

### QueryIntent
```python
@dataclass
class QueryIntent:
    intent_type: str  # "cost_analysis", "optimization", "trend_analysis", "forecast", "prevention"
    services: List[str]  # AWS service identifiers
    time_range: Tuple[datetime, datetime]
    accounts: List[str]  # AWS account IDs
    entities: Dict[str, Any]  # Extracted entities (resource IDs, etc.)
```

### CostContext
```python
@dataclass
class CostContext:
    historical_costs: Dict[str, List[CostDataPoint]]  # Service -> cost data
    forecast_data: Optional[Dict[str, List[ForecastPoint]]]
    prevention_actions: List[PreventionAction]
    current_budget: Optional[BudgetStatus]
    anomalies: List[CostAnomaly]
```

### ConversationTurn
```python
@dataclass
class ConversationTurn:
    query: str
    response: str
    timestamp: datetime
    context_used: CostContext
```

### AdvisorResponse
```python
@dataclass
class AdvisorResponse:
    response_text: str  # Formatted markdown response
    recommendations: List[Recommendation]
    cost_data: Dict[str, Any]  # Structured cost data
    confidence: float  # AI confidence score
    cached: bool  # Whether response was cached
```

### Recommendation
```python
@dataclass
class Recommendation:
    action: str  # Description of recommended action
    rationale: str  # Why this is recommended
    estimated_savings: float  # Monthly savings estimate
    priority: int  # 1-5, 5 being highest
    safe: bool  # Whether action respects safety guards
```

### Insight
```python
@dataclass
class Insight:
    insight_type: str  # "summary", "anomaly", "optimization", "forecast_alert"
    title: str
    description: str
    severity: str  # "info", "warning", "critical"
    action_required: bool
    related_services: List[str]
    estimated_impact: Optional[float]  # Cost impact
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Query Intent Extraction Consistency
*For any* natural language query containing time references and service names, parsing the query should consistently extract the same intent, time range, and services regardless of phrasing variations.

**Validates: Requirements 1.1, 1.3, 1.4**

### Property 2: Context Retrieval Completeness
*For any* query intent with specified services and time ranges, the context manager should retrieve all relevant cost data without missing any requested services or time periods.

**Validates: Requirements 2.1, 2.2, 2.3**

### Property 3: Bedrock Prompt Structure
*For any* query with context and conversation history, the constructed Bedrock prompt should include all three components (query, context, history) in the correct format.

**Validates: Requirements 3.2**

### Property 4: Response Caching Correctness
*For any* query, if a cached response exists and is within TTL, the system should return the cached response; otherwise, it should invoke Bedrock and cache the new response.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4**

### Property 5: Cache Invalidation Consistency
*For any* significant cost data change, all related cache entries should be invalidated to prevent stale responses.

**Validates: Requirements 9.5**

### Property 6: Conversation Context Continuity
*For any* follow-up query in a session, the system should include previous conversation turns in the context, enabling natural conversation flow.

**Validates: Requirements 7.1, 7.2, 7.3**

### Property 7: Recommendation Safety
*For any* cost optimization recommendation, the system should only suggest actions that respect Phase 3 safety guards (protected tags, whitelists, active usage).

**Validates: Requirements 5.6**

### Property 8: Recommendation Prioritization
*For any* set of recommendations, they should be ordered by estimated savings (highest first) with priority scores assigned correctly.

**Validates: Requirements 5.3**

### Property 9: Time Range Interpretation
*For any* relative time reference (e.g., "last month", "this week"), the system should consistently map it to the correct absolute date range based on current date.

**Validates: Requirements 1.3**

### Property 10: Service Name Normalization
*For any* common service name or alias (e.g., "storage", "compute"), the system should consistently map it to the correct AWS service identifier.

**Validates: Requirements 1.4**

### Property 11: Response Time Bounds
*For any* cached query, response time should be under 500ms; for non-cached queries, response time should be under 5 seconds (95th percentile).

**Validates: Requirements 16.1, 16.2**

### Property 12: Error Message Clarity
*For any* error condition (Bedrock unavailable, data missing, rate limit), the system should return a user-friendly error message without technical jargon.

**Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**

### Property 13: Forecast Integration Accuracy
*For any* query about future costs, the system should retrieve forecast data from Phase 2 and correctly interpret confidence intervals.

**Validates: Requirements 14.1, 14.2**

### Property 14: Prevention Action Attribution
*For any* query about prevention actions, the system should accurately retrieve action history from Phase 3 and explain savings achieved.

**Validates: Requirements 15.1, 15.2, 15.3**

### Property 15: Backward Compatibility
*For any* Phase 1, 1.5, 2, or 3 API endpoint, adding Phase 4 should not change the response format or behavior.

**Validates: Requirements 18.1, 18.2, 18.3, 18.4**

## Error Handling

### Bedrock API Errors
- **Rate Limit Exceeded (429):** Retry with exponential backoff (1s, 2s, 4s), max 3 attempts
- **Service Unavailable (503):** Return cached response if available, otherwise user-friendly error
- **Invalid Request (400):** Log error, return "Unable to process query" message
- **Timeout:** Return partial response if context was retrieved, otherwise error

### Cost Data Errors
- **Cost Explorer API Failure:** Use cached data if available, inform user of data staleness
- **Missing Data:** Explain which data is unavailable, provide partial answer if possible
- **Forecast Unavailable:** Explain forecast service is unavailable, provide historical trends instead

### Cache Errors
- **DynamoDB Unavailable:** Bypass cache, invoke Bedrock directly
- **Cache Corruption:** Invalidate corrupted entry, regenerate response
- **TTL Expiration:** Treat as cache miss, regenerate response

### Conversation History Errors
- **Session Not Found:** Start new conversation session
- **History Corruption:** Clear corrupted history, start fresh
- **Storage Limit Exceeded:** Truncate oldest conversation turns

## Testing Strategy

### Unit Tests
- Query parsing with various phrasings
- Time range extraction for different formats
- Service name normalization
- Prompt construction
- Response formatting
- Cache operations (get, store, invalidate)
- Error handling for each error type

### Property-Based Tests
- Property 1: Query intent extraction (100 iterations)
- Property 2: Context retrieval completeness (100 iterations)
- Property 3: Bedrock prompt structure (100 iterations)
- Property 4: Response caching correctness (100 iterations)
- Property 5: Cache invalidation consistency (100 iterations)
- Property 6: Conversation context continuity (100 iterations)
- Property 7: Recommendation safety (100 iterations)
- Property 8: Recommendation prioritization (100 iterations)
- Property 9: Time range interpretation (100 iterations)
- Property 10: Service name normalization (100 iterations)
- Property 11: Response time bounds (100 iterations)
- Property 12: Error message clarity (100 iterations)
- Property 13: Forecast integration accuracy (100 iterations)
- Property 14: Prevention action attribution (100 iterations)
- Property 15: Backward compatibility (100 iterations)

### Integration Tests
- End-to-end query processing
- Bedrock API integration
- Cost Explorer integration
- Phase 2 forecast integration
- Phase 3 prevention integration
- Cache hit/miss scenarios
- Conversation flow with multiple turns
- Proactive insight generation
- Backward compatibility with Phase 1-3

### Performance Tests
- Response time under load (100 concurrent queries)
- Cache hit rate measurement
- Bedrock API call frequency
- Memory usage during query processing

## Free Tier Compliance

### Bedrock Usage Optimization
- **Target:** <500 API calls/month
- **Strategy:** 40%+ cache hit rate through aggressive caching
- **Prompt Optimization:** Keep prompts under 1000 tokens
- **Model Selection:** Use Nova Lite (most cost-effective)

### DynamoDB Usage
- **Conversation History Table:** ~10 MB storage
- **Cache Table:** ~50 MB storage
- **Total:** ~60 MB (well within 25 GB free tier)

### Lambda Invocations
- **Estimated:** +1000 invocations/month
- **Total System:** ~5000 invocations/month (within 1M free tier)

### Cost Estimate
- **Bedrock:** ~$0.50/month (500 calls with caching)
- **DynamoDB:** $0 (within free tier)
- **Lambda:** $0 (within free tier)
- **Total Phase 4 Cost:** ~$0.50/month
- **Total System Cost:** ~$2.01/month (Phases 1-4)

## Performance Targets

- **Cached Query Response:** <500ms (P95)
- **Non-Cached Query Response:** <5s (P95)
- **Bedrock API Call:** 2-4s average
- **Context Retrieval:** <1s
- **Cache Hit Rate:** 40%+ target
- **Concurrent Queries:** 100 without degradation
- **Daily Insight Generation:** <10s per user

## Security Considerations

- **API Authentication:** API key required for all endpoints
- **Query Sanitization:** Sanitize user input before Bedrock invocation
- **Data Privacy:** No PII in Bedrock prompts
- **Cache Security:** Encrypt cache data at rest
- **Conversation History:** 24-hour TTL, automatic cleanup
- **IAM Permissions:** Least privilege for Lambda role

## Deployment Considerations

- **Lambda Memory:** 512 MB (sufficient for Bedrock calls)
- **Lambda Timeout:** 30 seconds (allows for Bedrock retries)
- **DynamoDB Tables:** 2 new tables (conversation-history, advisor-cache)
- **API Gateway Routes:** 4 new endpoints
- **Environment Variables:** BEDROCK_MODEL_ID, CACHE_TTL_HOURS
- **Backward Compatibility:** No changes to existing infrastructure
