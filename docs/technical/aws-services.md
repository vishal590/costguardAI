# AWS Services Research & Selection

**Keywords:** AWS, services, Free Tier, Kiro, Bedrock, Bedrock AgentCore, Nova, Strands Agents, Lambda, DynamoDB, S3, CloudFront, Cognito, research, selection, comparison, cost optimization, CostGuard AI, cost management, cost prevention, API Gateway, SNS, Cost Explorer API, Budgets API

## Related Files
- **[../project/ideas.md](../project/ideas.md)** - CostGuard AI project idea and AWS services needed
- **[architecture.md](./architecture.md)** - CostGuard AI architecture using these services
- **[../competition/faq.md](../competition/faq.md)** - FAQ (What AWS resources can I use?)
- **[../submission/requirements.md](../submission/requirements.md)** - Submission requirements
- **[../submission/article-requirements.md](../submission/article-requirements.md)** - Article documentation requirements
- **[../resources/research.md](../resources/research.md)** - General research and references
- **[../resources/best-practices.md](../resources/best-practices.md)** - AWS best practices
- **[../project/planning.md](../project/planning.md)** - CostGuard AI project planning
- **[../INDEX.md](../INDEX.md)** - Master documentation index

---

## AWS Free Tier Requirement

**Critical Requirement:** Your application must use **AWS Free Tier only**, without exceeding free tier limits.

**Judging Note:** Applications are judged on innovation, efficiency, and practical impact—**not computational scale**. Winning applications should be built entirely within Free Tier limits.

## Required Tools

### Kiro
- **Requirement:** Must use Kiro for at least a portion of development
- **Website:** [Kiro.dev](https://kiro.dev/)
- **Purpose:** Agentic IDE for rapid development
- **Integration:** Use Kiro agentic IDE on AWS Free Tier

## Recommended AWS Services

When building your app using Kiro agentic IDE on the AWS Free Tier, you are **encouraged** to explore:

- **Amazon Bedrock** - Foundation models and AI capabilities
- **Amazon Bedrock AgentCore** - Agent development
- **Amazon Nova** - Foundational models
- **Strands Agents** - Agent capabilities

## Selected AWS Services

**Project:** CostGuard AI - AI-powered AWS cost prevention and forecasting platform

### Core Services

#### AWS Lambda
- **Purpose:** Serverless compute for all business logic (cost data fetching, forecasting, prevention, AI advisor)
- **Free Tier:** 1M requests/month, 400,000 GB-seconds compute time
- **Configuration:** Node.js/Python runtime, 128-512 MB memory per function
- **Integration:** Orchestrates all services, triggered by API Gateway and scheduled events
- **Kiro Integration:** Kiro generates Lambda handler code, AWS SDK integration, error handling (70% of Lambda development)
- **Justification:** Serverless, cost-effective, auto-scaling, perfect for Free Tier. No infrastructure management needed.
- **Documentation:** [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- **Code Reference:** Lambda functions: CostDataFetcher, ForecastingEngine, PreventionController, BudgetManager, AIAdvisorHandler, AnomalyDetector
- **Expected Cost:** $0 (within Free Tier)

#### Amazon API Gateway
- **Purpose:** REST API layer for frontend to backend communication
- **Free Tier:** 1M API calls/month
- **Configuration:** REST API type, API key authentication
- **Integration:** Routes requests to Lambda functions
- **Kiro Integration:** Kiro generates API Gateway integration code and request/response handling
- **Justification:** Managed API layer, scales automatically, Free Tier sufficient for MVP
- **Documentation:** [AWS API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- **Expected Cost:** $0 (within Free Tier)

#### Amazon DynamoDB
- **Purpose:** NoSQL database for user preferences, cached forecasts, budget settings, alert history
- **Free Tier:** 25 GB storage, 25 read capacity units, 25 write capacity units
- **Configuration:** On-demand billing, single table design with sparse indexes
- **Integration:** Lambda functions read/write data, TTL for old data
- **Kiro Integration:** Kiro generates DynamoDB client code and query patterns
- **Justification:** Serverless, auto-scaling, no capacity planning, Free Tier sufficient
- **Documentation:** [AWS DynamoDB Documentation](https://docs.aws.amazon.com/dynamodb/)
- **Tables:** UserSettings, Forecasts, Budgets, Alerts
- **Expected Cost:** $0 (within Free Tier)

### AI/ML Services

#### Amazon Bedrock (Nova Models)
- **Purpose:** AI models for cost forecasting and conversational cost advisor
- **Free Tier:** Check current Bedrock Free Tier (typically includes some model invocations)
- **Use Case:** 
  - Cost forecasting: Predicts future AWS costs using ML models (Nova Pro/Lite)
  - Conversational AI: Natural language cost advisor answering user questions (Nova)
- **Alternatives Considered:** Amazon SageMaker (too complex, requires model training), External AI APIs (not AWS-native)
- **Why Selected:** Managed service, no model training needed, Nova models optimized for AWS, cost-effective, Free Tier available
- **Documentation:** [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- **Kiro Integration:** Kiro generates Bedrock client code, prompt templates, and response parsing logic (80% of Bedrock integration)
- **Expected Cost:** $0 (within Free Tier limits)

#### AWS Cost Explorer API
- **Purpose:** Programmatic access to AWS cost and usage data
- **Free Tier:** Free (data retrieval only, no charges for API calls)
- **Use Case:** Fetch historical cost data (12 months) for forecasting and analysis
- **Justification:** Required for cost data access, free API calls
- **Documentation:** [AWS Cost Explorer API Documentation](https://docs.aws.amazon.com/cost-management/latest/APIReference/)
- **Kiro Integration:** Kiro generates Cost Explorer API client code and data processing logic
- **Expected Cost:** $0 (free API access)

#### AWS Budgets API
- **Purpose:** Programmatic budget management and monitoring
- **Free Tier:** 2 budgets per account (free)
- **Use Case:** Create/update budgets programmatically, monitor budget thresholds
- **Justification:** Enables automated budget protection and budget guard system
- **Documentation:** [AWS Budgets API Documentation](https://docs.aws.amazon.com/cost-management/latest/APIReference/)
- **Kiro Integration:** Kiro generates Budgets API integration code
- **Expected Cost:** $0 (within Free Tier)

#### Amazon SNS (Simple Notification Service)
- **Purpose:** Send alerts and notifications (budget thresholds, anomalies, summaries)
- **Free Tier:** 1M publishes, 100 deliveries/month
- **Use Case:** Email/SMS alerts for cost anomalies, budget warnings, daily summaries
- **Justification:** Reliable notification delivery, Free Tier sufficient
- **Documentation:** [AWS SNS Documentation](https://docs.aws.amazon.com/sns/)
- **Kiro Integration:** Kiro generates SNS publish code and notification templates
- **Expected Cost:** $0 (within Free Tier)

#### Amazon S3
- **Purpose:** Static frontend hosting and file storage (cost reports, exports)
- **Free Tier:** 5 GB storage, 20,000 GET requests/month
- **Use Case:** Host React/Next.js frontend, store cost reports
- **Justification:** Cost-effective storage and hosting, Free Tier sufficient
- **Documentation:** [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- **Expected Cost:** $0 (within Free Tier)

#### AWS IAM
- **Purpose:** Security and permissions management
- **Free Tier:** Always free
- **Use Case:** IAM roles for Lambda functions, API access permissions
- **Justification:** Security requirement, always free
- **Documentation:** [AWS IAM Documentation](https://docs.aws.amazon.com/iam/)
- **Expected Cost:** $0 (always free)

### Infrastructure Services

#### [Infrastructure Service Name]
[Same structure as above]

## Service Comparison

### [Service Category] Comparison

| Service | Pros | Cons | Free Tier | Selected? |
|---------|------|------|-----------|-----------|
| [Service A] | [Pros] | [Cons] | [Details] | Yes/No |
| [Service B] | [Pros] | [Cons] | [Details] | Yes/No |

## Free Tier Utilization

| Service | Free Tier Limit | Expected Usage | Within Limit? | Monitoring Plan |
|---------|----------------|----------------|---------------|-----------------|
| [Service 1] | [Limit] | [Usage] | Yes/No | [How to monitor] |
| [Service 2] | [Limit] | [Usage] | Yes/No | [How to monitor] |

## Service Integration

### Integration Patterns
- [Pattern 1]: [Description]
- [Pattern 2]: [Description]

### Service Dependencies
```
[Service A] → [Service B] → [Service C]
```

### Kiro Integration
- [How Kiro integrates with selected services]
- [Kiro workflow with AWS services]

## Cost Estimates

| Service | Estimated Monthly Cost | Notes |
|---------|----------------------|-------|
| [Service 1] | $0 | Within Free Tier |
| [Service 2] | $0 | Within Free Tier |

**Total Expected Cost:** $0 (all within Free Tier)

## Resource Optimization Strategies

**For Builder Center Article:** Must document resource optimization strategies

### Strategies
1. [Strategy 1]: [Description]
2. [Strategy 2]: [Description]
3. [Strategy 3]: [Description]

### Monitoring
- [How to monitor usage]
- [Alerts setup]
- [Cost tracking]

## Research Notes

### [Service Name] Research
- **Use Cases:** [Use cases found]
- **Best Practices:** [Best practices]
- **Limitations:** [Limitations to be aware of]
- **Free Tier Details:** [Detailed Free Tier information]
- **References:** [Links to resources]

## Documentation for Article

**Required for Builder Center Article:**
- List of AWS services used
- Brief justification for each service
- Resource optimization strategies
- Expected running costs

See [../submission/article-requirements.md](../submission/article-requirements.md) for article requirements.

---

## See Also

- **[../project/ideas.md](../project/ideas.md)** - CostGuard AI project idea and AWS services needed
- **[architecture.md](./architecture.md)** - CostGuard AI architecture using these services
- **[../submission/requirements.md](../submission/requirements.md)** - Submission requirements
- **[../submission/article-requirements.md](../submission/article-requirements.md)** - Article requirements
- **[../resources/research.md](../resources/research.md)** - General research
- **[../resources/best-practices.md](../resources/best-practices.md)** - AWS best practices
- **[../project/planning.md](../project/planning.md)** - CostGuard AI project planning
- **[../INDEX.md](../INDEX.md)** - Master documentation index
