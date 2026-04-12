from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.config import get_settings
from app.main import app
from app.routes.query import (
    get_query_client,
    get_query_embedder,
    get_query_settings,
)
from app.services.ingestion import ingest_documents
from app.services.retriever import retrieve_chunks


class KeywordEmbedder:
    embedding_size = 4

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "vpn" in lowered else 0.0,
                    1.0 if "incident" in lowered else 0.0,
                    1.0 if "expense" in lowered else 0.0,
                    1.0 if "refund" in lowered else 0.0,
                ]
            )
        return vectors


def test_retrieve_chunks_returns_only_matching_tenant_records(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    tenant_a_dir = data_root / "tenant_a"
    tenant_b_dir = data_root / "tenant_b"
    tenant_a_dir.mkdir(parents=True)
    tenant_b_dir.mkdir(parents=True)

    (tenant_a_dir / "security.md").write_text(
        "Tenant A requires VPN access for internal dashboards.",
        encoding="utf-8",
    )
    (tenant_b_dir / "expense.md").write_text(
        "Tenant B expense reports are due monthly.",
        encoding="utf-8",
    )

    client = QdrantClient(path=str(tmp_path / "qdrant"))
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": "documents",
            "chunk_size_chars": 700,
        }
    )
    embedder = KeywordEmbedder()

    ingest_documents(
        data_root=data_root,
        client=client,
        embedder=embedder,
        settings=settings,
    )

    matches = retrieve_chunks(
        client=client,
        collection_name="documents",
        tenant_id="tenant_a",
        question="How do I access dashboards over VPN?",
        embedder=embedder,
        top_k=3,
    )
    client.close()

    assert matches
    assert all(match.tenant_id == "tenant_a" for match in matches)
    assert all("Tenant A" in match.text for match in matches)


def test_query_route_returns_answer_and_citations_for_requested_tenant(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    tenant_a_dir = data_root / "tenant_a"
    tenant_b_dir = data_root / "tenant_b"
    tenant_a_dir.mkdir(parents=True)
    tenant_b_dir.mkdir(parents=True)

    (tenant_a_dir / "security.md").write_text(
        "Tenant A requires VPN access for internal dashboards.",
        encoding="utf-8",
    )
    (tenant_b_dir / "refunds.md").write_text(
        "Tenant B refund requests are reviewed by billing operations.",
        encoding="utf-8",
    )

    client = QdrantClient(path=str(tmp_path / "qdrant"))
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": "documents",
            "chunk_size_chars": 700,
            "retrieval_top_k": 3,
        }
    )
    embedder = KeywordEmbedder()

    ingest_documents(
        data_root=data_root,
        client=client,
        embedder=embedder,
        settings=settings,
    )

    def override_settings():
        return settings

    def override_embedder():
        return embedder

    def override_client():
        return client

    app.dependency_overrides[get_query_settings] = override_settings
    app.dependency_overrides[get_query_embedder] = override_embedder
    app.dependency_overrides[get_query_client] = override_client

    try:
        response = TestClient(app).post(
            "/query",
            json={
                "question": "How do I access dashboards over VPN?",
                "tenant_id": "tenant_b",
            },
            headers={"X-API-Key": get_settings().tenant_a_api_key},
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    payload = response.json()
    assert "VPN" in payload["answer"] or "dashboard" in payload["answer"].lower()
    assert payload["citations"]
    assert all(citation["source"] == "security.md" for citation in payload["citations"])
