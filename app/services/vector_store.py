from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.config import Settings, get_settings
from app.services.chunking import TextChunk

TENANT_ID_FIELD = "tenant_id"
DOC_ID_FIELD = "doc_id"
CHUNK_ID_FIELD = "chunk_id"
SOURCE_FIELD = "source"
TEXT_FIELD = "text"
LINE_RANGE_FIELD = "line_range"
SUPPORTED_CHUNK_PAYLOAD_FIELDS = (
    TENANT_ID_FIELD,
    DOC_ID_FIELD,
    CHUNK_ID_FIELD,
    SOURCE_FIELD,
    TEXT_FIELD,
    "page",
    LINE_RANGE_FIELD,
)


@dataclass(frozen=True)
class IndexedDocument:
    tenant_id: str
    doc_id: str
    source: str
    chunk_count: int


def get_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    settings = settings or get_settings()

    if settings.qdrant_local_path:
        return QdrantClient(
            path=settings.qdrant_local_path,
            timeout=settings.qdrant_timeout_seconds,
        )

    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        grpc_port=settings.qdrant_grpc_port,
        prefer_grpc=settings.qdrant_prefer_grpc,
        timeout=settings.qdrant_timeout_seconds,
    )


def ensure_documents_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    client.create_payload_index(
        collection_name=collection_name,
        field_name=TENANT_ID_FIELD,
        field_schema=models.PayloadSchemaType.KEYWORD,
        wait=True,
    )


def replace_document_chunks(
    client: QdrantClient,
    collection_name: str,
    tenant_id: str,
    doc_id: str,
    source: str,
    chunks: list[TextChunk],
    vectors: list[list[float]],
) -> None:
    if len(chunks) != len(vectors):
        raise ValueError("Chunk count and vector count must match.")

    client.delete(
        collection_name=collection_name,
        points_selector=models.Filter(
            must=[
                models.FieldCondition(
                    key=TENANT_ID_FIELD,
                    match=models.MatchValue(value=tenant_id),
                ),
                models.FieldCondition(
                    key=DOC_ID_FIELD,
                    match=models.MatchValue(value=doc_id),
                ),
            ]
        ),
        wait=True,
    )

    points = [
        models.PointStruct(
            id=_build_point_id(tenant_id=tenant_id, doc_id=doc_id, chunk_id=chunk.chunk_id),
            vector=vector,
            payload={
                TENANT_ID_FIELD: tenant_id,
                DOC_ID_FIELD: doc_id,
                CHUNK_ID_FIELD: chunk.chunk_id,
                SOURCE_FIELD: source,
                TEXT_FIELD: chunk.text,
                LINE_RANGE_FIELD: chunk.line_range,
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    if points:
        client.upsert(
            collection_name=collection_name,
            points=points,
            wait=True,
        )


def count_points_for_tenant(
    client: QdrantClient,
    collection_name: str,
    tenant_id: str,
) -> int:
    result = client.count(
        collection_name=collection_name,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key=TENANT_ID_FIELD,
                    match=models.MatchValue(value=tenant_id),
                )
            ]
        ),
        exact=True,
    )
    return result.count


def count_collection_points(
    client: QdrantClient,
    collection_name: str,
) -> int:
    result = client.count(
        collection_name=collection_name,
        exact=True,
    )
    return result.count


def list_indexed_documents(
    client: QdrantClient,
    collection_name: str,
) -> list[IndexedDocument]:
    grouped: dict[tuple[str, str, str], int] = {}
    offset: str | int | None = None

    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}
            tenant_id = payload.get(TENANT_ID_FIELD)
            doc_id = payload.get(DOC_ID_FIELD)
            source = payload.get(SOURCE_FIELD)

            if not isinstance(tenant_id, str) or not isinstance(doc_id, str) or not isinstance(source, str):
                continue

            key = (tenant_id, doc_id, source)
            grouped[key] = grouped.get(key, 0) + 1

        if offset is None:
            break

    return [
        IndexedDocument(
            tenant_id=tenant_id,
            doc_id=doc_id,
            source=source,
            chunk_count=chunk_count,
        )
        for (tenant_id, doc_id, source), chunk_count in sorted(
            grouped.items(),
            key=lambda item: (item[0][0], item[0][2], item[0][1]),
        )
    ]


def delete_document_chunks(
    client: QdrantClient,
    collection_name: str,
    tenant_id: str,
    doc_id: str,
) -> int:
    count = client.count(
        collection_name=collection_name,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key=TENANT_ID_FIELD,
                    match=models.MatchValue(value=tenant_id),
                ),
                models.FieldCondition(
                    key=DOC_ID_FIELD,
                    match=models.MatchValue(value=doc_id),
                ),
            ]
        ),
        exact=True,
    ).count

    if count == 0:
        return 0

    client.delete(
        collection_name=collection_name,
        points_selector=models.Filter(
            must=[
                models.FieldCondition(
                    key=TENANT_ID_FIELD,
                    match=models.MatchValue(value=tenant_id),
                ),
                models.FieldCondition(
                    key=DOC_ID_FIELD,
                    match=models.MatchValue(value=doc_id),
                ),
            ]
        ),
        wait=True,
    )
    return count


def _build_point_id(tenant_id: str, doc_id: str, chunk_id: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"{tenant_id}:{doc_id}:{chunk_id}"))
