from hashlib import sha256
from pathlib import Path
import re

from fastapi import HTTPException
from sqlalchemy import select

from .config import settings
from .models import Collection, Document, Export, Finding, Investigation, Job, JobEvent, Passage, ProviderCall, uid


def fail(status, code, message):
    raise HTTPException(status, detail={"code": code, "message": message})


def collection_for(session, collection_id, owner, lock=False, include_deleted=False):
    query = select(Collection).where(Collection.id == collection_id, Collection.owner == owner)
    if not include_deleted:
        query = query.where(Collection.deleted.is_(False))
    if lock:
        query = query.with_for_update()
    collection = session.scalar(query)
    if not collection:
        fail(404, "not_found", "This resource is unavailable.")
    return collection


def document_for(session, document_id, owner, lock=False):
    doc = session.get(Document, document_id)
    if not doc or doc.deleted:
        fail(404, "not_found", "This source is unavailable.")
    collection_for(session, doc.collection_id, owner, lock=lock)
    if lock:
        session.refresh(doc)
        if doc.deleted:
            fail(404, "not_found", "This source is unavailable.")
    return doc


def job_for(session, job_id, owner, lock=False):
    job = session.get(Job, job_id)
    if not job:
        fail(404, "not_found", "This job is unavailable.")
    collection = collection_for(session, job.collection_id, owner, lock=lock, include_deleted=True)
    if collection.deleted and not job.kind.startswith("delete"):
        fail(404, "not_found", "This job is unavailable.")
    if lock:
        session.refresh(job, with_for_update=True)
    return job


def investigation_for(session, run_id, owner, lock=False):
    run = session.get(Investigation, run_id)
    if not run:
        fail(404, "not_found", "This investigation is unavailable.")
    collection_for(session, run.collection_id, owner, lock=lock)
    if lock:
        session.refresh(run, with_for_update=True)
    return run


def artifact_path(key):
    if not re.fullmatch(r"[a-f0-9-]{36}\.(txt|pdf|md)", key):
        raise ValueError("invalid_storage_key")
    root = settings.storage_dir
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / key
    if path.is_symlink():
        raise ValueError("invalid_storage_path")
    return path


def invalidate_runs(session, collection_id):
    for run in session.scalars(select(Investigation).where(Investigation.collection_id == collection_id)):
        run.stale = True
    for export in session.scalars(select(Export).where(Export.collection_id == collection_id)):
        export.state = "unavailable"


def add_job(session, collection_id, kind, resource_id, request_hash, idempotency_key=None):
    if not kind.startswith("delete") and session.scalar(select(Job).where(Job.collection_id == collection_id, Job.state.in_(["queued", "running"])).limit(1).offset(49)):
        fail(429, "queue_limit", "This collection already has 50 pending jobs.")
    job = Job(id=uid(), collection_id=collection_id, kind=kind, resource_id=resource_id, request_hash=request_hash, idempotency_key=idempotency_key)
    session.add(job)
    session.flush()
    session.add(JobEvent(job_id=job.id, state="queued"))
    return job


def store_text(session, collection, filename, data, replaces=None):
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".pdf"}:
        fail(415, "unsupported_type", "Upload a UTF-8 .txt file or a text-based PDF.")
    if len(data) > settings.max_upload:
        fail(413, "upload_too_large", "Files must be 20 MiB or smaller.")
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            fail(415, "unsupported_type", "The file does not contain a PDF header.")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            fail(422, "invalid_encoding", "Save this file as UTF-8 text and upload it again.")
        if not text.strip() or "\x00" in text:
            fail(422, "invalid_text", "Upload a non-empty text file without null bytes.")
        if len(text) > settings.max_characters:
            fail(413, "text_limit", "The extracted-text limit is 500,000 characters per file.")
    docs = list(session.scalars(select(Document).where(Document.collection_id == collection.id, Document.deleted.is_(False))))
    if not replaces and len({d.family_id for d in docs}) >= settings.max_documents:
        fail(429, "document_limit", "A collection can contain up to 25 documents.")
    if sum(d.size for d in docs) + len(data) > settings.max_collection_bytes:
        fail(429, "storage_limit", "This collection has reached its 100 MiB source-storage limit, including retained versions.")
    checksum = sha256(data).hexdigest()
    if any(d.checksum == checksum for d in docs):
        fail(409, "duplicate_source", "This exact text is already in the collection.")
    document_id = uid()
    family_id = replaces.family_id if replaces else document_id
    previous = [d for d in docs if d.family_id == family_id]
    if len(previous) >= settings.max_versions:
        fail(429, "version_limit", "A source can retain up to 10 versions. Export needed material or remove the source before starting a new history.")
    for old in previous:
        old.active = False
    doc = Document(id=document_id, family_id=family_id, version=max((d.version for d in previous), default=0)+1, active=True, collection_id=collection.id, title=Path(filename).name[:160], checksum=checksum, size=len(data), storage_key=f"{uid()}{suffix}", media_type="application/pdf" if suffix == ".pdf" else "text/plain")
    path = artifact_path(doc.storage_key)
    session.add(doc)
    session.flush()
    job = add_job(session, collection.id, "ingest", doc.id, checksum)
    collection.revision += 1
    invalidate_runs(session, collection.id)
    try:
        path.write_bytes(data)
        path.chmod(0o600)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return doc, job, path


def job_dict(job):
    result = {k: getattr(job, k) for k in ["id", "collection_id", "kind", "resource_id", "state", "stage", "attempts", "error_code", "cancel_requested", "result_payload"]}
    result["started_at"] = job.started_at.isoformat() if job.started_at else None
    result["finished_at"] = job.finished_at.isoformat() if job.finished_at else None
    return result


def document_dict(session, doc):
    job = session.scalar(select(Job).where(Job.resource_id == doc.id, Job.kind == "ingest").order_by(Job.created_at.desc()).limit(1))
    return {"id": doc.id, "collection_id": doc.collection_id, "title": doc.title, "checksum": doc.checksum, "size": doc.size, "state": doc.state, "created_at": doc.created_at.isoformat(), "job_id": job.id if job else None, "error_code": job.error_code if job else None, "family_id": doc.family_id, "version": doc.version, "active": doc.active, "media_type": doc.media_type, "page_count": doc.page_count, "warnings": doc.warnings, "extraction_version": doc.extraction_version}


def run_dict(session, run):
    job = session.scalar(select(Job).where(Job.resource_id == run.id, Job.kind == "investigate").order_by(Job.created_at.desc()).limit(1))
    findings = []
    for finding, passage, doc in session.execute(select(Finding, Passage, Document).join(Passage, Finding.passage_id == Passage.id).join(Document, Passage.document_id == Document.id).where(Finding.investigation_id == run.id, Document.deleted.is_(False)).order_by(Finding.id)):
        findings.append({"id": finding.id, "passage_id": passage.id, "document_id": doc.id, "document_title": doc.title, "relation": finding.relation, "quote": finding.quote, "explanation": finding.explanation, "line_start": passage.line_start+passage.text[:finding.quote_start].count("\n"), "line_end": passage.line_start+passage.text[:max(finding.quote_start, finding.quote_end-1)].count("\n"), "page_number": passage.page_number, "document_version": doc.version, "decision": finding.decision, "note": finding.note, "revision": finding.revision})
    calls = [{"kind": c.kind, "provider": c.provider, "model": c.model, "state": c.state, "duration_ms": c.duration_ms, "usage": c.usage} for c in session.scalars(select(ProviderCall).where(ProviderCall.job_id == job.id).order_by(ProviderCall.created_at).limit(200))]
    return {"id": run.id, "collection_id": run.collection_id, "claim": run.claim, "mode": run.mode, "outcome": run.outcome, "limitations": run.limitations, "stale": run.stale, "review_revision": run.review_revision, "source_manifest": run.source_manifest, "excluded_sources": run.excluded_sources, "findings": findings, "job": job_dict(job), "created_at": run.created_at.isoformat(), "configuration": run.configuration, "provider_calls": calls, "claim_id": run.claim_id, "claim_revision": run.claim_revision}
