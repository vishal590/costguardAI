# CostGuard Auth + BFF Deployment

When you want **login/logout** and **API keys kept server-side**, deploy the BFF stack and point the frontend to it.

**October 14, 2026:** Implementation is ongoing; all further testing and live deployment validation are deferred. The stack now injects `BFF_USER_POOL_ID` and `BFF_USER_POOL_CLIENT_ID` from its own Cognito resources. The handler restricts issuer/client/token use/expiry and still requires Cognito GetUser validation. Missing identity configuration returns 503. Existing deployments need those settings through a later deployment; no stack was updated by this local work. See the [development backlog](../technical/development-backlog.md).

## 1. Deploy BFF stack

From `infrastructure/`:

```bash
cdk deploy CostGuardBFFStack \
  -c bff_main_url=https://YOUR_MAIN_API/prod \
  -c bff_main_key=YOUR_MAIN_KEY \
  -c bff_multi_account_url=https://YOUR_MULTI_ACCOUNT_API/prod \
  -c bff_multi_account_key=YOUR_MULTI_KEY \
  -c bff_aiml_url=https://YOUR_AIML_API/prod \
  -c bff_aiml_key=YOUR_AIML_KEY \
  -c bff_autonomous_url=https://YOUR_AUTONOMOUS_API/prod \
  -c bff_autonomous_key=YOUR_AUTONOMOUS_KEY
```

Or set env vars instead of `-c`: `BFF_MAIN_BASE_URL`, `BFF_MAIN_API_KEY`, etc.

If you see **502** with `"BFF backend not configured: BFF_MAIN_BASE_URL"`, the BFF was deployed without backend URLs. Redeploy with the `-c` arguments above (at least `bff_main_url` and `bff_main_key` for cost-data and cost-estimation).

**Outputs:** `UserPoolId`, `UserPoolClientId`, `BFFApiUrl`, `CognitoRegion`, `UserAccessTableName`.

The BFF reads active grants from `costguard-user-access` by verified Cognito subject. Prepare a grant item locally with `scripts/prepare_user_access.py`; applying it is deferred. A configured table never falls back to environment grants. Single-account backends now require the same configured backend key and signed BFF delegation, with their stack account injected by CDK. Legacy direct key mode needs deliberate `allow_direct_api_keys=true`. Multi-account gateway key records require explicit role/scopes and `is_bff_gateway=true`. See [access and feature contracts](../technical/access-and-feature-contracts.md) before a future deployment. No migration or deployment was applied.

## 2. Create a Cognito user

In AWS Console → Cognito → User Pools → your pool → Users → Create user (username + temporary password). User signs in and can change password.

Or use AWS CLI:

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <UserPoolId> \
  --username youruser \
  --temporary-password TempPass1! \
  --user-attributes Name=email,Value=you@example.com
```

## 3. Frontend .env

In `client-aws-ideas/.env`:

```env
VITE_BFF_BASE_URL=https://YOUR_BFF_API_ID.execute-api.us-east-1.amazonaws.com/prod
VITE_COGNITO_USER_POOL_ID=us-east-1_xxxxx
VITE_COGNITO_CLIENT_ID=xxxxx
VITE_AWS_REGION=us-east-1
```

Remove or leave blank the direct API URLs and keys when using BFF; the BFF holds them.

## 4. Behaviour

- **Without BFF:** Frontend calls CostGuard APIs directly with `X-API-Key` from env (no login).
- **With BFF:** Frontend calls only the BFF URL with `Authorization: Bearer <access_token>`. BFF checks the configured pool/client access-token claims and requires Cognito GetUser validation and forwards requests to the right API with the right key. Only signed-in users can use the app; keys never appear in the browser.

The BFF expects the **Cognito access token** (not the id token). The frontend stores the access token after sign-in and sends it on every request.
