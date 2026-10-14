"""Offline integrity/optimizer checks and local installed-host readiness checks."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
from importlib.metadata import version


def verify_manifest(root, filename="manifest.json"):
    root = Path(root).resolve()
    manifest = json.loads((root / filename).read_text())
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Manifest must contain file hashes")
    for name, digest in files.items():
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Unsafe bundle entry")
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError("Unsafe or missing bundle entry: " + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Bundle checksum mismatch: " + name)
    return len(manifest["files"])


def load_worker(root):
    spec = importlib.util.spec_from_file_location("costguard_image_worker", Path(root)/"src/autonomous/training_worker.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def optimizer_self_test(root):
    worker = load_worker(root)
    class MemoryS3:
        class exceptions:
            class NoSuchKey(Exception):
                pass
        def __init__(self):
            self.objects = {}
        def get_object(self, Bucket, Key):
            if (Bucket,Key) not in self.objects:
                raise self.exceptions.NoSuchKey()
            return {"Body": io.BytesIO(self.objects[Bucket,Key])}
        def put_object(self, Bucket, Key, Body):
            self.objects[Bucket,Key] = Body
    store = MemoryS3()
    dataset = b"x,y\n0,1\n0.5,2\n1,3\n"
    initial = {"schema_version":1,"job_id":"readiness","dataset_sha256":worker.digest(dataset),
        "optimizer":{"kind":"sgd","learning_rate":.01},"weights":[.2,.3],"step":7}
    checkpoint = worker.serialize(initial)
    training = {"kind":"linear_regression_sgd","job_id":"readiness","dataset_key":"training/readiness/data.csv",
        "checkpoint_key":"training/readiness/source.json","checkpoint_sha256":worker.digest(checkpoint),"steps":30,"learning_rate":.01}
    store.put_object(Bucket="memory",Key=training["dataset_key"],Body=dataset)
    store.put_object(Bucket="memory",Key=training["checkpoint_key"],Body=checkpoint)
    config = worker.request(training,"memory","readiness-action")
    result = worker.run(store,config)
    if result["restored_step"] != 7 or result["final_step"] != 37 or worker.run(store,config) != result:
        raise ValueError("Optimizer resume/retry check failed")
    return {"restored_step":7,"final_step":37,"storage":"memory","aws_calls":0}


def installed_checks(root):
    checks = {}
    checks["linux"] = platform.system() == "Linux"
    checks["python_3_11"] = sys.version_info[:2] == (3,11)
    checks["isolated_interpreter"] = Path(sys.prefix).resolve() == (root/"venv").resolve()
    checks["worker_present"] = (root/"src/autonomous/training_worker.py").is_file()
    try: checks["installed_integrity"] = verify_manifest(root,"installed-manifest.json") > 0
    except (OSError,ValueError,KeyError): checks["installed_integrity"] = False
    for requirement in (root/"scripts/ami/requirements-runtime.txt").read_text().splitlines():
        if not requirement or requirement.startswith("#"):continue
        package, expected = requirement.split("==")
        try: checks[package] = version(package) == expected
        except Exception: checks[package] = False
    lock = Path("/var/lib/costguard/training-locks")
    checks["private_root_lock_directory"] = lock.is_dir() and not lock.is_symlink() and lock.stat().st_uid == 0 and lock.stat().st_mode & 0o077 == 0
    try:
        import fcntl
        checks["linux_file_locking"] = hasattr(fcntl,"flock")
    except ImportError: checks["linux_file_locking"] = False
    for state in ("is-active","is-enabled"):
        try: checks["ssm_"+state] = subprocess.run(["systemctl",state,"--quiet","amazon-ssm-agent"],timeout=10,check=False).returncode == 0
        except (OSError,subprocess.TimeoutExpired): checks["ssm_"+state] = False
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root",type=Path,default=Path("/opt/costguard"))
    parser.add_argument("--manifest-only",action="store_true")
    parser.add_argument("--installed",action="store_true")
    parser.add_argument("--self-test",action="store_true")
    args = parser.parse_args()
    report = {"aws_calls":0,"live_verified":False}
    if args.manifest_only or not args.installed:
        report["verified_bundle_files"] = verify_manifest(args.bundle_root)
    if args.installed:
        report["host_checks"] = installed_checks(args.bundle_root)
    if args.self_test:
        report["optimizer"] = optimizer_self_test(args.bundle_root)
    print(json.dumps(report,indent=2))
    if args.installed and not all(report["host_checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
