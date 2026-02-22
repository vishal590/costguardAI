# CostGuard Infrastructure

This directory contains all infrastructure-as-code configurations for the CostGuard system (Phases 1, 1.5, 2, and 3).

## Files

### Configuration Files (JSON)
- `dynamodb_tables.json` - DynamoDB table definitions (4 tables)
- `iam_permissions.json` - IAM role and policy definitions
- `lambda_environment.json` - Lambda environment variables and configuration
- `sns_topics.json` - SNS topic definitions and message formats
- `api_gateway.json` - API Gateway route definitions
- `eventbridge_schedule.json` - EventBridge schedule configuration

### CDK Infrastructure (Python)
- `cdk_stack.py` - Main CDK stack defining all infrastructure
- `app.py` - CDK app entry point
- `requirements.txt` - Python dependencies for CDK

## Deployment

### Prerequisites
1. AWS CLI configured with appropriate credentials
2. AWS CDK CLI installed: `npm install -g aws-cdk`
3. Python 3.11+ installed

### CDK Deployment Steps

1. Install CDK dependencies:
```bash
cd infrastructure
pip install -r requirements.txt
```

2. Bootstrap CDK (first time only):
```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

3. Synthesize CloudFormation template:
```bash
cdk synth
```

4. Deploy the stack:
```bash
cdk deploy
```

5. After deployment, subscribe to SNS topics:
```bash
aws sns subscribe --topic-arn <WARNINGS_TOPIC_ARN> --protocol email --notification-endpoint your-email@example.com
aws sns subscribe --topic-arn <ACTIONS_TOPIC_ARN> --protocol email --notification-endpoint your-email@example.com
aws sns subscribe --topic-arn <ERRORS_TOPIC_ARN> --protocol email --notification-endpoint your-email@example.com
```

### Manual Deployment (Alternative)

If not using CDK, you can deploy resources manually using the JSON configuration files:

1. **DynamoDB Tables**: Use `dynamodb_tables.json` with AWS CLI or Console
2. **IAM Roles**: Use `iam_permissions.json` to create roles and policies
3. **Lambda Function**: Deploy with environment variables from `lambda_environment.json`
4. **SNS Topics**: Create topics using `sns_topics.json`
5. **API Gateway**: Configure routes using `api_gateway.json`
6. **EventBridge**: Create schedule using `eventbridge_schedule.json`

## Infrastructure Components

### DynamoDB Tables (6 total)
1. `costguard-cost-data` - Historical cost data (Phase 1)
2. `costguard-forecast-cache` - AI forecast cache (Phase 2)
3. `costguard-prevention-config` - Prevention configuration (Phase 3)
4. `costguard-resource-inventory` - Resource inventory (Phase 3)
5. `costguard-prevention-audit` - Action audit log (Phase 3)
6. `costguard-approval-requests` - Approval tracking (Phase 3)

### Lambda Function
- **Name**: CostGuardLambda
- **Runtime**: Python 3.11
- **Timeout**: 15 minutes
- **Memory**: 512 MB
- **Handler**: src.lambda_handler.handler

### API Gateway Endpoints
- **Phase 1**: `/api/fetch`, `/api/cost-data`
- **Phase 1.5**: `/api/cost-estimation/current`, `/api/cost-estimation/service/{service}`
- **Phase 2**: `/api/cost-forecast`, `/api/cost-forecast/service/{service}`
- **Phase 3**: `/api/prevention/*` (6 endpoints)

### SNS Topics (3)
1. `costguard-prevention-warnings` - Budget threshold warnings
2. `costguard-prevention-actions` - Prevention action notifications
3. `costguard-prevention-errors` - Error notifications

### EventBridge Schedule
- **Rule**: costguard-budget-monitor
- **Schedule**: Every 5 minutes
- **Target**: CostGuardLambda

## Safety Configuration

The infrastructure is deployed with safety-first defaults:

- `PREVENTION_ENABLED=false` - Prevention system disabled by default
- `DRY_RUN_MODE=true` - Actions are logged but not executed
- `APPROVAL_REQUIRED=true` - All actions require approval

### Enabling Prevention System

1. Monitor dry run reports for 24-48 hours
2. Validate safety mechanisms are working
3. Update Lambda environment variables:
```bash
aws lambda update-function-configuration \
  --function-name CostGuardLambda \
  --environment Variables={PREVENTION_ENABLED=true,DRY_RUN_MODE=false}
```

## Free Tier Compliance

All infrastructure stays within AWS Free Tier limits:

- **DynamoDB**: 6 tables with PAY_PER_REQUEST billing (within 25 GB free tier)
- **Lambda**: ~8,640 invocations/month (within 1M free tier)
- **API Gateway**: Estimated usage within 1M requests/month
- **SNS**: ~348 messages/month (within 1M publishes/month)
- **EventBridge**: Rules are free, invocations count toward Lambda free tier
- **CloudWatch**: Logs within free tier limits

## Monitoring

After deployment, monitor:

1. **CloudWatch Logs**: `/aws/lambda/CostGuardLambda`
2. **DynamoDB Metrics**: Table read/write capacity
3. **Lambda Metrics**: Invocations, errors, duration
4. **API Gateway Metrics**: Request count, latency, errors
5. **SNS Metrics**: Messages published, delivery success

## Cleanup

To remove all infrastructure:

```bash
cdk destroy
```

Or manually delete resources in reverse order:
1. EventBridge rule
2. API Gateway
3. Lambda function
4. SNS topics
5. DynamoDB tables
6. IAM roles

## Notes

- All resources are tagged with `Project: CostGuard` and `Phase: X`
- DynamoDB tables use `RETAIN` removal policy to prevent accidental data loss
- Lambda has CloudWatch Logs retention set to 1 week
- API Gateway has CORS enabled for all origins (restrict in production)
- Resource management actions include conditions to protect production resources
