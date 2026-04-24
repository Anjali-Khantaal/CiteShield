from app.config import Settings
from app.services.embeddings import HashEmbeddingService, get_embedding_service


def test_hash_embedding_service_is_deterministic_and_normalized() -> None:
    service = HashEmbeddingService(vector_size=8)
    vectors = service.embed_texts(["VPN required", "VPN required"])

    assert len(vectors) == 2
    assert vectors[0] == vectors[1]
    norm = sum(value * value for value in vectors[0]) ** 0.5
    assert round(norm, 6) == 1.0


def test_get_embedding_service_returns_hash_backend() -> None:
    settings = Settings(embedding_backend="hash", embedding_vector_size=16)
    service = get_embedding_service(settings)

    assert isinstance(service, HashEmbeddingService)
    assert service.embedding_size == 16
