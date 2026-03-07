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
from boto3.dynamodb.conditions import Key, Attr

from autonomous.utils.time_manager import TimeManager
from autonomous.utils.cloudwatch_metrics import get_metrics_publisher
from autonomous.utils.xray_tracing import trace_subsegment, trace_cost_analysis, XRaySubsegment


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


@trace_subsegment('analyze_cost_patterns')
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
    try:
        # Query GPU costs table for historical cost data
        # Use scan with filter for date range (in production, would use GSI)
        response = gpu_costs_table.scan(
            FilterExpression=Attr('date').between(
                start_time.strftime('%Y-%m-%d'),
                end_time.strftime('%Y-%m-%d')
            )
        )
        
        cost_data = response.get('Items', [])
        
        # If no data in DynamoDB, query EC2 spot price history as fallback
        if not cost_data:
            cost_data = _get_spot_price_history_from_ec2(start_time, end_time)
        
        # Identify optimization windows from actual cost data
        optimization_windows = identify_optimization_windows(cost_data)
        
    except Exception as e:
        print(f"ERROR: Failed to query GPU cost data: {e}")
        # Fallback: Use EC2 spot price history directly
        cost_data = _get_spot_price_history_from_ec2(start_time, end_time)
        optimization_windows = identify_optimization_windows(cost_data)
    
    # Add X-Ray tracing metadata
    trace_cost_analysis(days, len(optimization_windows))
    
    return optimization_windows


def identify_optimization_windows(data: List[Dict[str, Any]]) -> List[OptimizationWindow]:
    """
    Identify optimization windows from cost data using pattern analysis.
    
    Args:
        data: List of cost data points
        
    Returns:
        List of optimization windows
    """
    if not data:
        return []
    
    # Group cost data by hour of day to identify patterns
    hourly_costs = {}
    for item in data:
        date_str = item.get('date', '')
        if date_str:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                hour = dt.hour
                cost = float(item.get('cost', 0))
                
                if hour not in hourly_costs:
                    hourly_costs[hour] = []
                hourly_costs[hour].append(cost)
            except:
                continue
    
    # Calculate average cost per hour
    avg_hourly_costs = {}
    for hour, costs in hourly_costs.items():
        if costs:
            avg_hourly_costs[hour] = sum(costs) / len(costs)
    
    if not avg_hourly_costs:
        return []
    
    # Find hours with consistently low costs (bottom 25%)
    sorted_hours = sorted(avg_hourly_costs.items(), key=lambda x: x[1])
    low_cost_threshold = sorted_hours[len(sorted_hours) // 4][1] if len(sorted_hours) >= 4 else sorted_hours[0][1]
    
    # Identify contiguous low-cost periods (optimization windows)
    low_cost_hours = [hour for hour, cost in avg_hourly_costs.items() if cost <= low_cost_threshold * 1.1]
    low_cost_hours.sort()
    
    optimization_windows = []
    current_date = datetime.utcnow().date()
    
    # Group contiguous hours into windows
    if low_cost_hours:
        window_start_hour = low_cost_hours[0]
        window_end_hour = low_cost_hours[0]
        
        for i in range(1, len(low_cost_hours)):
            if low_cost_hours[i] == low_cost_hours[i-1] + 1:
                window_end_hour = low_cost_hours[i]
            else:
                # Create window for this contiguous period
                if window_end_hour - window_start_hour >= 2:  # At least 2 hours
                    window_start = datetime.combine(current_date, datetime.min.time()).replace(hour=window_start_hour)
                    window_end = datetime.combine(current_date, datetime.min.time()).replace(hour=window_end_hour + 1)
                    
                    # Calculate average spot price for this window
                    window_costs = [avg_hourly_costs[h] for h in range(window_start_hour, window_end_hour + 1) if h in avg_hourly_costs]
                    avg_price = sum(window_costs) / len(window_costs) if window_costs else 0.3
                    
                    # Calculate price stability (coefficient of variation)
                    if len(window_costs) > 1:
                        mean_cost = sum(window_costs) / len(window_costs)
                        variance = sum((c - mean_cost) ** 2 for c in window_costs) / len(window_costs)
                        std_dev = variance ** 0.5
                        cv = std_dev / mean_cost if mean_cost > 0 else 1.0
                        stability = max(0.0, 1.0 - cv)  # Higher stability = lower variation
                    else:
                        stability = 0.9
                    
                    # Get instance type and region from data if available
                    instance_type = data[0].get('instance_type', 'g4dn.xlarge') if data else 'g4dn.xlarge'
                    region = data[0].get('region', 'us-east-1') if data else 'us-east-1'
                    
                    window = OptimizationWindow(
                        window_start=window_start,
                        window_end=window_end,
                        avg_spot_price=avg_price,
                        price_stability=stability,
                        region=region,
                        instance_type=instance_type,
                    )
                    optimization_windows.append(window)
                
                window_start_hour = low_cost_hours[i]
                window_end_hour = low_cost_hours[i]
        
        # Add final window
        if window_end_hour - window_start_hour >= 2:
            window_start = datetime.combine(current_date, datetime.min.time()).replace(hour=window_start_hour)
            window_end = datetime.combine(current_date, datetime.min.time()).replace(hour=window_end_hour + 1)
            
            window_costs = [avg_hourly_costs[h] for h in range(window_start_hour, window_end_hour + 1) if h in avg_hourly_costs]
            avg_price = sum(window_costs) / len(window_costs) if window_costs else 0.3
            
            if len(window_costs) > 1:
                mean_cost = sum(window_costs) / len(window_costs)
                variance = sum((c - mean_cost) ** 2 for c in window_costs) / len(window_costs)
                std_dev = variance ** 0.5
                cv = std_dev / mean_cost if mean_cost > 0 else 1.0
                stability = max(0.0, 1.0 - cv)
            else:
                stability = 0.9
            
            instance_type = data[0].get('instance_type', 'g4dn.xlarge') if data else 'g4dn.xlarge'
            region = data[0].get('region', 'us-east-1') if data else 'us-east-1'
            
            window = OptimizationWindow(
                window_start=window_start,
                window_end=window_end,
                avg_spot_price=avg_price,
                price_stability=stability,
                region=region,
                instance_type=instance_type,
            )
            optimization_windows.append(window)
    
    return optimization_windows


def _get_spot_price_history_from_ec2(start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
    """Get spot price history from EC2 API as fallback."""
    try:
        # Query EC2 spot price history
        response = ec2_client.describe_spot_price_history(
            InstanceTypes=['g4dn.xlarge', 'g4dn.2xlarge', 'g4dn.4xlarge'],
            ProductDescriptions=['Linux/UNIX'],
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=1000
        )
        
        # Convert to cost data format
        cost_data = []
        for price_history in response.get('SpotPriceHistory', []):
            cost_data.append({
                'date': price_history['Timestamp'].strftime('%Y-%m-%d'),
                'cost': float(price_history['SpotPrice']),
                'instance_type': price_history['InstanceType'],
                'region': price_history['AvailabilityZone'][:-1]  # Remove AZ suffix
            })
        
        return cost_data
    except Exception as e:
        print(f"ERROR: Failed to get spot price history: {e}")
        return []


def calculate_pattern_stability(window: OptimizationWindow) -> float:
    """
    Calculate pattern stability for an optimization window using coefficient of variation.
    
    Args:
        window: Optimization window to analyze
        
    Returns:
        Stability score between 0.0 and 1.0
    """
    # Query historical spot prices for this window across multiple days
    try:
        # Get spot prices for this time window over the last 7 days
        historical_prices = []
        for day_offset in range(7):
            check_date = window.window_start - timedelta(days=day_offset)
            check_end = window.window_end - timedelta(days=day_offset)
            
            try:
                response = ec2_client.describe_spot_price_history(
                    InstanceTypes=[window.instance_type],
                    ProductDescriptions=['Linux/UNIX'],
                    StartTime=check_date,
                    EndTime=check_end,
                    MaxResults=100
                )
                
                for price_history in response.get('SpotPriceHistory', []):
                    historical_prices.append(float(price_history['SpotPrice']))
            except:
                continue
        
        if len(historical_prices) < 2:
            # Fallback to window's stored stability
            return window.price_stability
        
        # Calculate coefficient of variation
        mean_price = sum(historical_prices) / len(historical_prices)
        variance = sum((p - mean_price) ** 2 for p in historical_prices) / len(historical_prices)
        std_dev = variance ** 0.5
        cv = std_dev / mean_price if mean_price > 0 else 1.0
        
        # Convert to stability score (lower CV = higher stability)
        stability = max(0.0, 1.0 - cv)
        return stability
        
    except Exception as e:
        print(f"ERROR: Failed to calculate pattern stability: {e}")
        # Fallback to window's stored stability
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
    Check spot instance availability in region using EC2 API.
    
    Args:
        region: AWS region
        instance_type: EC2 instance type
        
    Returns:
        Availability percentage (0.0 to 1.0)
    """
    try:
        # Query spot price history to infer availability
        # If we can get recent spot prices, the instance is likely available
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        response = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            ProductDescriptions=['Linux/UNIX'],
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=10
        )
        
        # If we got recent prices, assume availability
        if response.get('SpotPriceHistory'):
            # Check multiple availability zones
            azs = set()
            for price_history in response['SpotPriceHistory']:
                if price_history['AvailabilityZone'].startswith(region):
                    azs.add(price_history['AvailabilityZone'])
            
            # Availability is proportional to number of AZs with prices
            # Assume 3 AZs per region, so 3 AZs = 100% availability
            availability = min(1.0, len(azs) / 3.0)
            return max(0.5, availability)  # Minimum 50% if we got any prices
        
        return 0.5  # Default if no recent prices
        
    except Exception as e:
        print(f"ERROR: Failed to check spot availability: {e}")
        return 0.5  # Default availability on error


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
    
    # Get metrics publisher
    metrics = get_metrics_publisher()
    
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
    total_confidence = 0.0
    
    for window in optimization_windows:
        recommendation = generate_recommendation(window)
        if recommendation:
            recommendations.append(recommendation)
            total_confidence += recommendation.confidence_score
            
            # Publish event
            publish_recommendation_event(recommendation)
            
            # Record action
            record_action(recommendation)
    
    print(f"Generated {len(recommendations)} recommendations")
    
    # Publish CloudWatch metrics
    if recommendations:
        avg_confidence = total_confidence / len(recommendations)
        metrics.publish_confidence_score(avg_confidence)
        print(f"Published confidence score metric: {avg_confidence:.2f}")
    
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
