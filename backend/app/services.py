from hashlib import sha256
from pathlib import Path
import re

from fastapi import HTTPException
from sqlalchemy import select

from .config import settings
from .models import Collection, Document, Finding, Investigation, Job, JobEvent, Passage, uid


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
    collection_for(session, job.collection_id, owner, lock=lock, include_deleted=True)
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
    if not re.fullmatch(r"[a-f0-9-]{36}\.txt", key):
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


def add_job(session, collection_id, kind, resource_id, request_hash, idempotency_key=None):
    if session.scalar(select(Job).where(Job.collection_id == collection_id, Job.state.in_(["queued", "running"])).limit(1).offset(49)):
        fail(429, "queue_limit", "This collection already has 50 pending jobs.")
    job = Job(id=uid(), collection_id=collection_id, kind=kind, resource_id=resource_id, request_hash=request_hash, idempotency_key=idempotency_key)
    session.add(job)
    session.flush()
    session.add(JobEvent(job_id=job.id, state="queued"))
    return job


def store_text(session, collection, filename, data):
    if not filename.lower().endswith(".txt"):
        fail(415, "unsupported_type", "This first slice accepts UTF-8 .txt files. PDF support is scheduled for M3.")
    if len(data) > settings.max_upload:
        fail(413, "upload_too_large", "Text files must be 2 MiB or smaller.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail(422, "invalid_encoding", "Save this file as UTF-8 text and upload it again.")
    if not text.strip() or "\x00" in text:
        fail(422, "invalid_text", "Upload a non-empty text file without null bytes.")
    if len(text) > settings.max_characters:
        fail(413, "text_limit", "The extracted-text limit is 500,000 characters per file.")
    docs = list(session.scalars(select(Document).where(Document.collection_id == collection.id, Document.deleted.is_(False))))
    if len(docs) >= settings.max_documents:
        fail(429, "document_limit", "A collection can contain up to 25 documents.")
    checksum = sha256(data).hexdigest()
    if any(d.checksum == checksum for d in docs):
        fail(409, "duplicate_source", "This exact text is already in the collection.")
    doc = Document(id=uid(), collection_id=collection.id, title=Path(filename).name[:160], checksum=checksum, size=len(data), storage_key=f"{uid()}.txt")
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
    return {k: getattr(job, k) for k in ["id", "collection_id", "kind", "resource_id", "state", "stage", "attempts", "error_code", "cancel_requested"]}


def document_dict(session, doc):
    job = session.scalar(select(Job).where(Job.resource_id == doc.id, Job.kind == "ingest").order_by(Job.created_at.desc()).limit(1))
    return {"id": doc.id, "collection_id": doc.collection_id, "title": doc.title, "checksum": doc.checksum, "size": doc.size, "state": doc.state, "created_at": doc.created_at.isoformat(), "job_id": job.id if job else None, "error_code": job.error_code if job else None}


def run_dict(session, run):
    job = session.scalar(select(Job).where(Job.resource_id == run.id, Job.kind == "investigate").order_by(Job.created_at.desc()).limit(1))
    findings = []
    for finding, passage, doc in session.execute(select(Finding, Passage, Document).join(Passage, Finding.passage_id == Passage.id).join(Document, Passage.document_id == Document.id).where(Finding.investigation_id == run.id, Document.deleted.is_(False)).order_by(Finding.id)):
        findings.append({"id": finding.id, "passage_id": passage.id, "document_id": doc.id, "document_title": doc.title, "relation": finding.relation, "quote": finding.quote, "explanation": finding.explanation, "line_start": passage.line_start, "line_end": passage.line_end, "decision": finding.decision, "note": finding.note, "revision": finding.revision})
    return {"id": run.id, "collection_id": run.collection_id, "claim": run.claim, "mode": run.mode, "outcome": run.outcome, "limitations": run.limitations, "stale": run.stale, "review_revision": run.review_revision, "source_manifest": run.source_manifest, "excluded_sources": run.excluded_sources, "findings": findings, "job": job_dict(job), "created_at": run.created_at.isoformat()}
