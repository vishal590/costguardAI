# CostGuard AI - Quick Reference Guide

**Last Updated:** February 2026  
**Purpose:** Fast access to commonly needed documentation

---

## 🚀 I Need To...

### Get Started
- **Install & Deploy:** [README.md](../README.md#getting-started)
- **Understand Architecture:** [Architecture](./technical/architecture.md)
- **See API Examples:** [API_EXAMPLES.md](./API_EXAMPLES.md)

### Use the API
- **Phase 1 (Historical):** [API Examples - Phase 1](./API_EXAMPLES.md#phase-1-historical-cost-data)
- **Phase 1.5 (Real-Time):** [API Examples - Phase 1.5](./API_EXAMPLES.md#phase-15-near-real-time-cost-estimation)
- **Phase 2 (Forecasting):** [API Examples - Phase 2](./API_EXAMPLES.md#phase-2-ai-powered-cost-forecasting)
- **Phase 3 (Prevention):** [API Examples - Phase 3](./API_EXAMPLES.md#phase-3-automated-cost-prevention)
- **Phase 4 (AI Advisor):** [API Examples - Phase 4](./API_EXAMPLES.md#phase-4-ai-cost-advisor)
- **Phase 5 (Multi-Account):** [Phase 5 API Docs](./technical/phase5-multi-account/API_DOCUMENTATION.md)

### Deploy
- **Phase 1:** [Phase 1 README](./technical/phase1-cost-pipeline/README.md#deployment)
- **Phase 1.5:** [Infrastructure Updates](./technical/phase1.5-near-realtime/infrastructure-updates.md)
- **Phase 2:** [Infrastructure Updates](./technical/phase2-ai-forecasting/infrastructure-updates.md)
- **Phase 3:** [Infrastructure Updates](./technical/phase3-automated-prevention/infrastructure-updates.md)
- **Phase 4:** [Deployment Checklist](../DEPLOYMENT_CHECKLIST.md)
- **Phase 5:** [Deployment Scripts](../DEPLOYMENT_SCRIPTS.md)

### Troubleshoot
- **Phase 1 Issues:** [Phase 1 README - Troubleshooting](./technical/phase1-cost-pipeline/README.md#troubleshooting)
- **Phase 1.5 Issues:** [Phase 1.5 README - Troubleshooting](./technical/phase1.5-near-realtime/README.md#troubleshooting)
- **Phase 2 Issues:** [Phase 2 README - Troubleshooting](./technical/phase2-ai-forecasting/README.md#troubleshooting)
- **Phase 3 Issues:** [Phase 3 README - Troubleshooting](./technical/phase3-automated-prevention/README.md#troubleshooting)
- **Phase 4 Issues:** [Phase 4 README - Troubleshooting](./technical/phase4-ai-advisor/README.md#troubleshooting)

### Understand Costs
- **Cost Breakdown:** [README - Cost Optimization](../README.md#cost-optimization)
- **Free Tier Usage:** [AWS Services](./technical/aws-services.md#free-tier)
- **Phase Costs:** [PROJECT_STATUS.md](./PROJECT_STATUS.md#monthly-cost-breakdown)

### Check Status
- **Overall Status:** [PROJECT_STATUS.md](./PROJECT_STATUS.md)
- **Phase 4 Status:** [PHASE4_STATUS.md](./PHASE4_STATUS.md)
- **Test Results:** [PROJECT_STATUS.md - Test Coverage](./PROJECT_STATUS.md#test-coverage)

---

## 📖 By Feature

### Historical Cost Data
- **Overview:** [Phase 1 README](./technical/phase1-cost-pipeline/README.md)
- **API:** [API Examples - Phase 1](./API_EXAMPLES.md#phase-1-historical-cost-data)
- **Design:** [Phase 1 Specification](./technical/phase1-cost-pipeline/specification.md)

### Real-Time Estimation
- **Overview:** [Phase 1.5 README](./technical/phase1.5-near-realtime/README.md)
- **API:** [API Examples - Phase 1.5](./API_EXAMPLES.md#phase-15-near-real-time-cost-estimation)
- **Design:** [Phase 1.5 Design](./technical/phase1.5-near-realtime/design.md)

### AI Forecasting
- **Overview:** [Phase 2 README](./technical/phase2-ai-forecasting/README.md)
- **API:** [API Examples - Phase 2](./API_EXAMPLES.md#phase-2-ai-powered-cost-forecasting)
- **Design:** [Phase 2 Specification](./technical/phase2-ai-forecasting/specification.md)
- **Bedrock Setup:** [Infrastructure Updates](./technical/phase2-ai-forecasting/infrastructure-updates.md)

### Automated Prevention
- **Overview:** [Phase 3 README](./technical/phase3-automated-prevention/README.md)
- **API:** [API Examples - Phase 3](./API_EXAMPLES.md#phase-3-automated-cost-prevention)
- **Design:** [Phase 3 Specification](./technical/phase3-automated-prevention/specification.md)
- **EventBridge Setup:** [Infrastructure Updates](./technical/phase3-automated-prevention/infrastructure-updates.md)

### AI Cost Advisor
- **Overview:** [Phase 4 README](./technical/phase4-ai-advisor/README.md)
- **API:** [API Examples - Phase 4](./API_EXAMPLES.md#phase-4-ai-cost-advisor)
- **Design:** [Phase 4 Specification](./technical/phase4-ai-advisor/specification.md)
- **Deployment:** [Deployment Checklist](../DEPLOYMENT_CHECKLIST.md)

### Multi-Account Management
- **Overview:** [Phase 5 README](./technical/phase5-multi-account/README.md)
- **API:** [Phase 5 API Documentation](./technical/phase5-multi-account/API_DOCUMENTATION.md)
- **Cross-Account Setup:** [CROSS_ACCOUNT_SETUP.md](../infrastructure/CROSS_ACCOUNT_SETUP.md)
- **Deployment:** [Deployment Scripts](../DEPLOYMENT_SCRIPTS.md)

### GPU Cost Management
- **Overview:** [Phase 6 User Guide](./user-guide/phase6-user-guide.md)
- **API:** [Phase 6 API Documentation](./api/phase6-api-documentation.md)
- **Deployment:** [Phase 6 Deployment Guide](./deployment/phase6-deployment-guide.md)
- **GPU Tracking:** [GPU Cost Tracking](./user-guide/phase6-user-guide.md#gpu-cost-tracking)
- **Workload Classification:** [Workload Classification](./user-guide/phase6-user-guide.md#workload-classification)
- **Cost-Per-Inference:** [Cost-Per-Inference](./user-guide/phase6-user-guide.md#cost-per-inference)
- **Spot Recommendations:** [Spot Instance Recommendations](./user-guide/phase6-user-guide.md#spot-instance-recommendations)
- **SageMaker Costs:** [SageMaker Cost Tracking](./user-guide/phase6-user-guide.md#sagemaker-cost-tracking)
- **Bedrock Costs:** [Bedrock Cost Tracking](./user-guide/phase6-user-guide.md#bedrock-cost-tracking)

---

## 🔧 By Technology

### AWS Services
- **Cost Explorer:** [AWS Services Guide](./technical/aws-services.md#cost-explorer)
- **CloudWatch:** [AWS Services Guide](./technical/aws-services.md#cloudwatch)
- **Bedrock:** [AWS Services Guide](./technical/aws-services.md#amazon-bedrock)
- **DynamoDB:** [Database Design](./technical/database-design.md)
- **Lambda:** [Architecture](./technical/architecture.md#lambda-functions)
- **API Gateway:** [API Design](./technical/api-design.md)
- **EventBridge:** [AWS Services Guide](./technical/aws-services.md#eventbridge)
- **Organizations:** [Phase 5 README](./technical/phase5-multi-account/README.md#organizations-integration)

### AI/ML
- **Bedrock Integration:** [Architecture - AI](./technical/architecture.md#ai-model-selection)
- **Nova Lite Model:** [AWS Services - Nova](./technical/aws-services.md#nova-lite)
- **Forecasting:** [Phase 2 Design](./technical/phase2-ai-forecasting/design.md#forecasting-engine)
- **NLP:** [Phase 4 Design](./technical/phase4-ai-advisor/design.md#query-processor)
- **Conversational AI:** [Phase 4 README](./technical/phase4-ai-advisor/README.md#conversational-ai)

### Testing
- **Testing Strategy:** [Architecture - Testing](./technical/architecture.md#testing-strategy)
- **Property-Based Testing:** [Best Practices](./resources/best-practices.md#property-based-testing)
- **Test Results:** [PROJECT_STATUS.md - Test Coverage](./PROJECT_STATUS.md#test-coverage)

---

## 📊 By Phase

| Phase | README | API | Design | Deploy | Tests |
|-------|--------|-----|--------|--------|-------|
| **1** | [README](./technical/phase1-cost-pipeline/README.md) | [API](./API_EXAMPLES.md#phase-1-historical-cost-data) | [Spec](./technical/phase1-cost-pipeline/specification.md) | [Deploy](./technical/phase1-cost-pipeline/README.md#deployment) | [Tests](./technical/phase1-cost-pipeline/implementation-summary.md) |
| **1.5** | [README](./technical/phase1.5-near-realtime/README.md) | [API](./API_EXAMPLES.md#phase-15-near-real-time-cost-estimation) | [Design](./technical/phase1.5-near-realtime/design.md) | [Infra](./technical/phase1.5-near-realtime/infrastructure-updates.md) | [Tests](./technical/phase1.5-near-realtime/implementation-summary.md) |
| **2** | [README](./technical/phase2-ai-forecasting/README.md) | [API](./API_EXAMPLES.md#phase-2-ai-powered-cost-forecasting) | [Spec](./technical/phase2-ai-forecasting/specification.md) | [Infra](./technical/phase2-ai-forecasting/infrastructure-updates.md) | [Tests](./technical/phase2-ai-forecasting/implementation-summary.md) |
| **3** | [README](./technical/phase3-automated-prevention/README.md) | [API](./API_EXAMPLES.md#phase-3-automated-cost-prevention) | [Spec](./technical/phase3-automated-prevention/specification.md) | [Infra](./technical/phase3-automated-prevention/infrastructure-updates.md) | [Tests](./technical/phase3-automated-prevention/implementation-summary.md) |
| **4** | [README](./technical/phase4-ai-advisor/README.md) | [API](./API_EXAMPLES.md#phase-4-ai-cost-advisor) | [Spec](./technical/phase4-ai-advisor/specification.md) | [Checklist](../DEPLOYMENT_CHECKLIST.md) | [Tests](./technical/phase4-ai-advisor/implementation-summary.md) |
| **5** | [README](./technical/phase5-multi-account/README.md) | [API Docs](./technical/phase5-multi-account/API_DOCUMENTATION.md) | [Design](../.kiro/specs/multi-account-cost-management/design.md) | [Scripts](../DEPLOYMENT_SCRIPTS.md) | [Tasks](../.kiro/specs/multi-account-cost-management/tasks.md#task-32-run-comprehensive-test-suite) |
| **6** | [User Guide](./user-guide/phase6-user-guide.md) | [API Docs](./api/phase6-api-documentation.md) | [Deployment](./deployment/phase6-deployment-guide.md) | [Deploy](./deployment/phase6-deployment-guide.md) | [Validation](../PHASE6_VALIDATION_REPORT.md) |

---

## 🎯 Common Questions

### "How do I...?"

**...get started quickly?**
1. Read [README.md](../README.md)
2. Follow [Getting Started](../README.md#getting-started)
3. Try [API Examples](./API_EXAMPLES.md)

**...deploy to AWS?**
1. Check [Prerequisites](../README.md#prerequisites)
2. Follow phase-specific deployment guides (see [By Phase](#-by-phase))
3. Verify with [API Examples](./API_EXAMPLES.md)

**...use the AI advisor?**
1. Read [Phase 4 README](./technical/phase4-ai-advisor/README.md)
2. Deploy using [Deployment Checklist](../DEPLOYMENT_CHECKLIST.md)
3. Try [Phase 4 API Examples](./API_EXAMPLES.md#phase-4-ai-cost-advisor)

**...set up multi-account?**
1. Read [Phase 5 README](./technical/phase5-multi-account/README.md)
2. Follow [Cross-Account Setup](../infrastructure/CROSS_ACCOUNT_SETUP.md)
3. Deploy with [Deployment Scripts](../DEPLOYMENT_SCRIPTS.md)

**...track GPU costs?**
1. Read [Phase 6 User Guide](./user-guide/phase6-user-guide.md#gpu-cost-tracking)
2. Check [Phase 6 API Docs](./api/phase6-api-documentation.md#gpu-cost-tracking-endpoints)
3. Deploy with [Phase 6 Deployment Guide](./deployment/phase6-deployment-guide.md)

**...optimize ML workload costs?**
1. Read [Phase 6 User Guide](./user-guide/phase6-user-guide.md)
2. Check [Workload Classification](./user-guide/phase6-user-guide.md#workload-classification)
3. Use [Spot Recommendations](./user-guide/phase6-user-guide.md#spot-instance-recommendations)

**...calculate cost-per-inference?**
1. Read [Cost-Per-Inference Guide](./user-guide/phase6-user-guide.md#cost-per-inference)
2. Check [API Documentation](./api/phase6-api-documentation.md#cost-per-inference-endpoints)
3. See [Real-World Examples](./user-guide/phase6-user-guide.md#real-world-example-2)

**...stop idle GPUs?**
1. Read [GPU Prevention Guide](./user-guide/phase6-user-guide.md#gpu-prevention)
2. Check [Idle GPU Detection](./api/phase6-api-documentation.md#get-idle-gpus)
3. Use [GPU Prevention API](./api/phase6-api-documentation.md#run-gpu-prevention-cycle)

**...understand the architecture?**
1. Read [Architecture Overview](./technical/architecture.md)
2. Review [AWS Services Used](./technical/aws-services.md)
3. Check phase-specific designs (see [By Phase](#-by-phase))

**...check test coverage?**
1. See [PROJECT_STATUS.md - Test Coverage](./PROJECT_STATUS.md#test-coverage)
2. Review phase-specific test results (see [By Phase](#-by-phase))
3. Read [Testing Strategy](./technical/architecture.md#testing-strategy)

**...estimate costs?**
1. Read [Cost Optimization](../README.md#cost-optimization)
2. Check [Monthly Cost Breakdown](./PROJECT_STATUS.md#monthly-cost-breakdown)
3. Review [Free Tier Usage](./technical/aws-services.md#free-tier)

**...find API documentation?**
1. Start with [API_EXAMPLES.md](./API_EXAMPLES.md)
2. Check [API Design](./technical/api-design.md)
3. See phase-specific API docs (see [By Phase](#-by-phase))

---

## 🔍 Search by Keyword

**Cost Management:**
- Historical: [Phase 1](#historical-cost-data)
- Real-Time: [Phase 1.5](#real-time-estimation)
- Forecasting: [Phase 2](#ai-forecasting)
- Prevention: [Phase 3](#automated-prevention)
- Multi-Account: [Phase 5](#multi-account-management)
- GPU Costs: [Phase 6](#gpu-cost-management)

**AI/ML:**
- Bedrock: [AWS Services](./technical/aws-services.md#amazon-bedrock)
- Forecasting: [Phase 2](#ai-forecasting)
- Advisor: [Phase 4](#ai-cost-advisor)
- NLP: [Phase 4 Design](./technical/phase4-ai-advisor/design.md#query-processor)
- GPU Tracking: [Phase 6](#gpu-cost-management)
- Workload Classification: [Phase 6 User Guide](./user-guide/phase6-user-guide.md#workload-classification)
- ML Optimization: [Phase 6 User Guide](./user-guide/phase6-user-guide.md)

**AWS Services:**
- Cost Explorer: [Phase 1](#historical-cost-data)
- CloudWatch: [Phase 1.5](#real-time-estimation)
- Bedrock: [Phase 2](#ai-forecasting), [Phase 4](#ai-cost-advisor)
- EventBridge: [Phase 3](#automated-prevention)
- Organizations: [Phase 5](#multi-account-management)

**Features:**
- Budget Monitoring: [Phase 3](#automated-prevention)
- Idle Detection: [Phase 3](#automated-prevention)
- Conversational AI: [Phase 4](#ai-cost-advisor)
- Cost Allocation: [Phase 5](#multi-account-management)
- Chargeback: [Phase 5](#multi-account-management)
- GPU Tracking: [Phase 6](#gpu-cost-management)
- Workload Classification: [Phase 6 User Guide](./user-guide/phase6-user-guide.md#workload-classification)
- Cost-Per-Inference: [Phase 6 User Guide](./user-guide/phase6-user-guide.md#cost-per-inference)
- Spot Recommendations: [Phase 6 User Guide](./user-guide/phase6-user-guide.md#spot-instance-recommendations)
- Idle GPU Detection: [Phase 6 User Guide](./user-guide/phase6-user-guide.md#gpu-prevention)

---

## 📚 Full Documentation

For comprehensive navigation:
- **[INDEX.md](./INDEX.md)** - Master documentation index
- **[DOCUMENTATION_MAP.md](./DOCUMENTATION_MAP.md)** - Complete documentation map
- **[PROJECT_STATUS.md](./PROJECT_STATUS.md)** - Overall project status

---

**Last Updated:** February 2026  
**Maintained By:** CostGuard AI Team  
**Need Help?** Check [INDEX.md](./INDEX.md) or [DOCUMENTATION_MAP.md](./DOCUMENTATION_MAP.md)
