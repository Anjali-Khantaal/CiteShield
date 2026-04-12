from fastapi import APIRouter, Depends
from qdrant_client import QdrantClient

from app.auth import TenantContext, get_tenant_context
from app.config import Settings, get_settings
from app.metrics import record_retrieval_error
from app.models import CitationResponse, QueryRequest, QueryResponse
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.generator import (
    AnswerGenerator,
    generate_answer,
    get_answer_generator,
)
from app.services.retriever import retrieve_chunks
from app.services.vector_store import get_qdrant_client

router = APIRouter(tags=["query"])


def get_query_settings() -> Settings:
    return get_settings()


def get_query_embedder(
    settings: Settings = Depends(get_query_settings),
) -> EmbeddingService:
    return get_embedding_service(settings)


def get_query_client(
    settings: Settings = Depends(get_query_settings),
) -> QdrantClient:
    return get_qdrant_client(settings)


def get_query_generator(
    settings: Settings = Depends(get_query_settings),
) -> AnswerGenerator:
    return get_answer_generator(settings)


@router.post("/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_query_settings),
    embedder: EmbeddingService = Depends(get_query_embedder),
    client: QdrantClient = Depends(get_query_client),
    generator: AnswerGenerator = Depends(get_query_generator),
) -> QueryResponse:
    top_k = request.top_k or settings.retrieval_top_k

    try:
        matches = retrieve_chunks(
            client=client,
            collection_name=settings.qdrant_collection_name,
            tenant_id=tenant.tenant_id,
            question=request.question,
            embedder=embedder,
            top_k=top_k,
        )
    except Exception:
        record_retrieval_error(route="/query", method="POST", status_code=500)
        raise
    answer = generate_answer(
        question=request.question,
        retrieved_chunks=matches,
        generator=generator,
    )

    return QueryResponse(
        answer=answer.answer,
        citations=[
            CitationResponse(source=citation.source, chunk_id=citation.chunk_id)
            for citation in answer.citations
        ],
    )
