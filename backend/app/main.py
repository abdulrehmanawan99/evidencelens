import base64
from datetime import datetime
from hashlib import sha256
import json
from urllib.parse import unquote

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select, text, tuple_
from sqlalchemy.orm import Session as SASession
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import settings
from .db import owner_dependency, session_dependency
from .fixtures import CLAIMS, SOURCES
from .models import Collection, Document, Finding, Investigation, Job, JobEvent, Passage, ReviewEvent, now, uid
from .schemas import CollectionInput, CollectionOut, DocumentOut, InvestigationInput, InvestigationOut, JobOut, ReviewInput, SourceOut
from .services import add_job, collection_for, document_dict, document_for, fail, invalidate_runs, investigation_for, job_dict, job_for, run_dict, store_text

app = FastAPI(title="EvidenceLens", version="0.1.0", description="Private local fixture workflow. Live AI and PDFs are not yet implemented.")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
DB = Depends(session_dependency)
Owner = Depends(owner_dependency)


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    request_id = uid()
    origin = request.headers.get("origin")
    allowed = {settings.app_origin, "http://127.0.0.1:8000"}
    if origin and origin not in allowed:
        return JSONResponse(status_code=403, content={"detail": {"code": "origin_rejected", "message": "Only the configured local app origin is allowed."}})
    if request.headers.get("sec-fetch-site") == "cross-site":
        return JSONResponse(status_code=403, content={"detail": {"code": "cross_site_request", "message": "Cross-site requests are disabled."}})
    response = await call_next(request)
    response.headers.update({"X-Request-ID": request_id, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
    return response


def page_query(query, model, cursor, limit):
    if cursor:
        try:
            stamp, record_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
            query = query.where(tuple_(model.created_at, model.id) < tuple_(datetime.fromisoformat(stamp), record_id))
        except (ValueError, UnicodeError):
            fail(422, "invalid_cursor", "Use a cursor returned by this endpoint.")
    return query.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)


def page_result(rows, limit, serialize):
    more = len(rows) > limit
    rows = rows[:limit]
    cursor = base64.urlsafe_b64encode(f"{rows[-1].created_at.isoformat()}|{rows[-1].id}".encode()).decode() if more else None
    return {"items": [serialize(row) for row in rows], "next_cursor": cursor}


def collection_dict(session, collection):
    counts = dict(session.execute(select(Document.state, func.count()).where(Document.collection_id == collection.id, Document.deleted.is_(False)).group_by(Document.state)).all())
    return {"id": collection.id, "title": collection.title, "revision": collection.revision, "created_at": collection.created_at.isoformat(), "document_count": sum(counts.values()), "ready_count": counts.get("ready", 0)}


@app.get("/api/v1/health/live")
def live():
    return {"status": "ok"}


@app.get("/api/v1/health/ready")
def ready(session: SASession = DB):
    try:
        session.execute(text("SELECT 1 FROM collections LIMIT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "code": "database_or_migrations_unavailable"})
    return {"status": "ready", "mode": "fixture"}


@app.get("/api/v1/provider-status")
def provider_status():
    return {"mode": "fixture", "provider": "harbor-fixture-v1", "live_enabled": False, "supported_claims": CLAIMS, "message": "Predefined synthetic scenarios. No live model calls or semantic search.", "accepted_types": ["text/plain"], "max_upload_bytes": settings.max_upload}


@app.get("/api/v1/collections")
def collections(cursor: str | None = None, limit: int = Query(20, ge=1, le=100), session: SASession = DB, owner: str = Owner):
    rows = list(session.scalars(page_query(select(Collection).where(Collection.owner == owner, Collection.deleted.is_(False)), Collection, cursor, limit)))
    return page_result(rows, limit, lambda c: collection_dict(session, c))


@app.post("/api/v1/collections", status_code=201, response_model=CollectionOut)
def create_collection(body: CollectionInput, session: SASession = DB, owner: str = Owner):
    collection = Collection(title=body.title, owner=owner)
    session.add(collection)
    session.commit()
    return collection_dict(session, collection)


@app.post("/api/v1/sample", status_code=201, response_model=CollectionOut)
def sample(session: SASession = DB, owner: str = Owner):
    collection = Collection(title="Harbor Transit · Q2 review", owner=owner)
    session.add(collection)
    session.flush()
    paths = []
    try:
        for filename, content in SOURCES:
            _, _, path = store_text(session, collection, filename, content.encode())
            paths.append(path)
        session.commit()
    except Exception:
        session.rollback()
        for path in paths:
            path.unlink(missing_ok=True)
        raise
    return collection_dict(session, collection)


@app.get("/api/v1/collections/{collection_id}", response_model=CollectionOut)
def get_collection(collection_id: str, session: SASession = DB, owner: str = Owner):
    return collection_dict(session, collection_for(session, collection_id, owner))


@app.patch("/api/v1/collections/{collection_id}", response_model=CollectionOut)
def rename_collection(collection_id: str, body: CollectionInput, session: SASession = DB, owner: str = Owner):
    collection = collection_for(session, collection_id, owner, lock=True)
    collection.title = body.title
    session.commit()
    return collection_dict(session, collection)


@app.get("/api/v1/collections/{collection_id}/documents")
def documents(collection_id: str, session: SASession = DB, owner: str = Owner):
    collection_for(session, collection_id, owner)
    docs = session.scalars(select(Document).where(Document.collection_id == collection_id, Document.deleted.is_(False)).order_by(Document.created_at, Document.id).limit(25))
    return {"items": [document_dict(session, doc) for doc in docs], "next_cursor": None}


@app.post("/api/v1/collections/{collection_id}/documents", status_code=202)
async def upload(collection_id: str, request: Request, x_filename: str = Header(default="upload.txt"), session: SASession = DB, owner: str = Owner):
    # Stream the raw file body; this avoids an unbounded multipart spool before validation.
    collection = collection_for(session, collection_id, owner)
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type not in {"text/plain", "application/octet-stream"}:
        fail(415, "unsupported_type", "Only UTF-8 .txt files are supported in this slice.")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > settings.max_upload:
            fail(413, "upload_too_large", "Text files must be 2 MiB or smaller.")
    collection = collection_for(session, collection_id, owner, lock=True)
    path = None
    try:
        doc, job, path = store_text(session, collection, unquote(x_filename), bytes(data))
        session.commit()
    except Exception:
        session.rollback()
        if path:
            path.unlink(missing_ok=True)
        raise
    return {"document": document_dict(session, doc), "job": job_dict(job)}


@app.get("/api/v1/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, session: SASession = DB, owner: str = Owner):
    return document_dict(session, document_for(session, document_id, owner))


@app.get("/api/v1/documents/{document_id}/source", response_model=SourceOut)
def source(document_id: str, after: int = Query(-1, ge=-1), passage_id: str | None = None, session: SASession = DB, owner: str = Owner):
    doc = document_for(session, document_id, owner, lock=True)
    if passage_id:
        target = session.scalar(select(Passage).where(Passage.id == passage_id, Passage.document_id == doc.id))
        if not target:
            fail(404, "not_found", "This passage is unavailable.")
        after = target.ordinal - 1
    passages = list(session.scalars(select(Passage).where(Passage.document_id == doc.id, Passage.ordinal > after).order_by(Passage.ordinal).limit(101)))
    more = len(passages) > 100
    passages = passages[:100]
    return {"document": document_dict(session, doc), "passages": [{k: getattr(p, k) for k in ["id", "text", "line_start", "line_end", "start_offset", "ordinal"]} for p in passages], "next_after": passages[-1].ordinal if more else None}


@app.post("/api/v1/documents/{document_id}/retry", status_code=202, response_model=JobOut)
def retry_document(document_id: str, session: SASession = DB, owner: str = Owner):
    doc = document_for(session, document_id, owner, lock=True)
    if doc.state not in {"failed", "cancelled"}:
        fail(409, "invalid_state", "Only failed or cancelled ingestion can be retried.")
    doc.generation += 1
    doc.state = "queued"
    job = add_job(session, doc.collection_id, "ingest", doc.id, doc.checksum)
    session.commit()
    return job_dict(job)


def tombstone(session, collection, docs):
    affected_ids = {doc.id for doc in docs}
    for doc in docs:
        doc.deleted = True
    collection.revision += 1
    invalidate_runs(session, collection.id)
    for job in session.scalars(select(Job).where(Job.collection_id == collection.id, Job.kind.in_(["ingest", "investigate"]), Job.state.in_(["queued", "running"]))):
        if job.kind == "ingest" and job.resource_id not in affected_ids:
            continue
        job.cancel_requested = True
        if job.state == "queued":
            job.state = "cancelled"
            job.finished_at = now()
            session.add(JobEvent(job_id=job.id, state="cancelled"))


@app.delete("/api/v1/documents/{document_id}", status_code=202, response_model=JobOut)
def delete_document(document_id: str, session: SASession = DB, owner: str = Owner):
    doc = document_for(session, document_id, owner, lock=True)
    collection = collection_for(session, doc.collection_id, owner)
    tombstone(session, collection, [doc])
    job = add_job(session, collection.id, "delete_document", doc.id, doc.id)
    session.commit()
    return job_dict(job)


@app.delete("/api/v1/collections/{collection_id}", status_code=202, response_model=JobOut)
def delete_collection(collection_id: str, session: SASession = DB, owner: str = Owner):
    collection = collection_for(session, collection_id, owner, lock=True)
    docs = list(session.scalars(select(Document).where(Document.collection_id == collection.id, Document.deleted.is_(False))))
    tombstone(session, collection, docs)
    collection.deleted = True
    job = add_job(session, collection.id, "delete_collection", collection.id, collection.id)
    session.commit()
    return job_dict(job)


@app.post("/api/v1/collections/{collection_id}/investigations", status_code=202)
def investigate(collection_id: str, body: InvestigationInput, idempotency_key: str | None = Header(default=None, max_length=100), session: SASession = DB, owner: str = Owner):
    collection = collection_for(session, collection_id, owner, lock=True)
    request_hash = sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
    if idempotency_key:
        old = session.scalar(select(Job).where(Job.collection_id == collection.id, Job.kind == "investigate", Job.idempotency_key == idempotency_key))
        if old:
            if old.request_hash != request_hash:
                fail(409, "idempotency_conflict", "That idempotency key was used with a different request.")
            return {"id": old.resource_id, "job": job_dict(old)}
    docs = list(session.scalars(select(Document).where(Document.collection_id == collection.id, Document.deleted.is_(False))))
    included = [d for d in docs if d.state == "ready"]
    excluded = [d for d in docs if d.state != "ready"]
    if excluded and not body.allow_partial:
        fail(409, "collection_not_ready", "Wait for every source, or explicitly choose to analyze ready sources only.")
    if not included:
        fail(409, "no_ready_sources", "Upload a source and wait for ingestion before investigating.")
    active = session.scalar(select(func.count()).select_from(Job).where(Job.collection_id == collection.id, Job.kind == "investigate", Job.state.in_(["queued", "running"])))
    if active >= 2:
        fail(429, "investigation_limit", "Wait for an active investigation to finish or cancel it.")
    run = Investigation(id=uid(), collection_id=collection.id, claim=body.claim, collection_revision=collection.revision, source_manifest=[{"id": d.id, "title": d.title, "checksum": d.checksum} for d in included], excluded_sources=[{"id": d.id, "title": d.title, "state": d.state} for d in excluded])
    session.add(run)
    session.flush()
    job = add_job(session, collection.id, "investigate", run.id, request_hash, idempotency_key)
    session.commit()
    return {"id": run.id, "job": job_dict(job)}


@app.get("/api/v1/collections/{collection_id}/investigations")
def investigations(collection_id: str, cursor: str | None = None, limit: int = Query(20, ge=1, le=100), session: SASession = DB, owner: str = Owner):
    collection_for(session, collection_id, owner)
    rows = list(session.scalars(page_query(select(Investigation).where(Investigation.collection_id == collection_id), Investigation, cursor, limit)))
    return page_result(rows, limit, lambda r: {"id": r.id, "claim": r.claim, "outcome": r.outcome, "stale": r.stale, "created_at": r.created_at.isoformat()})


@app.get("/api/v1/investigations/{run_id}", response_model=InvestigationOut)
def get_investigation(run_id: str, session: SASession = DB, owner: str = Owner):
    # Serialize against worker publication/deletion before refreshing the already-loaded run.
    # Under READ COMMITTED, separate reads could otherwise mix old run data with new jobs/findings.
    return run_dict(session, investigation_for(session, run_id, owner, lock=True))


@app.put("/api/v1/findings/{finding_id}/review")
def review(finding_id: str, body: ReviewInput, session: SASession = DB, owner: str = Owner):
    finding = session.get(Finding, finding_id)
    if not finding:
        fail(404, "not_found", "This finding is unavailable.")
    run = investigation_for(session, finding.investigation_id, owner, lock=True)
    session.refresh(finding, with_for_update=True)
    if run.stale:
        fail(409, "stale_investigation", "Sources changed. Start a new investigation before review or export.")
    if body.expected_revision != finding.revision:
        fail(409, "revision_conflict", "This finding changed. Reload it before saving.")
    finding.decision, finding.note = body.decision, body.note
    finding.revision += 1
    run.review_revision += 1
    session.add(ReviewEvent(finding_id=finding.id, decision=finding.decision, note=finding.note, revision=finding.revision))
    session.commit()
    return run_dict(session, run)


@app.get("/api/v1/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, session: SASession = DB, owner: str = Owner):
    return job_dict(job_for(session, job_id, owner))


@app.get("/api/v1/jobs/{job_id}/events")
def job_events(job_id: str, session: SASession = DB, owner: str = Owner):
    job_for(session, job_id, owner)
    return {"items": [{"id": e.id, "state": e.state, "created_at": e.created_at.isoformat()} for e in session.scalars(select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.id).limit(100))]}


@app.post("/api/v1/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, session: SASession = DB, owner: str = Owner):
    job = job_for(session, job_id, owner, lock=True)
    if job.kind.startswith("delete"):
        fail(409, "cleanup_required", "Deletion cleanup cannot be cancelled.")
    if job.state in {"queued", "running"}:
        job.cancel_requested = True
        if job.state == "queued":
            job.state = "cancelled"
            job.stage = "cancelled"
            job.finished_at = now()
            if job.kind == "ingest":
                doc = session.get(Document, job.resource_id)
                doc.state = "cancelled"
            session.add(JobEvent(job_id=job.id, state="cancellation_requested"))
        session.commit()
    return job_dict(job)


@app.post("/api/v1/jobs/{job_id}/retry-cleanup", status_code=202, response_model=JobOut)
def retry_cleanup(job_id: str, session: SASession = DB, owner: str = Owner):
    old = job_for(session, job_id, owner, lock=True)
    if not old.kind.startswith("delete") or old.state != "failed":
        fail(409, "invalid_state", "Only failed deletion cleanup can be retried here.")
    active = session.scalar(select(Job).where(Job.collection_id == old.collection_id, Job.resource_id == old.resource_id, Job.kind == old.kind, Job.state.in_(["queued", "running"])))
    if active:
        return job_dict(active)
    job = add_job(session, old.collection_id, old.kind, old.resource_id, old.request_hash)
    session.commit()
    return job_dict(job)


def md_escape(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("[", "\\[").replace("]", "\\]")


@app.get("/api/v1/investigations/{run_id}/export")
def export(run_id: str, expected_revision: int = Query(ge=0), draft: bool = False, session: SASession = DB, owner: str = Owner):
    run = investigation_for(session, run_id, owner, lock=True)
    result = run_dict(session, run)
    if run.stale or run.review_revision != expected_revision:
        fail(409, "stale_export", "Sources or review decisions changed. Reload the investigation before exporting.")
    if result["job"]["state"] != "succeeded":
        fail(409, "run_not_complete", "Wait for a successful investigation before exporting.")
    accepted = [f for f in result["findings"] if f["decision"] == "accepted"]
    if not accepted and not draft:
        fail(409, "review_required", "Accept evidence first, or explicitly request a draft export.")
    findings = [f for f in result["findings"] if f["decision"] != "dismissed"] if draft else accepted
    lines = ["# EvidenceLens — cited brief", "", "**DRAFT / NOT FULLY REVIEWED**" if draft else "**Analyst-reviewed evidence**", "", "Mode: FIXTURE — synthetic sources; no live model was called.", f"Investigation: {run.id}", f"Review revision: {run.review_revision}", f"Analysis: {run.analysis_version}", f"Unreviewed findings: {sum(f['decision'] == 'unreviewed' for f in result['findings'])}", "", "## Claim", "", md_escape(run.claim), "", f"Outcome in selected sources: {run.outcome}", "", "## Evidence", ""]
    for i, finding in enumerate(findings, 1):
        lines += [f"### {i}. {finding['relation'].title()} — {md_escape(finding['document_title'])}", "", "> " + md_escape(finding["quote"]).replace("\n", "\n> "), "", md_escape(finding["explanation"]), "", f"Lines {finding['line_start']}–{finding['line_end']}; passage {finding['passage_id']}; review: {finding['decision']}.", "", f"[Open local source]({settings.app_origin}/?collection={run.collection_id}&document={finding['document_id']}&passage={finding['passage_id']})", ""]
        if finding["note"]:
            lines += ["Reviewer note: " + md_escape(finding["note"]), ""]
    lines += ["## Source register", ""]
    for source in run.source_manifest:
        lines += [f"- {md_escape(source['title'])} — SHA-256: {source['checksum']}"]
    if run.excluded_sources:
        lines += ["", "Excluded from this run:"] + ["- " + md_escape(d["title"]) + " (" + d["state"] + ")" for d in run.excluded_sources]
    lines += ["", "## Limitations", "", run.limitations or "", "", "Source links require this local installation and retained sources. Downloaded exports cannot be recalled by deletion. This brief reports selected document evidence, not exhaustive fact-checking.", ""]
    return Response("\n".join(lines), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="evidencelens-{run.id[:8]}-r{run.review_revision}.md"'})
