# CostGuard AI - Quick Reference Guide

> **Current backend references (October 3, 2026):** [Project status](PROJECT_STATUS.md), [architecture](technical/architecture.md), [API contracts](technical/api-design.md), [database schemas](technical/database-design.md), and [known limitations](technical/documentation-code-sync.md). Historical deployment/test/planning reports preserve their original results; they do not certify present live operation.


**Last Updated:** February 2026  
**Purpose:** Fast access to commonly needed documentation

---

## 🚀 I Need To...

### Get Started
- **Install & Deploy:** [README.md](../README.md#-getting-started)
- **Understand Architecture:** [Architecture](./technical/architecture.md)
- **See API Examples:** [API_EXAMPLES.md](./API_EXAMPLES.md)

### Use the API
- **Phase 1 (Historical):** [API Examples - Phase 1](./API_EXAMPLES.md#phase-1-historical-cost-data)
- **Phase 1.5 (Real-Time):** [API Examples - Phase 1.5](./API_EXAMPLES.md#phase-15-near-real-time-cost-estimation)
- **Phase 2 (Forecasting):** [API Examples - Phase 2](./API_EXAMPLES.md#phase-2-ai-powered-cost-forecasting)
- **Phase 3 (Prevention):** [API Examples - Phase 3](./API_EXAMPLES.md)
- **Phase 4 (AI Advisor):** [API Examples - Phase 4](./API_EXAMPLES.md)
- **Phase 5 (Multi-Account):** [Phase 5 API Docs](./technical/phase5-multi-account/API_DOCUMENTATION.md)

### Deploy
- **Phase 1:** [Phase 1 README](./technical/phase1-cost-pipeline/README.md#deployment)
- **Phase 1.5:** [Infrastructure Updates](./technical/phase1.5-near-realtime/infrastructure-updates.md)
- **Phase 2:** [Infrastructure Updates](./technical/phase2-ai-forecasting/infrastructure-updates.md)
- **Phase 3:** [Infrastructure Updates](./technical/phase3-automated-prevention/infrastructure-updates.md)
- **Phase 4:** [Deployment Checklist](deployment/DEPLOYMENT_CHECKLIST.md)
- **Phase 5:** [Deployment Scripts](deployment/DEPLOYMENT_SCRIPTS.md)

### Troubleshoot
- **Phase 1 Issues:** [Phase 1 README - Troubleshooting](./technical/phase1-cost-pipeline/README.md#troubleshooting)
- **Phase 1.5 Issues:** [Phase 1.5 README - Troubleshooting](./technical/phase1.5-near-realtime/README.md#troubleshooting)
- **Phase 2 Issues:** [Phase 2 README - Troubleshooting](./technical/phase2-ai-forecasting/README.md)
- **Phase 3 Issues:** [Phase 3 README - Troubleshooting](./technical/phase3-automated-prevention/README.md#troubleshooting)
- **Phase 4 Issues:** [Phase 4 README - Troubleshooting](./technical/phase4-ai-advisor/README.md#troubleshooting)

### Understand Costs
- **Cost Breakdown:** [README - Cost Optimization](../README.md#-cost-optimization)
- **Free Tier Usage:** [AWS Services](./technical/aws-services.md)
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
- **API:** [API Examples - Phase 3](./API_EXAMPLES.md)
- **Design:** [Phase 3 Specification](./technical/phase3-automated-prevention/specification.md)
- **EventBridge Setup:** [Infrastructure Updates](./technical/phase3-automated-prevention/infrastructure-updates.md)

### AI Cost Advisor
- **Overview:** [Phase 4 README](./technical/phase4-ai-advisor/README.md)
- **API:** [API Examples - Phase 4](./API_EXAMPLES.md)
- **Design:** [Phase 4 Specification](./technical/phase4-ai-advisor/specification.md)
- **Deployment:** [Deployment Checklist](deployment/DEPLOYMENT_CHECKLIST.md)

### Multi-Account Management
- **Overview:** [Phase 5 README](./technical/phase5-multi-account/README.md)
- **API:** [Phase 5 API Documentation](./technical/phase5-multi-account/API_DOCUMENTATION.md)
- **Cross-Account Setup:** [CROSS_ACCOUNT_SETUP.md](../infrastructure/CROSS_ACCOUNT_SETUP.md)
- **Deployment:** [Deployment Scripts](deployment/DEPLOYMENT_SCRIPTS.md)

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
- **Cost Explorer:** [AWS Services Guide](./technical/aws-services.md)
- **CloudWatch:** [AWS Services Guide](./technical/aws-services.md)
- **Bedrock:** [AWS Services Guide](./technical/aws-services.md)
- **DynamoDB:** [Database Design](./technical/database-design.md)
- **Lambda:** [Architecture](./technical/architecture.md)
- **API Gateway:** [API Design](./technical/api-design.md)
- **EventBridge:** [AWS Services Guide](./technical/aws-services.md)
- **Organizations:** [Phase 5 README](./technical/phase5-multi-account/README.md)

### AI/ML
- **Bedrock Integration:** [Architecture - AI](./technical/architecture.md)
- **Nova Lite Model:** [AWS Services - Nova](./technical/aws-services.md)
- **Forecasting:** [Phase 2 Design](../.kiro/specs/ai-cost-forecasting/design.md)
- **NLP:** [Phase 4 Design](../.kiro/specs/ai-cost-advisor/design.md)
- **Conversational AI:** [Phase 4 README](./technical/phase4-ai-advisor/README.md)

### Testing
- **Testing Strategy:** [Architecture - Testing](./technical/architecture.md)
- **Property-Based Testing:** [Best Practices](./resources/best-practices.md)
- **Test Results:** [PROJECT_STATUS.md - Test Coverage](./PROJECT_STATUS.md#test-coverage)

---

## 📊 By Phase

| Phase | README | API | Design | Deploy | Tests |
|-------|--------|-----|--------|--------|-------|
| **1** | [README](./technical/phase1-cost-pipeline/README.md) | [API](./API_EXAMPLES.md#phase-1-historical-cost-data) | [Spec](./technical/phase1-cost-pipeline/specification.md) | [Deploy](./technical/phase1-cost-pipeline/README.md#deployment) | [Tests](./technical/phase1-cost-pipeline/implementation-summary.md) |
| **1.5** | [README](./technical/phase1.5-near-realtime/README.md) | [API](./API_EXAMPLES.md#phase-15-near-real-time-cost-estimation) | [Design](./technical/phase1.5-near-realtime/design.md) | [Infra](./technical/phase1.5-near-realtime/infrastructure-updates.md) | [Tests](./technical/phase1.5-near-realtime/implementation-summary.md) |
| **2** | [README](./technical/phase2-ai-forecasting/README.md) | [API](./API_EXAMPLES.md#phase-2-ai-powered-cost-forecasting) | [Spec](./technical/phase2-ai-forecasting/specification.md) | [Infra](./technical/phase2-ai-forecasting/infrastructure-updates.md) | [Tests](./technical/phase2-ai-forecasting/implementation-summary.md) |
| **3** | [README](./technical/phase3-automated-prevention/README.md) | [API](./API_EXAMPLES.md) | [Spec](./technical/phase3-automated-prevention/specification.md) | [Infra](./technical/phase3-automated-prevention/infrastructure-updates.md) | [Tests](./technical/phase3-automated-prevention/implementation-summary.md) |
| **4** | [README](./technical/phase4-ai-advisor/README.md) | [API](./API_EXAMPLES.md) | [Spec](./technical/phase4-ai-advisor/specification.md) | [Checklist](deployment/DEPLOYMENT_CHECKLIST.md) | [Tests](./technical/phase4-ai-advisor/implementation-summary.md) |
| **5** | [README](./technical/phase5-multi-account/README.md) | [API Docs](./technical/phase5-multi-account/API_DOCUMENTATION.md) | [Design](../.kiro/specs/multi-account-cost-management/design.md) | [Scripts](deployment/DEPLOYMENT_SCRIPTS.md) | [Tasks](../.kiro/specs/multi-account-cost-management/tasks.md) |
| **6** | [User Guide](./user-guide/phase6-user-guide.md) | [API Docs](./api/phase6-api-documentation.md) | [Deployment](./deployment/phase6-deployment-guide.md) | [Deploy](./deployment/phase6-deployment-guide.md) | [Validation](project/PHASE6_VALIDATION_REPORT.md) |
| **7-8** | [Future Roadmap](./FUTURE_ROADMAP.md) | [Phase 7 Rec](./project/phase7-recommendation.md) | [Timeline](./project/phase-timeline.md) | ⏸️ Post-Hackathon | ⏸️ Planned |

---

## 🎯 Common Questions

### "How do I...?"

**...get started quickly?**
1. Read [README.md](../README.md)
2. Follow [Getting Started](../README.md#-getting-started)
3. Try [API Examples](./API_EXAMPLES.md)

**...deploy to AWS?**
1. Check [Prerequisites](../README.md#prerequisites)
2. Follow phase-specific deployment guides (see [By Phase](#-by-phase))
3. Verify with [API Examples](./API_EXAMPLES.md)

**...use the AI advisor?**
1. Read [Phase 4 README](./technical/phase4-ai-advisor/README.md)
2. Deploy using [Deployment Checklist](deployment/DEPLOYMENT_CHECKLIST.md)
3. Try [Phase 4 API Examples](./API_EXAMPLES.md)

**...set up multi-account?**
1. Read [Phase 5 README](./technical/phase5-multi-account/README.md)
2. Follow [Cross-Account Setup](../infrastructure/CROSS_ACCOUNT_SETUP.md)
3. Deploy with [Deployment Scripts](deployment/DEPLOYMENT_SCRIPTS.md)

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
2. Check [Idle GPU Detection](./api/phase6-api-documentation.md#3-get-idle-gpus)
3. Use [GPU Prevention API](./api/phase6-api-documentation.md#16-run-gpu-prevention-cycle)

**...see future roadmap?**
1. Read [Future Roadmap](./FUTURE_ROADMAP.md) - Phase 7-8 post-hackathon features
2. Check [Phase 7 Recommendation](./project/phase7-recommendation.md) - Unit Economics + RI/SP
3. Review [Phase Timeline](./project/phase-timeline.md) - Complete priorities

**...understand the architecture?**
1. Read [Architecture Overview](./technical/architecture.md)
2. Review [AWS Services Used](./technical/aws-services.md)
3. Check phase-specific designs (see [By Phase](#-by-phase))

**...check test coverage?**
1. See [PROJECT_STATUS.md - Test Coverage](./PROJECT_STATUS.md#test-coverage)
2. Review phase-specific test results (see [By Phase](#-by-phase))
3. Read [Testing Strategy](./technical/architecture.md)

**...estimate costs?**
1. Read [Cost Optimization](../README.md#-cost-optimization)
2. Check [Monthly Cost Breakdown](./PROJECT_STATUS.md#monthly-cost-breakdown)
3. Review [Free Tier Usage](./technical/aws-services.md)

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
- Bedrock: [AWS Services](./technical/aws-services.md)
- Forecasting: [Phase 2](#ai-forecasting)
- Advisor: [Phase 4](#ai-cost-advisor)
- NLP: [Phase 4 Design](../.kiro/specs/ai-cost-advisor/design.md)
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
- Unit Economics: [Future Roadmap](./FUTURE_ROADMAP.md#feature-71-unit-economics-tracking) (Phase 7)
- RI/SP Optimization: [Future Roadmap](./FUTURE_ROADMAP.md#feature-72-reserved-instance--savings-plan-optimization) (Phase 7)
- Developer Tools: [Future Roadmap](./FUTURE_ROADMAP.md#phase-8-developer-cost-transparency-tools) (Phase 8)

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
