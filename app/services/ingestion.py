from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Protocol

from qdrant_client import QdrantClient

from app.config import Settings, get_settings
from app.services.chunking import TextChunk, chunk_text
from app.services.vector_store import (
    count_points_for_tenant,
    ensure_documents_collection,
    replace_document_chunks,
)

SUPPORTED_SOURCE_EXTENSIONS = {".md", ".markdown", ".txt"}
TENANT_IDS = ("tenant_a", "tenant_b")


class Embedder(Protocol):
    @property
    def embedding_size(self) -> int: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class SourceDocument:
    tenant_id: str
    doc_id: str
    source: str
    text: str
    metadata: dict[str, str | None]


@dataclass(frozen=True)
class DocumentIngestionResult:
    tenant_id: str
    doc_id: str
    source: str
    chunk_count: int


@dataclass(frozen=True)
class IngestionSummary:
    collection_name: str
    document_count: int
    chunk_count: int
    tenant_chunk_counts: dict[str, int]
    documents: list[DocumentIngestionResult]


def load_source_documents(data_root: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for tenant_id in TENANT_IDS:
        tenant_dir = data_root / tenant_id
        if not tenant_dir.exists():
            continue

        for source_path in sorted(tenant_dir.rglob("*")):
            if not source_path.is_file() or source_path.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
                continue

            relative_source = source_path.relative_to(tenant_dir).as_posix()
            doc_id = source_path.stem
            text = source_path.read_text(encoding="utf-8").strip()
            if not text:
                continue

            documents.append(
                SourceDocument(
                    tenant_id=tenant_id,
                    doc_id=doc_id,
                    source=relative_source,
                    text=text,
                    metadata=_load_source_metadata(source_path),
                )
            )

    return documents


def ingest_documents(
    *,
    data_root: Path,
    client: QdrantClient,
    embedder: Embedder,
    settings: Settings | None = None,
) -> IngestionSummary:
    settings = settings or get_settings()
    ensure_documents_collection(
        client=client,
        collection_name=settings.qdrant_collection_name,
        vector_size=embedder.embedding_size,
    )

    documents = load_source_documents(data_root)
    results: list[DocumentIngestionResult] = []
    tenant_chunk_counts = {tenant_id: 0 for tenant_id in TENANT_IDS}
    total_chunks = 0

    for document in documents:
        chunks = _attach_metadata(
            chunk_text(document.text, max_chars=settings.chunk_size_chars),
            document.metadata,
        )
        vectors = embedder.embed_texts([chunk.text for chunk in chunks])

        replace_document_chunks(
            client=client,
            collection_name=settings.qdrant_collection_name,
            tenant_id=document.tenant_id,
            doc_id=document.doc_id,
            source=document.source,
            chunks=chunks,
            vectors=vectors,
        )

        results.append(
            DocumentIngestionResult(
                tenant_id=document.tenant_id,
                doc_id=document.doc_id,
                source=document.source,
                chunk_count=len(chunks),
            )
        )
        tenant_chunk_counts[document.tenant_id] += len(chunks)
        total_chunks += len(chunks)

    return IngestionSummary(
        collection_name=settings.qdrant_collection_name,
        document_count=len(results),
        chunk_count=total_chunks,
        tenant_chunk_counts=tenant_chunk_counts,
        documents=results,
    )


def ingest_source_document(
    *,
    tenant_id: str,
    source: str,
    text: str,
    client: QdrantClient,
    embedder: Embedder,
    settings: Settings | None = None,
) -> DocumentIngestionResult:
    settings = settings or get_settings()
    ensure_documents_collection(
        client=client,
        collection_name=settings.qdrant_collection_name,
        vector_size=embedder.embedding_size,
    )

    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("Document text must not be empty.")

    doc_id = _derive_doc_id(source)
    chunks = chunk_text(normalized_text, max_chars=settings.chunk_size_chars)
    vectors = embedder.embed_texts([chunk.text for chunk in chunks])

    replace_document_chunks(
        client=client,
        collection_name=settings.qdrant_collection_name,
        tenant_id=tenant_id,
        doc_id=doc_id,
        source=source,
        chunks=chunks,
        vectors=vectors,
    )

    return DocumentIngestionResult(
        tenant_id=tenant_id,
        doc_id=doc_id,
        source=source,
        chunk_count=len(chunks),
    )


def build_tenant_point_counts(
    *,
    client: QdrantClient,
    collection_name: str,
) -> dict[str, int]:
    return {
        tenant_id: count_points_for_tenant(
            client=client,
            collection_name=collection_name,
            tenant_id=tenant_id,
        )
        for tenant_id in TENANT_IDS
    }


def _derive_doc_id(source: str) -> str:
    stem = Path(source).stem.strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "_", stem).strip("_")
    return normalized or "document"


def _load_source_metadata(source_path: Path) -> dict[str, str | None]:
    metadata_path = source_path.with_suffix(".metadata.json")
    if not metadata_path.exists():
        return {}

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Metadata sidecar must be an object: {metadata_path}")

    supported_keys = {
        "modality",
        "media_path",
        "source_url",
        "license",
        "attribution",
        "time_range",
        "frame_time",
    }
    return {
        key: str(value)
        for key, value in payload.items()
        if key in supported_keys and value is not None and str(value).strip()
    }


def _attach_metadata(chunks: list[TextChunk], metadata: dict[str, str | None]) -> list[TextChunk]:
    if not metadata:
        return chunks

    return [
        TextChunk(
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            line_range=chunk.line_range,
            metadata=metadata,
        )
        for chunk in chunks
    ]
