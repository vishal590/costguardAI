"""
Unit Tests for Learning Engine

Comprehensive unit tests for the Learning Engine Lambda function.

Tests cover:
- Action recording and retrieval
- Outcome recording
- Success rate calculation with various datasets
- Confidence score generation
- Pattern identification
- Threshold adjustment logic
- Cumulative ROI calculation
- Learning mode toggle behavior
- Lambda handler for different event types
"""

import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

# Import functions from learning_engine
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))

from autonomous.learning_engine import (
    Action,
    Outcome,
    record_action,
    record_outcome,
    query_historical_actions,
    calculate_success_rate,
    generate_confidence_score,
    identify_patterns,
    adjust_thresholds,
    calculate_cumulative_roi,
    generate_success_report,
    handler,
)


# Fixtures

@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table."""
    with patch('autonomous.learning_engine.action_history_table') as mock_table:
        yield mock_table


@pytest.fixture
def mock_events_client():
    """Mock EventBridge client."""
    with patch('autonomous.learning_engine.events_client') as mock_client:
        yield mock_client


@pytest.fixture
def mock_sns_client():
    """Mock SNS client."""
    with patch('autonomous.learning_engine.sns_client') as mock_client:
        yield mock_client


@pytest.fixture
def sample_action():
    """Sample action for testing."""
    return Action(
        action_id="act_test_123",
        action_type="schedule",
        parameters={
            "instance_type": "g4dn.xlarge",
            "region": "us-east-1",
        },
    )


@pytest.fixture
def sample_outcome():
    """Sample outcome for testing."""
    return Outcome(
        action_id="act_test_123",
        success=True,
        cost_impact=-12.50,
        performance_impact=0.02,
    )


# Tests for Action class

def test_action_to_dict(sample_action):
    """Test Action.to_dict() serialization."""
    action_dict = sample_action.to_dict()
    
    assert action_dict["action_id"] == "act_test_123"
    assert action_dict["action_type"] == "schedule"
    assert action_dict["parameters"]["instance_type"] == "g4dn.xlarge"
    assert "timestamp" in action_dict


def test_action_from_dict():
    """Test Action.from_dict() deserialization."""
    data = {
        "action_id": "act_test_456",
        "action_type": "spot_migration",
        "parameters": {"instance_type": "g4dn.2xlarge"},
        "timestamp": "2024-01-14T10:30:00",
    }
    
    action = Action.from_dict(data)
    
    assert action.action_id == "act_test_456"
    assert action.action_type == "spot_migration"
    assert action.parameters["instance_type"] == "g4dn.2xlarge"


def test_action_round_trip(sample_action):
    """Test Action serialization round-trip."""
    action_dict = sample_action.to_dict()
    restored_action = Action.from_dict(action_dict)
    
    assert restored_action.action_id == sample_action.action_id
    assert restored_action.action_type == sample_action.action_type
    assert restored_action.parameters == sample_action.parameters


# Tests for Outcome class

def test_outcome_to_dict(sample_outcome):
    """Test Outcome.to_dict() serialization."""
    outcome_dict = sample_outcome.to_dict()
    
    assert outcome_dict["action_id"] == "act_test_123"
    assert outcome_dict["success"] is True
    assert outcome_dict["cost_impact"] == -12.50
    assert outcome_dict["performance_impact"] == 0.02
    assert "timestamp" in outcome_dict


# Tests for record_action

def test_record_action_success(mock_dynamodb_table, sample_action):
    """Test successful action recording."""
    mock_dynamodb_table.put_item = MagicMock()
    
    record_action(sample_action)
    
    # Verify put_item was called
    mock_dynamodb_table.put_item.assert_called_once()
    
    # Verify item structure
    call_args = mock_dynamodb_table.put_item.call_args
    item = call_args[1]["Item"]
    
    assert item["action_id"] == "act_test_123"
    assert item["action_type"] == "schedule"
    assert item["status"] == "pending"
    assert "ttl" in item


def test_record_action_with_ttl(mock_dynamodb_table, sample_action):
    """Test action recording includes 90-day TTL."""
    mock_dynamodb_table.put_item = MagicMock()
    
    before_time = datetime.utcnow() + timedelta(days=89)
    record_action(sample_action)
    after_time = datetime.utcnow() + timedelta(days=91)
    
    call_args = mock_dynamodb_table.put_item.call_args
    item = call_args[1]["Item"]
    ttl = item["ttl"]
    
    # Verify TTL is approximately 90 days from now
    assert before_time.timestamp() < ttl < after_time.timestamp()


def test_record_action_error_handling(mock_dynamodb_table, sample_action):
    """Test error handling in record_action."""
    mock_dynamodb_table.put_item.side_effect = Exception("DynamoDB error")
    
    with pytest.raises(Exception):
        record_action(sample_action)


# Tests for record_outcome

def test_record_outcome_success(mock_dynamodb_table, sample_outcome):
    """Test successful outcome recording."""
    mock_dynamodb_table.update_item = MagicMock()
    
    record_outcome("act_test_123", sample_outcome)
    
    # Verify update_item was called
    mock_dynamodb_table.update_item.assert_called_once()
    
    # Verify update expression
    call_args = mock_dynamodb_table.update_item.call_args
    assert "UpdateExpression" in call_args[1]
    assert "status" in call_args[1]["UpdateExpression"]


def test_record_outcome_with_decimal_conversion(mock_dynamodb_table, sample_outcome):
    """Test outcome recording converts floats to Decimal."""
    mock_dynamodb_table.update_item = MagicMock()
    
    record_outcome("act_test_123", sample_outcome)
    
    call_args = mock_dynamodb_table.update_item.call_args
    values = call_args[1]["ExpressionAttributeValues"]
    
    # Verify cost_impact is Decimal
    assert isinstance(values[":cost_impact"], Decimal)
    assert isinstance(values[":perf_impact"], Decimal)


# Tests for query_historical_actions

def test_query_historical_actions_success(mock_dynamodb_table):
    """Test successful historical action query."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "action_type": "schedule", "status": "completed"},
            {"action_id": "act_2", "action_type": "schedule", "status": "completed"},
        ]
    }
    
    actions = query_historical_actions("schedule", limit=100)
    
    assert len(actions) == 2
    assert actions[0]["action_id"] == "act_1"
    
    # Verify query used GSI
    call_args = mock_dynamodb_table.query.call_args
    assert call_args[1]["IndexName"] == "action-type-index"


def test_query_historical_actions_empty_result(mock_dynamodb_table):
    """Test query with no results."""
    mock_dynamodb_table.query.return_value = {"Items": []}
    
    actions = query_historical_actions("nonexistent_type")
    
    assert len(actions) == 0


def test_query_historical_actions_error_handling(mock_dynamodb_table):
    """Test error handling in query."""
    mock_dynamodb_table.query.side_effect = Exception("Query error")
    
    actions = query_historical_actions("schedule")
    
    # Should return empty list on error
    assert actions == []


# Tests for calculate_success_rate

def test_calculate_success_rate_with_data(mock_dynamodb_table):
    """Test success rate calculation with historical data."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "status": "completed", "success": True},
            {"action_id": "act_2", "status": "completed", "success": True},
            {"action_id": "act_3", "status": "completed", "success": False},
            {"action_id": "act_4", "status": "completed", "success": True},
        ]
    }
    
    success_rate = calculate_success_rate("schedule")
    
    # 3 successful out of 4 = 0.75
    assert success_rate == 0.75


def test_calculate_success_rate_no_data(mock_dynamodb_table):
    """Test success rate with no historical data."""
    mock_dynamodb_table.query.return_value = {"Items": []}
    
    success_rate = calculate_success_rate("schedule")
    
    # Should return default 0.5
    assert success_rate == 0.5


def test_calculate_success_rate_all_successful(mock_dynamodb_table):
    """Test success rate with 100% success."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "status": "completed", "success": True},
            {"action_id": "act_2", "status": "completed", "success": True},
        ]
    }
    
    success_rate = calculate_success_rate("schedule")
    
    assert success_rate == 1.0


def test_calculate_success_rate_all_failed(mock_dynamodb_table):
    """Test success rate with 0% success."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "status": "completed", "success": False},
            {"action_id": "act_2", "status": "completed", "success": False},
        ]
    }
    
    success_rate = calculate_success_rate("schedule")
    
    assert success_rate == 0.0


def test_calculate_success_rate_filters_incomplete(mock_dynamodb_table):
    """Test success rate filters out incomplete actions."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "status": "completed", "success": True},
            {"action_id": "act_2", "status": "pending"},  # Should be filtered
            {"action_id": "act_3", "status": "completed", "success": False},
        ]
    }
    
    success_rate = calculate_success_rate("schedule")
    
    # Only 2 completed actions: 1 success, 1 failure = 0.5
    assert success_rate == 0.5


# Tests for generate_confidence_score

def test_generate_confidence_score(mock_dynamodb_table):
    """Test confidence score generation."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "status": "completed", "success": True},
            {"action_id": "act_2", "status": "completed", "success": True},
            {"action_id": "act_3", "status": "completed", "success": False},
        ]
    }
    
    confidence = generate_confidence_score("schedule", {"instance_type": "g4dn.xlarge"})
    
    # Success rate is 2/3 = 0.667
    assert 0.6 < confidence < 0.7


def test_generate_confidence_score_valid_range(mock_dynamodb_table):
    """Test confidence score is always in valid range."""
    mock_dynamodb_table.query.return_value = {"Items": []}
    
    confidence = generate_confidence_score("schedule", {})
    
    assert 0.0 <= confidence <= 1.0


# Tests for identify_patterns

def test_identify_patterns_time_of_day(mock_dynamodb_table):
    """Test pattern identification for time of day."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "status": "completed", "success": True, "timestamp": "2024-01-14T02:00:00"},
            {"action_id": "act_2", "status": "completed", "success": True, "timestamp": "2024-01-14T02:30:00"},
            {"action_id": "act_3", "status": "completed", "success": True, "timestamp": "2024-01-14T14:00:00"},
        ]
    }
    
    patterns = identify_patterns("schedule")
    
    # Should identify time_of_day pattern
    assert len(patterns) > 0
    time_pattern = next((p for p in patterns if p["type"] == "time_of_day"), None)
    assert time_pattern is not None
    assert "best_hour" in time_pattern


def test_identify_patterns_instance_transition(mock_dynamodb_table):
    """Test pattern identification for instance transitions."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {
                "action_id": "act_1",
                "status": "completed",
                "success": True,
                "timestamp": "2024-01-14T10:00:00",
                "parameters": {"original_type": "g4dn.2xlarge", "new_type": "g4dn.xlarge"},
            },
            {
                "action_id": "act_2",
                "status": "completed",
                "success": True,
                "timestamp": "2024-01-14T11:00:00",
                "parameters": {"original_type": "g4dn.2xlarge", "new_type": "g4dn.xlarge"},
            },
        ]
    }
    
    patterns = identify_patterns("right_sizing")
    
    # Should identify instance_transition pattern
    assert len(patterns) > 0
    transition_pattern = next((p for p in patterns if p["type"] == "instance_transition"), None)
    assert transition_pattern is not None
    assert "best_transition" in transition_pattern


def test_identify_patterns_no_data(mock_dynamodb_table):
    """Test pattern identification with no data."""
    mock_dynamodb_table.query.return_value = {"Items": []}
    
    patterns = identify_patterns("schedule")
    
    assert patterns == []


# Tests for adjust_thresholds

@patch.dict(os.environ, {"LEARNING_MODE_ENABLED": "true", "MIN_ACTIONS_FOR_LEARNING": "30"})
def test_adjust_thresholds_with_low_success_rate(mock_dynamodb_table, mock_events_client):
    """Test threshold adjustment with low success rate."""
    # Mock sufficient historical data
    mock_dynamodb_table.query.return_value = {
        "Items": [{"action_id": f"act_{i}"} for i in range(35)]
    }
    mock_dynamodb_table.put_item = MagicMock()
    mock_events_client.put_events = MagicMock()
    
    adjust_thresholds("schedule", 0.65)  # Below 0.7 threshold
    
    # Verify adjustment was recorded
    mock_dynamodb_table.put_item.assert_called_once()
    
    # Verify event was published
    mock_events_client.put_events.assert_called_once()


@patch.dict(os.environ, {"LEARNING_MODE_ENABLED": "false"})
def test_adjust_thresholds_learning_mode_disabled(mock_dynamodb_table):
    """Test threshold adjustment skipped when learning mode disabled."""
    mock_dynamodb_table.put_item = MagicMock()
    
    adjust_thresholds("schedule", 0.65)
    
    # Should not record adjustment
    mock_dynamodb_table.put_item.assert_not_called()


@patch.dict(os.environ, {"LEARNING_MODE_ENABLED": "true", "MIN_ACTIONS_FOR_LEARNING": "30"})
def test_adjust_thresholds_insufficient_data(mock_dynamodb_table):
    """Test threshold adjustment skipped with insufficient data."""
    # Mock insufficient historical data
    mock_dynamodb_table.query.return_value = {
        "Items": [{"action_id": f"act_{i}"} for i in range(20)]  # Less than 30
    }
    mock_dynamodb_table.put_item = MagicMock()
    
    adjust_thresholds("schedule", 0.65)
    
    # Should not record adjustment
    mock_dynamodb_table.put_item.assert_not_called()


@patch.dict(os.environ, {"LEARNING_MODE_ENABLED": "true"})
def test_adjust_thresholds_high_success_rate(mock_dynamodb_table):
    """Test threshold adjustment skipped with high success rate."""
    mock_dynamodb_table.query.return_value = {
        "Items": [{"action_id": f"act_{i}"} for i in range(35)]
    }
    mock_dynamodb_table.put_item = MagicMock()
    
    adjust_thresholds("schedule", 0.85)  # Above 0.7 threshold
    
    # Should not record adjustment
    mock_dynamodb_table.put_item.assert_not_called()


# Tests for calculate_cumulative_roi

def test_calculate_cumulative_roi_with_savings(mock_dynamodb_table):
    """Test cumulative ROI calculation with cost savings."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "actual_cost_impact": Decimal("-12.50")},
            {"action_id": "act_2", "actual_cost_impact": Decimal("-8.75")},
            {"action_id": "act_3", "actual_cost_impact": Decimal("-15.00")},
        ]
    }
    
    roi = calculate_cumulative_roi()
    
    # Total savings: -36.25
    assert abs(roi - (-36.25)) < 0.01


def test_calculate_cumulative_roi_mixed_impacts(mock_dynamodb_table):
    """Test cumulative ROI with mixed cost impacts."""
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "actual_cost_impact": Decimal("-20.00")},
            {"action_id": "act_2", "actual_cost_impact": Decimal("5.00")},
            {"action_id": "act_3", "actual_cost_impact": Decimal("-10.00")},
        ]
    }
    
    roi = calculate_cumulative_roi()
    
    # Total: -25.00
    assert abs(roi - (-25.00)) < 0.01


def test_calculate_cumulative_roi_no_data(mock_dynamodb_table):
    """Test cumulative ROI with no data."""
    mock_dynamodb_table.query.return_value = {"Items": []}
    
    roi = calculate_cumulative_roi()
    
    assert roi == 0.0


# Tests for generate_success_report

def test_generate_success_report_milestone_reached(mock_dynamodb_table):
    """Test success report generation when milestone reached."""
    # Mock cumulative ROI > $100 savings
    mock_dynamodb_table.query.side_effect = [
        # First call: status-index query for cumulative ROI
        {"Items": [
            {"action_id": "act_1", "actual_cost_impact": Decimal("-120.00")},
        ]},
        # Subsequent calls: action-type-index queries
        {"Items": [{"action_id": "act_1", "status": "completed", "success": True}]},
        {"Items": [{"action_id": "act_2", "status": "completed", "success": True}]},
        {"Items": [{"action_id": "act_3", "status": "completed", "success": False}]},
    ]
    
    report = generate_success_report()
    
    assert "cumulative_savings" in report
    assert report["cumulative_savings"] == 120.00
    assert "action_breakdown" in report


def test_generate_success_report_below_threshold(mock_dynamodb_table):
    """Test success report not generated below threshold."""
    # Mock cumulative ROI < $100 savings
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {"action_id": "act_1", "actual_cost_impact": Decimal("-50.00")},
        ]
    }
    
    report = generate_success_report()
    
    assert report == {}


# Tests for handler

def test_handler_action_completed_event(mock_dynamodb_table, mock_events_client):
    """Test handler with ActionCompleted event."""
    mock_dynamodb_table.update_item = MagicMock()
    mock_dynamodb_table.query.return_value = {
        "Items": [{"action_id": "act_1", "status": "completed", "success": True}]
    }
    mock_events_client.put_events = MagicMock()
    
    event = {
        "detail-type": "ActionCompleted",
        "detail": {
            "action_id": "act_test_123",
            "action_type": "schedule",
            "success": True,
            "outcome": {
                "actual_cost_impact": -12.50,
                "performance_impact": 0.02,
            },
        },
    }
    
    response = handler(event, None)
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "action_id" in body
    assert "success_rate" in body


def test_handler_scheduled_event(mock_dynamodb_table):
    """Test handler with scheduled batch analysis event."""
    mock_dynamodb_table.query.side_effect = [
        {"Items": [{"action_id": "act_1", "status": "completed", "success": True}]},
        {"Items": []},
        {"Items": [{"action_id": "act_2", "status": "completed", "success": False}]},
        {"Items": []},
        {"Items": [{"action_id": "act_3", "status": "completed", "success": True}]},
        {"Items": []},
        {"Items": []},  # For cumulative ROI
    ]
    
    event = {
        "detail-type": "Scheduled Event",
        "source": "aws.events",
    }
    
    response = handler(event, None)
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["analysis_type"] == "batch"
    assert "results" in body


def test_handler_missing_action_id():
    """Test handler with missing action_id."""
    event = {
        "detail-type": "ActionCompleted",
        "detail": {
            "action_type": "schedule",
        },
    }
    
    response = handler(event, None)
    
    assert response["statusCode"] == 400


def test_handler_unknown_event_type():
    """Test handler with unknown event type."""
    event = {
        "detail-type": "UnknownEvent",
    }
    
    response = handler(event, None)
    
    assert response["statusCode"] == 400


def test_handler_error_handling(mock_dynamodb_table):
    """Test handler error handling."""
    mock_dynamodb_table.update_item.side_effect = Exception("DynamoDB error")
    
    event = {
        "detail-type": "ActionCompleted",
        "detail": {
            "action_id": "act_test_123",
            "action_type": "schedule",
            "success": True,
            "outcome": {
                "actual_cost_impact": -12.50,
                "performance_impact": 0.02,
            },
        },
    }
    
    response = handler(event, None)
    
    assert response["statusCode"] == 500
