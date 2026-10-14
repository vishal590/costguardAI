# Phase 6 Extension (Autonomous): Endpoints vs Frontend Integration

> Current confidence/statistics behavior is defined by [stored-outcome observations](autonomous-action-observation-contracts.md). Earlier numeric confidence/default examples are superseded. All continuing validation remains deferred.


> **Backend/frontend contracts reviewed October 14, 2026.** The sibling frontend was updated and built locally. Historical hook/tab entries below describe earlier integration; live browser/API behavior remains unverified. See [current API contracts](api-design.md) and [known limitations](documentation-code-sync.md).

**Purpose:** Checklist of Phase 6 Extension (autonomous action loops) backend endpoints and frontend integration.

**Backend:** `src/autonomous_handler.py` implements the full REST API. The **Autonomous stack** (CostGuardAutonomousStack) has its own API Gateway and Lambda (CostGuard-Autonomous-API) that serves all `/api/autonomous/*` endpoints. The main stack does not expose autonomous routes; use the Autonomous stack API URL.

**Autonomous stack (autonomous_stack.py):** All 9 routes are defined on the Autonomous stack API and wired to the Autonomous API Lambda.

---

## Autonomous handler endpoints (all integrated)

| # | Method | Endpoint | Purpose | Frontend (apiSlice + UI) |
|---|--------|----------|----------|---------------------------|
| 1 | POST | `/api/autonomous/schedule-analysis` | Trigger GPU Scheduler analysis | ✅ runScheduleAnalysis, “Schedule analysis” tab |
| 2 | GET | `/api/autonomous/action-history` | List autonomous actions (filters) | ✅ getActionHistory, “Action history” tab |
| 3 | POST | `/api/autonomous/approve-action` | Approve a pending action | ✅ approveAutonomousAction, “Approve action” tab |
| 4 | POST | `/api/autonomous/rollback` | Rollback an autonomous action | ✅ autonomousRollback, “Rollback” tab |
| 5 | GET | `/api/autonomous/confidence-scores` | Learning engine confidence scores | ✅ getConfidenceScores, “Confidence scores” tab |
| 6 | GET | `/api/autonomous/demo-status` | Current demo phase, progress, savings | ✅ getDemoStatus, “Demo run” tab |
| 7 | POST | `/api/autonomous/demo/start` | Start autonomous demo run | ✅ startDemo, “Demo run” tab |
| 8 | POST | `/api/autonomous/demo/reset` | Reset demo state | ✅ resetDemo, “Demo run” tab |
| 9 | POST | `/api/autonomous/demo/trigger-interruption` | Simulate spot interruption (demo) | ✅ triggerDemoInterruption, “Demo run” tab |

---

## Summary

- **Backend:** Autonomous stack has its own API Gateway + Lambda (CostGuard-Autonomous-API) serving all 9 paths. Lambda env: `ACTION_HISTORY_TABLE`, `EVENT_BUS_NAME`, `GPU_SCHEDULER_FUNCTION`, `LEARNING_ENGINE_FUNCTION`, `DEMO_MODE`, `CHECKPOINTS_BUCKET`. Role has DynamoDB (action-history), EventBridge PutEvents, and Lambda invoke for GPU Scheduler and Learning Engine.
- **Frontend:** Set `VITE_AUTONOMOUS_API_BASE_URL` to the Autonomous stack API URL (output **AutonomousAPIUrl**). Phase 6 Demo page (`/demo`) has 6 tabs; all 9 endpoints have apiSlice hooks and UI. When the URL is not set, the Demo page shows an info alert and skips requests.

**Troubleshooting OPTIONS 403:** If you see `OPTIONS 403 Forbidden` on `/api/autonomous/demo-status` (and other autonomous paths), you are almost certainly using the **wrong base URL**. The AI/ML stack API (e.g. `chcymuh4qi...`) only has `/api/ai-ml/*` routes. The Autonomous stack has a **separate** API with `/api/autonomous/*`. Use the **AutonomousAPIUrl** output from `cdk deploy CostGuardAutonomousStack` for `VITE_AUTONOMOUS_API_BASE_URL`, not the AI/ML API URL.

**Troubleshooting CORS error on GET/POST:** If preflight (OPTIONS) succeeds but the actual request shows "CORS error" in the browser, the Lambda response must include `Access-Control-Allow-Origin` (e.g. in `autonomous_handler.py`, all responses use `CORS_HEADERS`). Redeploy the Autonomous stack so the handler returns CORS on every response.

**Behaviour (no config):** Demo-status phase and progress are time-based (0–10 min after demo/start). When phase is `completed`, in-progress actions older than 10 minutes are excluded from the count so the payload is consistent. Schedule-analysis returns payload only (e.g. `recommendations`, `analysis_timestamp`, `dry_run_mode`); empty `recommendations` is valid when there are no scheduling opportunities.

## Approval and Rollback Contract

`POST /api/autonomous/approve-action` requires `request_id`, `action_id`, `signature` (non-empty strings) and `approved` (boolean). The signature is provided with the approval notification; use it for either approval or rejection. An accepted event returns **202** with `status: "approval_submitted"`, `approved`, `action_id` and `request_id`. Frontend clients must treat this as submission and refresh action history to see the stored decision.

The `costguard.autonomous.api` event rule sends `ActionApproved`, `ActionRejected` and `RollbackRequested` to Safety Guard. Approval processing validates the stored HMAC and 15-minute approval deadline (separate from retention TTL), finds the matching request among audit entries, conditionally updates its decision and emits an execution request. Identical retries are accepted; an opposite decision cannot overwrite an applied decision. Failed EventBridge entries return 500 at the API. A 202 response can precede worker validation failure.

A sixth worker executes supported approved EC2 operations and restores persisted resource state on rollback. Execution defaults to disabled until the CDK deployment parameter is explicitly enabled. Schedule-analysis accepts an optional workload target and cost estimate. Replacement requests require a versioned launch template, runtime and cost estimate. The optional EC2 reference training contract restores model/optimizer state and verifies progress; other models need adapters; demo progress remains elapsed-time based. See [execution and rollback](autonomous-execution.md).

## Training Request Integration

The sibling frontend now collects explicit source instance/job/type and replacement JSON, preserves optional training configuration and validates checkpoint/job fields before submission. Interruption and approval responses are treated as asynchronous acknowledgements. Schedule analysis preserves an optional executable target and defaults to dry run. Empty approval signatures are prevented and masked.

Action history polls every three seconds while open, showing lifecycle status, verified training steps/loss/checkpoints and the last recorded error. Approval and rollback use the new `action_id` history filter. BFF-only configuration enables the page. Demo progress is identified as elapsed-time based; approved actions may modify opted-in resources when execution is enabled. See [EC2 training resume](ec2-training-resume.md) and [source synchronization](documentation-code-sync.md).
