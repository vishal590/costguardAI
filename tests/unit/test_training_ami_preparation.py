"""Offline packaging, integrity and plan validation; no AWS clients."""
import importlib.util
import json
from pathlib import Path
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(relative):
    spec = importlib.util.spec_from_file_location(Path(relative).stem, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load("scripts/build_training_ami_bundle.py")
verify = load("scripts/ami/verify_runtime.py")
readiness = load("scripts/ami/check_readiness.py")


def test_deterministic_allowlist_and_resume(tmp_path):
    first, second = tmp_path / "first.tar.gz", tmp_path / "second.tar.gz"
    builder.build(first)
    builder.build(second)
    assert first.read_bytes() == second.read_bytes()
    extracted = tmp_path / "extracted"
    with tarfile.open(first) as archive:
        assert set(archive.getnames()) == set(builder.FILES) | {"manifest.json"}
        assert all(item.isfile() for item in archive.getmembers())
        archive.extractall(extracted, filter="data")
    assert verify.verify_manifest(extracted) == len(builder.FILES)
    result = verify.optimizer_self_test(extracted)
    assert result == {"restored_step": 7, "final_step": 37, "storage": "memory", "aws_calls": 0}
    with pytest.raises(FileExistsError):
        builder.build(first)
    (extracted / "src/autonomous/training_worker.py").write_text("tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify.verify_manifest(extracted)


@pytest.mark.parametrize("files", [{}, {"../escape": "bad"}])
def test_reject_empty_or_unsafe_manifest(tmp_path, files):
    (tmp_path / "manifest.json").write_text(json.dumps({"files": files}))
    with pytest.raises(ValueError):
        verify.verify_manifest(tmp_path)


def test_missing_or_nonportable_wheels(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    wheel = wheels / "boto3-1.42.19-py3-none-any.whl"
    wheel.write_bytes(b"placeholder")
    with pytest.raises(ValueError, match="Missing pinned wheel"):
        builder.build(tmp_path / "missing.tar.gz", wheels)
    wheel.rename(wheels / "boto3-1.42.19-cp311-linux_x86_64.whl")
    with pytest.raises(ValueError, match="portable"):
        builder.build(tmp_path / "platform.tar.gz", wheels)


def complete_plan():
    plan = json.loads((ROOT / "scripts/ami/readiness.example.json").read_text())
    profile = "arn:aws:iam::123456789012:instance-profile/training"
    plan["stack_outputs"] = {"TrainingInstanceProfileArn": profile,
                             "TrainingDocumentName": "training", "CheckpointsBucketName": "checkpoints"}
    plan["launch_template_data"].update({"ImageId": "ami-0123456789abcdef0", "IamInstanceProfile": {"Arn": profile}})
    plan["network"] = {key: True for key in plan["network"]}
    plan["network"]["method"] = "vpc_endpoints"
    return plan


def test_complete_plan_is_never_live_verified():
    result = readiness.check(complete_plan())
    assert result["plan_complete"] and result["pending"] == []
    assert result["live_verified"] is False and result["aws_calls"] == 0
    sample = json.loads((ROOT / "scripts/ami/readiness.example.json").read_text())
    assert not readiness.check(sample)["plan_complete"]


@pytest.mark.parametrize("section,key,value", [
    ("launch_template_data", "IamInstanceProfile", {"Arn": "wrong"}),
    ("launch_template_data", "InstanceMarketOptions", {"MarketType": "spot"}),
    ("launch_template_tags", "CostGuardProtected", "true"),
    ("launch_template_tags", "Environment", "production"),
    ("network", "ssmmessages_endpoint", False),
    ("network", "s3_route", False),
    (None, "instance_architecture", "arm64"),
    (None, "execution_enabled", True),
])
def test_plan_fails_closed(section, key, value):
    plan = complete_plan()
    target = plan if section is None else plan[section]
    target[key] = value
    assert not readiness.check(plan)["plan_complete"]
