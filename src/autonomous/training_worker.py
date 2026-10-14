"""Bounded, resumable linear-regression SGD workload for Linux EC2/SSM.

This concrete reference workload uses CSV columns x,y. Its checkpoint includes
model and optimizer state, step, dataset digest and training-job identity.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path

MAX_BYTES = 4 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def serialize(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


def validate(training):
    if not isinstance(training, dict) or training.get("kind") != "linear_regression_sgd":
        raise ValueError("Unsupported training workload")
    job = training.get("job_id", "")
    if not isinstance(job, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job):
        raise ValueError("Invalid training job ID")
    prefix = "training/" + job + "/"
    for field in ("dataset_key", "checkpoint_key"):
        key = training.get(field)
        if not isinstance(key, str) or not key.startswith(prefix) or ".." in key.split("/"):
            raise ValueError("Training objects must belong to the job prefix")
    if not re.fullmatch(r"[a-f0-9]{64}", training.get("checkpoint_sha256", "")):
        raise ValueError("An input checkpoint SHA256 is required")
    steps = training.get("steps")
    if (steps is None or isinstance(steps, (bool, str))
            or not math.isfinite(float(steps)) or int(steps) != steps or not 1 <= steps <= 10000):
        raise ValueError("Training steps must be an integer from 1 to 10000")
    rate = float(training.get("learning_rate", 0))
    if not math.isfinite(rate) or not 0 < rate <= 1:
        raise ValueError("Learning rate must be positive and at most one")
    return prefix


def read(s3, bucket, key):
    response = s3.get_object(Bucket=bucket, Key=key)
    data = response["Body"].read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Training object exceeds 4 MiB")
    return data


def load(s3, bucket, training):
    validate(training)
    dataset = read(s3, bucket, training["dataset_key"])
    rows = [(float(row["x"]), float(row["y"])) for row in csv.DictReader(io.StringIO(dataset.decode("utf-8")))]
    if not rows or len(rows) > 10000 or any(not math.isfinite(n) for row in rows for n in row):
        raise ValueError("Dataset needs 1-10000 finite x,y pairs")
    checkpoint = read(s3, bucket, training["checkpoint_key"])
    if digest(checkpoint) != training["checkpoint_sha256"]:
        raise ValueError("Checkpoint checksum mismatch")
    state = json.loads(checkpoint)
    if (state.get("schema_version") != 1 or state.get("job_id") != training["job_id"]
            or state.get("dataset_sha256") != digest(dataset)
            or state.get("optimizer") != {"kind": "sgd", "learning_rate": float(training["learning_rate"])}):
        raise ValueError("Checkpoint identity, dataset or optimizer does not match")
    step = state.get("step")
    weights = state.get("weights")
    if (isinstance(step, bool) or not isinstance(step, int) or step < 0
            or not isinstance(weights, list) or len(weights) != 2
            or any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in weights)):
        raise ValueError("Invalid model state")
    return rows, state


def request(training, bucket, action_id):
    prefix = validate(training)
    run_id = digest(action_id.encode())[:48]
    return {"training": training, "bucket": bucket, "run_id": run_id,
            "result_key": prefix + "runs/" + run_id + "/result.json",
            "output_checkpoint_key": prefix + "runs/" + run_id + "/checkpoint.json"}


def verify(s3, config, initial):
    result = json.loads(read(s3, config["bucket"], config["result_key"]))
    state_data = read(s3, config["bucket"], config["output_checkpoint_key"])
    state = json.loads(state_data)
    target = initial["step"] + int(config["training"]["steps"])
    if (result.get("request_sha256") != digest(serialize(config))
            or result.get("restored_step") != initial["step"] or result.get("final_step") != target
            or result.get("initial_weights") != initial["weights"]
            or result.get("output_checkpoint_sha256") != digest(state_data)
            or state.get("step") != target or state.get("job_id") != initial["job_id"]
            or state.get("dataset_sha256") != initial["dataset_sha256"]
            or state.get("optimizer") != initial["optimizer"]
            or not math.isfinite(float(result.get("loss", float("nan"))))
            or not isinstance(state.get("weights"), list) or len(state["weights"]) != 2
            or any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in state["weights"])):
        raise ValueError("Training result does not prove checkpoint restoration and progress")
    return result


def run(s3, config):
    rows, state = load(s3, config["bucket"], config["training"])
    # Immutable input and deterministic output keys let retries reuse an already
    # verified result rather than repeating optimizer steps.
    try:
        return verify(s3, config, state)
    except s3.exceptions.NoSuchKey:
        pass
    initial = json.loads(serialize(state))
    slope, bias = state["weights"]
    rate = state["optimizer"]["learning_rate"]
    for step in range(state["step"], state["step"] + int(config["training"]["steps"])):
        x, y = rows[step % len(rows)]
        error = slope*x + bias - y
        slope -= rate * 2 * error * x
        bias -= rate * 2 * error
        if not math.isfinite(slope) or not math.isfinite(bias):
            raise ValueError("Optimizer diverged")
        state.update(step=step+1, weights=[slope, bias])
        # Persist real weights after every step, including interruptible runs.
        s3.put_object(Bucket=config["bucket"], Key=config["output_checkpoint_key"], Body=serialize(state))
    loss = sum((slope*x+bias-y)**2 for x,y in rows) / len(rows)
    result = {"request_sha256": digest(serialize(config)), "restored_step": initial["step"],
              "final_step": state["step"], "initial_weights": initial["weights"],
              "output_checkpoint_sha256": digest(serialize(state)), "loss": loss,
              "job_id": state["job_id"], "status": "training_progress_verified"}
    s3.put_object(Bucket=config["bucket"], Key=config["result_key"], Body=serialize(result))
    return verify(s3, config, initial)


def main():
    import boto3
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-base64", required=True)
    args = parser.parse_args()
    config = json.loads(base64.b64decode(args.request_base64, validate=True))
    # The SSM request supplies run_id/output keys, which must still be scoped.
    prefix = validate(config["training"])
    if not re.fullmatch(r"[a-f0-9]{48}", config["run_id"]):
        raise ValueError("Invalid run identifier")
    for field, name in [("result_key", "result.json"), ("output_checkpoint_key", "checkpoint.json")]:
        if config[field] != prefix+"runs/"+config["run_id"]+"/"+name:
            raise ValueError("Output key is outside the run")
    lock_directory = Path("/var/lib/costguard/training-locks")
    lock_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = lock_directory / (config["run_id"] + ".lock")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(run(boto3.client("s3"), config)))


if __name__ == "__main__":
    main()
