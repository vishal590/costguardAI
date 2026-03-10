# Where Service Data Appears (Phase 1, 1.5, 3)

**Keywords:** services, Phase 1, Phase 1.5, Phase 3, cost history, current estimate, 22 services, Resource Manager, Cost Explorer

**Related:** [Phase 1 README](./phase1-cost-pipeline/README.md) · [Phase 1.5 README](./phase1.5-near-realtime/README.md) · [Phase 3 README](./phase3-automated-prevention/README.md) · [DOCUMENTATION_MAP](../DOCUMENTATION_MAP.md)

---

## Summary

| Where you see it | Source | Services | UI location |
|------------------|--------|----------|-------------|
| **Cost history (Phase 1)** | Cost Explorer API → DynamoDB | **All** services returned by Cost Explorer (API Gateway, CloudWatch, Glue, Lambda, DynamoDB, S3, etc.). No fixed limit. | Phase 1 Cost → tab "Cost history (Phase 1)" |
| **Current cost estimate (Phase 1.5)** | CloudWatch + Pricing API | **5 only:** EC2, Lambda, DynamoDB, S3, RDS. Only services with collected metrics in the time window are returned. | Phase 1 Cost → tab "Current estimate (Phase 1.5)" |
| **Resource discovery (Phase 3)** | Resource Manager | **22** AWS services (discovery for prevention: EC2, Lambda, S3, RDS, DynamoDB, EBS, NAT Gateway, etc.). | Phase 3 Prevention → Resources, actions, rollback |

---

## Details

### Phase 1 – Cost history

- **API:** `GET /api/cost-data?startDate=...&endDate=...&service=...`
- **Data:** Fetched from Cost Explorer (`GetCostAndUsage` with `GroupBy: SERVICE`), stored in DynamoDB. Cost Explorer returns whatever services have cost in the account for the date range.
- **Filter:** Optional `service` query param supports **ec2, lambda, dynamodb, s3, rds** (short names) for filtering; without filter, **all** stored services are returned.
- **UI:** Cost page → "Cost history (Phase 1)" tab → table shows date, service, blended/unblended cost. Service dropdown filter (All, EC2, Lambda, DynamoDB, S3, RDS).

### Phase 1.5 – Current cost estimate

- **API:** `GET /api/cost-estimation/current?hours=...`
- **Data:** CloudWatch metrics + Pricing API. Backend requests metrics for **five services only:** ec2, lambda, dynamodb, s3, rds. Only services that have metrics (e.g. existing functions, tables, buckets, instances) in the time window are included in the response.
- **UI:** Cost page → "Current estimate (Phase 1.5)" tab → total and breakdown by service (e.g. Lambda, DynamoDB, S3). If only three have usage, only three appear.

### Phase 3 – 22 services (Resource Manager)

- **Purpose:** Resource discovery for **automated prevention** (idle detection, actions, rollback). Not cost history or current estimate.
- **Data:** Resource Manager discovers resources across **22** AWS service types (see `resource_manager.py`). Used by Phase 3 prevention engine and API.
- **UI:** Phase 3 Prevention section (resources list, action history, rollback). You see the 22-services data there, not in Phase 1 cost or Phase 1.5 estimate.

---

**Last updated:** March 2026
