from dataclasses import dataclass
import re
from typing import Protocol

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.services.vector_store import (
    CHUNK_ID_FIELD,
    DOC_ID_FIELD,
    FRAME_TIME_FIELD,
    LINE_RANGE_FIELD,
    MEDIA_PATH_FIELD,
    MODALITY_FIELD,
    SOURCE_URL_FIELD,
    TIME_RANGE_FIELD,
    SOURCE_FIELD,
    TENANT_ID_FIELD,
    TEXT_FIELD,
)


class QueryEmbedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class RetrievalMatch:
    tenant_id: str
    doc_id: str
    chunk_id: int
    source: str
    text: str
    line_range: str | None
    score: float
    modality: str | None = None
    media_path: str | None = None
    source_url: str | None = None
    time_range: str | None = None
    frame_time: str | None = None


def retrieve_chunks(
    *,
    client: QdrantClient,
    collection_name: str,
    tenant_id: str,
    question: str,
    embedder: QueryEmbedder,
    top_k: int,
) -> list[RetrievalMatch]:
    question_vector = embedder.embed_texts([question])[0]
    response = client.query_points(
        collection_name=collection_name,
        query=question_vector,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key=TENANT_ID_FIELD,
                    match=models.MatchValue(value=tenant_id),
                )
            ]
        ),
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )

    matches: list[RetrievalMatch] = []
    for point in response.points:
        payload = point.payload or {}
        matches.append(
            RetrievalMatch(
                tenant_id=str(payload.get(TENANT_ID_FIELD, tenant_id)),
                doc_id=str(payload.get(DOC_ID_FIELD, "")),
                chunk_id=int(payload.get(CHUNK_ID_FIELD, 0)),
                source=str(payload.get(SOURCE_FIELD, "")),
                text=str(payload.get(TEXT_FIELD, "")),
                line_range=_optional_string(payload.get(LINE_RANGE_FIELD)),
                score=float(point.score or 0.0),
                modality=_optional_string(payload.get(MODALITY_FIELD)),
                media_path=_optional_string(payload.get(MEDIA_PATH_FIELD)),
                source_url=_optional_string(payload.get(SOURCE_URL_FIELD)),
                time_range=_optional_string(payload.get(TIME_RANGE_FIELD)),
                frame_time=_optional_string(payload.get(FRAME_TIME_FIELD)),
            )
        )

    return _rerank_for_query_intent(question=question, matches=matches)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _rerank_for_query_intent(*, question: str, matches: list[RetrievalMatch]) -> list[RetrievalMatch]:
    if not matches:
        return matches

    question_terms = _terms(question)
    modality_hint = _modality_hint(question_terms)
    if modality_hint is None and not question_terms:
        return matches

    return sorted(
        matches,
        key=lambda match: _intent_score(
            match=match,
            question_terms=question_terms,
            modality_hint=modality_hint,
        ),
        reverse=True,
    )


def _intent_score(
    *,
    match: RetrievalMatch,
    question_terms: set[str],
    modality_hint: str | None,
) -> float:
    searchable = " ".join(
        part
        for part in (
            match.source,
            match.doc_id,
            match.modality or "",
            match.text[:350],
        )
        if part
    )
    searchable_terms = _terms(searchable)
    lexical_overlap = len(question_terms & searchable_terms)
    modality_boost = 0.0
    if modality_hint and match.modality == modality_hint:
        modality_boost = 0.18

    return match.score + lexical_overlap * 0.025 + modality_boost


def _modality_hint(question_terms: set[str]) -> str | None:
    if question_terms & {"image", "poster", "screenshot", "diagram", "photo", "picture"}:
        return "image"
    if question_terms & {"audio", "transcript", "recording", "briefing", "spoken"}:
        return "audio"
    if question_terms & {"video", "frame", "slide", "slides", "clip"}:
        return "video"
    return None


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_]+", text.lower())
        if len(token) > 2
    }
