# Configured GPU Evidence, Review and Historical Records

**Source update: October 14, 2026; tasks 161-165.** Local source implementations only. Tests, builds, synthesis, browser checks, account calls, metric-agent configuration and deployment remain deferred. Resource execution is unavailable in the legacy GPU integration.

## GPU low-usage evidence

GET `/api/ai-ml/idle-gpus` accepts start_date/end_date as 1-31 completed daily dates with an exclusive end and a finite threshold percentage from 0 to 100. Its legacy route/field names do not establish actual inactivity.

The adapter requires an explicit operator-declared custom metric contract. An illustrative shape is:

```json
{
  "namespace": "CostGuard/GPU",
  "metric_name": "AllDeviceUtilizationMaximum",
  "aggregation": "all_device_maximum"
}
```

This is a contract shape, not an installed or verified metric agent. GPU_UTILIZATION_METRIC_CONTRACT can be supplied through deployment configuration, including the gpu_utilization_metric_contract CDK context. The expected metric uses InstanceId and Percent and represents the maximum across all relevant GPU devices. Agent/device sampling and completeness must be established separately; the declaration does not verify them. No GPU agent was installed or enabled.

Default AWS GPU availability is not inferred and CPU metrics are never substituted. Missing/invalid configuration returns an explicit unknown configuration state without GPU discovery. Configured reads inspect at most 20 current running g/p-family instance observations and five list pages in the selected SDK region, with has_more. They are not a historical fleet inventory.

Every dated hourly Maximum bucket in the requested window must be present with valid positive samples and values from 0 to 100. Missing/sparse/conflicting metrics remain unknown. Candidates require every returned hourly maximum below the threshold. The displayed utilization is a mean of hourly operator-declared all-device maxima; low-usage hours count observed matching buckets, not a proportion stretched across missing dates. This still does not prove continuous inactivity or safe removal.

Response data_contract=gpu_low_usage_observed_v2 includes observation_report, windows, bounded unavailable examples and unverified inventory/device-source flags. Cost/waste fields are null: an instance type or low utilization does not prove billing profile, avoidable charges or savings.

## Read-only review preview

POST `/api/ai-ml/gpu-prevention` accepts start_date/end_date/threshold and optional dry_run=true. It returns gpu_review_preview_v2 bounded review candidates, execution_enabled=false, zero resource actions and null savings. dry_run=false returns 409. Operator authorization is required under current write-role rules.

This route no longer returns simulated counts. It does not stop/terminate resources or create action/savings records. Legacy private execution helpers are blocked. A production execution implementation would require separate verified evidence, protections, authorization, audit/approval and restoration work; it is not implied by this preview.

The frontend attaches preview responses to their requested dates/threshold, exposes missing configuration and unknown evidence, and labels observed windows without claiming monetary savings.

## Historical action observations

GET `/api/ai-ml/gpu-cost-savings` retains its legacy path but now returns gpu_action_observations_v2 unverified records. GPU_PREVENTION_ACTIONS_TABLE must explicitly identify existing storage. CDK gpu_action_history_table can import a specifically named existing table and grant read-only access; no table or data migration is created automatically. This configuration has not been applied.

A consistent paginated scan reads at most 20 pages and returns at most 100 matching records sorted within the scanned selection. Dates are bounded to 1-31 completed days with an exclusive end. Invalid/naive timestamps cannot be assigned to the requested UTC period and are counted separately. Read metadata discloses scanned/matched/invalid rows, has_more and non-atomic scope. Missing/failed storage returns 503, not a successful empty list. Responses are capped at 2 MiB.

Legacy recorded projections can be retained as explicitly unverified source values, but are never summed into realized savings. Status labels such as executed do not certify stopped/terminated resources. Savings, final-state counts and average idle duration remain null. No new action/savings records are written by previews.

## Remaining source gaps

Aggregate GPU billing records still require a separate review of instance identity, instance-hours versus GPU-hours, pagination and classification. Task 166 now exposes gpu_utilization_observed_v2 configured hourly-max evidence with server-applied instance/type filters; presentation distinguishes missing configuration/coverage and mean-of-maxima. Other classification/spot/model compatibility estimates do not become validated through this evidence adapter. Historical test/coverage claims do not validate current source.

See [active backlog](development-backlog.md), [API contracts](api-design.md) and [feature boundaries](access-and-feature-contracts.md).

## Aggregate billing update (Task 167)

GET gpu-costs now returns gpu_cost_observations_v2 DAILY instance-type/usage-type EC2 Compute observations over 1-31 completed dates. USD credits remain signed; all pages are read within 100-page/50,000-row bounds, and oversized responses are 413 at 2 MiB. Missing/estimated dates disclose partial observations. Aggregate record IDs are not EC2 instance IDs. Provider Hrs quantities are instance-usage observations, not GPU-device hours, and missing quantities are unknown. Resource/workload attribution, GPU-hour cost, utilization and confidence are unavailable. Workload-attributed filters return 422. No hidden end-date clamp or old cache payload is used.

Cross-account results distinguish observed partial costs from complete date/account totals and preserve per-account failures/coverage; unknown spend/device-hours/utilization do not become zero. Manual resource labels do not join aggregate billing. Runtime validation remains deferred.
