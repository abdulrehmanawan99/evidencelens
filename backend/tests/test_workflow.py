from datetime import timedelta
from hashlib import sha256
import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db import Session, owner_dependency
from app.fixtures import CLAIMS
from app.main import app
from app.models import Collection, Document, Finding, Job, Passage, ReviewEvent, now
from app.services import artifact_path
from app.worker import claim_job, finish, prepare, run_once, split_passages


def drain():
    for _ in range(80):
        if not run_once():
            return
    raise AssertionError("Queue did not drain")


def seeded(client):
    response = client.post("/api/v1/sample")
    assert response.status_code == 201, response.text
    collection = response.json()
    drain()
    return collection


def analyzed(client, collection, claim=CLAIMS[0], key="test-key"):
    response = client.post(f"/api/v1/collections/{collection['id']}/investigations", json={"claim": claim}, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    drain()
    response = client.get(f"/api/v1/investigations/{run_id}")
    assert response.status_code == 200, response.text
    return response.json()


def test_complete_workflow_review_source_and_export(client):
    collection = seeded(client)
    run = analyzed(client, collection)
    assert run["job"]["state"] == "succeeded"
    assert run["outcome"] == "conflicting_evidence"
    assert {f["relation"] for f in run["findings"]} == {"supports", "conflicts", "context"}
    assert client.get(f"/api/v1/investigations/{run['id']}/export?expected_revision=0").status_code == 409
    finding = next(f for f in run["findings"] if f["relation"] == "supports")
    source = client.get(f"/api/v1/documents/{finding['document_id']}/source?passage_id={finding['passage_id']}").json()
    assert finding["quote"] in source["passages"][0]["text"]
    review = client.put(f"/api/v1/findings/{finding['id']}/review", json={"decision": "accepted", "note": "Checked against the original.", "expected_revision": 0})
    assert review.status_code == 200
    assert review.json()["review_revision"] == 1
    exported = client.get(f"/api/v1/investigations/{run['id']}/export?expected_revision=1")
    assert exported.status_code == 200
    assert finding["quote"] in exported.text
    assert "FIXTURE" in exported.text and "SHA-256" in exported.text
    assert "Checked against the original." in exported.text
    assert "Unreviewed findings: 2" in exported.text
    assert "1.05 million" not in exported.text
    with Session() as session:
        assert session.scalar(select(func.count()).select_from(ReviewEvent)) == 1


@pytest.mark.parametrize("claim", CLAIMS[1:])
def test_unanswerable_claims_do_not_invent_evidence(client, claim):
    run = analyzed(client, seeded(client), claim)
    assert run["outcome"] == "insufficient_evidence"
    assert not run["findings"]
    draft = client.get(f"/api/v1/investigations/{run['id']}/export?expected_revision=0&draft=true")
    assert draft.status_code == 200 and "DRAFT / NOT FULLY REVIEWED" in draft.text


def test_custom_claim_fails_honestly(client):
    run = analyzed(client, seeded(client), "Invent a conclusion about a different company.")
    assert run["job"]["state"] == "failed"
    assert run["job"]["error_code"] == "fixture_not_available"
    assert not run["findings"]


def test_custom_document_ingests_but_does_not_get_canned_analysis(client):
    c = client.post("/api/v1/collections", json={"title": "My sources"}).json()
    response = client.post(f"/api/v1/collections/{c['id']}/documents", content=b"My own report.\n\nSome actual evidence.", headers={"Content-Type": "text/plain", "X-Filename": "report.txt"})
    assert response.status_code == 202
    drain()
    doc = response.json()["document"]
    assert client.get(f"/api/v1/documents/{doc['id']}/source").json()["passages"][0]["text"] == "My own report."
    run = analyzed(client, c)
    assert run["job"]["error_code"] == "fixture_not_available"


def test_ownership_blocks_all_direct_ids(client):
    c = seeded(client)
    run = analyzed(client, c)
    finding = run["findings"][0]
    app.dependency_overrides[owner_dependency] = lambda: "another-owner"
    assert client.get("/api/v1/collections").json()["items"] == []
    for path in [f"/collections/{c['id']}", f"/collections/{c['id']}/documents", f"/documents/{finding['document_id']}", f"/documents/{finding['document_id']}/source", f"/investigations/{run['id']}", f"/jobs/{run['job']['id']}", f"/jobs/{run['job']['id']}/events", f"/investigations/{run['id']}/export?expected_revision=0&draft=true"]:
        assert client.get("/api/v1"+path).status_code == 404, path
    assert client.put(f"/api/v1/findings/{finding['id']}/review", json={"decision":"accepted","expected_revision":0}).status_code == 404
    assert client.delete(f"/api/v1/documents/{finding['document_id']}").status_code == 404


def test_citation_cannot_open_in_another_document(client):
    c = seeded(client)
    docs = client.get(f"/api/v1/collections/{c['id']}/documents").json()["items"]
    passage = client.get(f"/api/v1/documents/{docs[0]['id']}/source").json()["passages"][0]
    assert client.get(f"/api/v1/documents/{docs[1]['id']}/source?passage_id={passage['id']}").status_code == 404


def test_idempotency_and_optimistic_review_conflicts(client):
    c = seeded(client)
    run = analyzed(client, c)
    same = client.post(f"/api/v1/collections/{c['id']}/investigations", json={"claim":CLAIMS[0]}, headers={"Idempotency-Key":"test-key"})
    assert same.json()["id"] == run["id"]
    conflict = client.post(f"/api/v1/collections/{c['id']}/investigations", json={"claim":CLAIMS[1]}, headers={"Idempotency-Key":"test-key"})
    assert conflict.status_code == 409
    f = run["findings"][0]
    body = {"decision":"accepted","expected_revision":0}
    assert client.put(f"/api/v1/findings/{f['id']}/review", json=body).status_code == 200
    assert client.put(f"/api/v1/findings/{f['id']}/review", json=body).status_code == 409
    assert client.get(f"/api/v1/investigations/{run['id']}/export?expected_revision=0&draft=true").status_code == 409


def test_partial_collection_requires_explicit_choice(client):
    c = client.post("/api/v1/sample").json()
    assert run_once()
    blocked = client.post(f"/api/v1/collections/{c['id']}/investigations", json={"claim":CLAIMS[0]})
    assert blocked.status_code == 409
    partial = client.post(f"/api/v1/collections/{c['id']}/investigations", json={"claim":CLAIMS[0],"allow_partial":True})
    assert partial.status_code == 202
    run = client.get(f"/api/v1/investigations/{partial.json()['id']}").json()
    assert len(run["source_manifest"]) == 1 and len(run["excluded_sources"]) == 3


def test_deleted_source_revokes_immediately_and_cleans_derivatives(client):
    c = seeded(client)
    run = analyzed(client, c)
    f = run["findings"][0]
    with Session() as session:
        path = artifact_path(session.get(Document, f["document_id"]).storage_key)
    deletion = client.delete(f"/api/v1/documents/{f['document_id']}")
    assert deletion.status_code == 202
    assert client.get(f"/api/v1/documents/{f['document_id']}/source").status_code == 404
    assert client.get(f"/api/v1/investigations/{run['id']}/export?expected_revision=0&draft=true").status_code == 409
    drain()
    assert not path.exists()
    with Session() as session:
        assert session.scalar(select(func.count()).select_from(Passage).where(Passage.document_id == f["document_id"])) == 0
        assert session.get(Finding, f["id"]) is None


def test_cancelled_ingestion_can_retry(client):
    c = client.post("/api/v1/sample").json()
    doc = client.get(f"/api/v1/collections/{c['id']}/documents").json()["items"][0]
    assert client.post(f"/api/v1/jobs/{doc['job_id']}/cancel").json()["state"] == "cancelled"
    assert client.post(f"/api/v1/documents/{doc['id']}/retry").status_code == 202
    drain()
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["state"] == "ready"


def test_expired_lease_is_reclaimed_and_old_worker_cannot_publish(client):
    client.post("/api/v1/sample")
    first = claim_job()
    payload = prepare(first)
    with Session.begin() as session:
        session.get(Job, first["id"]).lease_until = now() - timedelta(seconds=1)
    recovered = claim_job()
    assert recovered["id"] == first["id"] and recovered["token"] != first["token"]
    assert finish(first, payload) is False
    assert finish(recovered, prepare(recovered)) is True
    with Session() as session:
        assert session.get(Job, first["id"]).attempts == 2


def test_cancellation_wins_publication_race(client):
    client.post("/api/v1/sample")
    claim = claim_job()
    payload = prepare(claim)
    assert client.post(f"/api/v1/jobs/{claim['id']}/cancel").status_code == 200
    assert finish(claim, payload)
    with Session() as session:
        assert session.get(Job, claim["id"]).state == "cancelled"
        assert session.scalar(select(func.count()).select_from(Passage).where(Passage.document_id == claim["resource_id"])) == 0


def test_invalid_quote_is_rejected_before_publication(client):
    c = seeded(client)
    response = client.post(f"/api/v1/collections/{c['id']}/investigations", json={"claim":CLAIMS[0]})
    claim = claim_job()
    payload = prepare(claim)
    payload["analysis"][1][0]["quote"] = "Invented quotation."
    with pytest.raises(ValueError, match="invalid_evidence"):
        finish(claim, payload)
    with Session() as session:
        assert session.scalar(select(func.count()).select_from(Finding)) == 0


@pytest.mark.parametrize("filename,content,status", [("fake.pdf",b"not a PDF",415),("bad.txt",b"\xff\xfe",422),("empty.txt",b" ",422),("null.txt",b"bad\x00data",422),("big.txt",b"x"*2_097_153,413)])
def test_upload_validation(client, filename, content, status):
    c = client.post("/api/v1/collections",json={"title":"Test"}).json()
    response = client.post(f"/api/v1/collections/{c['id']}/documents", content=content, headers={"Content-Type":"text/plain","X-Filename":filename})
    assert response.status_code == status


def test_cross_site_and_host_rejected(client):
    assert client.post("/api/v1/sample", headers={"Origin":"https://attacker.example"}).status_code == 403
    assert client.post("/api/v1/sample", headers={"Sec-Fetch-Site":"cross-site"}).status_code == 403
    assert client.get("/api/v1/health/live", headers={"Host":"attacker.example"}).status_code == 400


def test_collection_pagination_and_invalid_cursor(client):
    for i in range(3):
        assert client.post("/api/v1/collections",json={"title":f"Collection {i}"}).status_code == 201
    first = client.get("/api/v1/collections?limit=2").json()
    second = client.get("/api/v1/collections",params={"limit":2,"cursor":first["next_cursor"]}).json()
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert not {c["id"] for c in first["items"]}.intersection(c["id"] for c in second["items"])
    assert client.get("/api/v1/collections?cursor=bad").status_code == 422


def test_passage_offsets_preserve_source_text():
    text = "Title\n\nA paragraph with a number: 1.20.\nSecond line.\n\n" + "x" * 4100
    parts = split_passages(text)
    assert len(parts) == 4
    for part in parts:
        assert text[part["start_offset"]:part["start_offset"]+len(part["text"])] == part["text"]
    assert parts[1]["line_start"] == 3 and parts[1]["line_end"] == 4


def test_investigation_response_is_consistent_when_worker_publishes_during_read(client, monkeypatch):
    import app.main as main_module
    from app.models import Investigation
    c = seeded(client)
    response = client.post(f"/api/v1/collections/{c['id']}/investigations", json={"claim":CLAIMS[0]})
    run_id = response.json()["id"]
    original = main_module.investigation_for

    def publish_between_reads(session, resource_id, owner, lock=False):
        # Reproduce the real HTTP race deterministically: identity map holds the old run,
        # while a separate worker transaction publishes findings and successful job state.
        old_run = session.get(Investigation, resource_id)
        assert old_run.outcome is None
        assert run_once()
        return original(session, resource_id, owner, lock=lock)

    monkeypatch.setattr(main_module, "investigation_for", publish_between_reads)
    result = client.get(f"/api/v1/investigations/{run_id}").json()
    assert result["job"]["state"] == "succeeded"
    assert len(result["findings"]) == 3
    assert result["outcome"] == "conflicting_evidence"


def test_removing_one_source_does_not_cancel_other_ingestion(client):
    c = client.post("/api/v1/sample").json()
    docs = client.get(f"/api/v1/collections/{c['id']}/documents").json()["items"]
    assert client.delete(f"/api/v1/documents/{docs[0]['id']}").status_code == 202
    drain()
    remaining = client.get(f"/api/v1/collections/{c['id']}/documents").json()["items"]
    assert len(remaining) == 3 and all(doc["state"] == "ready" for doc in remaining)


def test_recovered_cancelled_ingestion_is_retryable(client):
    client.post("/api/v1/sample")
    claim = claim_job()
    assert client.post(f"/api/v1/jobs/{claim['id']}/cancel").status_code == 200
    with Session.begin() as session:
        session.get(Job, claim["id"]).lease_until = now()-timedelta(seconds=1)
    assert run_once()
    with Session() as session:
        assert session.get(Document, claim["resource_id"]).state == "cancelled"
    assert client.post(f"/api/v1/documents/{claim['resource_id']}/retry").status_code == 202
    drain()
    assert client.get(f"/api/v1/documents/{claim['resource_id']}").json()["state"] == "ready"


def test_failed_cleanup_can_be_retried_without_restoring_access(client):
    c = seeded(client)
    doc = client.get(f"/api/v1/collections/{c['id']}/documents").json()["items"][0]
    cleanup = client.delete(f"/api/v1/documents/{doc['id']}").json()
    with Session.begin() as session:
        job = session.get(Job, cleanup["id"])
        job.state, job.error_code = "failed", "attempt_or_deadline_limit"
    retry = client.post(f"/api/v1/jobs/{cleanup['id']}/retry-cleanup")
    assert retry.status_code == 202
    assert client.get(f"/api/v1/documents/{doc['id']}/source").status_code == 404
    drain()
    assert client.get(f"/api/v1/jobs/{retry.json()['id']}").json()["state"] == "succeeded"


def test_original_bytes_are_preserved_and_integrity_is_checked(client):
    c = client.post("/api/v1/collections", json={"title":"Original bytes"}).json()
    original = b"\xef\xbb\xbfTitle\r\n\r\nA source passage.\r\n"
    uploaded = client.post(f"/api/v1/collections/{c['id']}/documents", content=original, headers={"Content-Type":"text/plain","X-Filename":"source.txt"}).json()
    doc = uploaded["document"]
    assert doc["checksum"] == sha256(original).hexdigest()
    with Session() as session:
        path = artifact_path(session.get(Document, doc["id"]).storage_key)
    assert path.read_bytes() == original
    path.write_bytes(b"Changed without a new upload.")
    drain()
    job = client.get(f"/api/v1/jobs/{uploaded['job']['id']}").json()
    assert job["state"] == "failed" and job["error_code"] == "source_integrity_mismatch"
