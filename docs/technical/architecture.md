# Technical Architecture

**Keywords:** architecture, design, AWS, infrastructure, services, system design, components, integration, scalability, security, Kiro, Free Tier, CostGuard AI, serverless, Lambda, API Gateway, DynamoDB, Bedrock, cost management, cost prevention, cost forecasting, AI advisor, predictive analytics, automated prevention, microservices, event-driven

## Related Files
- **[phase1-kiro-spec.md](./phase1-kiro-spec.md)** - 🚀 **Phase 1 Kiro Specification - Ready for code generation**
- **[../submission/SEMI-FINALIST-PHASE.md](../submission/SEMI-FINALIST-PHASE.md)** - 🚀 **CURRENT PHASE - Semi-finalist building & article requirements**
- **[../project/ideas.md](../project/ideas.md)** - CostGuard AI project idea and concept
- **[aws-services.md](./aws-services.md)** - AWS services used in CostGuard AI architecture
- **[api-design.md](./api-design.md)** - CostGuard AI API specifications and endpoints
- **[database-design.md](./database-design.md)** - DynamoDB schema for CostGuard AI
- **[development-notes.md](./development-notes.md)** - Development progress and implementation notes
- **[../submission/requirements.md](../submission/requirements.md)** - Requirements driving architecture
- **[../submission/FORM-FIELD-RESPONSES.md](../submission/FORM-FIELD-RESPONSES.md)** - Original submission with game plan
- **[../project/planning.md](../project/planning.md)** - CostGuard AI project planning and timeline
- **[../resources/best-practices.md](../resources/best-practices.md)** - AWS best practices for CostGuard AI
- **[../INDEX.md](../INDEX.md)** - Master documentation index

---

## Architecture Overview

**Architecture Type:** Serverless Microservices  
**Primary AWS Services:** Lambda, API Gateway, DynamoDB, Bedrock, Cost Explorer API, Budgets API, SNS, S3  
**Kiro Integration:** ~65% of development using Kiro for Lambda functions, AWS SDK integration, Bedrock integration, testing  
**Design Principles:** 
- Serverless-first (cost-effective, scalable)
- Event-driven architecture
- AI-powered decision making
- Free Tier compliance
- Security by design
- Microservices for modularity
**Free Tier Compliance:** All services configured to stay within Free Tier limits, monitoring in place

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Static Web App (React/Next.js)                          │  │
│  │  Hosted on: S3 + CloudFront (optional)                   │  │
│  └──────────────────────┬───────────────────────────────────┘  │
└─────────────────────────┼─────────────────────────────────────┘
                          │ HTTPS
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Amazon API Gateway (REST API)                          │  │
│  │  Endpoints: /forecast, /prevent, /advisor, /budgets      │  │
│  └──────────────────────┬───────────────────────────────────┘  │
└─────────────────────────┼─────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Lambda Functions Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Cost Data   │  │ Forecasting  │  │ Prevention   │          │
│  │ Fetcher     │  │ Engine       │  │ Controller   │          │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                │                 │                   │
│  ┌──────┴──────┐  ┌──────┴───────┐  ┌──────┴───────┐          │
│  │ Budget      │  │ AI Advisor   │  │ Anomaly      │          │
│  │ Manager     │  │ Handler      │  │ Detector     │          │
│  └─────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────┬─────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Bedrock    │  │ Cost Explorer│  │   DynamoDB   │
│  (Nova AI)   │  │     API      │  │   (Storage)  │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Services Integration                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Budgets API  │  │   SNS        │  │   S3        │          │
│  │ (Budget      │  │ (Alerts)     │  │ (Reports)   │          │
│  │  Guards)     │  │              │  │             │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ EC2/S3 APIs  │  │   IAM        │                            │
│  │ (Auto-stop)  │  │ (Security)   │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Frontend
- **Technology:** React/Next.js (TypeScript)
- **Hosting:** Amazon S3 (static hosting) + CloudFront (optional, for better performance)
- **Description:** Single-page application providing dashboard, cost forecasts, budget management, and AI advisor interface
- **Free Tier:** S3: 5 GB storage, 20,000 GET requests/month
- **Features:**
  - Near-real-time cost estimation dashboard (updates every 5-15 minutes using CloudWatch metrics)
  - Interactive forecast charts
  - Budget configuration UI
  - Conversational AI advisor chat interface
  - Alert management

### Backend/API
- **Technology:** AWS Lambda (Node.js/Python)
- **Hosting:** AWS Lambda (serverless)
- **Description:** Serverless API layer handling all business logic, data processing, and AWS service integration
- **Free Tier:** 1M requests/month, 400,000 GB-seconds compute
- **Lambda Functions:**
  1. **CostDataFetcher** - Fetches cost data from Cost Explorer API
  2. **ForecastingEngine** - Generates cost forecasts using Bedrock
  3. **PreventionController** - Manages automated cost prevention
  4. **BudgetManager** - Handles budget creation and monitoring
  5. **AIAdvisorHandler** - Processes conversational queries
  6. **AnomalyDetector** - Detects cost anomalies
- **See:** [api-design.md](./api-design.md)

### AI/ML Services
- **Service:** Amazon Bedrock (Nova models)
- **Purpose:** 
  - Cost forecasting: Predicts future AWS costs using ML models
  - Conversational AI: Natural language cost advisor
- **Integration:** Lambda functions invoke Bedrock APIs with prompts containing historical cost data
- **Kiro Integration:** Kiro generates Bedrock client code, prompt templates, and response parsing logic
- **Free Tier:** Check current Bedrock Free Tier (typically includes some model invocations)
- **Models Used:**
  - Nova Pro/Lite for cost forecasting
  - Nova for conversational advisor

### Data Storage
- **Database:** Amazon DynamoDB
- **Purpose:** 
  - User preferences and configurations
  - Cached forecast results
  - Historical cost snapshots
  - Budget settings
  - Alert configurations
- **Free Tier:** 25 GB storage, 25 read capacity units, 25 write capacity units
- **Tables:**
  - `UserSettings` - User preferences and configurations
  - `Forecasts` - Cached forecast results
  - `Budgets` - Budget configurations
  - `Alerts` - Alert history
- **See:** [database-design.md](./database-design.md)

### Authentication & Authorization
- **Service:** AWS IAM (for Lambda permissions) + API Key (for frontend)
- **Description:** 
  - IAM roles for Lambda functions to access AWS services
  - API keys for frontend authentication (simple approach for MVP)
  - Future: Could use Cognito for user management
- **Free Tier:** IAM is always free

### Notification Service
- **Service:** Amazon SNS (Simple Notification Service)
- **Purpose:** Send alerts for budget thresholds, anomalies, and daily summaries
- **Free Tier:** 1M publishes, 100 deliveries/month
- **Channels:** Email, SMS (optional)

### File Storage
- **Service:** Amazon S3
- **Purpose:** 
  - Host static frontend files
  - Store cost reports/exports
  - Backup DynamoDB data
- **Free Tier:** 5 GB storage, 20,000 GET requests/month

### Kiro Integration
- **Usage:** Kiro used for ~65% of development
- **Portion:** 
  - Lambda function development (70%)
  - AWS SDK integration code (80%)
  - Bedrock integration (80%)
  - Testing and documentation (90%)
- **Workflow:** 
  1. Developer provides spec to Kiro
  2. Kiro generates Lambda handler, AWS SDK code, tests
  3. Developer reviews, customizes, and deploys
- **Key Benefits:** Speed, AWS best practices, consistency

### Other Components
- **API Gateway:** REST API endpoints for frontend
- **Cost Explorer API:** Fetch AWS cost data
- **Budgets API:** Manage AWS budgets programmatically
- **EC2/S3 APIs:** For automated resource management (auto-shutdown)

## AWS Services Used

| Service | Purpose | Configuration | Free Tier Usage |
|---------|---------|---------------|-----------------|
| **Lambda** | Serverless compute for all business logic | Node.js/Python runtime, 128-512 MB memory | 1M requests/month, 400K GB-seconds |
| **API Gateway** | REST API for frontend | REST API type, API key authentication | 1M API calls/month |
| **DynamoDB** | NoSQL database for user data | On-demand billing, single table design | 25 GB storage, 25 RCU/WCU |
| **Bedrock** | AI models for forecasting & advisor | Nova Pro/Lite models | Check current Free Tier |
| **Cost Explorer API** | Fetch AWS cost data | Programmatic API access | Free (data retrieval) |
| **Budgets API** | Manage AWS budgets | Programmatic budget management | 2 budgets free |
| **SNS** | Send alerts and notifications | Email/SMS topics | 1M publishes, 100 deliveries |
| **S3** | Static hosting & file storage | Standard storage class | 5 GB storage, 20K GET requests |
| **IAM** | Security and permissions | Roles for Lambda, policies | Always free |

**Detailed service information:** See [aws-services.md](./aws-services.md)

## Data Flow

### Cost Forecasting Flow
1. **User Request:** Frontend calls `/api/forecast` endpoint
2. **API Gateway:** Routes request to `ForecastingEngine` Lambda
3. **Cost Data Fetch:** Lambda calls Cost Explorer API to get historical data (12 months)
4. **Data Processing:** Lambda processes and formats cost data
5. **Bedrock Invocation:** Lambda sends cost data to Bedrock Nova model with forecasting prompt
6. **AI Processing:** Bedrock generates cost forecast (30-day prediction)
7. **Storage:** Forecast result cached in DynamoDB
8. **Response:** Lambda returns forecast to frontend via API Gateway

### Automated Prevention Flow
1. **Scheduled Trigger:** CloudWatch Events triggers `PreventionController` Lambda (every 5-15 minutes)
2. **Budget Check:** Lambda calls Budgets API to check current spending vs. thresholds
3. **Cost Analysis:** Lambda fetches cost estimates from CloudWatch Metrics (near-real-time) and historical data from Cost Explorer API
4. **Decision Logic:** If budget threshold reached (e.g., 90%), trigger prevention actions
5. **Safety Checks:** Lambda verifies resource tags (e.g., never touch "production"), checks idle status, runs dry-run mode
6. **Resource Management:** Lambda calls EC2/RDS/EBS/Lambda/S3/DynamoDB/SNS/SQS APIs to stop/terminate idle resources across 20+ services
7. **Notification:** Lambda publishes to SNS to alert user before/after actions
8. **Logging:** All actions logged to DynamoDB for audit and rollback capability

### AI Advisor Flow
1. **User Query:** User asks question in frontend chat interface
2. **API Request:** Frontend sends query to `/api/advisor` endpoint
3. **Lambda Processing:** `AIAdvisorHandler` Lambda receives query
4. **Context Fetch:** Lambda retrieves relevant cost data from Cost Explorer API
5. **Bedrock Invocation:** Lambda sends query + cost context to Bedrock Nova
6. **AI Response:** Bedrock generates natural language explanation
7. **Response:** Lambda returns explanation to frontend

### Near-Real-Time Cost Estimation Flow
1. **Scheduled Trigger:** CloudWatch Events triggers `CostEstimator` Lambda (every 5-15 minutes)
2. **Metrics Fetch:** Lambda calls CloudWatch Metrics API to get usage data (EC2 CPU, Lambda invocations, S3 requests, DynamoDB read/write units, etc.)
3. **Cost Estimation:** Lambda calculates estimated costs using usage × AWS pricing models
4. **Anomaly Detection:** Lambda compares estimated costs to historical patterns, detects spikes
5. **Storage:** Cost estimates stored in DynamoDB for dashboard display
6. **Alert:** If anomaly detected, Lambda publishes to SNS immediately (minutes vs. 24hr billing delay)
7. **Prevention:** Optionally triggers prevention actions if severe

### Anomaly Detection Flow (Historical)
1. **Scheduled Check:** CloudWatch Events triggers `AnomalyDetector` Lambda (hourly)
2. **Cost Fetch:** Lambda gets historical cost data from Cost Explorer API (24hr delay)
3. **Pattern Analysis:** Lambda analyzes spending patterns using ML logic
4. **Anomaly Detection:** Identifies unusual spending spikes or patterns
5. **Alert:** If anomaly detected, Lambda publishes to SNS
6. **Prevention:** Optionally triggers prevention actions if severe

## Security Architecture

- **Authentication:** 
  - API Gateway API keys for frontend authentication
  - IAM roles for Lambda functions (no hardcoded credentials)
  - Future: AWS Cognito for user management (if needed)
- **Authorization:** 
  - IAM policies restrict Lambda access to only required AWS services
  - Least privilege principle applied
  - API Gateway authorizers (if implementing user auth)
- **Data Encryption:** 
  - DynamoDB encryption at rest (enabled by default)
  - S3 encryption at rest (enabled)
  - HTTPS for all API communications (API Gateway)
  - Data in transit encrypted via TLS
- **Network Security:** 
  - All Lambda functions in VPC (optional, for enhanced security)
  - API Gateway with HTTPS only
  - No public internet exposure for backend services
- **Free Tier Security:** 
  - All security features available in Free Tier
  - IAM is always free
  - Encryption included in Free Tier

## Scalability Considerations

- **Horizontal Scaling:** 
  - Lambda automatically scales to handle concurrent requests
  - API Gateway scales automatically
  - DynamoDB on-demand mode scales automatically
  - No manual scaling required
- **Vertical Scaling:** 
  - Lambda memory can be adjusted (128 MB - 10 GB)
  - For Free Tier, keep within 400K GB-seconds limit
- **Load Handling:** 
  - API Gateway throttling: 10,000 requests/second (default)
  - Lambda concurrency limits: 1,000 concurrent executions (default)
  - DynamoDB on-demand handles any traffic pattern
- **Free Tier Limits:** 
  - Monitor usage via CloudWatch
  - Implement request throttling if approaching limits
  - Cache frequently accessed data in DynamoDB
  - Optimize Lambda execution time to stay within limits
  - Use DynamoDB on-demand to avoid capacity planning

## Cost Optimization

- **Free Tier Usage:** 
  - All services configured to use Free Tier
  - Lambda: 1M requests/month (sufficient for MVP)
  - DynamoDB: 25 GB storage (more than enough)
  - API Gateway: 1M calls/month (sufficient)
  - S3: 5 GB storage (sufficient for static site)
  - SNS: 1M publishes (sufficient for alerts)
- **Cost Estimates:** $0 (all within Free Tier)
- **Optimization Strategies:** 
  1. **Lambda Optimization:**
     - Right-size memory allocation (128-256 MB for most functions)
     - Optimize code execution time
     - Use Lambda layers for shared code
     - Implement connection pooling for API calls
  2. **DynamoDB Optimization:**
     - Use on-demand billing (no capacity planning)
     - Implement TTL for old data
     - Use sparse indexes
     - Batch operations where possible
  3. **API Gateway Optimization:**
     - Enable caching for frequently accessed endpoints
     - Use compression for responses
  4. **S3 Optimization:**
     - Use S3 lifecycle policies (if needed)
     - Enable compression for static assets
  5. **Bedrock Optimization:**
     - Cache forecast results in DynamoDB
     - Batch similar queries
     - Use appropriate model size (Nova Lite for simple queries)
- **Monitoring:** 
  - CloudWatch metrics for all services
  - Set up billing alerts in AWS Budgets
  - Monitor Lambda invocations and duration
  - Track DynamoDB read/write units
  - Monitor API Gateway request count

## Deployment Architecture

- **Environment:** 
  - **Development:** Local development with AWS SAM or CDK
  - **Production:** Single environment (Free Tier constraint)
  - Future: Separate dev/prod if scaling beyond Free Tier
- **CI/CD:** 
  - **Option 1:** AWS SAM CLI for local development and deployment
  - **Option 2:** AWS CDK for infrastructure as code
  - **Option 3:** Manual deployment via AWS Console (for MVP)
  - Future: GitHub Actions or AWS CodePipeline for automated CI/CD
- **Infrastructure as Code:** 
  - **Primary:** AWS CDK (TypeScript/Python)
  - **Alternative:** AWS SAM templates
  - **Benefits:** Version control, repeatable deployments, documentation
- **Kiro Deployment:** 
  - Kiro generates Lambda function code
  - Developer reviews and commits to repository
  - CDK/SAM deploys infrastructure and code
  - Kiro-generated tests run in CI/CD pipeline

## Design Decisions

### Decision 1: Serverless Architecture
**Context:** Need cost-effective, scalable architecture within Free Tier  
**Options:** 
  1. Serverless (Lambda, API Gateway, DynamoDB)
  2. Container-based (ECS, Fargate)
  3. EC2-based (traditional servers)
**Decision:** Serverless architecture  
**Rationale:** 
  - Zero infrastructure management
  - Pay only for what you use
  - Automatic scaling
  - Free Tier provides generous limits
  - Aligns with AWS best practices
**Free Tier Impact:** All services have generous Free Tier limits

### Decision 2: DynamoDB vs RDS
**Context:** Need database for user data and caching  
**Options:** 
  1. DynamoDB (NoSQL, serverless)
  2. RDS (PostgreSQL/MySQL, managed)
  3. S3 (object storage)
**Decision:** DynamoDB  
**Rationale:** 
  - Serverless (no server management)
  - Scales automatically
  - Free Tier: 25 GB (sufficient for MVP)
  - Fast read/write performance
  - On-demand billing (no capacity planning)
**Free Tier Impact:** DynamoDB Free Tier sufficient for MVP needs

### Decision 3: Bedrock vs SageMaker
**Context:** Need AI/ML for forecasting and conversational AI  
**Options:** 
  1. Amazon Bedrock (managed foundation models)
  2. Amazon SageMaker (build custom models)
  3. External AI APIs (OpenAI, etc.)
**Decision:** Amazon Bedrock with Nova models  
**Rationale:** 
  - No model training needed (faster development)
  - Managed service (no infrastructure)
  - Nova models optimized for AWS use cases
  - Cost-effective (pay per token)
  - Free Tier available
**Free Tier Impact:** Bedrock Free Tier sufficient for MVP usage

### Decision 4: API Gateway vs AppSync
**Context:** Need API layer for frontend  
**Options:** 
  1. API Gateway (REST API)
  2. AppSync (GraphQL)
  3. Direct Lambda URLs
**Decision:** API Gateway REST API  
**Rationale:** 
  - Simpler to implement
  - Better Free Tier limits (1M requests)
  - REST is more familiar
  - Easier integration with frontend
**Free Tier Impact:** API Gateway Free Tier sufficient

### Decision 5: Kiro Integration
**Context:** Required to use Kiro for at least portion of development  
**Decision:** Use Kiro for ~65% of development, focusing on:
  - Lambda function development (70%)
  - AWS SDK integration (80%)
  - Bedrock integration (80%)
  - Testing and documentation (90%)
**Rationale:** 
  - Kiro excels at AWS service integration
  - Generates boilerplate code quickly
  - Ensures AWS best practices
  - Speeds up development significantly
  - Auto-generates tests and documentation
**Portion:** ~65% of total development

---

## See Also

- **[../project/ideas.md](../project/ideas.md)** - CostGuard AI project idea, features, and market impact
- **[aws-services.md](./aws-services.md)** - Detailed AWS services for CostGuard AI (Lambda, Bedrock, DynamoDB, etc.)
- **[api-design.md](./api-design.md)** - CostGuard AI API endpoints and specifications
- **[database-design.md](./database-design.md)** - DynamoDB tables and data models for CostGuard AI
- **[development-notes.md](./development-notes.md)** - CostGuard AI development progress and notes
- **[../submission/requirements.md](../submission/requirements.md)** - Submission requirements (Kiro documentation, Free Tier)
- **[../project/planning.md](../project/planning.md)** - CostGuard AI development timeline and milestones
- **[../resources/best-practices.md](../resources/best-practices.md)** - AWS best practices for serverless architecture
- **[../competition/tracks.md](../competition/tracks.md)** - Commercial Potential track (selected track)
- **[../INDEX.md](../INDEX.md)** - Master documentation index
