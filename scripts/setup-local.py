"""Prepare private local config, host-owned artifacts, and a persistent Docker volume."""
import os
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
config = root / ".env"
if not config.exists():
    shutil.copyfile(root / ".env.example", config)
config.chmod(0o600)
values = dict(line.split("=", 1) for line in config.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#"))
additions = {"LOCAL_UID": str(os.getuid()), "LOCAL_GID": str(os.getgid())}
if additions["LOCAL_UID"] == "0":
    raise SystemExit("Run setup as your normal user, without sudo.")
with config.open("a") as stream:
    for key, value in additions.items():
        if key not in values:
            stream.write(f"\n{key}={value}\n")
storage = Path(os.environ.get("ARTIFACTS_DIR", values.get("ARTIFACTS_DIR", ".local/v1-artifacts")))
if not storage.is_absolute():
    storage = root / storage
storage.mkdir(parents=True, exist_ok=True, mode=0o700)
subprocess.run(["docker", "volume", "create", os.environ.get("PGDATA_VOLUME", values.get("PGDATA_VOLUME", "evidencelens_v1_pgdata"))], check=True, stdout=subprocess.DEVNULL)
print("Local config, artifact directory, and persistent database volume are ready.")
