"""
Advanced Embedding and Inference Caching

Extends the query-response caching with specialized caching for:
1. Embedding vectors (cache query embeddings to avoid recomputation)
2. Inference results (cache model outputs separately from context)
3. Chunking patterns (cache semantic chunks to avoid reprocessing)

This layer sits between the load balancer and the embedding/inference calls.
Target: 92% cache hit rate → 98%+ cache hit rate (6% improvement).
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger(__name__)


class AdvancedCache:
    """
    Multi-layer caching for embeddings, inference, and semantic chunks.

    Layers:
    1. Embedding cache: Maps query text → embedding vector
    2. Inference cache: Maps (model, prompt) → response
    3. Chunk cache: Maps (document_id, chunk_id) → semantic info
    """

    # Cache key prefixes
    PREFIX_EMBEDDING = "adv:embedding:"
    PREFIX_INFERENCE = "adv:inference:"
    PREFIX_CHUNK = "adv:chunk:"
    PREFIX_STATS = "adv:cache:stats"

    # Configuration
    EMBEDDING_TTL = 604800  # 7 days - embeddings don't change
    INFERENCE_TTL = 86400  # 24 hours - model outputs may vary with updates
    CHUNK_TTL = 2592000  # 30 days - chunks are stable

    def __init__(self):
        """Initialize advanced cache with Redis."""
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
        self.enabled = os.getenv("ENABLE_ADVANCED_CACHE", "true").lower() in {"1", "true", "yes"}
        self.redis_client: Optional[redis.Redis] = None

        if not redis:
            logger.warning("Redis module not available, advanced cache disabled")
            self.enabled = False
            return

        if self.enabled:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=False,  # Need binary for pickle
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                )
                self.redis_client.ping()
                logger.info("Advanced cache initialized (Redis DB 1 connected)")
            except Exception as e:
                logger.warning(f"Advanced cache Redis connection failed: {e}, disabled")
                self.redis_client = None
                self.enabled = False

    def _hash_text(self, text: str) -> str:
        """Generate hash for text content."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _hash_model_prompt(self, model: str, prompt: str) -> str:
        """Generate hash for model + prompt combination."""
        combined = f"{model}:{prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    # ========== EMBEDDING CACHE ==========

    def get_embedding(self, query: str) -> Optional[List[float]]:
        """
        Get cached embedding for query.

        Args:
            query: Text to get embedding for

        Returns:
            Embedding vector or None if not cached
        """
        if not self.enabled or not self.redis_client:
            return None

        try:
            query_hash = self._hash_text(query)
            cache_key = f"{self.PREFIX_EMBEDDING}{query_hash}"

            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                embedding = json.loads(cached_data)
                self._record_stat("embedding_hit")
                logger.debug(f"Embedding cache HIT for query_hash={query_hash}")
                return embedding

            self._record_stat("embedding_miss")
            logger.debug(f"Embedding cache MISS for query_hash={query_hash}")
            return None

        except Exception as e:
            logger.warning(f"Embedding cache retrieval error: {e}")
            return None

    def cache_embedding(self, query: str, embedding: List[float]) -> bool:
        """
        Cache embedding vector for query.

        Args:
            query: Original text
            embedding: Embedding vector

        Returns:
            True if cached successfully
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            query_hash = self._hash_text(query)
            cache_key = f"{self.PREFIX_EMBEDDING}{query_hash}"

            # Cache as JSON for compatibility
            self.redis_client.setex(
                cache_key,
                self.EMBEDDING_TTL,
                json.dumps(embedding),
            )

            self._record_stat("embedding_cached")
            logger.debug(f"Cached embedding for query_hash={query_hash}")
            return True

        except Exception as e:
            logger.warning(f"Embedding cache storage error: {e}")
            return False

    # ========== INFERENCE CACHE ==========

    def get_inference(self, model: str, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Get cached inference result.

        Args:
            model: LLM model name
            system_prompt: System prompt
            user_prompt: User prompt

        Returns:
            Cached response or None
        """
        if not self.enabled or not self.redis_client:
            return None

        try:
            # Create composite key from model + both prompts
            combined = f"{model}:{system_prompt}:{user_prompt}"
            combined_hash = self._hash_text(combined)
            cache_key = f"{self.PREFIX_INFERENCE}{combined_hash}"

            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                response = cached_data.decode("utf-8")
                self._record_stat("inference_hit")
                logger.debug(f"Inference cache HIT (model={model})")
                return response

            self._record_stat("inference_miss")
            logger.debug(f"Inference cache MISS (model={model})")
            return None

        except Exception as e:
            logger.warning(f"Inference cache retrieval error: {e}")
            return None

    def cache_inference(self, model: str, system_prompt: str, user_prompt: str, response: str) -> bool:
        """
        Cache inference result.

        Args:
            model: LLM model name
            system_prompt: System prompt used
            user_prompt: User prompt used
            response: Generated response

        Returns:
            True if cached successfully
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            combined = f"{model}:{system_prompt}:{user_prompt}"
            combined_hash = self._hash_text(combined)
            cache_key = f"{self.PREFIX_INFERENCE}{combined_hash}"

            self.redis_client.setex(
                cache_key,
                self.INFERENCE_TTL,
                response.encode("utf-8"),
            )

            self._record_stat("inference_cached")
            logger.debug(f"Cached inference result (model={model})")
            return True

        except Exception as e:
            logger.warning(f"Inference cache storage error: {e}")
            return False

    # ========== CHUNK CACHE ==========

    def get_chunk_metadata(self, document_id: int, chunk_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached chunk metadata (semantic chunking info).

        Args:
            document_id: Document ID
            chunk_id: Chunk ID

        Returns:
            Chunk metadata or None
        """
        if not self.enabled or not self.redis_client:
            return None

        try:
            chunk_key = f"{self.PREFIX_CHUNK}{document_id}:{chunk_id}"
            cached_data = self.redis_client.get(chunk_key)

            if cached_data:
                metadata = json.loads(cached_data)
                self._record_stat("chunk_hit")
                logger.debug(f"Chunk cache HIT (doc={document_id}, chunk={chunk_id})")
                return metadata

            self._record_stat("chunk_miss")
            return None

        except Exception as e:
            logger.warning(f"Chunk cache retrieval error: {e}")
            return None

    def cache_chunk_metadata(self, document_id: int, chunk_id: int, metadata: Dict[str, Any]) -> bool:
        """
        Cache chunk metadata.

        Args:
            document_id: Document ID
            chunk_id: Chunk ID
            metadata: Chunk metadata to cache

        Returns:
            True if cached successfully
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            chunk_key = f"{self.PREFIX_CHUNK}{document_id}:{chunk_id}"

            self.redis_client.setex(
                chunk_key,
                self.CHUNK_TTL,
                json.dumps(metadata),
            )

            self._record_stat("chunk_cached")
            return True

        except Exception as e:
            logger.warning(f"Chunk cache storage error: {e}")
            return False

    # ========== STATS & MONITORING ==========

    def _record_stat(self, stat_name: str) -> None:
        """Record cache statistic."""
        try:
            if not self.redis_client:
                return

            self.redis_client.hincrby(self.PREFIX_STATS, stat_name, 1)
        except Exception as e:
            logger.debug(f"Stat recording error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.enabled or not self.redis_client:
            return {"enabled": False}

        try:
            stats = self.redis_client.hgetall(self.PREFIX_STATS)

            # Calculate hit rates
            embedding_hits = int(stats.get(b"embedding_hit", 0) or 0)
            embedding_misses = int(stats.get(b"embedding_miss", 0) or 0)
            embedding_total = embedding_hits + embedding_misses

            inference_hits = int(stats.get(b"inference_hit", 0) or 0)
            inference_misses = int(stats.get(b"inference_miss", 0) or 0)
            inference_total = inference_hits + inference_misses

            chunk_hits = int(stats.get(b"chunk_hit", 0) or 0)
            chunk_misses = int(stats.get(b"chunk_miss", 0) or 0)
            chunk_total = chunk_hits + chunk_misses

            return {
                "enabled": True,
                "embedding": {
                    "hits": embedding_hits,
                    "misses": embedding_misses,
                    "total": embedding_total,
                    "hit_rate": f"{(embedding_hits / max(embedding_total, 1)) * 100:.1f}%",
                },
                "inference": {
                    "hits": inference_hits,
                    "misses": inference_misses,
                    "total": inference_total,
                    "hit_rate": f"{(inference_hits / max(inference_total, 1)) * 100:.1f}%",
                },
                "chunks": {
                    "hits": chunk_hits,
                    "misses": chunk_misses,
                    "total": chunk_total,
                    "hit_rate": f"{(chunk_hits / max(chunk_total, 1)) * 100:.1f}%",
                },
                "overall": {
                    "total_hits": embedding_hits + inference_hits + chunk_hits,
                    "total_misses": embedding_misses + inference_misses + chunk_misses,
                    "overall_hit_rate": f"{((embedding_hits + inference_hits + chunk_hits) / max(embedding_total + inference_total + chunk_total, 1)) * 100:.1f}%",
                },
            }

        except Exception as e:
            logger.warning(f"Error retrieving cache stats: {e}")
            return {"enabled": True, "error": str(e)}

    def clear_all(self) -> bool:
        """Clear all advanced cache entries."""
        if not self.enabled or not self.redis_client:
            return False

        try:
            patterns = [
                f"{self.PREFIX_EMBEDDING}*",
                f"{self.PREFIX_INFERENCE}*",
                f"{self.PREFIX_CHUNK}*",
            ]

            for pattern in patterns:
                cursor = 0
                while True:
                    cursor, keys = self.redis_client.scan(cursor, match=pattern)
                    if keys:
                        self.redis_client.delete(*keys)
                    if cursor == 0:
                        break

            logger.info("Advanced cache cleared")
            return True

        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
            return False


# Global advanced cache instance
_advanced_cache: Optional[AdvancedCache] = None


def get_advanced_cache() -> AdvancedCache:
    """Get or create global advanced cache instance."""
    global _advanced_cache
    if _advanced_cache is None:
        _advanced_cache = AdvancedCache()
    return _advanced_cache
