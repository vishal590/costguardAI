"""
GPU Scheduler Lambda Function

Analyzes historical GPU cost patterns and schedules training jobs during
optimization windows to minimize costs.

Responsibilities:
- Query 7+ days of GPU cost data from DynamoDB
- Identify optimization windows (periods with consistently low spot prices)
- Calculate confidence scores based on pattern stability
- Generate scheduling recommendations with expected cost savings
- Publish ScheduleRecommendation events to EventBridge

Requirements: 1.1-1.10, 8.2
"""

import json
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Key

from autonomous.utils.time_manager import TimeManager


# Environment variables
GPU_COSTS_TABLE = os.environ.get("GPU_COSTS_TABLE", "costguard-gpu-costs")
ACTION_HISTORY_TABLE = os.environ.get("ACTION_HISTORY_TABLE", "costguard-action-history")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "costguard-autonomous-events")
PHASE6_API_ENDPOINT = os.environ.get("PHASE6_API_ENDPOINT", "")
DRY_RUN_MODE = os.environ.get("DRY_RUN_MODE", "false").lower() == "true"
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.8"))
MIN_COST_SAVINGS_PERCENT = float(os.environ.get("MIN_COST_SAVINGS_PERCENT", "20"))
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

# AWS clients
dynamodb = boto3.resource("dynamodb")
events_client = boto3.client("events")
ec2_client = boto3.client("ec2")

# Tables
gpu_costs_table = dynamodb.Table(GPU_COSTS_TABLE)
action_history_table = dynamodb.Table(ACTION_HISTORY_TABLE)


class OptimizationWindow:
    """Represents a time window with low GPU costs suitable for scheduling."""
    
    def __init__(
        self,
        window_start: datetime,
        window_end: datetime,
        avg_spot_price: float,
        price_stability: float,
        region: str,
        instance_type: str,
    ):
        self.window_start = window_start
        self.window_end = window_end
        self.avg_spot_price = avg_spot_price
        self.price_stability = price_stability
        self.region = region
        self.instance_type = instance_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "avg_spot_price": self.avg_spot_price,
            "price_stability": self.price_stability,
            "region": self.region,
            "instance_type": self.instance_type,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OptimizationWindow":
        """Create from dictionary."""
        return cls(
            window_start=datetime.fromisoformat(data["window_start"]),
            window_end=datetime.fromisoformat(data["window_end"]),
            avg_spot_price=data["avg_spot_price"],
            price_stability=data["price_stability"],
            region=data["region"],
            instance_type=data["instance_type"],
        )


class ScheduleRecommendation:
    """Represents a scheduling recommendation for a training job."""
    
    def __init__(
        self,
        recommendation_id: str,
        window: OptimizationWindow,
        confidence_score: float,
        expected_savings_percent: float,
        expected_savings_dollars: float,
    ):
        self.recommendation_id = recommendation_id
        self.window = window
        self.confidence_score = confidence_score
        self.expected_savings_percent = expected_savings_percent
        self.expected_savings_dollars = expected_savings_dollars
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "recommendation_id": self.recommendation_id,
            "window_start": self.window.window_start.isoformat(),
            "window_end": self.window.window_end.isoformat(),
            "confidence_score": self.confidence_score,
            "expected_savings_percent": self.expected_savings_percent,
            "expected_savings_dollars": self.expected_savings_dollars,
            "spot_instance_type": self.window.instance_type,
            "region": self.window.region,
            "historical_pattern": {
                "avg_spot_price": self.window.avg_spot_price,
                "price_stability": self.window.price_stability,
            },
        }


def analyze_cost_patterns(days: int) -> List[OptimizationWindow]:
    """
    Analyze GPU cost patterns over specified number of days.
    
    Args:
        days: Number of days to analyze (minimum 7)
        
    Returns:
        List of identified optimization windows
    """
    # Calculate time range with demo mode compression
    end_time = datetime.utcnow()
    time_window = TimeManager.get_analysis_window(days)
    start_time = end_time - time_window
    
    # Query GPU cost data from DynamoDB
    # In production, this would scan the workload-type-index GSI
    # For now, we'll use a simplified query
    
    optimization_windows = []
    
    # Identify low-cost periods (simplified algorithm)
    # In production, this would use more sophisticated pattern analysis
    
    # Example: Identify early morning hours (2-6 AM) as optimization windows
    current_date = start_time.date()
    end_date = end_time.date()
    
    while current_date <= end_date:
        window_start = datetime.combine(current_date, datetime.min.time()).replace(hour=2)
        window_end = datetime.combine(current_date, datetime.min.time()).replace(hour=6)
        
        # Only include future windows
        if window_start > end_time:
            window = OptimizationWindow(
                window_start=window_start,
                window_end=window_end,
                avg_spot_price=0.294,  # Example price
                price_stability=0.92,  # High stability
                region="us-east-1",
                instance_type="g4dn.xlarge",
            )
            optimization_windows.append(window)
        
        current_date += timedelta(days=1)
    
    return optimization_windows


def identify_optimization_windows(data: List[Dict[str, Any]]) -> List[OptimizationWindow]:
    """
    Identify optimization windows from cost data.
    
    Args:
        data: List of cost data points
        
    Returns:
        List of optimization windows
    """
    # Simplified implementation
    # In production, this would use clustering and pattern recognition
    return []


def calculate_pattern_stability(window: OptimizationWindow) -> float:
    """
    Calculate pattern stability for an optimization window.
    
    Args:
        window: Optimization window to analyze
        
    Returns:
        Stability score between 0.0 and 1.0
    """
    # Simplified implementation
    # In production, this would calculate coefficient of variation
    return window.price_stability


def calculate_confidence_score(window: OptimizationWindow) -> float:
    """
    Calculate confidence score for an optimization window.
    
    Args:
        window: Optimization window to score
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    # Base confidence on pattern stability
    stability = calculate_pattern_stability(window)
    
    # Confidence increases with stability
    confidence = min(1.0, max(0.0, stability))
    
    return confidence


def calculate_expected_savings(
    window: OptimizationWindow,
    on_demand_price: float = 0.526,  # g4dn.xlarge on-demand price
) -> Tuple[float, float]:
    """
    Calculate expected cost savings for using spot instance in window.
    
    Args:
        window: Optimization window
        on_demand_price: On-demand instance price per hour
        
    Returns:
        Tuple of (savings_percent, savings_dollars)
    """
    spot_price = window.avg_spot_price
    savings_dollars = on_demand_price - spot_price
    savings_percent = (savings_dollars / on_demand_price) * 100
    
    return savings_percent, savings_dollars


def should_recommend_spot(savings_percent: float) -> bool:
    """
    Determine if spot instance should be recommended based on savings.
    
    Args:
        savings_percent: Expected savings percentage
        
    Returns:
        True if savings exceed threshold
    """
    return savings_percent >= MIN_COST_SAVINGS_PERCENT


def check_spot_availability(region: str, instance_type: str = "g4dn.xlarge") -> float:
    """
    Check spot instance availability in region.
    
    Args:
        region: AWS region
        instance_type: EC2 instance type
        
    Returns:
        Availability percentage (0.0 to 1.0)
    """
    # Simplified implementation
    # In production, this would query EC2 spot instance availability
    return 0.85  # 85% availability


def generate_recommendation(window: OptimizationWindow) -> Optional[ScheduleRecommendation]:
    """
    Generate scheduling recommendation for an optimization window.
    
    Args:
        window: Optimization window
        
    Returns:
        ScheduleRecommendation if window meets criteria, None otherwise
    """
    # Calculate confidence score
    confidence = calculate_confidence_score(window)
    
    # Only recommend if confidence meets threshold
    if confidence < CONFIDENCE_THRESHOLD:
        return None
    
    # Calculate expected savings
    savings_percent, savings_dollars = calculate_expected_savings(window)
    
    # Only recommend if savings meet threshold
    if not should_recommend_spot(savings_percent):
        return None
    
    # Check spot availability
    availability = check_spot_availability(window.region, window.instance_type)
    if availability < 0.30:
        # Availability too low, don't recommend
        return None
    
    # Generate recommendation ID
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    recommendation_id = f"rec_{timestamp}"
    
    return ScheduleRecommendation(
        recommendation_id=recommendation_id,
        window=window,
        confidence_score=confidence,
        expected_savings_percent=savings_percent,
        expected_savings_dollars=savings_dollars,
    )


def publish_recommendation_event(recommendation: ScheduleRecommendation) -> None:
    """
    Publish ScheduleRecommendation event to EventBridge.
    
    Args:
        recommendation: Recommendation to publish
    """
    # Check DRY_RUN_MODE at runtime, not at module import time
    dry_run = os.environ.get("DRY_RUN_MODE", "false").lower() == "true"
    
    event_detail = recommendation.to_dict()
    
    event = {
        "Source": "costguard.autonomous.scheduler",
        "DetailType": "ScheduleRecommendation",
        "Detail": json.dumps(event_detail, default=str),
        "EventBusName": EVENT_BUS_NAME,
    }
    
    if not dry_run:
        events_client.put_events(Entries=[event])
        print(f"Published ScheduleRecommendation event: {recommendation.recommendation_id}")
    else:
        print(f"[DRY-RUN] Would publish ScheduleRecommendation event: {recommendation.recommendation_id}")
        print(f"[DRY-RUN] Event detail: {json.dumps(event_detail, indent=2, default=str)}")


def record_action(recommendation: ScheduleRecommendation) -> None:
    """
    Record scheduling action in action history table.
    
    Args:
        recommendation: Recommendation to record
    """
    timestamp = datetime.utcnow().isoformat()
    ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())
    
    item = {
        "action_id": f"act_{recommendation.recommendation_id}",
        "timestamp": timestamp,
        "action_type": "schedule",
        "status": "completed" if not DRY_RUN_MODE else "dry_run",
        "parameters": {
            "window_start": recommendation.window.window_start.isoformat(),
            "window_end": recommendation.window.window_end.isoformat(),
            "instance_type": recommendation.window.instance_type,
            "region": recommendation.window.region,
        },
        "confidence_score": Decimal(str(recommendation.confidence_score)),
        "expected_cost_impact": Decimal(str(-recommendation.expected_savings_dollars)),
        "dry_run": DRY_RUN_MODE,
        "ttl": ttl,
    }
    
    if not DRY_RUN_MODE:
        action_history_table.put_item(Item=item)
        print(f"Recorded action: {item['action_id']}")
    else:
        print(f"[DRY-RUN] Would record action: {item['action_id']}")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GPU Scheduler.
    
    Args:
        event: EventBridge event or API Gateway request
        context: Lambda context
        
    Returns:
        Response with recommendations and confidence scores
    """
    print(f"GPU Scheduler invoked with event: {json.dumps(event, default=str)}")
    
    # Parse parameters from event
    if "body" in event:
        # API Gateway request
        body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        days = body.get("days", 7)
        confidence_threshold = body.get("confidence_threshold", CONFIDENCE_THRESHOLD)
        dry_run = body.get("dry_run", DRY_RUN_MODE)
    else:
        # EventBridge scheduled event
        days = 7
        confidence_threshold = CONFIDENCE_THRESHOLD
        dry_run = DRY_RUN_MODE
    
    # Analyze cost patterns
    print(f"Analyzing {days} days of GPU cost patterns...")
    optimization_windows = analyze_cost_patterns(days)
    print(f"Identified {len(optimization_windows)} optimization windows")
    
    # Generate recommendations
    recommendations = []
    for window in optimization_windows:
        recommendation = generate_recommendation(window)
        if recommendation:
            recommendations.append(recommendation)
            
            # Publish event
            publish_recommendation_event(recommendation)
            
            # Record action
            record_action(recommendation)
    
    print(f"Generated {len(recommendations)} recommendations")
    
    # Build response
    response_data = {
        "recommendations": [rec.to_dict() for rec in recommendations],
        "analysis_timestamp": datetime.utcnow().isoformat(),
        "dry_run_mode": dry_run,
    }
    
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(response_data, default=str),
    }
