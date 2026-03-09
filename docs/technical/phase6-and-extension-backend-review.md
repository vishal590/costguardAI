# Phase 6 & Phase 6 Extension: Backend Review and Integration Guide

**Purpose:** After a full read of the backend code, this doc answers: what we built, why we built it, how it works, use cases, how Phase 6 and Phase 6 Extension relate to each other and to the whole CostGuard AI app, and how to integrate them (backend vs frontend).

**Last updated:** March 2026

---

## 1. CostGuard app at a glance

| Phase | What it does | Where it lives (backend) |
|-------|----------------|---------------------------|
| 1 | Cost data fetch/query (Cost Explorer), cost estimation | Main Lambda, main API |
| 2 | Cost forecast | Main Lambda, main API |
| 3 | Prevention (budget + idle + actions + rollback) | Main Lambda, main API |
| 4 | Advisor (Bedrock Q&A, suggestions) | Main Lambda, main API |
| 5 | Multi-account (organizations, consolidated costs) | MultiAccountStack or stub in main Lambda |
| **6** | **AI/ML workload cost (GPU, SageMaker, Bedrock, spot, etc.)** | **AIML stack: separate API + separate Lambda** (or main Lambda if routes added) |
| **6 Extension** | **Autonomous action loops (analyze → decide → act → verify → learn)** | **AutonomousStack: 5 Lambdas + EventBridge, no REST API for “run loop”** |

---

## 2. Phase 6: AI/ML Workload Cost Management — What We Built

### 2.1 Entry point and routing

- **Handler:** `src/ai_ml_handler.py` — single `handler(event, context)` for API Gateway.
- **Routing:** By `httpMethod` and `path.endswith(...)`. Supports 20+ endpoints (see list below).
- **How it’s invoked today:** Only when a request hits an API that has `/api/ai-ml/*` and is sent to a Lambda that runs this handler. The **main** Lambda has a branch: if path contains `'/ai-ml/'` it delegates to `ai_ml_handler.handler`. The **main CDK stack does not define** `/api/ai-ml` on its API Gateway, so the main API URL never receives these paths. They are only reachable on the **AIML stack API** (separate RestApi + separate Lambda “CostGuard-AIMLHandler”).

### 2.2 Endpoints (what we built)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/gpu-costs` | GET | GPU costs from Cost Explorer (EC2 GPU instances), optional workload/instance filter; uses cache |
| `/gpu-utilization` | GET | **501 Not Implemented** |
| `/idle-gpus` | GET | Idle GPU detection (threshold), wasted cost and idle hours |
| `/gpu-prevention` | POST | Trigger GPU prevention (idle stop/terminate) |
| `/gpu-cost-savings` | GET | GPU cost savings report |
| `/workload-classification` | GET | Classify workload for one instance (instance_id + dates) |
| `/workload-classification` | POST | Manual override: set workload_type (training/inference/idle) for an instance |
| `/cost-per-inference` | GET | Cost per inference (model, endpoint, date range); cached |
| `/inference-trends` | GET | Cost trends over days for a model |
| `/cost-per-training` | GET | Cost per training job (job_id); cached |
| `/training-comparison` | GET | Compare instance types for a model (savings vs baseline) |
| `/spot-recommendations` | GET | **Requires workload_id** (not start/end date) — spot suitability for one workload |
| `/spot-savings` | GET | Spot vs on-demand savings for instance type(s) |
| `/sagemaker-costs` | GET | SageMaker costs by date range (training/inference/notebook); cached |
| `/sagemaker-idle-endpoints` | GET | Idle SageMaker endpoints |
| `/bedrock-costs` | GET | Bedrock costs by date range; cached |
| `/bedrock-cost-per-invocation` | GET | Cost per invocation |
| `/multi-account/gpu-costs` | GET | GPU costs across accounts |
| `/multi-account/gpu-utilization` | GET | GPU utilization across accounts |
| `/multi-account/top-gpu-accounts` | GET | Top GPU spending accounts |

All that take dates expect `start_date` and `end_date` in `YYYY-MM-DD`. Many use `AIMLCacheManager` (DynamoDB) for caching.

### 2.3 Backend services (how it’s built)

- **`src/services/ai_ml/`**  
  - **gpu_cost_tracker.py** — Cost Explorer (EC2, grouped by instance type etc.), filters GPU instance patterns (p3, p4, g4, g5, …), returns `GPUCostData` (cost, gpu_hours, workload_type, utilization, etc.).  
  - **workload_classifier.py** — Classify workload (training/inference/idle) from CloudWatch or manual override; stores in DynamoDB.  
  - **idle_detector.py** — Idle GPU detection (threshold).  
  - **cost_per_inference_calculator.py** — Cost per inference (model/endpoint, date range).  
  - **cost_per_training_calculator.py** — Cost per training job, instance comparison.  
  - **spot_instance_recommender.py** — Spot recommendations **per workload_id**; spot savings by instance type.  
  - **sagemaker_cost_tracker.py** — SageMaker cost tracking.  
  - **bedrock_cost_tracker.py** — Bedrock cost tracking.  
  - **ai_ml_cache_manager.py** — Cache layer (DynamoDB).  
  - **prevention_integration.py** — GPU prevention (idle stop/terminate).

- **DynamoDB (AIML stack):**  
  - `costguard-gpu-costs`  
  - `costguard-workload-classifications`  
  - `costguard-aiml-cache`  

- **Dependencies:** Cost Explorer, CloudWatch, Pricing (where used), DynamoDB. No dependency on Phase 6 Extension.

### 2.4 Why we built Phase 6

- **Hackathon/product fit:** AI/ML workload cost is a “painkiller” for AI startups (GPU = large share of spend).  
- **Differentiation:** GPU cost by workload type (training vs inference vs idle), cost-per-inference, cost-per-training, spot recommendations — positioned as something competitors don’t do well.  
- **Use cases:**  
  - See where GPU money goes (by instance, workload type, time).  
  - Decide what to optimize (idle GPUs, over-provisioned training, inference choice).  
  - Get spot recommendations and savings estimates for specific workloads.  
  - Track SageMaker/Bedrock costs and unit costs.

---

## 3. Phase 6 Extension: Autonomous Action Loops — What We Built

### 3.1 High-level flow

A **5-phase loop**: Analyze → Decide → Act → Verify → Learn.

- **Analyze:** GPU Scheduler reads GPU cost patterns (from DynamoDB `costguard-gpu-costs`), finds “optimization windows,” emits **ScheduleRecommendation** events.  
- **Decide:** Safety Guard receives **ActionRequest** events, validates, optionally requests approval (SNS), then emits approval/denial; can create rollback capability.  
- **Act:** Right Sizer (and Spot Manager for spot interruptions) perform the actual optimization actions (e.g. right-size, migration).  
- **Verify:** Action outcomes are recorded (e.g. in action history).  
- **Learn:** Learning Engine consumes **ActionCompleted** (and history), updates success rates and confidence; can adjust thresholds.

Events flow on a **custom EventBridge bus** (`costguard-autonomous-events`). Lambdas are triggered by:

- **Schedule:** GPU Scheduler (hourly), Right Sizer (daily 02:00 UTC), Learning Engine (daily 03:00 UTC and on ActionCompleted).  
- **Events:** Safety Guard on ActionRequest; Spot Manager on SpotInterruptionDetected; Learning Engine on ActionCompleted.

There is **no REST API in AutonomousStack** to “start” or “stop” a loop. The loop runs on schedule and/or in response to events.

### 3.2 Lambdas and tables (AutonomousStack)

| Lambda | Handler | Trigger | Role |
|--------|--------|--------|------|
| CostGuard-GPU-Scheduler | `autonomous.gpu_scheduler.handler` | Hourly EventBridge schedule (and can be invoked with body for API-style params) | Reads GPU_COSTS_TABLE, writes action history, puts ScheduleRecommendation events |
| CostGuard-Spot-Manager | `autonomous.spot_manager.handler` | EventBridge: SpotInterruptionDetected | Checkpoints, fallback, puts ActionRequest |
| CostGuard-Right-Sizer | `autonomous.right_sizer.handler` | Daily 02:00 UTC | Utilization analysis, migration recommendations |
| CostGuard-Learning-Engine | `autonomous.learning_engine.handler` | Daily 03:00 UTC + ActionCompleted events | Reads action history, updates success rates, confidence |
| CostGuard-Safety-Guard | `autonomous.safety_guard.handler` | EventBridge: ActionRequest | Validates, approval flow, puts approval/denial events |

Tables (in or referenced by AutonomousStack): `costguard-action-history`, training checkpoints, migration rollbacks; S3 for checkpoints; SNS for approvals/alerts. **GPU_COSTS_TABLE** is set to `costguard-gpu-costs` — same name as Phase 6’s GPU cost table, so when both stacks are deployed in the same account, the autonomous loop reads the same GPU cost data that Phase 6 can write/populate.

### 3.3 How the “demo” runs today

- **Not via the web UI.** The Demo page in the frontend calls the **main** API:  
  - `POST /api/autonomous/demo/start`  
  - `GET /api/autonomous/demo-status`  
  Those are implemented in the **main** Lambda as a **stub**: they always return 200 and a static “idle” demo-status (or a “deploy AutonomousStack” message). They do **not** invoke the autonomous Lambdas or EventBridge.

- **Real demo:** Run locally with `scripts/run_demo_mode.py`. That script **invokes the five autonomous Lambdas by name** (RequestResponse), in order: GPU Scheduler → Safety Guard → Right Sizer → Learning Engine (and Spot Manager as needed). So the “loop” is orchestrated **outside** the deployed API (script + Lambda invoke). Demo mode completes in ~5 seconds when the Lambdas are deployed.

### 3.4 Why we built Phase 6 Extension

- **Close the loop:** Not just “show costs and recommendations” but **analyze → decide → act → verify → learn** with safety (approval, rollback) and learning.  
- **Use cases:**  
  - Automatically find GPU optimization windows and emit recommendations.  
  - Validate and approve risky actions (Safety Guard).  
  - React to spot interruptions (Spot Manager).  
  - Right-size based on utilization.  
  - Improve over time from outcomes (Learning Engine).

---

## 4. How Phase 6 and Phase 6 Extension relate

- **Data:** Phase 6 (AI/ML) can **produce** GPU cost and classification data (via API calls that use Cost Explorer, etc.). That data is stored in tables such as `costguard-gpu-costs` (when using the AIML stack). Phase 6 Extension (Autonomous) **consumes** `costguard-gpu-costs` in the GPU Scheduler. So Phase 6 “feeds” the autonomous loop with GPU cost data when both stacks use the same table name in the same account.  
- **No direct API call between them:** Extension does not call Phase 6’s REST API. It reads from DynamoDB (and EventBridge).  
- **Deployment:** Phase 6 = AIML stack (optional): separate API + AIML Lambda. Phase 6 Extension = Autonomous stack (optional): 5 Lambdas + EventBridge + tables. Main stack = Phases 1–4 + stub for Phase 5 + **stub** for autonomous demo (no real loop).

---

## 5. How they fit into the whole CostGuard app

- **Phases 1–4:** Core cost visibility, forecast, prevention, advisor — one main API and one main Lambda.  
- **Phase 5:** Multi-account — either separate stack + separate API or stub on main API.  
- **Phase 6:** AI/ML workload cost — **optional**; today only on AIML stack (separate API + Lambda). Use case: “Where is my GPU/SageMaker/Bedrock money going, and what can I optimize?”  
- **Phase 6 Extension:** Autonomous optimization — **optional**; EventBridge + 5 Lambdas, no REST “run” API. Use case: “Automatically analyze and act on GPU/cost patterns, with safety and learning.”  
- **Demo page:** Today it only talks to the main API and gets a **stub** response (idle state / “deploy AutonomousStack”). A **real** demo requires either: (1) running `scripts/run_demo_mode.py` against deployed autonomous Lambdas, or (2) adding an API that starts a run (e.g. invokes the first Lambda or puts an event) and a way to expose “demo status” from the autonomous run (e.g. from action history or a small state table).

---

## 6. Current integration gaps

| Gap | Current state | Impact |
|-----|----------------|--------|
| Phase 6 AI/ML on main API | Main stack has no `/api/ai-ml` routes. Main Lambda has delegation code but never receives `/ai-ml` requests. | Frontend using only the main API URL cannot call any Phase 6 AI/ML endpoint. |
| Phase 6 AI/ML on frontend | No dedicated “Phase 6 AI/ML” page that calls `/api/ai-ml/*`. | Users don’t see GPU costs, spot recommendations, etc. in the app. |
| Autonomous demo from UI | Demo start/status are stubs on main Lambda. No API triggers the real loop; no API reads real run state. | Clicking “Run” on the Demo page does nothing visible; real demo is script-only. |
| Single API URL | Frontend typically has one base URL (main API). Phase 6 is on a different API (AIML). | To use Phase 6 from the app, either add routes to the main API or add a second base URL and a Phase 6 AI/ML page that uses it. |

---

## 7. Recommendations (what to do in backend vs frontend)

### Option A — Minimal (no CDK/main Lambda changes)

- **Frontend:**  
  - Add a **“Phase 6 AI/ML”** page and nav item.  
  - Use **AIML stack API base URL** when configured (e.g. `VITE_AIML_API_BASE_URL`). If unset, show a short message: “Configure AIML API URL to see Phase 6 AI/ML data.”  
  - For **Demo:** Keep current behavior; add one line of copy: “For a full autonomous demo, run `scripts/run_demo_mode.py` with AutonomousStack deployed.”  
- **Backend:** No change. Phase 6 remains on AIML stack only; demo remains stub on main API.

### Option B — Phase 6 on main API (one URL)

- **Backend:** In **main** CDK stack, add `/api/ai-ml` (e.g. proxy `{proxy+}`) so the main Lambda receives `/api/ai-ml/*`. Main Lambda already delegates to `ai_ml_handler` when path contains `'/ai-ml/'`. Ensure main Lambda package includes `ai_ml_handler` and `services.ai_ml` (and deps). Watch Lambda package size (250MB limit; AIML was split out partly for this).  
- **Frontend:** Same “Phase 6 AI/ML” page, but call the **main** API base URL (no second URL).  
- **Demo:** Still stub unless you add a real “demo run” API (see Option C).

### Option C — Real autonomous demo from UI

- **Backend:**  
  - Add a small “demo run” state (e.g. DynamoDB item or minimal table).  
  - `POST /api/autonomous/demo/start`: e.g. put event on EventBridge to start analyze, or invoke GPU Scheduler Lambda with demo payload; set “run started” state.  
  - `GET /api/autonomous/demo-status`: read from action history or demo state and return current phase, progress, savings (or keep stub if AutonomousStack not deployed).  
- **Frontend:** Demo page keeps polling demo-status; when backend is wired, it shows real progress.  
- Requires AutonomousStack deployed and main Lambda (or a dedicated orchestrator) able to invoke Lambdas or put events.

---

## 8. Summary

- **Phase 6** = AI/ML workload cost (GPU, SageMaker, Bedrock, spot, workload classification, cost-per-inference/training). Implemented in `ai_ml_handler.py` and `services/ai_ml/*`. Exposed only on AIML stack API today; main Lambda has delegation but main API has no routes.  
- **Phase 6 Extension** = Autonomous 5-phase loop (analyze/decide/act/verify/learn) via EventBridge and 5 Lambdas; reads Phase 6’s GPU cost table; no REST “run” or “status” in the autonomous stack; demo is script-driven.  
- **Relation:** Phase 6 produces GPU (and related) cost data; Phase 6 Extension consumes it and runs the autonomous loop. They integrate via shared table name and events, not via REST.  
- **Integration:** To make Phase 6 visible in the app, add a frontend page and either a second API URL (AIML) or main-API routes (Option B). To make the Demo page “do something” real, add backend demo start/status that drive or reflect the autonomous run (Option C).
