"""Centralized configuration loader for the Technical Service Assistant.

Provides a typed-ish interface (simple dataclasses avoided to keep dependency surface small)
and lazy environment variable parsing with sensible defaults. All services should import
from this module instead of reading os.environ directly to ensure consistency.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from utils.logging_config import get_logger

logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent

# Load .env file early if present (local development convenience)
try:  # pragma: no cover - simple optional side-effect
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    # Also allow project root .env if config.py moved
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Fallback: look one directory up
        root_env = Path(__file__).parent.parent / ".env"
        if root_env.exists():
            load_dotenv(root_env)
except Exception:
    # Silent failure acceptable; config still works with environment variables / docker-compose
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


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
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
    coding_model: str
    reasoning_model: str
    vision_model: str
    ollama_url: str
    default_model_num_ctx: int
    embedding_model_num_ctx: int
    chat_model_num_ctx: int
    coding_model_num_ctx: int
    reasoning_model_num_ctx: int
    vision_model_num_ctx: int

    # Chunking
    chunk_strategy: str

    # Logging / Paths
    log_dir: str
    log_level: str
    uploads_dir: str
    archive_dir: str
    redis_url: str | None

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
    chat_stream_chunk_words: int
    chat_stream_delay_seconds: float
    generation_timeout_seconds: int

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
    s.embedding_model = os.getenv("EMBEDDING_MODEL", "llama3.2:3b")
    s.rerank_model = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")
    s.chat_model = os.getenv("CHAT_MODEL", "mistral:7b")
    s.coding_model = os.getenv("CODING_MODEL", "codellama:7b")
    s.reasoning_model = os.getenv("REASONING_MODEL", "llama3.2:3b")
    s.vision_model = os.getenv("VISION_MODEL", "llava:7b")
    s.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434/api/embeddings")
    default_model_num_ctx = _get_int("DEFAULT_MODEL_NUM_CTX", 4096)
    s.default_model_num_ctx = default_model_num_ctx
    s.embedding_model_num_ctx = _get_int("EMBEDDING_MODEL_NUM_CTX", default_model_num_ctx)
    s.chat_model_num_ctx = _get_int("CHAT_MODEL_NUM_CTX", default_model_num_ctx)
    s.coding_model_num_ctx = _get_int("CODING_MODEL_NUM_CTX", default_model_num_ctx)
    s.reasoning_model_num_ctx = _get_int("REASONING_MODEL_NUM_CTX", default_model_num_ctx)
    s.vision_model_num_ctx = _get_int("VISION_MODEL_NUM_CTX", default_model_num_ctx)

    # Chunking
    s.chunk_strategy = os.getenv("CHUNK_STRATEGY", "sent_overlap")

    # Logging / Paths
    default_log_dir = os.getenv("LOG_DIR", str(PROJECT_ROOT / "logs"))
    s.log_dir = default_log_dir
    s.log_level = os.getenv("LOG_LEVEL", "INFO")
    s.uploads_dir = os.getenv("UPLOADS_DIR", str(PROJECT_ROOT / "uploads"))
    s.archive_dir = os.getenv("ARCHIVE_DIR", str(PROJECT_ROOT / "archive"))
    s.redis_url = os.getenv("REDIS_URL")

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
    app_url = os.getenv("APP_URL", "https://rni-llm-01.lab.sensus.net")
    s.verification_email_link_base = os.getenv(
        "VERIFICATION_EMAIL_LINK_BASE", f"{app_url}/verify-email"
    )
    s.password_reset_email_sender = os.getenv("PASSWORD_RESET_EMAIL_SENDER", s.verification_email_sender)
    s.password_reset_email_subject = os.getenv(
        "PASSWORD_RESET_EMAIL_SUBJECT", "Reset your Technical Service Assistant password"
    )
    s.password_reset_email_link_base = os.getenv(
        "PASSWORD_RESET_EMAIL_LINK_BASE", f"{app_url}/reset-password"
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
    s.chat_stream_chunk_words = max(1, _get_int("CHAT_STREAM_CHUNK_WORDS", 40))
    s.chat_stream_delay_seconds = max(0.0, _get_float("CHAT_STREAM_DELAY_SECONDS", 0.0))
    s.generation_timeout_seconds = _get_int("GENERATION_TIMEOUT_SECONDS", 300)

    # Web cache
    s.web_cache_ttl_seconds = _get_int("WEB_CACHE_TTL_SECONDS", 900)  # 15 minutes default
    s.web_cache_enabled = _get_bool("WEB_CACHE_ENABLED", True)
    s.web_cache_max_rows = _get_int("WEB_CACHE_MAX_ROWS", 5000)
    s.enable_feedback = _get_bool("ENABLE_FEEDBACK", True)

    # Phase 2B Query Expansion Controls (feature-flagged)
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
    # Individual weights applied to normalized relevance signals derived from metadata
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

    # Large document controls (avoid heavy table/image extraction on massive PDFs)
    s.large_doc_page_threshold = _get_int("LARGE_DOC_PAGE_THRESHOLD", 400)
    s.skip_tables_for_large_docs = _get_bool("SKIP_TABLES_FOR_LARGE_DOCS", True)
    s.skip_images_for_large_docs = _get_bool("SKIP_IMAGES_FOR_LARGE_DOCS", True)
    s.skip_ocr_for_large_docs = _get_bool("SKIP_OCR_FOR_LARGE_DOCS", True)

    return s


def get_model_num_ctx(model_name: str | None) -> int:
    """Resolve the configured num_ctx for a given model, case-insensitive."""

    settings = get_settings()
    default = settings.default_model_num_ctx or 4096
    if not model_name:
        return default

    key = model_name.lower()
    mapping = {
        settings.embedding_model.lower(): settings.embedding_model_num_ctx,
        settings.chat_model.lower(): settings.chat_model_num_ctx,
        settings.coding_model.lower(): settings.coding_model_num_ctx,
        settings.reasoning_model.lower(): settings.reasoning_model_num_ctx,
        settings.vision_model.lower(): settings.vision_model_num_ctx,
    }

    if key in mapping:
        return mapping[key]

    base_key = key.split(":")[0]
    for name, value in mapping.items():
        if name.split(":")[0] == base_key:
            return value

    return default


def select_embedding_model(document_type: str = "", content: str = "", size_kb: int = 0) -> str:
    """
    Dynamically select the best embedding model based on document characteristics.

    Args:
        document_type: Classified document type (e.g., 'code', 'technical', 'general')
        content: Document content for keyword analysis
        size_kb: Document size in KB

    Returns:
        Model name to use for embeddings
    """
    settings = get_settings()

    # Default to configured embedding model
    selected_model = settings.embedding_model

    # Analyze content for keywords
    content_lower = content.lower()
    has_code = any(
        keyword in content_lower
        for keyword in ["function", "class", "import", "def ", "var ", "const ", "let ", "public", "private"]
    )
    has_math = any(
        keyword in content_lower for keyword in ["equation", "formula", "theorem", "proof", "calculate", "algorithm"]
    )
    has_technical = any(
        keyword in content_lower for keyword in ["api", "protocol", "network", "database", "server", "client"]
    )

    # Model selection logic
    if document_type == "code" or has_code:
        # For code documents, use a model good at code understanding
        # Since we don't have specialized code embedding models, use reasoning model for embeddings if available
        if settings.reasoning_model and "llama" in settings.reasoning_model.lower():
            selected_model = settings.reasoning_model
    elif document_type in ["mathematical", "scientific"] or has_math:
        # For math/science, use reasoning model
        if settings.reasoning_model:
            selected_model = settings.reasoning_model
    elif size_kb > 1000:  # Large documents
        # For very large documents, use model with largest context
        if settings.reasoning_model and get_model_num_ctx(settings.reasoning_model) > get_model_num_ctx(
            settings.embedding_model
        ):
            selected_model = settings.reasoning_model
    elif document_type == "technical" or has_technical:
        # Technical docs benefit from general embeddings
        pass  # Keep default

    return selected_model


if __name__ == "__main__":
    # Simple debug output
    cfg = get_settings()
    for k, v in cfg.as_dict().items():
        logger.info(f"{k}={v}")
