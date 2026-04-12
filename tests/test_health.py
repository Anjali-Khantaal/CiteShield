from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.routes.health import get_health_client, get_health_settings


class HealthyClient:
    def collection_exists(self, _collection_name: str) -> bool:
        return True


class FailingClient:
    def collection_exists(self, _collection_name: str) -> bool:
        raise RuntimeError("qdrant unavailable")


def test_health_returns_ok() -> None:
    app.dependency_overrides[get_health_client] = lambda: HealthyClient()

    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "qdrant": "ok",
        "generator": "configured",
    }


def test_health_returns_degraded_when_qdrant_is_unavailable() -> None:
    app.dependency_overrides[get_health_client] = lambda: FailingClient()

    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "qdrant": "unavailable",
        "generator": "configured",
    }


def test_health_returns_degraded_when_generator_is_not_configured() -> None:
    invalid_settings = get_settings().model_copy(update={"generator_backend": "missing-backend"})
    app.dependency_overrides[get_health_settings] = lambda: invalid_settings
    app.dependency_overrides[get_health_client] = lambda: HealthyClient()

    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "qdrant": "ok",
        "generator": "not_configured",
    }
