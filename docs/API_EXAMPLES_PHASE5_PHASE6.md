# API Examples - Phase 5 and Phase 6

**Source review:** October 3, 2026. Examples follow the current CDK paths. Base URL variables contain the appropriate stack output including the stage; API keys must satisfy that backend's authentication requirements.

## Phase 5: Multi-Account Cost Management

Set `MULTI_ACCOUNT_API_ENDPOINT` to `MultiAccountAPIEndpoint`, and use a key initialized with `setup_api_auth.py`. The deployed API uses `/api/organizations`, `/api/costs`, `/api/allocation` and `/api/budgets`.

```bash
curl -H "X-API-Key: $MULTI_ACCOUNT_API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/organizations"

curl -H "X-API-Key: $MULTI_ACCOUNT_API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/organizations/$ORG_ID/accounts"

curl -H "X-API-Key: $MULTI_ACCOUNT_API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/costs/consolidated?start_date=2026-03-01&end_date=2026-03-31"

curl -H "X-API-Key: $MULTI_ACCOUNT_API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/allocation/by-tag?tag_key=Team&start_date=2026-03-01&end_date=2026-03-31"

curl -H "X-API-Key: $MULTI_ACCOUNT_API_KEY" \
  "$MULTI_ACCOUNT_API_ENDPOINT/api/budgets/hierarchy?date=2026-03-01"
```

See [all eleven routes and request fields](technical/phase5-multi-account/API_DOCUMENTATION.md). Report, cross-account forecast and prevention service modules do not imply additional REST routes.

## Phase 6: AI/ML Workload Cost Management

Set `AIML_API_ENDPOINT` to `AIMLAPIEndpoint`. Use this stack's URL, not the main API URL. Replace the example dates and instance ID with actual data.

```bash
curl -H "X-API-Key: $AIML_API_KEY" \
  "$AIML_API_ENDPOINT/api/ai-ml/gpu-costs?start_date=2026-03-01&end_date=2026-03-31"

curl -H "X-API-Key: $AIML_API_KEY" \
  "$AIML_API_ENDPOINT/api/ai-ml/gpu-utilization?start_date=2026-03-01&end_date=2026-03-31&instance_id=i-0123456789abcdef0"

curl -H "X-API-Key: $AIML_API_KEY" \
  "$AIML_API_ENDPOINT/api/ai-ml/spot-recommendations?workload_id=i-0123456789abcdef0"
```

GPU utilization returns per-instance `avg_utilization`, a metric pattern and a timestamp; missing metrics can produce null utilization. Spot recommendations require `workload_id` rather than a date-only request. The two multi-account GPU cost/utilization paths dispatch to their dedicated multi-account handlers; see [source synchronization review](technical/documentation-code-sync.md).

## BFF Requests

With Cognito/BFF configured, use `BFFApiUrl` and a Cognito **access token**. Backend keys remain server-side.

```bash
curl -H "Authorization: Bearer $COGNITO_ACCESS_TOKEN" \
  "$BFF_API_ENDPOINT/api/ai-ml/gpu-utilization?start_date=2026-03-01&end_date=2026-03-31"
```

## Complete Documentation

- [API design](technical/api-design.md)
- [AI/ML API reference](api/phase6-api-documentation.md)
- [BFF setup](deployment/BFF_AUTH_DEPLOYMENT.md)
- [Autonomous endpoints](technical/phase6-extension-endpoints-and-frontend.md)
