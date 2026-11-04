"""Evaluate the running app through its public API, deleting only created collections."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--api", default="http://127.0.0.1:8000")
parser.add_argument("--suite", choices=["fixture", "live"], default="fixture")
parser.add_argument("--split", choices=["development", "held_out", "all"], default="development")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
dataset = json.loads((ROOT / "fixtures/evaluation.json").read_text())


def api(path, body=None, method=None, raw=False, headers=None):
    data = body if raw else (json.dumps(body).encode() if body is not None else None)
    req = Request(args.api + "/api/v1" + path, data=data, method=method, headers={"Content-Type": "text/plain" if raw else "application/json", **(headers or {})})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def wait(job):
    end = time.monotonic() + 930
    while job["state"] in {"queued", "running"}:
        if time.monotonic() > end:
            raise RuntimeError("evaluation_timeout")
        time.sleep(.2)
        job = api("/jobs/" + job["id"])
    if job["state"] != "succeeded":
        raise RuntimeError(job["error_code"] or job["state"])
    return job


status = api("/provider-status")
report = {"dataset": dataset["version"], "started_at": datetime.now(timezone.utc).isoformat(), "suite": args.suite, "split": args.split, "mode": status["mode"], "provider": status["provider"], "embedding": status.get("embedding"), "results": []}
if (args.suite == "live" and (status["mode"] == "fixture" or not status["configured"])) or (args.suite == "fixture" and status["mode"] != "fixture"):
    report.update(state="blocked", reason="Configure and check a live generation and embedding provider." if args.suite == "live" else "Select fixture mode.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(report["reason"])
    raise SystemExit(2)

collections = []
try:
    scenarios = [("txt", dataset["development"]), ("pdf", dataset["development"])] if args.suite == "fixture" or args.split in {"development", "all"} else []
    if args.suite == "live" and args.split in {"held_out", "all"}:
        scenarios += [("held_out", dataset["held_out"])]
    for format, cases in scenarios:
        collection = None
        for case in cases:
            if format == "held_out" or collection is None:
                started = time.monotonic()
                collection = api("/collections", {"title": "Evaluation " + case["id"]}) if format == "held_out" else api("/sample?format=" + format, {}, "POST")
                collections.append(collection["id"])
                for doc in case.get("documents", []):
                    uploaded = api(f"/collections/{collection['id']}/documents", doc["text"].encode(), "POST", True, {"X-Filename": doc["name"]})
                    wait(uploaded["job"])
                while True:
                    docs = api(f"/collections/{collection['id']}/documents")["items"]
                    if all(doc["state"] == "ready" for doc in docs):
                        break
                    if any(doc["state"] in {"failed", "cancelled"} for doc in docs) or time.monotonic()-started > 930:
                        raise RuntimeError("evaluation_ingestion_failed")
                    time.sleep(.2)
                ingestion_ms = round((time.monotonic()-started)*1000)
            result = {"id": case["id"], "split": "held_out" if format == "held_out" else "development", "format": format, "ingestion_ms": ingestion_ms}
            started = time.monotonic()
            try:
                run = api(f"/collections/{collection['id']}/investigations", {"claim": case["claim"]}, "POST", headers={"Idempotency-Key": str(uuid4())})
                job = wait(run["job"])
                run = api("/investigations/"+run["id"])
                trace = api(f"/investigations/{run['id']}/trace")
                passages = {}
                for hit in trace["hits"]:
                    if hit["in_context"]:
                        passages[hit["passage_id"]] = api("/passages/"+hit["passage_id"])["text"]
                citations = [f["passage_id"] in passages and f["quote"] in passages[f["passage_id"]] for f in run["findings"]]
                evidence = case["evidence"]
                covered = [any(label["text"] in text for text in passages.values()) for label in evidence]
                matched = [any(f["relation"] == label["relation"] and label["text"] in passages.get(f["passage_id"], "") for f in run["findings"]) for label in evidence]
                result.update(state="succeeded", outcome=run["outcome"], outcome_correct=run["outcome"] == case["outcome"], citations_valid=all(citations), citation_count=len(citations), relevant_passages=len(evidence), retrieval_recalled=sum(covered), evidence_matched=sum(matched), findings=len(run["findings"]), provider_calls=run["provider_calls"], configuration=run["configuration"], run_id=run["id"])
            except (RuntimeError, HTTPError) as exc:
                result.update(state="failed", error=str(exc))
            result["investigation_ms"] = round((time.monotonic()-started)*1000)
            report["results"].append(result)
finally:
    for identifier in collections:
        try:
            wait(api("/collections/"+identifier, method="DELETE"))
        except Exception:
            print("Cleanup may need retry for evaluation collection " + identifier)

rows = report["results"]
total = sum(row.get("relevant_passages", 0) for row in rows)
report.update(state="passed" if all(row.get("state") == "succeeded" and row["outcome_correct"] and row["citations_valid"] and row["evidence_matched"] == row["relevant_passages"] for row in rows) else "failed", metrics={"cases": len(rows), "outcomes_correct": sum(row.get("outcome_correct", False) for row in rows), "citations": sum(row.get("citation_count", 0) for row in rows), "valid_citation_cases": sum(row.get("citations_valid", False) for row in rows), "retrieval_recall_at_context": sum(row.get("retrieval_recalled", 0) for row in rows)/total if total else None, "evidence_recall": sum(row.get("evidence_matched", 0) for row in rows)/total if total else None, "investigation_median_ms": statistics.median(row["investigation_ms"] for row in rows), "investigation_max_ms": max(row["investigation_ms"] for row in rows)})
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2)+"\n")
print(json.dumps({"state":report["state"], "suite":args.suite, "metrics":report["metrics"]}))
raise SystemExit(0 if report["state"] == "passed" else 1)
