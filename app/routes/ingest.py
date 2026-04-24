from fastapi import APIRouter, Depends, HTTPException, Request, status
from qdrant_client import QdrantClient

from app.auth import SessionContext, get_session_context
from app.config import Settings, get_settings
from app.metrics import record_ingest, refresh_indexed_chunks
from app.models import IngestRequest, IngestResponse
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.ingestion import TENANT_IDS, ingest_source_document
from app.services.vector_store import get_qdrant_client

router = APIRouter(tags=["ingest"])


def get_ingest_settings() -> Settings:
    return get_settings()


def get_ingest_embedder(
    settings: Settings = Depends(get_ingest_settings),
) -> EmbeddingService:
    return get_embedding_service(settings)


def get_ingest_client(
    settings: Settings = Depends(get_ingest_settings),
) -> QdrantClient:
    return get_qdrant_client(settings)


@router.post("/ingest", response_model=IngestResponse)
def ingest_document(
    request: IngestRequest,
    fastapi_request: Request,
    session: SessionContext = Depends(get_session_context),
    settings: Settings = Depends(get_ingest_settings),
    embedder: EmbeddingService = Depends(get_ingest_embedder),
    client: QdrantClient = Depends(get_ingest_client),
) -> IngestResponse:
    tenant_id = _resolve_ingest_tenant_id(session=session, request=request)
    fastapi_request.state.tenant_id = tenant_id
    result = ingest_source_document(
        tenant_id=tenant_id,
        source=request.source,
        text=request.text,
        client=client,
        embedder=embedder,
        settings=settings,
    )
    record_ingest(route="/ingest", method="POST", status_code=200)
    refresh_indexed_chunks(
        client=client,
        collection_name=settings.qdrant_collection_name,
    )
    return IngestResponse(
        tenant_id=result.tenant_id,
        doc_id=result.doc_id,
        source=result.source,
        chunk_count=result.chunk_count,
    )


def _resolve_ingest_tenant_id(
    *,
    session: SessionContext,
    request: IngestRequest,
) -> str:
    if session.role == "tenant" and session.tenant_id is not None:
        return session.tenant_id

    if session.role != "superuser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant key or superuser key required.",
        )

    if request.target_tenant is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_tenant is required when using the superuser key.",
        )

    if request.target_tenant not in TENANT_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_tenant must be one of: tenant_a, tenant_b.",
        )

    return request.target_tenant
