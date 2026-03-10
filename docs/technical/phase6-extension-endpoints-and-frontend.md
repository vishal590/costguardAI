# Phase 6 Extension (Autonomous): Endpoints vs Frontend Integration

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
