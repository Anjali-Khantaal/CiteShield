from dataclasses import dataclass
from typing import Protocol

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.services.vector_store import (
    CHUNK_ID_FIELD,
    DOC_ID_FIELD,
    LINE_RANGE_FIELD,
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
            )
        )

    return matches


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
