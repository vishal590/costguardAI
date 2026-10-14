# Bedrock Observed Charges and Runtime Usage

**Source update: October 14, 2026; tasks 157-160.** Local backend/frontend implementation only. Tests, builds, synthesis, browser and AWS-account validation remain deferred. No model invocation, account query or deployment was performed while implementing these changes.

## Observed service charges

GET `/api/ai-ml/bedrock-costs` requires start_date/end_date over 1-31 completed DAILY dates with an exclusive end. BFF identity/current grants and backend account authorization apply.

The service reads all Cost Explorer pages within a 100-page/50,000-observation limit. It requires finite USD UnblendedCost, retains signed credits, rejects conflicting duplicates and preserves every returned usage type in the overall observed total. Missing/estimated/unknown dates disclose partial reporting; empty observations are null rather than a zero bill. This is the provider service filter Amazon Bedrock, not verified coverage of every model/provider billing service or a complete invoice.

Responses use data_contract=bedrock_observed_v2 and result_scope=observed_service_usage_costs. At most 100 usage types are listed, with total count, has-more, listed subtotal and unlisted observed residual. The full observed total includes retained types beyond the display bound. Provider limits/failures do not return a silently truncated successful total. Response artifacts are capped at 2 MiB; old cached contracts are ignored.

Usage-type names do not establish a runtime ModelId. Model-attributed rows, model count, invocation/token totals and cost-per-invocation fields remain unavailable. A model_id-filtered service-cost request returns 422. Guessed identity mappings and old/default model price recommendations have been removed from this path.

## Runtime usage

The legacy GET `/api/ai-ml/bedrock-cost-per-invocation` route now requires start_date/end_date/model and returns data_contract=bedrock_usage_observed_v2. Its historical route name does not establish cost attribution: total_cost, cost_per_invocation and cost/token ratios remain null, with cost_attribution_status=unavailable.

Runtime observations read actual AWS/Bedrock ModelId Invocations, InputTokenCount and OutputTokenCount metrics. Full daily coverage is required independently for each complete-period total. Partial observed subtotals and missing dates remain separate; sparse/failed metrics are unknown. Positive sample counts, finite nonnegative integral values, dated buckets and supported numeric precision are required. Tokens are never estimated as invocations multiplied by an average.

Invocations covers successful runtime calls; errors/throttles are separate metrics. InputTokenCount excludes cached tokens. Cache counters, AWS/BedrockMantle, Agents and extra dimensional scopes are not aggregated by this adapter. Observed runtime counters do not establish billed units or reconcile the service cost report. [AWS runtime metric definitions](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html), [token scope](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-token-burndown.html).

## Interface and remaining work

The frontend provides separate observed-cost and explicit-model runtime tabs, current-query loading/error/retry states, exclusive-date checks and complete/partial/missing coverage. It forwards model correctly and requires current response contracts before displaying results. Cost rows remain usage labels, not invented model identities.

No model compatibility/price recommendation, cost join, execution or invocation logging configuration is added. Actual billed attribution, other runtime namespaces/counters and GPU evidence/pricing remain separate work. No source change has been validated against a deployed account.

See [API contracts](api-design.md), [active backlog](development-backlog.md) and [feature boundaries](access-and-feature-contracts.md).
