from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

import httpx
import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import func, select

from app import providers
from app.config import settings
from app.db import Session, owner_dependency
from app.fixtures import CLAIMS, PDF_DIRECTORY
from app.main import app
from app.models import Document, EmbeddingProfile, Export, Finding, Job, Passage, PassageEmbedding, ProviderCall, now, uid
from app.providers import LiveAdapter, ProviderError, configuration, embed_texts, validate_vectors
from app.services import artifact_path
from app.worker import JobControl, claim_job, finish, prepare, run_once, sweep_orphans
from test_workflow import analyzed, drain, seeded


def pdf_bytes(pages):
    buffer = BytesIO()
    canvas = Canvas(buffer, invariant=True)
    for page in pages:
        text = canvas.beginText(40, 760)
        text.setFont("Helvetica", 11)
        for line in page.splitlines():
            text.textLine(line)
        canvas.drawText(text)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def upload(client, collection, data, name="source.pdf"):
    response = client.post(f"/api/v1/collections/{collection['id']}/documents", content=data, headers={"Content-Type":"application/pdf" if name.endswith(".pdf") else "text/plain", "X-Filename":name})
    assert response.status_code == 202, response.text
    return response.json()


def test_pdf_pages_content_and_exact_locations(client):
    collection = client.post("/api/v1/collections", json={"title":"PDF sources"}).json()
    original = pdf_bytes(["First page.\n\nA different source passage.", "Second page.\n\nThe measured value was 42 units."])
    result = upload(client, collection, original)
    drain()
    doc_id = result["document"]["id"]
    doc = client.get(f"/api/v1/documents/{doc_id}").json()
    assert doc["state"] == "ready" and doc["page_count"] == 2
    source = client.get(f"/api/v1/documents/{doc_id}/source?page=2").json()
    assert source["passages"] and all(p["page_number"] == 2 for p in source["passages"])
    assert "42 units" in " ".join(p["text"] for p in source["passages"])
    assert client.get(f"/api/v1/documents/{doc_id}/content").content == original
    assert client.get(f"/api/v1/documents/{doc_id}/source?page=3").status_code == 422


def test_pdf_sample_completes_cited_review_workflow(client):
    response = client.post("/api/v1/sample?format=pdf")
    assert response.status_code == 201, response.text
    collection = response.json()
    drain()
    run = analyzed(client, collection)
    assert run["job"]["state"] == "succeeded", run["job"]
    assert run["outcome"] == "conflicting_evidence"
    assert len(run["findings"]) == 3 and all(f["page_number"] == 1 for f in run["findings"])


@pytest.mark.parametrize("kind,expected", [("encrypted","encrypted_pdf"),("blank","ocr_required"),("malformed","malformed_pdf"),("many_pages","pdf_page_limit")])
def test_pdf_rejections_are_recoverable_job_errors(client, kind, expected):
    collection = client.post("/api/v1/collections",json={"title":"PDF validation"}).json()
    if kind == "malformed":
        data = b"%PDF-1.7\nmalformed document"
    else:
        writer = PdfWriter()
        for _ in range(101 if kind == "many_pages" else 1):
            writer.add_blank_page(width=600,height=800)
        if kind == "encrypted":
            writer.encrypt("test-only-password")
        buffer = BytesIO()
        writer.write(buffer)
        data = buffer.getvalue()
    uploaded = upload(client, collection, data)
    drain()
    job = client.get(f"/api/v1/jobs/{uploaded['job']['id']}").json()
    assert job["state"] == "failed" and job["error_code"] == expected, job


def test_pdf_partly_unreadable_pages_are_disclosed(client):
    data = pdf_bytes(["An extractable text page.", ""])
    c = client.post("/api/v1/collections",json={"title":"Partial PDF"}).json()
    uploaded = upload(client,c,data)
    drain()
    doc = client.get(f"/api/v1/documents/{uploaded['document']['id']}").json()
    assert doc["state"] == "ready" and doc["warnings"][0]["page"] == 2
    assert doc["warnings"][0]["code"] == "ocr_required"
    page = client.get(f"/api/v1/documents/{doc['id']}/source?page=2").json()
    assert page["page_number"] == 2 and page["passages"] == []


def test_parser_wall_timeout_and_temporary_cleanup(client):
    object.__setattr__(settings,"parser_seconds",0)
    c = client.post("/api/v1/collections",json={"title":"Parser timeout"}).json()
    uploaded = upload(client,c,pdf_bytes(["A source passage."]))
    drain()
    job = client.get(f"/api/v1/jobs/{uploaded['job']['id']}").json()
    assert job["error_code"] == "parser_timeout"
    assert not list((settings.storage_dir/".tmp").glob("parser-*"))


def test_deleting_excluded_source_purges_its_export_metadata(client):
    c = seeded(client)
    failed = upload(client, c, b"%PDF-1.7\nmalformed document", "private-excluded.pdf")
    drain()
    created = client.post(f"/api/v1/collections/{c['id']}/investigations", json={"claim": CLAIMS[0], "allow_partial": True}).json()
    drain()
    run = client.get(f"/api/v1/investigations/{created['id']}").json()
    exported = client.post(f"/api/v1/investigations/{run['id']}/exports", json={"expected_revision": 0, "draft": True}).json()
    drain()
    assert b"private-excluded.pdf" in client.get(f"/api/v1/exports/{exported['id']}/download").content
    client.delete(f"/api/v1/documents/{failed['document']['id']}")
    drain()
    after = client.get(f"/api/v1/investigations/{run['id']}").json()
    assert after["excluded_sources"][0]["title"] == "[deleted source]"
    with Session() as session:
        assert session.get(Export, exported["id"]).snapshot == {}


def test_document_versions_activation_and_family_deletion(client):
    c = seeded(client)
    run = analyzed(client,c)
    first = run["source_manifest"][0]
    old_id = first["id"]
    response = client.post(f"/api/v1/documents/{old_id}/versions",content=b"A revised report.\n\nThe total changed.",headers={"X-Filename":"revised.txt"})
    assert response.status_code == 202,response.text
    new_id = response.json()["document"]["id"]
    drain()
    versions = client.get(f"/api/v1/documents/{new_id}/versions").json()["items"]
    assert [d["version"] for d in versions] == [2,1]
    assert versions[0]["active"] and not versions[1]["active"]
    assert client.get(f"/api/v1/investigations/{run['id']}").json()["stale"]
    assert client.get(f"/api/v1/documents/{old_id}/source").status_code == 200
    assert client.post(f"/api/v1/documents/{old_id}/activate").status_code == 200
    current = client.get(f"/api/v1/collections/{c['id']}/documents").json()["items"]
    assert old_id in {d["id"] for d in current} and new_id not in {d["id"] for d in current}
    assert client.delete(f"/api/v1/documents/{old_id}").status_code == 202
    drain()
    assert client.get(f"/api/v1/documents/{new_id}/source").status_code == 404


def test_atomic_profile_reindex_and_retrieval_trace(client):
    c = seeded(client)
    status = client.get(f"/api/v1/collections/{c['id']}/index-status").json()
    assert status["ready"] and status["expected"] == status["indexed"]
    old_id = status["profile_id"]
    object.__setattr__(settings,"chunking_version","profile-version-2")
    assert not client.get(f"/api/v1/collections/{c['id']}/index-status").json()["ready"]
    assert client.post(f"/api/v1/collections/{c['id']}/reindex").status_code == 202
    drain()
    status = client.get(f"/api/v1/collections/{c['id']}/index-status").json()
    assert status["ready"] and status["profile_id"] != old_id
    run = analyzed(client,c)
    trace = client.get(f"/api/v1/investigations/{run['id']}/trace").json()
    assert trace["embedding_profile_id"] == status["profile_id"]
    assert {h["method"] for h in trace["hits"]} == {"keyword","vector"}
    assert any(h["in_context"] for h in trace["hits"])


def test_cross_collection_vector_hits_are_excluded(client):
    a,b = seeded(client),seeded(client)
    run = analyzed(client,a)
    trace = client.get(f"/api/v1/investigations/{run['id']}/trace").json()
    with Session() as session:
        allowed = set(session.scalars(select(Passage.id).where(Passage.collection_id == a["id"])))
    assert trace["hits"] and all(h["passage_id"] in allowed for h in trace["hits"])


def test_persisted_export_freezes_review_revision_and_is_revoked_on_delete(client):
    c=seeded(client)
    run=analyzed(client,c)
    finding=run["findings"][0]
    review=client.put(f"/api/v1/findings/{finding['id']}/review",json={"decision":"accepted","note":"Original note.","expected_revision":0}).json()
    response=client.post(f"/api/v1/investigations/{run['id']}/exports",json={"expected_revision":1},headers={"Idempotency-Key":"export-key"})
    assert response.status_code==202,response.text
    export=response.json()
    again=client.post(f"/api/v1/investigations/{run['id']}/exports",json={"expected_revision":1},headers={"Idempotency-Key":"export-key"})
    assert again.json()["id"]==export["id"]
    client.put(f"/api/v1/findings/{finding['id']}/review",json={"decision":"accepted","note":"Changed note.","expected_revision":1})
    drain()
    content=client.get(f"/api/v1/exports/{export['id']}/download")
    assert content.status_code==200 and "Original note." in content.text and "Changed note." not in content.text
    metadata=client.get(f"/api/v1/exports/{export['id']}").json()
    assert metadata["checksum"]==sha256(content.content).hexdigest()
    client.delete(f"/api/v1/documents/{finding['document_id']}")
    assert client.get(f"/api/v1/exports/{export['id']}/download").status_code==409
    drain()
    with Session() as session:
        stored=session.get(Export,export["id"])
        assert stored.snapshot=={} and not artifact_path(stored.storage_key).exists()


def test_claim_revision_and_suggestion_confirmation(client):
    c=seeded(client)
    run=analyzed(client,c)
    f=next(f for f in run["findings"] if f["relation"]=="supports")
    response=client.post(f"/api/v1/collections/{c['id']}/claim-suggestions",json={"passage_id":f["passage_id"]})
    assert response.status_code==202
    drain()
    result=client.get(f"/api/v1/jobs/{response.json()['id']}").json()["result_payload"]
    assert result["requires_confirmation"] and result["claims"]==[CLAIMS[0]]
    claim=client.patch(f"/api/v1/claims/{run['claim_id']}",json={"text":CLAIMS[1],"expected_revision":1})
    assert claim.status_code==200 and claim.json()["revision"]==2
    assert client.patch(f"/api/v1/claims/{run['claim_id']}",json={"text":CLAIMS[2],"expected_revision":1}).status_code==409
    assert client.get(f"/api/v1/investigations/{run['id']}").json()["claim"]==CLAIMS[0]


def test_export_and_original_and_claim_direct_ids_enforce_owner(client):
    c=seeded(client)
    run=analyzed(client,c)
    exp=client.post(f"/api/v1/investigations/{run['id']}/exports",json={"draft":True,"expected_revision":0}).json()
    drain()
    app.dependency_overrides[owner_dependency]=lambda:"another-owner"
    doc=run["source_manifest"][0]["id"]
    for path in [f"/documents/{doc}/content",f"/documents/{doc}/versions",f"/exports/{exp['id']}",f"/exports/{exp['id']}/download",f"/investigations/{run['id']}/trace",f"/collections/{c['id']}/index-status",f"/collections/{c['id']}/claims"]:
        assert client.get("/api/v1"+path).status_code==404,path


def remote_settings(mode="openai"):
    for key,value in {"model_mode":mode,"generation_model":"test-generation","generation_endpoint":"https://unit.provider/v1","generation_key":"test-only-key","embedding_provider":"openai","embedding_model":"test-embedding","embedding_endpoint":"https://unit.provider/v1","embedding_key":"test-only-key","embedding_dimensions":3}.items():
        object.__setattr__(settings,key,value)


def evidence():
    doc=SimpleNamespace(id=uid(),title="Original report",version=1)
    passage=SimpleNamespace(id=uid(),document_id=doc.id,page_number=2,text="The measured total was 42 units.")
    return doc,passage


@pytest.mark.parametrize("mode",["openai","openai_compatible","ollama"])
def test_live_generation_adapters_validate_actual_request_contracts(monkeypatch,mode):
    remote_settings(mode)
    doc,passage=evidence()
    answer={"outcome":"supported_in_sources","findings":[{"passage_id":passage.id,"relation":"supports","quote":passage.text,"explanation":"The passage states the total."}],"limitations":"Selected sources only."}
    requests=[]
    def handler(request):
        payload=json.loads(request.content);requests.append(payload)
        if mode=="openai":
            assert payload["store"] is False and payload["text"]["format"]["strict"]
            return httpx.Response(200,json={"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(answer)}]}],"usage":{"input_tokens":100,"output_tokens":50}})
        if mode=="openai_compatible":
            assert payload["response_format"]["type"]=="json_schema"
            return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":json.dumps(answer)}}]})
        assert payload["stream"] is False and "format" in payload
        return httpx.Response(200,json={"done":True,"done_reason":"stop","message":{"content":json.dumps(answer)}})
    monkeypatch.setattr(providers,"transport",httpx.MockTransport(handler))
    result=LiveAdapter().analyze("The measured total was 42 units.",[doc],[passage])
    assert result.findings[0]["quote_start"]==0 and len(requests)==1


def test_live_adapter_rejects_invented_citations_after_one_repair(monkeypatch):
    remote_settings()
    doc,passage=evidence()
    calls=[]
    def handler(request):
        calls.append(1)
        output={"outcome":"supported_in_sources","findings":[{"passage_id":uid(),"relation":"supports","quote":"Invented quote.","explanation":"Unsupported."}],"limitations":"None."}
        return httpx.Response(200,json={"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(output)}]}]})
    monkeypatch.setattr(providers,"transport",httpx.MockTransport(handler))
    with pytest.raises(ProviderError,match="invalid_evidence"):
        LiveAdapter().analyze("The total was 42.",[doc],[passage])
    assert len(calls)==2


@pytest.mark.parametrize("vectors,count,dimensions",[([[0,0,0]],1,3),([[1,float("nan"),2]],1,3),([[1,2]],1,3),([[1,0,0]],2,3)])
def test_invalid_embeddings_cannot_enter_index(vectors,count,dimensions):
    with pytest.raises(ProviderError):validate_vectors(vectors,count,dimensions)


def test_embedding_response_order_and_dimension_contract(monkeypatch):
    remote_settings()
    monkeypatch.setattr(providers,"transport",httpx.MockTransport(lambda request:httpx.Response(200,json={"data":[{"index":1,"embedding":[0,1,0]},{"index":0,"embedding":[1,0,0]}]})))
    profile,vectors=embed_texts(["first","second"])
    assert vectors==[[1,0,0],[0,1,0]]


def test_provider_refusal_is_not_repaired_or_published(monkeypatch):
    remote_settings()
    doc,passage=evidence()
    monkeypatch.setattr(providers,"transport",httpx.MockTransport(lambda request:httpx.Response(200,json={"status":"completed","output":[{"type":"message","content":[{"type":"refusal","refusal":"No."}]}]})))
    with pytest.raises(ProviderError,match="model_refused"):LiveAdapter().analyze("A claim.",[doc],[passage])


@pytest.mark.parametrize("url",["http://public.example/v1","https://user:secret@example.com/v1","https://example.com/v1?key=secret","file:///tmp/model"])
def test_invalid_provider_destinations_rejected(url):
    with pytest.raises(ProviderError):providers.checked_endpoint(url)


def test_missing_live_configuration_is_actionable_without_secret_disclosure(client):
    c=seeded(client)
    object.__setattr__(settings,"model_mode","openai")
    status=client.get("/api/v1/provider-status").json()
    assert not status["configured"] and status["configuration_error"]
    response=client.post(f"/api/v1/collections/{c['id']}/investigations",json={"claim":"A new claim."})
    assert response.status_code==503


def test_provider_budget_survives_worker_recovery(client):
    c=seeded(client)
    response=client.post(f"/api/v1/collections/{c['id']}/investigations",json={"claim":CLAIMS[0]})
    claim=claim_job()
    control=JobControl(claim)
    for _ in range(6):control.record(kind="generation",provider="mock",model="test",state="failed",duration_ms=1,usage={})
    with pytest.raises(ProviderError,match="provider_call_budget"):control.before_request()


def test_heartbeat_renews_long_running_job_lease(client):
    object.__setattr__(settings,"lease_seconds",3)
    client.post("/api/v1/sample")
    claim=claim_job()
    control=JobControl(claim);control.start()
    try:
        time.sleep(3.5)
        control.check()
    finally:control.close()


def test_orphan_sweeper_preserves_referenced_sources(client):
    c=seeded(client)
    orphan=artifact_path(f"{uid()}.txt");orphan.write_text("orphan")
    old=time.time()-settings.temporary_ttl_seconds-10
    os.utime(orphan,(old,old))
    sweep_orphans()
    assert not orphan.exists()
    with Session() as session:
        for doc in session.scalars(select(Document).where(Document.collection_id==c["id"])):assert artifact_path(doc.storage_key).exists()
