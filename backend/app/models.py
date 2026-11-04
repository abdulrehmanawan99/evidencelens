from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(160))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("id", "collection_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    checksum: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(24), default="queued")
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    generation: Mapped[int] = mapped_column(Integer, default=1)
    family_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    media_type: Mapped[str] = mapped_column(String(40), default="text/plain")
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    extraction_version: Mapped[str] = mapped_column(String(50), default="text-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Passage(Base):
    __tablename__ = "passages"
    __table_args__ = (ForeignKeyConstraint(["document_id", "collection_id"], ["documents.id", "documents.collection_id"]), UniqueConstraint("id", "collection_id"), UniqueConstraint("document_id", "ordinal"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    collection_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer)
    line_start: Mapped[int] = mapped_column(Integer)
    line_end: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int] = mapped_column(Integer, default=1)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("collection_id", "kind", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_payload: Mapped[dict | None] = mapped_column(JSON)


class JobEvent(Base):
    __tablename__ = "job_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    state: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Investigation(Base):
    __tablename__ = "investigations"
    __table_args__ = (UniqueConstraint("id", "collection_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id"), index=True)
    claim: Mapped[str] = mapped_column(Text)
    collection_revision: Mapped[int] = mapped_column(Integer)
    source_manifest: Mapped[list] = mapped_column(JSON)
    excluded_sources: Mapped[list] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(20), default="fixture")
    analysis_version: Mapped[str] = mapped_column(String(50), default="harbor-fixture-v1")
    outcome: Mapped[str | None] = mapped_column(String(50))
    limitations: Mapped[str | None] = mapped_column(Text)
    review_revision: Mapped[int] = mapped_column(Integer, default=0)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding_profile_id: Mapped[str | None] = mapped_column(String(36))
    claim_id: Mapped[str | None] = mapped_column(String(36))
    claim_revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (ForeignKeyConstraint(["investigation_id", "collection_id"], ["investigations.id", "investigations.collection_id"]), ForeignKeyConstraint(["passage_id", "collection_id"], ["passages.id", "passages.collection_id"]))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    collection_id: Mapped[str] = mapped_column(String(36), index=True)
    investigation_id: Mapped[str] = mapped_column(String(36), index=True)
    passage_id: Mapped[str] = mapped_column(String(36))
    relation: Mapped[str] = mapped_column(String(16))
    explanation: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text)
    quote_start: Mapped[int] = mapped_column(Integer)
    quote_end: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16), default="unreviewed")
    note: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=0)


class ReviewEvent(Base):
    __tablename__ = "review_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), index=True)
    decision: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EmbeddingProfile(Base):
    __tablename__ = "embedding_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(160))
    dimensions: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PassageEmbedding(Base):
    __tablename__ = "passage_embeddings"
    __table_args__ = (UniqueConstraint("passage_id", "profile_id"), ForeignKeyConstraint(["passage_id", "collection_id"], ["passages.id", "passages.collection_id"]))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    passage_id: Mapped[str] = mapped_column(String(36), index=True)
    collection_id: Mapped[str] = mapped_column(String(36), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("embedding_profiles.id"), index=True)
    vector: Mapped[list] = mapped_column(Vector())


class RetrievalHit(Base):
    __tablename__ = "retrieval_hits"
    __table_args__ = (ForeignKeyConstraint(["investigation_id", "collection_id"], ["investigations.id", "investigations.collection_id"]), ForeignKeyConstraint(["passage_id", "collection_id"], ["passages.id", "passages.collection_id"]))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    investigation_id: Mapped[str] = mapped_column(String(36), index=True)
    collection_id: Mapped[str] = mapped_column(String(36), index=True)
    passage_id: Mapped[str] = mapped_column(String(36))
    method: Mapped[str] = mapped_column(String(20))
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[str] = mapped_column(String(60))
    in_context: Mapped[bool] = mapped_column(Boolean)


class ProviderCall(Base):
    __tablename__ = "provider_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(30))
    duration_ms: Mapped[int] = mapped_column(Integer)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Export(Base):
    __tablename__ = "exports"
    __table_args__ = (ForeignKeyConstraint(["investigation_id", "collection_id"], ["investigations.id", "investigations.collection_id"]),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    collection_id: Mapped[str] = mapped_column(String(36), index=True)
    investigation_id: Mapped[str] = mapped_column(String(36), index=True)
    review_revision: Mapped[int] = mapped_column(Integer)
    draft: Mapped[bool] = mapped_column(Boolean)
    mode: Mapped[str] = mapped_column(String(30))
    state: Mapped[str] = mapped_column(String(24), default="queued")
    snapshot: Mapped[dict] = mapped_column(JSON)
    storage_key: Mapped[str] = mapped_column(String(80))
    checksum: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ClaimRevision(Base):
    __tablename__ = "claim_revisions"
    __table_args__ = (UniqueConstraint("claim_id", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
