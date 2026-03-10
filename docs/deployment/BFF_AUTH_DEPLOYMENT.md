# CostGuard Auth + BFF Deployment

When you want **login/logout** and **API keys kept server-side**, deploy the BFF stack and point the frontend to it.

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

**Outputs:** `UserPoolId`, `UserPoolClientId`, `BFFApiUrl`, `CognitoRegion`.

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
- **With BFF:** Frontend calls only the BFF URL with `Authorization: Bearer <access_token>`. BFF validates the token (Cognito GetUser) and forwards requests to the right API with the right key. Only signed-in users can use the app; keys never appear in the browser.

The BFF expects the **Cognito access token** (not the id token). The frontend stores the access token after sign-in and sends it on every request.
