# Phase 4 Specification: AI Cost Advisor

**Source review:** October 3, 2026.

## Implemented Contract

The main Lambda exposes POST `/api/advisor/query`, GET/DELETE `/api/advisor/history`, and GET `/api/advisor/suggestions`. `advisor_engine.py` coordinates query processing, cost context, Bedrock responses, caching and conversation history. Insights use historical cost, forecast and prevention services.

The main CDK stack defines `advisor-cache` (partition key `query_hash`, TTL `ttl`) and `advisor-conversation-history` (partition key `session_id`, numeric sort key `timestamp`, TTL `ttl`), with Lambda read/write grants and API routes. Infrastructure code is implemented; this review did not verify the live deployment.

## References

- [API contracts](../api-design.md)
- [Database schema](../database-design.md)
- [Phase 4 README](README.md)
- [Implementation history](implementation-summary.md)
- [Infrastructure configuration](infrastructure-updates.md)

Earlier performance/coverage figures are historical evidence rather than results from this source review.
