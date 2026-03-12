# Backend Repo Review (Docs + Code)

**Date:** March 2026  
**Scope:** aws-ideas repo — documentation, code (src, infrastructure), and alignment with ARTICLE_DRAFT and submission requirements.

---

## 1. Executive summary

- **Code structure:** Matches the phased design. Handlers (`lambda_handler.py`, `ai_ml_handler.py`, `autonomous_handler.py`) route correctly; services are organized by phase and domain.
- **Infrastructure:** Five CDK stacks (CostGuardStack, MultiAccountStack, AIMLStack, AutonomousStack, BFFStack). Article’s “three stacks” is correct when grouping Core, Multi-account, and AI/ML+Autonomous (BFF is auth-only).
- **Docs vs code:** PROJECT_STATUS, ARTICLE_DRAFT, and technical docs are aligned on phases, features, and cost (~$4–5/month). A few doc/code mismatches and stale numbers were found and are listed below.
- **Recommendations:** Fix the inconsistencies in this review; optional: run full pytest and set README/INDEX to the actual test count and article deadline.

---

## 2. Code structure (verified)

### 2.1 Handlers and routing

| Handler | Responsibility | Notes |
|--------|----------------|-------|
| `lambda_handler.py` | Phase 1–4 + Phase 5 stub + delegates `/ai-ml/*` to `ai_ml_handler` | EventBridge budget events; no `/api/autonomous/*` (lives in Autonomous stack). |
| `ai_ml_handler.py` | All `/api/ai-ml/*` | gpu-costs, idle-gpus, cost-per-inference, cost-per-training, spot-recommendations, spot-savings, multi-account/gpu-costs, etc. |
| `autonomous_handler.py` | Autonomous API (separate stack) | schedule-analysis, action-history, approve-action, rollback, confidence-scores, **demo-status**, **demo/start**, demo/reset, demo/trigger-interruption. |

- Main stack API does **not** serve `/api/autonomous/*`; frontend must use Autonomous stack API URL for demo (documented in `phase6-extension-endpoints-and-frontend.md`).
- Phase 5 multi-account: main Lambda returns stub when MultiAccountStack URL not used; full API in MultiAccountStack.

### 2.2 Services (src/services, src/autonomous)

- **Phase 1–2:** cost_explorer, dynamodb, historical_data, forecast_engine, forecast_cache, bedrock_client, pricing_manager, cost_estimator, cloudwatch_collector.
- **Phase 3:** prevention_engine, budget_monitor, resource_manager, idle_detector, safety_guard, action_executor, approval_manager, rollback_manager, notification_service, eventbridge_scheduler.
- **Phase 4:** advisor_engine, query_processor, context_manager, bedrock_advisor_client, response_formatter, advisor_cache_manager, insight_generator.
- **Phase 5:** multi_account/* (organization_discovery, cost aggregation, allocation, etc.).
- **Phase 6:** ai_ml/* (gpu_cost_tracker, workload_classifier, idle_detector, spot_instance_recommender, cost_per_inference/training, sagemaker/bedrock cost trackers, etc.).
- **Autonomous:** autonomous/* (gpu_scheduler, spot_manager, right_sizer, learning_engine, safety_guard, utils).

Structure matches PROJECT_STATUS and the article.

### 2.3 Infrastructure (infrastructure/app.py)

- **CostGuardStack** — Phases 1–4  
- **CostGuardMultiAccountStack** — Phase 5  
- **CostGuardAIMLStack** — Phase 6  
- **CostGuardAutonomousStack** — Phase 6 extension (depends on AIML)  
- **CostGuardBFFStack** — Cognito + BFF (no dependency on other stacks)

Article’s “Three CDK/CloudFormation stacks” is correct if interpreted as (1) Core, (2) Multi-account, (3) AI/ML + autonomous. BFF is not counted as a “feature” stack.

---

## 3. Documentation vs code

### 3.1 Prevention services: 22 vs 20+

- **PROJECT_STATUS / technical:** “22 AWS services (20 with idle detection)”.
- **SERVICES-WHERE-DATA-APPEARS.md:** “22 AWS service types” for Phase 3 Resource Manager.
- **Article / pitch:** “20+ services” — conservative and correct (22 total, 20 with idle logic).

No change needed; “20+” is accurate.

### 3.2 Test counts

- **PROJECT_STATUS.md:** 1621 passing (1134 unit + 386 property + 101 integration); Phase 6: 41 unit; Phase 6 Extension: 171 unit; 14 integration for autonomous.
- **ARTICLE_DRAFT.md:** “1,621 tests passing” — aligned.
- **README.md:** “1,434 tests passing” and breakdown “962 unit, 386 property, 126 integration” — **outdated** and inconsistent with PROJECT_STATUS.

**Recommendation:** Update README test section to “1,621 tests passing (1,134 unit + 386 property + 101 integration)” and the same breakdown as PROJECT_STATUS, or run `pytest --co` / full run and set numbers from that.

### 3.3 Article deadline (INDEX.md)

- **SEMI_FINALIST_SELECTION_EMAIL.md (authoritative):** Article due **March 13, 2026, 8:00 PM UTC** (12:00 PM PT).
- **INDEX.md Quick Reference:** “Article Deadline: March 13, 2026 **11:59pm PT**” — **wrong** (that would be ~20:59 UTC next day).

**Recommendation:** Change INDEX.md to “March 13, 2026 8:00 PM UTC (12:00 PM PT)” so it matches the official email.

### 3.4 Cost ($4–5/month)

- Already aligned: ARTICLE_DRAFT and PROJECT_STATUS use “about $4–5/month at typical usage” and “~$4.51” breakdown; dependency on usage is stated. README still has “~$4.01” in one place; PROJECT_STATUS is the single source of truth with the full breakdown.

### 3.5 Autonomous demo endpoints

- **autonomous_handler.py** implements: `/demo/start`, `/demo-status`, plus schedule-analysis, action-history, approve-action, rollback, confidence-scores, demo/reset, demo/trigger-interruption. Frontend “Run autonomous optimization” → POST demo/start, GET demo-status — matches AGENTS.md and article.

---

## 4. Doc set overview

- **Submission:** ARTICLE_DRAFT, HOW_TO_WRITE_ARTICLE, SEMI_FINALIST_SELECTION_EMAIL, requirements, FORM-FIELD_RESPONSES, DEMO_SCREENSHOTS_AND_CAPTIONS — consistent with each other and with code.
- **Status:** PROJECT_STATUS is up to date (phases, costs, test counts, deployment). INDEX and DOCUMENTATION_MAP point to the right places.
- **Technical:** Phase READMEs, SERVICES-WHERE-DATA-APPEARS, phase6-extension-endpoints-and-frontend, autonomous docs — match handler routing and stack layout.
- **Older/optional:** Some deployment and test-summary docs mention older test totals (e.g. 1236, 1246); they don’t contradict the current “1,621” if PROJECT_STATUS is treated as canonical.

---

## 5. Gaps and minor issues

1. **README test numbers:** “1,434 tests” and “962 unit, 386 property, 126 integration” should be updated to match PROJECT_STATUS (1,621 and 1134/386/101) or to a fresh pytest run.
2. **INDEX.md article deadline:** Use “8:00 PM UTC (12:00 PM PT)” instead of “11:59pm PT”.
3. **README cost:** Optional: add a line that PROJECT_STATUS has the authoritative monthly cost breakdown (~$4.51) so readers know where to look.
4. **Phase 4 “PENDING DEPLOYMENT”:** INDEX.md still says “Phase 4 (CODE COMPLETE - PENDING DEPLOYMENT)”. If Phase 4 is deployed in your environment, update that line to “DEPLOYED” or remove “PENDING DEPLOYMENT”.

---

## 6. Checklist (for article and submission)

- [x] Article cost: “about $4–5/month at typical usage” with usage dependency.
- [x] Why this matters: 20+, enterprise-style, per-action rollback, $4–5, Free Tier.
- [x] How I built this: Technical approach, architecture (three stacks), AWS table, Kiro, development milestones, tests 1,621, coverage ~87%.
- [x] Demo: Autonomous demo/start + demo-status; 5.26s; 20–30% savings (validated with Cost Explorer).
- [ ] README test count updated to 1,621 (or current pytest count).
- [ ] INDEX.md article deadline set to 8:00 PM UTC (12:00 PM PT).

---

**Conclusion:** Backend repo (docs + code) is in good shape and supports the article and submission. Fixing the README test count and INDEX deadline will remove the only clear inconsistencies found in this review.
