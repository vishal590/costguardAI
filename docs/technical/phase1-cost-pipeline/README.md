# Phase 1: Cost Data Pipeline

> **Current-reference note (October 3, 2026):** Use [current API contracts](../api-design.md), [database schemas](../database-design.md) and [project status](../../PROJECT_STATUS.md) for source behavior. Test counts, coverage and deployment metrics below record earlier work; they were not rerun or checked against AWS in this documentation pass.

> **Part of CostGuard AI** - AWS Cost Management & Optimization Platform  
> **Documentation Location:** `docs/technical/phase1-cost-pipeline/`  
> **Related:** [Project README](../../../README.md) | [Docs Index](../../INDEX.md) | [Development Notes](../development-notes.md)

A serverless AWS cost data pipeline that fetches historical cost data from AWS Cost Explorer and makes it available through REST API endpoints. Built with AWS Lambda, DynamoDB, and API Gateway.

## Features

- **Automated Cost Data Fetching**: Retrieve AWS cost data from Cost Explorer API with configurable date ranges and granularity
- **Efficient Storage**: Store cost data in DynamoDB using partition key (pk) and sort key (sk) for optimized Query operations
- **REST API**: Query stored cost data through authenticated REST endpoints
- **Robust Error Handling**: Exponential backoff retry logic for rate limits and transient errors
- **Property-Based Testing**: Comprehensive test coverage with both unit and property-based tests
- **Free Tier Compatible**: Designed to operate within AWS Free Tier limits

**Where service data appears:** Cost history (Phase 1) shows **all** services from Cost Explorer. Current estimate (Phase 1.5) uses **5** services (EC2, Lambda, DynamoDB, S3, RDS). The **22 services** in Resource Manager are used in **Phase 3 Prevention** only. See [Services: where data appears](../SERVICES-WHERE-DATA-APPEARS.md).

## Architecture

```
┌─────────────────┐
│   API Gateway   │  ← API Key Authentication
│   (REST API)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Lambda      │  ← Python 3.11, 256 MB, 30s timeout
│    Function     │
└────┬────────┬───┘
     │        │
     ▼        ▼
┌─────────┐  ┌──────────┐
│  Cost   │  │ DynamoDB │  ← On-demand billing, TTL enabled
│Explorer │  │  Table   │
└─────────┘  └──────────┘
```

## Project Structure

```
.
├── src/                          # Source code
│   ├── lambda_handler.py         # Main Lambda handler
│   ├── services/                 # Service layer
│   │   ├── cost_explorer.py     # Cost Explorer integration
│   │   └── dynamodb.py           # DynamoDB operations
│   └── utils/                    # Utility functions
│       ├── types.py              # Type definitions
│       ├── validation.py         # Input validation
│       ├── date_utils.py         # Date utilities
│       ├── helpers.py            # Helper functions
│       └── error_handler.py      # Error handling & retry logic
├── tests/                        # Test suite
│   └── unit/                     # Unit and property-based tests
├── infrastructure/               # AWS CDK infrastructure
│   ├── app.py                    # Main CDK app
│   ├── dynamodb_table.py         # DynamoDB table definition
│   ├── lambda_function.py        # Lambda configuration
│   ├── iam_roles.py              # IAM roles and policies
│   └── api_gateway.py            # API Gateway configuration
├── docs/                         # Documentation
├── deploy.sh                     # Deployment script (Unix/Linux/macOS)
├── deploy.ps1                    # Deployment script (Windows)
├── requirements.txt              # Python dependencies
└── pytest.ini                    # Pytest configuration
```

## Prerequisites

- **Python 3.11** or later
- **AWS CLI** configured with credentials
- **AWS CDK CLI**: `npm install -g aws-cdk`
- **AWS Account** with permissions for:
  - Cost Explorer (ce:GetCostAndUsage, ce:GetDimensionValues)
  - DynamoDB (create tables, read/write)
  - Lambda (create functions)
  - API Gateway (create APIs)
  - IAM (create roles and policies)
  - CloudWatch Logs

## Setup Instructions

### 1. Clone and Navigate to Project

```bash
cd cost-data-pipeline
```

### 2. Create Virtual Environment

**Unix/Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure AWS Credentials

Ensure your AWS credentials are configured:

```bash
aws configure
```

You'll need:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., us-east-1)
- Output format (json)

### 5. Run Tests

```bash
pytest --cov=src --cov-report=term-missing tests/
```

Expected output: 105 tests passed, 91%+ coverage

## Deployment

### Automated Deployment

**Unix/Linux/macOS:**
```bash
chmod +x deploy.sh
./deploy.sh
```

**Windows PowerShell:**
```powershell
.\deploy.ps1
```

The deployment script will:
1. Create virtual environment
2. Install dependencies
3. Run tests
4. Package Lambda function
5. Deploy infrastructure with CDK
6. Output API endpoint and API key ID

### Manual Deployment

If you prefer manual deployment:

1. **Install CDK dependencies:**
```bash
cd infrastructure
pip install -r requirements.txt
```

2. **Bootstrap CDK (first time only):**
```bash
cdk bootstrap
```

3. **Deploy infrastructure:**
```bash
cdk deploy
```

4. **Note the outputs:**
   - API Gateway endpoint URL
   - API Key ID

### Retrieve API Key

After deployment, retrieve your API key value:

```bash
aws apigateway get-api-key --api-key <API_KEY_ID> --include-value --query 'value' --output text
```

## API Usage

### Base URL

```
https://<api-id>.execute-api.<region>.amazonaws.com/prod
```

### Authentication

All requests require an API key in the `x-api-key` header:

```bash
curl -H "x-api-key: YOUR_API_KEY" <endpoint>
```

### Endpoints

#### 1. Fetch Cost Data

**POST** `/api/cost-data/fetch`

Fetches cost data from AWS Cost Explorer and stores it in DynamoDB.

**Request Body:**
```json
{
  "startDate": "2025-01-01",
  "endDate": "2025-12-31",
  "granularity": "MONTHLY"
}
```

**Parameters:**
- `startDate` (optional): Start date in YYYY-MM-DD format. Default: 12 months ago
- `endDate` (optional): End date in YYYY-MM-DD format. Default: today
- `granularity` (optional): DAILY | MONTHLY | HOURLY. Default: MONTHLY

**Response:**
```json
{
  "success": true,
  "message": "Cost data fetched and stored successfully",
  "data": {
    "recordsProcessed": 120,
    "dateRange": {
      "start": "2025-01-01",
      "end": "2025-12-31"
    },
    "totalCost": 1234.56,
    "services": ["EC2", "S3", "Lambda", "DynamoDB"]
  }
}
```

**Example:**
```bash
curl -X POST \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"startDate":"2025-01-01","endDate":"2025-12-31","granularity":"MONTHLY"}' \
  https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/api/cost-data/fetch
```

#### 2. Query Cost Data

**GET** `/api/cost-data`

Queries stored cost data from DynamoDB with optional filters.

**Query Parameters:**
- `startDate` (optional): Filter by start date (YYYY-MM-DD)
- `endDate` (optional): Filter by end date (YYYY-MM-DD)
- `service` (optional): Filter by service name
- `limit` (optional): Maximum records to return. Default: 100

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-01-01",
      "service": "Amazon Elastic Compute Cloud - Compute",
      "blendedCost": 123.45,
      "unblendedCost": 123.45,
      "currency": "USD"
    }
  ],
  "count": 12
}
```

**Examples:**

Query all data:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/api/cost-data"
```

Query with date range:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/api/cost-data?startDate=2025-01-01&endDate=2025-12-31"
```

Query specific service:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/api/cost-data?service=Amazon%20S3"
```

Query with limit:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/api/cost-data?limit=50"
```

### Error Responses

All errors follow this format:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  }
}
```

**Common Error Codes:**
- `INVALID_DATE_FORMAT`: Date doesn't match YYYY-MM-DD format
- `INVALID_DATE_RANGE`: Start date is after end date
- `INVALID_GRANULARITY`: Granularity is not DAILY, MONTHLY, or HOURLY
- `COST_EXPLORER_ERROR`: Error calling Cost Explorer API
- `DYNAMODB_ERROR`: Error accessing DynamoDB
- `VALIDATION_ERROR`: Input validation failed
- `INTERNAL_ERROR`: Unexpected server error

## Environment Variables

The Lambda function uses these environment variables (automatically set by CDK):

- `DYNAMODB_TABLE_NAME`: Name of the DynamoDB table (costguard-cost-data)
- `AWS_REGION`: AWS region for services

## Testing

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=src --cov-report=html
```

View coverage report: `htmlcov/index.html`

### Run Specific Test Files

```bash
pytest tests/unit/test_lambda_handler.py
pytest tests/unit/test_cost_explorer.py
pytest tests/unit/test_dynamodb.py
```

### Test Categories

- **Unit Tests**: Test specific functions and edge cases
- **Property-Based Tests**: Test universal properties across random inputs (using Hypothesis)
- **Integration Tests**: Test end-to-end flows (Task 13)

## Monitoring and Logs

### CloudWatch Logs

Lambda execution logs are available in CloudWatch:

```bash
aws logs tail /aws/lambda/costguard-cost-data-handler --follow
```

### Key Log Points

The Lambda function logs at these points:
- Function start (with event details)
- API calls to Cost Explorer (with parameters)
- Database operations (with record counts)
- Errors (with stack traces)
- Retry attempts (with attempt numbers)
- Function completion (with summary)

### Metrics

Monitor these CloudWatch metrics:
- Lambda invocations
- Lambda errors
- Lambda duration
- DynamoDB read/write capacity
- API Gateway requests
- API Gateway 4xx/5xx errors

## Cost Considerations

This pipeline is designed for AWS Free Tier:

- **DynamoDB**: On-demand billing (25 GB storage, 25 WCU, 25 RCU free)
- **Lambda**: 1M requests and 400,000 GB-seconds free per month
- **API Gateway**: 1M API calls free for 12 months
- **CloudWatch Logs**: 5 GB ingestion, 5 GB storage free
- **Cost Explorer API**: First 100 requests free, then $0.01 per request

**Estimated Monthly Cost** (after Free Tier):
- Minimal usage: $0-5
- Moderate usage (1000 API calls): $5-15
- Heavy usage (10000 API calls): $15-50

Monitor your usage in AWS Cost Explorer to avoid unexpected charges.

## Limitations

### Query Performance
- **Date Range Required for Efficiency:** For optimal performance, always provide both `startDate` and `endDate` parameters. Queries without a date range fall back to Scan operations, which are less efficient for large datasets.
- **Partition-Based Queries:** The system queries each month partition separately (COST#YYYY-MM). Queries spanning many months will make multiple DynamoDB Query calls, which is efficient but may take longer for very large date ranges.

### Schema Constraints
- **Partition Key Design:** Data is partitioned by month (COST#YYYY-MM). This design optimizes queries by date range but means service-based queries across multiple months require querying each month partition.
- **Global Secondary Index:** The optional GSI (`service-date-index`) mentioned in the specification is not currently implemented. Service-based queries use sort key filtering within month partitions.

### Data Accuracy
- **Cost Explorer Delay:** Historical cost data from AWS Cost Explorer has a 24-hour delay. The most recent data available is from yesterday.
- **Granularity Limits:** Cost Explorer API supports DAILY, MONTHLY, and HOURLY granularity, but HOURLY data may not be available for all services or time periods.

### Free Tier Considerations
- **DynamoDB Storage:** On-demand billing mode is used, but storage costs apply after the 25 GB free tier.
- **API Gateway Limits:** 1M API calls/month free tier. Monitor usage to avoid charges.
- **Cost Explorer API:** First 100 requests free, then $0.01 per request. Frequent fetching may incur costs.

### Scalability
- **Large Date Ranges:** Querying very large date ranges (e.g., 12+ months) will query multiple partitions sequentially. Consider pagination or limiting date ranges for better performance.
- **Batch Writes:** DynamoDB batch writes are limited to 25 items per batch. The system handles this automatically, but very large datasets may take longer to store.

## Troubleshooting

### Deployment Issues

**CDK Bootstrap Error:**
```bash
cdk bootstrap aws://<account-id>/<region>
```

**Permission Denied:**
- Ensure AWS credentials have necessary permissions
- Check IAM policies for Cost Explorer, DynamoDB, Lambda, API Gateway

**Lambda Package Too Large:**
- The package should be < 50 MB
- boto3 is included in Lambda runtime (no need to package)

### Runtime Issues

**401 Unauthorized:**
- Check API key is correct
- Ensure `x-api-key` header is included

**403 Forbidden:**
- Verify IAM role has Cost Explorer permissions
- Check DynamoDB table permissions

**429 Rate Limit:**
- Cost Explorer API has rate limits
- The system automatically retries with exponential backoff
- Consider reducing request frequency

**500 Internal Error:**
- Check CloudWatch Logs for details
- Verify DynamoDB table exists
- Ensure Lambda has correct environment variables

## Cleanup

To delete all infrastructure:

```bash
cd infrastructure
cdk destroy
```

**Note:** The DynamoDB table has a RETAIN removal policy and won't be automatically deleted. Delete it manually if needed:

```bash
aws dynamodb delete-table --table-name costguard-cost-data
```

## Development

### Adding New Features

1. Update requirements in `.kiro/specs/cost-data-pipeline/requirements.md`
2. Update design in `.kiro/specs/cost-data-pipeline/design.md`
3. Add tasks to `.kiro/specs/cost-data-pipeline/tasks.md`
4. Implement code changes
5. Write tests (unit and property-based)
6. Run tests and ensure coverage > 80%
7. Update documentation

### Code Style

- Follow PEP 8 style guide
- Use type hints for function signatures
- Write docstrings for all public functions
- Keep functions small and focused

### Testing Guidelines

- Write property-based tests for universal properties
- Write unit tests for specific examples and edge cases
- Aim for 80%+ code coverage
- Mock external services (Cost Explorer, DynamoDB)

## License

[Your License Here]

## Support

For issues and questions:
- Check CloudWatch Logs for error details
- Review the troubleshooting section
- Consult AWS documentation for service-specific issues

## Contributing

[Your Contributing Guidelines Here]
