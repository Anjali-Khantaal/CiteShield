from time import perf_counter

from fastapi import APIRouter, Depends, Request
from qdrant_client import QdrantClient

from app.auth import TenantContext, get_tenant_context
from app.config import Settings, get_settings
from app.metrics import record_qdrant_latency, record_query_profile, record_retrieval_error
from app.models import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentToolTrace,
    CitationResponse,
    RetrievalDiagnosticResponse,
)
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.generator import AnswerGenerator, generate_answer, get_answer_generator
from app.services.retriever import RetrievalMatch, retrieve_chunks
from app.services.vector_store import get_qdrant_client, list_indexed_documents
from app.tracing import LifecycleTracker, generator_model_name

router = APIRouter(prefix="/agent", tags=["agent"])


def get_agent_settings() -> Settings:
    return get_settings()


def get_agent_embedder(settings: Settings = Depends(get_agent_settings)) -> EmbeddingService:
    return get_embedding_service(settings)


def get_agent_client(settings: Settings = Depends(get_agent_settings)) -> QdrantClient:
    return get_qdrant_client(settings)


def get_agent_generator(settings: Settings = Depends(get_agent_settings)) -> AnswerGenerator:
    return get_answer_generator(settings)


@router.post("/query", response_model=AgentQueryResponse, response_model_exclude_none=True)
def agent_query(
    request: AgentQueryRequest,
    fastapi_request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    settings: Settings = Depends(get_agent_settings),
    embedder: EmbeddingService = Depends(get_agent_embedder),
    client: QdrantClient = Depends(get_agent_client),
    generator: AnswerGenerator = Depends(get_agent_generator),
) -> AgentQueryResponse:
    """Deterministic tool-using RAG agent.

    The endpoint intentionally runs a fixed tool sequence instead of allowing
    unconstrained autonomous planning.
    """

    top_k = request.top_k or settings.retrieval_top_k
    fastapi_request.state.tenant_id = tenant.tenant_id
    tools_used: list[AgentToolTrace] = []

    documents = _list_tenant_documents(
        client=client,
        collection_name=settings.qdrant_collection_name,
        tenant_id=tenant.tenant_id,
    )
    tools_used.append(
        AgentToolTrace(
            tool="list_tenant_documents",
            summary=f"Found {len(documents)} indexed tenant document(s).",
        )
    )

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
        record_qdrant_latency(operation="agent_search", latency_seconds=retrieval_seconds)
    except Exception:
        record_retrieval_error(route="/agent/query", method="POST", status_code=500)
        raise

    tools_used.append(
        AgentToolTrace(
            tool="retrieve_documents",
            summary=f"Retrieved {len(matches)} tenant-scoped chunk(s).",
        )
    )

    generation_started = perf_counter()
    answer = generate_answer(question=request.question, retrieved_chunks=matches, generator=generator)
    generation_seconds = perf_counter() - generation_started

    abstained = answer.answer.startswith("I do not have enough reliable context")
    citation_count = len(answer.citations)
    diagnostics = _build_diagnostics(top_k=top_k, matches=matches, abstained=abstained)
    tools_used.append(
        AgentToolTrace(
            tool="explain_retrieval_diagnostics",
            summary=(
                f"top_k={diagnostics.top_k}, retrieved={diagnostics.retrieved_count}, "
                f"citations={citation_count}, abstained={abstained}"
            ),
        )
    )

    fastapi_request.state.query_profile = {
        "retrieval_ms": round(retrieval_seconds * 1000, 2),
        "generation_ms": round(generation_seconds * 1000, 2),
        "citation_count": citation_count,
        "abstained": abstained,
    }
    record_query_profile(
        route="/agent/query",
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
        route="/agent/query",
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

    return AgentQueryResponse(
        tenant_id=tenant.tenant_id,
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
        tools_used=tools_used,
        diagnostics=diagnostics if request.include_diagnostics else None,
    )


def _list_tenant_documents(*, client: QdrantClient, collection_name: str, tenant_id: str) -> list[str]:
    return [
        document.source
        for document in list_indexed_documents(client=client, collection_name=collection_name)
        if document.tenant_id == tenant_id
    ]


def _build_diagnostics(*, top_k: int, matches: list[RetrievalMatch], abstained: bool) -> RetrievalDiagnosticResponse:
    scores = [match.score for match in matches]
    return RetrievalDiagnosticResponse(
        top_k=top_k,
        retrieved_count=len(matches),
        retrieved_sources=[match.source for match in matches],
        max_score=round(max(scores), 4) if scores else None,
        min_score=round(min(scores), 4) if scores else None,
        abstained=abstained,
    )
