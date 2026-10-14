# CostGuard AI - Future Roadmap (Phase 7-8)

> **Current source boundary - October 14, 2026:** Phase 7 unit-economics ingestion/analysis and read-only RI/SP commitment analytics have local implementations with operator-input and observed-period limits. Advanced purchase optimization and external business-system integration remain outstanding. Phase 8 IDE/CI/IaC products below remain proposals; advisor evidence JSON export does not implement those products. All continuing tests/builds/browser/account/deployment validation is deferred. Use the [active backlog](technical/development-backlog.md), [current contracts](technical/access-and-feature-contracts.md) and [source sync summary](technical/documentation-code-sync.md).
>
> The original February roadmap below is historical planning. Its target quarters, effort/commercial assumptions, competitor claims and complete/deployed assertions are not current verified facts or release commitments.


**Keywords:** future roadmap, post-hackathon, Phase 7, Phase 8, unit economics, RI/SP optimization, developer tools, VS Code extension, GitHub Action, IaC cost preview, planned features, commercial launch, semantic search, cross-reference

**Status:** Historical roadmap; limited Phase 7 source now implemented, Phase 8 products still proposed  
**Priority:** MEDIUM - Commercial viability features  
**Last Updated:** February 2026

**Related Documentation:**
- [PROJECT_STATUS.md](./PROJECT_STATUS.md) - Current project status (Phases 1-6)
- [project/phase7-recommendation.md](./project/phase7-recommendation.md) - Phase 7 detailed recommendation
- [project/phase-timeline.md](./project/phase-timeline.md) - Complete phase timeline
- [HACKATHON-EMPHASIS-ANALYSIS.md](./HACKATHON-EMPHASIS-ANALYSIS.md) - Why Phase 7-8 deferred
- [INDEX.md](./INDEX.md) - Master documentation index

---

## Executive Summary

This document outlines CostGuard AI's post-hackathon roadmap for Phase 7-8. These features are planned for commercial launch after the AWS 10,000 AIdeas Competition.

**Current Status (Hackathon Submission):**
- ✅ Phase 1-4: Complete & Deployed (Historical data, real-time estimation, AI forecasting, automated prevention)
- ✅ Phase 5: Complete (Multi-account cost management)
- ✅ Phase 6: Complete (AI/ML workload cost management)

**Future Roadmap (Post-Hackathon):**
- 📋 Phase 7: Unit Economics + RI/SP Optimization
- 📋 Phase 8: Developer Cost Transparency Tools

**Why Deferred:**
- Phase 6 (AI/ML workload costs) has higher hackathon alignment (93.33% vs 84.06%)
- Phase 7-8 features are valuable but not required for hackathon submission
- Focus on execution quality over feature quantity ("thin slice beats moonshot")
- All competitors already have Phase 7 features (not differentiating)
- Phase 8 requires AI integration to align with hackathon theme

---

## Phase 7: Unit Economics + RI/SP Optimization

### Overview

**Status:** PLANNED - Post-Hackathon  
**Priority:** MEDIUM-HIGH  
**Estimated Effort:** 2-3 weeks  
**Target Launch:** Q2 2026 (Post-Hackathon)

**What It Is:**
Enterprise-grade FinOps features that CloudZero, nOps, and Vantage charge $500-2000+/month for, brought to SMBs at $10-50/month.

**Why Important:**
- Addresses CFO pain points (margin forecasting, commitment waste)
- Completes FinOps platform (visibility + ownership + automation + optimization)
- Commercial viability (enterprise features at SMB prices)

**Why Deferred:**
- ALL competitors already have these features (CloudZero, nOps, Vantage)
- Lower hackathon score than AI/ML (84.06% vs 93.33%)
- Traditional FinOps, not AI-focused (hackathon requires "innovative AI applications")
- Still valuable for commercial launch, but not differentiating for hackathon

---

### Feature 7.1: Unit Economics Tracking

#### What It Is
Track cloud costs relative to business metrics (cost per customer, per transaction, per API call, per feature).

#### Business Value

**Problem:**
- Finance can't forecast margins without cost-per-customer insights
- Product managers can't price products without understanding unit costs
- Engineers can't justify optimization investments without economic lens
- 74% of CFOs report 5-10%+ monthly forecast variance without unit economics

**Solution:**
- Track cost per customer, per transaction, per API call
- Custom metrics API for business data ingestion
- Tag-based cost attribution
- Trend analysis and anomaly detection

**Real Impact:**
- Startup with 1,000 customers spending $5,000/month = $5/customer
- Customer count grows to 2,000 but spend grows to $15,000 = $7.50/customer (50% increase)
- Unit economics reveals: customer acquisition is getting more expensive
- Without unit economics: "AWS bill went up" (no actionable insight)

#### Key Features

**Custom Metrics API:**
```
POST /api/unit-economics/metrics
  - Submit business metrics (customers, transactions, API calls)
  - Body: { "date": "2026-02-01", "customers": 1000, "transactions": 50000 }
```

**Cost Per Customer:**
```
GET /api/unit-economics/cost-per-customer
  - Get cost per customer over time
  - Response: [{ "date": "2026-02-01", "cost_per_customer": 5.00, "total_cost": 5000, "customers": 1000 }]
```

**Cost Per Transaction:**
```
GET /api/unit-economics/cost-per-transaction
  - Get cost per transaction over time
```

**Trend Analysis:**
```
GET /api/unit-economics/trends
  - Get unit cost trends and anomalies
  - Response: { "trend": "increasing", "anomalies": [...], "forecast": [...] }
```

#### Implementation Plan

**Week 1: Foundation**
- Custom metrics API endpoint
- Tag-based cost attribution engine
- Unit cost calculation logic
- DynamoDB schema extension

**Week 2: Analytics**
- Cost per customer/transaction calculations
- Trend analysis logic
- Anomaly detection for unit costs
- API endpoints for queries
- Performance caching

**Week 3: Testing & Documentation**
- Unit tests for calculations
- Property-based tests for attribution
- Integration tests with business metrics
- API documentation
- Deployment guide

#### Competitive Positioning

**vs. CloudZero ($500-2000+/month):**
- CloudZero: Requires "extensive tagging infrastructure"
- CostGuard AI: Works with minimal tags (simpler setup)
- CloudZero: $500-2000+/month
- CostGuard AI: $10-50/month (10x cheaper)

**vs. nOps ($500-2000+/month):**
- nOps: Business Unit Economics with custom metrics
- CostGuard AI: Same features at 10x lower price
- nOps: Complex setup
- CostGuard AI: Out-of-the-box simplicity

**vs. Vantage ($500-2000+/month):**
- Vantage: Less sophisticated unit economics
- CostGuard AI: More sophisticated (like CloudZero)
- Vantage: $500-2000+/month
- CostGuard AI: $10-50/month

---

### Feature 7.2: Reserved Instance / Savings Plan Optimization

#### What It Is
Automated recommendations for RI/SP purchases, utilization tracking, commitment waste detection.

#### Business Value

**Problem:**
- 20-30% of cloud spend wasted on unused prepaid capacity (IDC)
- Companies leave 20%+ savings on the table with poor RI/SP management
- Misaligned commitments lead to wasted spending or higher costs during spikes
- SMBs don't have expertise to optimize commitments

**Solution:**
- Automated RI/SP purchase recommendations
- Utilization tracking (monitor usage vs. commitment)
- Waste detection (unused or underutilized commitments)
- ROI calculator (savings vs. commitment cost)

**Real Impact:**
- Startup spending $5,000/month on EC2 on-demand
- With 3-year Standard RI: Save up to 72% = $3,600/month savings = $43,200/year
- But if usage drops or shifts, unused RI = wasted money
- RI/SP optimization ensures commitments match actual usage

#### Key Features

**Commitment Recommendations:**
```
GET /api/commitments/recommendations
  - Get RI/SP purchase recommendations
  - Response: [
      {
        "service": "EC2",
        "instance_type": "m5.large",
        "recommendation": "3-year Standard RI",
        "current_cost": 5000,
        "projected_cost": 1400,
        "savings": 3600,
        "roi": "72%"
      }
    ]
```

**Utilization Tracking:**
```
GET /api/commitments/utilization
  - Get current RI/SP utilization
  - Response: {
      "total_commitments": 10,
      "utilized": 8,
      "underutilized": 2,
      "utilization_rate": "80%"
    }
```

**Waste Detection:**
```
GET /api/commitments/waste
  - Get commitment waste analysis
  - Response: {
      "wasted_spend": 500,
      "unused_commitments": [...],
      "recommendations": [...]
    }
```

**ROI Calculator:**
```
GET /api/commitments/roi
  - Calculate ROI for commitment purchases
  - Response: { "savings": 3600, "roi": "72%", "payback_period": "6 months" }
```

#### Implementation Plan

**Week 1: Analysis**
- Usage pattern analysis for stable workloads
- RI/SP recommendation engine
- Utilization tracking logic
- Cost Explorer integration for RI/SP data

**Week 2: Optimization**
- ROI calculator for commitments
- Automated recommendation generation
- API endpoints for optimization
- Alerts for underutilized commitments
- Commitment comparison tool (RI vs. SP)

**Week 3: Testing & Documentation**
- Unit tests for recommendation engine
- Property-based tests for ROI calculations
- Integration tests with Cost Explorer
- API documentation
- Deployment guide

#### Competitive Positioning

**vs. nOps ($500-2000+/month):**
- nOps: Automated RI/SP recommendations and management
- CostGuard AI: Same features at 10x lower price
- nOps: $500+/month
- CostGuard AI: $10-50/month

**vs. CloudZero ($500-2000+/month):**
- CloudZero: RI/SP analysis but limited optimization
- CostGuard AI: Full automation (recommendations + tracking + waste detection)
- CloudZero: $500-2000+/month
- CostGuard AI: $10-50/month

**vs. Vantage ($500-2000+/month):**
- Vantage: Commitment tracking
- CostGuard AI: Tracking + optimization + automation
- Vantage: $500-2000+/month
- CostGuard AI: $10-50/month

---

### Phase 7 Cost Estimate

**Additional AWS Costs:**
- Cost Explorer API: +$0.50/month (50 additional API calls for RI/SP data)
- Lambda: +2,000 invocations/month (within 1M free tier)
- DynamoDB: +50 MB storage (within 25 GB free tier)

**Total Phase 7 Cost:** ~$0.50/month additional  
**Total System Cost (Phases 1-7):** ~$3.01/month

**Still within Free Tier:** Yes (except Cost Explorer and Bedrock API calls)

---

## Phase 8: Developer Cost Transparency Tools

### Overview

**Status:** PLANNED - Post-Hackathon  
**Priority:** MEDIUM  
**Estimated Effort:** 2-3 weeks  
**Target Launch:** Q3 2026 (Post-Hackathon)

**What It Is:**
Developer-focused tools that provide real-time cost feedback during development, before deployment.

**Why Important:**
- "Shift-left" cost management (catch issues before deployment)
- NO competitor does this well (wide open market)
- Developer-focused (catches cost issues immediately)
- Prevents cost surprises (developers see cost impact in real-time)

**Why Deferred:**
- Requires AI integration to align with hackathon theme ("innovative AI applications")
- Lower priority than AI/ML workload costs (Phase 6)
- Can be built post-hackathon with AI layer added

---

### Feature 8.1: VS Code Extension

#### What It Is
Real-time cost feedback during development with cost annotations in code.

#### Business Value

**Problem:**
- Developers don't see cost impact until after deployment
- Cost surprises after launch (e.g., "Why is our Lambda bill $10K?")
- No feedback loop during development
- Engineers can't optimize costs without visibility

**Solution:**
- Real-time cost annotations in VS Code
- Resource cost estimates as you code
- Cost warnings for expensive operations
- Optimization suggestions inline

**Real Impact:**
- Developer writes Lambda function with 10GB memory
- VS Code extension shows: "This Lambda will cost $0.50/1000 invocations"
- Developer reduces to 1GB memory: "Now $0.05/1000 invocations (90% savings)"
- Cost issue caught before deployment

#### Key Features

**Cost Annotations:**
- Inline cost estimates for AWS resources
- Hover tooltips with cost breakdowns
- Warning highlights for expensive operations

**Resource Cost Estimates:**
- Lambda function costs (memory × duration × invocations)
- DynamoDB table costs (read/write capacity × requests)
- S3 bucket costs (storage × requests)
- EC2 instance costs (instance type × hours)

**Optimization Suggestions:**
- "Consider using Lambda with 1GB memory instead of 10GB (90% savings)"
- "Use DynamoDB on-demand instead of provisioned (20% savings for low traffic)"
- "Switch to S3 Intelligent-Tiering (30% savings for infrequent access)"

**AI-Powered Recommendations:**
- Use Amazon Bedrock to analyze code patterns
- Generate natural language optimization suggestions
- Context-aware recommendations based on usage patterns

#### Implementation Plan

**Week 1: Foundation**
- VS Code extension scaffolding
- AWS resource detection in code
- Cost calculation engine
- Bedrock integration for AI recommendations

**Week 2: Features**
- Inline cost annotations
- Hover tooltips with breakdowns
- Warning highlights
- Optimization suggestions panel

**Week 3: Testing & Documentation**
- Extension testing
- User guide
- Demo videos
- VS Code Marketplace publishing

---

### Feature 8.2: GitHub Action

#### What It Is
PR cost impact analysis with cost diff in PR comments.

#### Business Value

**Problem:**
- No visibility into cost impact of code changes
- Cost surprises after merge (e.g., "This PR increased our bill by $5K/month")
- No cost review process in CI/CD
- Engineers can't evaluate cost trade-offs

**Solution:**
- Automated cost analysis on every PR
- Cost diff in PR comments (before vs. after)
- Cost approval workflow (require approval for high-cost changes)
- Cost trend tracking over time

**Real Impact:**
- Developer opens PR to add new Lambda function
- GitHub Action analyzes PR: "This PR will increase monthly costs by $500"
- Team reviews cost impact before merge
- Cost issue caught before production

#### Key Features

**PR Cost Analysis:**
- Analyze infrastructure changes in PR
- Calculate cost impact (before vs. after)
- Post cost diff as PR comment

**Cost Approval Workflow:**
- Require approval for PRs with cost impact > threshold
- Notify cost owners for review
- Block merge until approved

**Cost Trend Tracking:**
- Track cost impact of PRs over time
- Identify cost-increasing patterns
- Alert when cumulative cost impact exceeds budget

**AI-Powered Analysis:**
- Use Amazon Bedrock to analyze infrastructure changes
- Generate natural language cost impact summaries
- Suggest cost-optimized alternatives

#### Implementation Plan

**Week 1: Foundation**
- GitHub Action scaffolding
- Infrastructure change detection
- Cost calculation engine
- Bedrock integration for AI analysis

**Week 2: Features**
- PR cost analysis logic
- Cost diff comment generation
- Approval workflow integration
- Cost trend tracking

**Week 3: Testing & Documentation**
- Action testing
- User guide
- Demo videos
- GitHub Marketplace publishing

---

### Feature 8.3: Infrastructure-as-Code Cost Preview

#### What It Is
Pre-deployment cost estimation for CloudFormation, CDK, and Terraform.

#### Business Value

**Problem:**
- No cost visibility before deploying infrastructure
- Cost surprises after deployment (e.g., "This stack costs $10K/month?")
- No way to compare cost of different architectures
- Engineers can't evaluate cost trade-offs

**Solution:**
- Pre-deployment cost estimation for IaC
- Cost comparison for different architectures
- What-if scenarios (e.g., "What if I use Spot instances?")
- Cost optimization suggestions

**Real Impact:**
- Engineer writes CloudFormation template for new service
- Cost preview shows: "This stack will cost $5,000/month"
- Engineer adjusts instance types: "Now $2,000/month (60% savings)"
- Cost issue caught before deployment

#### Key Features

**CloudFormation Cost Preview:**
- Parse CloudFormation templates
- Calculate cost for all resources
- Show cost breakdown by resource type

**CDK Cost Preview:**
- Integrate with AWS CDK
- Calculate cost for synthesized templates
- Show cost impact of CDK constructs

**Terraform Cost Preview:**
- Parse Terraform plans
- Calculate cost for all resources
- Show cost breakdown by module

**AI-Powered Optimization:**
- Use Amazon Bedrock to analyze infrastructure patterns
- Generate natural language optimization suggestions
- Suggest cost-optimized alternatives (e.g., "Use Spot instances for 70% savings")

#### Implementation Plan

**Week 1: Foundation**
- IaC parser (CloudFormation, CDK, Terraform)
- Cost calculation engine
- Bedrock integration for AI optimization

**Week 2: Features**
- Cost preview for CloudFormation
- Cost preview for CDK
- Cost preview for Terraform
- What-if scenarios

**Week 3: Testing & Documentation**
- Parser testing
- User guide
- Demo videos
- CLI tool publishing

---

### Phase 8 Cost Estimate

**Additional AWS Costs:**
- Bedrock API: +$0.50/month (AI-powered recommendations)
- Lambda: +1,000 invocations/month (within 1M free tier)
- DynamoDB: +20 MB storage (within 25 GB free tier)

**Total Phase 8 Cost:** ~$0.50/month additional  
**Total System Cost (Phases 1-8):** ~$3.51/month

**Still within Free Tier:** Yes (except Cost Explorer and Bedrock API calls)

---

## Why Phase 7-8 Are Deferred

### Hackathon Alignment Analysis

**Phase 6 (AI/ML Workload Costs) Score:** 93.33%
- ✅ Painkiller problem (AI startups spend 80% of funding on GPU costs)
- ✅ Clear ROI (save $7K-10K/month on GPU costs)
- ✅ NO competitor does this (wide open market)
- ✅ AWS alignment ("agent workflows that do real tasks")
- ✅ Industry-specific (AI/ML, fastest-growing segment)

**Phase 7 (Unit Economics + RI/SP) Score:** 84.06%
- ⚠️ ALL competitors already have this (CloudZero, nOps, Vantage)
- ⚠️ Traditional FinOps, not AI-focused
- ⚠️ Lower hackathon alignment (not "innovative AI applications")
- ✅ Still valuable for commercial launch

**Phase 8 (Developer Tools) Score:** TBD
- ⚠️ Requires AI integration to align with hackathon theme
- ⚠️ Lower priority than Phase 6
- ✅ Unique positioning (NO competitor does this)
- ✅ Can be built post-hackathon with AI layer

**Conclusion:**
- Phase 6 has +9.27% score advantage over Phase 7
- Focus on execution quality over feature quantity
- "Thin slice beats moonshot" (AWS emphasis)
- Phase 7-8 are valuable but not required for hackathon

See [HACKATHON-EMPHASIS-ANALYSIS.md](./HACKATHON-EMPHASIS-ANALYSIS.md) for detailed analysis.

---

## Commercial Launch Strategy

### Phase 7 Launch (Q2 2026)

**Target Market:**
- SMBs with 10-100 employees
- Startups with $10K-100K/month AWS spend
- Companies needing CFO-level insights

**Pricing:**
- Basic: $10/month (unit economics only)
- Pro: $30/month (unit economics + RI/SP optimization)
- Enterprise: $50/month (all features + priority support)

**Marketing:**
- "CloudZero for startups" positioning
- "Enterprise FinOps at SMB prices"
- CFO-focused messaging (margin forecasting, commitment waste)

### Phase 8 Launch (Q3 2026)

**Target Market:**
- Development teams using VS Code
- Teams using GitHub for CI/CD
- Infrastructure-as-code users

**Pricing:**
- Developer: $5/month per developer (VS Code extension)
- Team: $20/month per team (GitHub Action + IaC preview)
- Enterprise: $50/month (all features + priority support)

**Marketing:**
- "Shift-left cost management" positioning
- "Catch cost issues before deployment"
- Developer-focused messaging (real-time feedback, cost annotations)

---

## Success Metrics

### Phase 7 Success Criteria

**Adoption:**
- 100+ users tracking unit economics
- 50+ users using RI/SP optimization
- 20+ users with $1K+ monthly savings

**Technical:**
- 90%+ test coverage
- <500ms API response time
- 95%+ uptime

**Business:**
- $5K+ MRR from Phase 7 features
- 80%+ customer satisfaction
- 50%+ feature adoption rate

### Phase 8 Success Criteria

**Adoption:**
- 500+ VS Code extension installs
- 100+ GitHub Action users
- 50+ IaC preview users

**Technical:**
- 90%+ test coverage
- <1s cost preview time
- 95%+ uptime

**Business:**
- $3K+ MRR from Phase 8 features
- 80%+ customer satisfaction
- 60%+ feature adoption rate

---

## Risk Assessment

### Phase 7 Risks

**Risk 1: Complexity**
- Unit economics and RI/SP optimization add significant complexity
- Mitigation: Start with simple unit metrics, incremental rollout

**Risk 2: Data Quality**
- Unit economics requires accurate business metrics from users
- Mitigation: Clear API documentation, validation, sample data

**Risk 3: RI/SP Recommendation Accuracy**
- Incorrect recommendations could cost users money
- Mitigation: Conservative recommendations, ROI calculations, disclaimers

### Phase 8 Risks

**Risk 1: VS Code Extension Complexity**
- Building a robust VS Code extension is challenging
- Mitigation: Start with simple features, iterate based on feedback

**Risk 2: GitHub Action Reliability**
- GitHub Actions must be reliable and fast
- Mitigation: Comprehensive testing, error handling, fallbacks

**Risk 3: IaC Parser Accuracy**
- Parsing CloudFormation/CDK/Terraform is complex
- Mitigation: Use existing parsers, validate against AWS pricing API

---

## Conclusion

Phase 7-8 are valuable features for commercial launch but deferred for hackathon submission.

**Why Deferred:**
- Phase 6 (AI/ML workload costs) has higher hackathon alignment
- Focus on execution quality over feature quantity
- "Thin slice beats moonshot" (AWS emphasis)
- Phase 7-8 are valuable but not differentiating for hackathon

**Post-Hackathon Plan:**
- Q2 2026: Launch Phase 7 (Unit Economics + RI/SP)
- Q3 2026: Launch Phase 8 (Developer Tools)
- Q4 2026: Complete commercial platform

**Commercial Value:**
- Phase 7: Enterprise FinOps at SMB prices ($10-50/month vs $500-2000+)
- Phase 8: Unique positioning (NO competitor does developer tools)
- Combined: Complete FinOps platform for SMBs

**Next Steps:**
1. Complete Phase 6 (AI/ML workload costs) for hackathon
2. Document Phase 7-8 as future roadmap
3. Launch Phase 7-8 post-hackathon for commercial viability

---

**Status:** PLANNED - Post-Hackathon Development  
**Last Updated:** February 2026  
**Next Review:** After hackathon results (May 2026)

---

## See Also

- **[PROJECT_STATUS.md](./PROJECT_STATUS.md)** - Current project status (Phases 1-6)
- **[project/phase7-recommendation.md](./project/phase7-recommendation.md)** - Phase 7 detailed recommendation
- **[project/phase-timeline.md](./project/phase-timeline.md)** - Complete phase timeline
- **[HACKATHON-EMPHASIS-ANALYSIS.md](./HACKATHON-EMPHASIS-ANALYSIS.md)** - Why Phase 7-8 deferred
- **[INDEX.md](./INDEX.md)** - Master documentation index
