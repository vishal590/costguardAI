# Documentation and Code Synchronization

**Current source review:** October 14, 2026; continuing local implementation through task 220.

The backend workspace is CostGuard AI (`aws-ideas`), with the separate `client-aws-ideas` React frontend. Five stacks are defined: main, multi-account, AI/ML, autonomous and Cognito/BFF. Kiro remains untouched. The [ordered backlog](development-backlog.md) records implemented source work and the next tasks; [project status](../PROJECT_STATUS.md), [API design](api-design.md), [database design](database-design.md) and the focused contracts below describe current behavior.

**All testing remains deferred at the user's request.** Continuing work has not run tests, builds, lint/compilation, synthesis, browser checks, link validation, AWS-account calls or deployments. Earlier checks below are historical evidence and do not validate the current changes. Public AWS documentation/catalog research is distinct from account operations. Current source is not a verified release; deployed state, account access, migrations and runtime behavior remain unverified.

## Current Source Boundaries

- Access uses authenticated owner/session identity, explicit role/account/organization grants and request-bound backend delegation. Missing access/storage/configuration fails explicitly; local source does not create live keys/grants or migrate deployed schemas.
- Cost views preserve metric/currency/date/estimated coverage and unavailable amounts. Operator business volumes, conservative pricing profiles, aggregate billing and observed commitment inventory do not establish complete invoices or verified realized savings.
- Forecasts require observed history and expose uncalibrated uncertainty; missing source context does not become fabricated confidence. Advisor answers preserve the current question and evidence rules, bound optional context and expose original answer evidence/omissions. [Current advisor evidence contracts](advisor-evidence-prompt-contracts.md).
- Prevention monitoring persists editable configuration separately from runtime outcomes, uses fresh bounded evidence and reports discovery failures/unavailable coverage. Low observed activity is a review signal. Versioned config edits do not enable execution or apply schedules. Resource execution, approvals and rollback retain their documented gates; accepted rollback does not establish completed restoration.
- [SageMaker observations](sagemaker-observed-contracts.md) separate observed service/category costs, bounded job metadata and complete low-invocation evidence. Historical job/endpoint attribution and incomplete pricing stay unavailable.
- [Bedrock observations](bedrock-observed-contracts.md) separate service/usage-type costs from actual runtime token/invocation counters. Usage names do not establish model billing identity or model-switch savings.
- [GPU observations](gpu-observed-contracts.md) require operator-configured GPU-specific metrics. No CPU substitution or sparse-duration expansion establishes inactivity. Type-level billing is not instance/workload billing; previews and legacy action rows do not establish execution or verified savings.
- [Inference/training observations](inference-training-observed-contracts.md) use an explicit counter/source and actual job/resource metadata, with unavailable monetary attribution. [Spot quote observations](spot-quote-observed-contracts.md) compare matched reference quotes without assuming compatibility, capacity, risk or realized savings.
- [Workload declarations and patterns](workload-label-observed-contracts.md) separate operator labels from dated hourly GPU patterns. Versioned application set/clear retains a MANUAL pointer and atomically records future HISTORY revisions. UI exposes current declaration, conditional edits, bounded history, dated evidence and scoped CSV. Legacy declarations/tag history are not reconstructed; identity/confidence/safety remain unverified.
- [Inventory persistence](inventory-persistence-contracts.md) namespaces new stored observations by configured account/service/region/raw ID, preserves raw live identifiers and separates acknowledged writes/failures from fresh discovery. Legacy rows are not migrated; monitoring validates stored diagnostic consistency. Listing operations retain at most 100 identities from five pages and expose bounds/provider-exhaustion diagnostics; metadata/retry calls and complete inventory remain outside that guarantee.
- [Public prevention audit history](prevention-history-observed-contracts.md) uses at most ten scan pages of up to 100 rows each, exact-selection continuation and projected summaries, reports invalid/unknown-time/additional rows and sorts within the selection. It does not return restoration snapshots or establish globally latest/complete history.
- The main advisor uses bounded legacy prevention-audit scans (ten pages of 100 rows, at most 100 retained matches), explicitly disclosing invalid/omitted/additional rows. Descriptive cost comparisons expose exclusions and never treat an empty flag list as verified normal spending. The separate AI/ML advisor integration is not wired into this main path.

## Continuing Implementation and Deferred Work

User authorization is to select and implement successive tasks without routine approval, keeping documentation current. Task 198 refreshed this current summary; tasks 199-201 bound public prevention history and expose summary coverage. Tasks 202-204 add scoped audit filters/export, selection-bound continuation and explicit legacy currency uncertainty. Testing and cloud/deployment verification stay parked in the backlog. Existing deployments may need access/key/schema/configuration migration before exposing the new contracts. Source implementation status and validation status must remain separate.

## Historical Work and Validation Evidence

The following notes describe earlier authorized fixes and checks before the continuing-work testing deferral. They preserve project history and must not be interpreted as validation of the current working tree. Earlier forecast/default-confidence examples are superseded by current contracts.

## Backend Fixes Completed

### Multi-Account GPU Dispatch

`src/ai_ml_handler.py` now matches multi-account GPU paths before generic GPU suffixes. `/api/ai-ml/multi-account/gpu-costs` reaches `handle_multi_account_gpu_costs`; `/api/ai-ml/multi-account/gpu-utilization` reaches `handle_multi_account_gpu_utilization`. Single-account routing is preserved. All four dispatch cases have focused regression coverage.

### Autonomous Event Consumers and Approval State

The CDK rules explicitly route API `ActionApproved`, `ActionRejected` and `RollbackRequested` events from `costguard.autonomous.api` to Safety Guard. Demo interruption events from `costguard.autonomous.demo` reach Spot Manager. Worker action-request/completion rules include the worker source names and retain the legacy base source. The event archive includes the API, demo and worker sources. Safety Guard's own approval events are excluded from the API rule to prevent feedback.

Approval submission requires typed fields and passes the signature to the worker. It returns **202** with `status: "approval_submitted"`; EventBridge entry failures return 500 for approval and rollback. Safety Guard checks the stored HMAC, request identity and expiry before applying a conditional status update. Identical deliveries are idempotent and an opposite decision cannot reverse an applied decision. Request lookup handles audit entries and pagination. Rollback metadata is added without overwriting pending approval fields or extending the approval deadline. Approval requests are persisted before notification.

### Approved EC2 Execution and Resource Rollback

A sixth worker, `autonomous.action_executor`, now consumes Safety Guard `ExecuteAction` and `ExecuteRollback` requests. Scheduler recommendations with workload targets reach approval; Spot Manager submits complete Spot/On-Demand replacement requests without fabricated approvals or instance IDs. Right-sizing requests also go through human approval. Direct analysis input honors dry-run and confidence settings, and the API forwards workload parameters and worker failures.

The executor schedules real EC2 start/stop operations, provisions replacements from explicitly versioned launch templates, and changes existing instance types. It stores actual pre-action state before changes, owns its replacement instances, prevents conflicting resource actions, uses delivery leases and restores resource state on rollback. One-time cleanup callbacks enforce their times. Completion events feed Learning Engine using the original action/timestamp key; duplicate delivery does not create new outcome rows or undo a rollback. Failed publication can be retried after the resource operation.

CDK adds the executor, Scheduler group/role, approval secret and a dead-letter queue. **Execution defaults to disabled** through `EnableAutonomousExecution=false`; this work did not deploy or enable it. Approval expiry is separate from 90-day history retention. See [supported operations, payloads and recovery](autonomous-execution.md).

### Frontend Compatibility Follow-Up

`client-aws-ideas` now preserves schedule workloads, collects explicit replacement/training inputs, supports BFF-only configuration and requires a masked non-empty approval signature. Submission acknowledgements are displayed as asynchronous acceptance. History panels poll every three seconds and expose status, audit markers, verified training progress/checkpoint data and the last execution error. Approval and rollback track the submitted action directly through the new `action_id` history query parameter. Demo phases are labeled as time-based and savings as demo-reported; the UI no longer promises no AWS changes when execution is enabled.

The confidence API now counts canonical `success: true` and honors explicit false before legacy outcome strings. Frontend API/form tests and actual rendered React/MUI controls use local mocked hooks; the production build succeeds. Frontend current documentation is `client-aws-ideas/docs/api/autonomous-contract-sync.md`.

## Next Work and Deferred Validation

**Decision recorded:** October 14, 2026. The user requested continuous implementation and deferred all testing. The [active backlog](development-backlog.md) now records local implementations for its original 17 tasks and follow-up gaps through task 197. See [access and feature contracts](access-and-feature-contracts.md) for required configuration, migration, new APIs and boundaries.

No tests, builds, synthesis, browser checks or AWS operations ran during continuing implementation. Earlier passing results predate these changes. Validation, AMI creation and cloud testing remain parked. Policy previews remain disabled/dry-run. Continue from newly discovered source gaps without routine approval prompts.

## Open Code Limitations

- A 202 response proves submission, not worker validation, execution or completed rollback. Unsupported payloads and legacy metadata-only recovery records cannot claim resource restoration.
- Resource execution supports opted-in EC2 targets in the stack region. Optional `parameters.training` now restores and verifies a real reference SGD workload through SSM. Other model/framework adapters and live AMI/workload validation remain outstanding; provisioning alone never proves training resumed.
- Billing baseline plus an operator-supplied hourly estimate is a fail-closed budget check, not a guaranteed billing cap. Billing lag, actual runtime and callback failures need live operational validation.
- Demo-status progress remains elapsed-time based and combined with action history. It does not establish verified phase completion or measured production savings.
- The frontend now submits explicit workload/training parameters and follows asynchronous actions, but live API/browser operation remains unverified. No AWS deployment or resource operation was performed.

## Validation

The initial documentation pass extracted route tables and table/index schemas statically and checked local links. The first authorized routing fixes passed 54 focused checks on October 3. The October 4 execution follow-up passed **219 focused checks**: 172 existing worker tests and 47 execution/API/approval/CDK regressions. Tests use Moto EC2/DynamoDB resources and mocked billing/events/schedule clients; CDK validation synthesizes rules, target permissions, execution opt-in and resource definitions with inline test assets in a temporary directory. The complete repository suite and frontend were not run.

The October 13 training follow-up passed **236 focused checks** (172 worker tests plus 64 training/execution/API/CDK checks). See [EC2 training resume](ec2-training-resume.md) for the actual workload, checkpoint contract and prerequisites.

On October 14, **66 focused backend checks** and **16 frontend checks** passed. Frontend `npm run build` passed with the existing large-bundle warning. The full repository test suites, deployed browser/API flow and live AWS were not run.

The earlier AMI-preparation documentation validation checked 212 backend and 15 frontend Markdown files: zero missing local targets, invalid fragments or unbalanced fences. `git diff --check` passed. No AWS account was contacted and Kiro was left untouched.

Relevant tests: `tests/unit/test_autonomous_execution.py`, `tests/unit/test_autonomous_event_rules.py`, `tests/unit/test_backend_routing_regressions.py` and the five affected worker suites under `tests/unit/autonomous/`.

## Local AMI Preparation Verification - October 14, 2026

The preparation, training and CDK checks passed 28 focused tests. The 16-file worker/runtime archive passed SHA256 and internal manifest verification. The extracted worker restored step 7, advanced to step 37 and reused its result on retry in a Linux in-memory test. Bundled SDK dependencies installed without index access and imported on Linux. Installer Bash syntax passed; the installer itself was not run. Actual Amazon Linux 2023/Python 3.11, SSM registration, effective IAM and network checks remain pending. No AWS calls or AMI creation were performed.

Backend and frontend documentation validation covered 212 and 15 Markdown files respectively with zero missing local targets, invalid fragments or unbalanced fences.


Task 202 adds applied audit-date filters and a scoped current-selection CSV; continuation is next. All validation remains deferred.

Tasks 203-204 complete current audit continuation/navigation and strict selection/currency boundaries. Continuing source remains unvalidated; all testing/build/browser/account/deployment work stays deferred.

Task 205 narrows declaration cache invalidation to the affected instance and shares strict selection parsing; read-only previews do not refetch unrelated reports. All validation remains deferred.

Tasks 206-207 add current advisor answer/evidence JSON export and clarify historical roadmap/index claims versus limited implemented source and proposed products. All validation remains deferred.

Tasks 213-215 add direct configured EC2/RDS/Lambda metadata inspection and scoped JSON export, plus current architecture/route references. No resource-list continuation, billing attribution, action eligibility or execution is inferred. All validation remains deferred.

Tasks 216-219 replace autonomous confidence-statistic defaults with bounded stored-outcome/heuristic observations, explicit missing denominators and scoped UI/CSV. Worker execution/calibration are not certified or enabled; all validation remains deferred.

Task 220 binds manual-label drafts to their own acknowledged commit, preserving stale-draft protection when another writer advances the readback revision. All validation remains deferred.
