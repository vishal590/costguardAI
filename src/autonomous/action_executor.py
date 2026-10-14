"""Execute approved, reversible EC2 operations and persist their recovery state.

Schedule actions start/stop an existing opted-in EC2 instance. Replacement actions
launch one instance from an explicitly versioned, opted-in launch template. Model
training and checkpoint application remain the responsibility of that workload.
"""
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "costguard-autonomous-events")
SCHEDULE_GROUP = os.environ.get("SCHEDULE_GROUP", "costguard-autonomous")
EXECUTOR_ARN = os.environ.get("EXECUTOR_ARN", "")
SCHEDULE_ROLE_ARN = os.environ.get("SCHEDULE_ROLE_ARN", "")
dynamodb = boto3.resource("dynamodb")
action_history_table = dynamodb.Table(os.environ.get("ACTION_HISTORY_TABLE", "costguard-action-history"))
rollback_table = dynamodb.Table(os.environ.get("MIGRATION_ROLLBACKS_TABLE", "costguard-migration-rollbacks"))
ec2 = boto3.client("ec2", region_name=REGION)
scheduler = boto3.client("scheduler", region_name=REGION)
events = boto3.client("events")
ce = boto3.client("ce", region_name="us-east-1")


def token(action_id):
    return hashlib.sha256(action_id.encode()).hexdigest()[:48]


def utcnow():
    return datetime.now(timezone.utc)


def encode(value):
    return json.dumps(value, default=lambda obj: float(obj) if isinstance(obj, Decimal) else str(obj))


def update(key, **values):
    names = {"#n" + str(i): name for i, name in enumerate(values)}
    attrs = {":v" + str(i): value for i, value in enumerate(values.values())}
    action_history_table.update_item(Key=key,
        UpdateExpression="SET " + ", ".join(f"#n{i} = :v{i}" for i in range(len(values))),
        ExpressionAttributeNames=names, ExpressionAttributeValues=attrs)


def get_record(detail):
    key = {"action_id": detail["action_id"], "timestamp": detail["action_timestamp"]}
    item = action_history_table.get_item(Key=key, ConsistentRead=True).get("Item")
    if not item:
        raise ValueError("Action record not found")
    return key, item


def managed(tags):
    tags = {tag["Key"]: tag["Value"] for tag in tags}
    return (tags.get("CostGuardManaged", "").lower() == "true"
            and tags.get("CostGuardProtected", "false").lower() != "true"
            and tags.get("DoNotStop", "false").lower() != "true"
            and tags.get("Environment", "").lower() not in ("prod", "production"))


def instance(instance_id):
    data = ec2.describe_instances(InstanceIds=[instance_id])
    items = [item for reservation in data["Reservations"] for item in reservation["Instances"]]
    if len(items) != 1 or not managed(items[0].get("Tags", [])):
        raise ValueError("Target must be an unprotected CostGuardManaged=true instance")
    return items[0]


def validate_parameters(action_type, parameters):
    if action_type not in ("schedule", "spot_migration", "ondemand_fallback", "right_sizing"):
        raise ValueError("Unsupported reversible action type")
    if parameters.get("region") != REGION:
        raise ValueError("Execution is restricted to the stack region")
    if action_type == "schedule":
        if not parameters.get("instance_id"):
            raise ValueError("Schedule execution requires instance_id")
        start = datetime.fromisoformat(parameters["window_start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(parameters["window_end"].replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("Schedule times must include a timezone")
        hours = (end - start).total_seconds() / 3600
        if not 0 < hours <= 24 or start <= utcnow() + timedelta(minutes=1):
            raise ValueError("Schedule needs a future start and a window of at most 24 hours")
    elif action_type == "right_sizing":
        if not parameters.get("instance_id") or not parameters.get("new_instance_type"):
            raise ValueError("Right sizing requires instance_id and new_instance_type")
        hours = 1
    else:
        version = str(parameters.get("launch_template_version", ""))
        if not parameters.get("launch_template_id") or not version.isdigit() or int(version) < 1:
            raise ValueError("Replacement requires launch_template_id and a numeric version")
        minutes = int(parameters.get("max_runtime_minutes", 0))
        if not 1 <= minutes <= 1440:
            raise ValueError("Replacement runtime must be between 1 and 1440 minutes")
        hours = minutes / 60
    if parameters.get("training") is not None:
        from autonomous.training_worker import validate
        if action_type not in ("spot_migration", "ondemand_fallback"):
            raise ValueError("Checkpoint training is supported for replacement actions only")
        validate(parameters["training"])
        if parameters.get("training_job_id", parameters["training"]["job_id"]) != parameters["training"]["job_id"]:
            raise ValueError("Training job identity mismatch")
    rate = Decimal(str(parameters.get("max_hourly_cost", 0)))
    if not rate.is_finite() or rate <= 0:
        raise ValueError("An explicit positive max_hourly_cost is required")
    return rate * Decimal(str(hours))


def check_budget(estimated_cost):
    # Fail closed: incomplete billing information is not permission to spend.
    now = utcnow()
    response = ce.get_cost_and_usage(
        TimePeriod={"Start": now.replace(day=1).strftime("%Y-%m-%d"),
                    "End": (now + timedelta(days=1)).strftime("%Y-%m-%d")},
        Granularity="MONTHLY", Metrics=["UnblendedCost"])
    rows = response.get("ResultsByTime", [])
    if not rows:
        raise ValueError("Cost Explorer did not return a budget baseline")
    if any(row["Total"]["UnblendedCost"]["Unit"] != "USD" for row in rows):
        raise ValueError("Budget baseline must be in USD")
    spent = sum(Decimal(row["Total"]["UnblendedCost"]["Amount"]) for row in rows)
    limit = Decimal(os.environ.get("FREE_TIER_BUDGET_LIMIT", "5"))
    if spent + estimated_cost > limit:
        raise ValueError("Month-to-date cost plus the action estimate exceeds the budget")


def resource_lock(item):
    instance_id = item["parameters"].get("instance_id")
    if not instance_id:
        return
    rollback_table.put_item(Item={"rollback_id": "resource-" + instance_id, "created_at": "lock",
        "owner": item["action_id"], "ttl": int(time.time()) + 90 * 86400},
        ConditionExpression="attribute_not_exists(rollback_id) OR #owner = :owner",
        ExpressionAttributeNames={"#owner": "owner"}, ExpressionAttributeValues={":owner": item["action_id"]})


def release_resource(item):
    instance_id = item["parameters"].get("instance_id")
    if instance_id:
        try:
            rollback_table.delete_item(Key={"rollback_id": "resource-" + instance_id, "created_at": "lock"},
                ConditionExpression="#owner = :owner", ExpressionAttributeNames={"#owner": "owner"},
                ExpressionAttributeValues={":owner": item["action_id"]})
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise


def snapshot(key, item):
    rollback_key = {"rollback_id": "execution-" + token(item["action_id"]), "created_at": key["timestamp"]}
    saved = rollback_table.get_item(Key=rollback_key, ConsistentRead=True).get("Item")
    if saved:
        resource_lock(item)
        return saved
    parameters = item["parameters"]
    resource_lock(item)
    state = dict(rollback_key, action_id=item["action_id"], action_timestamp=key["timestamp"],
                 action_type=item["action_type"], parameters=parameters,
                 ttl=int(time.time()) + 90 * 86400)
    if item["action_type"] in ("schedule", "right_sizing"):
        current = instance(parameters["instance_id"])
        if current["State"]["Name"] not in ("running", "stopped"):
            raise ValueError("Instance must be running or stopped")
        if item["action_type"] == "schedule" and current["State"]["Name"] != "stopped":
            raise ValueError("A scheduled target must initially be stopped")
        state.update(instance_id=current["InstanceId"], original_state=current["State"]["Name"],
                     original_type=current["InstanceType"])
    else:
        template = ec2.describe_launch_templates(LaunchTemplateIds=[parameters["launch_template_id"]])["LaunchTemplates"][0]
        if not managed(template.get("Tags", [])):
            raise ValueError("Launch template must be opted in and unprotected")
        data = ec2.describe_launch_template_versions(LaunchTemplateId=parameters["launch_template_id"],
            Versions=[str(parameters["launch_template_version"])] )["LaunchTemplateVersions"][0]["LaunchTemplateData"]
        profile = data.get("IamInstanceProfile")
        expected_profile = os.environ.get("TRAINING_INSTANCE_PROFILE_ARN")
        if parameters.get("training"):
            from autonomous.training_adapter import preflight
            preflight(json.loads(encode(parameters["training"])))
            if not expected_profile or profile != {"Arn": expected_profile}:
                raise ValueError("Training requires the configured instance profile ARN")
        elif profile:
            raise ValueError("Instance profiles require an explicitly configured training workload")
        if data.get("InstanceMarketOptions"):
            raise ValueError("Launch-template market overrides are unsupported")
        # Never allow template tags to defeat resource ownership checks.
        state["launch_template_id"] = template["LaunchTemplateId"]
    rollback_table.put_item(Item=state,
                            ConditionExpression="attribute_not_exists(rollback_id)")
    update(key, rollback_id=state["rollback_id"], rollback_created=True)
    return state


def save_snapshot(state):
    rollback_table.put_item(Item=state)


def schedule_callback(item, phase, when):
    if not EXECUTOR_ARN or not SCHEDULE_ROLE_ARN:
        raise ValueError("Executor and schedule role ARNs must be configured")
    name = "cg-" + token(item["action_id"]) + "-" + phase.lower()
    target = {"Arn": EXECUTOR_ARN, "RoleArn": SCHEDULE_ROLE_ARN,
        "Input": encode({"source": "costguard.autonomous.schedule", "detail-type": phase,
                         "detail": {"action_id": item["action_id"], "action_timestamp": item["timestamp"]}}),
        "RetryPolicy": {"MaximumEventAgeInSeconds": 3600, "MaximumRetryAttempts": 10}}
    if os.environ.get("SCHEDULE_DLQ_ARN"):
        target["DeadLetterConfig"] = {"Arn": os.environ["SCHEDULE_DLQ_ARN"]}
    scheduler.create_schedule(Name=name, GroupName=SCHEDULE_GROUP,
        ClientToken=token(name), ScheduleExpression="at(" + when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + ")",
        ScheduleExpressionTimezone="UTC", FlexibleTimeWindow={"Mode": "OFF"},
        ActionAfterCompletion="DELETE", Target=target)
    return name


def delete_callback(name):
    try:
        scheduler.delete_schedule(Name=name, GroupName=SCHEDULE_GROUP)
    except ClientError as error:
        if error.response["Error"]["Code"] != "ResourceNotFoundException":
            raise


def set_instance_state(instance_id, target):
    current = instance(instance_id)["State"]["Name"]
    if current == target:
        return
    if current not in ("running", "stopped", "pending", "stopping"):
        raise ValueError("Cannot restore a terminated or unsupported instance")
    if current in ("pending", "stopping"):
        ec2.get_waiter("instance_running" if current == "pending" else "instance_stopped").wait(
            InstanceIds=[instance_id], WaiterConfig={"Delay": 5, "MaxAttempts": 100})
    if target == "stopped":
        ec2.stop_instances(InstanceIds=[instance_id])
    else:
        ec2.start_instances(InstanceIds=[instance_id])
    ec2.get_waiter("instance_" + target).wait(InstanceIds=[instance_id],
                                            WaiterConfig={"Delay": 5, "MaxAttempts": 100})


def completion(key, item):
    # Event publication is retried from the durable completed record. Delivery is
    # at least once; the Learning Engine updates this same record idempotently.
    if item.get("completion_published"):
        return
    detail = {"action_id": item["action_id"], "action_timestamp": key["timestamp"],
              "action_type": item["action_type"], "success": item.get("success", True),
              "outcome": {}, "resource_result": item.get("resource_result", {}),
              "cost_impact_measured": False}
    response = events.put_events(Entries=[{"Source": "costguard.autonomous.executor",
        "DetailType": "ActionCompleted", "Detail": encode(detail), "EventBusName": EVENT_BUS_NAME}])
    if response.get("FailedEntryCount", 0):
        raise RuntimeError("Completion event was not accepted")
    update(key, completion_published=True)


def execute(key, item, state):
    parameters = item["parameters"]
    kind = item["action_type"]
    if kind == "schedule":
        names = ["cg-" + token(item["action_id"]) + "-scheduledstart",
                 "cg-" + token(item["action_id"]) + "-scheduledstop"]
        state["schedules"] = names
        save_snapshot(state)
        # Stop is configured first: do not start a workload without a stop timer.
        schedule_callback(item, "ScheduledStop", datetime.fromisoformat(parameters["window_end"].replace("Z", "+00:00")))
        schedule_callback(item, "ScheduledStart", datetime.fromisoformat(parameters["window_start"].replace("Z", "+00:00")))
        update(key, status="scheduled", resource_result={"schedule_names": names})
    elif kind == "right_sizing":
        set_instance_state(state["instance_id"], "stopped")
        ec2.modify_instance_attribute(InstanceId=state["instance_id"], InstanceType={"Value": parameters["new_instance_type"]})
        set_instance_state(state["instance_id"], state["original_state"])
        update(key, status="completed", success=True, resource_result={"instance_id": state["instance_id"]})
        release_resource(item)
    else:
        # Cleanup is installed before RunInstances; retrying uses the same token.
        if "cleanup_at" not in state:
            state["cleanup_at"] = (utcnow() + timedelta(minutes=int(parameters["max_runtime_minutes"]))).isoformat()
            state["schedules"] = ["cg-" + token(item["action_id"]) + "-replacementexpired"]
            save_snapshot(state)
        if not state.get("replacement_id") and datetime.fromisoformat(state["cleanup_at"]) <= utcnow() + timedelta(minutes=1):
            raise ValueError("Replacement launch deadline has elapsed; rollback the action")
        schedule_callback(item, "ReplacementExpired", datetime.fromisoformat(state["cleanup_at"]))
        args = {"LaunchTemplate": {"LaunchTemplateId": parameters["launch_template_id"],
                                   "Version": str(parameters["launch_template_version"])},
                "MinCount": 1, "MaxCount": 1, "ClientToken": token(item["action_id"]),
                "TagSpecifications": [{"ResourceType": "instance", "Tags": [
                    {"Key": "CostGuardManaged", "Value": "true"},
                    {"Key": "CostGuardActionId", "Value": item["action_id"]}]}]}
        if kind == "spot_migration":
            args["InstanceMarketOptions"] = {"MarketType": "spot", "SpotOptions": {"SpotInstanceType": "one-time"}}
        if not state.get("replacement_id"):
            result = ec2.run_instances(**args)
            state["replacement_id"] = result["Instances"][0]["InstanceId"]
            save_snapshot(state)
        resource_result = {"instance_id": state["replacement_id"], "operation": "instance_provisioned"}
        if parameters.get("training"):
            from autonomous.training_adapter import resume
            ec2.get_waiter("instance_running").wait(InstanceIds=[state["replacement_id"]],
                                                    WaiterConfig={"Delay": 5, "MaxAttempts": 60})
            resource_result["training"] = resume(item, state["replacement_id"], state, save_snapshot)
            resource_result["operation"] = "training_progress_verified"
        update(key, status="completed", success=True, resource_result=resource_result)


def owned_replacements(item):
    # Recover a launch even if Lambda died before storing the instance ID.
    query = {"Filters": [{"Name": "tag:CostGuardActionId", "Values": [item["action_id"]]}]}
    owned = []
    while True:
        response = ec2.describe_instances(**query)
        owned.extend(obj for reservation in response["Reservations"] for obj in reservation["Instances"]
                     if obj.get("ClientToken") == token(item["action_id"]))
        if not response.get("NextToken"):
            return owned
        query["NextToken"] = response["NextToken"]


def rollback(key, item, state):
    if item["action_type"] in ("schedule", "right_sizing"):
        resource_lock(item)
        current = instance(state["instance_id"])
        if item["status"] == "completed":
            expected_type = (item["parameters"]["new_instance_type"] if item["action_type"] == "right_sizing"
                             else state["original_type"])
            if current["InstanceType"] != expected_type or current["State"]["Name"] != state["original_state"]:
                release_resource(item)
                raise ValueError("Resource changed after completion; refusing to overwrite newer state")
        update(key, status="rolling_back")
        for name in state.get("schedules", []):
            delete_callback(name)
        set_instance_state(state["instance_id"], "stopped")
        if item["action_type"] == "right_sizing":
            ec2.modify_instance_attribute(InstanceId=state["instance_id"], InstanceType={"Value": state["original_type"]})
        set_instance_state(state["instance_id"], state["original_state"])
    else:
        update(key, status="rolling_back")
        for name in state.get("schedules", []):
            delete_callback(name)
        if state.get("training_command_id"):
            from autonomous.training_adapter import cancel
            cancel(state, state["replacement_id"])
        for obj in owned_replacements(item):
            if not managed(obj.get("Tags", [])):
                raise ValueError("Replacement is protected; rollback refused")
            if obj["State"]["Name"] != "terminated":
                ec2.terminate_instances(InstanceIds=[obj["InstanceId"]])
                ec2.get_waiter("instance_terminated").wait(InstanceIds=[obj["InstanceId"]], WaiterConfig={"Delay": 5, "MaxAttempts": 100})
    release_resource(item)
    update(key, status="rolled_back", rolled_back_at=utcnow().isoformat())


def handler(event, context):
    if (os.environ.get("DRY_RUN_MODE", "true").lower() == "true"
            or os.environ.get("EXECUTION_ENABLED", "false").lower() != "true"):
        return {"statusCode": 200, "status": "dry_run"}
    phase = event.get("detail-type")
    required_source = ("costguard.autonomous.schedule" if phase in
                       ("ScheduledStart", "ScheduledStop", "ReplacementExpired") else "costguard.autonomous.safetyguard")
    if event.get("source") != required_source or phase not in (
            "ExecuteAction", "ExecuteRollback", "ScheduledStart", "ScheduledStop", "ReplacementExpired"):
        raise ValueError("Invalid executor event source or type")
    key, item = get_record(event["detail"])
    if item.get("dry_run") or item.get("approval_decision") != "approved":
        raise ValueError("Action is not approved for execution")
    if item["status"] == "rolled_back":
        return {"statusCode": 200, "status": "rolled_back"}
    if phase == "ExecuteAction" and item["status"] == "completed":
        completion(key, item)
        return {"statusCode": 200, "status": "completed"}
    lease_token = str(uuid.uuid4())
    now = int(time.time())
    action_history_table.update_item(Key=key,
        UpdateExpression="SET lease_until = :until, lease_token = :token",
        ConditionExpression="attribute_not_exists(lease_until) OR lease_until < :now",
        ExpressionAttributeValues={":until": now + 910, ":token": lease_token, ":now": now})
    try:
        # Re-read after the lease to reject stale deliveries and racing rollbacks.
        key, item = get_record(event["detail"])
        rollback_key = {"rollback_id": "execution-" + token(item["action_id"]), "created_at": key["timestamp"]}
        state = rollback_table.get_item(Key=rollback_key, ConsistentRead=True).get("Item")
        if item["status"] == "rolled_back":
            return {"statusCode": 200, "status": "rolled_back"}
        if phase == "ExecuteRollback":
            if not state:
                raise ValueError("No persisted pre-action state; rollback cannot claim restoration")
            rollback(key, item, state)
        elif phase == "ExecuteAction":
            if item["status"] not in ("approved", "execution_failed"):
                return {"statusCode": 200, "status": item["status"]}
            if not state and int(item.get("approval_expires_at", 0)) <= int(time.time()):
                raise ValueError("Approval expired before execution started")
            cost = validate_parameters(item["action_type"], item["parameters"])
            check_budget(cost)
            state = snapshot(key, item)
            execute(key, item, state)
        elif not state:
            raise ValueError("Scheduled action has no recovery state")
        elif phase == "ScheduledStart" and item["status"] in ("scheduled", "running"):
            if utcnow() < datetime.fromisoformat(item["parameters"]["window_start"].replace("Z", "+00:00")):
                raise RuntimeError("Scheduled start arrived before its window")
            if utcnow() >= datetime.fromisoformat(item["parameters"]["window_end"].replace("Z", "+00:00")):
                raise ValueError("Optimization window has ended")
            check_budget(validate_parameters_for_start(item))
            update(key, start_attempted=True)
            set_instance_state(state["instance_id"], "running")
            update(key, status="running")
        elif phase == "ScheduledStop" and item["status"] in ("scheduled", "running", "execution_failed"):
            if utcnow() < datetime.fromisoformat(item["parameters"]["window_end"].replace("Z", "+00:00")):
                raise RuntimeError("Scheduled stop arrived before its window ended")
            set_instance_state(state["instance_id"], state["original_state"])
            update(key, status="completed", success=bool(item.get("start_attempted")))
            release_resource(item)
        elif phase == "ReplacementExpired":
            # Expiry reverses only the replacement owned by this action.
            if utcnow() < datetime.fromisoformat(state["cleanup_at"]):
                raise RuntimeError("Replacement expiry arrived before its deadline")
            rollback(key, item, state)
        key, latest = get_record(event["detail"])
        if latest["status"] == "completed":
            completion(key, latest)
        return {"statusCode": 200, "status": latest["status"]}
    except Exception as error:
        # Preserve completed status when publication failed so retries only resend.
        latest = action_history_table.get_item(Key=key, ConsistentRead=True).get("Item", {})
        if phase == "ExecuteAction" and latest.get("status") != "completed":
            saved = rollback_table.get_item(Key=rollback_key, ConsistentRead=True).get("Item")
            if not saved:
                # No snapshot means no resource mutation was authorized. Release
                # any lock taken while validating the target, not another owner.
                release_resource(item)
            update(key, status="execution_failed", execution_error=str(error))
        raise  # EventBridge/Lambda must retry failures rather than accept a 500 body.
    finally:
        action_history_table.update_item(Key=key, UpdateExpression="REMOVE lease_until, lease_token",
            ConditionExpression="lease_token = :token", ExpressionAttributeValues={":token": lease_token})


def validate_parameters_for_start(item):
    parameters = item["parameters"]
    start = datetime.fromisoformat(parameters["window_start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(parameters["window_end"].replace("Z", "+00:00"))
    return Decimal(str(parameters["max_hourly_cost"])) * Decimal(str((end-start).total_seconds()/3600))
