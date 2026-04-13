import re
from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.config import get_settings
from app.main import app
from app.metrics import get_metrics_client, get_metrics_settings
from app.routes.ingest import (
    get_ingest_client,
    get_ingest_embedder,
    get_ingest_settings,
)
from app.routes.query import (
    get_query_client,
    get_query_embedder,
    get_query_generator,
    get_query_settings,
)
from app.services.generator import ExtractiveAnswerGenerator


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


def test_metrics_endpoint_exposes_request_ingest_latency_and_gauge_metrics(tmp_path: Path) -> None:
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": "documents",
            "chunk_size_chars": 700,
            "retrieval_top_k": 3,
        }
    )
    embedder = KeywordEmbedder()
    tenant_a_key = get_settings().tenant_a_api_key

    app.dependency_overrides[get_ingest_settings] = lambda: settings
    app.dependency_overrides[get_ingest_embedder] = lambda: embedder
    app.dependency_overrides[get_ingest_client] = lambda: client
    app.dependency_overrides[get_query_settings] = lambda: settings
    app.dependency_overrides[get_query_embedder] = lambda: embedder
    app.dependency_overrides[get_query_client] = lambda: client
    app.dependency_overrides[get_query_generator] = lambda: ExtractiveAnswerGenerator()
    app.dependency_overrides[get_metrics_settings] = lambda: settings
    app.dependency_overrides[get_metrics_client] = lambda: client

    try:
        test_client = TestClient(app)
        ingest_response = test_client.post(
            "/ingest",
            json={
                "source": "remote_work_policy.md",
                "text": "Tenant A requires VPN access for internal dashboards.",
            },
            headers={"X-API-Key": tenant_a_key},
        )
        query_response = test_client.post(
            "/query",
            json={"question": "What is the VPN rule?", "top_k": 3},
            headers={"X-API-Key": tenant_a_key},
        )
        metrics_response = test_client.get("/metrics")
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert ingest_response.status_code == 200
    assert query_response.status_code == 200
    assert metrics_response.status_code == 200
    assert metrics_response.headers["content-type"].startswith("text/plain")

    body = metrics_response.text
    assert "rag_requests_total" in body
    assert "rag_ingest_total" in body
    assert "rag_retrieval_errors_total" in body
    assert "rag_request_latency_seconds" in body
    assert "rag_indexed_chunks" in body
    assert re.search(r'rag_ingest_total\{[^}]*method="POST"[^}]*route="/ingest"[^}]*status_code="200"[^}]*\}', body)
    assert re.search(r'rag_requests_total\{[^}]*method="POST"[^}]*route="/query"[^}]*status_code="200"[^}]*\}', body)
    assert "rag_indexed_chunks 1.0" in body


def test_metrics_endpoint_tracks_retrieval_errors(tmp_path: Path) -> None:
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": "missing_documents",
            "chunk_size_chars": 700,
            "retrieval_top_k": 3,
        }
    )
    embedder = KeywordEmbedder()
    tenant_a_key = get_settings().tenant_a_api_key

    app.dependency_overrides[get_query_settings] = lambda: settings
    app.dependency_overrides[get_query_embedder] = lambda: embedder
    app.dependency_overrides[get_query_client] = lambda: client
    app.dependency_overrides[get_query_generator] = lambda: ExtractiveAnswerGenerator()
    app.dependency_overrides[get_metrics_settings] = lambda: settings
    app.dependency_overrides[get_metrics_client] = lambda: client

    try:
        test_client = TestClient(app, raise_server_exceptions=False)
        failure_response = test_client.post(
            "/query",
            json={"question": "What is the VPN rule?"},
            headers={"X-API-Key": tenant_a_key},
        )
        metrics_response = test_client.get("/metrics")
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert failure_response.status_code == 500
    assert metrics_response.status_code == 200
    assert re.search(
        r'rag_retrieval_errors_total\{[^}]*method="POST"[^}]*route="/query"[^}]*status_code="500"[^}]*\}',
        metrics_response.text,
    )
