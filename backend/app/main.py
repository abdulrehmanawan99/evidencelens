import base64
import asyncio
import os
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
from .fixtures import CLAIMS, PDF_DIRECTORY, SOURCES
from .models import Claim, ClaimRevision, Collection, Document, Export, Finding, Investigation, Job, JobEvent, Passage, ReviewEvent, now, uid
from .providers import ProviderError, configuration
from .retrieval import index_status
from .exporting import make_snapshot, render_markdown
from .schemas import CollectionInput, CollectionOut, DocumentOut, InvestigationInput, InvestigationOut, JobOut, ReviewInput, SourceOut
from .services import add_job, collection_for, document_dict, document_for, fail, invalidate_runs, investigation_for, job_dict, job_for, run_dict, store_text

app = FastAPI(title="EvidenceLens", version="1.0.0", description="Private, source-grounded PDF/text investigations with explicit fixture and live-provider modes.")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts.split(","))
DB = Depends(session_dependency)
Owner = Depends(owner_dependency)


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    request_id = uid()
    origin = request.headers.get("origin")
    allowed = {settings.app_origin, os.getenv("API_ORIGIN", "http://127.0.0.1:8000")}
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
    counts = dict(session.execute(select(Document.state, func.count()).where(Document.collection_id == collection.id, Document.deleted.is_(False), Document.active.is_(True)).group_by(Document.state)).all())
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
    return {"status": "ready", "mode": settings.model_mode}


@app.get("/api/v1/provider-status")
def provider_status():
    try:
        config, error = configuration(), None
    except ProviderError as exc:
        config, error = {}, exc.code
    fixture = settings.model_mode == "fixture"
    return {"mode": settings.model_mode, "provider": config.get("generation_model", "unconfigured"), "live_enabled": not fixture and not error, "configured": not error, "configuration_error": error, "embedding": config.get("embedding"), "supported_claims": CLAIMS if fixture else [], "message": "Predefined synthetic scenarios with a lexical demo index; no live model calls." if fixture else "Document excerpts are sent to the server-configured provider. Results require review.", "accepted_types": ["text/plain", "application/pdf"], "max_upload_bytes": settings.max_upload}


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
def sample(format: str = Query(default="txt", pattern="^(txt|pdf)$"), session: SASession = DB, owner: str = Owner):
    collection = Collection(title="Harbor Transit · Q2 review"+(" · PDF" if format == "pdf" else ""), owner=owner)
    session.add(collection)
    session.flush()
    paths = []
    try:
        for index, (filename, content) in enumerate(SOURCES, 1):
            data = (PDF_DIRECTORY / f"{index}.pdf").read_bytes() if format == "pdf" else content.encode()
            _, _, path = store_text(session, collection, filename.removesuffix(".txt")+".pdf" if format == "pdf" else filename, data)
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
    docs = session.scalars(select(Document).where(Document.collection_id == collection_id, Document.deleted.is_(False), Document.active.is_(True)).order_by(Document.created_at, Document.id).limit(25))
    return {"items": [document_dict(session, doc) for doc in docs], "next_cursor": None}


@app.post("/api/v1/collections/{collection_id}/documents", status_code=202)
async def upload(collection_id: str, request: Request, x_filename: str = Header(default="upload.txt"), session: SASession = DB, owner: str = Owner):
    # Stream the raw file body; this avoids an unbounded multipart spool before validation.
    collection = collection_for(session, collection_id, owner)
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type not in {"text/plain", "application/pdf", "application/octet-stream"}:
        fail(415, "unsupported_type", "Upload a UTF-8 .txt file or a text-based PDF.")
    data = bytearray()
    try:
        async with asyncio.timeout(60):
            async for chunk in request.stream():
                if len(data)+len(chunk) > settings.max_upload:
                    fail(413, "upload_too_large", "Files must be 20 MiB or smaller.")
                data.extend(chunk)
    except TimeoutError:
        fail(408, "upload_timeout", "The upload exceeded its 60-second receive window.")
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
def source(document_id: str, after: int = Query(-1, ge=-1), passage_id: str | None = None, page: int | None = Query(default=None, ge=1, le=100), session: SASession = DB, owner: str = Owner):
    doc = document_for(session, document_id, owner, lock=True)
    if page is None and doc.media_type == "application/pdf":
        page = 1
    if passage_id:
        target = session.scalar(select(Passage).where(Passage.id == passage_id, Passage.document_id == doc.id))
        if not target:
            fail(404, "not_found", "This passage is unavailable.")
        after = target.ordinal - 1
        page = target.page_number
    query = select(Passage).where(Passage.document_id == doc.id, Passage.ordinal > after)
    if page is not None:
        if page > doc.page_count:
            fail(422, "invalid_page", "This page is outside the source document.")
        query = query.where(Passage.page_number == page)
    passages = list(session.scalars(query.order_by(Passage.ordinal).limit(101)))
    more = len(passages) > 100
    passages = passages[:100]
    return {"document": document_dict(session, doc), "page_number": page or 1, "passages": [{k: getattr(p, k) for k in ["id", "text", "line_start", "line_end", "start_offset", "ordinal", "page_number"]} for p in passages], "next_after": passages[-1].ordinal if more else None}


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
    for old in session.scalars(select(Job).where(Job.collection_id == collection.id, Job.kind == "claims")):
        old.result_payload = None
    for job in session.scalars(select(Job).where(Job.collection_id == collection.id, Job.state.in_(["queued", "running"]))):
        if job.kind.startswith("delete"):
            continue
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
    versions = list(session.scalars(select(Document).where(Document.family_id == doc.family_id, Document.collection_id == doc.collection_id, Document.deleted.is_(False))))
    tombstone(session, collection, versions)
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
    try:
        config = configuration()
    except ProviderError as exc:
        fail(503, exc.code, "Configure and check the selected model and embedding providers before analysis.")
    docs = list(session.scalars(select(Document).where(Document.collection_id == collection.id, Document.deleted.is_(False), Document.active.is_(True))))
    included = [d for d in docs if d.state == "ready"]
    excluded = [d for d in docs if d.state != "ready"]
    if excluded and not body.allow_partial:
        fail(409, "collection_not_ready", "Wait for every source, or explicitly choose to analyze ready sources only.")
    if not included:
        fail(409, "no_ready_sources", "Upload a source and wait for ingestion before investigating.")
    active = session.scalar(select(func.count()).select_from(Job).where(Job.collection_id == collection.id, Job.kind == "investigate", Job.state.in_(["queued", "running"])))
    if active >= 2:
        fail(429, "investigation_limit", "Wait for an active investigation to finish or cancel it.")
    if body.claim_id:
        confirmed_claim = session.scalar(select(Claim).where(Claim.id == body.claim_id, Claim.collection_id == collection.id))
        if not confirmed_claim:
            fail(404, "not_found", "This claim is unavailable.")
        if confirmed_claim.revision != body.expected_claim_revision or confirmed_claim.text != body.claim:
            fail(409, "claim_revision_conflict", "Reload or save the claim's current revision before investigating.")
    else:
        confirmed_claim = session.scalar(select(Claim).where(Claim.collection_id == collection.id, Claim.text == body.claim).order_by(Claim.created_at).limit(1))
        if not confirmed_claim:
            confirmed_claim = Claim(id=uid(), collection_id=collection.id, text=body.claim, revision=1)
            session.add(confirmed_claim)
            session.flush()
            session.add(ClaimRevision(claim_id=confirmed_claim.id, revision=1, text=body.claim))
    run = Investigation(id=uid(), collection_id=collection.id, claim=body.claim, claim_id=confirmed_claim.id, claim_revision=confirmed_claim.revision, collection_revision=collection.revision, configuration=config, mode=settings.model_mode, analysis_version=settings.analysis_version, source_manifest=[{"id": d.id, "title": d.title, "checksum": d.checksum, "version": d.version, "family_id": d.family_id, "media_type": d.media_type, "page_count": d.page_count, "warnings": d.warnings} for d in included], excluded_sources=[{"id": d.id, "title": d.title, "state": d.state} for d in excluded])
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
            elif job.kind == "export":
                session.get(Export, job.resource_id).state = "unavailable"
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


@app.get("/api/v1/investigations/{run_id}/export", deprecated=True)
def export(run_id: str, expected_revision: int = Query(ge=0), draft: bool = False, session: SASession = DB, owner: str = Owner):
    # Compatibility download; the UI uses persisted export jobs/revisions.
    from .exporting import validated_snapshot
    run = investigation_for(session, run_id, owner, lock=True)
    snapshot = validated_snapshot(session, run, expected_revision, draft)
    return Response(render_markdown(snapshot, settings.app_origin), media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="evidencelens-{run.id[:8]}-r{run.review_revision}.md"'})


from .routes_v1 import router
app.include_router(router)
