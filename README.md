# AWS 10,000 AIdeas Hackathon Project

> **Competition:** AWS Global 10,000 AIdeas Competition  
> **Submission Deadline:** January 21, 2026 11:59pm PT  
> **Prize Pool:** $250,000 cash + $30,000 AWS Credits

## ⚠️ MANDATORY - READ FIRST

**Before participating, you MUST read and comply with:**
- **[docs/MANDATORY-RULES.md](./docs/MANDATORY-RULES.md)** - Quick reference for all mandatory rules
- **[docs/competition/terms.md](./docs/competition/terms.md)** - Complete Terms and Conditions

**Non-compliance may result in disqualification or prize forfeiture.**

## 📚 Documentation

**Start here:** [docs/INDEX.md](./docs/INDEX.md) - Master documentation index with navigation to all files

**NEW:** [docs/DOCUMENTATION_MAP.md](./docs/DOCUMENTATION_MAP.md) - Complete documentation map with:
- Role-based navigation (Developers, PMs, Stakeholders)
- Topic clustering and semantic organization
- Cross-reference matrix and use case navigation
- Comprehensive search tags and documentation metrics

### Quick Links
- ⚠️ **[Mandatory Rules](./docs/MANDATORY-RULES.md)** - All mandatory requirements
- ⚠️ **[Terms & Conditions](./docs/competition/terms.md)** - Complete terms
- ⚠️ **[FAQ](./docs/competition/faq.md)** - Frequently Asked Questions
- [Competition Overview](./docs/competition/overview.md)
- [Eligibility Requirements](./docs/competition/eligibility.md)
- [Submission Requirements](./docs/submission/requirements.md)
- [Project Ideas](./docs/project/ideas.md)
- [Project Planning](./docs/project/planning.md)

## 🚀 Project Overview

**CostGuard** is a near-real-time AWS cost monitoring and estimation system that provides immediate visibility into cloud spending. Unlike traditional cost tracking tools that rely on AWS Cost Explorer's 24-hour delayed data, CostGuard estimates current costs by collecting CloudWatch metrics and applying real-time pricing calculations.

### Key Features (Phases 1-6 Complete)

- **Historical Cost Data (Phase 1):** Fetch and query AWS cost data from Cost Explorer with flexible granularity (hourly, daily, monthly)
- **Near-Real-Time Cost Estimation (Phase 1.5):** Estimate current AWS costs based on CloudWatch metrics for EC2, Lambda, DynamoDB, S3, and RDS
- **AI-Powered Cost Forecasting (Phase 2):** Generate 7-30 day cost forecasts using Amazon Bedrock Nova Lite with 95% confidence intervals
- **Automated Cost Prevention (Phase 3):** Automatically detect and prevent cost overruns with:
  - Budget threshold monitoring (80% warning, 90% action)
  - Idle resource detection across 20+ AWS services
  - Automated actions (stop EC2, limit Lambda, switch DynamoDB billing)
  - Safety guards (tag-based protection, whitelists, active usage checks)
  - Approval workflows with 30-minute timeout
  - 24-hour rollback capability
  - Comprehensive audit logging
- **AI Cost Advisor (Phase 4):** Conversational AI assistant powered by Amazon Bedrock Nova Lite:
  - Natural language cost queries ("What were my EC2 costs last month?")
  - Context-aware responses with historical data, forecasts, and prevention actions
  - Proactive cost insights (daily summaries, anomaly detection, optimization suggestions)
  - Conversation history for follow-up questions
  - Aggressive caching (40%+ hit rate) for cost efficiency
  - Markdown-formatted responses with cost tables and highlights
- **Multi-Account Cost Management (Phase 5):** Enterprise-grade multi-account support:
  - AWS Organizations integration
  - Cross-account cost aggregation
  - Tag-based cost allocation
  - Chargeback and showback reports
  - Hierarchical budgets
- **AI/ML Workload Cost Management (Phase 6):** GPU cost tracking and optimization:
  - GPU cost tracking by workload type (training, inference, idle)
  - Cost-per-inference and cost-per-training calculations
  - Spot instance recommendations (up to 70% savings)
  - SageMaker and Bedrock cost optimization
  - Automated workload classification
- **RESTful API:** Simple HTTP API with API key authentication
- **Free Tier Compliant:** Designed to operate within AWS Free Tier limits
- **Serverless Architecture:** Built on AWS Lambda, API Gateway, DynamoDB, Amazon Bedrock, and EventBridge for automatic scaling

### Future Roadmap (Phase 7-8)

See [docs/FUTURE_ROADMAP.md](./docs/FUTURE_ROADMAP.md) for post-hackathon features:
- **Phase 7:** Unit Economics + RI/SP Optimization (enterprise FinOps at SMB prices)
- **Phase 8:** Developer Cost Transparency Tools (VS Code extension, GitHub Action, IaC cost preview)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway                              │
│  Phase 1: /api/fetch, /api/cost-data                       │
│  Phase 1.5: /api/cost-estimation/*                          │
│  Phase 2: /api/cost-forecast/*                              │
│  Phase 3: /api/prevention/* (NEW)                           │
│  Phase 4: /api/advisor/* (NEW)                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Function                                 │
│  - Cost Explorer integration (historical data)              │
│  - CloudWatch metrics collection (real-time)                │
│  - Cost estimation algorithms                               │
│  - Pricing data management                                  │
│  - AI forecasting with Amazon Bedrock                       │
│  - Forecast caching with DynamoDB                           │
│  - Budget monitoring & prevention engine                    │
│  - Resource discovery & idle detection                      │
│  - Safety guards & action execution                         │
│  - AI Cost Advisor with conversational interface (NEW)      │
│  - Query processing & context management (NEW)              │
│  - Response formatting & caching (NEW)                      │
└────┬────────────────────┬────────────────────┬─────────────┘
     │                    │                    │
     ▼                    ▼                    ▼
┌──────────┐      ┌──────────────┐    ┌─────────────────┐
│   Cost   │      │   DynamoDB   │    │  CloudWatch,    │
│ Explorer │      │  - Cost Data │    │  Pricing API,   │
│  Budgets │      │  - Forecasts │    │  Bedrock Nova,  │
│          │      │  - Config    │    │  & SNS Topics   │
│          │      │  - Inventory │    │                 │
│          │      │  - Audit Log │    │                 │
│          │      │  - Advisor   │    │                 │
│          │      │    Cache     │    │                 │
│          │      │  - Advisor   │    │                 │
│          │      │    History   │    │                 │
└──────────┘      └──────────────┘    └─────────────────┘
                           ▲
                           │
                  ┌────────┴────────┐
                  │   EventBridge   │
                  │  (5-min schedule)│
                  └─────────────────┘
```

## 🛠️ Tech Stack

- **AWS Services:** Lambda, API Gateway, DynamoDB, Cost Explorer, AWS Budgets, CloudWatch, Pricing API, Amazon Bedrock (Nova Lite), SNS, EventBridge
- **Language:** Python 3.11
- **Testing:** pytest, Hypothesis (property-based testing), moto (AWS mocking)
- **Infrastructure:** AWS CDK (Python)
- **Authentication:** API Gateway API Keys

## 📁 Project Structure

```
aws-ideas/
├── docs/                          # Documentation
│   ├── competition/               # Competition rules and info
│   ├── submission/                # Submission requirements
│   ├── technical/                 # Technical documentation
│   │   ├── phase1-cost-pipeline/  # Phase 1 docs
│   │   ├── phase1.5-near-realtime/ # Phase 1.5 docs
│   │   ├── phase2-ai-forecasting/ # Phase 2 docs
│   │   ├── phase3-automated-prevention/ # Phase 3 docs
│   │   └── phase4-ai-advisor/     # Phase 4 docs (NEW)
│   └── INDEX.md                   # Master documentation index
├── src/                           # Source code
│   ├── lambda_handler.py          # Main Lambda handler
│   ├── services/                  # Service modules
│   │   ├── cost_explorer.py       # Cost Explorer integration
│   │   ├── cloudwatch_collector.py # CloudWatch metrics
│   │   ├── cost_estimator.py      # Cost estimation
│   │   ├── pricing_manager.py     # Pricing data management
│   │   ├── forecast_engine.py     # Forecast orchestration
│   │   ├── bedrock_client.py      # Amazon Bedrock integration
│   │   ├── historical_data.py     # Historical data retrieval
│   │   ├── forecast_cache.py      # Forecast caching
│   │   ├── prevention_engine.py   # Prevention orchestration (NEW)
│   │   ├── budget_monitor.py      # Budget monitoring (NEW)
│   │   ├── resource_manager.py    # Resource discovery (NEW)
│   │   ├── idle_detector.py       # Idle detection (NEW)
│   │   ├── safety_guard.py        # Safety checks (NEW)
│   │   ├── action_executor.py     # Action execution (NEW)
│   │   ├── approval_manager.py    # Approval workflows (NEW)
│   │   ├── rollback_manager.py    # Rollback management (NEW)
│   │   ├── notification_service.py # SNS notifications (NEW)
│   │   ├── eventbridge_scheduler.py # EventBridge integration (NEW)
│   │   ├── advisor_engine.py      # AI advisor orchestration (NEW)
│   │   ├── query_processor.py     # NLP query parsing (NEW)
│   │   ├── context_manager.py     # Context retrieval (NEW)
│   │   ├── bedrock_advisor_client.py # Bedrock advisor client (NEW)
│   │   ├── response_formatter.py  # Response formatting (NEW)
│   │   ├── advisor_cache_manager.py # Advisor caching (NEW)
│   │   ├── insight_generator.py   # Proactive insights (NEW)
│   │   └── dynamodb.py            # DynamoDB operations
│   └── utils/                     # Utility modules
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests (598 tests)
│   ├── property/                  # Property-based tests (82 tests)
│   └── integration/               # Integration tests
├── infrastructure/                # AWS CDK infrastructure code
│   ├── cdk_stack.py               # Complete CDK stack
│   ├── dynamodb_tables.json       # DynamoDB table configs
│   ├── iam_permissions.json       # IAM role configs
│   ├── lambda_environment.json    # Lambda env vars
│   ├── sns_topics.json            # SNS topic configs
│   ├── api_gateway.json           # API Gateway configs
│   └── eventbridge_schedule.json  # EventBridge schedule
└── README.md                      # This file
```

## 🏃 Getting Started

### Prerequisites

- AWS Account with appropriate permissions
- Python 3.12+
- AWS CLI configured
- Node.js 18+ (for AWS CDK)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd aws-ideas
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install CDK dependencies:**
   ```bash
   cd infrastructure
   npm install
   cd ..
   ```

### Deployment

**📖 Complete Deployment Guide:** See [DEPLOYMENT_PLAN.md](./DEPLOYMENT_PLAN.md) for detailed phase-by-phase deployment instructions.

**🔧 Troubleshooting:** See [DEPLOYMENT_TROUBLESHOOTING.md](./DEPLOYMENT_TROUBLESHOOTING.md) for solutions to common deployment issues.

**Quick Start:**

1. **Bootstrap CDK (first time only):**
   ```bash
   cd infrastructure
   cdk bootstrap aws://YOUR-ACCOUNT-ID/us-east-1
   ```

2. **Deploy the stack:**
   ```bash
   cdk deploy --require-approval never
   ```

3. **Note the API endpoint from the deployment output**

**Deployment Status:** ✅ Phase 1-3 deployed successfully on February 27, 2026. See [DEPLOYMENT_STATUS.md](./DEPLOYMENT_STATUS.md) for details.

### Usage

#### Phase 1: Historical Cost Data

**Fetch cost data from Cost Explorer:**
```bash
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2025-01-01",
    "endDate": "2025-12-31",
    "granularity": "MONTHLY"
  }' \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/cost-data/fetch"
```

**Query stored cost data:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/cost-data?startDate=2025-01-01&endDate=2025-12-31"
```

#### Phase 1.5: Near-Real-Time Cost Estimation

**Get current cost estimates for all services:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/current?hours=1"
```

**Get cost estimate for a specific service:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/cost-estimation/service/ec2?hours=24"
```

**Supported services:** `ec2`, `lambda`, `dynamodb`, `s3`, `rds`

#### Phase 2: AI-Powered Cost Forecasting

**Get 30-day cost forecast:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/cost-forecast?days=30&granularity=daily"
```

**Get weekly forecast for specific service:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/cost-forecast/service/ec2?days=30&granularity=weekly"
```

**Query Parameters:**
- `days` - Forecast horizon: 7, 14, or 30 days (default: 30)
- `granularity` - Time resolution: `daily` or `weekly` (default: daily)

**Response includes:**
- Predicted costs for each time period
- 95% confidence intervals (upper/lower bounds)
- Metadata (model used, cache status, historical data days)

#### Phase 3: Automated Cost Prevention

**Get prevention system status:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/prevention/status"
```

**Enable prevention system:**
```bash
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/prevention/enable"
```

**Get discovered resources:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/prevention/resources?service=ec2&limit=50"
```

**Rollback a prevention action:**
```bash
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action_id": "action-123"}' \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/prevention/rollback"
```

**Get prevention action history:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/prevention/history?start_date=2025-01-01&limit=100"
```

**Features:**
- Automatic budget monitoring every 5 minutes via EventBridge
- Idle resource detection across 20+ AWS services (EC2, RDS, Lambda, EBS, S3, DynamoDB, etc.)
- Safety guards: tag-based protection, whitelists, active usage checks
- Dry run mode for testing (enabled by default)
- Approval workflows with 30-minute timeout
- 24-hour rollback capability
- Comprehensive audit logging

#### Phase 4: AI Cost Advisor

**Ask natural language cost questions:**
```bash
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What were my EC2 costs last month?",
    "user_id": "user123",
    "session_id": "session456"
  }' \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/advisor/query"
```

**Get conversation history:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/advisor/history?session_id=session456"
```

**Clear conversation history:**
```bash
curl -X DELETE \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "session456"}' \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/advisor/history"
```

**Get proactive cost insights:**
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/api/advisor/suggestions?user_id=user123"
```

**Features:**
- Natural language query processing with intent classification
- Context-aware responses using historical data, forecasts, and prevention actions
- Conversation history for follow-up questions (last 10 turns)
- Proactive insights: daily summaries, anomaly detection, optimization suggestions
- Aggressive caching (40%+ hit rate, 24-hour TTL) for cost efficiency
- Markdown-formatted responses with cost tables and number highlighting
- Response time: <500ms (cached), <5s (non-cached)

**Example queries:**
- "What were my costs last month?"
- "Show me EC2 spending trends"
- "How can I reduce my Lambda costs?"
- "What's my forecast for next week?"
- "Which resources are idle?"

**Features:**
- Automatic budget monitoring every 5 minutes via EventBridge
- Idle resource detection across 20+ AWS services (EC2, RDS, Lambda, EBS, S3, DynamoDB, etc.)
- Safety guards: tag-based protection, whitelists, active usage checks
- Dry run mode for testing (enabled by default)
- Approval workflows with 30-minute timeout
- 24-hour rollback capability
- Comprehensive audit logging

For more examples, see [docs/API_EXAMPLES.md](./docs/API_EXAMPLES.md)

### Running Tests

**Run all tests:**
```bash
pytest
```

**Run with coverage:**
```bash
pytest --cov=src --cov-report=html
```

**Run property-based tests only:**
```bash
pytest -k "properties"
```

### Local Development

**Set up virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Run tests in watch mode:**
```bash
pytest-watch
```

## 📖 Documentation Structure

All documentation is organized in the `docs/` folder. See [docs/INDEX.md](./docs/INDEX.md) for:
- Complete file listing
- Topic-based navigation
- Use-case navigation
- Code-documentation linking
- Search tips

### Key Documentation

- **[Future Roadmap](./docs/FUTURE_ROADMAP.md)** - Phase 7-8 post-hackathon features
- **[API Examples](./docs/API_EXAMPLES.md)** - Complete API usage examples with curl and Python
- **[Phase 1 Technical Docs](./docs/technical/phase1-cost-pipeline/)** - Historical cost data pipeline
- **[Phase 1.5 Technical Docs](./docs/technical/phase1.5-near-realtime/)** - Near-real-time cost estimation
- **[Phase 2 Technical Docs](./docs/technical/phase2-ai-forecasting/)** - AI-powered cost forecasting
- **[Architecture](./docs/technical/architecture.md)** - System architecture and design decisions
- **[Submission Guide](./docs/submission/SUBMISSION-GUIDE.md)** - Competition submission information

## 🎯 API Endpoints

### Phase 1: Historical Cost Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/fetch` | Fetch cost data from AWS Cost Explorer |
| GET | `/api/cost-data` | Query stored historical cost data |

### Phase 1.5: Near-Real-Time Cost Estimation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cost-estimation/current` | Get current cost estimates for all services |
| GET | `/api/cost-estimation/service/{service}` | Get cost estimate for specific service |

### Phase 2: AI-Powered Cost Forecasting

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cost-forecast` | Get AI-powered cost forecast for all services |
| GET | `/api/cost-forecast/service/{service}` | Get cost forecast for specific service |

### Phase 3: Automated Cost Prevention

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/prevention/status` | Get prevention system status |
| POST | `/api/prevention/enable` | Enable prevention system |
| POST | `/api/prevention/disable` | Disable prevention system |
| GET | `/api/prevention/resources` | Get discovered resource inventory |
| POST | `/api/prevention/rollback` | Rollback a prevention action |
| GET | `/api/prevention/history` | Get prevention action history |

### Phase 4: AI Cost Advisor

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/advisor/query` | Ask natural language cost questions |
| GET | `/api/advisor/history` | Get conversation history for a session |
| DELETE | `/api/advisor/history` | Clear conversation history |
| GET | `/api/advisor/suggestions` | Get proactive cost insights |

**Query Parameters:**
- `hours` - Time range in hours for estimation (default: 1, max: 168)
- `days` - Forecast horizon for forecasting: 7, 14, or 30 (default: 30)
- `granularity` - Time resolution: `daily` or `weekly` (default: daily)
- `startDate` - Start date for historical queries (YYYY-MM-DD)
- `endDate` - End date for historical queries (YYYY-MM-DD)
- `service` - Filter by service name
- `state` - Filter resources by state (running, stopped, etc.)
- `limit` - Maximum number of records to return
- `user_id` - User identifier for advisor queries (default: "default")
- `session_id` - Session identifier for conversation history (default: "default")

## 🧪 Testing

The project uses a comprehensive testing strategy:

- **Unit Tests:** Test individual components with mocked dependencies (598 tests)
- **Property-Based Tests:** Validate universal properties using Hypothesis (82 tests, 100+ iterations per property)
- **Integration Tests:** Test end-to-end flows and service interactions

**Test Coverage:** 87%+ code coverage maintained (680 tests passing)

**Key Properties Tested:**
- **Phase 1 & 1.5:** Non-negative cost estimates, pricing data freshness, API response validation
- **Phase 2:** Forecast confidence intervals, cache key uniqueness, Bedrock prompt structure
- **Phase 3:** Budget threshold detection, protected resource safety, idle detection consistency, action reversibility, dry run safety, audit trail completeness, multi-service coverage, safety check ordering, notification delivery, configuration validation, approval timeout handling, resource inventory freshness, action prioritization, error isolation, backward compatibility
- **Phase 4 (NEW):** Query intent extraction consistency, context retrieval completeness, response caching correctness, conversation context continuity, time range interpretation, service name normalization, response time bounds, error message clarity, forecast integration accuracy, prevention action attribution, backward compatibility

## 💰 Cost Optimization

CostGuard is designed to operate within AWS Free Tier:

- **Lambda:** ~10,640 invocations/month (within 1M free tier)
  - API requests: ~2,000/month
  - EventBridge scheduled: ~8,640/month (budget monitoring every 5 minutes)
- **API Gateway:** ~2,000 requests/month (within 1M free tier)
- **DynamoDB:** On-demand billing, ~260 MB storage (within 25 GB free tier)
  - Cost data table: ~50 MB
  - Forecast cache table: ~50 MB
  - Prevention config table: ~10 MB
  - Resource inventory table: ~40 MB
  - Prevention audit table: ~30 MB
  - Approval requests table: ~20 MB
  - Advisor cache table: ~50 MB (NEW)
  - Advisor conversation history table: ~10 MB (NEW)
- **CloudWatch:** ~50,000 API requests/month (within 1M free tier)
- **Cost Explorer:** ~100 API calls/month (~$1/month)
- **AWS Budgets:** 2 budgets (free)
- **Pricing API:** ~100 calls/month with caching (~$0.01/month)
- **Amazon Bedrock (Nova Lite):** ~1,000 requests/month with 80%+ cache hit rate (~$1.00/month)
  - Phase 2 forecasting: ~500 requests/month (~$0.50/month)
  - Phase 4 advisor: ~500 requests/month (~$0.50/month)
- **SNS:** ~348 messages/month (within 1M publishes/month free tier)
- **EventBridge:** Rules are free, invocations count toward Lambda free tier

**Estimated Monthly Cost:** ~$2.01 (mostly Cost Explorer API and Bedrock)

**Phase 4 adds ~$0.50/month** for conversational AI capabilities while providing significant value through natural language cost insights.

## 🔗 Resources

- [AWS Builder Center](https://builder.aws.com)
- [10,000 AIdeas Competition](https://builder.aws.com/connect/events/10000aideas)
- [AWS Free Tier](https://aws.amazon.com/free/)

---

**Note:** This project is part of the AWS Global 10,000 AIdeas Competition. 

**⚠️ IMPORTANT:** See [docs/MANDATORY-RULES.md](./docs/MANDATORY-RULES.md) and [docs/competition/terms.md](./docs/competition/terms.md) for mandatory requirements and terms.
