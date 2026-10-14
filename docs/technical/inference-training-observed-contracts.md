# Inference Counters and Training Metadata

**Source update: October 14, 2026; tasks 169-172.** Local implementations only. All tests, builds, synthesis, browser checks, AWS-account calls and deployment remain deferred.

## One explicit inference telemetry source

GET `/api/ai-ml/cost-per-inference` now requires start_date/end_date/source/endpoint. The legacy path does not establish monetary attribution. Dates cover 1-31 completed DAILY dates with an exclusive end. Optional model is a supplied label, not verified model identity.

| Source | Endpoint identity | Required extra field | Provider counter |
|---|---|---|---|
| lambda | Unqualified FunctionName metric value | None | AWS/Lambda Invocations Sum |
| sagemaker | EndpointName | variant | AWS/SageMaker Invocations Sum for that variant |
| bedrock | Runtime ModelId | None | AWS/Bedrock Invocations Sum |
| api_gateway_rest | REST ApiName dimension | stage | AWS/ApiGateway Count SampleCount |

Exactly one source is read. Counts from API/function/model layers are not added together. Positive valid samples and dated integral counters are required. Full daily coverage is needed for a complete-period total; partial observed subtotal and missing dates remain separate. Sparse/failed dates are unknown, never zero. These are provider counters, not independently verified business inference volume.

Lambda invocations can include function errors, batching and retries. API stage counts include error requests. Model counters and additional namespaces/dimensions have their own scope. [Lambda definitions](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html), [API Gateway statistics/dimensions](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-metrics-and-dimensions.html).

Responses use inference_counter_observations_v2 with data_quality including namespace/metric/statistic, dimensions, region, daily values and semantics. Total/compute/API/transfer costs, cost_per_inference and cost-threshold decisions remain null: account-wide service charges do not establish endpoint-attributed costs or a matching billable denominator. No old cached unit-cost payload is used.

GET `/api/ai-ml/inference-trends` requires source/endpoint, optional variant/stage and days=1..31. It reads one completed daily window and returns inference_counter_trends_v2, preserving missing counts and unavailable monetary values. No ongoing partial day is mislabeled complete.

## Explicit training/resource metadata

GET `/api/ai-ml/cost-per-training` now requires job_id/source. source=sagemaker means a training job name; source=ec2_instance means an EC2 instance ID. There is no source-guessing fallback after an outage.

SageMaker metadata retains supplied model/dataset labels, observed job status, provider start/end times and TrainingTimeInSeconds when present/valid. Missing fields stay null. Provider training seconds do not establish billed cost. EC2 metadata retains resource tags/state/type and last launch time; instance uptime and state-transition text are never treated as training start/end or duration. Labels are not independently verified model/dataset identity. [AWS DescribeTrainingJob](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeTrainingJob.html).

Responses use training_metadata_observed_v2 and include timing/source/region/observation metadata. Attributed cost components, total and hourly cost remain null. Service/account storage/transfer charges are not assigned to a job. No old cached cost-per-training payload is used.

GET `/api/ai-ml/training-comparison` validates model/instance selections but returns training_comparison_scope_v2 with comparison_status=unavailable. Matched workload benchmarks, hardware compatibility and billing offers are required before estimating duration or ranking costs. Fixed default durations/rates and first-item baselines do not establish a comparison.

## Interface

The frontend provides a selected inference-counter view and an explicit training/resource metadata view, with current-contract guards, loading/error/retry and submitted-source labels. The job/resource snapshot is independent of page cost-report dates. It displays nullable observed times/counts and unavailable unit costs, without claiming measured zero or verified model labels.

No billing attribution adapter, benchmark run or resource operation is added. Required routes/IAM/configuration must be deployed before the new contracts can operate. Runtime behavior remains unvalidated.
