"""Run from the repository root after dependency installation and database startup."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description="Start the private EvidenceLens API, fixture worker, and UI.")
parser.add_argument("--production", action="store_true", help="Build and start the production UI instead of the development server")
args = parser.parse_args()
env = os.environ.copy()
config = ROOT / ".env"
if config.exists():
    for line in config.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), value.strip().strip("\"'"))
if env.get("MODEL_MODE", "fixture") != "fixture":
    raise SystemExit("Only fixture mode is implemented in this build. Live providers are a later milestone.")
env["STORAGE_DIR"] = str((ROOT / env.get("STORAGE_DIR", ".local/artifacts")).resolve())
env["NEXT_TELEMETRY_DISABLED"] = "1"
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT / "backend", env=env, check=True)
if args.production:
    subprocess.run(["npm", "run", "build"], cwd=ROOT / "apps/web", env=env, check=True)
processes = []


def launch(command, cwd):
    process = subprocess.Popen(command, cwd=cwd, env=env, start_new_session=os.name != "nt")
    processes.append(process)
    return process


def shutdown(*_):
    for process in reversed(processes):
        if process.poll() is None:
            if os.name == "nt":
                process.terminate()
            else:
                os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)


signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
try:
    launch([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], ROOT / "backend")
    launch([sys.executable, "-m", "app.worker"], ROOT / "backend")
    launch(["npm", "start" if args.production else "run", *([] if args.production else ["dev"])], ROOT / "apps/web")
    print("\nEvidenceLens: http://127.0.0.1:3000\nAPI documentation: http://127.0.0.1:8000/docs\nCtrl+C stops all three processes.\n", flush=True)
    while all(process.poll() is None for process in processes):
        time.sleep(0.5)
    failed = [process.returncode for process in processes if process.poll() is not None and process.returncode]
    if failed:
        raise SystemExit(failed[0])
finally:
    shutdown()
