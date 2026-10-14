# Phase 3: Monitoring, Review and Restoration

**Source update: October 14, 2026.** These are local implementations. All further tests, builds, synthesis, browser checks and AWS validation remain deferred at the user's request. No deployment, resource action or notification was performed during this continuing work.

Use [project status](../../PROJECT_STATUS.md), [the active backlog](../development-backlog.md), [API contracts](../api-design.md), [database contracts](../database-design.md) and [access/feature boundaries](../access-and-feature-contracts.md) for current scope. Other files in this phase directory preserve earlier designs, reviews and reported results; they do not establish current completion or coverage.

## Current behavior

Monitoring starts disabled. Enabling it permits budget monitoring and review planning; automatic resource execution remains disabled by deployment configuration and unavailable without durable audit. The legacy approval flow has no public response receiver or durable resume workflow. Its blocking poll is not production-ready.

AWS COST budgets provide observed spending and limits; missing data is unavailable. Configured warning/action-review percentages feed polling. The CDK schedule is five minutes, with one shared source constant for the rule and reported environment value. Status leaves the live schedule unverified. Stored polling/cache preferences do not reconfigure EventBridge or create an inventory cache.

Discovery reads fresh observations from configured service adapters. Responses expose requested adapters, issue counts, bounded examples and unverified completeness. Empty results and zero reported issues do not establish an empty or complete AWS account. Shared load-balancer reads distinguish classic/application/network types as elb/alb/nlb; gateway load balancers are outside this selection. In-memory identity is service/region/resource ID, with conflicting observations omitted. Historical inventory rows are not migrated or pruned.

Active low-usage rules cover EC2, RDS and Lambda. They require every dated five-minute bucket in the observation window, valid samples and matching regions. Missing/sparse metrics remain unknown. EC2 combines low CPU with zero recorded network traffic and excludes accelerator families. Matching a rule is a review signal, not proof of workload inactivity. Confidence and unsupported monetary estimates remain null.

Review checks retain production/protected/exclude tags, explicit protected resource IDs, measured minimum windows, fresh evidence and actionable state. Custom safety settings add protections and cannot shorten baseline windows. Supported candidate operations are narrower than AWS capabilities: on-demand EBS-root EC2 stop, standalone Single-AZ MySQL/MariaDB/PostgreSQL stop without replicas, and active identified Lambda concurrency limiting. Execution gates remain independent of preview eligibility.

## API and interface

| Method | Main API route | Purpose |
|---|---|---|
| GET | `/api/prevention/status` | Settings, dependency configuration, schedule provenance and saved cycle observations |
| POST | `/api/prevention/config` | Administrator threshold/service settings with expected_version |
| POST | `/api/prevention/enable` | Enable monitoring configuration |
| POST | `/api/prevention/disable` | Disable monitoring configuration |
| GET | `/api/prevention/resources` | Observed resource selection and discovery diagnostics |
| GET | `/api/prevention/history` | Bounded retained audit records |
| POST | `/api/prevention/rollback` | Submit supported restoration from a valid snapshot |

BFF access uses a Cognito access token and current server grant. Operators can toggle monitoring and request supported restoration; administrators can edit thresholds/service selection. Backend account scope and signed delegation remain required. Direct privileged key integration must be deliberately configured. The new configuration route requires deployment before the form can operate.

Configuration reads are consistent. Conditional versions prevent concurrent overwrites; stale drafts return 409 and storage failures 503. Scheduled observations use a separate row, preserving the prior successful summary across failures/skips without changing settings versions. Latest outcome reads distinguish unavailable from not recorded. These are best-effort saved observations, not a live tracker or full run history.

The frontend exposes current server status, refresh/retry, administrator settings, prior successful candidate summaries, latest outcome, discovery diagnostics and bounded unavailable-evidence examples. Resource CSV exports cover only the current observed selection and include filter/read-time/coverage provenance. Shared CSV quoting/formula protection applies.

## Restoration and limits

Rollback requires a matching, recent, identity/region-checked snapshot. Parsing uses JSON/safe literal data; it never evaluates state as code or infers missing state. Lambda restoration preserves the exact prior reserved-concurrency setting, including its absence. Accepted requests return 202/rollback_submitted with an unverified target state and null restored state. They do not certify restoration.

Resource/history responses are limited to 2 MiB. History uses retained scans before sorting/limiting and is not an efficient storage cursor. Resource inventory persistence is best effort with 90-day TTL; its raw resource-ID primary keys still permit regional/account collisions. Monitoring outcomes are not distributed locks or cross-invocation deduplication. Some legacy metadata errors remain unreported. Notification delivery, live permissions and resource outcomes remain unverified.

## Source references

- [Main handler](../../../src/lambda_handler.py), [main stack](../../../infrastructure/cdk_stack.py)
- [Monitoring engine](../../../src/services/prevention_engine.py), [budget monitor](../../../src/services/budget_monitor.py)
- [Discovery](../../../src/services/resource_manager.py), [observed metrics](../../../src/services/idle_detector.py), [review checks](../../../src/services/safety_guard.py)
- [Operation eligibility](../../../src/services/resource_actions.py), [restoration](../../../src/services/rollback_manager.py)
- [Current examples](../../API_EXAMPLES.md#phase-3-monitoring-and-restoration)

Current audit selection behavior: [bounded history contracts](../prevention-history-observed-contracts.md). All continuing validation remains deferred.

Tasks 213-215 add [direct known-resource metadata inspection](../resource-inspection-contracts.md) and scoped JSON export, separate from bounded inventory listing and resource eligibility/execution. All validation remains deferred.
