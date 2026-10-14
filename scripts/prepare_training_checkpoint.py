"""Prepare a local initial model checkpoint; this script makes no AWS calls."""
import argparse
import csv
import io
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from autonomous.training_worker import MAX_BYTES, digest, serialize, validate


def prepare(dataset, job_id, learning_rate, steps):
    if len(dataset) > MAX_BYTES:
        raise ValueError("Dataset exceeds 4 MiB")
    rows = [(float(row["x"]),float(row["y"])) for row in csv.DictReader(io.StringIO(dataset.decode()))]
    if not rows or len(rows)>10000 or any(not math.isfinite(v) for row in rows for v in row):
        raise ValueError("Dataset needs 1-10000 finite x,y pairs")
    state = {"schema_version":1,"job_id":job_id,"dataset_sha256":digest(dataset),
             "optimizer":{"kind":"sgd","learning_rate":learning_rate},"weights":[0.0,0.0],"step":0}
    checkpoint = serialize(state)
    training = {"kind":"linear_regression_sgd","job_id":job_id,
        "dataset_key":f"training/{job_id}/datasets/{digest(dataset)}.csv",
        "checkpoint_key":f"training/{job_id}/checkpoints/{digest(checkpoint)}.json",
        "checkpoint_sha256":digest(checkpoint),"learning_rate":learning_rate,"steps":steps}
    validate(training)
    return checkpoint,training


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataset",type=Path,required=True)
    parser.add_argument("--job-id",required=True)
    parser.add_argument("--checkpoint-out",type=Path,required=True)
    parser.add_argument("--learning-rate",type=float,default=.01)
    parser.add_argument("--steps",type=int,default=100)
    args=parser.parse_args()
    checkpoint,training=prepare(args.dataset.read_bytes(),args.job_id,args.learning_rate,args.steps)
    with args.checkpoint_out.open("xb") as output:
        output.write(checkpoint)
    print(json.dumps(training,indent=2))


if __name__=="__main__":
    main()
