"""Server-managed grants and request-bound BFF delegation."""
import base64
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl, urlencode

ROLES = {"viewer", "operator", "admin"}


class AccessDenied(ValueError):
    pass


class BackendAuthenticationError(AccessDenied):
    pass


class BackendConfigurationError(RuntimeError):
    pass


def validate_grant(grant):
    if not isinstance(grant, dict) or grant.get("role") not in ROLES:
        raise AccessDenied("No application access grant")
    for key in ("organizations", "accounts"):
        values = grant.get(key)
        if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value for value in values):
            raise AccessDenied("Missing organization/account scope")
    return {"role": grant["role"], "organizations": list(grant["organizations"]), "accounts": list(grant["accounts"])}


def allows(grant, kind, value):
    return "*" in grant.get(kind, []) or value in grant.get(kind, [])


def authorize_request(grant, method, path, params):
    validate_grant(grant)
    if path.endswith('/prevention/config') and method not in ('GET', 'HEAD', 'OPTIONS') and grant['role'] != 'admin':
        raise AccessDenied('Administrator role required for monitoring configuration')
    if method not in ("GET", "HEAD", "OPTIONS") and grant["role"] == "viewer":
        # Advisor questions read existing costs; they do not change AWS resources.
        if not ((method == "POST" and path in ("/api/advisor/query", "/api/organization-advisor/query")) or (method == "DELETE" and path == "/api/advisor/history")):
            raise AccessDenied("Operator role required")
    if path.startswith("/api/budgets") and ("*" not in grant["accounts"] or (method not in ("GET", "HEAD") and grant["role"] != "admin")):
        raise AccessDenied("Organization administrator with full account scope required")
    if path.startswith("/api/allocation/rules") and "*" not in grant["accounts"]:
        raise AccessDenied("Rule configuration requires full account scope")
    if path.startswith("/api/allocation/rules") and method != "GET" and (grant["role"] != "admin" or "*" not in grant["accounts"]):
        raise AccessDenied("Organization administrator with full account scope required")
    if "/multi-account/" in path and "*" not in grant["accounts"] and not params.get("account_ids") and not params.get("query", {}).get("account_ids"):
        raise AccessDenied("Explicit scoped account IDs required")
    if path.startswith("/api/organization-policies") and "*" not in grant["accounts"]:
        raise AccessDenied("Policy inspection requires full account scope")
    if path.startswith("/api/organization-policies") and method not in ("GET", "HEAD") and (grant["role"] != "admin" or "*" not in grant["accounts"]):
        raise AccessDenied("Organization administrator required")
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[:2] == ["api", "organizations"] and not allows(grant, "organizations", parts[2]):
        raise AccessDenied("Organization is outside your scope")
    if len(parts) >= 4 and parts[:3] == ["api", "costs", "account"] and not allows(grant, "accounts", parts[3]):
        raise AccessDenied("Account is outside your scope")
    def inspect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                kind = "organizations" if key in ("org_id", "organization_id", "org_ids") else "accounts" if key in ("account_id", "account_ids") else None
                if kind:
                    identifiers = item if isinstance(item, list) else str(item).split(",")
                    if any(not allows(grant, kind, identifier) for identifier in identifiers):
                        raise AccessDenied("Requested resource is outside your scope")
                inspect(item)
        elif isinstance(value, list):
            for item in value: inspect(item)
    inspect(params)


def canonical_request(method, path, query, body):
    if isinstance(body, str): body = body.encode()
    return {"method": method.upper(), "path": path,
            "query": urlencode(sorted(parse_qsl(query or "", keep_blank_values=True))),
            "body_sha256": hashlib.sha256(body or b"").hexdigest()}


def sign_delegation(key, identity, grant, method, path, query, body):
    payload = {"subject": identity, "grant": validate_grant(grant), "issued_at": int(time.time()),
               "request": canonical_request(method, path, query, body)}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode()
    signature = hmac.new(key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return {"X-CostGuard-Context": encoded, "X-CostGuard-Signature": signature}


def verify_delegation(key, headers, method, path, query, body):
    encoded = headers.get("x-costguard-context", "")
    signature = headers.get("x-costguard-signature", "")
    if not encoded or len(encoded) > 16384 or not hmac.compare_digest(hmac.new(key.encode(), encoded.encode(), hashlib.sha256).hexdigest(), signature):
        raise AccessDenied("Invalid BFF delegation")
    payload = json.loads(base64.b64decode(encoded, altchars=b"-_", validate=True))
    issued = payload.get("issued_at")
    if type(issued) is not int or not -5 <= time.time() - issued <= 60:
        raise AccessDenied("Expired BFF delegation")
    if not isinstance(payload.get("subject"), str) or not payload["subject"]:
        raise AccessDenied("Missing delegated identity")
    if payload.get("request") != canonical_request(method, path, query, body):
        raise AccessDenied("Delegation does not match request")
    payload["grant"] = validate_grant(payload["grant"])
    return payload


def authorize_stack_request(event):
    """Protect single-account REST handlers as well as the BFF entry point."""
    import os
    from .request_json import prepare_json_body
    parsed_body = prepare_json_body(event)
    headers = {key.lower(): value for key, value in (event.get('headers') or {}).items()}
    key = os.environ.get('BACKEND_API_KEY', '')
    if not key: raise BackendConfigurationError('Backend access key is not configured')
    if not isinstance(headers.get('x-api-key'), str) or not hmac.compare_digest(headers['x-api-key'], key):
        raise BackendAuthenticationError('Invalid backend access key')
    method, path = event.get('httpMethod', 'GET'), event.get('path', '')
    multiple, single = event.get('multiValueQueryStringParameters') or {}, event.get('queryStringParameters') or {}
    pairs = [(name, '' if value is None else value) for name, values in multiple.items() for value in values]
    pairs.extend((name, '' if value is None else value) for name, value in single.items() if name not in multiple)
    query = event.get('rawQueryString') if isinstance(event.get('rawQueryString'), str) else urlencode(pairs)
    if headers.get('x-costguard-context'):
        delegated = verify_delegation(key, headers, method, path, query, event.get('body'))
        grant, subject = delegated['grant'], delegated['subject']
    elif os.environ.get('ALLOW_DIRECT_API_KEYS', 'false').lower() == 'true':
        grant = {'role': 'admin', 'organizations': ['*'], 'accounts': [os.environ.get('BACKEND_ACCOUNT_ID', '')]}
        subject = 'direct-key-integration'
    else: raise AccessDenied('Signed application identity required')
    account = os.environ.get('BACKEND_ACCOUNT_ID', '')
    if not account or not allows(grant, 'accounts', account):
        raise AccessDenied('Account is outside your scope')
    authorize_request(grant, method, path, {'query': single, 'body': parsed_body})
    event['_principal'] = {'subject': subject, 'grant': grant}
    return event['_principal']


def advisor_identity(event, session='default'):
    principal = event.get('_principal')
    if not principal: raise AccessDenied('Authenticated advisor identity required')
    if not isinstance(session, str) or not session or len(session) > 128:
        raise ValueError('Session ID must contain 1-128 characters')
    owner = hashlib.sha256(principal['subject'].encode()).hexdigest()
    return principal['subject'], owner + ':' + session
