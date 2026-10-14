# API Design

**Source update:** October 14, 2026. Continuing implementations are unvalidated; all further testing is deferred. Routes below are extracted from the checked-in CDK stacks. They describe available infrastructure definitions, not a live endpoint test.

## API Overview

REST APIs use API Gateway with Lambda proxy integration. Base URLs come from stack outputs and normally include the `prod` stage. Append the `/api/...` path to the relevant output; do not substitute a different stack's URL.

| Stack | Scope | API base URL output |
|---|---|---|
| `CostGuardStack` | Phases 1-4; limited multi-account compatibility stubs | `APIEndpoint` |
| `CostGuardMultiAccountStack` | Organization discovery, costs, allocation and budgets | `MultiAccountAPIEndpoint` |
| `CostGuardAIMLStack` | GPU, SageMaker and Bedrock workload costs | `AIMLAPIEndpoint` |
| `CostGuardAutonomousStack` | Six worker Lambdas plus a separate nine-route API | `AutonomousAPIUrl` |
| `CostGuardBFFStack` | Cognito access-token validation and backend proxy | `BFFApiUrl` |

**BFF implementation update:** October 14, 2026. Forwarding and configured Cognito application binding are implemented locally; all further validation is deferred.

## Authentication & Authorization

With BFF, send `Authorization: Bearer <Cognito access token>`. BFF requires the configured Cognito pool issuer, client ID, access-token use and future expiry, then requires Cognito GetUser acceptance of the original token before forwarding with server-side backend keys. Missing pool/client configuration returns 503; invalid credentials return 401. These new authentication checks are implemented but testing is deferred. BFF reads an active grant for the verified subject from `costguard-user-access` and signs request-bound delegation. Single-account REST handlers require matching server keys and signed identity; direct privileged key mode must be explicitly enabled. `GET /api/session` is handled locally by BFF to expose the current user's grant status. It selects AI/ML and autonomous backends by their prefixes; `/api/organizations`, `/api/costs`, `/api/allocation` and `/api/budgets`, plus reports, forecasts, organization advisor/policies, business metrics, unit economics and commitments, go to the multi-account backend. Other paths use the main backend. Prefixes match complete path segments. REST repeated query values and HTTP raw query strings are preserved; encoded request bodies are decoded before forwarding. See the [active backlog](development-backlog.md) for implementation and deferred validation status.

Direct callers must satisfy each stack's API Gateway key configuration. Multi-account requests also undergo DynamoDB-backed authentication and rate limiting in `src/services/multi_account/api_auth.py`; initialize/configure the auth tables and explicitly scoped key records through `setup_api_auth.py` (plan by default; live apply deferred). Gateway keys require signed delegation within their role/scope. The per-user limit defaults to 100 requests/minute and is stored with the key. Do not assume rate-limit response headers or a separate burst allowance: the limiter now uses an atomic conditional counter for the per-minute quota; there is no separate burst allowance. Unavailable limiting fails with 503.

See [BFF setup](../deployment/BFF_AUTH_DEPLOYMENT.md) and [multi-account reference](phase5-multi-account/API_DOCUMENTATION.md).

## Endpoints

### CostGuardStack

Source: [stack](../../infrastructure/cdk_stack.py) and [handler](../../src/lambda_handler.py).

| Method | Path |
|---|---|
| POST | `/api/fetch` |
| GET | `/api/cost-data` |
| GET | `/api/cost-data/summary` |
| POST | `/api/cost-data/fetch` |
| GET | `/api/cost-estimation/current` |
| GET | `/api/cost-estimation/service/{service}` |
| GET | `/api/cost-forecast` |
| GET | `/api/cost-forecast/service/{service}` |
| GET | `/api/prevention/status` |
| POST | `/api/prevention/config` |
| POST | `/api/prevention/enable` |
| POST | `/api/prevention/disable` |
| GET | `/api/prevention/resource` |
| GET | `/api/prevention/resources` |
| POST | `/api/prevention/rollback` |
| GET | `/api/prevention/history` |
| POST | `/api/advisor/query` |
| GET | `/api/advisor/history` |
| DELETE | `/api/advisor/history` |
| GET | `/api/advisor/suggestions` |
| GET | `/api/organizations` |
| GET | `/api/organizations/{org_id}/accounts` |
| GET | `/api/costs/consolidated` |
| GET | `/api/costs/by-account` |

The four organization/cost routes are compatibility fallbacks returning explicit 503 unavailable errors. AI/ML and autonomous routes require their separate APIs.

### CostGuardMultiAccountStack

Source: [stack](../../infrastructure/multi_account_stack.py) and [handler](../../src/multi_account_api_handler.py).

| Method | Path |
|---|---|
| GET | `/api/organizations` |
| GET | `/api/organizations/{org_id}/accounts` |
| GET | `/api/costs/consolidated` |
| GET | `/api/costs/by-account` |
| GET | `/api/costs/account/{account_id}` |
| GET | `/api/allocation/by-tag` |
| GET | `/api/allocation/unallocated` |
| GET | `/api/allocation/rules` |
| POST | `/api/allocation/rules` |
| GET | `/api/budgets/hierarchy` |
| POST | `/api/budgets/organization` |
| POST | `/api/budgets/ou/{ou_id}` |
| GET | `/api/reports/showback` |
| GET | `/api/reports/chargeback` |
| GET | `/api/forecasts/organization` |
| GET | `/api/forecasts/account/{account_id}` |
| POST | `/api/organization-advisor/query` |
| GET | `/api/organization-policies/effective/{account_id}` |
| GET | `/api/organization-policies/{scope}/{entity_id}` |
| PUT | `/api/organization-policies/{scope}/{entity_id}` |
| GET | `/api/business-metrics/{account_id}` |
| PUT | `/api/business-metrics/{account_id}` |
| GET | `/api/unit-economics` |
| GET | `/api/commitments/analytics` |


The 24 methods above include new scoped reports, forecasts/advisor, policy configuration and Phase 7 analytics. Policy routes store/preview disabled configuration and do not execute cross-account prevention. All new behavior is unvalidated; see [access and feature contracts](access-and-feature-contracts.md).

### CostGuardAIMLStack

Source: [stack](../../infrastructure/aiml_stack.py) and [handler](../../src/ai_ml_handler.py).

| Method | Path |
|---|---|
| GET | `/api/ai-ml/gpu-costs` |
| GET | `/api/ai-ml/gpu-utilization` |
| GET | `/api/ai-ml/idle-gpus` |
| POST | `/api/ai-ml/gpu-prevention` |
| GET | `/api/ai-ml/gpu-cost-savings` |
| GET | `/api/ai-ml/workload-classification` |
| POST | `/api/ai-ml/workload-classification` |
| GET | `/api/ai-ml/cost-per-inference` |
| GET | `/api/ai-ml/inference-trends` |
| GET | `/api/ai-ml/cost-per-training` |
| GET | `/api/ai-ml/training-comparison` |
| GET | `/api/ai-ml/spot-recommendations` |
| GET | `/api/ai-ml/spot-savings` |
| GET | `/api/ai-ml/sagemaker-costs` |
| GET | `/api/ai-ml/sagemaker-idle-endpoints` |
| GET | `/api/ai-ml/bedrock-costs` |
| GET | `/api/ai-ml/bedrock-cost-per-invocation` |
| GET | `/api/ai-ml/multi-account/gpu-costs` |
| GET | `/api/ai-ml/multi-account/gpu-utilization` |
| GET | `/api/ai-ml/multi-account/top-gpu-accounts` |

### CostGuardAutonomousStack

Source: [stack](../../infrastructure/autonomous_stack.py) and [handler](../../src/autonomous_handler.py).

| Method | Path |
|---|---|
| POST | `/api/autonomous/schedule-analysis` |
| GET | `/api/autonomous/action-history` |
| POST | `/api/autonomous/approve-action` |
| POST | `/api/autonomous/rollback` |
| GET | `/api/autonomous/confidence-scores` |
| GET | `/api/autonomous/demo-status` |
| POST | `/api/autonomous/demo/start` |
| POST | `/api/autonomous/demo/reset` |
| POST | `/api/autonomous/demo/trigger-interruption` |

### CostGuardBFFStack

The BFF defines a proxy resource and forwards requests; it does not create another independent set of business contracts. Missing/invalid access tokens return 401; an unconfigured backend or failed upstream connection returns 502. Backend status and response bodies are passed through.

## Requests and Responses

Parameter names vary by feature. Historical fetch/query uses `startDate` and `endDate`; AI/ML and multi-account date filters use `start_date` and `end_date`. Consult the handler-specific reference before reusing a payload.

The response body is the endpoint's JSON payload. Lambda's `statusCode`, `headers` and serialized `body` are integration fields, not a wrapper returned to an HTTP client. Main and multi-account errors generally use:

```json
{"success": false, "error": {"code": "INVALID_REQUEST", "message": "Description"}}
```

AI/ML errors use `{"error":{"code":"...","message":"..."}}` without the `success` field. Autonomous and BFF errors commonly use `{"error":"..."}`. Success bodies are also endpoint-specific; there is no universal `data` envelope.

### GPU Utilization

`GET /api/ai-ml/gpu-utilization` requires `start_date` and `end_date` (`YYYY-MM-DD`, start before end). Optional filters are `instance_id` and `instance_type`. It returns `utilization` and `date_range`. Each utilization item contains `instance_id`, `instance_type`, `avg_utilization`, `gpu_utilization_pattern` and `timestamp`; missing metrics yield `avg_utilization: null` and an empty pattern. The pattern is capped at 96 values. Missing or invalid parameters return 400.

### Forecasts

Forecast horizons are 7, 14 or 30 days with daily/weekly granularity. The engine requests 30 days of stored history (overriding the retriever's standalone 90-day default), accepts at least 7 days, and skips Bedrock for all-zero history. Model-provided and +/-20% fallback ranges are explicitly uncalibrated; the legacy confidence-level parameter establishes no probability guarantee. See [forecast reference](phase2-ai-forecasting/README.md).

### Autonomous Requests

`GET /api/autonomous/action-history` accepts optional `action_id` in addition to type/status/date/limit filters. With an action ID it queries that partition directly, newest first and consistently, for approval/execution/rollback tracking. `resource_result.training` exposes verified progress and checkpoints; `execution_error` may describe the last retry failure even after later completion.

Confidence scores count canonical boolean `success`; legacy `outcome: "success"` is used only when that field is absent.

Schedule-analysis accepts `days` (1-30), `confidence_threshold` (0-1), boolean `dry_run` and optional `workload` (`instance_id`, positive `max_hourly_cost`). The scheduler adds its recommended UTC window and region; no workload means analysis only. Its API default for `dry_run` is false. It invokes GPU Scheduler synchronously and unwraps an API Gateway-shaped result. Demo/start requires demo mode and invokes the scheduler asynchronously. Demo/status combines elapsed-time progress with action history. Approval requires non-empty string `request_id`, `action_id`, `signature` and a boolean `approved`. Successful event submission returns **202** with `status: "approval_submitted"`, `approved`, `action_id` and `request_id`. Safety Guard asynchronously checks the HMAC, matching pending request and 15-minute deadline, then atomically records the decision and submits approved actions to the executor. Duplicate identical decisions are accepted; opposite decisions cannot reverse an applied decision. Worker validation errors are not returned by the original REST call; inspect action history for the stored status.

`POST /api/autonomous/demo/trigger-interruption` requires demo mode and explicit `instance_id`, `training_job_id` and replacement `parameters`. It forwards the optional `parameters.training` contract, validates job identity and returns **202** with `status: "interruption_submitted"`; it does not invent an instance/job or certify execution. The supported EC2 reference workload and checkpoint schema are documented in [training resume](ec2-training-resume.md).

Rollback returns 202 with an estimated completion time. Both endpoints return 500 if EventBridge reports a failed entry. Acceptance does not prove resource restoration.

## Known Limitations

In `ai_ml_handler.handler`, the multi-account GPU cost/utilization paths are matched before generic GPU suffixes and reach their dedicated multi-account handlers.

Autonomous API approval/rejection and rollback events use source `costguard.autonomous.api` and explicitly target Safety Guard. Approved decisions emit execution requests for reversible EC2 operations. Rollback restores persisted resource state and cancels timers through the executor. Execution defaults to disabled; supported parameters and limits are documented in [autonomous execution](autonomous-execution.md). See [source synchronization review](documentation-code-sync.md).

## Examples and References

- [API examples](../API_EXAMPLES.md)
- [Multi-account API](phase5-multi-account/API_DOCUMENTATION.md)
- [AI/ML API](../api/phase6-api-documentation.md)
- [Autonomous API](phase6-extension-endpoints-and-frontend.md)
- [Database design](database-design.md)


## Cost-History and Forecast Contract Update (October 14, 2026)

`POST /api/cost-data/fetch` defaults to DAILY; supplied end dates follow Cost Explorer's exclusive-end contract. `GET /api/cost-data` accepts `granularity=DAILY|MONTHLY|HOURLY|UNKNOWN` (DAILY default), inclusive start/end filters on period starts and `limit=1..1000`. Rows include `granularity` and exclusive `period_end`. Results expose `has_more`, `result_scope=page_records` and `legacy_period_unknown`. Use the filter-bound next_cursor as cursor to navigate live pages; this does not provide snapshot isolation or a full-period total. UNKNOWN is a read-only view of legacy data without trustworthy granularity.

Forecast metadata includes observed history days, missing dates, history method, cost metric, next-UTC-day forecast start and range method. Missing observations are not imputed in the active path. Advisor confidence is nullable with an unavailable method. BFF maps backend-key 401 to 503. Main-stack autonomous and organization fallback routes also return 503 without accepting actions or manufacturing empty results. Report artifacts above 2 MiB return 413.

These are local source contracts; all validation remains deferred.


`GET /api/budgets/hierarchy?date=YYYY-MM-DD` now returns configured organization/OU/account limits with observed period coverage (yesterday UTC default), including root accounts and all configured budgets. Partial or absent costs leave actual spend/utilization null. Multiple budgets are retained in `budgets`; per-budget period starts and as-of dates explain comparisons. Creation persists validated USD limits/names/periods and verifies OU membership; it creates application configuration only. Advisor failures return 503 and response timeouts return 504. All validation remains deferred.


Allocation and unallocated-cost GET routes accept Team/Project/Environment, optional account_ids, and 1-25 accounts over at most 31 inclusive days. Complete daily tag/service coverage is required (422 otherwise). Residuals cover all selected accounts; no resource-level inventory is manufactured. GET /api/allocation/rules reviews configuration with limit=1..200 and has_more; full account scope is required. POST saves typed validated configuration for administrators. Saved rules are not applied to measured tag views. All validation is deferred.


Core cost-history rows include nullable is_estimated; forecast metadata includes estimated_dates and unknown_estimate_dates. Empty cost fetches expose observationStatus=no_observations with nullable total/currency; mixed currencies fail before storage. Current/service estimates expose coveredComponents/missingComponents and allow explicitly partial S3 Standard-storage estimates. Multi-account daily-derived views and report exports disclose provider-estimated/unknown observations. These are unvalidated source contracts.


`GET /api/cost-data/summary?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&service=...` aggregates stored DAILY BlendedCost rows for up to 31 inclusive dates, with optional service. It returns observed_total, by_service, daily null gaps, provider estimate flags, missing_dates, complete_date_coverage and invoice_coverage_verified=false. It reads independently of page limits and does not prove all AWS charges or an atomically collected dataset. Mixed currencies return unavailable. Source behavior is unvalidated.


Cost-history GET resolves missing dates to a recent bounded range (31 dates by default); maximum 366 inclusive dates, or 31 for HOURLY history. Core fetch uses exclusive ends and accepts at most 31 DAILY/366 MONTHLY/14 recent HOURLY days, with no future end date. History bounds and collection bounds are distinct. These source constraints are unvalidated.

Single-account backend credentials now distinguish 503 missing configuration, 401 invalid key and 403 permission/delegation denial. BFF translates upstream key 401 to 503. Cognito definitive rejection is 401; service/throttle/network failures are 503. BFF timeouts are explicit 504 with best-effort remaining-budget/socket bounds. No hard latency/cancellation guarantee is claimed.


Legacy prevention status now includes execution_enabled, execution_configured, effective_dry_run_mode and configured-dependency readiness (AWS access unverified). Deployment automatic execution is off; enabling monitoring does not enable resource changes. Accepted manual legacy rollback returns 202/rollback_submitted with unverified target_state and null restored_state. Audit history validates limits 1-1000 and aware timestamp/epoch or inclusive UTC-date filters, exposes has_more, and bounds response artifacts at 2 MiB. Source changes are unvalidated.

GET /api/prevention/resources returns result_scope=observed_inventory, inventory_completeness=unverified, idle_evidence_included=false and active_idle_services=[ec2,rds,lambda]. Listed resources are not classified as idle. Oversized responses return 413 at 2 MiB; narrowing discovery configuration is currently required. No inventory pagination contract is added. Validation deferred.

POST /api/prevention/config is administrator-only within the authorized backend account. Body: expected_version (current nonnegative status config_version), optional nonempty budget_thresholds object (warning/action percentages), optional enabled_services list. At least one setting is required and unknown fields are rejected. Success returns current status; malformed settings return 400, stale drafts/concurrent writes 409, config storage failures 503. It cannot enable monitoring/execution or change schedules/approval. This method is defined locally in main CDK, unvalidated and undeployed.

Prevention status now includes latest_cycle and latest_cycle_read_status (available/not_recorded/unavailable), separate from last_cycle_summary (latest saved successful summary). Observed success/failure/disabled-skip records are best effort; cycle results disclose outcome_persistence. New observations do not establish live progress, inventory/budget scope or notification/resource outcomes. Source behavior remains unvalidated.

Resource responses and successful monitoring cycle summaries include discovery_report with per-adapter observed resources/reported issues and up to 50 issue_examples. inventory_completeness stays unverified; all_metadata_reads_verified is false. Reported issues do not capture every legacy metadata failure or verify persistence. No provider exception text or completeness guarantee is introduced. Validation deferred.

Resource GET supports service/state query names only, once each, as nonempty bounded names. Service must be a known adapter; service-specific discovery is narrowed before SDK reads. Known services omitted from monitoring configuration produce an empty observed result with requested_service_configured=false; applied_filters disclose scope. Invalid or repeated filters return 400. Validation deferred.

Monitoring observations validate stored shapes and bounded examples before display. Malformed/oversized observation records produce latest_cycle_read_status=unavailable and no malformed summary. Current resource filters narrow reads and preserve applied_filters/requested_service_configured; CSV exports cover current observed selections only. All validation remains deferred.

SageMaker idle-endpoint responses now describe observed low-invocation review candidates, not proven inactivity. observation_report includes returned endpoint count, unavailable count/examples (20 maximum), method and unverified coverage. Only one real-time production variant is supported; invocation buckets must cover the whole observed hour. Window/latency provenance is returned, and cost_per_hour/total_wasted_cost_per_hour/estimated_monthly_waste remain null. Other job-cost routes have separate outstanding pricing limitations. Validation deferred.

SageMaker cost GET now returns data_contract=sagemaker_observed_v2, result_scope, currency, unclassified_costs and data_quality with observed/missing/estimated dates, metric, category method and unverified invoice coverage. Period is at most 31 completed DAILY dates with an exclusive end. Empty/missing-category amounts are null; unclassified charges remain in overall totals. Category filters disclose selected scope and preserve overall_observed_total. Legacy cached payloads are ignored. Job monetary fields are nullable metadata-only. Provider-invalid observations return 503; invalid date windows return 400. Validation deferred.

Bedrock cost GET now uses bedrock_observed_v2: finite USD provider service/usage costs over 1-31 completed dates, at most 100 listed usage types with residual/truncation and unverified invoice/model coverage. Model-filtered costs return 422. Legacy cost-per-invocation GET now requires model and returns bedrock_usage_observed_v2 actual runtime counters with per-metric complete/partial/missing coverage; attributed money/ratios stay null. Old cached contracts and guessed model prices are not current evidence. See [Bedrock contracts](bedrock-observed-contracts.md). Validation deferred.

GPU idle reads now use gpu_low_usage_observed_v2 configured custom-GPU hourly evidence, unknown configuration/coverage and nullable monetary values. POST gpu-prevention is gpu_review_preview_v2 read-only review; dry_run=false returns 409 and no resource/action/savings writes occur. GET gpu-cost-savings is gpu_action_observations_v2 bounded unverified history from explicitly configured existing storage, with unavailable savings and 503 for missing/failing storage. See [GPU contracts](gpu-observed-contracts.md). Aggregate GPU billing/utilization presentation remains separate queued work. Validation deferred.

GPU costs now use gpu_cost_observations_v2 daily instance-type/usage-type USD compute observations, nullable device-hour/resource/workload attribution and explicit date/provider-estimate coverage. Workload-attributed filters return 422; invalid periods 400; provider failure 503; oversized returned reports 413. No hidden end-date clamp or old cache contract applies. GPU utilization uses gpu_utilization_observed_v2 configured hourly maxima with pre-discovery instance/type filters. Cross-account results retain observed_partial_cost and per-account quality, with nullable complete totals/device metrics. CSV exports cover all returned aggregate rows with provenance, not an inventory or complete invoice. Validation deferred.

Inference cost GET now requires source/endpoint plus dates, with variant or stage for relevant sources, and returns inference_counter_observations_v2 one selected provider counter with daily coverage. Monetary ratios/threshold decisions remain null. Trends require source/endpoint and 1-31 completed days, using one read and preserving gaps. Training cost GET requires source/job_id and returns training_metadata_observed_v2 provider/resource metadata with unknown attributed costs; EC2 launch time is not job timing. Training comparison returns explicit unavailable benchmark scope. See [current inference/training contracts](inference-training-observed-contracts.md). Validation deferred.

Spot recommendations GET now requires an EC2 instance workload_id and returns spot_quote_observations_v2 strict type/AZ/region/profile reference quotes. recommendations remain empty; suitability/risk/current-billed/realized/monthly savings are unavailable. Quoted rate differences and SKU/query/price-change times are separate. Optional what-if scenarios and type-only spot-savings requests explain unavailable scope. See [spot quote contracts](spot-quote-observed-contracts.md). No account/runtime validation ran.

Tasks 178-179: [current workload declaration and pattern contracts](workload-label-observed-contracts.md) define manual_only reads, expected-version set/clear, retained MANUAL storage and separate metric assessment. Clear returns to tag/unknown source without EC2 mutation. All validation remains deferred.

Tasks 186-187 extend [declaration contracts](workload-label-observed-contracts.md): atomic MANUAL/HISTORY version writes and bounded history-mode reads/UI, without legacy reconstruction or complete audit guarantees. History omits TTL; storage grows with writes. All validation remains deferred.

Tasks 189-191: [advisor evidence/prompt contracts](advisor-evidence-prompt-contracts.md) document the 2000-character question bound, preserved question/instructions, bounded optional context and unavailable estimates. No new AI/ML main-advisor wiring or execution is implied. All validation remains deferred.

Tasks 199-201: [current prevention audit contracts](prevention-history-observed-contracts.md) cap/project public history reads and expose bounded selection quality without restoration snapshots. No globally latest/complete-history or verified execution/savings claim. All validation deferred.

Tasks 202-204: [current audit selection contracts](prevention-history-observed-contracts.md) now cover applied dates/scoped CSV, exact-selection next_cursor continuation, strict single-valued query inputs and unavailable legacy estimate currency. Scan selections are not snapshots/global latest history. All validation deferred.

Tasks 208-210: [inventory persistence contracts](inventory-persistence-contracts.md) separate fresh discovery from scoped storage acknowledgements/failures and preserve raw API/action identities. Report/UI/CSV scope is explicit; legacy storage is not migrated and account scope is configured, not independently verified. All validation deferred.

Tasks 211-212: [inventory listing contracts](inventory-persistence-contracts.md) bound each discovery listing to five pages/100 retained identities and expose/validate page/item/bound diagnostics. These limits exclude metadata/retry calls and do not guarantee complete inventory, deadlines or resource continuation. All validation remains deferred.

Tasks 213-215: [direct resource inspection contracts](resource-inspection-contracts.md) define the new main GET /api/prevention/resource, configured-service/bare-ID/account-region scope, no listing/persistence/metric/billing/resource action and scoped frontend JSON export. Provider observations remain unavailable on denial/not-found/outage/ambiguity; all validation deferred.

Tasks 216-219: [autonomous stored-outcome contracts](autonomous-action-observation-contracts.md) supersede one-page/default-0.5 confidence summaries with bounded recorded outcomes, explicit unknown denominators/heuristic samples and unavailable calibrated confidence. No worker execution change/enablement is implied; all validation remains deferred.

Task 220: [declaration write acknowledgement](workload-label-observed-contracts.md) distinguishes the committed revision from a potentially newer readback, preventing stale-draft rebinding. Validation deferred.
