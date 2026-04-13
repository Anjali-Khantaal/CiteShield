from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CiteShield"
    tenant_a_api_key: str = "tenant-a-dev-key"
    tenant_b_api_key: str = "tenant-b-dev-key"
    superuser_api_key: str = "superuser-dev-key"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    embedding_model_cache_dir: str | None = None
    embedding_vector_size: int = 384
    chunk_size_chars: int = 700
    retrieval_top_k: int = 3
    generator_backend: str = "extractive"
    generator_min_score_threshold: float = 0.15
    generator_min_term_overlap: int = 2
    generator_max_sentences: int = 2
    gemini_api_key: str | None = None
    gemini_model_name: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.0
    gemini_max_output_tokens: int = 300
    gemini_timeout_seconds: int = 30
    feature_strict_grounding: bool = True
    frontend_allowed_origins_raw: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:4173,"
        "http://127.0.0.1:4173"
    )

    qdrant_host: str = "127.0.0.1"
    qdrant_http_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_collection_name: str = "documents"
    qdrant_prefer_grpc: bool = False
    qdrant_timeout_seconds: int = 10
    qdrant_local_path: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_http_port}"

    @property
    def frontend_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.frontend_allowed_origins_raw.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
