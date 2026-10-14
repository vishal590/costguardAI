# Read-Only Commitment Analytics

**October 14, 2026:** Implemented locally; all testing/build/synthesis/browser/live AWS validation is deferred. No RI or Savings Plan was purchased or modified.

`GET /api/commitments/analytics` accepts ordered inclusive `start_date`/`end_date` (at most 31 days) and optional comma-separated `account_ids` (1-25 permitted accounts). The multi-account handler enforces grants and uses a LINKED_ACCOUNT filter for every Cost Explorer operation. CE requests use an exclusive end date internally.

Returned sections cover RI utilization (grouped by subscription), RI coverage, Savings Plans utilization, coverage and utilization details. Paginated operations consume all pages; each unavailable AWS section reports its error code and null data rather than zero. `retrieved_at` marks retrieval time and does not guarantee billing data freshness. Inventory consists of commitments observed in this reporting period, not full live resource metadata.

Unused-cost indicators derive only from returned unused recurring/upfront RI fee and unused Savings Plans commitment fields. Missing metrics remain null. Positive unused values generate an informational workload-coverage review item; there is no automated purchase recommendation or purchase API. The UI displays each section, incomplete status and data provenance.

Sources: AWS [RI utilization](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetReservationUtilization.html) and [Savings Plans utilization](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetSavingsPlansUtilization.html). Effective permissions, linked-account attribution, CE coverage/lag and field semantics need deferred validation before operational use.

See [access contracts](access-and-feature-contracts.md), [Phase 7 unit economics](phase7-unit-economics.md) and the [active backlog](development-backlog.md).
