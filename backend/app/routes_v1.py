import asyncio
from hashlib import sha256
import json
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session as SASession

from .config import settings
from .db import owner_dependency, session_dependency
from .exporting import validated_snapshot
from .models import Claim, ClaimRevision, Document, Export, Investigation, Job, Passage, RetrievalHit, uid
from .providers import ProviderError, configuration, embedding_configuration
from .retrieval import index_status
from .schemas import ClaimInput, ExportInput, ExportOut, JobOut, ProviderCheckInput, SuggestInput
from .services import add_job, artifact_path, collection_for, document_dict, document_for, fail, invalidate_runs, investigation_for, job_dict, store_text

router = APIRouter(prefix="/api/v1")
DB, Owner = Depends(session_dependency), Depends(owner_dependency)


@router.get("/documents/{document_id}/content")
def original(document_id: str, session: SASession = DB, owner: str = Owner):
    doc = document_for(session, document_id, owner, lock=True)
    try:
        data = artifact_path(doc.storage_key).read_bytes()
    except FileNotFoundError:
        fail(409, "source_unavailable", "The stored original is unavailable. Restore it or remove the source.")
    if sha256(data).hexdigest() != doc.checksum:
        fail(409, "source_integrity_mismatch", "The stored original no longer matches its checksum.")
    return Response(data, media_type=doc.media_type, headers={"Content-Disposition": f'inline; filename="source-{doc.id}.{"pdf" if doc.media_type == "application/pdf" else "txt"}"', "Accept-Ranges": "none"})


@router.get("/documents/{document_id}/versions")
def versions(document_id: str, session: SASession = DB, owner: str = Owner):
    doc = document_for(session, document_id, owner)
    rows = session.scalars(select(Document).where(Document.collection_id == doc.collection_id, Document.family_id == doc.family_id, Document.deleted.is_(False)).order_by(Document.version.desc()).limit(settings.max_versions))
    return {"items": [document_dict(session, row) for row in rows], "next_cursor": None}


@router.post("/documents/{document_id}/versions", status_code=202)
async def replacement(document_id: str, request: Request, x_filename: str = Header(default="replacement.txt"), session: SASession = DB, owner: str = Owner):
    doc = document_for(session, document_id, owner)
    data = bytearray()
    try:
        async with asyncio.timeout(60):
            async for chunk in request.stream():
                if len(data)+len(chunk) > settings.max_upload:
                    fail(413, "upload_too_large", "Files must be 20 MiB or smaller.")
                data.extend(chunk)
    except TimeoutError:
        fail(408, "upload_timeout", "The upload exceeded its 60-second receive window.")
    collection = collection_for(session, doc.collection_id, owner, lock=True)
    path = None
    try:
        new, job, path = store_text(session, collection, unquote(x_filename), bytes(data), replaces=doc)
        session.commit()
    except Exception:
        session.rollback()
        if path:
            path.unlink(missing_ok=True)
        raise
    return {"document": document_dict(session, new), "job": job_dict(job)}


@router.post("/documents/{document_id}/activate")
def activate(document_id: str, session: SASession = DB, owner: str = Owner):
    doc = document_for(session, document_id, owner, lock=True)
    if doc.state != "ready":
        fail(409, "source_not_ready", "Only a successfully ingested version can be activated.")
    collection = collection_for(session, doc.collection_id, owner)
    for version in session.scalars(select(Document).where(Document.family_id == doc.family_id, Document.collection_id == doc.collection_id)):
        version.active = False
    session.flush()
    doc.active = True
    collection.revision += 1
    invalidate_runs(session, collection.id)
    session.commit()
    return document_dict(session, doc)


@router.get("/passages/{passage_id}")
def passage(passage_id: str, session: SASession = DB, owner: str = Owner):
    row = session.get(Passage, passage_id)
    if not row:
        fail(404, "not_found", "This passage is unavailable.")
    doc = document_for(session, row.document_id, owner)
    return {"id": row.id, "document_id": doc.id, "page_number": row.page_number, "text": row.text, "line_start": row.line_start, "line_end": row.line_end}


@router.get("/collections/{collection_id}/index-status")
def search_status(collection_id: str, session: SASession = DB, owner: str = Owner):
    collection_for(session, collection_id, owner)
    try:
        return index_status(session, collection_id)
    except ProviderError as exc:
        return {"ready": False, "expected": 0, "indexed": 0, "configuration_error": exc.code, "fingerprint": None}


@router.post("/collections/{collection_id}/reindex", status_code=202, response_model=JobOut)
def reindex(collection_id: str, session: SASession = DB, owner: str = Owner):
    collection = collection_for(session, collection_id, owner, lock=True)
    try:
        profile = embedding_configuration()
    except ProviderError as exc:
        fail(503, exc.code, "Configure the embedding provider before rebuilding the index.")
    existing = session.scalar(select(Job).where(Job.collection_id == collection.id, Job.kind == "reindex", Job.state.in_(["queued", "running"])))
    if existing:
        return job_dict(existing)
    job = add_job(session, collection.id, "reindex", collection.id, profile["fingerprint"])
    job.result_payload = {"fingerprint": profile["fingerprint"], "collection_revision": collection.revision}
    session.commit()
    return job_dict(job)


@router.post("/provider-checks", status_code=202, response_model=JobOut)
def check_provider(body: ProviderCheckInput, session: SASession = DB, owner: str = Owner):
    collection = collection_for(session, body.collection_id, owner, lock=True)
    try:
        config = configuration()
    except ProviderError as exc:
        fail(503, exc.code, "Configure the provider's model, endpoint, and required server-side keys.")
    existing = session.scalar(select(Job).where(Job.collection_id == collection.id, Job.kind == "provider_check", Job.state.in_(["queued", "running"])))
    if existing:
        return job_dict(existing)
    job = add_job(session, collection.id, "provider_check", collection.id, sha256(json.dumps(config, sort_keys=True).encode()).hexdigest())
    session.commit()
    return job_dict(job)


@router.post("/collections/{collection_id}/claim-suggestions", status_code=202, response_model=JobOut)
def suggestions(collection_id: str, body: SuggestInput, session: SASession = DB, owner: str = Owner):
    collection = collection_for(session, collection_id, owner, lock=True)
    row = session.get(Passage, body.passage_id)
    if not row or row.collection_id != collection.id:
        fail(404, "not_found", "This passage is unavailable.")
    document_for(session, row.document_id, owner)
    job = add_job(session, collection.id, "claims", row.id, sha256(row.text.encode()).hexdigest())
    session.commit()
    return job_dict(job)


@router.get("/collections/{collection_id}/claims")
def claims(collection_id: str, cursor: str | None = None, limit: int = Query(50, ge=1, le=100), session: SASession = DB, owner: str = Owner):
    collection_for(session, collection_id, owner)
    query = select(Claim).where(Claim.collection_id == collection_id)
    if cursor:
        query = query.where(Claim.id > cursor)
    rows = list(session.scalars(query.order_by(Claim.id).limit(limit+1)))
    return {"items": [{"id": c.id, "text": c.text, "revision": c.revision} for c in rows[:limit]], "next_cursor": rows[limit-1].id if len(rows) > limit else None}


@router.post("/collections/{collection_id}/claims", status_code=201)
def create_claim(collection_id: str, body: ClaimInput, session: SASession = DB, owner: str = Owner):
    collection_for(session, collection_id, owner, lock=True)
    claim = Claim(id=uid(), collection_id=collection_id, text=body.text.strip(), revision=1)
    if len(claim.text) < 3:
        fail(422, "invalid_claim", "Enter a non-blank claim.")
    session.add(claim)
    session.flush()
    session.add(ClaimRevision(claim_id=claim.id, revision=1, text=claim.text))
    session.commit()
    return {"id": claim.id, "text": claim.text, "revision": claim.revision}


@router.patch("/claims/{claim_id}")
def edit_claim(claim_id: str, body: ClaimInput, session: SASession = DB, owner: str = Owner):
    claim = session.get(Claim, claim_id)
    if not claim:
        fail(404, "not_found", "This claim is unavailable.")
    collection_for(session, claim.collection_id, owner, lock=True)
    session.refresh(claim)
    if claim.revision != body.expected_revision:
        fail(409, "claim_revision_conflict", "Reload this claim before editing it.")
    if len(body.text.strip()) < 3:
        fail(422, "invalid_claim", "Enter a non-blank claim.")
    claim.text, claim.revision = body.text.strip(), claim.revision+1
    session.add(ClaimRevision(claim_id=claim.id, revision=claim.revision, text=claim.text))
    session.commit()
    return {"id": claim.id, "text": claim.text, "revision": claim.revision}


def export_dict(session, row):
    job = session.scalar(select(Job).where(Job.kind == "export", Job.resource_id == row.id).order_by(Job.created_at.desc()).limit(1))
    return {"id": row.id, "investigation_id": row.investigation_id, "review_revision": row.review_revision, "draft": row.draft, "mode": row.mode, "state": row.state, "checksum": row.checksum, "created_at": row.created_at.isoformat(), "job": job_dict(job)}


@router.post("/investigations/{run_id}/exports", status_code=202, response_model=ExportOut)
def create_export(run_id: str, body: ExportInput, idempotency_key: str | None = Header(default=None, max_length=100), session: SASession = DB, owner: str = Owner):
    run = investigation_for(session, run_id, owner, lock=True)
    snapshot = validated_snapshot(session, run, body.expected_revision, body.draft)
    digest = sha256(json.dumps({"run_id": run_id, **body.model_dump()}, sort_keys=True).encode()).hexdigest()
    if idempotency_key:
        old = session.scalar(select(Job).where(Job.collection_id == run.collection_id, Job.kind == "export", Job.idempotency_key == idempotency_key))
        if old:
            if old.request_hash != digest:
                fail(409, "idempotency_conflict", "That key was used with another export request.")
            return export_dict(session, session.get(Export, old.resource_id))
    if session.scalar(select(func.count()).select_from(Export).where(Export.collection_id == run.collection_id)) >= 100:
        fail(429, "export_limit", "This collection has reached its 100-export retention limit.")
    row = Export(id=uid(), collection_id=run.collection_id, investigation_id=run.id, review_revision=body.expected_revision, draft=body.draft, mode=run.mode, snapshot=snapshot, storage_key=f"{uid()}.md")
    session.add(row)
    session.flush()
    add_job(session, run.collection_id, "export", row.id, digest, idempotency_key)
    session.commit()
    return export_dict(session, row)


@router.get("/investigations/{run_id}/exports")
def exports(run_id: str, session: SASession = DB, owner: str = Owner):
    run = investigation_for(session, run_id, owner)
    rows = session.scalars(select(Export).where(Export.investigation_id == run.id).order_by(Export.created_at.desc()).limit(100))
    return {"items": [export_dict(session, row) for row in rows], "next_cursor": None}


def export_for(session, export_id, owner, lock=False):
    row = session.get(Export, export_id)
    if not row:
        fail(404, "not_found", "This export is unavailable.")
    run = investigation_for(session, row.investigation_id, owner, lock=lock)
    if lock:
        session.refresh(row)
    return row, run


@router.get("/exports/{export_id}", response_model=ExportOut)
def get_export(export_id: str, session: SASession = DB, owner: str = Owner):
    row, _ = export_for(session, export_id, owner, lock=True)
    return export_dict(session, row)


@router.get("/exports/{export_id}/download")
def download(export_id: str, session: SASession = DB, owner: str = Owner):
    row, run = export_for(session, export_id, owner, lock=True)
    if run.stale or row.state != "ready":
        fail(409, "export_unavailable", "This export is pending, failed, or invalidated by source changes.")
    try:
        content = artifact_path(row.storage_key).read_bytes()
    except FileNotFoundError:
        fail(409, "export_unavailable", "The stored export is unavailable.")
    if sha256(content).hexdigest() != row.checksum:
        fail(409, "export_integrity_mismatch", "The stored export no longer matches its checksum.")
    return Response(content, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="evidencelens-{run.id[:8]}-r{row.review_revision}.md"'})


@router.get("/investigations/{run_id}/trace")
def trace(run_id: str, session: SASession = DB, owner: str = Owner):
    run = investigation_for(session, run_id, owner, lock=True)
    hits = session.scalars(select(RetrievalHit).where(RetrievalHit.investigation_id == run.id).order_by(RetrievalHit.method, RetrievalHit.rank).limit(80))
    return {"configuration": run.configuration, "embedding_profile_id": run.embedding_profile_id, "hits": [{"passage_id": h.passage_id, "method": h.method, "rank": h.rank, "score": h.score, "in_context": h.in_context} for h in hits]}
