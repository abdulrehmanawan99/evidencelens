"""Durable bounded jobs, renewed leases, fenced publication, and idempotent cleanup."""
from datetime import timedelta
from hashlib import sha256
import logging
from pathlib import Path
import shutil
import signal
import threading
import time

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from .config import settings
from .db import Session
from .extraction import extract, split_passages
from .exporting import render_markdown
from .fixtures import CHECKSUMS, FixtureUnavailable
from .models import Claim, ClaimRevision, Collection, Document, EmbeddingProfile, Export, Finding, Investigation, Job, JobEvent, Passage, PassageEmbedding, ProviderCall, RetrievalHit, ReviewEvent, now, uid
from .providers import ProviderError, analysis_adapter, configuration, embed_texts, embedding_configuration, suggest_claims
from .retrieval import ensure_profile, retrieve
from .services import artifact_path

logger = logging.getLogger("evidencelens.worker")


class Cancelled(Exception):
    pass


def deadline_seconds(kind):
    return settings.ingestion_deadline_seconds if kind in {"ingest", "reindex"} else settings.job_deadline_seconds


def claim_job():
    with Session.begin() as session:
        current = now()
        job = session.scalar(select(Job).where(or_(Job.state == "queued", (Job.state == "running") & (Job.lease_until < current))).order_by(Job.created_at, Job.id).with_for_update(skip_locked=True).limit(1))
        if not job:
            return None
        terminal = None
        if not job.started_at:
            job.started_at = current
        if job.attempts >= 3 or (current-job.started_at).total_seconds() >= deadline_seconds(job.kind):
            terminal = "attempt_or_deadline_limit"
        if job.state == "running":
            session.add(JobEvent(job_id=job.id, state="lease_recovered"))
        job.state, job.stage = "running", "starting"
        if not terminal:
            job.attempts += 1
        job.lease_token = uid()
        job.lease_until = current+timedelta(seconds=settings.lease_seconds)
        session.add(JobEvent(job_id=job.id, state="starting"))
        return {"id": job.id, "token": job.lease_token, "collection_id": job.collection_id, "kind": job.kind, "resource_id": job.resource_id, "terminal": terminal}


class JobControl:
    def __init__(self, claim):
        self.claim = claim
        self.stopping = threading.Event()
        self.thread = None

    def check(self):
        with Session() as session:
            job = session.get(Job, self.claim["id"])
            if not job or job.state != "running" or job.lease_token != self.claim["token"] or not job.lease_until or job.lease_until <= now():
                raise ProviderError("lease_lost")
            if job.cancel_requested:
                raise Cancelled()
            if job.started_at and (now()-job.started_at).total_seconds() >= deadline_seconds(job.kind):
                raise ProviderError("job_deadline")

    def remaining(self):
        with Session() as session:
            job = session.get(Job, self.claim["id"])
            return max(0.1, deadline_seconds(job.kind)-(now()-job.started_at).total_seconds())

    def stage(self, value):
        self.check()
        with Session.begin() as session:
            collection = session.scalar(select(Collection).where(Collection.id == self.claim["collection_id"]).with_for_update())
            job = session.scalar(select(Job).where(Job.id == self.claim["id"]).with_for_update())
            if job.lease_token != self.claim["token"] or job.state != "running" or job.cancel_requested:
                raise Cancelled()
            job.stage = value
            session.add(JobEvent(job_id=job.id, state=value))
            if job.kind == "ingest":
                doc = session.get(Document, job.resource_id)
                if doc and not doc.deleted:
                    doc.state = "running"

    def before_request(self):
        self.check()
        with Session() as session:
            count = session.scalar(select(func.count()).select_from(ProviderCall).where(ProviderCall.job_id == self.claim["id"]))
        if count >= (200 if self.claim["kind"] in {"ingest", "reindex"} else 6):
            raise ProviderError("provider_call_budget")

    def record(self, **kwargs):
        with Session.begin() as session:
            session.add(ProviderCall(job_id=self.claim["id"], **kwargs))

    def start(self):
        def heartbeat():
            while not self.stopping.wait(max(1, settings.lease_seconds/3)):
                try:
                    with Session.begin() as session:
                        session.execute(update(Job).where(Job.id == self.claim["id"], Job.lease_token == self.claim["token"], Job.state == "running", Job.cancel_requested.is_(False), Job.lease_until > now()).values(lease_until=now()+timedelta(seconds=settings.lease_seconds)))
                except Exception:
                    logger.error("Lease renewal failed. job_id=%s", self.claim["id"])
        self.thread = threading.Thread(target=heartbeat, daemon=True)
        self.thread.start()

    def close(self):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=1)


def prepare(claim, control=None):
    control = control or JobControl(claim)
    control.check()
    kind = claim["kind"]
    if kind == "ingest":
        control.stage("extracting")
        with Session() as session:
            doc = session.get(Document, claim["resource_id"])
            if not doc or doc.deleted:
                raise ValueError("source_deleted")
            path, checksum, media_type = artifact_path(doc.storage_key), doc.checksum, doc.media_type
            pending = session.get(Job, claim["id"]).result_payload or {}
            if pending.get("embedding_fingerprint") and pending["embedding_fingerprint"] != embedding_configuration()["fingerprint"]:
                raise ProviderError("provider_configuration_changed")
        result = extract(path, checksum, media_type, control.check)
        with Session() as session:
            existing = session.scalar(select(func.count()).select_from(Passage).join(Document, Passage.document_id == Document.id).where(Passage.collection_id == claim["collection_id"], Document.active.is_(True), Document.deleted.is_(False), Document.id != claim["resource_id"]))
        if existing+len(result["passages"]) > settings.max_passages:
            raise ValueError("passage_limit")
        for passage in result["passages"]:
            passage["id"] = uid()
        control.stage("embedding")
        profile, vectors = embed_texts([part["text"] for part in result["passages"]], control)
        return {"extraction": result, "profile": profile, "vectors": vectors}
    if kind == "investigate":
        control.stage("retrieving")
        with Session() as session:
            run = session.get(Investigation, claim["resource_id"])
            if run.stale:
                raise ValueError("source_changed")
            current = configuration()
            if run.configuration and current != run.configuration:
                raise ProviderError("provider_configuration_changed")
            ids = [source["id"] for source in run.source_manifest]
            docs = list(session.scalars(select(Document).where(Document.id.in_(ids), Document.collection_id == run.collection_id, Document.deleted.is_(False), Document.state == "ready")))
            if len(docs) != len(ids):
                raise ValueError("source_changed")
            profile, passages, trace = retrieve(session, run.collection_id, ids, run.claim, control)
            claim_text = run.claim
        control.stage("analyzing")
        if passages:
            analysis = analysis_adapter().analyze(claim_text, docs, passages, control)
        else:
            analysis = ("insufficient_evidence", [], "No passages fit the configured retrieval/context budget. This does not establish that the claim is false.")
        control.check()
        return {"analysis": analysis, "profile_id": profile.id, "trace": trace, "context_ids": [p.id for p in passages]}
    if kind == "reindex":
        control.stage("embedding")
        with Session() as session:
            job = session.get(Job, claim["id"])
            payload = job.result_payload or {}
            if payload.get("fingerprint") != embedding_configuration()["fingerprint"]:
                raise ProviderError("provider_configuration_changed")
            collection = session.get(Collection, claim["collection_id"])
            passages = list(session.scalars(select(Passage).join(Document, Passage.document_id == Document.id).where(Passage.collection_id == collection.id, Document.active.is_(True), Document.deleted.is_(False), Document.state == "ready").order_by(Passage.id).limit(settings.max_passages+1)))
            revision = collection.revision
            if revision != payload.get("collection_revision") or len(passages) > settings.max_passages:
                raise ValueError("source_changed")
        profile, vectors = embed_texts([p.text for p in passages], control)
        return {"profile": profile, "vectors": vectors, "passage_ids": [p.id for p in passages], "revision": revision}
    if kind == "claims":
        control.stage("suggesting")
        with Session() as session:
            passage = session.get(Passage, claim["resource_id"])
            doc = session.get(Document, passage.document_id) if passage else None
            if not passage or passage.collection_id != claim["collection_id"] or not doc or doc.deleted:
                raise ValueError("source_deleted")
            if settings.model_mode == "fixture" and doc.checksum not in CHECKSUMS:
                raise FixtureUnavailable()
        return suggest_claims(passage, control)
    if kind == "export":
        control.stage("rendering")
        with Session() as session:
            export = session.get(Export, claim["resource_id"])
            run = session.get(Investigation, export.investigation_id)
            if run.stale or export.state == "unavailable":
                raise ValueError("source_changed")
            snapshot = export.snapshot
        return render_markdown(snapshot, settings.app_origin).encode()
    if kind == "provider_check":
        control.stage("checking_provider")
        profile, vectors = embed_texts(["Capability check: an original source passage."], control)
        if settings.model_mode != "fixture":
            from .providers import ClaimSuggestions, generate
            generate(ClaimSuggestions, "Return a JSON object with an empty claims array for this capability test.", "No document is supplied.", control)
        return {"mode": settings.model_mode, "embedding_model": profile["model"], "dimensions": len(vectors[0]), "structured_generation": settings.model_mode != "fixture", "fixture_only": settings.model_mode == "fixture"}
    return None


def cleanup(session, collection, docs):
    removed_ids = {doc.id for doc in docs}
    affected = [run for run in session.scalars(select(Investigation).where(Investigation.collection_id == collection.id)) if collection.deleted or any(s["id"] in removed_ids for s in run.source_manifest+run.excluded_sources)]
    for run in affected:
        finding_ids = select(Finding.id).where(Finding.investigation_id == run.id)
        session.execute(delete(ReviewEvent).where(ReviewEvent.finding_id.in_(finding_ids)))
        session.execute(delete(Finding).where(Finding.investigation_id == run.id))
        session.execute(delete(RetrievalHit).where(RetrievalHit.investigation_id == run.id))
        run.limitations, run.outcome, run.stale = None, None, True
        run.source_manifest = [{**source, "title": "[deleted source]" if source["id"] in removed_ids else source["title"]} for source in run.source_manifest]
        run.excluded_sources = [{**source, "title": "[deleted source]" if source["id"] in removed_ids else source["title"]} for source in run.excluded_sources]
        if collection.deleted:
            run.claim, run.source_manifest, run.excluded_sources = "", [], []
        for export in session.scalars(select(Export).where(Export.investigation_id == run.id)):
            artifact_path(export.storage_key).unlink(missing_ok=True)
            export.snapshot, export.state = {}, "deleted"
    for source in docs:
        passage_ids = select(Passage.id).where(Passage.document_id == source.id)
        session.execute(delete(PassageEmbedding).where(PassageEmbedding.passage_id.in_(passage_ids)))
        session.execute(delete(RetrievalHit).where(RetrievalHit.passage_id.in_(passage_ids)))
        session.execute(delete(Passage).where(Passage.document_id == source.id))
        artifact_path(source.storage_key).unlink(missing_ok=True)
        source.state, source.title, source.warnings = "deleted", "[deleted source]", []
    for job in session.scalars(select(Job).where(Job.collection_id == collection.id)):
        job.result_payload = None
    if collection.deleted:
        claims = select(Claim.id).where(Claim.collection_id == collection.id)
        session.execute(delete(ClaimRevision).where(ClaimRevision.claim_id.in_(claims)))
        session.execute(delete(Claim).where(Claim.collection_id == collection.id))


def finish(claim, payload=None, error=None):
    with Session.begin() as session:
        collection = session.scalar(select(Collection).where(Collection.id == claim["collection_id"]).with_for_update())
        job = session.scalar(select(Job).where(Job.id == claim["id"]).with_for_update())
        if not job or job.lease_token != claim["token"] or job.state != "running" or not job.lease_until or job.lease_until <= now():
            return False
        doc = session.get(Document, job.resource_id) if job.kind == "ingest" else None
        export = session.get(Export, job.resource_id) if job.kind == "export" else None
        cancelled = job.cancel_requested or (collection.deleted and not job.kind.startswith("delete")) or bool(doc and doc.deleted)
        if cancelled:
            job.state = job.stage = "cancelled"
            if doc and not doc.deleted:
                doc.state = "cancelled"
            if export:
                export.state = "unavailable"
        elif error:
            job.state = job.stage = "failed"
            job.error_code = error
            if doc:
                doc.state = "failed"
            if export:
                export.state = "failed"
        elif job.kind == "ingest":
            parts = payload["extraction"]["passages"]
            existing = session.scalar(select(func.count()).select_from(Passage).join(Document, Passage.document_id == Document.id).where(Passage.collection_id == collection.id, Document.active.is_(True), Document.deleted.is_(False), Document.id != doc.id))
            if existing+len(parts) > settings.max_passages:
                raise ValueError("passage_limit")
            profile = ensure_profile(session, payload["profile"])
            for part in parts:
                session.add(Passage(document_id=doc.id, collection_id=doc.collection_id, **part))
            session.flush()
            for part, vector in zip(parts, payload["vectors"], strict=True):
                session.add(PassageEmbedding(passage_id=part["id"], collection_id=doc.collection_id, profile_id=profile.id, vector=vector))
            doc.state, doc.page_count = "ready", len(payload["extraction"]["pages"])
            doc.warnings, doc.extraction_version = payload["extraction"]["warnings"], payload["extraction"]["extraction_version"]
            job.result_payload = {"passages": len(parts), "pages": doc.page_count, "profile_id": profile.id}
            job.state, job.stage = "succeeded", "published"
        elif job.kind == "investigate":
            run = session.get(Investigation, job.resource_id)
            if run.stale or run.collection_revision != collection.revision:
                job.state, job.error_code = "failed", "source_changed"
            else:
                outcome, findings, limitations = payload["analysis"]
                manifest = {s["id"] for s in run.source_manifest}
                for finding in findings:
                    passage = session.get(Passage, finding["passage_id"])
                    if not passage or passage.collection_id != run.collection_id or passage.document_id not in manifest or passage.id not in payload["context_ids"] or passage.text[finding["quote_start"]:finding["quote_end"]] != finding["quote"]:
                        raise ValueError("invalid_evidence")
                for finding in findings:
                    session.add(Finding(collection_id=run.collection_id, investigation_id=run.id, **finding))
                for hit in payload["trace"]:
                    session.add(RetrievalHit(collection_id=run.collection_id, investigation_id=run.id, **hit))
                run.outcome, run.limitations, run.embedding_profile_id = outcome, limitations, payload["profile_id"]
                job.result_payload = {"findings": len(findings), "context_passages": len(payload["context_ids"])}
                job.state, job.stage = "succeeded", "published"
        elif job.kind == "reindex":
            if collection.revision != payload["revision"]:
                job.state, job.error_code = "failed", "source_changed"
            else:
                profile = ensure_profile(session, payload["profile"])
                for passage_id, vector in zip(payload["passage_ids"], payload["vectors"], strict=True):
                    session.execute(insert(PassageEmbedding).values(id=uid(), passage_id=passage_id, collection_id=collection.id, profile_id=profile.id, vector=vector).on_conflict_do_update(index_elements=["passage_id", "profile_id"], set_={"vector": vector}))
                job.result_payload = {"profile_id": profile.id, "passages": len(payload["passage_ids"])}
                job.state, job.stage = "succeeded", "published"
        elif job.kind == "export":
            run = session.get(Investigation, export.investigation_id)
            if run.stale or export.state == "unavailable":
                job.state, job.error_code, export.state = "failed", "source_changed", "unavailable"
            else:
                path = artifact_path(export.storage_key)
                path.write_bytes(payload)
                path.chmod(0o600)
                export.checksum, export.state = sha256(payload).hexdigest(), "ready"
                job.state, job.stage = "succeeded", "published"
        elif job.kind in {"claims", "provider_check"}:
            job.result_payload = payload
            job.state, job.stage = "succeeded", "published"
        elif job.kind in {"delete_document", "delete_collection"}:
            if job.kind == "delete_collection":
                docs = list(session.scalars(select(Document).where(Document.collection_id == collection.id, Document.deleted.is_(True))))
            else:
                source = session.get(Document, job.resource_id)
                docs = list(session.scalars(select(Document).where(Document.collection_id == collection.id, Document.family_id == source.family_id, Document.deleted.is_(True)))) if source else []
            cleanup(session, collection, docs)
            job.state, job.stage = "succeeded", "cleaned"
        else:
            job.state, job.error_code = "failed", "unsupported_job"
        job.finished_at, job.lease_until = now(), None
        session.add(JobEvent(job_id=job.id, state=job.state))
        return True


def run_once():
    claim = claim_job()
    if not claim:
        return False
    control = JobControl(claim)
    control.start()
    try:
        if claim["terminal"]:
            finish(claim, error=claim["terminal"])
        else:
            finish(claim, prepare(claim, control))
    except Cancelled:
        finish(claim)
    except FixtureUnavailable:
        finish(claim, error="fixture_not_available")
    except ProviderError as exc:
        if exc.code != "lease_lost":
            finish(claim, error=exc.code)
    except (ValueError, FileNotFoundError) as exc:
        allowed = {"invalid_evidence", "source_changed", "source_deleted", "source_integrity_mismatch", "passage_limit", "encrypted_pdf", "pdf_page_limit", "parser_decoded_limit", "text_limit", "ocr_required", "malformed_pdf", "parser_memory_limit", "parser_timeout", "parser_resource_limit", "parser_isolation_unavailable"}
        code = str(exc) if isinstance(exc, ValueError) and str(exc) in allowed else "source_unavailable"
        finish(claim, error=code)
    except Exception:
        logger.error("Job attempt failed; lease recovery will retry it. job_id=%s", claim["id"])
    finally:
        control.close()
    return True


def sweep_orphans():
    root = settings.storage_dir
    if not root.exists():
        return
    with Session() as session:
        referenced = set(session.scalars(select(Document.storage_key).where(Document.deleted.is_(False))))
        referenced.update(session.scalars(select(Export.storage_key).where(Export.state != "deleted")))
    threshold = time.time()-settings.temporary_ttl_seconds
    for path in root.iterdir():
        if path.is_symlink():
            continue
        if path.name == ".tmp" and path.is_dir():
            for child in path.iterdir():
                if not child.is_symlink() and child.is_dir() and child.name.startswith("parser-") and child.stat().st_mtime < threshold:
                    shutil.rmtree(child)
        elif path.is_file() and path.stat().st_mtime < threshold and path.name not in referenced:
            try:
                if artifact_path(path.name) == path:
                    path.unlink()
            except ValueError:
                continue


def main():
    logging.basicConfig(level=logging.INFO)
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    last_sweep = 0
    while not stopping:
        try:
            if time.monotonic()-last_sweep > 60:
                sweep_orphans()
                last_sweep = time.monotonic()
            if not run_once():
                time.sleep(0.5)
        except Exception:
            logger.error("Worker cannot reach its database; retrying.")
            time.sleep(2)


if __name__ == "__main__":
    main()
