# Training AMI Preparation Bundle

Target: Amazon Linux 2023, Python 3.11. This folder prepares local artifacts only.
The installer must be run later on a separately authorized image-builder host.

Build the worker-only archive from the backend root:

```powershell
python scripts/build_training_ami_bundle.py --output .artifacts/training-ami/runtime.tar.gz --wheelhouse .artifacts/training-ami/wheelhouse
```

The archive contains only the reference worker/package initializer, preparation
scripts, examples, manifest and explicitly supplied portable dependency wheels.
It excludes credentials, environment files, tests, datasets and other Lambdas.
Verify its SHA256 sidecar before extraction on the authorized host.

On that host, after extraction:

```bash
sudo bash scripts/ami/install.sh
```

The default uses the bundled wheelhouse without package-index access. Missing
Python 3.11 or the SSM agent blocks installation. To explicitly prepare Amazon
Linux host packages, pass `--install-host-packages`. A deliberate
`--allow-pip-downloads` allows PyPI installation instead of an offline wheelhouse.
No flags enable autonomous execution or create an AMI.

The fixed SSM command uses `/opt/costguard/venv/bin/python` with the worker under
`/opt/costguard/src`. Source hashes and pinned SDK versions are checked on the
installed host. Root-only Linux file locking and enabled/active SSM-agent checks
are local prerequisites; they do not prove AWS registration or network access.

Offline verification after extraction:

```bash
python3 scripts/ami/verify_runtime.py --bundle-root . --self-test
python3 scripts/ami/check_readiness.py scripts/ami/readiness.example.json
```

The second command intentionally exits 2 until the operator supplies actual
stack outputs, a prepared AMI ID and network declarations. Even a complete plan
always reports `live_verified: false`. It makes no AWS calls.

See backend `docs/technical/ec2-ami-readiness.md` for host, IAM, launch-template,
network and validation details. Browser testing remains deferred.
