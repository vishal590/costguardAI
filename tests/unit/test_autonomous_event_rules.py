"""Synthesize event rules locally; no AWS calls or Lambda asset packaging."""
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aws_cdk import App, aws_lambda as lambda_
from aws_cdk.assertions import Template

from infrastructure.autonomous_stack import AutonomousStack


def test_rules_cover_worker_and_api_producers():
    with TemporaryDirectory(prefix="costguard-cdk-test-") as outdir:
        app = App(outdir=outdir)
        with patch.object(lambda_.Code, "from_asset", return_value=lambda_.Code.from_inline("def handler(event, context): pass")):
            stack = AutonomousStack(app, "EventRoutingTest")
        template = Template.from_stack(stack).to_json()
    resources = template["Resources"]
    rules = {resource["Properties"]["Name"]: resource["Properties"]
             for resource in resources.values() if resource["Type"] == "AWS::Events::Rule"}
    expected = [
        ("costguard-schedule-recommendation-approval", "costguard.autonomous.scheduler", "ScheduleRecommendation", "autonomous.safety_guard.handler"),
        ("costguard-approved-action-execution", "costguard.autonomous.safetyguard", "ExecuteAction", "autonomous.action_executor.handler"),
        ("costguard-approved-action-execution", "costguard.autonomous.safetyguard", "ExecuteRollback", "autonomous.action_executor.handler"),
        ("costguard-learning-engine-action-completed", "costguard.autonomous.executor", "ActionCompleted", "autonomous.learning_engine.handler"),
        ("costguard-safety-guard-api-requests", "costguard.autonomous.api", "ActionApproved", "autonomous.safety_guard.handler"),
        ("costguard-safety-guard-api-requests", "costguard.autonomous.api", "ActionRejected", "autonomous.safety_guard.handler"),
        ("costguard-safety-guard-api-requests", "costguard.autonomous.api", "RollbackRequested", "autonomous.safety_guard.handler"),
        ("costguard-safety-guard-action-request", "costguard.autonomous.spotmanager", "ActionRequest", "autonomous.safety_guard.handler"),
        ("costguard-spot-manager-interruption", "costguard.autonomous.demo", "SpotInterruptionDetected", "autonomous.spot_manager.handler"),
        ("costguard-learning-engine-action-completed", "costguard.autonomous.spotmanager", "ActionCompleted", "autonomous.learning_engine.handler"),
        ("costguard-learning-engine-action-completed", "costguard.autonomous.rightsizer", "ActionCompleted", "autonomous.learning_engine.handler"),
    ]
    for rule_name, source, detail_type, handler in expected:
        rule = rules[rule_name]
        assert source in rule["EventPattern"]["source"]
        assert detail_type in rule["EventPattern"]["detail-type"]
        target_id = rule["Targets"][0]["Arn"]["Fn::GetAtt"][0]
        assert resources[target_id]["Properties"]["Handler"] == handler
        assert "EventBusName" in rule
        assert any(resource["Type"] == "AWS::Lambda::Permission"
                   and resource["Properties"].get("Principal") == "events.amazonaws.com"
                   and resource["Properties"].get("FunctionName") == {"Fn::GetAtt": [target_id, "Arn"]}
                   for resource in resources.values())
    # Safety Guard emits its own decisions; accepting those here would feed back.
    assert rules["costguard-safety-guard-api-requests"]["EventPattern"]["source"] == ["costguard.autonomous.api"]
    for name in ("costguard-safety-guard-action-request", "costguard-spot-manager-interruption", "costguard-learning-engine-action-completed"):
        assert "costguard.autonomous" in rules[name]["EventPattern"]["source"]
    archive = next(resource["Properties"] for resource in resources.values() if resource["Type"] == "AWS::Events::Archive")
    assert "costguard.autonomous.api" in archive["EventPattern"]["source"]
    assert "costguard.autonomous.demo" in archive["EventPattern"]["source"]

    assert template["Parameters"]["EnableAutonomousExecution"]["Default"] == "false"
    function = next(obj["Properties"] for obj in resources.values() if obj["Type"] == "AWS::Lambda::Function" and obj["Properties"]["Handler"] == "autonomous.action_executor.handler")
    environment = function["Environment"]["Variables"]
    assert environment["EXECUTION_ENABLED"] == {"Ref": "EnableAutonomousExecution"}
    assert ":function:CostGuard-Action-Executor" in str(environment["EXECUTOR_ARN"])
    assert any(obj["Type"] == "AWS::SecretsManager::Secret" for obj in resources.values())
    assert any(obj["Type"] == "AWS::Scheduler::ScheduleGroup" for obj in resources.values())

    document = next(obj["Properties"] for obj in resources.values() if obj["Type"] == "AWS::SSM::Document")
    assert document["Content"]["mainSteps"][0]["name"] == "train"
    command = document["Content"]["mainSteps"][0]["inputs"]["runCommand"][0]
    assert "autonomous.training_worker" in command
    assert "/opt/costguard/venv/bin/python" in command
    assert document["Content"]["parameters"]["request"]["allowedPattern"] == "^[A-Za-z0-9+/=]+$"
    assert "TRAINING_DOCUMENT" in environment and "TRAINING_INSTANCE_PROFILE_ARN" in environment
    assert any(obj["Type"] == "AWS::IAM::InstanceProfile" for obj in resources.values())
