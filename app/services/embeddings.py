import hashlib
import math
import re
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import Settings, get_settings

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


@lru_cache
def _load_model(model_name: str, cache_dir: str | None) -> SentenceTransformer:
    return SentenceTransformer(
        model_name_or_path=model_name,
        cache_folder=cache_dir,
        token=False,
    )


class EmbeddingService:
    @property
    def embedding_size(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    def embed_texts(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - interface
        raise NotImplementedError


class SentenceTransformerEmbeddingService(EmbeddingService):
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


class HashEmbeddingService(EmbeddingService):
    def __init__(self, vector_size: int = 384) -> None:
        if vector_size <= 0:
            raise ValueError("embedding_vector_size must be > 0")
        self.vector_size = vector_size

    @property
    def embedding_size(self) -> int:
        return self.vector_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        tokens = _TOKEN_PATTERN.findall(text.lower()) or ["__empty__"]
        vector = [0.0] * self.vector_size

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.vector_size
            sign = -1.0 if digest[4] % 2 else 1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[idx] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def get_embedding_service(settings: Settings | None = None) -> EmbeddingService:
    settings = settings or get_settings()
    backend = settings.embedding_backend.strip().lower()

    if backend == "sentence_transformers":
        return SentenceTransformerEmbeddingService(
            model_name=settings.embedding_model_name,
            cache_dir=settings.embedding_model_cache_dir,
            batch_size=settings.embedding_batch_size,
        )

    if backend == "hash":
        return HashEmbeddingService(vector_size=settings.embedding_vector_size)

    raise ValueError(f"Unsupported embedding backend: {settings.embedding_backend}")
