# Phase 4: AI Cost Advisor - Infrastructure Configuration

**Source review:** October 3, 2026. Phase 4 infrastructure is already implemented in `infrastructure/cdk_stack.py`. This guide describes deployment/configuration of existing definitions; it does not establish live AWS status.

## Tables and API Routes

| Resource | Current definition |
|---|---|
| Advisor cache | `advisor-cache`, string partition key `query_hash`, TTL `ttl` |
| Conversation history | `advisor-conversation-history`, string partition key `session_id`, numeric sort key `timestamp`, TTL `ttl` |
| Lambda permissions | Both tables grant read/write access to the main Lambda role |
| API | POST `/api/advisor/query`, GET/DELETE `/api/advisor/history`, GET `/api/advisor/suggestions` |

These resources belong to `CostGuardStack`, alongside Phases 1-3. Do not create alternative table names or a separate advisor stack based on old manual deployment notes. Exact environment and IAM definitions are in the [main CDK source](../../../infrastructure/cdk_stack.py).

## Deployment

Install the infrastructure requirements and use CDK from `infrastructure/`. To deploy/update the main stack:

```bash
cdk deploy CostGuardStack
```

The stack output `APIEndpoint` is the main API base URL including the stage. With BFF, configure its main backend URL/key and use a Cognito access token. See [BFF setup](../../deployment/BFF_AUTH_DEPLOYMENT.md).

## Verification After Deployment

Check CloudFormation completion and the main Lambda's environment/permissions. Confirm the two table schemas, then exercise advisor query, suggestions and history on the correct API URL using credentials accepted by that API. Bedrock access and meaningful cost/prevention context are needed for useful responses. Record fresh endpoint outcomes and logs rather than assuming historical test counts apply.

## References

- [Current advisor contract](specification.md)
- [API design](../api-design.md)
- [Database schemas](../database-design.md)
- [Deployment checklist](../../deployment/DEPLOYMENT_CHECKLIST.md)
- [Current source status](../../PROJECT_STATUS.md)
