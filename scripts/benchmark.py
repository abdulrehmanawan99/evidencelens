"""Small fixture-only latency/queue benchmark of the running API and one worker."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import statistics
import time
from urllib.request import Request, urlopen
from uuid import uuid4

parser = argparse.ArgumentParser()
parser.add_argument("--api", default="http://127.0.0.1:8000")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()


def api(path, data=None, method=None):
    req = Request(args.api+"/api/v1"+path, data=json.dumps(data).encode() if data is not None else None, method=method, headers={"Content-Type":"application/json", "Idempotency-Key":str(uuid4())})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def wait(job):
    deadline = time.monotonic()+180
    while job["state"] in {"queued","running"}:
        if time.monotonic() > deadline:
            raise RuntimeError("benchmark_timeout")
        time.sleep(.1)
        job=api("/jobs/"+job["id"])
    if job["state"] != "succeeded":
        raise RuntimeError(job["error_code"] or job["state"])
    return job


if api("/provider-status")["mode"] != "fixture":
    raise SystemExit("This benchmark is restricted to fixture mode; it makes no paid model calls.")
collections, measurements = [], []
try:
    for _ in range(4):
        c=api("/sample",{},"POST")
        collections.append(c["id"])
        for _ in range(1800):
            docs=api(f"/collections/{c['id']}/documents")["items"]
            if all(d["state"]=="ready" for d in docs): break
            if any(d["state"] in {"failed","cancelled"} for d in docs): raise RuntimeError("ingestion_failed")
            time.sleep(.1)
        else: raise RuntimeError("ingestion_timeout")

    def investigate(identifier):
        started=time.time()
        r=api(f"/collections/{identifier}/investigations",{"claim":"Harbor Transit recorded 1.20 million journeys in Q2."},"POST")
        job=wait(r["job"])
        finished=time.time()
        start_job=datetime.fromisoformat(job["started_at"]).timestamp()
        end_job=datetime.fromisoformat(job["finished_at"]).timestamp()
        return {"end_to_end_ms":round((finished-started)*1000),"queue_wait_ms":round(max(0,start_job-started)*1000),"worker_ms":round((end_job-start_job)*1000)}

    for concurrency in (1,4):
        rows=[]
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for _ in range(8//concurrency):
                rows.extend(pool.map(investigate,collections[:concurrency]))
        measurements.append({"concurrency":concurrency,"samples":rows,"summary":{key:{"median":statistics.median(r[key] for r in rows),"p95":sorted(r[key] for r in rows)[math.ceil(.95*len(rows))-1],"max":max(r[key] for r in rows)} for key in rows[0]}})
finally:
    for identifier in collections:
        wait(api("/collections/"+identifier,method="DELETE"))
report={"measured_at":datetime.now(timezone.utc).isoformat(),"mode":"fixture","host":platform.platform(),"workload":"Four separate collections of four tiny synthetic text reports; one FIFO worker; eight warm investigations at each concurrency; polling every100ms. p95 with n=8 equals maximum. No live provider, large-PDF, endurance, or production capacity claim.","measurements":measurements}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps([{"concurrency":row["concurrency"],"summary":row["summary"]} for row in measurements]))
