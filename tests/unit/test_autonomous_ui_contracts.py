"""API regressions for the frontend's action monitor and confidence view."""
import json
from unittest.mock import MagicMock, patch

from src import autonomous_handler as api


def test_confidence_uses_canonical_success_and_preserves_legacy():
    table = MagicMock()
    table.scan.return_value = {"Items": [
        {"action_type": "schedule", "success": True, "confidence_score": .9},
        {"action_type": "schedule", "success": False, "outcome": "success", "confidence_score": .8},
        {"action_type": "schedule", "outcome": "success", "confidence_score": .7},
    ]}
    with patch.object(api, "action_history_table", table):
        response = api.handle_confidence_scores({})
    score = json.loads(response["body"])["confidence_scores"]["schedule"]
    assert score["total_actions"] == 3 and score["successful_actions"] == 2
    assert score["success_rate"] == 2/3


def test_action_monitor_queries_the_requested_partition():
    table = MagicMock()
    record = {"action_id": "action-1", "status": "completed", "timestamp": "2026-10-14T00:00:00Z",
              "resource_result": {"training": {"restored_step": 7, "final_step": 37}}, "execution_error": "prior failure"}
    table.query.return_value = {"Items": [record]}
    with patch.object(api, "action_history_table", table):
        response = api.handle_action_history({"queryStringParameters": {"action_id": "action-1", "limit": "100"}})
    table.scan.assert_not_called()
    query = table.query.call_args.kwargs
    assert query["KeyConditionExpression"].get_expression()["values"][1] == "action-1"
    assert query["ConsistentRead"] is True and query["ScanIndexForward"] is False
    assert json.loads(response["body"])["actions"] == [record]
