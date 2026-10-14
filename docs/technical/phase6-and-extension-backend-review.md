# Phase 6 and Autonomous Extension -> Backend Review

> **SageMaker source update (October 14, 2026):** The [current SageMaker contract](sagemaker-observed-contracts.md) supersedes earlier SageMaker estimates and endpoint-idle claims. This does not certify GPU/Bedrock paths or rerun any historical tests. Further validation remains deferred.

**Source review:** October 4, 2026. Backend source only; the separate frontend and live deployment were not inspected.

## What Is Implemented

Phase 6 uses `src/ai_ml_handler.py` and `src/services/ai_ml/` for GPU costs/utilization, classification, inference/training unit costs, spot recommendations, SageMaker, Bedrock and multi-account GPU services. `CostGuardAIMLStack` defines twenty API methods under `/api/ai-ml` and three tables. GPU utilization is implemented, including GPU metric lookup and CPU fallback.

The autonomous extension uses six workers (GPU Scheduler, Spot Manager, Right Sizer, Learning Engine, Safety Guard, Action Executor), EventBridge, checkpoints and action history. `CostGuardAutonomousStack` also defines **a separate REST API and API Lambda with nine routes**, including analysis, history, approval, rollback, confidence and demo start/status/reset/interruption. The API handler is `src/autonomous_handler.py`.

## Integration and URLs

Use `AIMLAPIEndpoint` for AI/ML and `AutonomousAPIUrl` for autonomous requests. The main Lambda has AI/ML delegation code, but the main API does not define AI/ML or autonomous routes. Its old autonomous stub helper is not routed by the current handler.

With BFF, use `BFFApiUrl` and a Cognito access token; the BFF selects the AI/ML and autonomous backend URLs from configuration. There is no requirement to add a new autonomous API merely to expose the already-defined routes.

## Shared Data and Execution

The autonomous workers reference the AI/ML GPU-cost table `costguard-gpu-costs`. Deploy in the app's dependency order: main -> multi-account -> AI/ML -> autonomous. BFF is configured separately.

Demo/start requires `DEMO_MODE=true`, asynchronously invokes GPU Scheduler and writes a start record. Demo/status derives progress from elapsed time and action records. `scripts/run_demo_mode.py` is an additional script-based demo path. Neither a fast script run nor elapsed-time status establishes verified production savings.

Approval/rejection and rollback APIs publish from `costguard.autonomous.api`; an explicit CDK rule targets Safety Guard. Demo interruption events target Spot Manager. Safety Guard validates signed decisions against unexpired pending requests and updates their status atomically. Approval acceptance is asynchronous. A sixth worker executes approved EC2 changes, persists recovery state, restores resources on rollback and sends completion events to Learning Engine. Execution defaults to disabled; see [supported execution scope](autonomous-execution.md).

## GPU Routing

The `/multi-account/gpu-costs` and `/multi-account/gpu-utilization` checks precede the generic GPU suffixes and call their dedicated handlers. Multi-account top-GPU-accounts retains its own branch. Offline regression tests cover all four single/multi-account cost and utilization dispatch paths.

## Current References

- [Complete API contracts](api-design.md)
- [AI/ML endpoint checklist](phase6-aiml-endpoints-and-frontend.md)
- [Autonomous endpoint checklist](phase6-extension-endpoints-and-frontend.md)
- [BFF deployment](../deployment/BFF_AUTH_DEPLOYMENT.md)
- [Source synchronization review](documentation-code-sync.md)

Frontend integration statements in older guides are records of prior work, not newly verified frontend behavior.
