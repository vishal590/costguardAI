"""Build a deterministic allowlisted runtime archive; no AWS or pip calls."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
FILES=("src/autonomous/__init__.py","src/autonomous/training_worker.py",
       "scripts/ami/install.sh","scripts/ami/verify_runtime.py","scripts/ami/check_readiness.py",
       "scripts/ami/requirements-runtime.txt","scripts/ami/readiness.example.json","scripts/ami/README.md")


def build(output, wheelhouse=None, root=ROOT):
    output=Path(output)
    payload={}
    for name in FILES:
        path=root/name
        if path.is_symlink() or not path.is_file():raise ValueError("Missing/unsafe source: "+name)
        payload[name]=path.read_bytes().replace(b"\r\n",b"\n")
    if wheelhouse:
        wheels=sorted(Path(wheelhouse).glob("*.whl"))
        if not wheels:raise ValueError("Wheelhouse is empty")
        for path in wheels:
            if path.is_symlink() or not path.name.endswith("-none-any.whl"):
                raise ValueError("Only portable pure-Python wheels are supported")
            payload["wheelhouse/"+path.name]=path.read_bytes()
        requirements=[line for line in payload["scripts/ami/requirements-runtime.txt"].decode().splitlines() if line and not line.startswith("#")]
        for requirement in requirements:
            package,version=requirement.split("==")
            prefix=package.replace("-","_")+"-"+version+"-"
            if not any(path.name.startswith(prefix) for path in wheels):
                raise ValueError("Missing pinned wheel: "+requirement)
    manifest={"schema_version":1,"python":"3.11","install_root":"/opt/costguard",
              "files":{name:hashlib.sha256(value).hexdigest() for name,value in sorted(payload.items())}}
    payload["manifest.json"]=(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists() or Path(str(output)+".sha256").exists():raise FileExistsError("Bundle output already exists")
    with output.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw,mode="wb",filename="",mtime=0) as zipped:
            with tarfile.open(fileobj=zipped,mode="w",format=tarfile.PAX_FORMAT) as archive:
                for name,value in sorted(payload.items()):
                    info=tarfile.TarInfo(name);info.size=len(value);info.mtime=0
                    info.mode=0o755 if name.endswith(".sh") else 0o644
                    archive.addfile(info,io.BytesIO(value))
    checksum=hashlib.sha256(output.read_bytes()).hexdigest()
    with Path(str(output)+".sha256").open("x",encoding="utf-8") as sidecar:
        sidecar.write(checksum+"  "+output.name+"\n")
    return {"archive":str(output),"sha256":checksum,"files":len(payload),"wheelhouse":bool(wheelhouse)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--wheelhouse",type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.output,args.wheelhouse),indent=2))


if __name__=="__main__":main()
