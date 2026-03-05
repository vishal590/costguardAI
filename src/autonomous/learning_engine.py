"""
Learning Engine Lambda Function

Tracks action outcomes and improves recommendations over time using
historical success rates and pattern identification.

Responsibilities:
- Record all autonomous actions with timestamps and parameters
- Record action outcomes (cost impact, performance impact)
- Calculate success rates by action type
- Generate confidence scores based on historical data
- Adjust recommendation thresholds when success rate <70%
- Calculate cumulative ROI and generate success reports

Requirements: 4.1-4.12
"""

import json
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Key

from autonomous.utils.cloudwatch_metrics import get_metrics_publisher
from autonomous.utils.xray_tracing import trace_subsegment, trace_action_outcome


# Environment variables
ACTION_HISTORY_TABLE = os.environ.get("ACTION_HISTORY_TABLE", "costguard-action-history")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "costguard-autonomous-events")
MIN_ACTIONS_FOR_LEARNING = int(os.environ.get("MIN_ACTIONS_FOR_LEARNING", "30"))
SUCCESS_RATE_THRESHOLD = float(os.environ.get("SUCCESS_RATE_THRESHOLD", "0.7"))
LEARNING_MODE_ENABLED = os.environ.get("LEARNING_MODE_ENABLED", "true").lower() == "true"

# AWS clients
dynamodb = boto3.resource("dynamodb")
events_client = boto3.client("events")
sns_client = boto3.client("sns")

# Tables
action_history_table = dynamodb.Table(ACTION_HISTORY_TABLE)


class Action:
    """Represents an autonomous action with metadata."""
    
    def __init__(
        self,
        action_id: str,
        action_type: str,
        parameters: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ):
        self.action_id = action_id
        self.action_type = action_type
        self.parameters = parameters
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "parameters": self.parameters,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        """Create from dictionary."""
        return cls(
            action_id=data["action_id"],
            action_type=data["action_type"],
            parameters=data["parameters"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class Outcome:
    """Represents the outcome of an autonomous action."""
    
    def __init__(
        self,
        action_id: str,
        success: bool,
        cost_impact: float,
        performance_impact: float,
        timestamp: Optional[datetime] = None,
    ):
        self.action_id = action_id
        self.success = success
        self.cost_impact = cost_impact
        self.performance_impact = performance_impact
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action_id": self.action_id,
            "success": self.success,
            "cost_impact": self.cost_impact,
            "performance_impact": self.performance_impact,
            "timestamp": self.timestamp.isoformat(),
        }


def record_action(action: Action) -> None:
    """
    Record an autonomous action in DynamoDB.
    
    Args:
        action: Action object to record
    """
    try:
        # Set TTL for 90 days
        ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())
        
        item = {
            "action_id": action.action_id,
            "timestamp": action.timestamp.isoformat(),
            "action_type": action.action_type,
            "status": "pending",
            "parameters": action.parameters,
            "ttl": ttl,
        }
        
        action_history_table.put_item(Item=item)
        print(f"Recorded action: {action.action_id} (type: {action.action_type})")
        
    except Exception as e:
        print(f"ERROR: Failed to record action: {e}")
        raise


def record_outcome(action_id: str, outcome: Outcome) -> None:
    """
    Record the outcome of an autonomous action.
    
    Args:
        action_id: Action ID
        outcome: Outcome object with results
    """
    try:
        # Update action record with outcome
        action_history_table.update_item(
            Key={"action_id": action_id, "timestamp": outcome.timestamp.isoformat()},
            UpdateExpression="SET #status = :status, #success = :success, "
                           "#cost_impact = :cost_impact, #perf_impact = :perf_impact",
            ExpressionAttributeNames={
                "#status": "status",
                "#success": "success",
                "#cost_impact": "actual_cost_impact",
                "#perf_impact": "performance_impact",
            },
            ExpressionAttributeValues={
                ":status": "completed",
                ":success": outcome.success,
                ":cost_impact": Decimal(str(outcome.cost_impact)),
                ":perf_impact": Decimal(str(outcome.performance_impact)),
            },
        )
        
        print(f"Recorded outcome for action {action_id}: success={outcome.success}, "
              f"cost_impact={outcome.cost_impact}, perf_impact={outcome.performance_impact}")
        
    except Exception as e:
        print(f"ERROR: Failed to record outcome: {e}")
        raise


def query_historical_actions(action_type: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Query historical actions of a specific type.
    
    Args:
        action_type: Type of action to query
        limit: Maximum number of actions to return
        
    Returns:
        List of action records
    """
    try:
        # Query using action-type-index GSI
        response = action_history_table.query(
            IndexName="action-type-index",
            KeyConditionExpression=Key("action_type").eq(action_type),
            Limit=limit,
            ScanIndexForward=False,  # Most recent first
        )
        
        actions = response.get("Items", [])
        print(f"Retrieved {len(actions)} historical actions of type '{action_type}'")
        
        return actions
        
    except Exception as e:
        print(f"ERROR: Failed to query historical actions: {e}")
        return []


@trace_subsegment('calculate_success_rate')
def calculate_success_rate(action_type: str) -> float:
    """
    Calculate success rate for a specific action type.
    
    Args:
        action_type: Type of action
        
    Returns:
        Success rate between 0.0 and 1.0
    """
    try:
        # Query historical actions
        actions = query_historical_actions(action_type, limit=1000)
        
        if not actions:
            # Insufficient data - return default confidence
            print(f"No historical data for action type '{action_type}', using default 0.5")
            return 0.5
        
        # Filter completed actions with success field
        completed_actions = [
            a for a in actions
            if a.get("status") == "completed" and "success" in a
        ]
        
        if not completed_actions:
            print(f"No completed actions for type '{action_type}', using default 0.5")
            return 0.5
        
        # Calculate success rate
        successful = sum(1 for a in completed_actions if a.get("success", False))
        total = len(completed_actions)
        success_rate = successful / total if total > 0 else 0.5
        
        # Ensure valid range [0.0, 1.0]
        success_rate = max(0.0, min(1.0, success_rate))
        
        print(f"Success rate for '{action_type}': {success_rate:.2%} ({successful}/{total})")
        
        return success_rate
        
    except Exception as e:
        print(f"ERROR: Failed to calculate success rate: {e}")
        return 0.5  # Default confidence on error


def generate_confidence_score(action_type: str, parameters: Dict[str, Any]) -> float:
    """
    Generate confidence score based on historical success rates.
    
    Args:
        action_type: Type of action
        parameters: Action parameters
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    try:
        # Get historical success rate
        success_rate = calculate_success_rate(action_type)
        
        # Base confidence on success rate
        confidence = success_rate
        
        # Adjust based on parameter similarity (simplified)
        # In production, would analyze parameter patterns
        
        # Ensure valid range
        confidence = max(0.0, min(1.0, confidence))
        
        print(f"Generated confidence score for '{action_type}': {confidence:.2f}")
        
        return confidence
        
    except Exception as e:
        print(f"ERROR: Failed to generate confidence score: {e}")
        return 0.5  # Default confidence on error


def identify_patterns(action_type: str) -> List[Dict[str, Any]]:
    """
    Identify patterns in successful optimizations.
    
    Args:
        action_type: Type of action to analyze
        
    Returns:
        List of identified patterns
    """
    try:
        # Query historical actions
        actions = query_historical_actions(action_type, limit=1000)
        
        # Filter successful actions
        successful_actions = [
            a for a in actions
            if a.get("status") == "completed" and a.get("success", False)
        ]
        
        if not successful_actions:
            return []
        
        patterns = []
        
        # Pattern 1: Time of day
        time_distribution = {}
        for action in successful_actions:
            timestamp = action.get("timestamp", "")
            if timestamp:
                hour = datetime.fromisoformat(timestamp).hour
                time_distribution[hour] = time_distribution.get(hour, 0) + 1
        
        if time_distribution:
            best_hour = max(time_distribution, key=time_distribution.get)
            patterns.append({
                "type": "time_of_day",
                "best_hour": best_hour,
                "success_count": time_distribution[best_hour],
            })
        
        # Pattern 2: Instance type (for right-sizing)
        if action_type == "right_sizing":
            instance_transitions = {}
            for action in successful_actions:
                params = action.get("parameters", {})
                transition = f"{params.get('original_type', 'unknown')}->{params.get('new_type', 'unknown')}"
                instance_transitions[transition] = instance_transitions.get(transition, 0) + 1
            
            if instance_transitions:
                best_transition = max(instance_transitions, key=instance_transitions.get)
                patterns.append({
                    "type": "instance_transition",
                    "best_transition": best_transition,
                    "success_count": instance_transitions[best_transition],
                })
        
        print(f"Identified {len(patterns)} patterns for '{action_type}'")
        
        return patterns
        
    except Exception as e:
        print(f"ERROR: Failed to identify patterns: {e}")
        return []


def adjust_thresholds(action_type: str, success_rate: float) -> None:
    """
    Adjust recommendation thresholds based on success rate.
    
    Only adjusts when:
    - Sufficient historical data exists (30+ actions)
    - Learning mode is enabled
    
    Args:
        action_type: Type of action
        success_rate: Current success rate
    """
    try:
        # Check if learning mode is enabled
        if not LEARNING_MODE_ENABLED:
            print(f"Learning mode disabled, skipping threshold adjustment")
            return
        
        # Check if sufficient data exists
        actions = query_historical_actions(action_type, limit=MIN_ACTIONS_FOR_LEARNING + 1)
        if len(actions) < MIN_ACTIONS_FOR_LEARNING:
            print(f"Insufficient data for threshold adjustment: {len(actions)} < {MIN_ACTIONS_FOR_LEARNING}")
            return
        
        # Adjust thresholds based on success rate
        if success_rate < SUCCESS_RATE_THRESHOLD:
            print(f"Low success rate ({success_rate:.2%}) for '{action_type}', adjusting thresholds")
            
            # Store threshold adjustment in action history
            adjustment_id = f"threshold_adj_{action_type}_{int(time.time())}"
            adjustment = {
                "action_id": adjustment_id,
                "timestamp": datetime.utcnow().isoformat(),
                "action_type": "threshold_adjustment",
                "status": "completed",
                "parameters": {
                    "target_action_type": action_type,
                    "old_success_rate": success_rate,
                    "adjustment_reason": "low_success_rate",
                },
                "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp()),
            }
            
            action_history_table.put_item(Item=adjustment)
            
            # Publish event for threshold adjustment
            events_client.put_events(
                Entries=[{
                    "Source": "costguard.autonomous.learningengine",
                    "DetailType": "ThresholdAdjusted",
                    "Detail": json.dumps({
                        "action_type": action_type,
                        "success_rate": success_rate,
                        "adjustment_id": adjustment_id,
                    }),
                    "EventBusName": EVENT_BUS_NAME,
                }]
            )
            
            print(f"Threshold adjustment recorded: {adjustment_id}")
        else:
            print(f"Success rate ({success_rate:.2%}) above threshold, no adjustment needed")
        
    except Exception as e:
        print(f"ERROR: Failed to adjust thresholds: {e}")


def calculate_cumulative_roi() -> float:
    """
    Calculate cumulative ROI from all completed actions.
    
    Returns:
        Total cost savings (negative = savings, positive = cost increase)
    """
    try:
        # Query all completed actions
        response = action_history_table.query(
            IndexName="status-index",
            KeyConditionExpression=Key("status").eq("completed"),
            Limit=10000,
        )
        
        actions = response.get("Items", [])
        
        # Sum cost impacts
        total_roi = Decimal("0")
        for action in actions:
            cost_impact = action.get("actual_cost_impact", 0)
            if cost_impact:
                total_roi += Decimal(str(cost_impact))
        
        roi_float = float(total_roi)
        print(f"Cumulative ROI: ${roi_float:.2f}")
        
        return roi_float
        
    except Exception as e:
        print(f"ERROR: Failed to calculate cumulative ROI: {e}")
        return 0.0


def generate_success_report() -> Dict[str, Any]:
    """
    Generate success report when cumulative savings exceed $100.
    
    Returns:
        Success report dictionary
    """
    try:
        cumulative_roi = calculate_cumulative_roi()
        
        if cumulative_roi < -100:  # Negative = savings
            # Query action counts by type
            action_types = ["schedule", "spot_migration", "right_sizing"]
            type_breakdown = {}
            
            for action_type in action_types:
                actions = query_historical_actions(action_type, limit=10000)
                completed = [a for a in actions if a.get("status") == "completed"]
                successful = [a for a in completed if a.get("success", False)]
                
                type_breakdown[action_type] = {
                    "total": len(actions),
                    "completed": len(completed),
                    "successful": len(successful),
                    "success_rate": len(successful) / len(completed) if completed else 0.0,
                }
            
            report = {
                "cumulative_savings": abs(cumulative_roi),
                "report_timestamp": datetime.utcnow().isoformat(),
                "action_breakdown": type_breakdown,
                "milestone": "100_dollars_saved",
            }
            
            print(f"Generated success report: ${abs(cumulative_roi):.2f} saved")
            
            return report
        else:
            print(f"Cumulative savings (${abs(cumulative_roi):.2f}) below $100 threshold")
            return {}
        
    except Exception as e:
        print(f"ERROR: Failed to generate success report: {e}")
        return {}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for Learning Engine.
    
    Handles:
    - ActionCompleted events from EventBridge
    - Scheduled batch analysis events
    
    Args:
        event: EventBridge event or scheduled event
        context: Lambda context
        
    Returns:
        Response with learning results
    """
    try:
        print(f"Learning Engine invoked with event: {json.dumps(event, default=str)}")
        
        # Get metrics publisher
        metrics = get_metrics_publisher()
        
        # Determine event type
        detail_type = event.get("detail-type", "")
        
        if detail_type == "ActionCompleted":
            # Handle action completion
            detail = event.get("detail", {})
            action_id = detail.get("action_id")
            action_type = detail.get("action_type")
            
            if not action_id or not action_type:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Missing action_id or action_type"}),
                }
            
            # Record outcome
            outcome = Outcome(
                action_id=action_id,
                success=detail.get("success", False),
                cost_impact=detail.get("outcome", {}).get("actual_cost_impact", 0.0),
                performance_impact=detail.get("outcome", {}).get("performance_impact", 0.0),
            )
            
            record_outcome(action_id, outcome)
            
            # Calculate success rate
            success_rate = calculate_success_rate(action_type)
            
            # Publish CloudWatch metrics
            metrics.publish_action_success_rate(action_type, success_rate)
            print(f"Published success rate metric for {action_type}: {success_rate:.2%}")
            
            # Check if action type should be flagged
            if success_rate < SUCCESS_RATE_THRESHOLD:
                print(f"WARNING: Low success rate for '{action_type}': {success_rate:.2%}")
                
                # Publish ConfidenceLow event
                events_client.put_events(
                    Entries=[{
                        "Source": "costguard.autonomous.learningengine",
                        "DetailType": "ConfidenceLow",
                        "Detail": json.dumps({
                            "action_type": action_type,
                            "success_rate": success_rate,
                            "threshold": SUCCESS_RATE_THRESHOLD,
                        }),
                        "EventBusName": EVENT_BUS_NAME,
                    }]
                )
            
            # Adjust thresholds if needed
            adjust_thresholds(action_type, success_rate)
            
            # Check for success milestone
            report = generate_success_report()
            if report:
                # Send success report via SNS (if topic configured)
                print(f"Success milestone reached: {report}")
                cumulative_savings = report.get("cumulative_savings", 0)
                metrics.publish_cumulative_savings(cumulative_savings)
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "action_id": action_id,
                    "success_rate": success_rate,
                    "patterns_identified": len(identify_patterns(action_type)),
                }),
            }
        
        elif detail_type == "Scheduled Event" or event.get("source") == "aws.events":
            # Handle scheduled batch analysis
            print("Running scheduled batch analysis")
            
            action_types = ["schedule", "spot_migration", "right_sizing"]
            results = {}
            total_success_rate = 0.0
            
            for action_type in action_types:
                success_rate = calculate_success_rate(action_type)
                patterns = identify_patterns(action_type)
                adjust_thresholds(action_type, success_rate)
                
                results[action_type] = {
                    "success_rate": success_rate,
                    "patterns_count": len(patterns),
                }
                
                # Publish metrics for each action type
                metrics.publish_action_success_rate(action_type, success_rate)
                total_success_rate += success_rate
            
            # Calculate cumulative ROI
            cumulative_roi = calculate_cumulative_roi()
            
            # Publish cumulative savings metric
            if cumulative_roi < 0:  # Negative = savings
                metrics.publish_cumulative_savings(abs(cumulative_roi))
            
            # Publish average confidence score
            avg_confidence = total_success_rate / len(action_types) if action_types else 0.5
            metrics.publish_confidence_score(avg_confidence)
            
            print(f"Published batch metrics: avg_confidence={avg_confidence:.2f}, cumulative_roi=${cumulative_roi:.2f}")
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "analysis_type": "batch",
                    "results": results,
                    "cumulative_roi": cumulative_roi,
                }),
            }
        
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unknown event type: {detail_type}"}),
            }
        
    except Exception as e:
        print(f"ERROR: Learning Engine handler failed: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
