from pathlib import Path

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_tenant_can_fetch_own_media(tmp_path: Path) -> None:
    media_path = tmp_path / "tenant_a/media/images/security.png"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"image-bytes")
    settings = get_settings().model_copy(update={"data_root": str(tmp_path)})
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        response = TestClient(app).get(
            "/media/tenant_a/media/images/security.png",
            headers={"X-API-Key": settings.tenant_a_api_key},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.content == b"image-bytes"


def test_tenant_cannot_fetch_other_tenant_media(tmp_path: Path) -> None:
    media_path = tmp_path / "tenant_b/media/audio/briefing.wav"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"audio-bytes")
    settings = get_settings().model_copy(update={"data_root": str(tmp_path)})
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        response = TestClient(app).get(
            "/media/tenant_b/media/audio/briefing.wav",
            headers={"X-API-Key": settings.tenant_a_api_key},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
