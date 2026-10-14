#!/usr/bin/env bash
# Run only on a separately authorized Amazon Linux 2023 image builder.
set -euo pipefail
install_host=false
allow_downloads=false
for arg in "$@"; do
  case "$arg" in
    --install-host-packages) install_host=true ;;
    --allow-pip-downloads) allow_downloads=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done
[[ "$(uname -s)" == Linux ]] || { echo "Linux is required" >&2; exit 1; }
[[ "$EUID" == 0 ]] || { echo "Run as root on the authorized image builder" >&2; exit 1; }
source /etc/os-release
[[ "$ID" == amzn && "$VERSION_ID" == 2023 ]] || { echo "This installer targets Amazon Linux 2023" >&2; exit 1; }
bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
if "$install_host"; then
  dnf install -y python3.11 python3.11-pip amazon-ssm-agent
fi
command -v python3.11 >/dev/null || { echo "Python 3.11 is missing; prepare host packages first" >&2; exit 1; }
command -v amazon-ssm-agent >/dev/null || { echo "SSM agent is missing; prepare host packages first" >&2; exit 1; }
python3.11 "$bundle_dir/scripts/ami/verify_runtime.py" --bundle-root "$bundle_dir" --manifest-only
# Refuse custom paths/symlinks: the SSM document uses this exact install root.
[[ ! -L /opt/costguard ]] || { echo "Install root must not be a symlink" >&2; exit 1; }
for path in /opt/costguard/src /opt/costguard/src/autonomous /opt/costguard/scripts /opt/costguard/scripts/ami /opt/costguard/venv /opt/costguard/src/autonomous/__init__.py /opt/costguard/src/autonomous/training_worker.py /opt/costguard/scripts/ami/verify_runtime.py /opt/costguard/scripts/ami/requirements-runtime.txt /opt/costguard/installed-manifest.json /var/lib/costguard /var/lib/costguard/training-locks; do
  [[ ! -L "$path" ]] || { echo "Runtime paths must not be symlinks" >&2; exit 1; }
done
install -d -m 0755 /opt/costguard /opt/costguard/src /opt/costguard/src/autonomous /opt/costguard/scripts /opt/costguard/scripts/ami
install -m 0644 "$bundle_dir/src/autonomous/__init__.py" /opt/costguard/src/autonomous/__init__.py
install -m 0644 "$bundle_dir/src/autonomous/training_worker.py" /opt/costguard/src/autonomous/training_worker.py
install -m 0644 "$bundle_dir/scripts/ami/verify_runtime.py" /opt/costguard/scripts/ami/verify_runtime.py
install -m 0644 "$bundle_dir/scripts/ami/requirements-runtime.txt" /opt/costguard/scripts/ami/requirements-runtime.txt
python3.11 - "$bundle_dir" <<'PY'
import json
from pathlib import Path
bundle = Path(__import__('sys').argv[1])
names = ['src/autonomous/__init__.py', 'src/autonomous/training_worker.py',
         'scripts/ami/verify_runtime.py', 'scripts/ami/requirements-runtime.txt']
source = json.loads((bundle/'manifest.json').read_text())
(Path('/opt/costguard')/'installed-manifest.json').write_text(json.dumps({'files': {name: source['files'][name] for name in names}}, indent=2))
PY
python3.11 -m venv /opt/costguard/venv
if "$allow_downloads"; then
  /opt/costguard/venv/bin/python -m pip --isolated install --index-url https://pypi.org/simple -r /opt/costguard/scripts/ami/requirements-runtime.txt
else
  [[ -d "$bundle_dir/wheelhouse" ]] || { echo "Offline wheelhouse missing; no packages downloaded" >&2; exit 1; }
  /opt/costguard/venv/bin/python -m pip --isolated install --no-index --find-links "$bundle_dir/wheelhouse" -r /opt/costguard/scripts/ami/requirements-runtime.txt
fi
install -d -m 0700 /var/lib/costguard /var/lib/costguard/training-locks
systemctl enable --now amazon-ssm-agent
/opt/costguard/venv/bin/python /opt/costguard/scripts/ami/verify_runtime.py --installed --self-test
