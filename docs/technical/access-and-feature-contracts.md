# Access and Feature Contracts

**Implementation update:** October 14, 2026. All changes here are local and unvalidated. The user deferred further tests, builds, browser checks and live AWS operations. Continue through the [active backlog](development-backlog.md).

## Application Access

The BFF validates the configured Cognito pool/client and then looks up the verified `sub` in an active `costguard-user-access` record. CDK sets `BFF_ACCESS_GRANTS_TABLE` and grants only GetItem access to BFF. Records contain `subject`, `is_active` and `grant`. Reads are consistent; a configured database never falls back to environment values. A legacy `BFF_ACCESS_GRANTS` JSON map is supported only when no table is configured. Each grant requires `role` (`viewer`, `operator`, `admin`), a nonempty `organizations` list and a nonempty `accounts` list. An explicit `*` grants full scope; do not use it unless intended. Public signup creates no application grant.

```json
{
  "verified-cognito-sub": {
    "role": "viewer",
    "organizations": ["o-your-organization"],
    "accounts": ["456041708434"]
  }
}
```

Viewer reads and advisor questions are allowed; resource mutations need operator/admin. Organization policy, budget and allocation-rule changes require an administrator with full account scope. Budget hierarchy reads also require full account scope because the existing response contains organization-wide values.

Prepare a typed grant item without AWS calls using `scripts/prepare_user_access.py --subject <verified-sub> --grant grant.json --output .artifacts/access/user-item.json`. Applying that item is deferred. `GET /api/session` returns only the signed-in user's current access status; the frontend shows an access-pending state when no active grant exists.

The BFF creates HMAC-signed delegation headers using the selected backend key. The signed context binds subject, grant, method, path, canonical query and body SHA256, and expires after 60 seconds (5-second future clock tolerance). It never copies identity headers from the browser. Backend service keys are privileged secrets: possession of a gateway key permits creating delegations within that key's configured scope.

Multi-account key records now require explicit `role`, `organizations`, `accounts` and `permissions`. Gateway records set `is_bff_gateway=true`, require signed context and reject scope or role exceeding the key record. Legacy records without scopes are denied. Direct keys retain their own server-side scope; they cannot supply delegated grants unless explicitly configured as gateway keys.

Main, AI/ML and autonomous REST handlers require `BACKEND_API_KEY` and `BACKEND_ACCOUNT_ID`, then signed delegation. CDK uses the matching `bff_main_key`, `bff_aiml_key` or `bff_autonomous_key` context/environment values. Direct single-account integrations require deliberate `allow_direct_api_keys=true`; they use a shared privileged integration identity, not per-person ownership. Existing deployments require matching key/configuration migration. Internal scheduled events bypass REST entry-point checks; no deployment or migration was applied here.

## Authentication Bootstrap

`setup_api_auth.py` now prints a plan by default and makes no AWS calls unless `--apply` is supplied. Provide a principal JSON file with explicit scopes/role, permissions, rate limit and optional gateway flag, plus a key-file path under an ignored private directory such as `.artifacts/access/`. Existing key files are reused; new keys use OS randomness. POSIX permissions are set to 0600; Windows file ACLs must be managed by the operator. Key values are not printed.

The live apply path inspects or creates correctly keyed auth tables, configures rate-limit TTL and upserts stable key ownership/scope records. `--rotate-from-key-file` disables a prior key after configuring the new one. Expired records require explicit operator renewal/rotation; repeat bootstrap preserves their existing expiry. Do not run apply while AWS work is deferred.

## Reports and Daily Allocation Data

`GET /api/reports/showback` and `GET /api/reports/chargeback` accept `entity_type`, `entity_name`, `start_date`, `end_date`, optional comma-separated `account_ids`, and `format=json|csv`. Showback supports team/project/environment; chargeback supports team/project. Dates are inclusive, at most 31 calendar days; select 1-25 permitted accounts.

Daily `costs_by_tag_service` records preserve exact entity/service costs from Cost Explorer grouping by one tag key and SERVICE. Collector date ranges use Cost Explorer's exclusive end; report date ranges use inclusive end. All pages are consumed before daily persistence. Three separate tag dimensions (Team, Project, Environment) are collected in addition to service totals. Allocation chooses one dimension so overlapping tags are not summed as independent spend.

Historical records without daily tag/service coverage yield 422 `ALLOCATION_DATA_UNAVAILABLE`. A missing record is never substituted with zero. CSV has real service/account/day rows and escapes formula-like text. PDF is explicitly unavailable; plain text is no longer labeled PDF. The BFF preserves download headers. Existing data needs a later authorized collection/backfill; none was run now.

## Pricing and Budget Availability

Regional pricing requests use `regionCode` and pagination. Only unambiguous on-demand product/unit matches become rates; conflicting profiles are omitted. Defaults and legacy cache entries are not treated as verified current pricing. Supported assumptions are Linux/shared EC2, x86 Lambda, standard on-demand DynamoDB, standard S3, and Single-AZ PostgreSQL/general-purpose RDS. Unsupported transfer/product profiles return unavailable estimates.

Estimation API rows include `status`, `pricingSource`, `pricingProfile` and `reason`. Unavailable amounts/bounds are null; totals cover available services only and `complete=false` marks partial results. Storage monthly rates are prorated using a 730-hour month assumption. This remains an estimate with declared profiles, not a full invoice or proof that every resource matches those assumptions. Product/profile matching and billing-mode fidelity need deferred validation.

Budget polling consumes every page, validates amounts/units and raises an unavailable condition on incomplete data or service failure. A prevention cycle fails rather than inventing a $1000 budget and zero spending. Missing forecasts remain null; actual spend is required. No estimate is substituted for month-to-date budget spend.

## Advisor and Organization Analytics

Single-account advisor user identity comes from verified delegation. Stored session keys include a hash of that identity; caller `user_id` is ignored. Query, history, clear-history and suggestions derive identity on the server. Cache keys include owner and session. Direct privileged key mode intentionally shares the integration identity. The frontend supports new/select conversations and scopes locally remembered IDs by signed-in username.

`GET /api/forecasts/organization` and `GET /api/forecasts/account/{account_id}` use only permitted accounts' persisted daily history. Query inputs: optional `account_ids`, `days=7|14|30`, `granularity=daily|weekly`. Forecasts require at least seven days observed for every selected account. Missing dates are reported; shared caches are disabled for this new scoped path to avoid cross-account reuse.

`POST /api/organization-advisor/query` accepts a cost question (maximum 2000 characters) and an inclusive date range up to 31 days. Optional query `account_ids` limits the permitted account selection. Only observed scoped cost context is sent to Bedrock; partial coverage is returned with the answer. No resource action is executed by advisor questions.

## Organization Policy Configuration

`GET|PUT /api/organization-policies/{scope}/{entity_id}` supports organization/OU/account scopes. `GET /api/organization-policies/effective/{account_id}` previews organization, outer-to-inner OU, then account overrides. Saved records have optimistic versioning: PUT requires `expected_version=0` to create or the current version to update; conflicts return 409.

Configuration permits budget limit, warning/action percentages and excluded resources. All saved policies require `enabled=false` and `dry_run_mode=true`. These routes persist and preview configuration; they do not apply policies to member accounts or execute prevention. Effective responses explain source scopes and versions. Execution adapters and live cross-account policy application remain outside this configuration work.

## Deferred Checks

All new auth, delegation, role/scope enforcement, collector persistence/pagination, exports, pricing profiles, missing-data states, session refresh/history isolation, analytics and policy configuration require later regression/build/synthesis/browser checks. Existing historical test results do not validate these changes. No further checks were run after the user deferred testing.


## Continued Implementation Contracts (October 14, 2026)

- Backend-key rejection is an upstream configuration failure (BFF 503), rather than a reason to expire the Cognito session. Session epochs protect sign-out and identity changes from pending refreshes.
- Advisor history includes a revision state item at numeric timestamp 0, not a chat turn. Clear increments that revision; transactional writes prevent an in-flight request from recreating cleared history. Confidence is nullable with method `unavailable`; a fixed score is not evidence.
- Default Nova forecasts use native messages-v1 requests and text-block responses. Exact-horizon valid points are required. Range method is exposed; model and heuristic ranges have no calibrated coverage claim. Cache identity is versioned and original creation time bounds retention.
- Core historical forecasts consume completed DAILY observations only, require seven distinct dates and disclose missing dates. They use BlendedCost; selected-account forecasts use UnblendedCost. Forecasts start on the next UTC day, not the day after an old observation. No automatic legacy conversion or backfill occurs.
- Core cost history selects one granularity. New keys use `SERVICE#<service>#<period-start>#<granularity>`; old records without metadata remain UNKNOWN. Query end dates are inclusive period-start filters; stored `period_end` is exclusive. Limits are 1-1000, `has_more` discloses truncation, and returned rows are not a full-period total. Task 69 adds filter-bound live cursor pages. Monthly records selected within a range may extend past its end.
- Collection requires requested amounts and consistent currencies rather than default zero/USD. Cross-account collection propagates role/external-ID configuration and preserves account collection metadata. Organization discovery prefers State; SDK/runtime deployment compatibility remains pending.
- Multi-account read-analytics deadlines are best-effort Lambda response bounds, not a hard latency SLA. Existing upstream SDK/model calls may already be in progress; there is no durable background-job or cancellation guarantee. Reports over 2 MiB return 413 after preparation.

All of these are unvalidated source changes. See backlog tasks 23-40 for details; tests, compilation, builds, synthesis, browser checks and AWS operations remain deferred.


## Follow-up Source Contracts (Tasks 41-49)

Forecast cache keys include the current UTC date. Main-stack autonomous/organization fallback routes return 503 and never report an unexecuted action or manufactured empty dataset as success. Frontend error messages preserve nested backend errors.

Advisor budget context uses an explicit `ADVISOR_BUDGET_NAME` or the sole COST budget; multiple unselected budgets are ambiguous. Historical context uses strict paginated collection and normalized service names. Availability and observed dates are included in structured advisor cost data. The active audit table supplies prevention context, with pre-action/rollback records excluded from completed-action claims. Estimated savings are nullable and never described as verified savings. No business/source information is invented from missing data.

Legacy Phase 3 rollback accepts safely parsed bounded JSON/literals with matching identities. Missing/invalid/naive/far-future timestamps and incomplete state block resource restoration. It does not use `eval` or infer executable state from regex fragments. Existing malformed snapshots may now be rejected; no live rollback ran.

Prevention history traverses all pages before sorting/filtering/limiting. Frontend cache tags invalidate affected reads after measurement/policy mutations, and selection controls avoid displaying replies for edited inputs. Validation remains deferred.


## Continued Execution and Data-Refresh Work (Tasks 50-53)

Legacy prevention re-resolves observed resource metadata and current safety checks before execution. Resource type/action and client region must match. Required rollback snapshot storage failure blocks action. Lambda snapshots preserve exact reserved concurrency; old snapshots without it cannot restore concurrency. Regional clients are used for capture/restore. None of this enables execution or validates live behavior.

Forecast cache metadata reserves `CACHE_DATA_REVISION` (no TTL). Each request pins that dataset revision; core cost refresh advances it before/after persistence, including failures. Old generations expire by TTL. This avoids a scan/delete invalidation race with older in-flight forecasts. Invalidation errors propagate; cache revision-read errors bypass reusable caching. Multi-record cost ingestion remains non-atomic, and a failed final invalidation may need operator repair. The forecast table name honors `FORECAST_CACHE_TABLE`.

Current estimates include unavailable rows for all requested services without observed metrics, with `missingMetricServices` and `coverageScope=selected_service_metric_profiles`. Completeness only describes the supported collected profiles, not all AWS charges; existing CloudWatch collection assumptions still constrain accuracy. All testing remains deferred.


## Metric and Pricing Constraints (Tasks 54-58)

CloudWatch average aggregation uses sample counts; sum aggregation requires observed values. Missing or non-finite data does not become zero. Periods account for the GetMetricStatistics point limit, and supported resource lists consume SDK paginator pages. Region is shared by collection and pricing.

Metric billing profiles must match conservative pricing assumptions: Linux shared on-demand EC2; x86 Lambda; standard on-demand DynamoDB; single-AZ PostgreSQL/gp2 RDS. Unknown/unsupported profiles are unavailable. The current S3 collector has no request observations, so a full S3 estimate is unavailable; task 67 adds an explicitly partial Standard-storage component. EC2/RDS running hours still use current-state/window approximations, and these estimates exclude other invoice components. The existing uncertainty margin depends on resource count and is labeled `heuristic_resource_count`; it has no calibrated coverage claim.

Advisor cache retains structured source availability and honors creation/TTL bounds. New source is unvalidated. [CloudWatch API](https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_GetMetricStatistics.html), [DynamoDB capacity modes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/capacity-mode.html).


## Advisor Failure and Budget Views (Tasks 59-62)

Advisor failure/absent model output returns 503; response timeout returns 504, without confidence or a successful fallback answer. In-flight work has no cancellation/durable-job guarantee. Monetary prevention monitoring processes known COST budgets only.

Budget hierarchy GET accepts `date=YYYY-MM-DD` (default yesterday UTC) and returns configured limits with period-to-date daily observations. Organization and descendant-OU rollups require full coverage for actual spend/utilization; partial observed spend and missing-date details remain separate. Root accounts and all configured budgets are retained; when multiple budgets exist the entity contains a `budgets` list rather than an arbitrary first choice. No forecast spend is synthesized. Annual/quarterly/monthly periods use calendar boundaries. Best-effort deadline behavior matches other read analytics.

Budget creation persists the name, currency, period and positive finite USD limit, with nullable unmeasured spend fields. OU must belong to the authorized organization; existing admin/full-account scope requirements remain. These are application configuration/observation views, not live AWS Budgets creation or policy execution. The active hierarchy uses the new measured view; older standalone utilization helpers retain their legacy daily semantics and are not the active REST path. All new behavior is unvalidated.


## Measured Allocation and Rule Configuration (Tasks 63-66)

Active allocation/unallocated routes share a single measured path for Team, Project or Environment. Requests use inclusive ordered dates (maximum 31) and 1-25 permitted accounts, with optional account_ids selection. Every date/account must contain tag/service observations; otherwise return 422. Allocation values include by-service/by-account cost. Unallocated residuals cover all selected accounts for the same dimension. Overlapping dimensions are not added. Resource-level untagged inventory is unavailable and explicitly labeled; a zero total leaves its percentage null.

Rules persist validated configuration with typed conditions. The UI submits TAG_BASED/PERCENTAGE/FIXED conditions, valid priority and target; account-specific conditions must refer to the actual organization. GET /api/allocation/rules lists persisted configuration in priority order with a 1-200 row bound and has_more. Organization-wide rule inspection requires full account scope; creation also requires administrator role. Rule writes refresh the rule list. Rules are not applied to measured tag views or resources. The multi-account API now defines 24 methods. All source changes remain unvalidated.


## Navigation, Components and Provider Estimates (Tasks 67-72)

S3 estimates can return `status=partial` for the observed Standard-storage component, with coveredComponents/missingComponents. Missing requests and other storage charges are excluded. Core empty collection reports no observed total; mixed currencies fail before storage.

Cost history accepts an opaque `cursor` matching the current start/end/service/granularity filters and returns `next_cursor`, `has_more`, `result_scope=page_records` and `pagination_consistency=live_keyset_not_snapshot`. Cursors navigate older date/service keys; new writes/expiry can change later results. Server reads still traverse and sort matching records; no efficient storage-level continuation is claimed.

Core and daily multi-account records preserve nullable is_estimated. Forecasts and observed analytics disclose estimated/unknown input dates, budget/allocation/unit-cost views disclose account/day observations, and JSON/CSV reports include provenance. A missing flag is unknown, not false; a non-estimated provider flag is not an immutable billing guarantee. No legacy backfill ran.

Tag collection requires complete returned periods/dimensions and finite USD amounts before writing verified allocation coverage. Partial dimension/day responses are failures rather than empty tag maps. All implementation remains unvalidated.


## History Retention and Visible Summary Semantics (Tasks 73-78)

Advisor chat turns expire logically after 24 hours regardless of DynamoDB TTL cleanup timing. Query pages are consumed until ten live matching turns are found. State metadata uses a separately renewed 90-day retention and fresh numeric generations after expiry/removal. Transactional writes require live matching state. An older owner-session history without usable state can be hidden; no migration ran. Missing history storage is an unavailable request, not successful persistence. UI reports loading/history/clear failures, resets conversation errors and reads auxiliary tabs on demand.

Overview cards preserve unavailable values, partial estimate labels and unknown prevention state. Seven-day forecast totals require all seven valid numeric points.

Proactive budget alerts now use the USD COST budget's own optional AWS CalculatedSpend projection and current reset limit, not a rolling model sum or a nonexistent table. A budget's TimePeriod may represent its lifetime rather than the current reset interval, so alert text labels TimeUnit without inventing period dates. Idle-resource monetary opportunities are nullable. Only verified supported EC2 compute pricing supplies a hypothetical 730-hour component; this is not realized savings or removal of retained charges. All validation is deferred.

Task 79 also supports total advisor forecast context when no service is selected, with normalized service aliases for specific cache reads. Cache absence remains unavailable. Validation deferred.


## Exports and Observed Trend (Tasks 80-82)

Forecast CSV includes displayed predictions plus model/metric/range/history provenance. Cost-history CSV explicitly exports the current page. Shared client CSV escaping quotes cells and protects formula-like strings; no browser export check ran.

The new main-stack GET /api/cost-data/summary reads all matching stored DAILY rows over at most 31 dates, with optional service. Frontend chart/export uses observed BlendedCost totals independent of table pages, preserving missing dates as null gaps and provider estimate flags. Complete date coverage does not establish full invoice coverage or an atomic collection snapshot. These source changes remain unvalidated.


Tasks 83-84 use eight actual completed UTC dates for daily comparisons and per-service increases. Missing observations suppress the comparison, nonpositive baselines have no invented percentage, and provider-estimate/metric metadata is exposed. A 50% increase trigger is a heuristic, not a calibrated anomaly probability. All validation is deferred.


## Visible Access and Policy Metadata (Tasks 85-87)

BFF UI capabilities come from current session grant data. Operator/admin controls gate collection/measurement writes; administrator/full account scope gates organization configuration writes. Full account scope is required for budget/rule/policy metadata inspection, including effective policy previews, because configuration can reference other accounts. The UI skips restricted metadata reads and disables unavailable write controls. These are UX hints; server authorization remains authoritative on each request.

Direct-key mode has no session-role discovery contract, so existing controls remain visible and the backend decides access. Grant changes can outpace cached UI hints. Failed access reads disable BFF capabilities and expose a retry action rather than rendering an object error or forcing reauthentication. Validation remains deferred.

Task 88 standardizes JSON object requests: malformed encoding/JSON, duplicate keys, non-object bodies and non-finite numbers return 400. Empty HTTP bodies remain empty objects; base64 JSON normalizes before delegation checks. Ordinary HTTP JSON bytes are preserved for signatures. These are unvalidated source changes.


## Request/Selection and Availability Follow-ups (Tasks 89-98)

CSV report errors retain structured messages; only successful CSV is downloaded. Report/analytics widgets discard replies for changed selections and multi-account reads expose current-argument errors. Shared date validation prevents blank fields from broad reads. HTTP history now always resolves bounded dates: recent 31 by default, maximum 366 inclusive dates or 31 for hourly. The internal query utility retains its undated fallback independently.

Core collection uses positive exclusive windows with maximum 31 DAILY/366 MONTHLY/14 recent HOURLY days and no future end date. Hourly data remains an optional provider setting, not enabled here. [AWS hourly data](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-services-hourly.html).

Missing single-account backend key configuration returns 503, bad credentials 401, and permission/delegation denial 403. BFF translates upstream 401 into 503 without invalidating Cognito credentials. Cognito service failures are 503; only definitive token/user rejection is 401. SDK/proxy timeouts use bounded retries and remaining response budget, with explicit 504 for proxy timeouts. These are best-effort bounds and do not cancel already-started backend work. All validation remains deferred.


Tasks 99-100 preserve credentials on transient client session-service failure and expose retry. Definitive user/session rejection still signs out. Startup restoration uses operation IDs and a client deadline; SDK storage/cache races remain unvalidated. Multi-account error codes distinguish 401 authentication, 403 access denial, 429 quota exhaustion and 503 unavailable access service. Only 401 advertises the API-key challenge. All testing remains deferred.

Tasks 101-102 distinguish nonnegative usage/pricing from signed provider cost observations. Invalid usage/rates/results are unavailable; finite matching-unit budget credits remain signed values. Positive configured limits are still required. Validation remains deferred.

Tasks 103-105 reject unpageable truncated discovery, align canonical forecast/advisor examples with uncalibrated/nullable output, and select supported legacy actions by actual service. Only EC2/RDS stop and Lambda concurrency limiting enter that automatic path; unsupported services never default to stop. Snapshot/region/identity requirements remain. No execution was enabled or validated.


## Legacy Monitoring and Restoration Boundaries (Tasks 106-113)

Legacy prevention exposes configured dependencies and effective dry-run mode. Main factory clients/topics are wired in source; connectivity/IAM/delivery remain unverified. PREVENTION_EXECUTION_ENABLED is fixed false in CDK, independent of mutable monitoring configuration. Missing audit also forces dry-run planning before approval polling. This is separate from the autonomous executor's existing deployment gate; neither was enabled.

Monetary plan/action/approval opportunities are nullable. Generic metadata and accepted SDK calls do not establish savings. Legacy approval records now retain actions, numeric index time, separate expiry/retention and conditional decisions. No legacy public approval receiver or durable resume workflow was added; its older blocking poll is not claimed production-ready.

Audit numeric timestamps match stack indexes, while API display uses UTC ISO plus epoch metadata. History failures are errors, not empty results. Calendar end filters are inclusive UTC; limits/truncation and 2 MiB response bounds are explicit. Scans still read retained data before sorting/limiting.

Manual operator rollback requests are distinct from automatic execution. Accepted restoration returns 202/rollback_submitted, target_state and verification_status=unverified; restored_state remains null. It does not prove the resource reached its target. Submitted rollback records never become completed-prevention/savings evidence for the advisor. No resource restoration, notification, test, build or AWS validation was performed.


## Resource Evidence (Tasks 114-116)

Active idle evidence covers EC2, RDS and Lambda only. Every five-minute bucket in the configured observation window must be present and valid; absence is unknown, including sparse Lambda metrics. EC2 combines CPU and network rules and excludes accelerator instance families. Matching a rule is a review signal, not proof of workload inactivity or safe execution. Confidence remains null. No execution gate was enabled.

Resource hourly metadata is nullable, limited to a matching Linux/shared/on-demand EC2 compute rate. It is not a total bill or verified savings. Last activity is a positive metric bucket timestamp, not a precise workload event, and missing activity remains null. Discovery pagination was added to eight previously first-page operations; errors and per-resource/service catches still prevent any completeness guarantee. Tests, builds, AWS reads and other validation remain deferred.

Task 117 obtains Lambda state/tags from GetFunction and uses Configuration.FunctionName for metrics. Failed detail reads omit the resource; no active state or protection-tag absence is inferred. ARN identity remains available for actions. Creation date is unavailable; LastModified is retained separately. Validation remains deferred.

Task 118 removes legacy safety checks that always passed active usage/minimum idle duration. Optional evidence defaults to denial; matching resource/window/status, recent end time, measured duration and allowed state are required. Execution re-reads evidence after resource discovery. This does not establish workload inactivity or enable execution. Validation deferred.

Tasks 119-120 disclose observed-inventory scope/completeness and missing idle classification in the API/UI. Resource responses are bounded at 2 MiB. Persistence supplies numeric last_updated for the deployed service-index, typed properties and 90-day retention. No existing rows were migrated; resource-ID-only keys can collide across regions/accounts and reads still use fresh discovery. No complete snapshot or stale-row cleanup is claimed. Validation deferred.

Task 121 makes Resource.creation_date nullable and normalizes only supplied aware, nonfuture timestamps. Launch/modification events are not proof of original creation; EC2 last_launch_time and Lambda last_modified remain properties. No missing date defaults to the observation time. Validation deferred.

Task 122 applies a conservative shared operation profile to planning and public execution. RDS scope excludes clusters, replicas, Multi-AZ and other engines; this is narrower than AWS support. EC2 requires an observed EBS root and no special lifecycle. AWS documents additional stop limitations and automatic restart after seven days: [RDS stopping guidance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html). Eligibility is not authorization or proof of safety; execution remains disabled and validation deferred.

Tasks 123-124 separate dry-run preview evaluation from execution permission. Preview bypasses only the dry-run blocking check, retains evidence/tag/state checks and never invokes resource actions. Configured budget percentages now reach polling; finite numeric/service validation and nested threshold merging apply. poll_interval_minutes does not update the deployed EventBridge schedule. No tests, builds or AWS validation ran.

Task 125 uses consistent monitoring config reads and optimistic config_version conditional saves. Missing records retain defaults; unavailable/malformed storage returns 503 and concurrent save conflicts return 409. HTTP enable/disable no longer report success after failed persistence. Unversioned legacy rows can transition once; no migration ran. Whole-cycle concurrency and notification deduplication remain separate limitations. Validation deferred.

Task 126 treats the current server monitoring read as authoritative. A prior localStorage flag cannot turn a disabled response into enabled, and delayed mutation handlers no longer manually repopulate status cache. Controls wait for the refreshed status after mutations; errors expose retry. Existing localStorage flags are ignored rather than migrated. Validation deferred.

Tasks 127-128 disclose deployment schedule provenance and fresh inventory reads. The CDK rule/environment share a five-minute constant, but no deployed rule was read or modified. Runtime polling/cache preferences are not applied to EventBridge or a cache. Fresh discovery performs one inventory write pass; last_inventory_refresh records the workflow read time, without verifying complete coverage. Validation deferred.

Tasks 129-130 expose monitoring details and propagate workflow/approval failures through cycle and scheduler results. A failed cycle does not become a successful zero-action result. Successful scheduler completion is not proof of notification delivery, complete inventory or a resource reaching its target. Existing scheduled-handler HTTP-style returns do not establish Lambda retry behavior. Validation deferred.

Tasks 131-132 run shared discovery/planning once per cycle even when multiple budgets breach action thresholds. Triggers do not prove that listed resources belong to each budget filter. Successful cycles persist a bounded last_cycle_summary with evidence counts, candidate/budget examples (20 each), truncation and unverified scope/outcome flags. Counts describe observations in that run, not full account coverage. Failed cycles may leave an older successful summary; no complete run history, distributed lock, cross-invocation idempotency or delivery guarantee was added. Validation deferred.

Tasks 133-134 display bounded cycle explanations and retain baseline resource protections when custom safety configuration is supplied. Production/protected/exclude rules are additive, case/whitespace normalized, and minimum observation durations cannot be shortened below defaults. Malformed tags/settings are rejected or blocked. Missing metrics remain unknown and operation eligibility does not certify workload safety. Validation deferred.

Task 135 exposes administrator-only monitoring configuration with required expected_version and only budget_thresholds/enabled_services. Both BFF authorization and backend delegation checks use the shared role rule; direct privileged integration remains deliberately configured admin access. Settings cannot change execution/enablement/approval/schedule. Main CDK includes POST /api/prevention/config, without deployment or validation.

Task 136 adds the administrator monitoring settings form, including local ordering checks, service selection, required version and explicit replacement of stale drafts. UI hints do not replace server authorization; the new route must be deployed before use. Validation remains deferred.

Task 137 adds a separate best-effort last_cycle observation with success/failed/skipped, UTC times and bounded successful summary. API latest_cycle_read_status is available/not_recorded/unavailable; failed storage is not represented as no prior runs. Completion ordering is based on local invocation time and is not a distributed execution lock. Outcome persistence failure does not itself prove monitoring failed; results disclose it. Validation deferred.

Task 138 shows the latest recorded outcome independently of prior successful candidates. Failure/read-unavailable cannot be mistaken for an empty or successful cycle. DynamoDB null fields are retained during monitoring map deserialization. No live run tracker, complete run history or cloud validation was added.

Task 139 groups unavailable low-usage evidence by reason and retains at most 20 observed resource examples, with explicit truncation. Reasons describe the adapter observation, not complete account coverage or proof of workload inactivity. Validation deferred.

Task 140 moves runtime timestamps and successful summaries to atomic conditional updates of the separate last_cycle row. Failure/skip updates preserve prior successful summaries; scheduled observations do not advance editable config_version. Legacy main-record metadata remains fallback-only, without migration. Observation persistence failures stay explicit; no full history/locking or AWS validation was added.

Task 141 attaches discovery_report to resource reads and successful cycle summaries. It includes requested adapters, observed per-adapter counts, reported issue counts and at most 50 examples, with truncation. UI shows read time and diagnostics even for empty results. Some legacy metadata catches remain unreported, inventory persistence is separate, and no reported issues is not a completeness/metadata guarantee. Validation deferred.

Task 142 groups shared load-balancer reads, identifies classic/application/network adapters as elb/alb/nlb and filters to requested types. Gateway load balancers are outside this scope. In-memory identity is service+region+resource_id; identical duplicates collapse, conflicting metadata omits that identity and records an issue. Persisted raw-ID keys and stale historical rows are unchanged. Diagnostics report raw/unique/duplicate/conflict counts; per-adapter counts precede deduplication. Validation deferred.

Tasks 142-143 also correct the classic ELB SDK client name, use client region rather than guessing it from availability zones and retain ALB/NLB ARN identity. Requested types are filtered before detail reads. Frontend CSV exports current observed selections with read/filter/coverage provenance and shared formula protection. Existing inventory keys/rows are not migrated, and export does not establish a complete inventory. Validation deferred.

Task 144 updates the active Phase 3 overview and examples to this source contract. Older phase designs/reviews/results are preserved with an explicit current-source boundary. Documentation examples are illustrative and were not executed; all validation remains deferred.

Task 145 validates resource query filters and narrows service-specific discovery before SDK reads. A known service excluded by monitoring configuration returns an empty observation with requested_service_configured=false, not a broader discovery read. applied_filters preserve the requested scope. Invalid/blank/repeated filters return 400. Validation deferred.

Task 146 validates constructed and read monitoring outcomes, including bounded nesting/text/maps, finite integer counters, aware times and typed bounded examples. Summary/outcome JSON limits are 192/224 KiB; DynamoDB whole-item limits may still reject an oversized combined record and persistence remains best effort. Invalid read state is unavailable, never fabricated zero/success. No tests, builds or AWS validation ran.

Tasks 147-148 review SageMaker estimate gaps and replace the endpoint low-usage path with fully observed single-variant real-time invocation windows. Current instance count comes from endpoint observations; unsupported profiles and missing buckets remain unknown. Cost/waste fields are null for this evidence adapter, and advisor recommendations are review-only with nullable aggregate opportunities. Latency uses observed sample weights and converts provider microseconds to milliseconds; absent samples are unknown. [AWS endpoint metrics](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html). Other SageMaker modeled pricing/job paths still require follow-up; GPU/Bedrock paths are not covered by this change. Validation deferred.

Task 149 removes fabricated SageMaker rate/job-charge fallbacks. Training/endpoint rows retain metadata and observed/requested duration, with compute/storage/transfer/total null and an explicit unavailable billing basis. Current capacity cannot reconstruct historical endpoint charges; wall time does not prove billable time or attributable cost. Instance recommendations are absent without verified current/alternative rates. A regional SKU/profile adapter remains outstanding; aggregate Cost Explorer parsing has separate follow-up gaps. Validation deferred.

Tasks 150-151 expose current-hour SageMaker low-usage review and bounded daily observed costs. CE observations include all pages and unclassified usage; finite USD credits remain signed. Missing categories/empty observations are unknown, and date/provider-estimate flags disclose partial coverage. Classification by usage-type name is heuristic. Job rows are creation-window metadata, not attributed charges. A v2 cache/display contract prevents older fake-cost rows from being treated as current. No tests, builds, browser or AWS-account validation ran.

Task 152 derives strict SageMaker product matching from a bounded read of the [public us-east-1 catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonSageMaker/current/us-east-1/index.json). Matching requires exact regional instance/component/profile attributes, current OnDemand terms and one untiered USD hourly SKU; ambiguity, unknown profiles and bounded-page exhaustion remain unavailable. Endpoint cost_per_hour is only a current compute component with provenance, not total charges or avoided cost. Historical/job costs and savings remain null. Utility alternative-rate comparison additionally requires caller-supplied compatibility constraints, which this service does not independently verify. Read-only IAM definitions are added without deployment. The public catalog read is source research, not account/runtime validation; all tests/builds/cloud validation remain deferred.

Task 153 limits SageMaker job details to 50 unique attempts per report, with independent listing status, has_more (null when unknown), failures and up to 20 omission examples. Cost aggregation remains independent of detail/listing coverage. Job lists are not a billing reconciliation. Report responses have a 2 MiB limit; oversized cached payloads are ignored. No tests/builds/runtime validation ran.

Tasks 154-155 export observed SageMaker category amounts with coverage provenance and provide a [current SageMaker source contract](sagemaker-observed-contracts.md). It supersedes older SageMaker price/waste/inactivity examples while preserving historical reports. SDK retries may issue more than the 50 distinct job attempts. All runtime validation remains deferred.

Task 156 bounds endpoint evidence to 20 unique detail attempts/five list pages and labels the result bounded_observed_low_usage_candidates, with has_more and list/detail limits. Listing failures are unavailable (503), not a successful empty selection. Rates are queried only for candidates and reused within one tracker instance; this is not a persistent pricing cache or latency guarantee. Responses have a 2 MiB limit. Validation deferred.

Tasks 158-159 separate observed Bedrock service/usage-type charges from runtime ModelId counters. Service reports retain all finite USD categories and signed credits over 1-31 completed dates, with unverified invoice/model coverage. Model billing cannot be inferred from usage labels; model-filtered cost requests return 422. Runtime counters come from actual CloudWatch metrics, with full/partial/missing daily coverage per metric. InputTokenCount excludes cached tokens; AWS/BedrockMantle and Agents use different scopes and are not covered. No fixed token averages, default model prices or unverified cost ratios remain in these paths. [AWS runtime metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html), [token counting scope](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-token-burndown.html). No tests/builds/account validation ran.

Task 160 exposes separate observed Bedrock charges and runtime ModelId counters with current-contract guards, date/coverage limits and unavailable billed attribution. See [current Bedrock contracts](bedrock-observed-contracts.md). Old guessed-model/fixed-token examples are superseded; GPU paths remain under separate review. Validation deferred.

Tasks 161-162 replace unsupported GPU assumptions with configured observed windows and read-only previews. GPU_UTILIZATION_METRIC_CONTRACT must name a custom namespace/metric and aggregation=all_device_maximum, using InstanceId and Percent. This is an operator declaration, not agent/device verification; no default AWS GPU or CPU substitute is inferred. Complete hourly Maximum/SampleCount evidence is required, with bounded current running-instance discovery and no monetary fallback. POST gpu-prevention only supports dry_run=true and returns review candidates, zero resource actions and null savings. dry_run=false returns 409; legacy private execution helpers are blocked. No agent setup, cloud call, resource execution or validation was performed.

Task 164 exposes bounded unverified historical GPU action records, not summed projected savings. Optional GPU_PREVENTION_ACTIONS_TABLE storage is explicit; missing/failing reads return 503. Configured scans use at most 20 pages/100 returned rows, with invalid-date/truncation/live-read scope. Naive legacy times cannot be silently assigned to the requested UTC window. Recorded statuses/projections do not verify resource outcomes or realized savings. CDK can import an existing named table read-only and pass an explicit metric contract; no configuration, table creation, deployment or validation ran.

Task 165 adds the [current configured GPU contract](gpu-observed-contracts.md), superseding earlier CPU-fallback, simulated execution and verified-savings claims without certifying remaining aggregate billing/classification/spot behavior. All configuration and runtime validation remain deferred.

Task 166 exposes gpu_utilization_observed_v2 with configured GPU hourly-max evidence and server-applied instance/type filters before discovery. Current-contract UI distinguishes mean-of-maxima, missing metrics, configuration and bounded scope. No CPU fallback or persistence client is required for utilization/review previews. Validation deferred.

Task 167 exposes gpu_cost_observations_v2 type/usage-level DAILY EC2 Compute charges with bounded pagination, finite USD amounts/credits and nullable instance-Hrs quantities. Placeholder resource identity, GPU device-hours, utilization and workload confidence are not inferred. Workload-attributed filters return 422; period ends are explicit rather than silently clamped. Cross-account costs have per-account coverage and observed_partial_cost, with null complete total on missing accounts/dates and unavailable GPU-hours/utilization. Fixed 70% spot savings are no longer inferred by the advisor from aggregate charges. Current-contract UI keeps manual resource labels separate from billing. No tests/builds/account validation ran.

Task 168 exports current GPU aggregate observations with shared CSV quoting/formula protection and explicit unavailable resource/device-hour attribution. README/API/index point to current AI/ML contracts and preserve remaining analytics gaps. This is not an exported complete inventory/invoice or verified savings report. No validation ran.

Task 170 requires one explicit inference telemetry source and identity, with variant/stage where needed, over 1-31 completed daily dates. Sources are never added together; full/partial/missing coverage and raw counter semantics are disclosed. Lambda invocations can include function errors and do not establish application inference count. REST API Count uses SampleCount, not the prior sum assumption. Account-wide costs do not establish endpoint charges; monetary ratios/threshold decisions stay null. [API Gateway metrics](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-metrics-and-dimensions.html), [Lambda counter scope](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html). Trends use one bounded counter read and preserve gaps. Validation deferred.

Task 171 requires an explicit SageMaker training job or EC2 instance metadata source. Provider training seconds remain distinct from billed costs; missing job times remain null. EC2 launch time is retained separately and never proves training timing. Account-wide service/storage totals cannot be assigned to a job, and fixed duration/rate instance comparisons no longer produce rankings. Labels are provider/operator metadata, not independently verified model/dataset identity. [AWS DescribeTrainingJob fields](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeTrainingJob.html). New source and SDK behavior remain unvalidated.

Task 172 adds explicit inference/training telemetry UI and [current source contracts](inference-training-observed-contracts.md). Query forwarding includes source/variant/stage/job identity; current-contract guards prevent legacy cached financial claims. Job/resource snapshots are separate from report date windows, and labels/counts/times do not establish billed attribution or compatibility. Validation deferred.

Task 174 observes explicit EC2 instance type/AZ/region and Linux/shared profile before comparing a strict current untiered on-demand compute SKU to matching Linux AZ/type Spot history. Both lookups paginate within bounds and fail unavailable without defaults. The latest matching historical change before query end is selected; AWS also returns the effective price before the requested start. Quote differences are not actual billed savings, capacity guarantees, compatibility or interruption probability. Current billed/monthly/realized amounts and risk/suitability remain null. Type-only savings and what-if routes explain unavailable scope instead of assuming discounts/duration. [AWS Spot price history semantics](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSpotPriceHistory.html). No account SDK calls, tests or deployment were performed.

Task 175 provides current-query spot quote UI and [current quote contracts](spot-quote-observed-contracts.md), with unavailable suitability/risk/realized savings and separate reference differences/provenance. Old fixed-discount/risk/monthly examples are superseded. No tests/builds/account validation or resource change ran.

Task 177 separates operator-declared workload labels from configured GPU utilization-pattern observations. No CPU fallback, automatic training/inference identity, calibrated confidence or missing-as-zero remains in this classifier. A retained versioned MANUAL row uses the deployed instance_id/date key, without TTL revision reuse; consistent reads and conditional saves return 409 on conflict and 503 on storage failure. Writes require an authenticated actor/current resource observation, change application metadata only and do not mutate EC2 tags. Application labels precede nonconflicting valid tags; conflicting/invalid tags remain unknown. GET manual_only reads declaration scope independently of metric dates. Legacy rows are not migrated and no tests/builds/account validation ran.

Tasks 178-179: [current workload declaration and pattern contracts](workload-label-observed-contracts.md) define manual_only reads, expected-version set/clear, retained MANUAL storage and separate metric assessment. Clear returns to tag/unknown source without EC2 mutation. All validation remains deferred.

Tasks 180-183: dated classification UI separates declarations from GPU patterns; hourly evidence and provenance CSV expose the current bounded source. Internal AI/ML advisor failures are explicit and model/monthly projections are removed. See [current contracts](workload-label-observed-contracts.md). All validation remains deferred.

Tasks 186-187 extend [declaration contracts](workload-label-observed-contracts.md): atomic MANUAL/HISTORY version writes and bounded history-mode reads/UI, without legacy reconstruction or complete audit guarantees. History omits TTL; storage grows with writes. All validation remains deferred.

Tasks 189-191: [advisor evidence/prompt contracts](advisor-evidence-prompt-contracts.md) document the 2000-character question bound, preserved question/instructions, bounded optional context and unavailable estimates. No new AI/ML main-advisor wiring or execution is implied. All validation remains deferred.

Tasks 192-195: [advisor evidence contracts](advisor-evidence-prompt-contracts.md) now include descriptive BlendedCost flags, request-local cached evidence metadata, observed-only tables and unavailable unverified recommendation amounts/safety/ranking. All validation remains deferred.

Tasks 199-201: [current prevention audit contracts](prevention-history-observed-contracts.md) cap/project public history reads and expose bounded selection quality without restoration snapshots. No globally latest/complete-history or verified execution/savings claim. All validation deferred.

Tasks 202-204: [current audit selection contracts](prevention-history-observed-contracts.md) now cover applied dates/scoped CSV, exact-selection next_cursor continuation, strict single-valued query inputs and unavailable legacy estimate currency. Scan selections are not snapshots/global latest history. All validation deferred.

Tasks 208-210: [inventory persistence contracts](inventory-persistence-contracts.md) separate fresh discovery from scoped storage acknowledgements/failures and preserve raw API/action identities. Report/UI/CSV scope is explicit; legacy storage is not migrated and account scope is configured, not independently verified. All validation deferred.

Tasks 211-212: [inventory listing contracts](inventory-persistence-contracts.md) bound each discovery listing to five pages/100 retained identities and expose/validate page/item/bound diagnostics. These limits exclude metadata/retry calls and do not guarantee complete inventory, deadlines or resource continuation. All validation remains deferred.

Tasks 213-215 add [direct known-resource metadata inspection](resource-inspection-contracts.md) and scoped JSON export, separate from bounded inventory listing and resource eligibility/execution. All validation remains deferred.

Tasks 216-219: [autonomous stored-outcome contracts](autonomous-action-observation-contracts.md) supersede one-page/default-0.5 confidence summaries with bounded recorded outcomes, explicit unknown denominators/heuristic samples and unavailable calibrated confidence. No worker execution change/enablement is implied; all validation remains deferred.

Task 220: [declaration write acknowledgement](workload-label-observed-contracts.md) distinguishes the committed revision from a potentially newer readback, preventing stale-draft rebinding. Validation deferred.
