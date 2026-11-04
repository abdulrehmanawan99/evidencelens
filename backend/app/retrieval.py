import json
import re
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .config import settings
from .models import Document, EmbeddingProfile, Passage, PassageEmbedding, uid
from .providers import ModelAnalysis, ProviderError, SYSTEM, embed_texts, embedding_configuration


def ensure_profile(session, configuration):
    fingerprint = configuration["fingerprint"]
    session.execute(insert(EmbeddingProfile).values(id=uid(), fingerprint=fingerprint, provider=configuration["provider"], model=configuration["model"], dimensions=configuration["dimensions"], configuration=configuration).on_conflict_do_nothing(index_elements=[EmbeddingProfile.fingerprint]))
    return session.scalar(select(EmbeddingProfile).where(EmbeddingProfile.fingerprint == fingerprint))


def index_status(session, collection_id):
    config = embedding_configuration()
    profile = session.scalar(select(EmbeddingProfile).where(EmbeddingProfile.fingerprint == config["fingerprint"]))
    base = select(Passage.id).join(Document, Passage.document_id == Document.id).where(Passage.collection_id == collection_id, Document.active.is_(True), Document.deleted.is_(False), Document.state == "ready")
    expected = session.scalar(select(func.count()).select_from(base.subquery()))
    indexed = session.scalar(select(func.count()).select_from(PassageEmbedding).where(PassageEmbedding.collection_id == collection_id, PassageEmbedding.profile_id == profile.id, PassageEmbedding.passage_id.in_(base))) if profile else 0
    return {"ready": expected > 0 and indexed == expected, "expected": expected, "indexed": indexed, "profile_id": profile.id if profile else None, "fingerprint": config["fingerprint"], "provider": config["provider"], "model": config["model"], "dimensions": config["dimensions"], "mode": "fixture" if config["provider"] == "fixture" else "live"}


def retrieve(session, collection_id, source_ids, claim, control=None):
    config, query_vectors = embed_texts([claim], control)
    profile = session.scalar(select(EmbeddingProfile).where(EmbeddingProfile.fingerprint == config["fingerprint"]))
    if not profile:
        raise ProviderError("index_required")
    passage_scope = [Passage.collection_id == collection_id, Passage.document_id.in_(source_ids)]
    expected = session.scalar(select(func.count()).select_from(Passage).where(*passage_scope))
    indexed = session.scalar(select(func.count()).select_from(PassageEmbedding).join(Passage, PassageEmbedding.passage_id == Passage.id).where(*passage_scope, PassageEmbedding.collection_id == collection_id, PassageEmbedding.profile_id == profile.id))
    if indexed != expected:
        raise ProviderError("index_required")
    distance = PassageEmbedding.vector.cosine_distance(query_vectors[0])
    vector_rows = session.execute(select(Passage, distance.label("score")).join(PassageEmbedding, PassageEmbedding.passage_id == Passage.id).where(*passage_scope, PassageEmbedding.collection_id == collection_id, PassageEmbedding.profile_id == profile.id).order_by(distance, Passage.id).limit(40)).all()
    terms = re.findall(r"[A-Za-z0-9]+(?:\.[0-9]+)?", claim)[:48]
    rank = func.ts_rank_cd(func.to_tsvector("english", Passage.text), func.websearch_to_tsquery("english", " OR ".join(terms)))
    keyword_rows = session.execute(select(Passage, rank.label("score")).where(*passage_scope, rank > 0).order_by(rank.desc(), Passage.id).limit(40)).all()
    scores, candidates, trace = defaultdict(float), {}, []
    for method, rows in [("vector", vector_rows), ("keyword", keyword_rows)]:
        for position, (passage, score) in enumerate(rows, 1):
            scores[passage.id] += 1/(60+position)
            candidates[passage.id] = passage
            trace.append({"passage_id": passage.id, "method": method, "rank": position, "score": str(score)})
    sources = {doc.id: doc for doc in session.scalars(select(Document).where(Document.id.in_(source_ids), Document.collection_id == collection_id))}
    overhead = len(SYSTEM.encode()) + len(json.dumps(ModelAnalysis.model_json_schema()).encode()) + len(claim.encode()) + 800
    budget = min(8000, settings.context_tokens-settings.max_output_tokens-1000-overhead)
    selected, counts, used = [], Counter(), 0
    for passage_id in sorted(candidates, key=lambda identifier: (-scores[identifier], identifier)):
        passage = candidates[passage_id]
        source = sources[passage.document_id]
        cost = len(json.dumps({"id": passage.id, "source": source.title, "version": source.version, "page": passage.page_number, "text": passage.text}, ensure_ascii=False).encode()) + 2
        if counts[source.id] >= 3 or used+cost > budget:
            continue
        selected.append(passage)
        used += cost
        counts[source.id] += 1
        if len(selected) == 12:
            break
    in_context = {passage.id for passage in selected}
    for hit in trace:
        hit["in_context"] = hit["passage_id"] in in_context
    return profile, selected, trace
