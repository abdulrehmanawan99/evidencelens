"""Start the local API, durable worker, and UI; preserve other running instances."""
import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description="Run EvidenceLens locally.")
parser.add_argument("--production", action="store_true")
parser.add_argument("--port", type=int, default=3000)
parser.add_argument("--api-port", type=int, default=8000)
args = parser.parse_args()
env = os.environ.copy()
config = ROOT/".env"
if config.exists():
    for line in config.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key,value=line.split("=",1)
            env.setdefault(key.strip(),value.strip().strip("\"'"))
for port in [args.port,args.api_port]:
    if not 1024 <= port <= 65535:
        raise SystemExit("Choose local ports between 1024 and 65535.")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1",port)) == 0:
            raise SystemExit(f"Port {port} is already in use. Stop that app or choose --port and --api-port values for another instance.")
node = env.get("NODE_EXECUTABLE") or shutil.which("node")
if not node:
    raise SystemExit("Install Node.js 22.13+ or 24, or set NODE_EXECUTABLE.")
version = subprocess.check_output([node,"--version"],text=True).strip().lstrip("v").split(".")
if tuple(map(int,version[:2])) < (22,13):
    raise SystemExit("The PDF reader requires Node.js 22.13+ or 24. Set NODE_EXECUTABLE to a supported runtime.")
env["STORAGE_DIR"] = str((ROOT/env.get("STORAGE_DIR",".local/artifacts")).resolve())
env["APP_ORIGIN"] = f"http://127.0.0.1:{args.port}"
env["API_ORIGIN"] = f"http://127.0.0.1:{args.api_port}"
env["API_URL"] = f"http://127.0.0.1:{args.api_port}"
env["NEXT_TELEMETRY_DISABLED"] = "1"
env.setdefault("BUILDX_CONFIG",str(ROOT/".local/buildx"))
if sys.platform == "darwin" and env.get("PARSER_BACKEND","auto") in {"auto","docker"}:
    docker=shutil.which("docker")
    if not docker:
        raise SystemExit("Docker is required for the isolated PDF parser on macOS. Start Docker Desktop.")
    image=env.get("PARSER_IMAGE","evidencelens-parser:1.0.0")
    found=subprocess.run([docker,"image","inspect",image],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if found.returncode:
        subprocess.run([docker,"build","-t",image,"-f","parser.Dockerfile","."],cwd=ROOT/"backend",env=env,check=True)
subprocess.run([sys.executable,"-m","alembic","upgrade","head"],cwd=ROOT/"backend",env=env,check=True)
subprocess.run([node,"scripts/copy-pdf-worker.mjs"],cwd=ROOT/"apps/web",env=env,check=True)
if args.production:
    subprocess.run([node,"node_modules/next/dist/bin/next","build"],cwd=ROOT/"apps/web",env=env,check=True)
processes=[]

def launch(command,cwd):
    process=subprocess.Popen(command,cwd=cwd,env=env,start_new_session=os.name!="nt")
    processes.append(process)
    return process

def shutdown():
    for process in reversed(processes):
        if process.poll() is None:
            if os.name=="nt": process.terminate()
            else: os.killpg(process.pid,signal.SIGTERM)
    for process in processes:
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name=="nt": process.kill()
            else: os.killpg(process.pid,signal.SIGKILL)

signal.signal(signal.SIGINT,lambda *_:sys.exit(0))
signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
try:
    launch([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port",str(args.api_port)],ROOT/"backend")
    launch([sys.executable,"-m","app.worker"],ROOT/"backend")
    launch([node,"node_modules/next/dist/bin/next","start" if args.production else "dev","--hostname","127.0.0.1","--port",str(args.port)],ROOT/"apps/web")
    ready=False
    for attempt in range(120):
        if any(process.poll() is not None for process in processes): break
        try:
            with urllib.request.urlopen(env["APP_ORIGIN"]+"/api/v1/health/ready",timeout=1) as response:
                if response.status==200: ready=True;break
        except Exception: pass
        time.sleep(.5)
    if not ready: raise SystemExit("One of the local services failed to become ready. See its logs above.")
    print(f"\nEvidenceLens: {env['APP_ORIGIN']}\nAPI docs: {env['API_ORIGIN']}/docs\nMode: {env.get('MODEL_MODE','fixture')}\nCtrl+C stops this launcher's three processes.\n",flush=True)
    while all(process.poll() is None for process in processes): time.sleep(.5)
    failed=[process.returncode for process in processes if process.poll() is not None and process.returncode]
    if failed: raise SystemExit(failed[0])
finally:
    shutdown()
