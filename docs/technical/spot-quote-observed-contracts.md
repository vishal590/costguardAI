# Scoped EC2 Spot Quote Observations

**Source update: October 14, 2026; tasks 173-175.** Local backend/frontend source only. All tests, builds, synthesis, browser/AWS-account checks and deployment remain deferred. No purchase or resource operation was performed.

GET `/api/ai-ml/spot-recommendations` retains its legacy route name but now requires workload_id to be one EC2 instance ID. It returns spot_quote_observations_v2 reference observations, not suitability recommendations. SageMaker/job-to-EC2 mapping is not inferred.

The EC2 response supplies the selected instance type, actual SDK region and availability zone. Only the observed Linux/UNIX shared-tenancy profile is covered. Standard lifecycle does not prove the customer's effective on-demand billed rate. Unsupported profiles remain unavailable.

The on-demand component requires one current, untiered, unambiguous USD/Hrs Compute Instance SKU matching region/type/OS/tenancy/software/capacity/operation. The spot component reads matching Linux type/AZ history, with bounded pagination and latest matching price-change selection. AWS includes the effective price before a requested time window, so price-change time and query time are exposed separately. Missing/ambiguous/failing lookups do not use default prices or discounts. [AWS price-history behavior](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSpotPriceHistory.html).

A quote difference is arithmetic between those references. It is not actual billed cost, realized/monthly savings, a future price or available-capacity guarantee. Storage, transfer, software charges, commitments and account-specific adjustments are outside the compute references. Interruption probability, workload/checkpointing compatibility and suitability remain null. No default 20% risk, 70% discount, 24/7 monthly projection or fabricated interruption count is retained.

Optional include_scenarios=true returns an explicit unavailable scenario scope. The legacy spot-savings route cannot establish a matched comparison from type names alone and returns unavailable monetary fields. Pure utility methods do not manufacture suitability/risk or aggregate savings without that missing evidence.

The frontend requires the current contract, accepts an explicit EC2 ID, uses current-query loading/error/retry, and displays selected type/region/AZ, reference rates, SKU and query/change times. It labels differences separately from savings and is independent of historical cost-report dates. No change/purchase action is offered.

See [active backlog](development-backlog.md), [API contracts](api-design.md) and [feature boundaries](access-and-feature-contracts.md). Runtime behavior remains unvalidated.
