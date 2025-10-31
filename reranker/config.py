"""Centralized configuration loader for the Technical Service Assistant.

Provides a typed-ish interface (simple dataclasses avoided to keep dependency surface small)
and lazy environment variable parsing with sensible defaults. All services should import
from this module instead of reading os.environ directly to ensure consistency.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Load .env automatically if present to mirror top-level config behavior
try:  # pragma: no cover - optional convenience
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent / ".env"
    project_env = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    elif project_env.exists():
        load_dotenv(project_env)
except Exception:
    pass


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

    # Performance & Reasoning
    max_reasoning_time_seconds: int
    max_synthesis_time_seconds: int
    max_context_time_seconds: int
    enable_fast_reasoning: bool
    max_memory_size: int
    max_context_tokens: int

    # Reranker / Retrieval tuning
    rerank_top_k: int
    retrieval_candidates: int

    # API
    api_host: str
    api_port: int
    api_key: str | None

    # Email / SMTP
    smtp_host: str
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_use_tls: bool
    verification_email_sender: str
    verification_email_subject: str
    verification_email_link_base: str
    password_reset_email_sender: str
    password_reset_email_subject: str
    password_reset_email_link_base: str

    # Feature Flags
    enable_table_extraction: bool
    enable_image_extraction: bool
    enable_ocr: bool

    # Security / CORS
    allowed_origins: str

    poll_interval_seconds: int

    # Web Cache
    web_cache_ttl_seconds: int
    web_cache_enabled: bool
    web_cache_max_rows: int
    enable_feedback: bool

    # Timeouts
    embedding_timeout_seconds: int

    # Phase 2B Query Expansion Controls
    enable_semantic_expansion_filter: bool
    expansion_max_terms_base: int
    expansion_similarity_threshold: float
    enable_expansion_instrumentation: bool
    enable_shadow_retrieval: bool
    expansion_adaptive_long_query_tokens: int
    expansion_min_terms: int
    expansion_problem_trigger_bonus: int
    expansion_semantic_test_mode: bool

    # Phase 2C Metadata Weighting & Ensemble Retrieval
    enable_metadata_weighting: bool
    metadata_weight_title: float
    metadata_weight_section: float
    metadata_weight_page: float
    metadata_weight_type: float
    metadata_max_boost: float
    enable_ensemble_retrieval: bool
    ensemble_rrf_k: int
    ensemble_weight_vector: float
    ensemble_weight_bm25: float

    # Large document processing controls
    large_doc_page_threshold: int
    skip_tables_for_large_docs: bool
    skip_images_for_large_docs: bool
    skip_ocr_for_large_docs: bool

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

    # Performance & Reasoning
    s.max_reasoning_time_seconds = _get_int("MAX_REASONING_TIME_SECONDS", 15)
    s.max_synthesis_time_seconds = _get_int("MAX_SYNTHESIS_TIME_SECONDS", 12)
    s.max_context_time_seconds = _get_int("MAX_CONTEXT_TIME_SECONDS", 3)
    s.enable_fast_reasoning = _get_bool("ENABLE_FAST_REASONING", True)
    s.max_memory_size = _get_int("MAX_MEMORY_SIZE", 1000)
    s.max_context_tokens = _get_int("MAX_CONTEXT_TOKENS", 4000)

    # Retrieval / Rerank
    s.rerank_top_k = _get_int("RERANK_TOP_K", 5)
    s.retrieval_candidates = _get_int("RETRIEVAL_CANDIDATES", 50)

    # API
    s.api_host = os.getenv("API_HOST", "0.0.0.0")
    s.api_port = _get_int("API_PORT", 8008)
    s.api_key = os.getenv("API_KEY")

    # Email / SMTP
    s.smtp_host = os.getenv("SMTP_HOST", "localhost")
    s.smtp_port = _get_int("SMTP_PORT", 587)
    s.smtp_username = os.getenv("SMTP_USERNAME")
    s.smtp_password = os.getenv("SMTP_PASSWORD")
    s.smtp_use_tls = _get_bool("SMTP_USE_TLS", True)
    s.verification_email_sender = os.getenv("VERIFICATION_EMAIL_SENDER", "no-reply@technical-service-assistant.local")
    s.verification_email_subject = os.getenv(
        "VERIFICATION_EMAIL_SUBJECT", "Verify your Technical Service Assistant account"
    )
    s.verification_email_link_base = os.getenv(
        "VERIFICATION_EMAIL_LINK_BASE", "https://rni-llm-01.lab.sensus.net/verify-email"
    )
    s.password_reset_email_sender = os.getenv("PASSWORD_RESET_EMAIL_SENDER", s.verification_email_sender)
    s.password_reset_email_subject = os.getenv(
        "PASSWORD_RESET_EMAIL_SUBJECT", "Reset your Technical Service Assistant password"
    )
    s.password_reset_email_link_base = os.getenv(
        "PASSWORD_RESET_EMAIL_LINK_BASE", "https://rni-llm-01.lab.sensus.net/reset-password"
    )

    # Feature Flags
    s.enable_table_extraction = _get_bool("ENABLE_TABLE_EXTRACTION", True)
    s.enable_image_extraction = _get_bool("ENABLE_IMAGE_EXTRACTION", True)
    s.enable_ocr = _get_bool("ENABLE_OCR", True)

    # Security
    s.allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")

    # Polling
    s.poll_interval_seconds = _get_int("POLL_INTERVAL_SECONDS", 60)

    # Timeouts
    s.embedding_timeout_seconds = _get_int("EMBEDDING_TIMEOUT_SECONDS", 60)

    # Web cache
    s.web_cache_ttl_seconds = _get_int("WEB_CACHE_TTL_SECONDS", 900)
    s.web_cache_enabled = _get_bool("WEB_CACHE_ENABLED", True)
    s.web_cache_max_rows = _get_int("WEB_CACHE_MAX_ROWS", 5000)
    s.enable_feedback = _get_bool("ENABLE_FEEDBACK", True)

    # Phase 2B Query Expansion Controls
    s.enable_semantic_expansion_filter = _get_bool("ENABLE_SEMANTIC_EXPANSION_FILTER", False)
    s.expansion_max_terms_base = _get_int("EXPANSION_MAX_TERMS_BASE", 6)
    try:
        s.expansion_similarity_threshold = float(os.getenv("EXPANSION_SIMILARITY_THRESHOLD", "0.55"))
    except ValueError:
        s.expansion_similarity_threshold = 0.55
    s.enable_expansion_instrumentation = _get_bool("ENABLE_EXPANSION_INSTRUMENTATION", True)
    s.enable_shadow_retrieval = _get_bool("ENABLE_SHADOW_RETRIEVAL", False)
    s.expansion_adaptive_long_query_tokens = _get_int("EXPANSION_ADAPTIVE_LONG_QUERY_TOKENS", 12)
    s.expansion_min_terms = _get_int("EXPANSION_MIN_TERMS", 2)
    s.expansion_problem_trigger_bonus = _get_int("EXPANSION_PROBLEM_TRIGGER_BONUS", 2)
    s.expansion_semantic_test_mode = _get_bool("EXPANSION_SEMANTIC_TEST_MODE", False)

    # Phase 2C Metadata Weighting & Ensemble Retrieval
    s.enable_metadata_weighting = _get_bool("ENABLE_METADATA_WEIGHTING", False)
    try:
        s.metadata_weight_title = float(os.getenv("METADATA_WEIGHT_TITLE", "1.2"))
    except ValueError:
        s.metadata_weight_title = 1.2
    try:
        s.metadata_weight_section = float(os.getenv("METADATA_WEIGHT_SECTION", "1.1"))
    except ValueError:
        s.metadata_weight_section = 1.1
    try:
        s.metadata_weight_page = float(os.getenv("METADATA_WEIGHT_PAGE", "1.0"))
    except ValueError:
        s.metadata_weight_page = 1.0
    try:
        s.metadata_weight_type = float(os.getenv("METADATA_WEIGHT_TYPE", "1.05"))
    except ValueError:
        s.metadata_weight_type = 1.05
    try:
        s.metadata_max_boost = float(os.getenv("METADATA_MAX_BOOST", "1.35"))
    except ValueError:
        s.metadata_max_boost = 1.35

    s.enable_ensemble_retrieval = _get_bool("ENABLE_ENSEMBLE_RETRIEVAL", False)
    s.ensemble_rrf_k = _get_int("ENSEMBLE_RRF_K", 60)
    try:
        s.ensemble_weight_vector = float(os.getenv("ENSEMBLE_WEIGHT_VECTOR", "0.55"))
    except ValueError:
        s.ensemble_weight_vector = 0.55
    try:
        s.ensemble_weight_bm25 = float(os.getenv("ENSEMBLE_WEIGHT_BM25", "0.45"))
    except ValueError:
        s.ensemble_weight_bm25 = 0.45

    # Large document controls
    s.large_doc_page_threshold = _get_int("LARGE_DOC_PAGE_THRESHOLD", 400)
    s.skip_tables_for_large_docs = _get_bool("SKIP_TABLES_FOR_LARGE_DOCS", True)
    s.skip_images_for_large_docs = _get_bool("SKIP_IMAGES_FOR_LARGE_DOCS", True)
    s.skip_ocr_for_large_docs = _get_bool("SKIP_OCR_FOR_LARGE_DOCS", True)

    return s


if __name__ == "__main__":
    # Simple debug output
    logging.basicConfig(level=logging.INFO)
    cfg = get_settings()
    for k, v in cfg.as_dict().items():
        logger.info(f"{k}={v}")
