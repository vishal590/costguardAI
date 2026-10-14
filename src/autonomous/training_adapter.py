"""Dispatch the fixed EC2 training document and verify S3 progress evidence."""
import base64
import os
import json
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from autonomous.training_worker import load, request, serialize, verify

s3 = boto3.client("s3")
ssm = boto3.client("ssm")
BUCKET = os.environ.get("CHECKPOINT_BUCKET", "")
DOCUMENT = os.environ.get("TRAINING_DOCUMENT", "")


def preflight(training):
    if not BUCKET or not DOCUMENT:
        raise ValueError("Training bucket and document must be configured")
    return load(s3, BUCKET, training)[1]


def resume(item, instance_id, state, save_state):
    training = json.loads(json.dumps(item["parameters"]["training"], default=float))
    initial = preflight(training)
    config = request(training, BUCKET, item["action_id"])
    deadline = datetime.fromisoformat(state["cleanup_at"])
    remaining = int((deadline-datetime.now(timezone.utc)).total_seconds()) - 30
    if remaining < 60:
        raise ValueError("Not enough runtime remains for training")
    command_id = state.get("training_command_id")
    if not command_id:
        nodes = ssm.describe_instance_information(Filters=[{"Key": "InstanceIds", "Values": [instance_id]}])["InstanceInformationList"]
        if not nodes or nodes[0].get("PingStatus") != "Online":
            raise RuntimeError("Replacement is not ready for Systems Manager")
        response = ssm.send_command(InstanceIds=[instance_id], DocumentName=DOCUMENT, DocumentVersion="1",
            Parameters={"request": [base64.b64encode(serialize(config)).decode()],
                        "timeout": [str(min(remaining, 600))]}, TimeoutSeconds=60)
        command_id = response["Command"]["CommandId"]
        state["training_command_id"] = command_id
        save_state(state)
    ssm.get_waiter("command_executed").wait(CommandId=command_id, InstanceId=instance_id,
        PluginName="train", WaiterConfig={"Delay": 5, "MaxAttempts": min(120, max(1, remaining//5))})
    invocation = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id, PluginName="train")
    if invocation.get("Status") != "Success" or invocation.get("ResponseCode") != 0:
        raise RuntimeError("Training command did not succeed")
    result = verify(s3, config, initial)
    return {"command_id": command_id, "job_id": training["job_id"],
            "restored_step": result["restored_step"], "final_step": result["final_step"],
            "loss": str(result["loss"]), "checkpoint_key": config["output_checkpoint_key"],
            "checkpoint_sha256": result["output_checkpoint_sha256"], "result_key": config["result_key"]}


def cancel(state, instance_id):
    if state.get("training_command_id"):
        try:
            ssm.cancel_command(CommandId=state["training_command_id"], InstanceIds=[instance_id])
        except ClientError as error:
            # Terminating the owned replacement still stops its process. A
            # completed/missing command must not prevent instance cleanup.
            state["training_cancel_error"] = error.response["Error"]["Code"]

