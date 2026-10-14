# Database Design

**Source review:** October 14, 2026. The deployed-schema definitions are in the stack modules instantiated by `infrastructure/app.py`. This is a source inventory, not an inspection of live AWS tables.

## Database Overview

The backend uses DynamoDB for historical costs, caches, configuration, organization metadata and action history. The five-stack app defines the tables listed below, including organization policies, business measurements and BFF access grants. BFF uses Cognito plus the retained `costguard-user-access` table. Two additional auth tables are initialized separately by `setup_api_auth.py`.

## Schema Design

All primary-key and index attributes below are strings unless marked `number`. Every stack-defined table uses `PAY_PER_REQUEST` billing and `RETAIN` removal policy. A dash means that key or TTL setting is absent.

### CostGuardStack

Source: [infrastructure/cdk_stack.py](../../infrastructure/cdk_stack.py).

| Table | Partition key | Sort key | TTL | Global secondary indexes |
|---|---|---|---|---|
| `costguard-cost-data-v2` | `pk` | `sk` | `ttl` | - |
| `costguard-forecast-cache` | `cache_key` | - | `ttl` | - |
| `costguard-prevention-config` | `config_key` | - | - | - |
| `costguard-resource-inventory` | `resource_id` | - | `ttl` | service-index: `service` / `last_updated` (number) |
| `costguard-prevention-audit` | `action_id` | - | `ttl` | timestamp-index: `timestamp` (number); resource-index: `resource_id` / `timestamp` (number) |
| `costguard-approval-requests` | `request_id` | - | `ttl` | status-index: `status` / `created_at` (number) |
| `advisor-cache` | `query_hash` | - | `ttl` | - |
| `advisor-conversation-history` | `session_id` | `timestamp` (number) | `ttl` | - |

### CostGuardMultiAccountStack

Source: [infrastructure/multi_account_stack.py](../../infrastructure/multi_account_stack.py).

| Table | Partition key | Sort key | TTL | Global secondary indexes |
|---|---|---|---|---|
| `costguard-organizations` | `org_id` | - | `ttl` | - |
| `costguard-accounts` | `account_id` | - | - | org_id-index: `org_id` |
| `costguard-multi-account-costs` | `account_id` | `date` | - | date-index: `date` |
| `costguard-allocation-rules` | `rule_id` | - | - | org_id-priority-index: `org_id` / `priority` (number) |
| `costguard-organization-policies` | `scope_key` | - | - | - |
| `costguard-business-metrics` | `metric_key` | `date` | - | - |
| `costguard-budgets` | `budget_id` | - | - | entity_id-type-index: `entity_id` / `entity_type` |

### CostGuardAIMLStack

Source: [infrastructure/aiml_stack.py](../../infrastructure/aiml_stack.py).

| Table | Partition key | Sort key | TTL | Global secondary indexes |
|---|---|---|---|---|
| `costguard-gpu-costs` | `instance_id` | `timestamp` | `ttl` | workload-type-index: `workload_type` / `timestamp` |
| `costguard-workload-classifications` | `instance_id` | `date` | `ttl` | - |
| `costguard-aiml-cache` | `cache_key` | - | `ttl` | - |

### CostGuardAutonomousStack

Source: [infrastructure/autonomous_stack.py](../../infrastructure/autonomous_stack.py).

| Table | Partition key | Sort key | TTL | Global secondary indexes |
|---|---|---|---|---|
| `costguard-action-history` | `action_id` | `timestamp` | `ttl` | action-type-index: `action_type` / `timestamp`; status-index: `status` / `timestamp` |
| `costguard-training-checkpoints` | `checkpoint_id` | `created_at` | `ttl` | training-job-index: `training_job_id` / `created_at` |
| `costguard-migration-rollbacks` | `rollback_id` | `created_at` | `ttl` | - |

Daily range reads exclude legacy period aggregates. Cost/aggregation APIs return missing-date coverage; cache keys include selected account scope. Policies use `scope_key`, configuration and an optimistic `version`; business metrics use a hashed metric identity, date, quantity, declared unit, source reference, submitter and version.

### CostGuardBFFStack

| Table | Partition key | Sort key | TTL | Purpose |
|---|---|---|---|---|
| `costguard-user-access` | `subject` | - | - | Active server-managed role and organization/account scopes |

New policy/metric/access tables are retained by CDK and have not been deployed. Daily cost records now include optional `costs_by_tag_service`; historical records without it cannot support measured allocation reports. Business measurements carry source references and optimistic versions. Advisor history keys include an authenticated owner hash. See [access and feature contracts](access-and-feature-contracts.md).

### Auxiliary Authentication Tables

| Table | Partition key | TTL | Initialization |
|---|---|---|---|
| `costguard-api-keys` | `api_key` | Not enabled by the setup script | `setup_api_auth.py` |
| `costguard-rate-limits` | `window_key` | `ttl` | `setup_api_auth.py` |

These tables are required by multi-account application authentication but are not created in the five-stack CDK app. The separate `multi_account_tables.py` construct definitions use different, unprefixed table names; they are not the tables instantiated by `MultiAccountStack` in the current app.

## Data Models and Access Patterns

Historical records use `pk = COST#YYYY-MM` and `sk = SERVICE#<canonical-service>#<date>#<granularity>`. Attributes include `date`, `service`, `granularity`, `period_end`, `blendedCost`, `unblendedCost`, `currency`, `unit`, `timestamp` and `ttl`. Service names are normalized for query/forecast compatibility. Example:

```json
{
  "pk": "COST#2026-03",
  "sk": "SERVICE#ec2#2026-03-01#DAILY",
  "granularity": "DAILY",
  "period_end": "2026-03-02",
  "date": "2026-03-01",
  "service": "ec2",
  "blended_cost": 1.25,
  "unblended_cost": 1.25,
  "currency": "USD",
  "unit": "USD",
  "timestamp": "2026-03-02T00:00:00Z"
}
```

The deployed historical table is `costguard-cost-data-v2`; some standalone service defaults still name `costguard-cost-data`. Use the Lambda's configured table name rather than assuming the service default identifies the deployed table.

Forecast and AI/ML caches are keyed by `cache_key`. Advisor responses use `query_hash`; conversations use session and numeric timestamp. Resource inventory can be queried by service; audit actions and approvals have resource/status indexes. Multi-account costs use account/date keys with a date index. GPU costs use instance/timestamp keys and a workload-type index. Autonomous actions use action/timestamp keys with action-type and status indexes. Some handler paths use scans, so an index's existence does not guarantee every request uses it or processes all pages.

There are no relational foreign keys. Organization/account references, shared GPU-cost table names, and action IDs are application-level relationships. The autonomous workers consume the AI/ML `costguard-gpu-costs` table; BFF stores users in Cognito rather than a `Users` DynamoDB table.

## Autonomous Execution Records

Approved operations retain their original action/timestamp key through scheduling, execution, completion, learning and rollback. `approval_expires_at` enforces the 15-minute decision deadline; `ttl` retains request/execution history for 90 days. Fields include `approval_decision`, `lease_until`, `lease_token`, `resource_result`, `completion_published` and `learning_recorded`.

`costguard-migration-rollbacks` stores execution snapshots at `rollback_id = execution-<action-token>` / the original action timestamp. Snapshot data includes original EC2 state/type or replacement ownership, schedule names and cleanup deadlines. The same table stores resource lock rows at `resource-<instance-id>` / `lock`. Snapshots precede mutations; a failure must not be described as resource restoration merely because history was updated. See [execution and rollback](autonomous-execution.md).

## Backup, Recovery and Retention

The main historical cost table enables point-in-time recovery. The multi-account, AI/ML and autonomous definitions explicitly disable it; other main tables do not enable it in their definitions. Retaining a table on stack deletion is not a backup or a recovery-time guarantee. TTL requires an item-level numeric expiration value and does not promise immediate deletion.

The autonomous S3 bucket holds checkpoints. Action-specific rollback records are separate from database recovery. No general database migration runner is defined by the CDK app; table/key changes require a migration plan before deployment.

## Source References

- [Historical record transformation](../../src/services/dynamodb.py)
- [Authentication setup](../../setup_api_auth.py)
- [API design](api-design.md)
- [Architecture](architecture.md)


## Historical Granularity and Conversation Revisions

Daily, monthly and hourly cost records use distinct sort keys. Records without granularity are UNKNOWN legacy data, displayed separately and excluded from forecasts. Query/history preparation deduplicates known-grain old/new keys, preferring the suffixed key. No automatic backfill ran. TTL and current deployment schema have not been inspected live.

Advisor history reserves timestamp 0 for `record_kind=session_state`, including a revision and retention TTL. Conversation writes condition on the current revision; clear advances it before paginated deletion of older turns. Owner-derived session identity remains required. Numeric turn timestamps use microsecond precision.

The repository's allocation/budget query indexes match the active names above, and list queries consume all pages. Runtime verification is deferred.

Forecast cache reserves `CACHE_DATA_REVISION` for a persistent dataset revision; forecast keys pin revision and UTC date. Cost refresh changes revisions before/after persistence. Old forecast generations expire normally; this does not make cost batches atomic.

Allocation-rule conditions now preserve DynamoDB string/numeric types; older string percentages are normalized on read. Budget records retain names/currency and nullable unmeasured spend. Measured hierarchy calculations read daily cost observations rather than trusting old stored default-zero fields. No schema migration was applied.

Core/daily multi-account cost records include nullable `is_estimated`, preserving the provider flag without interpreting missing metadata as final billing. Forecast metadata and daily-derived features retain estimated/unknown observation provenance. Legacy spelling `periodEnd` remains readable; new core records write `period_end`.

Advisor turn TTL remains 24 hours and is enforced during reads. Session-state metadata has renewable 90-day retention; fresh generations after expiration prevent revision reuse. Existing unversioned owner-session rows without live state may be hidden. No history migration ran.

Legacy pre-action/rollback audit writes now use numeric timestamp index attributes plus timestamp_iso metadata. Approval records use numeric created_at, actions_json, expires_at_epoch and separate 90-day retention TTL. Old missing-expiry approvals cannot authorize decisions; no migration ran.

Resource inventory observations now write last_updated as numeric UNIX seconds for the existing service-index, typed properties, unverified completeness and ttl at 90 days. The string primary key name remains resource_id; task 208 now stores a schema-2 hash of configured account/service/region/raw ID and retains raw_resource_id separately. Legacy raw-key rows are not migrated or deleted; storage consumers must distinguish schemas. Inventory writes are best effort, not an atomic complete snapshot or proof that previously stored resources still exist. Validation deferred.

Monitoring config rows now carry numeric config_version. Consistent reads bind conditional whole-record writes; unversioned rows use attribute_not_exists for the first versioned write, then equality checks. Existing rows are not backfilled. Conflicts are explicit rather than silently retried. Validation deferred.

Monitoring observations use config_key=last_cycle in the existing prevention-config table, separate from config_key=main. schema_version=1, numeric completed_order and typed observation map store the latest success/failure/disabled-skip; conditional newer-completion writes avoid replacing a newer stored completion. This is one best-effort record, not a run-history table or cross-invocation lock. No data migration or validation ran.

Task 140 updates last_cycle atomically, preserving last_successful_summary/last_successful_at across failed/skipped observations and retaining last_inventory_observed_at. Runtime updates no longer rewrite config_key=main or advance settings config_version. Legacy main-record runtime fields are read fallback-only. Conditional completion ordering does not serialize execution. Validation deferred.

Tasks 178-179: [current workload declaration and pattern contracts](workload-label-observed-contracts.md) define manual_only reads, expected-version set/clear, retained MANUAL storage and separate metric assessment. Clear returns to tag/unknown source without EC2 mutation. All validation remains deferred.

Tasks 186-187 extend [declaration contracts](workload-label-observed-contracts.md): atomic MANUAL/HISTORY version writes and bounded history-mode reads/UI, without legacy reconstruction or complete audit guarantees. History omits TTL; storage grows with writes. All validation remains deferred.

Tasks 208-210: [scoped inventory storage and write-report contracts](inventory-persistence-contracts.md) supersede raw-ID-only new writes and add explicit write/skip/failure diagnostics with stored-report consistency checks. Existing table/index definitions remain; source only, no migration/deployment/validation performed.
