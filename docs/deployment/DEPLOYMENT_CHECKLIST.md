# Phase 4 Deployment Checklist

**Source review:** October 3, 2026. Advisor infrastructure is already defined in `CostGuardStack`. These are deployment and verification steps, not missing implementation tasks. This checklist has not been executed against AWS in the documentation pass.

## Before Deployment

- [ ] Review [current status](../PROJECT_STATUS.md) and [known code limitations](../technical/documentation-code-sync.md).
- [ ] Configure AWS credentials, account and region for the intended environment.
- [ ] Install infrastructure requirements and CDK; confirm bootstrap status for that environment.
- [ ] Confirm Bedrock access and the existing main stack/table state.
- [ ] Run the relevant local tests and record their current results; earlier reported counts are historical.
- [ ] Review the CDK diff before applying changes.

## Deploy Existing Definitions

From `infrastructure/`, use `cdk deploy CostGuardStack`. The stack already defines advisor tables, read/write grants, main Lambda configuration and API methods. See [infrastructure configuration](../technical/phase4-ai-advisor/infrastructure-updates.md).

## Verify the Deployed Stack

- [ ] Confirm CloudFormation update completion.
- [ ] Verify `advisor-cache`: partition key `query_hash`, TTL `ttl`.
- [ ] Verify `advisor-conversation-history`: partition key `session_id`, numeric sort key `timestamp`, TTL `ttl`.
- [ ] Confirm main Lambda table access and Bedrock permissions/configuration.
- [ ] Use `APIEndpoint` for POST `/api/advisor/query` and GET `/api/advisor/suggestions`.
- [ ] Exercise GET/DELETE `/api/advisor/history` with a test session.
- [ ] Check validation errors, response bodies and logs using the [current API contracts](../technical/api-design.md).
- [ ] If BFF is deployed, verify Cognito access-token requests and the configured main backend URL/key.
- [ ] Record fresh evidence in a dated report; do not overwrite historical reports as though they were new results.

## Related Guidance

- [Advisor README](../technical/phase4-ai-advisor/README.md)
- [BFF deployment](BFF_AUTH_DEPLOYMENT.md)
- [Deployment guide](DEPLOYMENT_GUIDE.md)
