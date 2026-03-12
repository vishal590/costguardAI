# Demo Section: Which Screenshot Where + Captions

**Purpose:** Use your 7 frontend screenshots in the article Body **Demo** section in this order. Insert each with the **Image** tool and add the caption below it.  
**Aligned with:** [HACKATHON_COMPETITION_INFO.md](../HACKATHON_COMPETITION_INFO.md) (demo required; judging: Innovation, Efficiency, Practical impact).

---

## Order and captions (copy into Body)

**Intro (paste before first image):**  
The screenshots below show the CostGuard AI React dashboard: the autonomous optimization demo (Phase 6 Extension), near-real-time cost and cost history, AI-powered forecast, automated prevention, AI/ML workload costs (Phase 6), and multi-account (Phase 5).

| # | Your screenshot | Insert in Body as | Caption to add under the image |
|---|-----------------|-------------------|---------------------------------|
| 1 | **Demo** (Run autonomous optimization, phase progress, cumulative savings) | Image 1 | **Run autonomous optimization:** One click starts the 5-phase loop (Analyze → Decide → Act → Verify → Learn). The UI shows current phase, phase progress, overall progress, and cumulative savings. The loop runs in about 5.26 seconds in our tests, with projected 20–30% savings validated via Cost Explorer. |
| 2 | **Cost – Current estimate** (last 1h/24h/7d, total $0.0016, breakdown Lambda/DynamoDB/S3) | Image 2 | **Near-real-time cost estimate:** Rolling view for last 1 hour, 24 hours, or 7 days, with breakdown by service (EC2, Lambda, DynamoDB, S3, RDS). |
| 3 | **Prevention** (status Enabled, tabs Resources / Rollback / History) | Image 3 | **Automated prevention:** Budget monitoring, idle and at-risk resource detection, rollback of recent actions, and history. Prevention system status and managed resources. |
| 4 | **Forecast** (Service, Horizon 7/14/30 days, Granularity Daily/Weekly, chart area) | Image 4 | **AI-powered cost forecast (Bedrock Nova Lite):** Filter by service, horizon 7/14/30 days, daily or weekly granularity, with confidence band for planning. |
| 5 | **Cost – Cost history** (Fetch from Cost Explorer, table date/service/cost) | Image 5 | **Cost history from AWS Cost Explorer:** Fetch by date range, view and filter by service. Historical data for analysis and trends. |
| 6 | **AI/ML** (tabs: GPU costs, Idle GPUs, Spot recommendations, Cost per inference, SageMaker, Bedrock) | Image 6 | **AI/ML workload costs (Phase 6):** GPU costs by workload type, idle GPU detection, spot recommendations (up to 70% savings), cost per inference, SageMaker and Bedrock cost tracking. Requires Phase 6 AI/ML backend when deployed. |
| 7 | **Multi-account** (Organizations & costs, Consolidated, Allocation, Budgets) | Image 7 | **Multi-account cost visibility (Phase 5):** Organizations and accounts, consolidated costs, tag-based allocation, and hierarchical budgets for teams using AWS Organizations. |

**Outro (paste after last image):**  
From the React app you can start "Run autonomous optimization" and watch the system move through Analyze → Decide → Act → Verify → Learn, with progress and cumulative savings. The autonomous loop runs in about **5.26 seconds** end-to-end in our tests. You can also explore near-real-time cost, cost history from Cost Explorer, AI-powered forecast, prevention status and resources, AI/ML GPU and spot insights, and multi-account views from the same dashboard.

---

## Screenshot file hints (from your assets)

| Screenshot | Likely asset filename (for your reference) |
|------------|--------------------------------------------|
| Demo (Phase 6 Extension) | `phase_6_extension-9befa662-...png` |
| Cost (current estimate) | `phase__1-753756bb-...png` or `phase_1-47700231-...png` |
| Prevention | `phase_3-68fc1c05-...png` |
| Forecast | `phase_2-79254dfa-...png` |
| Cost (cost history) | (second Cost screenshot) |
| AI/ML | `phase_6-e8e1c76f-...png` |
| Multi-account | `phase_5-0959e056-...png` |

**Note on AI/ML screenshot:** If it shows the "Phase 6 AI/ML backend" warning banner, keep it—the caption already says "Requires Phase 6 AI/ML backend when deployed," so readers understand the UI is built and the backend is deployable.

---

## Cover image suggestion

Use **Demo** (Run autonomous optimization) or **Cost (current estimate)** as the article cover image in the Builder Center UI for strongest impact.
