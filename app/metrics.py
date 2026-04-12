from fastapi import APIRouter, Depends, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from qdrant_client import QdrantClient

from app.config import Settings, get_settings
from app.services.vector_store import count_collection_points, get_qdrant_client

REQUEST_LABELS = ("route", "method", "status_code")

rag_requests_total = Counter(
    "rag_requests_total",
    "Total HTTP requests handled by CiteShield.",
    REQUEST_LABELS,
)
rag_ingest_total = Counter(
    "rag_ingest_total",
    "Total successful ingest requests handled by CiteShield.",
    REQUEST_LABELS,
)
rag_retrieval_errors_total = Counter(
    "rag_retrieval_errors_total",
    "Total retrieval errors raised while serving query requests.",
    REQUEST_LABELS,
)
rag_request_latency_seconds = Histogram(
    "rag_request_latency_seconds",
    "HTTP request latency for CiteShield endpoints.",
    REQUEST_LABELS,
)
rag_indexed_chunks = Gauge(
    "rag_indexed_chunks",
    "Current number of indexed chunks stored in Qdrant.",
)

router = APIRouter(tags=["metrics"])


def get_metrics_settings() -> Settings:
    return get_settings()


def get_metrics_client(
    settings: Settings = Depends(get_metrics_settings),
) -> QdrantClient:
    return get_qdrant_client(settings)


def resolve_route_label(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        return route_path
    return request.url.path


def record_request(
    *,
    route: str,
    method: str,
    status_code: int | str,
    duration_seconds: float,
) -> None:
    labels = {
        "route": route,
        "method": method,
        "status_code": str(status_code),
    }
    rag_requests_total.labels(**labels).inc()
    rag_request_latency_seconds.labels(**labels).observe(duration_seconds)


def record_ingest(
    *,
    route: str,
    method: str,
    status_code: int | str,
) -> None:
    rag_ingest_total.labels(
        route=route,
        method=method,
        status_code=str(status_code),
    ).inc()


def record_retrieval_error(
    *,
    route: str,
    method: str,
    status_code: int | str,
) -> None:
    rag_retrieval_errors_total.labels(
        route=route,
        method=method,
        status_code=str(status_code),
    ).inc()


def refresh_indexed_chunks(
    *,
    client: QdrantClient,
    collection_name: str,
) -> None:
    try:
        rag_indexed_chunks.set(
            count_collection_points(
                client=client,
                collection_name=collection_name,
            )
        )
    except Exception:
        # Scrapes should stay available even if Qdrant is temporarily unavailable.
        return


@router.get("/metrics", include_in_schema=False)
def get_metrics(
    settings: Settings = Depends(get_metrics_settings),
    client: QdrantClient = Depends(get_metrics_client),
) -> Response:
    refresh_indexed_chunks(
        client=client,
        collection_name=settings.qdrant_collection_name,
    )
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
