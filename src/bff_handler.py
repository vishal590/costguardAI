"""
BFF (Backend-for-Frontend) Lambda: validates Cognito token and proxies to CostGuard APIs with API keys.

Frontend sends Authorization: Bearer <access_token>. BFF validates via Cognito GetUser, then forwards
the request to the appropriate backend (main, multi-account, aiml, autonomous) with X-API-Key. API keys never leave the backend.
"""
import base64
import binascii
import json
import logging
import math
import socket
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Any, Tuple, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from .services.access_control import AccessDenied, authorize_request, allows, sign_delegation, validate_grant

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Expose-Headers": "Content-Disposition",
}


def _get_backend_for_path(path: str) -> Tuple[str, str]:
    """Return (base_url_env_key, api_key_env_key) for the given path."""
    p = path if path.startswith("/") else "/" + path
    def matches(prefix):
        return p == prefix or p.startswith(prefix + "/")
    if matches("/api/autonomous"):
        return "BFF_AUTONOMOUS_BASE_URL", "BFF_AUTONOMOUS_API_KEY"
    if matches("/api/ai-ml"):
        return "BFF_AIML_BASE_URL", "BFF_AIML_API_KEY"
    if any(matches(prefix) for prefix in ("/api/organizations", "/api/costs", "/api/allocation", "/api/budgets", "/api/reports", "/api/forecasts", "/api/organization-advisor", "/api/organization-policies", "/api/business-metrics", "/api/unit-economics", "/api/commitments")):
        return "BFF_MULTI_ACCOUNT_BASE_URL", "BFF_MULTI_ACCOUNT_API_KEY"
    return "BFF_MAIN_BASE_URL", "BFF_MAIN_API_KEY"


def _query_string(event: Dict[str, Any]) -> Optional[str]:
    """Preserve HTTP API raw queries and REST API repeated values."""
    if isinstance(event.get("rawQueryString"), str):
        return event["rawQueryString"]
    single = event.get("queryStringParameters") or {}
    multiple = event.get("multiValueQueryStringParameters") or {}
    pairs = [(key, "" if value is None else value)
             for key, values in multiple.items() for value in values]
    pairs.extend((key, "" if value is None else value)
                 for key, value in single.items() if key not in multiple)
    return urllib.parse.urlencode(pairs) or None


def _access_grant(subject):
    """Read current server-controlled access; configured database never falls back."""
    table_name = os.environ.get("BFF_ACCESS_GRANTS_TABLE", "")
    if table_name:
        if not subject: return None
        try:
            item = boto3.resource("dynamodb", config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 1, "mode": "standard"})).Table(table_name).get_item(Key={"subject": subject}, ConsistentRead=True).get("Item")
        except Exception as exc:
            raise BFFConfigurationError("Access store unavailable") from exc
        return item.get("grant") if item and item.get("is_active") is True else None
    return json.loads(os.environ.get("BFF_ACCESS_GRANTS", "{}")).get(subject)


class BFFConfigurationError(RuntimeError):
    """Required server-side identity configuration is missing."""


class AuthenticationUnavailable(RuntimeError):
    pass


def _verify_cognito_token(token: str, region: str) -> Dict[str, Any]:
    """Bind the access token to this application, then validate it with Cognito.

    Decoded claims are untrusted until GetUser accepts the original token.
    Claim checks alone never authorize forwarding.
    """
    pool_id = os.environ.get("BFF_USER_POOL_ID", "")
    client_id = os.environ.get("BFF_USER_POOL_CLIENT_ID", "")
    if not pool_id or not client_id:
        raise BFFConfigurationError("Cognito pool/client configuration is missing")
    if len(token) > 16384 or len(token.split(".")) != 3:
        raise ValueError("Malformed access token")
    payload = token.split(".")[1]
    claims = json.loads(base64.b64decode(payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True))
    domain = "amazonaws.com.cn" if region.startswith("cn-") else "amazonaws.com"
    issuer = f"https://cognito-idp.{region}.{domain}/{pool_id}"
    if not isinstance(claims, dict) or claims.get("iss") != issuer or claims.get("client_id") != client_id or claims.get("token_use") != "access":
        raise ValueError("Token does not belong to the configured application")
    expiry = claims.get("exp")
    if type(expiry) not in (int, float) or not math.isfinite(expiry) or not expiry > time.time():
        raise ValueError("Expired or invalid token expiry")
    try:
        client = boto3.client("cognito-idp", region_name=region, config=Config(connect_timeout=2, read_timeout=4, retries={"max_attempts": 1, "mode": "standard"}))
        resp = client.get_user(AccessToken=token)
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') in ('NotAuthorizedException', 'InvalidParameterException', 'UserNotFoundException', 'UserNotConfirmedException', 'PasswordResetRequiredException'):
            raise ValueError('Access token was rejected') from error
        raise AuthenticationUnavailable('Cognito request unavailable') from error
    except Exception as error:
        raise AuthenticationUnavailable('Cognito request unavailable') from error
    if not isinstance(resp, dict): raise AuthenticationUnavailable('Invalid Cognito response')
    attributes = resp.get('UserAttributes', [])
    if not isinstance(attributes, list): raise AuthenticationUnavailable('Invalid Cognito attributes')
    subject = next((item.get('Value') for item in attributes if isinstance(item, dict) and item.get('Name') == 'sub'), None)
    if not isinstance(subject, str) or not subject or not isinstance(resp.get('Username'), str) or not resp['Username']:
        raise AuthenticationUnavailable('Cognito returned incomplete identity')
    return {'username': resp['Username'], 'subject': subject, 'attributes': attributes}


def _proxy_request(path: str, http_method: str, headers: Dict[str, str], body: Optional[str | bytes], query_string: Optional[str], timeout_seconds: float = 25.0) -> Tuple[int, Dict[str, str], str]:
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
    req_headers.update({key: value for key, value in headers.items() if key in ("X-CostGuard-Context", "X-CostGuard-Signature")})
    # Delegation is constructed server-side, never copied from client headers.
    req = urllib.request.Request(url, data=body.encode("utf-8") if isinstance(body, str) else body, headers=req_headers, method=http_method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers)
            return resp.getcode(), {**CORS_HEADERS, **{k.title(): v for k, v in resp_headers.items() if k.lower() in ("content-type", "access-control-allow-origin", "content-disposition")}}, resp_body
    except urllib.error.HTTPError as e:
        if e.code == 401:
            # Cognito already authenticated this user. Upstream key failures
            # must not trigger client logout or imply an expired user session.
            return 503, CORS_HEADERS, json.dumps({"error": "Backend authentication is unavailable", "code": "BACKEND_AUTHENTICATION_UNAVAILABLE"})
        try:
            body_str = e.read().decode("utf-8")
        except Exception:
            body_str = json.dumps({"error": str(e)})
        return e.code, CORS_HEADERS, body_str
    except (TimeoutError, socket.timeout):
        return 504, CORS_HEADERS, json.dumps({'error': 'Backend response deadline exceeded', 'code': 'BACKEND_TIMEOUT'})
    except urllib.error.URLError as error:
        status = 504 if isinstance(error.reason, (TimeoutError, socket.timeout)) else 502
        return status, CORS_HEADERS, json.dumps({'error': 'Backend request is temporarily unavailable'})
    except Exception as e:
        logger.exception("Proxy request failed")
        return 502, CORS_HEADERS, json.dumps({"error": "Backend request failed", "detail": str(e)})


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """API Gateway Lambda handler: validate JWT, then proxy."""
    started = time.monotonic()
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
            identity = _verify_cognito_token(token, region)
        except AuthenticationUnavailable:
            return {"statusCode": 503, "headers": CORS_HEADERS, "body": json.dumps({"error": "Authentication service is temporarily unavailable. Try again later.", "code": "AUTHENTICATION_UNAVAILABLE"})}
        except BFFConfigurationError:
            logger.error("BFF Cognito pool/client configuration is missing")
            return {"statusCode": 503, "headers": CORS_HEADERS,
                    "body": json.dumps({"error": "Authentication service is not configured"})}
        except Exception as e:
            logger.warning("Token verification failed: %s", type(e).__name__)
            return {
                "statusCode": 401,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Invalid or expired token"}),
            }
        path = event.get("path") or event.get("rawPath") or "/"
        # REST events normally omit the stage; strip it only when present.
        stage = event.get("requestContext", {}).get("stage") or "prod"
        if stage != "$default":
            prefix = "/" + stage
            if path.startswith(prefix + "/"):
                path = path[len(prefix):]
            elif path == prefix:
                path = "/"
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method") or "GET"
        if path == "/api/session" and http_method == "GET":
            try:
                try:
                    grant = validate_grant(_access_grant(identity.get("subject")))
                except AccessDenied:
                    grant = None
                return {"statusCode": 200, "headers": CORS_HEADERS,
                        "body": json.dumps({"authenticated": True, "username": identity.get("username"),
                            "subject": identity.get("subject"), "access_granted": grant is not None, "grant": grant})}
            except (ValueError, AttributeError, BFFConfigurationError):
                return {"statusCode": 503, "headers": CORS_HEADERS, "body": json.dumps({"error": "Access configuration is invalid"})}
        body = event.get("body")
        if event.get("isBase64Encoded"):
            try:
                body = base64.b64decode(body or "", validate=True)
            except (ValueError, TypeError, binascii.Error):
                return {"statusCode": 400, "headers": CORS_HEADERS,
                        "body": json.dumps({"error": "Invalid base64 request body"})}
        qs_str = _query_string(event)
        try:
            grant = _access_grant(identity.get("subject"))
            params = dict(urllib.parse.parse_qsl(qs_str or "", keep_blank_values=True))
            if body:
                from .services.request_json import prepare_json_body
                parsed_body = prepare_json_body({"body": body})
                params = {"query": params, "body": parsed_body}
            authorize_request(grant, http_method, path, params)
            if _get_backend_for_path(path)[0] != "BFF_MULTI_ACCOUNT_BASE_URL":
                account = os.environ.get("BFF_ACCOUNT_ID", "")
                if not account or not allows(grant, "accounts", account):
                    raise AccessDenied("Stack account is outside your scope")
            key_name = _get_backend_for_path(path)[1]
            key = os.environ.get(key_name, "")
            if not key:
                raise BFFConfigurationError("Backend key is missing")
            delegated = sign_delegation(key, identity["subject"], grant, http_method, path, qs_str, body)
        except AccessDenied as exc:
            return {"statusCode": 403, "headers": CORS_HEADERS, "body": json.dumps({"error": str(exc)})}
        except BFFConfigurationError:
            return {"statusCode": 503, "headers": CORS_HEADERS, "body": json.dumps({"error": "Backend access is not configured"})}
        except (ValueError, TypeError, AttributeError):
            return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"error": "Invalid request or access configuration"})}
        budget = min(25.0, 27.0-(time.monotonic()-started))
        if context is not None and hasattr(context, 'get_remaining_time_in_millis'):
            budget = min(budget, context.get_remaining_time_in_millis()/1000-1.0)
        if budget <= 0:
            return {'statusCode': 504, 'headers': CORS_HEADERS, 'body': json.dumps({'error': 'Request deadline exceeded', 'code': 'BFF_TIMEOUT'})}
        status_code, resp_headers, resp_body = _proxy_request(path, http_method, delegated, body, qs_str, timeout_seconds=budget)
        return {"statusCode": status_code, "headers": resp_headers, "body": resp_body}
    except Exception as e:
        logger.exception("BFF handler error")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Internal server error"}),
        }
