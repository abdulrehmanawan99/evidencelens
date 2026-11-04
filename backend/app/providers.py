"""Internal text-analysis contract. No provider SDK objects cross this boundary."""
from dataclasses import dataclass
from typing import NamedTuple, Protocol, Sequence, TypedDict

from .models import Document, Passage


class EvidenceCandidate(TypedDict):
    passage_id: str
    relation: str
    quote: str
    quote_start: int
    quote_end: int
    explanation: str


class AnalysisResult(NamedTuple):
    outcome: str
    findings: list[EvidenceCandidate]
    limitations: str


@dataclass(frozen=True)
class AnalysisCapabilities:
    mode: str
    structured_evidence: bool
    arbitrary_documents: bool
    max_claim_characters: int


class AnalysisAdapter(Protocol):
    def capabilities(self) -> AnalysisCapabilities: ...

    def analyze(self, claim: str, sources: Sequence[Document], passages: Sequence[Passage]) -> AnalysisResult: ...


class FixtureAdapter:
    def capabilities(self) -> AnalysisCapabilities:
        return AnalysisCapabilities(mode="fixture", structured_evidence=True, arbitrary_documents=False, max_claim_characters=2000)

    def analyze(self, claim: str, sources: Sequence[Document], passages: Sequence[Passage]) -> AnalysisResult:
        from .fixtures import analyze
        outcome, findings, limitations = analyze(claim, sources, passages)
        return AnalysisResult(outcome, findings, limitations)
