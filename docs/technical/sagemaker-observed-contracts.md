# SageMaker Observed Cost and Low-Usage Contracts

**Source update: October 14, 2026; tasks 147-155.** Implemented locally in the backend and sibling frontend. Tests, builds, synthesis, browser and AWS-account validation remain deferred. A bounded public price-catalog sample informed product matching; no account credentials, SDK pricing lookup, resource operation or deployment was used for that research.

## Observed cost report

GET `/api/ai-ml/sagemaker-costs?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` uses 1-31 completed daily dates with an exclusive end. Optional job_type is training, inference or notebook. Dates are checked before cache use. BFF Cognito identity/current grants and backend account authorization apply; direct privileged integration must be deliberately configured.

The service reads every Cost Explorer page, requires finite USD UnblendedCost amounts, retains signed credits and rejects conflicting duplicate observations. Training/inference/notebook categories use usage-type-name heuristics; unclassified usage remains in the overall observed total. Missing categories and empty observations remain null, including currency when no amounts exist. Missing dates and provider estimated/unknown flags explain partial observations; date coverage does not verify a complete invoice.

Responses use data_contract=sagemaker_observed_v2. Older cached payloads do not satisfy that contract. Category filters retain overall_observed_total and disclose selected scope rather than turning excluded categories into measured zero. Provider-invalid data is unavailable (503), invalid windows are 400, and oversized responses are 413 at 2 MiB. Cache age/freshness still follows the separate cache manager and is not a live-data guarantee.

Job breakdowns contain metadata for jobs created in the requested window. They do not attribute the provider total to jobs or include every job that accrued charges during the period. Detail reads are bounded at 50 distinct job attempts and five list pages; SDK retries can make additional underlying calls. Listing/has-more status, failed-detail counts and up to 20 omission examples disclose limits. Monetary job fields remain null; wall time, configured capacity and arbitrary storage/transfer percentages do not establish billed cost.

The frontend shows observed totals, residual categories, missing/estimated dates, partial job metadata and unavailable amounts. CSV exports include selected period, currency/metric, observation time and coverage provenance, using shared quoting/formula protection. Export is not an invoice reconciliation.

## Low-usage review

GET `/api/ai-ml/sagemaker-idle-endpoints?threshold=10` describes recent observed endpoint usage, independent of historical report dates. Threshold is an integer from 0 to 1000000 and candidates have strictly fewer observed requests than the threshold. The legacy route/field names do not establish actual inactivity.

Only an InService endpoint with one standard real-time production variant is covered. Serverless, async, multiple/shadow variants and instance pools remain unsupported/unknown. Resource and CloudWatch regions must match. Every five-minute invocation bucket in one completed observed hour must be present with valid samples; missing/sparse metrics never become zero invocations. Current instance count comes from live endpoint observations. Unavailable evidence is counted with at most 20 examples and explicit truncation; inventory completeness remains unverified.

ModelLatency is a sample-weighted average of available observations converted from microseconds to milliseconds. Missing latency stays null. Its samples do not certify latency coverage for the entire hour. [AWS metric definitions](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html).

## Compute component and remaining limits

The product adapter matches region, instanceName, suffixed instanceType, component, operation and usage kind. It accepts one unambiguous current untiered USD/Hrs OnDemand SKU, reading at most 20 pricing pages. Unsupported, ambiguous, conflicting, future-term and missing products remain unavailable. No hardcoded/default rates are retained. A bounded [public us-east-1 catalog sample](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonSageMaker/current/us-east-1/index.json) supplied the observed attribute structure; matching in other regions and runtime behavior remain unvalidated.

Supported endpoint observations can expose cost_per_hour with cost_status=partial_compute_component, cost_scope=on_demand_compute_component_only and SKU/region/query-time provenance. This is a current on-demand compute component. It excludes storage, transfer, model/software charges, commitments and other adjustments; it does not reconstruct historical costs or prove avoidable savings. Total wasted cost/monthly waste remain null. Alternative-instance utilities require caller-supplied compatibility constraints; the service does not independently verify performance compatibility.

The AI/ML stack defines read-only Pricing:GetProducts and SageMaker:DescribeEndpointConfig permissions in source; these have not been deployed. No endpoint deletion, scaling or automatic action is added. Low-usage recommendations request workload review. GPU/Bedrock paths retain separate source-review gaps and are not validated by this SageMaker work.

See [active backlog](development-backlog.md), [API contracts](api-design.md) and [access/feature boundaries](access-and-feature-contracts.md).

Task 156 bounds low-usage reads to 20 distinct endpoint details and five list pages, exposes has_more, returns 503 for unavailable listing and caps responses at 2 MiB. Compute rates are looked up only for candidates and reused only within one identify call. SDK retries may add underlying calls; synchronous latency remains unvalidated.
