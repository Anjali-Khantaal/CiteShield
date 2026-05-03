from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.routes.health import get_health_client, get_health_settings


class HealthyClient:
    def collection_exists(self, _collection_name: str) -> bool:
        return True


def test_health_allows_local_frontend_origin() -> None:
    settings = get_settings().model_copy(update={"generator_backend": "extractive"})
    app.dependency_overrides[get_health_settings] = lambda: settings
    app.dependency_overrides[get_health_client] = lambda: HealthyClient()

    try:
        response = TestClient(app).get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
