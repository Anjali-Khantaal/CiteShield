from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import Settings, get_settings


@lru_cache
def _load_model(model_name: str, cache_dir: str | None) -> SentenceTransformer:
    return SentenceTransformer(
        model_name_or_path=model_name,
        cache_folder=cache_dir,
        token=False,
    )


class EmbeddingService:
    def __init__(
        self,
        model_name: str,
        cache_dir: str | None = None,
        batch_size: int = 32,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.batch_size = batch_size

    @property
    def model(self) -> SentenceTransformer:
        return _load_model(self.model_name, self.cache_dir)

    @property
    def embedding_size(self) -> int:
        model = self.model
        if hasattr(model, "get_embedding_dimension"):
            embedding_size = model.get_embedding_dimension()
        else:
            embedding_size = model.get_sentence_embedding_dimension()
        if embedding_size is None:
            raise ValueError("SentenceTransformer did not report an embedding dimension.")
        return embedding_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()


def get_embedding_service(settings: Settings | None = None) -> EmbeddingService:
    settings = settings or get_settings()
    return EmbeddingService(
        model_name=settings.embedding_model_name,
        cache_dir=settings.embedding_model_cache_dir,
        batch_size=settings.embedding_batch_size,
    )
