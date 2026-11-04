from typing import Literal
from pydantic import BaseModel, Field, field_validator


class CollectionInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()


class InvestigationInput(BaseModel):
    claim: str = Field(min_length=3, max_length=2000)
    allow_partial: bool = False

    @field_validator("claim")
    @classmethod
    def clean_claim(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Enter a claim of at least three characters")
        return value.strip()


class ReviewInput(BaseModel):
    decision: Literal["accepted", "dismissed", "unreviewed"]
    note: str = Field(default="", max_length=2000)
    expected_revision: int = Field(ge=0)


class CollectionOut(BaseModel):
    id: str
    title: str
    revision: int
    created_at: str
    document_count: int
    ready_count: int


class DocumentOut(BaseModel):
    id: str
    collection_id: str
    title: str
    checksum: str
    size: int
    state: str
    created_at: str
    job_id: str | None
    error_code: str | None


class JobOut(BaseModel):
    id: str
    collection_id: str
    kind: str
    resource_id: str
    state: str
    stage: str
    attempts: int
    error_code: str | None
    cancel_requested: bool


class FindingOut(BaseModel):
    id: str
    passage_id: str
    document_id: str
    document_title: str
    relation: str
    quote: str
    explanation: str
    line_start: int
    line_end: int
    decision: str
    note: str
    revision: int


class InvestigationOut(BaseModel):
    id: str
    collection_id: str
    claim: str
    mode: str
    outcome: str | None
    limitations: str | None
    stale: bool
    review_revision: int
    source_manifest: list[dict]
    excluded_sources: list[dict]
    findings: list[FindingOut]
    job: JobOut
    created_at: str


class PassageOut(BaseModel):
    id: str
    text: str
    line_start: int
    line_end: int
    start_offset: int
    ordinal: int


class SourceOut(BaseModel):
    document: DocumentOut
    passages: list[PassageOut]
    next_after: int | None
