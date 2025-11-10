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
