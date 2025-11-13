"""Lightweight Redis helpers for instrumentation and cache metrics."""

from __future__ import annotations

import logging
from typing import Optional

try:
    import redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - optional dependency guard
    redis = None  # type: ignore
    RedisError = Exception  # type: ignore

from config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional["redis.Redis"] = None

# In-memory fallback for development when Redis is not available.
import threading
import time

_mem_store: dict = {}
_mem_ttl: dict = {}
_mem_lock = threading.Lock()


def _mem_set(key: str, value: str, ttl: int = 0) -> None:
    with _mem_lock:
        _mem_store[key] = value
        _mem_ttl[key] = time.time() + ttl if ttl and ttl > 0 else None


def _mem_get(key: str) -> Optional[str]:
    with _mem_lock:
        exp = _mem_ttl.get(key)
        if exp is not None and exp < time.time():
            # expired
            _mem_store.pop(key, None)
            _mem_ttl.pop(key, None)
            return None
        return _mem_store.get(key)


def get_redis_client() -> Optional["redis.Redis"]:
    """Return a cached Redis client if configuration is present."""

    global _redis_client
    if _redis_client is not None:
        return _redis_client

    settings = get_settings()
    redis_url = getattr(settings, "redis_url", None)
    if not redis_url or redis is None:
        if redis is None:
            logger.debug("redis library not installed; skipping Redis instrumentation")
        return None

    try:
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("Connected to Redis cache at %s", redis_url)
    except RedisError as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to connect to Redis (%s): %s", redis_url, exc)
        _redis_client = None
    return _redis_client


def _with_client(func):
    def wrapper(*args, **kwargs):
        client = get_redis_client()
        if not client:
            return False
        try:
            return func(client, *args, **kwargs)
        except RedisError as exc:  # pragma: no cover - network dependent
            logger.warning("Redis operation failed: %s", exc)
            return False

    return wrapper


@_with_client
def increment_counter(client, key: str, amount: int = 1) -> bool:
    client.incrby(key, amount)
    return True


@_with_client
def hincr_field(client, key: str, field: str, amount: int = 1) -> bool:
    client.hincrby(key, field, amount)
    return True


def track_model_usage(model: str) -> bool:
    return hincr_field("tsa:chat:model_usage", model)


def track_question_type(question_type: str) -> bool:
    return hincr_field("tsa:chat:question_type", question_type)


def track_instance_usage(instance_url: str) -> bool:
    instance = instance_url.replace("http://", "").replace("https://", "")
    return hincr_field("tsa:chat:instance_usage", instance)


# Short-term memory (decomposed requests) caching functions


def cache_decomposed_response(query_hash: str, user_id: int, response_data: dict, ttl: int = 3600) -> bool:
    """Cache decomposed response in Redis short-term memory.

    Args:
        query_hash: Hash of normalized query (from QuestionDecomposer)
        user_id: User ID for scoping
        response_data: Response metadata and result
        ttl: Time-to-live in seconds (default 1 hour)

    Returns:
        True if cached successfully, False otherwise
    """
    client = get_redis_client()
    key = f"tsa:chat:response:{query_hash}:{user_id}"
    try:
        import json

        payload = json.dumps(response_data)
        if client:
            client.setex(key, ttl, payload)
        else:
            _mem_set(key, payload, ttl)

        logger.debug(f"Cached decomposed response: {key} (TTL: {ttl}s)")
        return True
    except RedisError as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to cache decomposed response: %s", exc)
        return False


def get_decomposed_response(query_hash: str, user_id: int) -> Optional[dict]:
    """Retrieve cached decomposed response from Redis.

    Args:
        query_hash: Hash of normalized query
        user_id: User ID for scoping

    Returns:
        Cached response dict if found, None otherwise
    """
    client = get_redis_client()
    try:
        import json

        key = f"tsa:chat:response:{query_hash}:{user_id}"
        if client:
            value = client.get(key)
        else:
            value = _mem_get(key)

        if value:
            logger.debug(f"Cache hit for decomposed response: {key}")
            try:
                increment_counter("tsa:chat:cache_hits_decomp")
            except Exception:
                pass
            return json.loads(value)
        return None
    except RedisError as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to retrieve decomposed response: %s", exc)
        return None


def cache_sub_request_result(sub_request_id: str, result_data: dict, ttl: int = 3600) -> bool:
    """Cache individual sub-request result in Redis.

    Args:
        sub_request_id: UUID of sub-request
        result_data: Sub-request response (model, response, sources, etc.)
        ttl: Time-to-live in seconds (default 1 hour)

    Returns:
        True if cached successfully, False otherwise
    """
    client = get_redis_client()
    key = f"tsa:chat:subresp:{sub_request_id}"
    try:
        import json

        payload = json.dumps(result_data)
        if client:
            client.setex(key, ttl, payload)
        else:
            _mem_set(key, payload, ttl)

        logger.debug(f"Cached sub-request result: {key} (TTL: {ttl}s)")
        try:
            increment_counter("tsa:chat:sub_requests_cached")
        except Exception:
            pass
        return True
    except RedisError as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to cache sub-request result: %s", exc)
        return False


def get_sub_request_result(sub_request_id: str) -> Optional[dict]:
    """Retrieve cached sub-request result from Redis.

    Args:
        sub_request_id: UUID of sub-request

    Returns:
        Cached result dict if found, None otherwise
    """
    client = get_redis_client()
    try:
        import json

        key = f"tsa:chat:subresp:{sub_request_id}"
        if client:
            value = client.get(key)
        else:
            value = _mem_get(key)

        if value:
            logger.debug(f"Cache hit for sub-request result: {key}")
            try:
                increment_counter("tsa:chat:cache_hits_subreq")
            except Exception:
                pass
            return json.loads(value)
        return None
    except RedisError as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to retrieve sub-request result: %s", exc)
        return None


def cache_complexity_classification(query_hash: str, complexity: str, ttl: int = 86400) -> bool:
    """Cache complexity classification for query (long-lived cache).

    Args:
        query_hash: Hash of normalized query
        complexity: ComplexityLevel string (simple/moderate/complex)
        ttl: Time-to-live in seconds (default 24 hours)

    Returns:
        True if cached successfully, False otherwise
    """
    client = get_redis_client()
    key = f"tsa:chat:complexity:{query_hash}"
    try:
        if client:
            client.setex(key, ttl, complexity)
        else:
            _mem_set(key, complexity, ttl)
        logger.debug(f"Cached complexity classification: {key} = {complexity} (TTL: {ttl}s)")
        return True
    except RedisError as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to cache complexity classification: %s", exc)
        return False


def get_complexity_classification(query_hash: str) -> Optional[str]:
    """Retrieve cached complexity classification from Redis.

    Args:
        query_hash: Hash of normalized query

    Returns:
        Complexity string (simple/moderate/complex) if found, None otherwise
    """
    client = get_redis_client()
    try:
        key = f"tsa:chat:complexity:{query_hash}"
        if client:
            value = client.get(key)
        else:
            value = _mem_get(key)
        if value:
            logger.debug(f"Cache hit for complexity classification: {key}")
            return value
        return None
    except RedisError as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to retrieve complexity classification: %s", exc)
        return None


def track_decomposition_metric(complexity_level: str, metric_name: str, value: int = 1) -> bool:
    """Track decomposition metrics in Redis.

    Args:
        complexity_level: Complexity level (simple/moderate/complex)
        metric_name: Metric name (e.g., 'decomposition_total', 'cache_hits')
        value: Value to increment

    Returns:
        True if tracked successfully, False otherwise
    """
    return hincr_field(f"tsa:chat:decomposition_metrics", f"{complexity_level}:{metric_name}", value)


def get_decomposition_stats() -> dict:
    """Get decomposition statistics from Redis.

    Returns:
        Dict of decomposition metrics by complexity level
    """
    client = get_redis_client()
    if not client:
        return {}

    try:
        key = "tsa:chat:decomposition_metrics"
        stats = client.hgetall(key)
        return stats or {}
    except RedisError as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to retrieve decomposition stats: %s", exc)
        return {}
