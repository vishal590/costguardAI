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

### Key Features

- **Historical Cost Data (Phase 1):** Fetch and query AWS cost data from Cost Explorer with flexible granularity (hourly, daily, monthly)
- **Near-Real-Time Cost Estimation (Phase 1.5):** Estimate current AWS costs based on CloudWatch metrics for EC2, Lambda, DynamoDB, S3, and RDS
- **AI-Powered Cost Forecasting (Phase 2):** Generate 7-30 day cost forecasts using Amazon Bedrock Nova Lite with 95% confidence intervals
- **RESTful API:** Simple HTTP API with API key authentication
- **Free Tier Compliant:** Designed to operate within AWS Free Tier limits
- **Serverless Architecture:** Built on AWS Lambda, API Gateway, DynamoDB, and Amazon Bedrock for automatic scaling

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway                              │
│  Phase 1: /api/cost-data/fetch, /api/cost-data             │
│  Phase 1.5: /api/cost-estimation/current                    │
│             /api/cost-estimation/service/{service}          │
│  Phase 2: /api/cost-forecast                                │
│           /api/cost-forecast/service/{service}              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Function                                 │
│  - Cost Explorer integration (historical data)              │
│  - CloudWatch metrics collection (real-time)                │
│  - Cost estimation algorithms                               │
│  - Pricing data management                                  │
│  - AI forecasting with Amazon Bedrock (NEW)                 │
│  - Forecast caching with DynamoDB (NEW)                     │
└────┬────────────────────┬────────────────────┬─────────────┘
     │                    │                    │
     ▼                    ▼                    ▼
┌──────────┐      ┌──────────────┐    ┌─────────────────┐
│   Cost   │      │   DynamoDB   │    │  CloudWatch,    │
│ Explorer │      │  - Cost Data │    │  Pricing API &  │
│          │      │  - Forecasts │    │  Bedrock Nova   │
└──────────┘      └──────────────┘    └─────────────────┘
```

## 🛠️ Tech Stack

- **AWS Services:** Lambda, API Gateway, DynamoDB, Cost Explorer, CloudWatch, Pricing API, Amazon Bedrock (Nova Lite)
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
│   │   └── phase2-ai-forecasting/ # Phase 2 docs (NEW)
│   └── INDEX.md                   # Master documentation index
├── src/                           # Source code
│   ├── lambda_handler.py          # Main Lambda handler
│   ├── services/                  # Service modules
│   │   ├── cost_explorer.py       # Cost Explorer integration
│   │   ├── cloudwatch_collector.py # CloudWatch metrics
│   │   ├── cost_estimator.py      # Cost estimation
│   │   ├── pricing_manager.py     # Pricing data management
│   │   ├── forecast_engine.py     # Forecast orchestration (NEW)
│   │   ├── bedrock_client.py      # Amazon Bedrock integration (NEW)
│   │   ├── historical_data.py     # Historical data retrieval (NEW)
│   │   ├── forecast_cache.py      # Forecast caching (NEW)
│   │   └── dynamodb.py            # DynamoDB operations
│   └── utils/                     # Utility modules
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests
│   └── integration/               # Integration tests
├── infrastructure/                # AWS CDK infrastructure code
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

1. **Bootstrap CDK (first time only):**
   ```bash
   cd infrastructure
   cdk bootstrap
   ```

2. **Deploy the stack:**
   ```bash
   cdk deploy
   ```

3. **Note the API endpoint and API key from the deployment output**

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
| POST | `/api/cost-data/fetch` | Fetch cost data from AWS Cost Explorer |
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

**Query Parameters:**
- `hours` - Time range in hours for estimation (default: 1, max: 168)
- `days` - Forecast horizon for forecasting: 7, 14, or 30 (default: 30)
- `granularity` - Time resolution: `daily` or `weekly` (default: daily)
- `startDate` - Start date for historical queries (YYYY-MM-DD)
- `endDate` - End date for historical queries (YYYY-MM-DD)
- `service` - Filter by service name
- `limit` - Maximum number of records to return

## 🧪 Testing

The project uses a comprehensive testing strategy:

- **Unit Tests:** Test individual components with mocked dependencies
- **Property-Based Tests:** Validate universal properties using Hypothesis (100+ iterations per property)
- **Integration Tests:** Test end-to-end flows and service interactions

**Test Coverage:** 94%+ code coverage maintained (412 tests passing)

**Key Properties Tested:**
- Non-negative cost estimates and forecasts
- Forecast confidence interval validity
- Historical data validation and interpolation
- Cache key uniqueness and TTL enforcement
- Pricing data freshness
- API response structure validation
- Authentication enforcement
- Phase 1 & 1.5 backward compatibility
- Error isolation and retry logic
- Bedrock prompt structure and retry logic

## 💰 Cost Optimization

CostGuard is designed to operate within AWS Free Tier:

- **Lambda:** ~2,000 invocations/month (within 1M free tier)
- **API Gateway:** ~2,000 requests/month (within 1M free tier)
- **DynamoDB:** On-demand billing, ~100 MB storage (within 25 GB free tier)
  - Cost data table: ~50 MB
  - Forecast cache table: ~50 MB
- **CloudWatch:** ~50,000 API requests/month (within 1M free tier)
- **Cost Explorer:** ~100 API calls/month (~$1/month)
- **Pricing API:** ~100 calls/month with caching (~$0.01/month)
- **Amazon Bedrock (Nova Lite):** ~500 requests/month with 80%+ cache hit rate (~$0.50/month)

**Estimated Monthly Cost:** ~$1.51 (mostly Cost Explorer API and Bedrock)

## 🔗 Resources

- [AWS Builder Center](https://builder.aws.com)
- [10,000 AIdeas Competition](https://builder.aws.com/connect/events/10000aideas)
- [AWS Free Tier](https://aws.amazon.com/free/)

---

**Note:** This project is part of the AWS Global 10,000 AIdeas Competition. 

**⚠️ IMPORTANT:** See [docs/MANDATORY-RULES.md](./docs/MANDATORY-RULES.md) and [docs/competition/terms.md](./docs/competition/terms.md) for mandatory requirements and terms.
