# AWS Services Used by CostGuard

**Source review:** October 13, 2026. This catalog describes services referenced by the checked-in backend and CDK app. Historical competition requirements and cost estimates are recorded separately in [competition docs](../competition/overview.md) and [project history](../PROJECT_STATUS.md).

## Core Services

| Service | Current role | Source |
|---|---|---|
| Lambda | Main API, multi-account handlers, AI/ML API, autonomous workers/API and BFF | Five stack modules in `infrastructure/` |
| API Gateway | Separate REST APIs with Lambda integration; BFF proxy | `cdk_stack.py`, `multi_account_stack.py`, `aiml_stack.py`, `autonomous_stack.py`, `bff_stack.py` |
| DynamoDB | Historical costs, caches, configuration, organization metadata and audit/checkpoint records | [Schema inventory](database-design.md) |
| Cognito | User pool/client; access-token validation in BFF | `bff_stack.py`, `src/bff_handler.py` |
| IAM | Lambda execution roles, service permissions and cross-account access | Stack modules and role templates |

## AI/ML and Cost Services

| Service | Current role |
|---|---|
| Amazon Bedrock | Forecast and advisor model invocation; workload cost tracking |
| Cost Explorer | Historical AWS cost retrieval and workload/multi-account cost queries |
| CloudWatch | Usage/utilization metrics, logs, alarms and dashboards |
| AWS Pricing | Price lookup and estimation/recommendation inputs |
| AWS Budgets | Budget monitoring and integration with prevention/advisor services |
| SageMaker | Training/inference/notebook workload information and cost tracking |
| EC2 | GPU discovery, resource actions, spot and right-sizing workflows |

The core forecast engine requests 30 days of stored history and accepts a minimum of 7 days. GPU utilization is implemented with GPU metrics and CPU fallback. See [API contracts](api-design.md) for behavior and [known limitations](documentation-code-sync.md) for remaining execution gaps.

## Infrastructure Services

| Service | Current role |
|---|---|
| EventBridge | Scheduled collection/monitoring and custom autonomous event bus |
| EventBridge Scheduler | One-time approved EC2 start/stop and replacement-expiry callbacks |
| Secrets Manager | Generated autonomous approval HMAC key |
| SQS | Dead-letter storage for failed execution/callback deliveries |
| SNS | Warnings, action/error notifications, autonomous approval/alert topics |
| S3 | Autonomous checkpoint storage, datasets and verified model-state results |
| Systems Manager | Fixed EC2 reference-training command and invocation-status verification |
| AWS Organizations | Organization, OU and account discovery |
| STS | Cross-account role assumption |
| CloudFormation / CDK | Stack deployment and cross-account role templates |

The frontend is maintained in a separate repository. Static-site hosting choices from earlier planning documents are not defined by this backend's five-stack CDK app.

## Service Integration

The main stack provides historical data, estimates, forecasts, prevention and advisor APIs. Multi-account has its own organization/cost/allocation/budget routes. AI/ML has its own API and GPU tables. Autonomous has six workers plus a separate nine-route API and consumes the AI/ML GPU-cost table. BFF validates Cognito tokens and forwards requests to the configured backend URLs.

## Costs and Quotas

The source uses caching, TTL, scheduled work and on-demand tables to manage resource usage. It does not guarantee zero cost, Free Tier eligibility, current AWS prices/quotas or realized savings. Earlier numeric estimates and demo timings are historical scenarios; measure the deployed account before treating them as operating costs or performance guarantees.

## References

- [Architecture](architecture.md)
- [API design](api-design.md)
- [Database design](database-design.md)
- [Current project status](../PROJECT_STATUS.md)
- [BFF deployment](../deployment/BFF_AUTH_DEPLOYMENT.md)
