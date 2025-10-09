"""Centralized configuration loader for the Technical Service Assistant.

Provides a typed-ish interface (simple dataclasses avoided to keep dependency surface small)
and lazy environment variable parsing with sensible defaults. All services should import
from this module instead of reading os.environ directly to ensure consistency.
"""

from __future__ import annotations

import os
from functools import lru_cache


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Settings:
    # Database
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    # Models / Retrieval
    embedding_model: str
    rerank_model: str
    chat_model: str
    ollama_url: str

    # Chunking
    chunk_strategy: str

    # Logging / Paths
    log_dir: str
    log_level: str
    uploads_dir: str
    archive_dir: str

    # Reranker / Retrieval tuning
    rerank_top_k: int
    retrieval_candidates: int

    # API
    api_host: str
    api_port: int
    api_key: str | None

    # Feature Flags
    enable_table_extraction: bool
    enable_image_extraction: bool

    # Security / CORS
    allowed_origins: str

    poll_interval_seconds: int

    def as_dict(self):  # convenience for logging / debugging
        return {k: getattr(self, k) for k in self.__dict__.keys()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    # Database
    s.db_host = os.getenv("DB_HOST", "pgvector")
    s.db_port = _get_int("DB_PORT", 5432)
    s.db_name = os.getenv("DB_NAME", "vector_db")
    s.db_user = os.getenv("DB_USER", "postgres")
    s.db_password = os.getenv("DB_PASSWORD", "postgres")

    # Models
    s.embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:v1.5")
    s.rerank_model = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")
    s.chat_model = os.getenv("CHAT_MODEL", "mistral:7b")
    s.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434/api/embeddings")

    # Chunking
    s.chunk_strategy = os.getenv("CHUNK_STRATEGY", "sent_overlap")

    # Logging / Paths
    s.log_dir = os.getenv("LOG_DIR", "/app/logs")
    s.log_level = os.getenv("LOG_LEVEL", "INFO")
    s.uploads_dir = os.getenv("UPLOADS_DIR", "/app/uploads")
    s.archive_dir = os.getenv("ARCHIVE_DIR", os.path.join(s.uploads_dir, "archive"))

    # Retrieval / Rerank
    s.rerank_top_k = _get_int("RERANK_TOP_K", 5)
    s.retrieval_candidates = _get_int("RETRIEVAL_CANDIDATES", 50)

    # API
    s.api_host = os.getenv("API_HOST", "0.0.0.0")
    s.api_port = _get_int("API_PORT", 8008)
    s.api_key = os.getenv("API_KEY")

    # Feature Flags
    s.enable_table_extraction = _get_bool("ENABLE_TABLE_EXTRACTION", True)
    s.enable_image_extraction = _get_bool("ENABLE_IMAGE_EXTRACTION", True)

    # Security
    s.allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")

    # Polling
    s.poll_interval_seconds = _get_int("POLL_INTERVAL_SECONDS", 60)

    return s


if __name__ == "__main__":
    # Simple debug output
    cfg = get_settings()
    for k, v in cfg.as_dict().items():
        print(f"{k}={v}")
