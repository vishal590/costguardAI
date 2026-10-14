# Multi-Account API Documentation

**Local implementation update:** October 14, 2026. All further validation is deferred. This reference describes the 24 methods in `infrastructure/multi_account_stack.py` and `src/multi_account_api_handler.py`.

## Authentication

Use the stack output `MultiAccountAPIEndpoint` as the base URL and send `X-API-Key`. The handler authenticates explicitly scoped key records in `costguard-api-keys`, enforces role/account/organization grants and checks an atomic quota in `costguard-rate-limits`. Gateway keys additionally require request-bound signed identity. The plan-by-default `setup_api_auth.py` prepares repeatable bootstrap/configuration; live apply remains deferred. With BFF, send a Cognito access token instead; the BFF forwards the configured multi-account key.

## Rate Limiting

The application rate limit defaults to 100 requests/minute per user and can be configured in the key record. The implementation uses a time-window counter; it does not emit the previously advertised `X-RateLimit-*` headers or implement a separate 200-request burst allowance. Invalid/missing keys return 401; application rate-limit failure returns 429.

## Endpoints

There is no `/api/multi-account` prefix. Use the dedicated multi-account API, rather than the main API's compatibility stubs.

| Method | Path |
|---|---|
| GET | `/api/organizations` |
| GET | `/api/organizations/{org_id}/accounts` |
| GET | `/api/costs/consolidated` |
| GET | `/api/costs/by-account` |
| GET | `/api/costs/account/{account_id}` |
| GET | `/api/allocation/by-tag` |
| GET | `/api/allocation/unallocated` |
| GET | `/api/allocation/rules` |
| POST | `/api/allocation/rules` |
| GET | `/api/budgets/hierarchy` |
| POST | `/api/budgets/organization` |
| POST | `/api/budgets/ou/{ou_id}` |
| GET | `/api/reports/showback` |
| GET | `/api/reports/chargeback` |
| GET | `/api/forecasts/organization` |
| GET | `/api/forecasts/account/{account_id}` |
| POST | `/api/organization-advisor/query` |
| GET | `/api/organization-policies/effective/{account_id}` |
| GET | `/api/organization-policies/{scope}/{entity_id}` |
| PUT | `/api/organization-policies/{scope}/{entity_id}` |
| GET | `/api/business-metrics/{account_id}` |
| PUT | `/api/business-metrics/{account_id}` |
| GET | `/api/unit-economics` |
| GET | `/api/commitments/analytics` |


## Requests

| Route family | Parameters/body |
|---|---|
| Organizations | No query parameters; account listing takes `org_id` in the path |
| Consolidated costs | `start_date`, `end_date`; `granularity` defaults to `MONTHLY` |
| Costs by account / one account | `start_date`, `end_date`; individual account ID is in the path |
| Allocation by tag | `start_date`, `end_date`; `tag_key` defaults to `Team` |
| Unallocated costs | `start_date`, `end_date` |
| Create allocation rule | JSON: required `rule_name`, `rule_type`, `allocation_target`; optional `conditions` (default `{}`), `priority` (default 100) |
| Budget hierarchy | `date` defaults to today's UTC date |
| Create organization / OU budget | JSON: required `budget_name`, numeric `budget_limit`; `time_unit` defaults to `MONTHLY`, `currency` to `USD`; OU ID is in the path |

Dates use `YYYY-MM-DD`. Date validation and returned data are endpoint-specific; use the handler rather than assuming identical optional fields. These routes do not define a general pagination-token contract.

## Responses and Organization Setup

Success payloads include endpoint-specific organization/account/cost/allocation/budget fields. Most include `success: true`. Validation/service errors generally use `success: false` with an `error` object containing `code` and `message`; authentication failures use the separate auth-error helper.

Some discovery-backed requests return 200 with empty data and an explanatory message when no AWS Organization is configured. A 200 response in that case does not demonstrate successful cross-account collection. AWS Organizations membership and cross-account roles are needed for meaningful organization data.

## Examples

`MULTI_ACCOUNT_API_ENDPOINT` is the stack output including its stage; replace the example dates with a range containing your data.

```bash
curl -H "X-API-Key: $MULTI_ACCOUNT_API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/organizations"

curl -H "X-API-Key: $MULTI_ACCOUNT_API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/organizations/$ORG_ID/accounts"

curl -H "X-API-Key: $MULTI_ACCOUNT_API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/costs/consolidated?start_date=2026-03-01&end_date=2026-03-31"

curl -H "X-API-Key: $MULTI_ACCOUNT_API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/allocation/by-tag?tag_key=Team&start_date=2026-03-01&end_date=2026-03-31"
```

## New Routes and Deferred Execution

New report/forecast/advisor and disabled policy-configuration routes are now defined, together with business measurements, unit economics and commitment analytics. They use the actual paths above; `/api/multi-account/...` remains unsupported. Live execution/policy application and validation are deferred. See [access and feature contracts](../access-and-feature-contracts.md).

## Related Documentation

- [Complete API contracts](../api-design.md)
- [Phase 5 README](README.md)
- [Cross-account setup](../../../infrastructure/CROSS_ACCOUNT_SETUP.md)
- [Deployment scripts](../../deployment/DEPLOYMENT_SCRIPTS.md)
