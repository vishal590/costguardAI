"""Run real optimizer steps against local Moto S3, including checkpoint resume."""
import json

import boto3
import pytest
from moto import mock_aws

from autonomous import training_worker as worker


@pytest.fixture
def training():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = "training-worker-test"
        s3.create_bucket(Bucket=bucket)
        data = b"x,y\n0,1\n0.5,2\n1,3\n"
        state = {"schema_version": 1, "job_id": "job-1", "dataset_sha256": worker.digest(data),
                 "optimizer": {"kind": "sgd", "learning_rate": .01}, "weights": [.2,.3], "step": 7}
        checkpoint = worker.serialize(state)
        config = {"kind": "linear_regression_sgd", "job_id": "job-1", "dataset_key": "training/job-1/data.csv",
                  "checkpoint_key": "training/job-1/source.json", "checkpoint_sha256": worker.digest(checkpoint),
                  "steps": 100, "learning_rate": .01}
        s3.put_object(Bucket=bucket, Key=config["dataset_key"], Body=data)
        s3.put_object(Bucket=bucket, Key=config["checkpoint_key"], Body=checkpoint)
        yield s3, bucket, config, state


def test_checkpoint_resume_performs_real_optimizer_steps(training):
    s3, bucket, training_config, initial = training
    config = worker.request(training_config, bucket, "action-1")
    result = worker.run(s3, config)
    assert result["restored_step"] == 7 and result["final_step"] == 107
    assert result["initial_weights"] == [.2,.3]
    final = json.loads(worker.read(s3, bucket, config["output_checkpoint_key"]))
    assert final["weights"] != initial["weights"] and final["optimizer"] == initial["optimizer"]
    initial_loss = sum((.2*x+.3-y)**2 for x,y in [(0,1),(.5,2),(1,3)])/3
    assert result["loss"] < initial_loss
    assert worker.run(s3, config) == result  # retries do not advance another 100 steps


def test_output_checkpoint_can_resume_on_another_action(training):
    s3, bucket, settings, _ = training
    first = worker.request(settings, bucket, "first")
    result = worker.run(s3, first)
    next_settings = dict(settings, checkpoint_key=first["output_checkpoint_key"],
                         checkpoint_sha256=result["output_checkpoint_sha256"], steps=30)
    second = worker.run(s3, worker.request(next_settings, bucket, "second"))
    assert second["restored_step"] == 107 and second["final_step"] == 137


@pytest.mark.parametrize("change", [
    {"checkpoint_sha256": "0"*64}, {"learning_rate": .1}, {"job_id": "wrong-job"},
    {"steps": 0}, {"steps": True}, {"kind": "unknown"},
    {"checkpoint_key": "training/job-1/../other/source.json"},
])
def test_invalid_or_mismatched_checkpoint_is_rejected(training, change):
    s3, bucket, settings, _ = training
    settings.update(change)
    with pytest.raises((ValueError, KeyError)):
        worker.run(s3, worker.request(settings, bucket, "action-1"))


def test_corrupted_result_does_not_report_success(training):
    s3, bucket, settings, state = training
    config = worker.request(settings, bucket, "action-1")
    worker.run(s3, config)
    result = json.loads(worker.read(s3,bucket,config["result_key"]))
    result["final_step"] = 7
    s3.put_object(Bucket=bucket,Key=config["result_key"],Body=worker.serialize(result))
    with pytest.raises(ValueError,match="does not prove"):
        worker.verify(s3,config,state)


def test_dataset_changes_invalidate_the_model_checkpoint(training):
    s3,bucket,settings,_ = training
    s3.put_object(Bucket=bucket,Key=settings["dataset_key"],Body=b"x,y\n1,100\n")
    with pytest.raises(ValueError,match="does not match"):
        worker.run(s3,worker.request(settings,bucket,"action-1"))


def test_preparation_tool_produces_a_runnable_checkpoint(training):
    from scripts.prepare_training_checkpoint import prepare
    s3,bucket,_,_ = training
    dataset = b"x,y\n0,1\n0.5,2\n1,3\n"
    checkpoint,settings = prepare(dataset,"prepared-job",.01,10)
    s3.put_object(Bucket=bucket,Key=settings["dataset_key"],Body=dataset)
    s3.put_object(Bucket=bucket,Key=settings["checkpoint_key"],Body=checkpoint)
    result = worker.run(s3,worker.request(settings,bucket,"prepared-action"))
    assert result["restored_step"] == 0 and result["final_step"] == 10


@pytest.mark.parametrize("valid", [True,False])
def test_interruption_api_forwards_training_contract(monkeypatch, valid):
    from unittest.mock import MagicMock
    from src import autonomous_handler as api
    monkeypatch.setenv("DEMO_MODE","true")
    bus=MagicMock();bus.put_events.return_value={"FailedEntryCount":0}
    monkeypatch.setattr(api,"events_client",bus)
    monkeypatch.setattr(api,"action_history_table",MagicMock())
    body={"instance_id":"i-original","training_job_id":"job-1","parameters":{
        "region":"us-east-1","launch_template_id":"lt-test","launch_template_version":"1",
        "max_runtime_minutes":15,"max_hourly_cost":"0.1","training":{
            "kind":"linear_regression_sgd","job_id":"job-1","dataset_key":"training/job-1/data.csv",
            "checkpoint_key":"training/job-1/source.json","checkpoint_sha256":"0"*64,"steps":10,"learning_rate":.01}}}
    if not valid:body["parameters"]["training"]["job_id"]="wrong-job"
    response=api.handle_demo_trigger_interruption({"body":json.dumps(body)})
    assert response["statusCode"] == (202 if valid else 400)
    if valid:
        payload=json.loads(bus.put_events.call_args.kwargs["Entries"][0]["Detail"])
        assert payload["parameters"]["training"]==body["parameters"]["training"]
        assert json.loads(response["body"])["status"]=="interruption_submitted"
    else:bus.put_events.assert_not_called()
