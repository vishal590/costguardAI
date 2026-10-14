"""Offline regression checks for API dispatch and autonomous event decisions."""
import json
import time
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from src import ai_ml_handler as gpu
from src import autonomous_handler as api
from autonomous import safety_guard as guard


@pytest.mark.parametrize("suffix,target", [
    ("gpu-costs", "handle_gpu_costs"),
    ("gpu-utilization", "handle_gpu_utilization"),
    ("multi-account/gpu-costs", "handle_multi_account_gpu_costs"),
    ("multi-account/gpu-utilization", "handle_multi_account_gpu_utilization"),
])
def test_gpu_dispatch(suffix, target):
    names = ["handle_gpu_costs", "handle_gpu_utilization",
             "handle_multi_account_gpu_costs", "handle_multi_account_gpu_utilization"]
    mocks = {name: MagicMock(return_value={"statusCode": 200, "body": name}) for name in names}
    event = {"httpMethod": "GET", "path": "/api/ai-ml/" + suffix}
    with patch.multiple(gpu, **mocks):
        assert gpu.handler(event, None)["body"] == target
    for name, mock in mocks.items():
        assert mock.call_count == (1 if name == target else 0)


@pytest.fixture
def approval(monkeypatch):
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="approval-test",
            KeySchema=[{"AttributeName": "action_id", "KeyType": "HASH"},
                       {"AttributeName": "timestamp", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": name, "AttributeType": "S"}
                                  for name in ("action_id", "timestamp")],
            BillingMode="PAY_PER_REQUEST")
        monkeypatch.setattr(guard, "action_history_table", table)
        monkeypatch.setattr(guard, "APPROVAL_SECRET_KEY", "test-only-secret")
        monkeypatch.setattr(guard, "APPROVAL_SNS_TOPIC", "")
        monkeypatch.setattr(guard, "log_action", MagicMock())
        bus = MagicMock()
        bus.put_events.return_value = {"FailedEntryCount": 0}
        monkeypatch.setattr(guard, "events_client", bus)
        action = guard.ActionRequest("request-1", "terminate", "action-1", {}, 0.9, -10)
        guard.request_approval(action)
        key = {"action_id": action.action_id, "timestamp": action.timestamp.isoformat()}
        original = table.get_item(Key=key)["Item"]
        guard.create_rollback_capability(action)
        record = table.get_item(Key=key)["Item"]
        assert record["approval_request_id"] == original["approval_request_id"]
        assert record["approval_signature"] == original["approval_signature"]
        assert record["status"] == "pending_approval"
        assert record["ttl"] == original["ttl"]
        assert record["rollback_created"] is True
        # A newer audit entry must not hide the actual approval request.
        table.put_item(Item={"action_id": action.action_id, "timestamp": "9999-audit", "status": "logged"})
        try:
            yield table, key, record
        finally:
            table.delete()


def decision(record, approved=True):
    return {"source": "costguard.autonomous.api",
            "detail-type": "ActionApproved" if approved else "ActionRejected",
            "detail": {"request_id": record["approval_request_id"], "action_id": record["action_id"],
                       "signature": record["approval_signature"], "approved": approved}}


@pytest.mark.parametrize("approved", [True, False])
def test_api_event_applies_signed_decision_once(approval, approved):
    table, key, record = approval
    client = MagicMock()
    client.put_events.return_value = {"FailedEntryCount": 0}
    with patch.object(api, "events_client", client):
        response = api.handle_approve_action({"body": json.dumps(decision(record, approved)["detail"])})
    assert response["statusCode"] == 202
    assert json.loads(response["body"])["status"] == "approval_submitted"
    entry = client.put_events.call_args.kwargs["Entries"][0]
    event = {"source": entry["Source"], "detail-type": entry["DetailType"], "detail": json.loads(entry["Detail"])}
    assert guard.handler(event, None)["statusCode"] == 200
    assert table.get_item(Key=key)["Item"]["status"] == ("approved" if approved else "rejected")
    assert json.loads(guard.handler(event, None)["body"])["duplicate"] is True
    assert guard.handler(decision(record, not approved), None)["statusCode"] == 409
    guard.log_action.assert_called_once()


@pytest.mark.parametrize("change,status", [
    ({"signature": "tampered"}, 403),
    ({"signature": "\u2665"}, 403),
    ({"request_id": "unknown"}, 404),
    ({"approved": "true"}, 400),
    ({"approved": False}, 400),
])
def test_invalid_decision_leaves_pending(approval, change, status):
    table, key, record = approval
    event = decision(record)
    event["detail"].update(change)
    assert guard.handler(event, None)["statusCode"] == status
    assert table.get_item(Key=key)["Item"]["status"] == "pending_approval"
    guard.log_action.assert_not_called()


def test_expired_request_is_rejected(approval):
    table, key, record = approval
    table.update_item(Key=key, UpdateExpression="SET approval_expires_at = :expired",
                      ExpressionAttributeValues={":expired": int(time.time()) - 1})
    assert guard.handler(decision(record), None)["statusCode"] == 410
    assert table.get_item(Key=key)["Item"]["status"] == "pending_approval"


def test_conditional_update_rejects_race(approval):
    table, key, record = approval
    error = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
    with patch.object(table, "update_item", side_effect=error):
        assert guard.handler(decision(record), None)["statusCode"] == 409
    guard.log_action.assert_not_called()


def test_request_lookup_paginates(approval):
    _, _, record = approval
    table = MagicMock()
    cursor = {"action_id": "action-1", "timestamp": "audit"}
    table.query.side_effect = [{"Items": [], "LastEvaluatedKey": cursor}, {"Items": [record]}]
    with patch.object(guard, "action_history_table", table):
        assert guard.handler(decision(record), None)["statusCode"] == 200
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == cursor


@pytest.mark.parametrize("field,value", [("signature", ""), ("action_id", 10), ("approved", "false"), ("approved", None)])
def test_api_rejects_invalid_approval_fields(field, value):
    body = {"request_id": "request-1", "action_id": "action-1", "signature": "signature", "approved": True}
    body[field] = value
    with patch.object(api, "events_client") as client:
        assert api.handle_approve_action({"body": json.dumps(body)})["statusCode"] == 400
        client.put_events.assert_not_called()


@pytest.mark.parametrize("endpoint", [api.handle_approve_action, api.handle_rollback])
def test_api_reports_eventbridge_entry_failure(endpoint):
    body = {"request_id": "request-1", "action_id": "action-1", "signature": "signature", "approved": True}
    with patch.object(api, "events_client") as client:
        client.put_events.return_value = {"FailedEntryCount": 1, "Entries": [{"ErrorCode": "InternalFailure"}]}
        assert endpoint({"body": json.dumps(body)})["statusCode"] == 500


def test_api_rollback_event_reaches_guard():
    with patch.object(api, "events_client") as client:
        client.put_events.return_value = {"FailedEntryCount": 0}
        assert api.handle_rollback({"body": json.dumps({"action_id": "action-1"})})["statusCode"] == 202
        entry = client.put_events.call_args.kwargs["Entries"][0]
    event = {"source": entry["Source"], "detail-type": entry["DetailType"], "detail": json.loads(entry["Detail"])}
    with patch.object(guard, "execute_rollback", return_value=True) as rollback, patch.object(guard, "log_action"):
        assert guard.handler(event, None)["statusCode"] == 202
        rollback.assert_called_once_with("action-1")
