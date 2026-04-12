from fastapi import APIRouter, Depends, Response, status
from qdrant_client import QdrantClient

from app.config import Settings, get_settings
from app.models import HealthResponse
from app.services.generator import get_answer_generator
from app.services.vector_store import get_qdrant_client

router = APIRouter(tags=["health"])


def get_health_settings() -> Settings:
    return get_settings()


def get_health_client(
    settings: Settings = Depends(get_health_settings),
) -> QdrantClient:
    return get_qdrant_client(settings)


@router.get("/health", response_model=HealthResponse)
def health_check(
    response: Response,
    settings: Settings = Depends(get_health_settings),
    client: QdrantClient = Depends(get_health_client),
) -> HealthResponse:
    qdrant_status = "ok"
    generator_status = "configured"
    overall_status = "ok"

    try:
        client.collection_exists(settings.qdrant_collection_name)
    except Exception:
        qdrant_status = "unavailable"
        overall_status = "degraded"

    try:
        get_answer_generator(settings)
    except Exception:
        generator_status = "not_configured"
        overall_status = "degraded"

    if overall_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        qdrant=qdrant_status,
        generator=generator_status,
    )
