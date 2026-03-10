"""
BFF (Backend-for-Frontend) Lambda: validates Cognito token and proxies to CostGuard APIs with API keys.

Frontend sends Authorization: Bearer <access_token>. BFF validates via Cognito GetUser, then forwards
the request to the appropriate backend (main, multi-account, aiml, autonomous) with X-API-Key. API keys never leave the backend.
"""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Any, Tuple, Optional

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}


def _get_backend_for_path(path: str) -> Tuple[str, str]:
    """Return (base_url_env_key, api_key_env_key) for the given path."""
    p = path if path.startswith("/") else "/" + path
    if "/api/autonomous" in p:
        return "BFF_AUTONOMOUS_BASE_URL", "BFF_AUTONOMOUS_API_KEY"
    if "/api/ai-ml" in p:
        return "BFF_AIML_BASE_URL", "BFF_AIML_API_KEY"
    if p.startswith("/api/organizations") or p.startswith("/api/costs") or p.startswith("/api/allocation") or p.startswith("/api/budgets"):
        return "BFF_MULTI_ACCOUNT_BASE_URL", "BFF_MULTI_ACCOUNT_API_KEY"
    return "BFF_MAIN_BASE_URL", "BFF_MAIN_API_KEY"


def _verify_cognito_token(token: str, region: str) -> Dict[str, Any]:
    """Validate token via Cognito GetUser (uses access token). Returns user info or raises."""
    client = boto3.client("cognito-idp", region_name=region)
    resp = client.get_user(AccessToken=token)
    return {"username": resp.get("Username"), "attributes": resp.get("UserAttributes", [])}


def _proxy_request(path: str, http_method: str, headers: Dict[str, str], body: Optional[str], query_string: Optional[str]) -> Tuple[int, Dict[str, str], str]:
    """Forward request to the right backend; return (status_code, headers, body)."""
    base_key, key_key = _get_backend_for_path(path)
    base_url = (os.environ.get(base_key) or "").rstrip("/")
    api_key = os.environ.get(key_key) or ""
    if not base_url:
        return 502, CORS_HEADERS, json.dumps({"error": f"BFF backend not configured: {base_key}"})
    url = base_url + path + (f"?{query_string}" if query_string else "")
    req_headers = {"Content-Type": "application/json"}
    if api_key:
        req_headers["X-API-Key"] = api_key
    # Forward a few safe headers (e.g. none that leak auth)
    req = urllib.request.Request(url, data=body.encode("utf-8") if body else None, headers=req_headers, method=http_method)
    try:
        with urllib.request.urlopen(req, timeout=29) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers)
            return resp.getcode(), {**CORS_HEADERS, **{k: v for k, v in resp_headers.items() if k.lower() in ("content-type", "access-control-allow-origin")}}, resp_body
    except urllib.error.HTTPError as e:
        try:
            body_str = e.read().decode("utf-8")
        except Exception:
            body_str = json.dumps({"error": str(e)})
        return e.code, CORS_HEADERS, body_str
    except Exception as e:
        logger.exception("Proxy request failed")
        return 502, CORS_HEADERS, json.dumps({"error": "Backend request failed", "detail": str(e)})


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """API Gateway Lambda handler: validate JWT, then proxy."""
    try:
        headers = event.get("headers") or {}
        # API Gateway may lowercase headers
        auth = headers.get("Authorization") or headers.get("authorization") or ""
        if not auth.startswith("Bearer "):
            return {
                "statusCode": 401,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Missing or invalid Authorization header"}),
            }
        token = auth[7:].strip()
        region = os.environ.get("AWS_REGION", "us-east-1")
        try:
            _verify_cognito_token(token, region)
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return {
                "statusCode": 401,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Invalid or expired token"}),
            }
        path = event.get("path") or event.get("rawPath") or "/"
        # Strip API Gateway stage prefix (e.g. /prod) so we don't double it when forwarding
        if path.startswith("/prod/"):
            path = path[5:]
        elif path == "/prod":
            path = "/"
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method") or "GET"
        body = event.get("body")
        query_string = event.get("queryStringParameters")
        qs_str = None
        if query_string and isinstance(query_string, dict):
            qs_str = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query_string.items())
        elif isinstance(event.get("rawQueryString"), str):
            qs_str = event.get("rawQueryString")
        status_code, resp_headers, resp_body = _proxy_request(path, http_method, {}, body, qs_str)
        return {"statusCode": status_code, "headers": resp_headers, "body": resp_body}
    except Exception as e:
        logger.exception("BFF handler error")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Internal server error"}),
        }
