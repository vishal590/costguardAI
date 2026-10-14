"""Offline API Gateway-to-backend transport regressions."""
import base64
import json
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

import pytest
from src import bff_handler as bff


@pytest.mark.parametrize("path,backend", [
    ("/api/autonomous/actions/history", "AUTONOMOUS"),
    ("/api/ai-ml/multi-account/gpu-costs", "AIML"),
    ("/api/organizations", "MULTI_ACCOUNT"),
    ("/api/costs/account/123", "MULTI_ACCOUNT"),
    ("/api/allocation/rules", "MULTI_ACCOUNT"),
    ("/api/budgets/hierarchy", "MULTI_ACCOUNT"),
    ("/api/cost-data", "MAIN"),
    ("/api/cost-forecast", "MAIN"),
    ("/api/costs-extra", "MAIN"),
    ("/api/autonomous-extra", "MAIN"),
    ("/other/api/autonomous/actions", "MAIN"),
])
def test_route_boundaries(path, backend):
    assert bff._get_backend_for_path(path) == (f"BFF_{backend}_BASE_URL", f"BFF_{backend}_API_KEY")


def event(**overrides):
    return {"headers": {"Authorization": "Bearer local-token"}, "path": "/api/advisor/query",
            "httpMethod": "POST", **overrides}


def forward(monkeypatch, request_event):
    monkeypatch.setenv("BFF_MAIN_BASE_URL", "https://backend.example/prod")
    monkeypatch.setenv("BFF_MAIN_API_KEY", "server-key")
    response = MagicMock()
    response.read.return_value = b'{"ok":true}'
    response.getcode.return_value = 202
    response.headers = {"Content-Type": "application/json"}
    with patch.object(bff, "_verify_cognito_token", return_value={}), patch.object(bff.urllib.request, "urlopen") as opened:
        opened.return_value.__enter__.return_value = response
        result = bff.handler(request_event, None)
        return result, opened.call_args.args[0] if opened.called else None


def test_rest_query_merges_repeated_values_and_encodes_names(monkeypatch):
    result, request = forward(monkeypatch, event(queryStringParameters={"team": "last", "odd&name": "x+y /", "empty": None},
        multiValueQueryStringParameters={"team": ["first", "last"]}))
    assert result["statusCode"] == 202
    assert parse_qs(request.full_url.split("?", 1)[1], keep_blank_values=True) == {
        "team": ["first", "last"], "odd&name": ["x+y /"], "empty": [""]}
    assert request.get_header("X-api-key") == "server-key"
    assert request.get_header("Authorization") is None


def test_http_api_raw_query_wins_over_collapsed_parameters(monkeypatch):
    raw = "team=a&team=b&literal=a%2Bb"
    result, request = forward(monkeypatch, event(rawQueryString=raw, queryStringParameters={"team": "a,b"}))
    assert result["statusCode"] == 202
    assert request.full_url.endswith("?" + raw)


@pytest.mark.parametrize("stage", ["prod", "test"])
def test_stage_prefix_and_encoded_json_body(monkeypatch, stage):
    body = json.dumps({"query": "costs + savings"}).encode()
    result, request = forward(monkeypatch, event(path=f"/{stage}/api/advisor/query", requestContext={"stage": stage},
        body=base64.b64encode(body).decode(), isBase64Encoded=True))
    assert result["statusCode"] == 202
    assert request.full_url == "https://backend.example/prod/api/advisor/query"
    assert request.data == body


def test_invalid_encoded_body_never_reaches_backend(monkeypatch):
    result, request = forward(monkeypatch, event(body="!not-base64!", isBase64Encoded=True))
    assert result["statusCode"] == 400 and request is None


def test_plain_body_preserved(monkeypatch):
    result, request = forward(monkeypatch, event(body='{"query":"costs"}'))
    assert result["statusCode"] == 202
    assert request.data == b'{"query":"costs"}'


def test_missing_token_never_reaches_backend():
    with patch.object(bff.urllib.request, "urlopen") as opened:
        assert bff.handler({"path": "/api/cost-data"}, None)["statusCode"] == 401
        opened.assert_not_called()
