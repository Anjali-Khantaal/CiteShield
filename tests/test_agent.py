from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.config import get_settings
from app.main import app
from app.routes.agent import (
    get_agent_client,
    get_agent_embedder,
    get_agent_generator,
    get_agent_settings,
)
from app.services.generator import ExtractiveAnswerGenerator
from app.services.ingestion import ingest_documents


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


def test_agent_query_uses_tenant_scoped_tools(tmp_path: Path) -> None:
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
            "lifecycle_tracking_path": str(tmp_path / "agent-lifecycle.jsonl"),
        }
    )
    embedder = KeywordEmbedder()
    ingest_documents(data_root=data_root, client=client, embedder=embedder, settings=settings)

    app.dependency_overrides[get_agent_settings] = lambda: settings
    app.dependency_overrides[get_agent_embedder] = lambda: embedder
    app.dependency_overrides[get_agent_client] = lambda: client
    app.dependency_overrides[get_agent_generator] = lambda: ExtractiveAnswerGenerator()

    try:
        response = TestClient(app).post(
            "/agent/query",
            json={"question": "How do I access dashboards over VPN?", "top_k": 3},
            headers={"X-API-Key": get_settings().tenant_a_api_key},
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == "tenant_a"
    assert [tool["tool"] for tool in payload["tools_used"]] == [
        "list_tenant_documents",
        "retrieve_documents",
        "explain_retrieval_diagnostics",
    ]
    assert payload["citations"] == [{"source": "security.md", "chunk_id": 0}]
    assert payload["diagnostics"]["retrieved_sources"] == ["security.md"]
    assert "refunds.md" not in str(payload)


def test_agent_query_requires_tenant_key(tmp_path: Path) -> None:
    response = TestClient(app).post(
        "/agent/query",
        json={"question": "What is the VPN rule?"},
        headers={"X-API-Key": get_settings().superuser_api_key},
    )

    assert response.status_code == 403
