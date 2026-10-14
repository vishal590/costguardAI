# Phase 7 Unit Economics Specification

**October 14, 2026:** Initial implementation is complete locally; testing, builds and live AWS validation are deferred.

## Cost and Volume Boundary

A unit-cost result combines an explicit Team/Project/Environment allocation with business-volume measurements for a declared customer/transaction/feature metric over the same permitted accounts and inclusive dates. Metric quantity is operator-supplied, with a required source reference. Storing a number does not verify the external business system; provenance is returned with results.

Volumes are daily additive counts. Unique customers across days are not computed by summing daily customer counts: declare the unit as customer-days or supply an additive denominator with the correct interpretation. Unit names must match across records. Missing cost or volume records and zero denominators produce unavailable unit cost, never a fabricated zero.

## Storage and API

`costguard-business-metrics` uses `metric_key` (account plus a hash of metric type/name) and `date`. Records include quantity, unit_name, source_reference, submitted_by, version and update time.

- `GET /api/business-metrics/{account_id}`: read an existing metric/date and its version.
- `PUT /api/business-metrics/{account_id}`: operator/admin; body `metric_type=customer|transaction|feature`, `metric_name`, `date`, finite nonnegative `quantity`, `unit_name`, `source_reference`, `expected_version`. Version 0 creates; a current version updates; stale writes return 409.
- `GET /api/unit-economics`: permitted-account read; parameters `metric_type`, `metric_name`, `allocation_type=team|project|environment`, `allocation_name`, `start_date`, `end_date`, optional comma-separated `account_ids`. Maximum 31 days and 25 accounts.

The calculation returns observed allocated cost, volume, unit_name, unit_cost, coverage/missing records and quantity provenance. Unit cost is available only when cost and volume coverage is complete, units match and quantity is positive.

## UI and Limits

Multi-account Unit Economics displays the cost/measurement boundary, source type and unavailable reasons. Operator ingestion uses explicit daily measurements and optimistic versioning. These inputs are configuration/data operations and do not execute AWS resource changes.

Validation, deployment, measurement-source reconciliation and historical backfill remain deferred. See the [active backlog](development-backlog.md).
