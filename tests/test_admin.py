from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.config import get_settings
from app.main import app
from app.routes.admin import get_admin_client, get_admin_settings
from app.routes.ingest import (
    get_ingest_client,
    get_ingest_embedder,
    get_ingest_settings,
)


class KeywordEmbedder:
    embedding_size = 4

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "vpn" in lowered or "dashboard" in lowered else 0.0,
                    1.0 if "incident" in lowered else 0.0,
                    1.0 if "expense" in lowered else 0.0,
                    1.0 if "refund" in lowered else 0.0,
                ]
            )
        return vectors


def _make_test_client(tmp_path: Path) -> tuple[TestClient, QdrantClient]:
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": "documents",
            "chunk_size_chars": 700,
            "retrieval_top_k": 3,
        }
    )
    embedder = KeywordEmbedder()

    app.dependency_overrides[get_ingest_settings] = lambda: settings
    app.dependency_overrides[get_ingest_embedder] = lambda: embedder
    app.dependency_overrides[get_ingest_client] = lambda: client
    app.dependency_overrides[get_admin_settings] = lambda: settings
    app.dependency_overrides[get_admin_client] = lambda: client

    return TestClient(app), client


def test_superuser_can_list_documents_across_tenants(tmp_path: Path) -> None:
    test_client, client = _make_test_client(tmp_path)
    tenant_a_key = get_settings().tenant_a_api_key
    tenant_b_key = get_settings().tenant_b_api_key
    superuser_key = get_settings().superuser_api_key

    try:
        test_client.post(
            "/ingest",
            json={
                "source": "remote_work_policy.md",
                "text": "Tenant A requires VPN access for internal dashboards.",
            },
            headers={"X-API-Key": tenant_a_key},
        )
        test_client.post(
            "/ingest",
            json={
                "source": "expense_policy.md",
                "text": "Tenant B refund requests are reviewed by billing operations.",
            },
            headers={"X-API-Key": tenant_b_key},
        )
        response = test_client.get(
            "/admin/documents",
            headers={"X-API-Key": superuser_key},
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    body = response.json()
    assert body["total_documents"] == 2
    assert body["total_chunks"] == 2
    assert body["documents"] == [
        {
            "tenant_id": "tenant_a",
            "doc_id": "remote_work_policy",
            "source": "remote_work_policy.md",
            "chunk_count": 1,
            "accessible_by": ["tenant_a"],
        },
        {
            "tenant_id": "tenant_b",
            "doc_id": "expense_policy",
            "source": "expense_policy.md",
            "chunk_count": 1,
            "accessible_by": ["tenant_b"],
        },
    ]


def test_tenant_key_cannot_list_documents_across_tenants(tmp_path: Path) -> None:
    test_client, client = _make_test_client(tmp_path)

    try:
        response = test_client.get(
            "/admin/documents",
            headers={"X-API-Key": get_settings().tenant_a_api_key},
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 403
    assert response.json()["detail"] == "Superuser key required."


def test_superuser_can_delete_document(tmp_path: Path) -> None:
    test_client, client = _make_test_client(tmp_path)
    tenant_a_key = get_settings().tenant_a_api_key
    superuser_key = get_settings().superuser_api_key

    try:
        ingest_response = test_client.post(
            "/ingest",
            json={
                "source": "remote_work_policy.md",
                "text": "Tenant A requires VPN access for internal dashboards.",
            },
            headers={"X-API-Key": tenant_a_key},
        )
        delete_response = test_client.delete(
            "/admin/documents/tenant_a/remote_work_policy",
            headers={"X-API-Key": superuser_key},
        )
        inventory_response = test_client.get(
            "/admin/documents",
            headers={"X-API-Key": superuser_key},
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert ingest_response.status_code == 200
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "tenant_id": "tenant_a",
        "doc_id": "remote_work_policy",
        "deleted_chunks": 1,
    }
    assert inventory_response.status_code == 200
    assert inventory_response.json()["documents"] == []
