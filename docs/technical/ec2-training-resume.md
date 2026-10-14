# EC2 Training Resume

**Implemented and reviewed:** October 13, 2026. Local tests run real optimizer steps; AWS infrastructure and commands are mocked. Nothing was deployed.

## Implemented Workload

The existing EC2 replacement path now accepts an optional `parameters.training` contract. The supplied reference worker performs real linear-regression stochastic gradient descent on a CSV dataset with `x,y` columns. It restores two model weights, SGD learning-rate state, dataset identity and the optimizer step from an S3 checkpoint, then persists updated weights after each step.

This is a concrete, CPU-based training workload. It demonstrates interruption/resume semantics and is not a claim of GPU training throughput, PyTorch/TensorFlow compatibility or support for an arbitrary existing model. Resource-only replacement actions remain supported when the training contract is absent.

## Request Contract

Add this object inside the existing replacement request's `parameters`, alongside the launch-template ID/version, region, runtime and cost estimate:

```json
{
  "training": {
    "kind": "linear_regression_sgd",
    "job_id": "example-job",
    "dataset_key": "training/example-job/datasets/dataset-digest.csv",
    "checkpoint_key": "training/example-job/checkpoints/checkpoint-digest.json",
    "checkpoint_sha256": "replace-with-the-64-character-sha256",
    "steps": 100,
    "learning_rate": 0.01
  }
}
```

The existing `POST /api/autonomous/demo/trigger-interruption` route forwards this contract when `DEMO_MODE=true`. Its body now requires explicit `instance_id`, `training_job_id` and `parameters`; it returns **202** with `status: "interruption_submitted"`. Job identities must match. This submits an event for approval, not completed training.

Use actual object keys and a SHA256 produced by the preparation tool. Objects must belong to `training/<job_id>/`; the bucket is the stack's configured checkpoint bucket, not a request-selected destination. The checkpoint's job, dataset digest and optimizer configuration must match the request. Requests permit 1-10000 steps and at most 4 MiB per input/result object. Datasets contain 1-10000 finite numeric pairs. Schedule/right-sizing actions reject this training contract; it is currently supported for Spot and On-Demand replacement actions.

## Preparing an Initial Checkpoint

`scripts/prepare_training_checkpoint.py` makes no AWS calls. It validates a local CSV dataset, creates an initial model checkpoint with zero weights/step zero, and prints the training contract with content-addressed dataset/checkpoint keys:

```powershell
python scripts/prepare_training_checkpoint.py --dataset training-data.csv --job-id example-job --checkpoint-out initial-model.json --learning-rate 0.01 --steps 100
```

The tool refuses to overwrite an existing checkpoint file. When a deployment is separately authorized and configured, upload the dataset and checkpoint to the configured bucket at the printed keys. The assistant did not upload objects or deploy these resources during implementation.

## Current Preparation Status

**October 14, 2026:** Local AMI preparation is complete: a worker-only archive, pinned portable dependency wheels, installer, integrity/runtime verification and an offline launch-plan checker are prepared. See [AMI readiness](ec2-ami-readiness.md). All further testing and AMI creation are deferred. The [development backlog](development-backlog.md) is now the active next-work plan. Actual Amazon Linux installation, AMI creation, deployed IAM/network checks and SSM registration remain pending.

No live AMI creation, installation, deployment or execution enablement was performed. The local setup material is reviewable before a separately authorized AWS step.

## EC2 Prerequisites

The launch template must use the exact ARN returned by the CDK `TrainingInstanceProfileArn` output in `IamInstanceProfile.Arn`. Generic instance profiles remain rejected. The provisioned role allows SSM registration and S3 reads/writes in the checkpoint bucket's `training/*` prefix; the executor can pass only this training role for EC2 launches.

Prepare an Amazon Linux 2023 AMI with Python 3.11 in `/opt/costguard/venv`, pinned boto3 dependencies, the SSM agent and this repository's `src/autonomous/training_worker.py` package installed under `/opt/costguard/src`. The fixed SSM document invokes `/opt/costguard/venv/bin/python -m autonomous.training_worker` with that directory in `PYTHONPATH`; it does not download or install code at runtime. The instance must be able to contact SSM and S3. No AMI, dataset or model was installed in a live AWS account by this task.

The CDK `TrainingDocumentName` output identifies the fixed command document. Its only execution inputs are a validated base64 request and a bounded timeout. The API does not accept arbitrary shell commands or alternate document names. Existing execution opt-in, human approval, ownership checks, cleanup timers and budget checks still apply.

## Execution and Proof of Resume

The executor verifies the source checkpoint before provisioning, launches the owned replacement, waits for EC2 running and SSM readiness, then submits the configured training document. The SSM command ID is stored in the recovery snapshot so retries can wait on the same invocation.

The worker produces S3 objects at `training/<job_id>/runs/<action-token>/checkpoint.json` and `result.json`. Linux file locking serializes duplicate commands on that replacement. A validated existing result is reused without advancing optimizer steps again. Input checkpoints are never overwritten; a partially written output checkpoint can be supplied explicitly to a new approved action with its actual digest.

An SSM `Success` status alone is insufficient. The executor also verifies the request digest, original weights/step, exact final step, output checkpoint checksum, job/dataset/optimizer identity and finite model/loss values. Only then does it mark the action completed and emit `ActionCompleted` with `resource_result.operation: "training_progress_verified"`. Training details include `restored_step`, `final_step`, measured training loss, the command ID and the next checkpoint key/digest. These do not establish measured cost savings or completion of the user's full model training.

Missing evidence, a corrupt checkpoint, a dataset mismatch or a failed command leaves execution failed and emits no success event. Legacy `restore_from_checkpoint` metadata-only calls return false rather than claiming that downloading epoch/step metadata restored a model.

## Recovery and Next Resume

Rollback/expiry attempts to cancel the saved training command and then terminates only the action-owned replacement. SSM cancellation errors do not prevent resource cleanup. The S3 model checkpoint is retained for a subsequent approved action; use the returned checkpoint key/SHA256 with the same job, dataset and optimizer settings. This does not resurrect an original Spot instance after AWS terminates it.

Live SSM readiness, AMI installation/creation, networking, permissions and interruption timing still need AWS validation after separate deployment authorization. The sibling frontend now submits this training contract and displays action-history training results and execution errors. Its source contracts, rendered components and build were checked locally on October 14; live browser/API execution remains unverified.

## Verification

Tests perform actual SGD on local Moto S3 objects, resume a second run from the first checkpoint and verify loss reduction and exact step advancement. Mocked EC2/SSM tests connect approval, launch, command dispatch, proof verification, retries and rollback. They also reject a successful command lacking checkpoint evidence and a failed command claiming success. Local CDK synthesis checks the fixed document and instance-profile configuration.

AWS documents the distinction between [command status](https://docs.aws.amazon.com/systems-manager/latest/userguide/monitor-commands.html) and [GetCommandInvocation results](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_GetCommandInvocation.html). This implementation additionally checks its own model-state evidence.

See [autonomous execution](autonomous-execution.md) and [documentation/code synchronization](documentation-code-sync.md).
