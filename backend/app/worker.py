"""At-least-once fixture worker with short claims and fenced publication."""
from datetime import timedelta
from hashlib import sha256
import logging
import re
import signal
import time

from sqlalchemy import delete, or_, select

from .config import settings
from .db import Session
from .fixtures import FixtureUnavailable
from .models import Collection, Document, Finding, Investigation, Job, JobEvent, Passage, ReviewEvent, now, uid
from .providers import AnalysisAdapter, FixtureAdapter
from .services import artifact_path

logger = logging.getLogger("evidencelens.worker")
adapter: AnalysisAdapter = FixtureAdapter()


def split_passages(text):
    result = []
    for match in re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", text):
        start, end = match.span()
        while start < end:
            stop = min(start + 4000, end)
            part = text[start:stop]
            result.append({"text": part, "start_offset": start, "line_start": text.count("\n", 0, start)+1, "line_end": text.count("\n", 0, stop-1)+1, "ordinal": len(result)})
            start = stop
    if len(result) > 5000:
        raise ValueError("passage_limit")
    return result


def claim_job():
    with Session.begin() as session:
        current = now()
        job = session.scalar(select(Job).where(or_(Job.state == "queued", (Job.state == "running") & (Job.lease_until < current))).order_by(Job.created_at, Job.id).with_for_update(skip_locked=True).limit(1))
        if not job:
            return None
        if job.cancel_requested:
            job.state, job.finished_at = "cancelled", current
            if job.kind == "ingest":
                doc = session.get(Document, job.resource_id)
                if doc and not doc.deleted:
                    doc.state = "cancelled"
            session.add(JobEvent(job_id=job.id, state="cancelled"))
            return {"terminal": True}
        if job.attempts >= 3 or (current - job.created_at).total_seconds() > settings.job_deadline_seconds:
            job.state, job.error_code, job.finished_at = "failed", "attempt_or_deadline_limit", current
            if job.kind == "ingest":
                doc = session.get(Document, job.resource_id)
                if doc and not doc.deleted:
                    doc.state = "failed"
            session.add(JobEvent(job_id=job.id, state="failed"))
            return {"terminal": True}
        if job.state == "running":
            session.add(JobEvent(job_id=job.id, state="lease_recovered"))
        job.state = "running"
        job.attempts += 1
        job.lease_token = uid()
        job.lease_until = current + timedelta(seconds=settings.lease_seconds)
        job.stage = {"ingest": "extracting", "investigate": "analyzing"}.get(job.kind, "cleaning")
        session.add(JobEvent(job_id=job.id, state=job.stage))
        return {"id": job.id, "token": job.lease_token, "collection_id": job.collection_id, "kind": job.kind, "resource_id": job.resource_id}


def prepare(claim):
    with Session() as session:
        if claim["kind"] == "ingest":
            doc = session.get(Document, claim["resource_id"])
            if not doc or doc.deleted:
                raise ValueError("source_deleted")
            original = artifact_path(doc.storage_key).read_bytes()
            if sha256(original).hexdigest() != doc.checksum:
                raise ValueError("source_integrity_mismatch")
            content = original.decode("utf-8-sig")
            return split_passages(content)
        if claim["kind"] == "investigate":
            run = session.get(Investigation, claim["resource_id"])
            if run.stale:
                raise ValueError("source_changed")
            ids = [source["id"] for source in run.source_manifest]
            docs = list(session.scalars(select(Document).where(Document.id.in_(ids), Document.collection_id == run.collection_id, Document.deleted.is_(False), Document.state == "ready")))
            if len(docs) != len(ids):
                raise ValueError("source_changed")
            passages = list(session.scalars(select(Passage).where(Passage.document_id.in_(ids), Passage.collection_id == run.collection_id)))
            return adapter.analyze(run.claim, docs, passages)
        return None


def finish(claim, payload=None, error=None):
    with Session.begin() as session:
        collection = session.scalar(select(Collection).where(Collection.id == claim["collection_id"]).with_for_update())
        job = session.scalar(select(Job).where(Job.id == claim["id"]).with_for_update())
        if not job or job.lease_token != claim["token"] or job.state != "running" or job.lease_until <= now():
            return False
        doc = session.get(Document, job.resource_id) if job.kind == "ingest" else None
        cancelled = job.cancel_requested or (collection.deleted and not job.kind.startswith("delete")) or bool(doc and doc.deleted)
        if cancelled:
            job.state = job.stage = "cancelled"
            if doc and not doc.deleted:
                doc.state = "cancelled"
        elif error:
            job.state = job.stage = "failed"
            job.error_code = error
            if doc:
                doc.state = "failed"
        elif job.kind == "ingest":
            session.execute(delete(Passage).where(Passage.document_id == doc.id))
            for part in payload:
                session.add(Passage(document_id=doc.id, collection_id=doc.collection_id, **part))
            doc.state = "ready"
            job.state = "succeeded"
            job.stage = "published"
        elif job.kind == "investigate":
            run = session.get(Investigation, job.resource_id)
            if run.stale or run.collection_revision != collection.revision:
                job.state, job.error_code = "failed", "source_changed"
            else:
                outcome, findings, limitations = payload
                manifest = {s["id"] for s in run.source_manifest}
                for finding in findings:
                    passage = session.get(Passage, finding["passage_id"])
                    if not passage or passage.collection_id != run.collection_id or passage.document_id not in manifest or passage.text[finding["quote_start"]:finding["quote_end"]] != finding["quote"]:
                        raise ValueError("invalid_evidence")
                for finding in findings:
                    session.add(Finding(collection_id=run.collection_id, investigation_id=run.id, **finding))
                run.outcome, run.limitations = outcome, limitations
                job.state, job.stage = "succeeded", "published"
        elif job.kind in {"delete_document", "delete_collection"}:
            docs = list(session.scalars(select(Document).where(Document.collection_id == collection.id, Document.deleted.is_(True)))) if job.kind == "delete_collection" else [session.get(Document, job.resource_id)]
            for source in docs:
                if not source:
                    continue
                passage_ids = select(Passage.id).where(Passage.document_id == source.id)
                finding_ids = select(Finding.id).where(Finding.passage_id.in_(passage_ids))
                session.execute(delete(ReviewEvent).where(ReviewEvent.finding_id.in_(finding_ids)))
                session.execute(delete(Finding).where(Finding.passage_id.in_(passage_ids)))
                session.execute(delete(Passage).where(Passage.document_id == source.id))
                artifact_path(source.storage_key).unlink(missing_ok=True)
                source.state = "deleted"
            job.state, job.stage = "succeeded", "cleaned"
        else:
            job.state, job.error_code = "failed", "unsupported_job"
        job.finished_at = now()
        job.lease_until = None
        session.add(JobEvent(job_id=job.id, state=job.state))
        return True


def run_once():
    claim = claim_job()
    if not claim:
        return False
    if claim.get("terminal"):
        return True
    try:
        finish(claim, prepare(claim))
    except FixtureUnavailable:
        finish(claim, error="fixture_not_available")
    except (ValueError, FileNotFoundError) as exc:
        code = str(exc) if isinstance(exc, ValueError) and str(exc) in {"invalid_evidence", "source_changed", "source_deleted", "passage_limit", "source_integrity_mismatch"} else "source_unavailable"
        finish(claim, error=code)
    except Exception:
        # Leave the job leased for restart/reclaim; do not log imported data or connection strings.
        logger.error("Job attempt failed; lease recovery will retry it. job_id=%s", claim["id"])
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        try:
            if not run_once():
                time.sleep(0.5)
        except Exception:
            logger.error("Worker cannot reach its database; retrying.")
            time.sleep(2)


if __name__ == "__main__":
    main()
