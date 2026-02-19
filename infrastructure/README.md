# Cost Data Pipeline Infrastructure

This directory contains AWS CDK (Cloud Development Kit) infrastructure definitions for the Cost Data Pipeline.

## Components

- **dynamodb_table.py**: DynamoDB table definition with partition key (pk) and sort key (sk)
- **lambda_function.py**: Lambda function configuration (Python 3.11, 256 MB, 30s timeout)
- **iam_roles.py**: IAM roles and policies for Cost Explorer, DynamoDB, and CloudWatch access
- **api_gateway.py**: REST API with POST /api/cost-data/fetch and GET /api/cost-data endpoints
- **app.py**: Main CDK application that ties all components together

## Prerequisites

1. AWS CLI configured with credentials
2. AWS CDK CLI installed: `npm install -g aws-cdk`
3. Python 3.11 or later
4. Virtual environment with dependencies installed

## Setup

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Bootstrap CDK (first time only):
```bash
cdk bootstrap
```

## Deployment

1. Synthesize CloudFormation template:
```bash
cdk synth
```

2. Deploy infrastructure:
```bash
cdk deploy
```

3. Note the outputs:
   - API Gateway endpoint URL
   - API Key ID (use AWS CLI to retrieve the actual key value)

## Retrieve API Key

After deployment, retrieve the API key value:
```bash
aws apigateway get-api-key --api-key <API_KEY_ID> --include-value --query 'value' --output text
```

## Infrastructure Details

### DynamoDB Table
- **Name**: costguard-cost-data
- **Partition Key**: pk (String) - Format: COST#YYYY-MM
- **Sort Key**: sk (String) - Format: SERVICE#service-name
- **Billing Mode**: On-demand (Pay per request)
- **TTL**: Enabled on ttl attribute

### Lambda Function
- **Name**: costguard-cost-data-handler
- **Runtime**: Python 3.11
- **Memory**: 256 MB
- **Timeout**: 30 seconds
- **Handler**: lambda_handler.handler

### API Gateway
- **Name**: costguard-cost-data-api
- **Stage**: prod
- **Endpoints**:
  - POST /api/cost-data/fetch - Fetch and store cost data
  - GET /api/cost-data - Query stored cost data
- **Authentication**: API Key required
- **Throttling**: 10 requests/second, 20 burst

### IAM Permissions
- Cost Explorer: ce:GetCostAndUsage, ce:GetDimensionValues
- DynamoDB: PutItem, GetItem, Query, BatchWriteItem
- CloudWatch Logs: CreateLogGroup, CreateLogStream, PutLogEvents

## Cleanup

To delete all infrastructure:
```bash
cdk destroy
```

Note: The DynamoDB table has a RETAIN removal policy, so it will not be deleted automatically. Delete it manually if needed.

## Cost Considerations

This infrastructure is designed to stay within AWS Free Tier limits:
- DynamoDB: On-demand billing (25 GB storage, 25 WCU, 25 RCU free)
- Lambda: 1M requests and 400,000 GB-seconds free per month
- API Gateway: 1M API calls free for 12 months
- CloudWatch Logs: 5 GB ingestion, 5 GB storage free

Monitor your usage to avoid unexpected charges.
