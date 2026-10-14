"""Resource-level workflow tests: AWS resources are provided by Moto only."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from autonomous import action_executor as executor
from autonomous import safety_guard as guard
from autonomous import gpu_scheduler as gpu
from autonomous import spot_manager as spot
from autonomous import learning_engine as learning


@pytest.fixture
def workflow(monkeypatch):
    monkeypatch.setenv("DRY_RUN_MODE", "false")
    monkeypatch.setenv("EXECUTION_ENABLED", "true")
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        def table(name, partition, sort, indexes=None):
            args = dict(TableName=name, BillingMode="PAY_PER_REQUEST",
                KeySchema=[{"AttributeName": partition, "KeyType": "HASH"}, {"AttributeName": sort, "KeyType": "RANGE"}],
                AttributeDefinitions=[{"AttributeName": field, "AttributeType": "S"} for field in (partition, sort)])
            if indexes:
                args["AttributeDefinitions"] += [{"AttributeName": field, "AttributeType": "S"} for field in indexes]
                args["GlobalSecondaryIndexes"] = [{"IndexName": field.replace("_", "-") + "-index",
                    "KeySchema": [{"AttributeName": field, "KeyType": "HASH"}, {"AttributeName": sort, "KeyType": "RANGE"}],
                    "Projection": {"ProjectionType": "ALL"}} for field in indexes]
            return db.create_table(**args)
        history = table("execution-history", "action_id", "timestamp", ["action_type", "status"])
        recovery = table("execution-recovery", "rollback_id", "created_at")
        for module in (executor, guard, gpu, learning):
            monkeypatch.setattr(module, "action_history_table", history)
        monkeypatch.setattr(executor, "rollback_table", recovery)
        monkeypatch.setattr(executor, "REGION", "us-east-1")
        cloud = boto3.client("ec2", region_name="us-east-1")
        monkeypatch.setattr(executor, "ec2", cloud)
        monkeypatch.setattr(guard, "APPROVAL_SNS_TOPIC", "")
        monkeypatch.setattr(guard, "APPROVAL_SECRET_KEY", "test-secret")
        monkeypatch.setattr(guard, "check_budget_limit", lambda: True)
        monkeypatch.setattr(guard, "log_action", MagicMock())
        monkeypatch.setattr(learning, "get_metrics_publisher", MagicMock())
        monkeypatch.setattr(executor, "EXECUTOR_ARN", "arn:aws:lambda:us-east-1:123456789012:function:executor")
        monkeypatch.setattr(executor, "SCHEDULE_ROLE_ARN", "arn:aws:iam::123456789012:role/scheduler")
        scheduler = MagicMock()
        monkeypatch.setattr(executor, "scheduler", scheduler)
        billing = MagicMock()
        billing.get_cost_and_usage.return_value = {"ResultsByTime": [{"Total": {"UnblendedCost": {"Amount": "0", "Unit": "USD"}}}]}
        monkeypatch.setattr(executor, "ce", billing)
        queue = []
        def publish(Entries):
            for entry in Entries:
                queue.append({"source": entry["Source"], "detail-type": entry["DetailType"], "detail": json.loads(entry["Detail"])})
            return {"FailedEntryCount": 0}
        bus = MagicMock()
        bus.put_events.side_effect = publish
        for module, name in ((guard, "events_client"), (gpu, "events_client"), (spot, "events_client"), (executor, "events")):
            monkeypatch.setattr(module, name, bus)
        yield history, recovery, cloud, scheduler, queue, billing


def stopped_instance(cloud, opted_in=True):
    obj = cloud.run_instances(ImageId="ami-12345678", InstanceType="t3.small", MinCount=1, MaxCount=1)["Instances"][0]
    instance_id = obj["InstanceId"]
    if opted_in:
        cloud.create_tags(Resources=[instance_id], Tags=[{"Key": "CostGuardManaged", "Value": "true"}])
    cloud.stop_instances(InstanceIds=[instance_id])
    return instance_id


def parameters(instance_id):
    return {"region": "us-east-1", "instance_id": instance_id, "max_hourly_cost": "0.1",
            "window_start": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "window_end": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()}


def approved(workflow, params, kind="schedule"):
    history, _, _, _, queue, _ = workflow
    request = {"source": "costguard.autonomous.spotmanager", "detail-type": "ActionRequest", "detail": {
        "action_id": "action-1", "request_id": "request-1", "action_type": kind,
        "parameters": params, "confidence_score": 0.9, "expected_cost_impact": 0,
        "timestamp": "2026-10-03T00:00:00+00:00", "approval_required": True}}
    assert guard.handler(request, None)["statusCode"] == 202
    records = history.query(KeyConditionExpression=boto3.dynamodb.conditions.Key("action_id").eq("action-1"))["Items"]
    item = next(obj for obj in records if obj.get("approval_request_id"))
    decision = {"source": "costguard.autonomous.api", "detail-type": "ActionApproved", "detail": {
        "request_id": "request-1", "action_id": "action-1", "approved": True, "signature": item["approval_signature"]}}
    assert guard.handler(decision, None)["statusCode"] == 200
    return queue[-1], {"action_id": "action-1", "timestamp": item["timestamp"]}, decision


def callback(event, phase):
    return {"source": "costguard.autonomous.schedule", "detail-type": phase, "detail": event["detail"]}


def run_callback(event, phase):
    _, item = executor.get_record(event["detail"])
    if phase == "ReplacementExpired":
        recovery_key = {"rollback_id": "execution-" + executor.token(item["action_id"]), "created_at": item["timestamp"]}
        at = executor.rollback_table.get_item(Key=recovery_key)["Item"]["cleanup_at"]
    else:
        at = item["parameters"]["window_start" if phase == "ScheduledStart" else "window_end"]
    with patch.object(executor, "utcnow", return_value=datetime.fromisoformat(at) + timedelta(seconds=1)):
        return executor.handler(callback(event, phase), None)


def state(cloud, instance_id):
    return cloud.describe_instances(InstanceIds=[instance_id])["Reservations"][0]["Instances"][0]


def test_schedule_recommendation_approval_execution_and_learning(workflow):
    history, _, cloud, scheduler, queue, _ = workflow
    instance_id = stopped_instance(cloud)
    params = parameters(instance_id)
    window = gpu.OptimizationWindow(datetime.fromisoformat(params["window_start"]), datetime.fromisoformat(params["window_end"]), .1, .9, "us-east-1", "g4dn.xlarge")
    recommendation = gpu.ScheduleRecommendation("recommendation-1", window, .9, 30, 1)
    gpu.publish_recommendation_event(recommendation, workload=params)
    assert guard.handler(queue[-1], None)["statusCode"] == 202
    record = history.scan()["Items"][0]
    decision = {"source": "costguard.autonomous.api", "detail-type": "ActionApproved", "detail": {
        "request_id": record["approval_request_id"], "action_id": record["action_id"],
        "signature": record["approval_signature"], "approved": True}}
    assert guard.handler(decision, None)["statusCode"] == 200
    event = queue[-1]
    assert executor.handler(event, None)["status"] == "scheduled"
    assert scheduler.create_schedule.call_count == 2
    assert state(cloud, instance_id)["State"]["Name"] == "stopped"
    assert run_callback(event, "ScheduledStart")["status"] == "running"
    assert state(cloud, instance_id)["State"]["Name"] == "running"
    assert run_callback(event, "ScheduledStop")["status"] == "completed"
    assert state(cloud, instance_id)["State"]["Name"] == "stopped"
    complete = queue[-1]
    assert complete["detail-type"] == "ActionCompleted"
    assert complete["detail"]["cost_impact_measured"] is False
    count = history.item_count
    assert learning.handler(complete, None)["statusCode"] == 200
    assert learning.handler(complete, None)["statusCode"] == 200
    assert history.item_count == count
    key = {"action_id": record["action_id"], "timestamp": record["timestamp"]}
    item = history.get_item(Key=key)["Item"]
    assert item["learning_recorded"] is True
    assert "actual_cost_impact" not in item
    executor.handler(event, None)
    assert scheduler.create_schedule.call_count == 2


def test_rollback_running_schedule_restores_instance(workflow):
    history, _, cloud, scheduler, queue, _ = workflow
    instance_id = stopped_instance(cloud)
    event, key, decision = approved(workflow, parameters(instance_id))
    executor.handler(event, None)
    run_callback(event, "ScheduledStart")
    assert guard.execute_rollback(key["action_id"])
    rollback_event = queue[-1]
    assert executor.handler(rollback_event, None)["status"] == "rolled_back"
    assert state(cloud, instance_id)["State"]["Name"] == "stopped"
    assert scheduler.delete_schedule.call_count == 2
    assert run_callback(event, "ScheduledStart")["status"] == "rolled_back"
    assert guard.handler(decision, None)["statusCode"] == 200
    assert executor.handler(queue[-1], None)["status"] == "rolled_back"
    assert history.get_item(Key=key)["Item"]["status"] == "rolled_back"


def test_right_sizing_and_rollback_restore_type_and_running_state(workflow):
    _, _, cloud, _, queue, _ = workflow
    instance_id = stopped_instance(cloud)
    cloud.start_instances(InstanceIds=[instance_id])
    params = {"instance_id": instance_id, "new_instance_type": "t3.micro", "region": "us-east-1", "max_hourly_cost": "0.1"}
    event, _, _ = approved(workflow, params, "right_sizing")
    assert executor.handler(event, None)["status"] == "completed"
    assert state(cloud, instance_id)["InstanceType"] == "t3.micro"
    assert state(cloud, instance_id)["State"]["Name"] == "running"
    guard.execute_rollback("action-1")
    assert executor.handler(queue[-1], None)["status"] == "rolled_back"
    assert state(cloud, instance_id)["InstanceType"] == "t3.small"
    assert state(cloud, instance_id)["State"]["Name"] == "running"


@pytest.mark.parametrize("kind", ["spot_migration", "ondemand_fallback"])
def test_real_replacement_is_owned_idempotent_and_reversible(workflow, kind):
    _, _, cloud, scheduler, queue, _ = workflow
    template = cloud.create_launch_template(LaunchTemplateName="training-test", LaunchTemplateData={"ImageId": "ami-12345678", "InstanceType": "t3.micro"},
        TagSpecifications=[{"ResourceType": "launch-template", "Tags": [{"Key": "CostGuardManaged", "Value": "true"}]}])["LaunchTemplate"]
    params = {"region": "us-east-1", "launch_template_id": template["LaunchTemplateId"], "launch_template_version": "1",
              "max_runtime_minutes": 10, "max_hourly_cost": "0.1"}
    event, _, _ = approved(workflow, params, kind)
    assert executor.handler(event, None)["status"] == "completed"
    replacements = executor.owned_replacements({"action_id": "action-1"})
    assert len(replacements) == 1
    instance_id = replacements[0]["InstanceId"]
    assert instance_id.startswith("i-") and not instance_id.startswith("i-spot-")
    executor.handler(event, None)
    assert len(executor.owned_replacements({"action_id": "action-1"})) == 1
    guard.execute_rollback("action-1")
    assert executor.handler(queue[-1], None)["status"] == "rolled_back"
    assert state(cloud, instance_id)["State"]["Name"] == "terminated"
    assert scheduler.create_schedule.call_count == 1


@pytest.mark.parametrize("reason", ["unmanaged", "protected", "budget", "budget_unavailable", "disabled"])
def test_safety_failure_never_starts_resource(workflow, monkeypatch, reason):
    history, recovery, cloud, scheduler, _, billing = workflow
    instance_id = stopped_instance(cloud, opted_in=reason != "unmanaged")
    if reason == "protected":
        cloud.create_tags(Resources=[instance_id], Tags=[{"Key": "CostGuardProtected", "Value": "true"}])
    event, key, _ = approved(workflow, parameters(instance_id))
    if reason == "budget":
        billing.get_cost_and_usage.return_value["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"] = "5"
    if reason == "budget_unavailable":
        billing.get_cost_and_usage.side_effect = RuntimeError("Unavailable")
    if reason == "disabled":
        monkeypatch.setenv("EXECUTION_ENABLED", "false")
        assert executor.handler(event, None)["status"] == "dry_run"
    else:
        with pytest.raises((ValueError, RuntimeError)):
            executor.handler(event, None)
        assert history.get_item(Key=key)["Item"]["status"] == "execution_failed"
    assert state(cloud, instance_id)["State"]["Name"] == "stopped"
    scheduler.create_schedule.assert_not_called()
    assert "Item" not in recovery.get_item(Key={"rollback_id": "resource-" + instance_id, "created_at": "lock"})


def test_failed_completion_submission_retries_without_resource_execution(workflow):
    history, _, cloud, scheduler, queue, _ = workflow
    instance_id = stopped_instance(cloud)
    event, key, _ = approved(workflow, parameters(instance_id))
    executor.handler(event, None)
    run_callback(event, "ScheduledStart")
    original = executor.events.put_events.side_effect
    executor.events.put_events.side_effect = None
    executor.events.put_events.return_value = {"FailedEntryCount": 1}
    with pytest.raises(RuntimeError):
        run_callback(event, "ScheduledStop")
    assert history.get_item(Key=key)["Item"]["status"] == "completed"
    executor.events.put_events.side_effect = original
    executor.handler(event, None)
    assert scheduler.create_schedule.call_count == 2
    assert queue[-1]["detail-type"] == "ActionCompleted"


def test_spot_request_is_pending_and_has_full_contract(workflow, monkeypatch):
    _, _, _, _, queue, _ = workflow
    monkeypatch.setattr(spot, "check_spot_availability", lambda *args: False)
    params = {"region": "us-east-1", "launch_template_id": "lt-template", "launch_template_version": "1",
              "max_runtime_minutes": 10, "max_hourly_cost": "0.1"}
    event = {"id": "interrupt-1", "region": "us-east-1", "detail": {
        "instance_id": "i-source", "training_job_id": "job-1", "parameters": params}}
    response = spot.handler(event, None)
    assert response["statusCode"] == 202
    assert json.loads(response["body"])["status"] == "pending_approval"
    request = queue[-1]
    assert request["detail"]["action_type"] == "ondemand_fallback"
    assert request["detail"]["approval_required"] is True
    assert request["detail"]["parameters"]["source_instance_id"] == "i-source"
    assert guard.handler(request, None)["statusCode"] == 202


def test_pending_or_rejected_action_cannot_execute(workflow):
    history, _, cloud, scheduler, _, _ = workflow
    instance_id = stopped_instance(cloud)
    event, key, _ = approved(workflow, parameters(instance_id))
    history.update_item(Key=key, UpdateExpression="SET approval_decision = :rejected",
                        ExpressionAttributeValues={":rejected": "rejected"})
    with pytest.raises(ValueError, match="not approved"):
        executor.handler(event, None)
    scheduler.create_schedule.assert_not_called()
    assert state(cloud, instance_id)["State"]["Name"] == "stopped"


def test_expired_execution_approval_cannot_start(workflow):
    history, _, cloud, scheduler, _, _ = workflow
    event, key, _ = approved(workflow, parameters(stopped_instance(cloud)))
    history.update_item(Key=key, UpdateExpression="SET approval_expires_at = :expired",
                        ExpressionAttributeValues={":expired": 0})
    with pytest.raises(ValueError, match="Approval expired"):
        executor.handler(event, None)
    scheduler.create_schedule.assert_not_called()


def test_conflicting_actions_are_locked_until_restoration(workflow):
    history, _, cloud, scheduler, queue, _ = workflow
    event, key, _ = approved(workflow, parameters(stopped_instance(cloud)))
    executor.handler(event, None)
    item = history.get_item(Key=key)["Item"]
    second = dict(item, action_id="action-2", status="approved")
    history.put_item(Item=second)
    next_event = {"source": event["source"], "detail-type": "ExecuteAction",
                  "detail": {"action_id": "action-2", "action_timestamp": key["timestamp"]}}
    with pytest.raises(Exception, match="ConditionalCheckFailed"):
        executor.handler(next_event, None)
    assert scheduler.create_schedule.call_count == 2
    guard.execute_rollback("action-1")
    executor.handler(queue[-1], None)
    assert executor.handler(next_event, None)["status"] == "scheduled"


def test_busy_action_lease_cannot_duplicate_execution(workflow):
    import time
    history, _, cloud, scheduler, _, _ = workflow
    event, key, _ = approved(workflow, parameters(stopped_instance(cloud)))
    history.update_item(Key=key, UpdateExpression="SET lease_until = :future",
                        ExpressionAttributeValues={":future": int(time.time()) + 500})
    with pytest.raises(Exception, match="ConditionalCheckFailed"):
        executor.handler(event, None)
    scheduler.create_schedule.assert_not_called()


def test_replacement_expiry_terminates_only_action_owned_instance(workflow):
    _, _, cloud, _, queue, _ = workflow
    original = stopped_instance(cloud)
    template = cloud.create_launch_template(LaunchTemplateName="expiry-test", LaunchTemplateData={"ImageId": "ami-12345678", "InstanceType": "t3.micro"},
        TagSpecifications=[{"ResourceType": "launch-template", "Tags": [{"Key": "CostGuardManaged", "Value": "true"}]}])["LaunchTemplate"]
    params = {"region": "us-east-1", "launch_template_id": template["LaunchTemplateId"], "launch_template_version": "1",
              "max_runtime_minutes": 10, "max_hourly_cost": "0.1"}
    event, _, _ = approved(workflow, params, "ondemand_fallback")
    executor.handler(event, None)
    replacement = executor.owned_replacements({"action_id": "action-1"})[0]["InstanceId"]
    run_callback(event, "ReplacementExpired")
    assert state(cloud, replacement)["State"]["Name"] == "terminated"
    assert state(cloud, original)["State"]["Name"] == "stopped"


def test_rollback_retry_recovers_after_partial_failure(workflow):
    _, _, cloud, _, queue, _ = workflow
    instance_id = stopped_instance(cloud)
    cloud.start_instances(InstanceIds=[instance_id])
    params = {"instance_id": instance_id, "new_instance_type": "t3.micro", "region": "us-east-1", "max_hourly_cost": "0.1"}
    event, _, _ = approved(workflow, params, "right_sizing")
    executor.handler(event, None)
    guard.execute_rollback("action-1")
    restore = queue[-1]
    with patch.object(cloud, "modify_instance_attribute", side_effect=RuntimeError("Temporary failure")):
        with pytest.raises(RuntimeError):
            executor.handler(restore, None)
    assert executor.handler(restore, None)["status"] == "rolled_back"
    assert state(cloud, instance_id)["InstanceType"] == "t3.small"
    assert state(cloud, instance_id)["State"]["Name"] == "running"


def test_request_replay_preserves_signed_decision(workflow):
    history, _, cloud, scheduler, queue, _ = workflow
    event, key, decision = approved(workflow, parameters(stopped_instance(cloud)))
    before = history.get_item(Key=key)["Item"]
    action = guard.ActionRequest("request-1", "schedule", "action-1", before["parameters"], .9, 0, True)
    action.timestamp = datetime.fromisoformat(key["timestamp"])
    guard.request_approval(action)
    assert history.get_item(Key=key)["Item"]["status"] == "approved"
    assert guard.handler(decision, None)["statusCode"] == 200
    executor.handler(queue[-1], None)
    assert scheduler.create_schedule.call_count == 2


def test_schedule_callbacks_cannot_run_before_the_window(workflow):
    _, _, cloud, _, _, _ = workflow
    instance_id = stopped_instance(cloud)
    event, _, _ = approved(workflow, parameters(instance_id))
    executor.handler(event, None)
    with pytest.raises(RuntimeError, match="before its window"):
        executor.handler(callback(event, "ScheduledStart"), None)
    assert state(cloud, instance_id)["State"]["Name"] == "stopped"


@pytest.mark.parametrize("mode", ["success", "worker_error", "invalid_body", "function_error"])
def test_analysis_api_forwards_workload_and_worker_status(monkeypatch, mode):
    from io import BytesIO
    from src import autonomous_handler as api
    client = MagicMock()
    payload = {"days": 7, "dry_run": True, "workload": {"instance_id": "i-target", "max_hourly_cost": "0.1"}}
    worker_result = {"statusCode": 400 if mode == "worker_error" else 200,
                     "body": json.dumps({"recommendations": []})}
    client.invoke.return_value = {"Payload": BytesIO(json.dumps(worker_result).encode())}
    if mode == "function_error":
        client.invoke.return_value["FunctionError"] = "Unhandled"
    if mode == "invalid_body":
        payload["dry_run"] = "false"
    monkeypatch.setattr(api, "lambda_client", client)
    monkeypatch.setattr(api, "GPU_SCHEDULER_FUNCTION", "scheduler")
    response = api.handle_schedule_analysis({"body": json.dumps(payload)})
    assert response["statusCode"] == (500 if mode == "function_error" else 400 if mode in ("worker_error", "invalid_body") else 200)
    if mode == "invalid_body":
        client.invoke.assert_not_called()
    else:
        forwarded = json.loads(client.invoke.call_args.kwargs["Payload"])
        assert forwarded["workload"] == payload["workload"] and forwarded["dry_run"] is True


def test_numeric_nested_parameters_survive_approval_storage(workflow):
    history, _, cloud, _, _, _ = workflow
    params = parameters(stopped_instance(cloud))
    params["max_hourly_cost"] = 0.1
    event, key, _ = approved(workflow, params)
    assert str(history.get_item(Key=key)["Item"]["parameters"]["max_hourly_cost"]) == "0.1"
    assert executor.handler(event, None)["status"] == "scheduled"


@pytest.mark.parametrize("proof", ["valid", "missing", "failed_command"])
def test_replacement_training_requires_real_progress(workflow, monkeypatch, proof):
    import base64
    from autonomous import training_worker as worker, training_adapter as adapter
    _, _, cloud, _, queue, _ = workflow
    s3 = boto3.client("s3", region_name="us-east-1")
    bucket = "training-executor-test"
    s3.create_bucket(Bucket=bucket)
    data = b"x,y\n0,1\n0.5,2\n1,3\n"
    state_data = worker.serialize({"schema_version": 1, "job_id": "job-1", "dataset_sha256": worker.digest(data),
        "weights": [.2,.3], "step": 7, "optimizer": {"kind": "sgd", "learning_rate": .01}})
    settings = {"kind": "linear_regression_sgd", "job_id": "job-1", "dataset_key": "training/job-1/data.csv",
        "checkpoint_key": "training/job-1/source.json", "checkpoint_sha256": worker.digest(state_data), "steps": 30, "learning_rate": .01}
    s3.put_object(Bucket=bucket,Key=settings["dataset_key"],Body=data)
    s3.put_object(Bucket=bucket,Key=settings["checkpoint_key"],Body=state_data)
    iam = boto3.client("iam")
    profile = iam.create_instance_profile(InstanceProfileName="training-test")["InstanceProfile"]["Arn"]
    monkeypatch.setenv("TRAINING_INSTANCE_PROFILE_ARN",profile)
    monkeypatch.setattr(adapter,"BUCKET",bucket)
    monkeypatch.setattr(adapter,"DOCUMENT","CostGuard-Training")
    monkeypatch.setattr(adapter,"s3",s3)
    commands = MagicMock()
    commands.describe_instance_information.return_value = {"InstanceInformationList": [{"PingStatus": "Online"}]}
    commands.get_command_invocation.return_value = {"Status": "Success" if proof != "failed_command" else "Failed", "ResponseCode": 0 if proof != "failed_command" else 1}
    def send(**kwargs):
        config = json.loads(base64.b64decode(kwargs["Parameters"]["request"][0]))
        if proof == "valid":
            worker.run(s3,config)
        return {"Command": {"CommandId": "command-1"}}
    commands.send_command.side_effect = send
    monkeypatch.setattr(adapter,"ssm",commands)
    template = cloud.create_launch_template(LaunchTemplateName="training-resume-test",LaunchTemplateData={
        "ImageId": "ami-12345678", "InstanceType": "t3.micro", "IamInstanceProfile": {"Arn": profile}},
        TagSpecifications=[{"ResourceType": "launch-template", "Tags": [{"Key": "CostGuardManaged", "Value": "true"}]}])["LaunchTemplate"]
    params = {"region": "us-east-1", "launch_template_id": template["LaunchTemplateId"], "launch_template_version": "1",
        "max_runtime_minutes": 15, "max_hourly_cost": "0.1", "training": settings}
    event,key,_ = approved(workflow,params,"ondemand_fallback")
    if proof == "valid":
        assert executor.handler(event,None)["status"] == "completed"
        result = executor.action_history_table.get_item(Key=key)["Item"]["resource_result"]
        assert result["operation"] == "training_progress_verified"
        assert result["training"]["restored_step"] == 7 and result["training"]["final_step"] == 37
        executor.handler(event,None)
        commands.send_command.assert_called_once()
    else:
        with pytest.raises(Exception):
            executor.handler(event,None)
        assert executor.action_history_table.get_item(Key=key)["Item"]["status"] == "execution_failed"
        assert not any(obj["detail-type"] == "ActionCompleted" for obj in queue)
    guard.execute_rollback("action-1")
    executor.handler(queue[-1],None)
    commands.cancel_command.assert_called_once()
