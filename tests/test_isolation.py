from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.config import get_settings
from app.main import app
from app.routes.ingest import (
    get_ingest_client,
    get_ingest_embedder,
    get_ingest_settings,
)
from app.routes.query import (
    get_query_client,
    get_query_embedder,
    get_query_settings,
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


def _override_app_dependencies(*, client: QdrantClient, settings, embedder: KeywordEmbedder) -> None:
    app.dependency_overrides[get_ingest_settings] = lambda: settings
    app.dependency_overrides[get_ingest_embedder] = lambda: embedder
    app.dependency_overrides[get_ingest_client] = lambda: client
    app.dependency_overrides[get_query_settings] = lambda: settings
    app.dependency_overrides[get_query_embedder] = lambda: embedder
    app.dependency_overrides[get_query_client] = lambda: client


def _make_test_client(tmp_path: Path) -> tuple[TestClient, QdrantClient]:
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": "documents",
            "chunk_size_chars": 700,
            "retrieval_top_k": 3,
        }
    )
    _override_app_dependencies(client=client, settings=settings, embedder=KeywordEmbedder())
    return TestClient(app), client


def _post_json(test_client: TestClient, path: str, *, api_key: str | None, payload: dict):
    headers = {"X-API-Key": api_key} if api_key else None
    return test_client.post(path, json=payload, headers=headers)


def test_ingest_route_works_for_tenant_a(tmp_path: Path) -> None:
    test_client, client = _make_test_client(tmp_path)

    try:
        response = _post_json(
            test_client,
            "/ingest",
            api_key=get_settings().tenant_a_api_key,
            payload={
                "source": "remote_work_policy.md",
                "text": "Tenant A requires VPN access for internal dashboards.",
            },
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant_a",
        "doc_id": "remote_work_policy",
        "source": "remote_work_policy.md",
        "chunk_count": 1,
    }


def test_ingest_route_works_for_tenant_b(tmp_path: Path) -> None:
    test_client, client = _make_test_client(tmp_path)

    try:
        response = _post_json(
            test_client,
            "/ingest",
            api_key=get_settings().tenant_b_api_key,
            payload={
                "source": "expense_policy.md",
                "text": "Tenant B expense reports are due monthly.",
            },
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant_b",
        "doc_id": "expense_policy",
        "source": "expense_policy.md",
        "chunk_count": 1,
    }


def test_query_route_returns_only_tenant_a_citations(tmp_path: Path) -> None:
    test_client, client = _make_test_client(tmp_path)
    tenant_a_key = get_settings().tenant_a_api_key
    tenant_b_key = get_settings().tenant_b_api_key

    try:
        _post_json(
            test_client,
            "/ingest",
            api_key=tenant_a_key,
            payload={
                "source": "remote_work_policy.md",
                "text": "Tenant A requires VPN access for internal dashboards.",
            },
        )
        _post_json(
            test_client,
            "/ingest",
            api_key=tenant_b_key,
            payload={
                "source": "expense_policy.md",
                "text": "Tenant B expense reports are due monthly.",
            },
        )
        response = _post_json(
            test_client,
            "/query",
            api_key=tenant_a_key,
            payload={
                "question": "How do employees access internal dashboards over VPN?",
                "tenant_id": "tenant_b",
            },
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    assert "vpn" in response.json()["answer"].lower() or "dashboard" in response.json()["answer"].lower()
    assert response.json()["citations"] == [{"source": "remote_work_policy.md", "chunk_id": 0}]


def test_query_route_returns_only_tenant_b_citations(tmp_path: Path) -> None:
    test_client, client = _make_test_client(tmp_path)
    tenant_a_key = get_settings().tenant_a_api_key
    tenant_b_key = get_settings().tenant_b_api_key

    try:
        _post_json(
            test_client,
            "/ingest",
            api_key=tenant_a_key,
            payload={
                "source": "remote_work_policy.md",
                "text": "Tenant A requires VPN access for internal dashboards.",
            },
        )
        _post_json(
            test_client,
            "/ingest",
            api_key=tenant_b_key,
            payload={
                "source": "expense_policy.md",
                "text": "Tenant B refund requests are reviewed by billing operations.",
            },
        )
        response = _post_json(
            test_client,
            "/query",
            api_key=tenant_b_key,
            payload={
                "question": "Who reviews refund requests?",
                "tenant_id": "tenant_a",
            },
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    assert "refund" in response.json()["answer"].lower()
    assert response.json()["citations"] == [{"source": "expense_policy.md", "chunk_id": 0}]


def test_invalid_or_missing_api_key_is_rejected(tmp_path: Path) -> None:
    test_client, client = _make_test_client(tmp_path)

    try:
        invalid = _post_json(
            test_client,
            "/query",
            api_key="not-a-real-key",
            payload={"question": "What is the VPN rule?"},
        )
        missing = _post_json(
            test_client,
            "/query",
            api_key=None,
            payload={"question": "What is the VPN rule?"},
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid or missing API key."
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Invalid or missing API key."


def test_malicious_request_pretending_to_be_another_tenant_still_fails(tmp_path: Path) -> None:
    test_client, client = _make_test_client(tmp_path)
    tenant_a_key = get_settings().tenant_a_api_key
    tenant_b_key = get_settings().tenant_b_api_key

    try:
        ingest_a = _post_json(
            test_client,
            "/ingest",
            api_key=tenant_a_key,
            payload={
                "source": "remote_work_policy.md",
                "text": "Tenant A requires VPN access for internal dashboards.",
                "tenant_id": "tenant_b",
            },
        )
        ingest_b = _post_json(
            test_client,
            "/ingest",
            api_key=tenant_b_key,
            payload={
                "source": "expense_policy.md",
                "text": "Tenant B expense reports are due monthly.",
                "tenant_id": "tenant_a",
            },
        )
        query_a = _post_json(
            test_client,
            "/query",
            api_key=tenant_a_key,
            payload={
                "question": "How do employees access internal dashboards over VPN?",
                "tenant_id": "tenant_b",
            },
        )
        query_b = _post_json(
            test_client,
            "/query",
            api_key=tenant_b_key,
            payload={
                "question": "What is the VPN rule?",
                "tenant_id": "tenant_a",
            },
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert ingest_a.status_code == 200
    assert ingest_a.json()["tenant_id"] == "tenant_a"
    assert ingest_b.status_code == 200
    assert ingest_b.json()["tenant_id"] == "tenant_b"
    assert query_a.status_code == 200
    assert query_a.json()["citations"] == [{"source": "remote_work_policy.md", "chunk_id": 0}]
    assert query_b.status_code == 200
    assert "do not have enough reliable context" in query_b.json()["answer"]
    assert query_b.json()["citations"] == []
