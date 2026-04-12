import pytest
from pathlib import Path

from qdrant_client import QdrantClient

from app.config import get_settings
from app.services.ingestion import ingest_documents


class FakeEmbedder:
    embedding_size = 4

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0, 0.0, 0.0] for text in texts]


@pytest.mark.filterwarnings(
    "ignore:Payload indexes have no effect in the local Qdrant:UserWarning"
)
def test_ingest_documents_loads_both_tenants_into_qdrant_local(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    tenant_a_dir = data_root / "tenant_a"
    tenant_b_dir = data_root / "tenant_b"
    tenant_a_dir.mkdir(parents=True)
    tenant_b_dir.mkdir(parents=True)

    (tenant_a_dir / "policy.md").write_text(
        "# Policy\n\nTenant A requires VPN access for internal dashboards.\n",
        encoding="utf-8",
    )
    (tenant_b_dir / "handbook.md").write_text(
        "# Handbook\n\nTenant B acknowledges high severity incidents within fifteen minutes.\n",
        encoding="utf-8",
    )

    client = QdrantClient(path=str(tmp_path / "qdrant"))
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": "documents",
            "chunk_size_chars": 700,
        }
    )

    summary = ingest_documents(
        data_root=data_root,
        client=client,
        embedder=FakeEmbedder(),
        settings=settings,
    )

    records, _ = client.scroll(
        collection_name="documents",
        limit=20,
        with_payload=True,
        with_vectors=False,
    )
    client.close()

    tenant_ids = {record.payload["tenant_id"] for record in records}
    doc_ids = {record.payload["doc_id"] for record in records}

    assert summary.document_count == 2
    assert summary.chunk_count == 2
    assert summary.tenant_chunk_counts == {"tenant_a": 1, "tenant_b": 1}
    assert tenant_ids == {"tenant_a", "tenant_b"}
    assert doc_ids == {"policy", "handbook"}
    assert all("source" in record.payload for record in records)
    assert all("text" in record.payload for record in records)
    assert all("line_range" in record.payload for record in records)
