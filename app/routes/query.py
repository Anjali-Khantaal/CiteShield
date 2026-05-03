from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request, status
from qdrant_client import QdrantClient

from app.auth import TenantContext, get_tenant_context
from app.config import Settings, get_settings
from app.metrics import record_qdrant_latency, record_query_profile, record_retrieval_error
from app.models import CitationResponse, QueryRequest, QueryResponse
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.generator import AnswerGenerator, generate_answer, get_answer_generator
from app.services.retriever import retrieve_chunks
from app.services.vector_store import get_qdrant_client
from app.tracing import LifecycleTracker, generator_model_name

router = APIRouter(tags=["query"])


def get_query_settings() -> Settings:
    return get_settings()


def get_query_embedder(settings: Settings = Depends(get_query_settings)) -> EmbeddingService:
    return get_embedding_service(settings)


def get_query_client(settings: Settings = Depends(get_query_settings)) -> QdrantClient:
    return get_qdrant_client(settings)


def get_query_generator(settings: Settings = Depends(get_query_settings)) -> AnswerGenerator:
    return get_answer_generator(settings)


@router.post("/query", response_model=QueryResponse, response_model_exclude_none=True)
def query_documents(
    request: QueryRequest,
    fastapi_request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_query_settings),
    embedder: EmbeddingService = Depends(get_query_embedder),
    client: QdrantClient = Depends(get_query_client),
    generator: AnswerGenerator = Depends(get_query_generator),
) -> QueryResponse:
    top_k = request.top_k or settings.retrieval_top_k
    fastapi_request.state.tenant_id = tenant.tenant_id

    try:
        retrieval_started = perf_counter()
        matches = retrieve_chunks(
            client=client,
            collection_name=settings.qdrant_collection_name,
            tenant_id=tenant.tenant_id,
            question=request.question,
            embedder=embedder,
            top_k=top_k,
        )
        retrieval_seconds = perf_counter() - retrieval_started
        record_qdrant_latency(operation="search", latency_seconds=retrieval_seconds)
    except Exception:
        record_retrieval_error(route="/query", method="POST", status_code=500)
        raise

    generation_started = perf_counter()
    try:
        answer = generate_answer(question=request.question, retrieved_chunks=matches, generator=generator)
    except RuntimeError as exc:
        generation_seconds = perf_counter() - generation_started
        fastapi_request.state.query_profile = {
            "retrieval_ms": round(retrieval_seconds * 1000, 2),
            "generation_ms": round(generation_seconds * 1000, 2),
            "citation_count": 0,
            "abstained": True,
        }
        record_query_profile(
            route="/query",
            retrieval_seconds=retrieval_seconds,
            generation_seconds=generation_seconds,
            backend=settings.generator_backend,
            citation_count=0,
            abstained=True,
            top_k=top_k,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The configured LLM provider is temporarily unavailable. "
                "Enable GENERATOR_ENABLE_FALLBACK=true for a grounded local fallback, "
                "or retry when the provider recovers."
            ),
        ) from exc
    generation_seconds = perf_counter() - generation_started

    abstained = answer.answer.startswith("I do not have enough reliable context")
    citation_count = len(answer.citations)
    fastapi_request.state.query_profile = {
        "retrieval_ms": round(retrieval_seconds * 1000, 2),
        "generation_ms": round(generation_seconds * 1000, 2),
        "citation_count": citation_count,
        "abstained": abstained,
    }
    record_query_profile(
        route="/query",
        retrieval_seconds=retrieval_seconds,
        generation_seconds=generation_seconds,
        backend=settings.generator_backend,
        citation_count=citation_count,
        abstained=abstained,
        top_k=top_k,
    )
    LifecycleTracker(
        tracking_uri=settings.mlflow_tracking_uri,
        jsonl_path=settings.lifecycle_tracking_path,
    ).log_query_trace(
        request_id=str(getattr(fastapi_request.state, "request_id", "")),
        tenant_id=tenant.tenant_id,
        route="/query",
        embedding_backend=settings.embedding_backend,
        embedding_model_name=settings.embedding_model_name,
        generator_backend=settings.generator_backend,
        generator_model_name=generator_model_name(
            generator_backend=settings.generator_backend,
            gemini_model_name=settings.gemini_model_name,
            openai_compatible_model=settings.openai_compatible_model,
        ),
        top_k=top_k,
        retrieval_latency_ms=round(retrieval_seconds * 1000, 2),
        generation_latency_ms=round(generation_seconds * 1000, 2),
        retrieved_sources=[match.source for match in matches],
        citation_count=citation_count,
        abstained=abstained,
    )

    return QueryResponse(
        answer=answer.answer,
        citations=[
            CitationResponse(
                source=citation.source,
                chunk_id=citation.chunk_id,
                modality=citation.modality,
                media_path=citation.media_path,
                source_url=citation.source_url,
                time_range=citation.time_range,
                frame_time=citation.frame_time,
            )
            for citation in answer.citations
        ],
    )
