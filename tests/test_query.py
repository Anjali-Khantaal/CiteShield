import json
from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.config import get_settings
from app.main import app
from app.routes.query import (
    get_query_client,
    get_query_embedder,
    get_query_generator,
    get_query_settings,
)
from app.services.generator import ExtractiveAnswerGenerator
from app.services.ingestion import ingest_documents
from app.services.retriever import RetrievalMatch, _rerank_for_query_intent, retrieve_chunks


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


def test_query_intent_rerank_prefers_image_source_for_poster_question() -> None:
    matches = [
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="security_guidelines",
            chunk_id=0,
            source="security_guidelines.md",
            text="Approved production access requires MFA, a managed device, and an active ticket.",
            line_range=None,
            score=0.47,
        ),
        RetrievalMatch(
            tenant_id="tenant_a",
            doc_id="tenant_a_security_access_poster",
            chunk_id=0,
            source="derived/multimodal/tenant_a_security_access_poster.md",
            text=(
                "Tenant A Security Access Poster. Approved production access requires MFA, "
                "a managed device, and an active ticket."
            ),
            line_range=None,
            score=0.43,
            modality="image",
            media_path="media/images/security_access_poster.png",
        ),
    ]

    reranked = _rerank_for_query_intent(
        question="What does the security access poster say is required for approved production access?",
        matches=matches,
    )

    assert reranked[0].source == "derived/multimodal/tenant_a_security_access_poster.md"
    assert reranked[0].modality == "image"


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
            "generator_backend": "extractive",
            "lifecycle_tracking_path": str(tmp_path / "query-lifecycle.jsonl"),
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

    def override_generator():
        return ExtractiveAnswerGenerator()

    app.dependency_overrides[get_query_settings] = override_settings
    app.dependency_overrides[get_query_embedder] = override_embedder
    app.dependency_overrides[get_query_client] = override_client
    app.dependency_overrides[get_query_generator] = override_generator

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

    trace = json.loads((tmp_path / "query-lifecycle.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert trace["event"] == "query_trace"
    assert trace["tenant_id"] == "tenant_a"
    assert trace["params"]["generator_backend"] == "extractive"
    assert trace["params"]["retrieval_top_k"] == 3
    assert trace["metrics"]["citation_count"] >= 1
    assert trace["retrieved_sources"] == ["security.md"]


class FailingGenerator:
    def generate_answer(self, question, retrieved_chunks):
        raise RuntimeError("provider unavailable")


def test_query_route_returns_503_when_generator_provider_is_unavailable(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    tenant_a_dir = data_root / "tenant_a"
    tenant_a_dir.mkdir(parents=True)
    (tenant_a_dir / "security.md").write_text(
        "Tenant A requires VPN access for internal dashboards.",
        encoding="utf-8",
    )

    client = QdrantClient(path=str(tmp_path / "qdrant"))
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": "documents",
            "chunk_size_chars": 700,
            "retrieval_top_k": 3,
            "generator_backend": "gemini",
            "lifecycle_tracking_path": str(tmp_path / "query-lifecycle.jsonl"),
        }
    )
    embedder = KeywordEmbedder()
    ingest_documents(
        data_root=data_root,
        client=client,
        embedder=embedder,
        settings=settings,
    )

    app.dependency_overrides[get_query_settings] = lambda: settings
    app.dependency_overrides[get_query_embedder] = lambda: embedder
    app.dependency_overrides[get_query_client] = lambda: client
    app.dependency_overrides[get_query_generator] = lambda: FailingGenerator()

    try:
        response = TestClient(app).post(
            "/query",
            json={"question": "How do I access dashboards over VPN?"},
            headers={"X-API-Key": get_settings().tenant_a_api_key},
        )
    finally:
        app.dependency_overrides.clear()
        client.close()

    assert response.status_code == 503
    assert "LLM provider is temporarily unavailable" in response.json()["detail"]
