"""
Spot Manager Lambda Function

Handles spot instance interruptions with automatic checkpoint save/restore
and fallback to on-demand instances.

Responsibilities:
- Subscribe to EC2 spot interruption warnings
- Trigger checkpoint save within 30 seconds
- Verify checkpoint integrity
- Acquire replacement spot or on-demand instances
- Restore training from checkpoints
- Track migration costs

Requirements: 2.1-2.12
"""

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Key

from autonomous.utils.cloudwatch_metrics import get_metrics_publisher
from autonomous.utils.xray_tracing import (
    trace_subsegment,
    trace_checkpoint_operation,
    trace_migration_workflow,
    XRaySubsegment
)


# Environment variables
CHECKPOINT_BUCKET = os.environ.get("CHECKPOINT_BUCKET", "costguard-training-checkpoints")
TRAINING_CHECKPOINTS_TABLE = os.environ.get("TRAINING_CHECKPOINTS_TABLE", "costguard-training-checkpoints")
ACTION_HISTORY_TABLE = os.environ.get("ACTION_HISTORY_TABLE", "costguard-action-history")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "costguard-autonomous-events")
SPOT_TIMEOUT_SECONDS = int(os.environ.get("SPOT_TIMEOUT_SECONDS", "300"))  # 5 minutes
CHECKPOINT_TIMEOUT_SECONDS = int(os.environ.get("CHECKPOINT_TIMEOUT_SECONDS", "30"))
APPROVAL_REQUIRED_FOR_ONDEMAND = os.environ.get("APPROVAL_REQUIRED_FOR_ONDEMAND", "true").lower() == "true"

# AWS clients
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")
ec2_client = boto3.client("ec2")
pricing_client = boto3.client("pricing", region_name="us-east-1")
events_client = boto3.client("events")

# Tables
training_checkpoints_table = dynamodb.Table(TRAINING_CHECKPOINTS_TABLE)
action_history_table = dynamodb.Table(ACTION_HISTORY_TABLE)


class TrainingCheckpoint:
    """Represents a training checkpoint with metadata."""
    
    def __init__(
        self,
        checkpoint_id: str,
        instance_id: str,
        training_job_id: str,
        s3_location: str,
        training_state: Dict[str, Any],
        checkpoint_size_bytes: int = 0,
    ):
        self.checkpoint_id = checkpoint_id
        self.instance_id = instance_id
        self.training_job_id = training_job_id
        self.s3_location = s3_location
        self.training_state = training_state
        self.checkpoint_size_bytes = checkpoint_size_bytes
        self.created_at = datetime.utcnow()
        self.integrity_verified = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DynamoDB."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at.isoformat(),
            "instance_id": self.instance_id,
            "training_job_id": self.training_job_id,
            "s3_location": self.s3_location,
            "checkpoint_size_bytes": self.checkpoint_size_bytes,
            "integrity_verified": self.integrity_verified,
            "training_state": self.training_state,
            "created_by": "spot_manager",
            "restored_count": 0,
        }


@trace_subsegment('save_checkpoint')
def save_checkpoint(instance_id: str, training_state: Dict[str, Any]) -> str:
    """
    Save training checkpoint to S3 within 30 seconds.
    
    Args:
        instance_id: EC2 instance ID
        training_state: Training state to save (epoch, step, loss, model_name)
        
    Returns:
        Checkpoint ID
    """
    start_time = time.time()
    
    # Generate checkpoint ID
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    model_name = training_state.get("model_name", "model")
    checkpoint_id = f"ckpt_{timestamp}_{model_name}"
    
    # Serialize training state
    checkpoint_data = json.dumps(training_state, default=str).encode('utf-8')
    checkpoint_size = len(checkpoint_data)
    
    # Generate S3 key
    training_job_id = training_state.get("training_job_id", "unknown")
    s3_key = f"{training_job_id}/checkpoint_epoch_{training_state.get('epoch', 0)}.json"
    s3_location = f"s3://{CHECKPOINT_BUCKET}/{s3_key}"
    
    # Upload to S3
    try:
        s3_client.put_object(
            Bucket=CHECKPOINT_BUCKET,
            Key=s3_key,
            Body=checkpoint_data,
            Metadata={
                "checkpoint_id": checkpoint_id,
                "instance_id": instance_id,
                "training_job_id": training_job_id,
            }
        )
        
        elapsed = time.time() - start_time
        print(f"Checkpoint saved to S3 in {elapsed:.2f}s: {s3_location}")
        
        if elapsed > CHECKPOINT_TIMEOUT_SECONDS:
            print(f"WARNING: Checkpoint save exceeded timeout ({elapsed:.2f}s > {CHECKPOINT_TIMEOUT_SECONDS}s)")
        
        # Create checkpoint object
        checkpoint = TrainingCheckpoint(
            checkpoint_id=checkpoint_id,
            instance_id=instance_id,
            training_job_id=training_job_id,
            s3_location=s3_location,
            training_state=training_state,
            checkpoint_size_bytes=checkpoint_size,
        )
        
        # Verify integrity
        checkpoint.integrity_verified = verify_checkpoint_integrity(checkpoint_id, s3_key, checkpoint_data)
        
        # Store metadata in DynamoDB
        ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())
        item = checkpoint.to_dict()
        item["ttl"] = ttl
        
        training_checkpoints_table.put_item(Item=item)
        
        # Add X-Ray tracing metadata
        trace_checkpoint_operation(checkpoint_id, checkpoint_size, elapsed * 1000)
        
        return checkpoint_id
        
    except Exception as e:
        print(f"ERROR: Failed to save checkpoint: {e}")
        raise


def verify_checkpoint_integrity(checkpoint_id: str, s3_key: str, original_data: bytes) -> bool:
    """
    Verify checkpoint integrity with hash validation.
    
    Args:
        checkpoint_id: Checkpoint ID
        s3_key: S3 object key
        original_data: Original checkpoint data
        
    Returns:
        True if integrity verified
    """
    try:
        # Calculate hash of original data
        original_hash = hashlib.sha256(original_data).hexdigest()
        
        # Download from S3 and verify
        response = s3_client.get_object(Bucket=CHECKPOINT_BUCKET, Key=s3_key)
        downloaded_data = response['Body'].read()
        downloaded_hash = hashlib.sha256(downloaded_data).hexdigest()
        
        if original_hash == downloaded_hash:
            print(f"Checkpoint integrity verified: {checkpoint_id}")
            return True
        else:
            print(f"ERROR: Checkpoint integrity check failed: {checkpoint_id}")
            return False
            
    except Exception as e:
        print(f"ERROR: Failed to verify checkpoint integrity: {e}")
        return False


def restore_from_checkpoint(checkpoint_id: str, new_instance_id: str) -> bool:
    """Legacy metadata-only checkpoints cannot prove training restoration.

    Use parameters.training on an approved replacement action. The configured
    worker restores real weights/optimizer state and verifies output progress.
    """
    print("Training restore requires the approved executor training contract")
    return False


def select_most_recent_checkpoint(training_job_id: str) -> Optional[str]:
    """
    Select the most recent valid checkpoint for a training job.
    
    Args:
        training_job_id: Training job ID
        
    Returns:
        Checkpoint ID or None
    """
    try:
        # Query checkpoints for this training job
        response = training_checkpoints_table.query(
            IndexName="training-job-index",
            KeyConditionExpression=Key("training_job_id").eq(training_job_id),
            ScanIndexForward=False,  # Sort descending by created_at
            Limit=10
        )
        
        # Find most recent verified checkpoint
        for item in response.get("Items", []):
            if item.get("integrity_verified"):
                return item["checkpoint_id"]
        
        print(f"WARNING: No verified checkpoints found for training job: {training_job_id}")
        return None
        
    except Exception as e:
        print(f"ERROR: Failed to select checkpoint: {e}")
        return None


def acquire_replacement_instance(region: str, instance_type: str, training_job_id: str,
                                 parameters=None, request_id=None) -> Tuple[Optional[str], str]:
    """Queue a real replacement request; never manufacture a running instance."""
    parameters = dict(parameters or {})
    parameters.update(region=region, instance_type=instance_type, training_job_id=training_job_id)
    if check_spot_availability(region, instance_type):
        submitted = submit_replacement_request("spot_migration", parameters, request_id)
    else:
        submitted = submit_replacement_request("ondemand_fallback", parameters, request_id)
    return None, "pending_approval" if submitted else "failed"


def submit_replacement_request(action_type, parameters, request_id=None):
    from autonomous.action_executor import validate_parameters
    try:
        validate_parameters(action_type, parameters)
        request_id = request_id or "req_" + uuid.uuid4().hex
        action_request = {
            "request_id": request_id, "action_id": "act_" + request_id,
            "action_type": action_type, "parameters": parameters,
            "approval_required": True, "confidence_score": 0.5,
            "expected_cost_impact": 0, "timestamp": parameters.pop("request_timestamp", datetime.utcnow().isoformat()),
        }
        response = events_client.put_events(Entries=[{
            "Source": "costguard.autonomous.rightsizer" if action_type == "right_sizing" else "costguard.autonomous.spotmanager",
            "DetailType": "ActionRequest",
            "Detail": json.dumps(action_request), "EventBusName": EVENT_BUS_NAME}])
        if response.get("FailedEntryCount", 0):
            raise RuntimeError("Replacement action was not accepted")
        return request_id
    except (ValueError, KeyError, TypeError) as error:
        print(f"Replacement request rejected: {error}")
        return None


def check_spot_availability(region: str, instance_type: str) -> bool:
    """
    Check if spot instances are available in region.
    
    Args:
        region: AWS region
        instance_type: EC2 instance type
        
    Returns:
        True if spot instances available
    """
    try:
        # Query EC2 spot price history to check availability
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        response = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            ProductDescriptions=['Linux/UNIX'],
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=10
        )
        
        # If we got recent spot prices, instance is available
        return len(response.get('SpotPriceHistory', [])) > 0
        
    except Exception as e:
        print(f"ERROR: Failed to check spot availability: {e}")
        return False


def request_ondemand_approval(training_job_id: str, instance_type: str, region: str,
                             parameters=None):
    """Return a submitted request ID, not a simulated approval decision."""
    parameters = dict(parameters or {})
    parameters.update(training_job_id=training_job_id, instance_type=instance_type, region=region)
    return submit_replacement_request("ondemand_fallback", parameters)


def track_spot_cost(instance_id: str, duration_hours: float) -> Decimal:
    """
    Track spot instance cost using real AWS Pricing API and EC2 spot price history.
    
    Attempts to get actual spot pricing from EC2 API. If that fails, estimates
    based on on-demand pricing (typically 60% of on-demand). If all API calls fail,
    falls back to hardcoded pricing for g4dn.xlarge ($0.294/hour).
    
    Args:
        instance_id: Instance ID
        duration_hours: Duration in hours
        
    Returns:
        Cost in dollars
        
    Note:
        Fallback pricing is used only when AWS API calls fail. The fallback value
        ($0.294/hour) represents approximate g4dn.xlarge spot pricing in us-east-1.
        Actual pricing may vary by region and instance type.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Get instance type from EC2 API
        ec2_response = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance_type = 'g4dn.xlarge'  # Default
        if ec2_response.get('Reservations'):
            instance_type = ec2_response['Reservations'][0]['Instances'][0].get('InstanceType', 'g4dn.xlarge')
        
        # Get actual spot price from EC2 API
        response = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            ProductDescriptions=['Linux/UNIX'],
            MaxResults=1
        )
        
        if response.get('SpotPriceHistory'):
            spot_price = float(response['SpotPriceHistory'][0]['SpotPrice'])
        else:
            # Fallback: estimate 60% of on-demand price
            on_demand_price = _get_ondemand_price_from_pricing_api(instance_type)
            spot_price = on_demand_price * 0.6
        
        cost = Decimal(str(spot_price)) * Decimal(str(duration_hours))
        return cost
        
    except Exception as e:
        logger.warning(f"Failed to track spot cost via API for {instance_id}: {e}. Using fallback pricing.")
        # Fallback to simplified pricing (g4dn.xlarge spot ~$0.294/hour in us-east-1)
        # This is a last resort when all API calls fail
        spot_price_per_hour = Decimal("0.294")
        return spot_price_per_hour * Decimal(str(duration_hours))


def track_ondemand_cost(instance_id: str, duration_hours: float) -> Decimal:
    """
    Track on-demand instance cost using real AWS Pricing API.
    
    Attempts to get actual on-demand pricing from AWS Pricing API. If the API call
    fails, falls back to hardcoded pricing for g4dn.xlarge ($0.526/hour).
    
    Args:
        instance_id: Instance ID
        duration_hours: Duration in hours
        
    Returns:
        Cost in dollars
        
    Note:
        Fallback pricing is used only when AWS Pricing API calls fail. The fallback
        value ($0.526/hour) represents approximate g4dn.xlarge on-demand pricing
        in us-east-1. Actual pricing may vary by region and instance type.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Get actual on-demand price from Pricing API
        instance_type = instance_id.split('.')[0] if '.' in instance_id else 'g4dn.xlarge'
        ondemand_price_per_hour = _get_ondemand_price_from_pricing_api(instance_type)
        cost = Decimal(str(ondemand_price_per_hour)) * Decimal(str(duration_hours))
        return cost
        
    except Exception as e:
        logger.warning(f"Failed to track on-demand cost via API for {instance_id}: {e}. Using fallback pricing.")
        # Fallback to simplified pricing (g4dn.xlarge on-demand $0.526/hour in us-east-1)
        # This is a last resort when Pricing API calls fail
        ondemand_price_per_hour = Decimal("0.526")
        return ondemand_price_per_hour * Decimal(str(duration_hours))


def calculate_total_training_cost(training_job_id: str) -> Dict[str, Decimal]:
    """
    Calculate total training cost including all migrations.
    
    Args:
        training_job_id: Training job ID
        
    Returns:
        Dict with spot_cost, ondemand_cost, total_cost
    """
    try:
        # Query all actions for this training job
        response = action_history_table.query(
            IndexName="action-type-index",
            KeyConditionExpression=Key("action_type").eq("spot_migration"),
            FilterExpression="contains(parameters.training_job_id, :job_id)",
            ExpressionAttributeValues={":job_id": training_job_id}
        )
        
        spot_cost = Decimal("0")
        ondemand_cost = Decimal("0")
        
        for item in response.get("Items", []):
            params = item.get("parameters", {})
            spot_cost += Decimal(str(params.get("spot_cost", 0)))
            ondemand_cost += Decimal(str(params.get("ondemand_cost", 0)))
        
        total_cost = spot_cost + ondemand_cost
        
        return {
            "spot_cost": spot_cost,
            "ondemand_cost": ondemand_cost,
            "total_cost": total_cost,
        }
        
    except Exception as e:
        print(f"ERROR: Failed to calculate total cost: {e}")
        return {
            "spot_cost": Decimal("0"),
            "ondemand_cost": Decimal("0"),
            "total_cost": Decimal("0"),
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Save supplied checkpoint metadata and submit a replacement for approval.

    The configured launch template must boot the actual workload. Checkpoint
    metadata alone does not establish restoration of model weights or training.
    """
    detail = event.get("detail", {})
    parameters = dict(detail.get("parameters", {}))
    parameters.setdefault("region", event.get("region", os.environ.get("AWS_REGION", "us-east-1")))
    instance_id = detail.get("instance_id", detail.get("instance-id"))
    training_job_id = detail.get("training_job_id")
    if not instance_id or not training_job_id:
        return {"statusCode": 400, "body": json.dumps({"error": "instance_id and training_job_id are required"})}
    if os.environ.get("DRY_RUN_MODE", "true").lower() == "true":
        return {"statusCode": 200, "body": json.dumps({"status": "dry_run"})}
    from autonomous.action_executor import validate_parameters
    try:
        validate_parameters("ondemand_fallback", parameters)
    except (ValueError, KeyError, TypeError) as error:
        return {"statusCode": 400, "body": json.dumps({"error": str(error)})}
    # Use only caller-supplied checkpoint state. Never invent training progress.
    checkpoint_id = None
    if detail.get("training_state"):
        state = dict(detail["training_state"], training_job_id=training_job_id)
        checkpoint_id = save_checkpoint(instance_id, state)
        parameters["checkpoint_id"] = checkpoint_id
    parameters["source_instance_id"] = instance_id
    parameters["request_timestamp"] = event.get("time") or datetime.utcnow().isoformat()
    request_id = "req_" + hashlib.sha256((event.get("id") or json.dumps(detail, sort_keys=True)).encode()).hexdigest()[:40]
    _, mode = acquire_replacement_instance(parameters["region"], detail.get("instance_type", "g4dn.xlarge"),
                                          training_job_id, parameters, request_id)
    return {"statusCode": 202 if mode == "pending_approval" else 400,
            "body": json.dumps({"status": mode, "request_id": request_id,
                                "action_id": "act_" + request_id, "checkpoint_id": checkpoint_id})}
