# Builder Center Article – Copy-Paste Draft

**Yes, you can start writing the article now.** The draft below matches the official guidelines ([SEMI_FINALIST_SELECTION_EMAIL.md](./SEMI_FINALIST_SELECTION_EMAIL.md), [HOW_TO_WRITE_ARTICLE.md](./HOW_TO_WRITE_ARTICLE.md)): all 6 sections, Terms (development process, technical architecture, key learnings), Kiro, AWS services, and team name.

---

## Start here – steps to publish

1. **Open Builder Center** → click **"+"** (top right) → choose **"Article"** (not Post).
2. **Title:** Paste from **Section 1** below → `AIdeas: CostGuard AI`.
3. **Description:** Paste from **Section 2** (Primary) below into the description field (0–512 chars).
4. **Body:** Paste from **Section 3** (from `### App category` through `*Built with Kiro and AWS. CostGuard AI Team.*`). Do not paste the "Before you publish" line or the options/notes above the body.
5. **In the UI:** Add a **cover image**. In the **Demo** section, replace the *[Insert screenshots...]* line with your **screenshots or a video &lt; 5 min** (order and captions: [DEMO_SCREENSHOTS_AND_CAPTIONS.md](./DEMO_SCREENSHOTS_AND_CAPTIONS.md)).
6. **Tags:** Select **#aideas-2025**, **#commercial-solutions**, and **your region** (#EMEA, #NAMER, #APJC, #LATAM, #GCR, or #ANZ).
7. **Publish** by **March 13, 2026, 8:00 PM UTC**, then share the article link in the [10,000 AIdeas competition space](https://builder.aws.com/connect/space/3a92613a-ce41-30a7-bc0d-6067611fbd09/10000-aideas-competition) to get likes.

**Checklist:** [ARTICLE_WHAT_TO_WRITE.md](./ARTICLE_WHAT_TO_WRITE.md)

---

## 1. Title (paste into "Title" – 0/255 characters)

```
AIdeas: CostGuard AI
```

---

## 2. Description (paste into "Description" – 0/512 characters)

One or two sentences summarizing the article **without repeating the title**. This appears in **search results and feeds**. Max **512 characters**.

**What to include (from [HACKATHON_COMPETITION_INFO.md](../HACKATHON_COMPETITION_INFO.md)):**  
- **Article must showcase:** Overview of your application and **why it matters** → description should state what it is and its practical impact.  
- **Judging criteria:** **Innovation**, **Efficiency**, **Practical impact** (not computational scale) → signal novel solution, efficiency, real-world impact.  
- **Track (Commercial Potential):** Industry-specific solutions, enterprise applications, revenue-generating innovations → SMBs/startups, cost prevention = revenue protection.  
- **Technical requirements:** **Kiro** for at least part of development; **AWS Free Tier** only; original application → mention Kiro and AWS Free Tier.  
- **Recommended AWS services:** Amazon Bedrock, Nova → we use Bedrock (forecasting, advisor, AI/ML) → name Bedrock if space allows.  
- **Not:** Repeat the title ("AIdeas: CostGuard AI"); focus on scale or spend.

**Use this description (paste into Description – 0/512 chars).** Leads with execution (acts, prevention, autonomous loop).

**SEO recommendation:** Builder Center suggests description within **160 characters** for better search snippets. Use one of the short options below if you want to follow that.

**Short – for SEO, ≤160 chars (paste this if you want the 160-char recommendation):**
```
AWS cost platform that acts: real time estimation, prevention (20+ services), AI/ML optimization and autonomous loop with 20–30% savings. Kiro and Bedrock, Free Tier.
```
(158 characters)

**Primary – execution first (~320 chars, recommended if 160 limit not needed):**
```
An AWS cost platform that acts: near real time estimation, automated prevention (20+ services), and AI/ML workload optimization: GPU cost tracking by workload type, cost per inference, spot recommendations (up to 70%), idle GPU prevention, plus a self-optimizing 5 phase loop (Analyze, Decide, Act, Verify, Learn) with projected 20 to 30% savings. Built for SMBs and AI startups with Kiro and Bedrock on AWS Free Tier.
```
- **Overview + why it matters:** “acts” = does real work; prevention + projected savings = practical impact.  
- **Phase 6 (AI/ML):** Workload optimization, GPU by type, cost per inference, spot, idle GPU prevention → innovation, practical impact, Commercial track.  
- **Efficiency:** Near real time, automated, Free Tier.  
- **Phase 6 Extension (Autonomous):** Self-optimizing 5 phase loop (Analyze, Decide, Act, Verify, Learn), 20 to 30% savings → breakthrough, measurable impact.  
- **Per competition info:** Innovation, Efficiency, Practical impact; Kiro, Bedrock, AWS Free Tier.

**Optional – add Phase 2 + Phase 4 (forecasting, advisor) in one phrase (~380 chars, under 512):**
```
An AWS cost platform that acts: near real time estimation, AI powered forecasting and cost advisor (Bedrock), automated prevention (20+ services), and AI/ML workload optimization: GPU cost tracking by workload type, cost per inference, spot recommendations (up to 70%), idle GPU prevention, plus a self-optimizing 5 phase loop (Analyze, Decide, Act, Verify, Learn) with projected 20 to 30% savings. Built for SMBs and AI startups with Kiro and Bedrock on AWS Free Tier.
```
- Use if you want the description to explicitly mention forecasting and advisor; body still leads with execution.

---

**All phases and impact (from repo + [HACKATHON-EMPHASIS-ANALYSIS.md](../HACKATHON-EMPHASIS-ANALYSIS.md)):**  
- **Phase 6 (AI/ML):** GPU cost tracking (training/inference/idle), cost-per-inference and cost-per-training, spot recommendations (up to 70%), SageMaker/Bedrock tracking, idle GPU prevention. Painkiller for AI startups (GPU = big share of spend); clear ROI.  
- **Phase 6 Extension (Autonomous):** 5-phase loop (Analyze→Decide→Act→Verify→Learn), GPU scheduling, spot management, right-sizing, learning engine; real Cost Explorer/Pricing API/CloudWatch; demo 5.26s; projected 20 to 30% savings.  
- **Core:** Near-real-time estimation, automated prevention (20+ services). Judging: innovation, efficiency, **practical impact**; “agent workflows that do real tasks.”

- **Phase 1:** Historical cost data (Cost Explorer, DynamoDB) – foundation for forecasting and advisor.
- **Phase 1.5:** Near-real-time estimation (CloudWatch, minutes not 24h) – execution, fast detection.
- **Phase 2:** AI-powered forecasting (Bedrock Nova Lite, 7 to 30 day) – innovation, AI use.
- **Phase 3:** Automated prevention (20+ services, budget thresholds, idle detection, rollback) – execution, "real tasks."
- **Phase 4:** AI Cost Advisor (Bedrock, natural-language Q&A, suggestions) – differentiator; conversation secondary to "real tasks" per organizer.
- **Phase 5:** Multi-account (Organizations, cross-account costs, allocation, budgets) – scale for SMBs with multiple accounts.
- **Phase 6 (AI/ML):** GPU cost tracking (training/inference/idle), cost-per-inference and cost-per-training, spot recommendations (up to 70%), SageMaker/Bedrock tracking, idle GPU prevention – painkiller for AI startups; clear ROI.
- **Phase 6 Extension (Autonomous):** 5-phase loop (Analyze→Decide→Act→Verify→Learn), GPU scheduling, spot management, right-sizing, learning engine; demo 5.26s; projected 20 to 30% savings – execution, measurable impact.
Judging: **innovation, efficiency, practical impact**; "agent workflows that do real tasks."

**Option A (Phase 6 + Extension + core, no dashes, ~275 chars):**
```
An AWS cost platform that acts: near real time estimation, automated prevention (20+ services), and AI/ML optimization: GPU cost tracking, cost per inference, spot recommendations (up to 70%), plus an autonomous loop (Analyze to Decide to Act to Verify to Learn) with projected 20 to 30% savings. Built for SMBs and AI startups with Kiro and Bedrock on AWS Free Tier.
```

**Option B (AI/ML painkiller first, no dashes, ~255 chars):**
```
AI/ML and general AWS cost platform: GPU cost tracking, cost per inference, spot recommendations (up to 70%), and an autonomous loop with projected 20 to 30% savings, plus near real time estimation and automated prevention across 20+ services. For SMBs and AI startups. Kiro and Bedrock, AWS Free Tier.
```

**Option C (short, both phases implied, no dashes, ~225 chars):**
```
Stops AWS overruns and optimizes AI/ML spend: near real time estimation, automated prevention (20+ services), GPU tracking and spot recommendations, and an autonomous loop with projected 20 to 30% savings. For SMBs and AI startups. Kiro and Bedrock, AWS Free Tier.
```

**Option D (all phases hinted, no dashes, ~320 chars):**
```
An AWS cost platform that acts: near real time estimation, AI powered forecasting and cost advisor (Bedrock), automated prevention (20+ services), multi account support, and AI/ML workload optimization: GPU cost tracking by workload type, cost per inference, spot recommendations (up to 70%), idle GPU prevention, plus a self-optimizing 5 phase loop (Analyze, Decide, Act, Verify, Learn) with projected 20 to 30% savings. Built for SMBs and AI startups with Kiro and Bedrock on AWS Free Tier.
```

---

## 3. Body (paste into "Body" – full article in Markdown)

Add your **cover image** in the Builder Center UI. After pasting, insert **screenshots or a short video** in the Demo section. Select **tags**: `#aideas-2025`, `#commercial-solutions`, and your region tag.

**What to share (screenshots, backend, diagram):** See **[DEMO_SCREENSHOTS_AND_CAPTIONS.md](./DEMO_SCREENSHOTS_AND_CAPTIONS.md)** for which of your 7 screenshots to insert in the Demo section, in what order, and the exact captions. See **[ARTICLE_BODY_MEDIA_PLAN.md](./ARTICLE_BODY_MEDIA_PLAN.md)** for optional backend snippet and 5-phase loop diagram.

---

### App category

**Commercial Solutions.** CostGuard AI is a commercial-grade AWS cost prevention and optimization platform for small and medium businesses and startups.

---

### My vision

**The problem:** AWS bills can double overnight. Cost Explorer data is 24 hours behind. Enterprise tools cost hundreds per month. AWS Budgets Actions only cover five services. Startups and SMBs need prevention that is fast, broad, and affordable.

**What we built:** CostGuard AI—a platform that **acts**, not just advises:

1. **Estimates costs in near-real time** (minutes, not 24 hours) using CloudWatch metrics and pricing data for EC2, Lambda, DynamoDB, S3, and RDS.
2. **Prevents overspending automatically** across 20+ AWS services: budget thresholds, idle resource detection, safe automated actions (e.g. stop EC2, limit Lambda), tag-based protection, approval workflows, and rollback.
3. **Runs an autonomous optimization loop** (Analyze → Decide → Act → Verify → Learn) for AI/ML workloads: GPU cost tracking by type, cost per inference, spot recommendations (up to 70%), idle GPU prevention, right-sizing, and learning from outcomes—with real Cost Explorer validation (e.g. 20 to 30% savings).
4. **Adds AI-powered forecasting** (Amazon Bedrock Nova Lite): 7 to 30 day cost forecasts with confidence intervals for planning and avoiding surprises.
5. **Adds an AI cost advisor** (Amazon Bedrock) so you can ask things like “Why did my bill go up?” and get answers with real cost data, forecasts, and optimization suggestions.
6. **Scales to multiple accounts** via AWS Organizations, cross-account costs, and tag-based allocation.

We built a **React dashboard** (separate repo) so you can run “Run autonomous optimization,” see phase progress and savings, and explore cost, forecast, and advisor in one place.

---

### Why this matters

Small businesses and startups spending roughly $100 to $10,000 per month on AWS are the most exposed to surprise bills. A single $500 overrun can derail a monthly budget. The gap is not that cost tools do not exist. It is that they do not work for this segment: enterprise tools cost $500 or more per month, AWS native data is 24 hours behind, and AWS Budgets Actions only protect five services while most spend runs across 20+. Cost optimization is the number one priority for SMBs, and cost uncertainty is a real barrier to cloud adoption.

CostGuard AI addresses that by making prevention accessible, fast, and broad. It does not just alert; it acts, with safety guards and rollback. It runs at about $4 to $5 per month at typical usage (actual cost depends on usage) and is designed to stay within Free Tier where possible, so teams that cannot afford $500 per month tools get enterprise-style control. Detection happens in minutes from CloudWatch metrics, so you can prevent overruns instead of reacting after the fact. Prevention covers 20+ services with idle detection, budget thresholds, and per-action rollback so you can undo a specific stop within 24 hours. For AI and ML workloads we added GPU cost tracking, spot recommendations with up to 70% savings, and a self-optimizing loop that we validate with Cost Explorer at 20 to 30% savings in demo runs. For Commercial Solutions, that means measurable savings, less manual firefighting, and lower risk for teams that need to protect revenue without enterprise budgets.

---

### How I built this

**Technical approach:** We wanted cost prevention that acts (stops idle resources, rolls back) instead of only alerting, at a price SMBs can afford. So we built a serverless backend: a single Lambda for the core API that routes requests by path: Cost Explorer and DynamoDB for historical cost (Phase 1); CloudWatch metrics plus a pricing cache for near-real-time estimation (Phase 1.5); Amazon Bedrock Nova Lite for 7 to 30 day forecasts and the conversational cost advisor (Phases 2 and 4); and a prevention engine that uses a resource manager to discover resources across 22 AWS service types, an idle detector with service-specific criteria (e.g. EC2 CPU, RDS connections, Lambda invocations), safety guards, approval workflows, and per-action rollback (Phase 3). EventBridge runs budget monitoring on a schedule (e.g. every 5 minutes). For Phase 5 we added a separate Multi-account stack (Organizations, cross-account costs, allocation). For Phase 6 we added an AI/ML stack: a dedicated Lambda and API for GPU cost tracking, idle GPUs, cost per inference and cost per training, spot recommendations, and SageMaker/Bedrock cost tracking, all backed by Cost Explorer, CloudWatch, and the Pricing API. The autonomous loop (Phase 6 extension) lives in its own stack: an API Lambda that serves demo/start and demo-status plus the 5-phase loop (Analyze, Decide, Act, Verify, Learn) implemented with five Lambdas (GPU Scheduler, Spot Manager, Right Sizer, Learning Engine, Safety Guard), DynamoDB for action history, and EventBridge for orchestration. We validate outcomes with Cost Explorer so the 20 to 30% savings claim is grounded in real data. The React frontend (separate repo) calls the core and AI/ML APIs for cost, forecast, and advisor; for “Run autonomous optimization” it calls the Autonomous stack API (POST demo/start, GET demo-status).

**Architecture:** We use CDK and deploy four feature stacks (plus an optional BFF stack for Cognito auth). **(1) Core stack (Phases 1 to 4):** One Lambda, one API Gateway, and DynamoDB tables for cost data, forecast cache, prevention config, resource inventory, audit log, approval requests, and advisor cache/history. This stack handles cost fetch/query, cost estimation, forecast, prevention, and advisor endpoints. **(2) Multi-account stack (Phase 5):** Its own Lambda and API for Organizations, cross-account cost aggregation, and tag-based allocation. **(3) AI/ML stack (Phase 6):** Dedicated Lambda and API for GPU costs, idle GPUs, cost per inference, cost per training, spot recommendations and savings, and multi-account GPU costs, plus DynamoDB tables for GPU costs, workload classifications, and AI/ML cache. **(4) Autonomous stack (Phase 6 extension):** API Lambda for demo/start, demo-status, schedule analysis, action history, approve-action, rollback, and confidence scores; five Lambdas for the loop; DynamoDB for action history and training checkpoints; EventBridge custom bus; S3 for checkpoints; SNS for approvals and alerts. The frontend uses the Core (and optionally Multi-account) API for cost, forecast, and advisor, and the Autonomous stack API for the demo so “Run autonomous optimization” hits the real loop.

**AWS services used:**

| Service | Purpose | Why / Free Tier |
|--------|---------|------------------|
| **Lambda** | All API and business logic (cost, forecast, prevention, advisor, AI/ML, autonomous) | Serverless, scales to zero. Free Tier: 1M requests/month. |
| **API Gateway** | REST API, API key auth | Managed, Free Tier: 1M calls/month. |
| **DynamoDB** | Cost data, forecasts, config, inventory, audit, approvals, advisor cache/history, GPU costs, action history | Serverless. Free Tier: 25 GB, 25 RCU/WCU. |
| **Amazon Bedrock (Nova Lite)** | Cost forecasting, conversational advisor | 7 to 30 day forecasts and natural-language Q&A; we cache to limit cost. |
| **Cost Explorer API** | Historical cost data, GPU costs, savings validation | Needed for real numbers; 24h delay is an AWS limitation. |
| **CloudWatch** | Metrics for near-real-time estimation (EC2, Lambda, DynamoDB, S3, RDS) and GPU utilization | Standard metrics in Free Tier. |
| **EventBridge** | Scheduled prevention checks, autonomous loop orchestration | Free Tier: 14M events/month. |
| **SNS** | Notifications (budget alerts, prevention actions, autonomous approvals) | Free Tier: 1M publishes. |
| **AWS Budgets** | Thresholds for prevention (e.g. 80% warning, 90% action) | Used via API. |
| **S3** | Training checkpoints for autonomous learning | Free Tier: 5 GB, lifecycle for retention. |
| **IAM** | Roles for Lambda and cross-account access | No extra cost. |

**Kiro usage:** We used Kiro for about 65% of development in a spec-driven way: natural-language specs to Kiro-generated code to review and customize to deploy. Kiro was used heavily for Lambda handlers, Cost Explorer/CloudWatch integration, DynamoDB access patterns, Bedrock client and prompts, prevention logic (including resource discovery and idle detection), and tests (70 to 90% per phase where applicable). This kept velocity high while we kept control over architecture and safety (e.g. tag-based protection, rollback, dry-run).

**Key development milestones:**
- **Phase 1:** Cost data pipeline: Cost Explorer fetch, DynamoDB store and query by date range. Foundation for forecasts and advisor.
- **Phase 1.5:** Near-real-time estimation: CloudWatch metrics plus a pricing cache (24h) for EC2, Lambda, DynamoDB, S3, RDS so we estimate current spend in minutes.
- **Phase 2:** Bedrock forecasting: 7 to 30 day forecasts with confidence intervals; adaptive TTL and cache warming to limit Bedrock calls.
- **Phase 3:** Automated prevention: Resource discovery across 22 service types (EC2, RDS, Lambda, S3, DynamoDB, EBS, ElastiCache, Redshift, ECS, EKS, NAT Gateway, Elastic IP, load balancers, SNS, SQS, API Gateway, Step Functions, Glue, SageMaker, CloudFront); idle detection with service-specific criteria (e.g. EC2 CPU, RDS connections, Lambda invocations, EBS attached, S3 requests); budget monitoring; safety guards (tag protection, whitelists); action execution; approval workflows; 24h per-action rollback; EventBridge schedule.
- **Phase 4:** AI cost advisor: Bedrock for natural-language Q&A, context from cost data and forecasts and prevention, markdown responses, cache, and suggestions from idle resources and budget data.
- **Phase 5:** Multi-account: Organization discovery, cross-account cost aggregation, allocation rules, chargeback/showback; separate stack with its own Lambda and API.
- **Phase 6:** AI/ML workload cost: GPU cost tracking (Cost Explorer), workload classification (CloudWatch, EC2 tags), idle GPU detection, cost per inference and cost per training (CloudWatch + Cost Explorer), spot recommender (Pricing API, spot history), SageMaker and Bedrock cost tracking; 20 API endpoints.
- **Phase 6 extension:** Autonomous loop: API for demo/start, demo-status, schedule analysis, action history, approve-action, rollback, confidence scores; five Lambdas (GPU Scheduler, Spot Manager, Right Sizer, Learning Engine, Safety Guard); action history and checkpoint tables; Cost Explorer used to compute actual savings (20 to 30% in demo). Loop runs in ~5.26 seconds in our tests.
- **Frontend:** React dashboard (separate repo): cost, forecast, advisor, prevention, multi-account, AI/ML, and Demo page that calls the Autonomous API for “Run autonomous optimization” and polls demo-status for phase, progress, and cumulative savings.

**1,621 tests passing** (1,134 unit, 386 property, 101 integration); **~87% coverage**. **Expected running cost:** about \$4 to \$5/month at typical usage (Phases 1 to 6 + autonomous), designed to stay within Free Tier where possible; actual cost depends on usage (Cost Explorer and Bedrock calls, etc.).

---

### Demo

*[Insert screenshots or a video under 5 minutes here. Suggested: (1) Dashboard with “Run autonomous optimization” and phase progress; (2) Results: current phase, progress bar, cumulative savings; (3) Optional: Cost, Forecast, or Advisor screens.]*

**What the demo shows:** From the React app you can start “Run autonomous optimization.” The UI polls the backend and shows the current phase (Analyze → Decide → Act → Verify → Learn), overall progress, and cumulative savings. The autonomous loop runs in about **5.26 seconds** end-to-end in our tests, with savings validated via Cost Explorer (e.g. 20 to 30% in demo scenarios). You can also explore historical cost, forecasts, and the AI advisor from the same dashboard.

---

### What I learned

Along the way I gained a few insights that shaped how we built CostGuard AI and what I’d do again.

**Key insight: one entrypoint can carry many capabilities, but some features need their own home.** Early on we put cost fetch, estimation, forecast, prevention, and advisor behind a single Lambda and routing by path. That kept the surface area small and made it easy to add phases without new APIs. When we added multi account, AI/ML, and the autonomous loop, we gave them separate stacks and Lambdas; they needed their own EventBridge rules and handlers (e.g. the five Lambdas for the loop). Learning when to extend the router versus when to spin up a new stack was part of the journey and kept the codebase deployable and understandable.

**Key insight: if the product “acts” on resources, safety has to be in the code, not only in documentation.** We stop instances and change configs, so we had to design for mistakes. We implemented protected tags (so tagged production resources are never touched), pre action state storage and a 24 hour rollback window, dry run as the default, and approval workflows. Building those layers and reviewing every piece, including prevention and rollback code generated by Kiro, was what made me confident enough to ship automation that actually acts. I learned that “safety first” only works when it’s enforced in the implementation.

**Key insight: real data turns a claim into something you can defend.** At first the autonomous loop used mocks. Once we wired it to Cost Explorer and CloudWatch (Learning Engine for before and after savings, Safety Guard for budget checks, prevention for idle detection), the 20 to 30% savings claim became something we could validate and tune. I also learned where to cache (forecast, advisor, pricing) so we keep typical cost around $4 to $5 per month while still calling live APIs where it matters. Deciding when to cache versus when to call live was critical for both credibility and cost.

**Key insight: tests unlock refactors and new features.** We invested in unit, property based, and integration tests from the start (1,600+ tests now). That meant we could add the autonomous stack and the demo APIs without regressions, and change rollback or idle detection logic with a safety net. Writing specs and tests alongside each phase (and using Kiro for much of the handler and test code) kept the bar high. For my development journey, that discipline paid off every time we added a new phase.

**Key insight: phased delivery matched how we think about the product.** We built in order: cost data, then estimation, then forecast and advisor, then prevention with monitoring driven by EventBridge, then separate stacks for multi account, AI/ML, and autonomous. Each phase had a clear place and something shippable. Doing it in that order made “what we built” easy to explain and meant we never had to retrofit a monolith; a lesson I’ll take to the next project.

---

*Built with Kiro and AWS. CostGuard AI Team.*

---

**Before you publish:** Add a cover image in the Builder Center UI, insert your demo screenshots or video in the Demo section, and select tags: `#aideas-2025`, `#commercial-solutions`, and your region (`#EMEA`, `#NAMER`, `#APJC`, `#LATAM`, `#GCR`, or `#ANZ`).
