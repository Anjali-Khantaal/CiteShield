from unittest.mock import MagicMock

from qdrant_client import QdrantClient, models

from app.services.vector_store import TENANT_ID_FIELD, ensure_documents_collection


def test_ensure_documents_collection_creates_collection_in_local_qdrant(
    tmp_path,
) -> None:
    client = QdrantClient(path=str(tmp_path / "qdrant"))

    ensure_documents_collection(
        client=client,
        collection_name="documents",
        vector_size=384,
    )

    collection_names = [item.name for item in client.get_collections().collections]
    collection_info = client.get_collection("documents")
    client.close()

    assert "documents" in collection_names
    assert collection_info.config.params.vectors.size == 384


def test_ensure_documents_collection_requests_tenant_keyword_index() -> None:
    client = MagicMock()
    client.collection_exists.return_value = False

    ensure_documents_collection(
        client=client,
        collection_name="documents",
        vector_size=384,
    )

    client.create_payload_index.assert_called_once_with(
        collection_name="documents",
        field_name=TENANT_ID_FIELD,
        field_schema=models.PayloadSchemaType.KEYWORD,
        wait=True,
    )
