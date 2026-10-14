# EC2 Training AMI Readiness

**Local preparation completed:** October 14, 2026. No AMI was created, no host installer was run, and no AWS resources were deployed or enabled. All further testing and AMI creation are deferred by user instruction. Feature implementation continues through the [development backlog](development-backlog.md).

## Prepared Runtime

The target is Amazon Linux 2023 with Python 3.11 in `/opt/costguard/venv`, the SSM agent and the reference CPU training worker under `/opt/costguard/src`. The fixed CDK SSM document uses that virtual environment's interpreter. It does not install packages during a training command.

Amazon Linux provides versioned Python packages; this setup leaves the system interpreter alone. See [AWS Python guidance](https://docs.aws.amazon.com/linux/al2023/ug/python.html). AWS Amazon Linux AMIs usually include the [SSM agent](https://docs.aws.amazon.com/systems-manager/latest/userguide/agent-install-al2.html); the installer still checks its presence and enabled/active service state.

The allowlisted bundle includes the worker, package initializer, installation and verification tools, an incomplete readiness example, and seven portable dependency wheels. SDK versions are pinned in [runtime requirements](../../scripts/ami/requirements-runtime.txt); this records a reproducible runtime, not a claim that these versions are the latest. Credentials, datasets, environment files, tests and unrelated Lambdas are excluded. Local artifacts under `.artifacts/` are ignored by Git.

## Rebuild and Verify Locally

From the backend root, obtain the pinned portable wheels if needed:

```powershell
python -m pip --isolated download --only-binary=:all: --no-deps --index-url https://pypi.org/simple --dest .artifacts/training-ami/wheelhouse -r scripts/ami/requirements-runtime.txt
python scripts/build_training_ami_bundle.py --output .artifacts/training-ami/runtime.tar.gz --wheelhouse .artifacts/training-ami/wheelhouse
```

The builder refuses to overwrite an archive or checksum sidecar. Use a new output filename when rebuilding. File order, timestamps and gzip metadata are deterministic. The archive has a SHA256 sidecar and an internal per-file hash manifest. Verify the sidecar before extracting on an authorized host:

```bash
sha256sum -c runtime.tar.gz.sha256
mkdir runtime
cd runtime
tar -xzf ../runtime.tar.gz
python3 scripts/ami/verify_runtime.py --bundle-root . --self-test
```

The self-test restores step 7, advances to step 37 and reuses the verified result on retry, using in-memory storage with zero AWS calls. Manifest verification detects missing, modified and unsafe entries. Hashes detect corruption; obtain the archive and checksum from the trusted build source.

## Installation on a Future Authorized Builder

Do this only after the AWS image-builder step is explicitly authorized. On Amazon Linux 2023, from the extracted bundle:

```bash
sudo bash scripts/ami/install.sh
```

The default installation uses bundled wheels without package-index access and requires Python 3.11 and the SSM agent already present. `--install-host-packages` explicitly permits DNF to install `python3.11`, `python3.11-pip` and `amazon-ssm-agent`; `--allow-pip-downloads` explicitly permits PyPI instead of offline wheels. Neither flag enables autonomous execution or creates an AMI.

The installer uses fixed paths, rejects symlink destinations, creates a root-only training-lock directory, enables the agent, and checks installed source hashes, exact dependency versions, isolated Python 3.11, Linux locking and local SSM service state. Recheck with:

```bash
sudo /opt/costguard/venv/bin/python /opt/costguard/scripts/ami/verify_runtime.py --installed --self-test
```

Local service checks do not prove registration in Systems Manager. Consult AWS [agent status guidance](https://docs.aws.amazon.com/systems-manager/latest/userguide/ssm-agent-status-and-restart.html) if they fail.

## IAM, Launch Template and Networking

Use the exact `TrainingInstanceProfileArn`, `TrainingDocumentName` and `CheckpointsBucketName` stack outputs. The CDK training role includes SSM registration permissions and S3 Get/Put on that bucket's `training/*` prefix. The executor can pass only the configured training role. Existing infrastructure definitions are checked by local synthesis; an operator must later verify the effective deployed IAM and endpoint policies.

After authorized image creation, set the actual AMI ID and a compatible instance type in a versioned launch template. Use `IamInstanceProfile: {"Arn": "<TrainingInstanceProfileArn>"}`. Select the same region as the stack and a matching AMI/instance architecture. Template tags must opt in with `CostGuardManaged=true`, omit protection or set `CostGuardProtected=false`, and use a non-production environment. Do not put `InstanceMarketOptions` in the template; the executor chooses On-Demand or one-time Spot. Requests must use an explicit numeric template version.

Instances need DNS and outbound HTTPS to SSM, `ssmmessages` and the checkpoint bucket. Private networks can use SSM/ssmmessages interface endpoints with private DNS and endpoint security groups permitting HTTPS from the instance, plus an appropriate S3 endpoint route and policy. Public egress requires working routing/NAT or public connectivity. Some older SSM configurations also use `ec2messages`; check the region and agent requirements in AWS [SSM troubleshooting guidance](https://docs.aws.amazon.com/en_en/systems-manager/latest/userguide/troubleshooting-ssm-agent.html). Account policies, subnet routes and bucket encryption permissions must permit the real workload.

Copy [the readiness example](../../scripts/ami/readiness.example.json), fill actual outputs and network declarations, then run:

```powershell
python scripts/ami/check_readiness.py path/to/readiness.json
```

The supplied example intentionally exits 2 because cloud values and routes are unknown. A complete declared plan reports `plan_complete: true`, but always `live_verified: false` and `aws_calls: 0`. It cannot establish actual AMI architecture, IAM permissions, SSM registration or reachable endpoints. Keep `execution_enabled: false` during preparation.

## Validation and Remaining Work

The focused preparation, training and CDK checks passed **28 tests**. Bundled wheels resolved without package-index access into a local dependency directory, and boto3/botocore plus Linux file-lock support imported successfully under Ubuntu/WSL Python 3.12. Offline tests cover deterministic allowlisting, overwrite refusal, manifest corruption/path rejection, checkpoint resume/retry, missing or nonportable dependencies, incomplete and unsafe launch plans, and the CDK virtual-environment command. Linux shell syntax, extracted bundle integrity and the real optimizer self-test were checked through local Ubuntu/WSL. Its Python 3.12 does not certify the target Python 3.11 Amazon Linux host.

The separately authorized next step is installation on an Amazon Linux 2023 builder, host verification and AMI creation, followed by validation of the actual IAM profile, network access and SSM registration. End-to-end training and interruption timing require a later bounded AWS validation. No such live checks are claimed by local preparation.

See [training resume](ec2-training-resume.md), [autonomous execution](autonomous-execution.md) and [documentation/code synchronization](documentation-code-sync.md).
