# Phase 2 Forecast Timeout and Bedrock Reference

**Keywords (for search):** Phase 2, cost-forecast, forecast timeout, Bedrock, Nova Lite, quota, ThrottlingException, API Gateway 29s, Lambda logs, CloudWatch, insufficient data, cache hit, amazon.nova-lite-v1:0

**Related docs:** [Phase 2 README](./README.md) · [Deployment troubleshooting](../../deployment/DEPLOYMENT_TROUBLESHOOTING.md) · [DOCUMENTATION_MAP](../../DOCUMENTATION_MAP.md#phase-2-ai-powered-cost-forecasting--complete)

---

## Purpose

This document records what was tried when the **cost-forecast API** returned a **timeout** response (`success: false`, `error: "timeout"`, empty `forecast_data`) so the same diagnosis and fixes can be reused. It is intended for semantic search and cross-reference (e.g. "forecast timeout", "Bedrock quota", "Phase 2 not working").

---

## 1. Problem Summary

- **API:** `GET /api/cost-forecast?days=30&granularity=daily` (and `/api/cost-forecast/service/{service}`).
- **Observed response:** HTTP 200 with body `success: false`, `forecast_data: []`, `error: "timeout"`, `message: "Forecast is taking longer than expected (API limit)..."`.
- **When:** From first use; also with `days=7` or `days=14` (same timeout).
- **Constraint:** API Gateway integration timeout is **29 seconds**; the handler uses a **28-second** thread timeout and returns this payload if the forecast thread is still running.

---

## 2. Code and Flow (Cross-Reference)

| Component | Location | Role |
|-----------|----------|------|
| **Forecast handler** | `src/lambda_handler.py` — `handle_forecast_request`, `handle_forecast_service_request` | Parses `days`/`granularity`, runs forecast in a daemon thread, waits up to `FORECAST_THREAD_TIMEOUT` (28s), returns timeout payload if thread still alive. |
| **Thread timeout constant** | `src/lambda_handler.py` — `FORECAST_THREAD_TIMEOUT = 28.0` | Keeps response under API Gateway 29s limit. |
| **Forecast engine** | `src/services/forecast_engine.py` — `generate_forecast()` | Cache check → historical data (30 days) → validate → Bedrock `invoke_forecast()` → build response → cache store. |
| **Historical data** | `src/services/historical_data.py` — `get_historical_data()` | Reads from DynamoDB cost table (`COST_DATA_TABLE`); requires ≥30 data points or raises `InsufficientDataError`. |
| **Bedrock client** | `src/services/bedrock_client.py` — `invoke_forecast()`, `_invoke_model()`, `retry_with_backoff()` | Model ID **`amazon.nova-lite-v1:0`** (Nova Lite v1). Retries on `ThrottlingException` with backoff (1s, 2s, 4s). |
| **Forecast cache** | `src/services/forecast_cache.py` | Cache read/write; cache hits return immediately (no timeout). |

If the **combined** time (cold start + DynamoDB + Bedrock + retries) exceeds 28 seconds, the handler returns the timeout response and does **not** wait for or log the thread’s eventual success or failure.

---

## 3. Root Causes (What We Concluded)

1. **Bedrock quota / rate limit**  
   When Bedrock returns 429 (ThrottlingException), the client retries with backoff. Retries can push total time over 28s, so the API returns timeout instead of 429. **Fix:** Increase Bedrock quota for Nova Lite (e.g. requests per minute) in **Bedrock console → Quotas** or **Service Quotas**.

2. **Bedrock first-time / cold latency**  
   First request to a model (or after eviction) can be slow (tens of seconds). Together with DynamoDB and cold start, total time can exceed 28s. **Mitigation:** Retry the same request later; once a result is cached, subsequent identical requests are fast (cache hit).

3. **Insufficient cost data**  
   If DynamoDB has &lt;30 data points for the range, the thread raises `InsufficientDataError` and the handler would return **400** with a clear message—**not** the timeout payload. So timeout implies we got past historical data (or the thread was still busy before that).

---

## 4. What We Tried (No Code Changes Required From You)

- **Cache serialization fix:** Forecast response (dataclass) was passed to cache `store_forecast()` and `json.dumps()` failed on cache miss. Fixed by serializing to dict (e.g. `asdict`) before storing. **Ref:** `src/services/forecast_engine.py`.
- **Thread timeout:** Increased from 25s to 28s to use more of the 29s API Gateway limit. **Ref:** `src/lambda_handler.py` — `FORECAST_THREAD_TIMEOUT = 28.0`.
- **Historical data window:** Reduced from 45 to 30 days to shrink the Bedrock prompt and speed up inference. **Ref:** `src/services/forecast_engine.py` — `days_back=30`.
- **Confirming Bedrock model:** Cost-forecast uses **Nova Lite (v1)** only: model ID **`amazon.nova-lite-v1:0`**. Not Nova 2 Lite. **Ref:** `src/services/bedrock_client.py`.
- **Console checks:** Model access (Nova Lite enabled in us-east-1), Quotas (Nova Lite or on-demand inference limits). Anthropic “submit use case” banner applies only to Claude, not Nova Lite.

---

## 5. How to Diagnose (Lambda Logs)

- **Log group:** `/aws/lambda/CostGuardLambda` (or the CostGuard Lambda name from your stack).
- **Useful messages:**
  - `Generating forecast: days=30, granularity=daily` — request reached forecast handler.
  - `Forecast request timed out after 28s` — 28s limit hit; timeout response returned.
  - No Bedrock or DynamoDB error is logged when we timeout, because the handler returns before the thread finishes.
- **How to search:** CloudWatch → Log groups → select the Lambda log group → **Search log group** with phrase `Forecast request timed out` or `Generating forecast`. Or use **Logs Insights** with a query like:
  `fields @timestamp, @message | filter @message like /Generating forecast|Forecast request timed out/ | sort @timestamp desc`
- **REPORT line:** Duration ~28,000 ms and Billed Duration ~28s confirm the request ran until the timeout.

**Cross-reference:** [DEPLOYMENT_TROUBLESHOOTING.md](../../deployment/DEPLOYMENT_TROUBLESHOOTING.md) for general Lambda/API debugging.

---

## 6. How to Fix (Actionable)

1. **Bedrock Quotas**  
   - Bedrock console → **Labs → Quotas (New)** (or Service Quotas → Amazon Bedrock).  
   - Find **Nova Lite** (or on-demand inference for Nova Lite).  
   - **Request quota increase** (e.g. requests per minute) so that normal + retry traffic fits within limit.

2. **Model access**  
   - Bedrock → **Model catalog** → filter **Amazon** → **Nova Lite** (`amazon.nova-lite-v1:0`).  
   - Ensure **Access granted** in **us-east-1**; if not, request access.

3. **Retry and cache**  
   - After quota is increased, call the API again (e.g. `days=7` first).  
   - Once one request completes within 28s, that result is cached; repeat same params for a cache hit and fast response.

4. **If timeouts persist**  
   - Consider an **async pattern:** return 202 Accepted, run forecast in background, client polls for result (or use a longer integration timeout if you change away from the 29s API Gateway limit).

---

## 7. Example Lambda Log Snippet (What You Saw)

```
[INFO]  Generating forecast: days=30, granularity=daily
[INFO]  Found credentials in environment variables.
[WARNING] Forecast request timed out after 28s
REPORT  Duration: 28008.08 ms  Billed Duration: 28451 ms
```

Same pattern for `days=7`. No exception or Bedrock error in the same request because the handler had already returned the timeout response.

---

## 8. Cross-References for Discoverability

- **Phase 2 overview:** [Phase 2 README](./README.md)
- **Documentation map (Phase 2):** [DOCUMENTATION_MAP.md](../../DOCUMENTATION_MAP.md#phase-2-ai-powered-cost-forecasting--complete)
- **Deployment / troubleshooting:** [DEPLOYMENT_TROUBLESHOOTING.md](../../deployment/DEPLOYMENT_TROUBLESHOOTING.md)
- **API examples:** [API_EXAMPLES.md](../../API_EXAMPLES.md) (if Phase 2 examples exist)
- **Backend handlers:** `src/lambda_handler.py` (forecast), `src/services/forecast_engine.py`, `src/services/bedrock_client.py`, `src/services/historical_data.py`

---

**Last updated:** March 2026  
**Status:** Reference doc; no code changes in this file. Use when investigating "forecast timeout", "Phase 2 not working", or "Bedrock quota" next time.
