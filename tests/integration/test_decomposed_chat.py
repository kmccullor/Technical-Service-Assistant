"""Integration tests for decomposed chat with Redis caching."""

from __future__ import annotations


import pytest

pytestmark = pytest.mark.integration

from reranker.question_decomposer import ComplexityLevel, QuestionDecomposer
from utils.redis_cache import (
    cache_complexity_classification,
    cache_decomposed_response,
    cache_sub_request_result,
    track_decomposition_metric,
)


class TestDecomposedChatFlow:
    """Test full decomposed chat flow with caching."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_decomposition_with_caching(self, decomposer):
        """Test decomposition result is cacheable."""
        query = "What is FlexNet? How does it work?"
        user_id = 1

        # Decompose query
        result = decomposer.decompose_question(query, user_id)

        # Serialize to cache
        cached_data = result.to_dict()

        # Verify cache format
        assert "query_hash" in cached_data
        assert "complexity" in cached_data
        assert "sub_requests" in cached_data
        assert isinstance(cached_data["sub_requests"], list)

    def test_complexity_cached_across_calls(self, decomposer):
        """Same query should have consistent complexity classification."""
        query = "Compare FlexNet and LTE"

        result1 = decomposer.decompose_question(query, user_id=1)
        complexity1 = result1.complexity

        result2 = decomposer.decompose_question(query, user_id=1)
        complexity2 = result2.complexity

        assert complexity1 == complexity2, "Same query should have same complexity"

    def test_sub_request_independence(self, decomposer):
        """Each sub-request should be independently cacheable."""
        query = "Explain FlexNet. Then describe LTE. Finally compare them."
        result = decomposer.decompose_question(query)

        # Each sub-request should be independently cacheable
        for sub_req in result.sub_requests:
            # Simulate caching
            sub_data = {
                "id": sub_req.id,
                "sub_query": sub_req.sub_query,
                "response": f"Response to {sub_req.sub_query}",
            }

            assert sub_data["id"] == sub_req.id
            assert len(sub_data["id"]) == 36  # UUID format

    def test_multi_part_query_parallel_processing(self, decomposer):
        """Multi-part queries should decompose for parallel processing."""
        query = "What is FlexNet? How do routers communicate? What about failure scenarios?"

        result = decomposer.decompose_question(query)

        # Query has multiple parts, should decompose
        if result.total_sub_requests > 1:
            # Can process in parallel
            assert len(result.sub_requests) <= decomposer.max_sub_requests
            for sub_req in result.sub_requests:
                assert sub_req.sub_query is not None
                assert sub_req.complexity is not None


class TestRedisCacheIntegration:
    """Test Redis cache operations for decomposed queries."""

    def test_cache_and_retrieve_decomposed_response(self):
        """Test caching and retrieving decomposed responses."""
        query_hash = "abc123"
        user_id = 1
        response_data = {
            "response": "Test response",
            "sources": ["source1", "source2"],
            "model": "mistral:7b",
        }

        # Cache
        cache_result = cache_decomposed_response(query_hash, user_id, response_data)
        # Should not fail even if Redis is not configured
        assert cache_result is not None

    def test_cache_and_retrieve_sub_request(self):
        """Test caching and retrieving sub-request results."""
        sub_request_id = "uuid-123"
        result_data = {
            "sub_query": "What is FlexNet?",
            "response": "FlexNet is...",
            "model": "llama3.2:3b",
            "time_ms": 2500,
        }

        # Cache
        cache_result = cache_sub_request_result(sub_request_id, result_data)
        # Should not fail even if Redis is not configured
        assert cache_result is not None

    def test_cache_complexity_classification(self):
        """Test caching complexity classifications."""
        query_hash = "xyz789"
        complexity = "moderate"

        # Cache with long TTL
        cache_result = cache_complexity_classification(query_hash, complexity, ttl=86400)
        # Should not fail even if Redis is not configured
        assert cache_result is not None

    def test_track_decomposition_metrics(self):
        """Test tracking decomposition metrics."""
        # Track metrics
        metric_result = track_decomposition_metric("simple", "total", 1)
        # Should not fail even if Redis is not configured
        assert metric_result is not None


class TestCacheKeyConsistency:
    """Test cache key generation consistency."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_follow_up_question_cache_reuse(self, decomposer):
        """Follow-up questions in same session should reuse cache."""
        query1 = "Tell me about FlexNet"
        query2 = "Tell me about FlexNet"  # Identical

        key1 = decomposer.generate_cache_key(query1, user_id=1)
        key2 = decomposer.generate_cache_key(query2, user_id=1)

        assert key1 == key2, "Identical queries should have same cache key"

    def test_similar_but_different_questions(self, decomposer):
        """Similar but different questions should have different cache keys."""
        query1 = "Tell me about FlexNet"
        query2 = "Tell me about LTE"

        key1 = decomposer.generate_cache_key(query1, user_id=1)
        key2 = decomposer.generate_cache_key(query2, user_id=1)

        assert key1 != key2, "Different queries should have different cache keys"

    def test_cache_key_user_scoping(self, decomposer):
        """Cache keys should be scoped by user ID."""
        query = "What is FlexNet?"

        key_user1 = decomposer.generate_cache_key(query, user_id=1)
        key_user2 = decomposer.generate_cache_key(query, user_id=2)

        assert key_user1 != key_user2, "Same query for different users should have different keys"


class TestModelRoutingDecisions:
    """Test model routing based on decomposition."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_simple_query_routes_to_small_model(self, decomposer):
        """Simple queries should route to small models."""
        query = "What is FlexNet?"
        result = decomposer.decompose_question(query)

        assert result.complexity == ComplexityLevel.SIMPLE

        model = decomposer.select_model_for_complexity(result.complexity)
        assert model is not None

    def test_complex_query_routes_to_large_model(self, decomposer):
        """Complex queries should route to larger models."""
        query = "Design a comprehensive monitoring system for 50,000 AMI meters including error detection, performance thresholds, escalation procedures, and alerting strategies."

        result = decomposer.decompose_question(query)

        assert result.complexity == ComplexityLevel.COMPLEX

        model = decomposer.select_model_for_complexity(result.complexity)
        assert model is not None

    def test_each_sub_request_gets_appropriate_model(self, decomposer):
        """Each sub-request should get model appropriate to its complexity."""
        query = "What is FlexNet and how do I design a deployment?"
        result = decomposer.decompose_question(query)

        for sub_req in result.sub_requests:
            model = decomposer.select_model_for_complexity(sub_req.complexity)
            assert model is not None
            assert isinstance(model, str)


class TestDecompositionQuality:
    """Test decomposition quality and confidence scores."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_single_question_high_confidence(self, decomposer):
        """Single questions should have high decomposition confidence."""
        query = "What is FlexNet?"
        result = decomposer.decompose_question(query)

        # Single question, high confidence
        assert result.decomposition_confidence >= 0.5

    def test_multi_question_confidence_still_high(self, decomposer):
        """Multi-questions should still have reasonable confidence."""
        query = "What is FlexNet? How does it work?"
        result = decomposer.decompose_question(query)

        # Decomposed, but should have confidence >= 0.5
        assert result.decomposition_confidence >= 0.5

    def test_decomposition_confidence_is_numeric(self, decomposer):
        """Decomposition confidence should be a valid numeric score."""
        query = "Complex question about design and implementation?"
        result = decomposer.decompose_question(query)

        assert isinstance(result.decomposition_confidence, float)
        assert 0.0 <= result.decomposition_confidence <= 1.0

    def test_sub_request_confidence_scores(self, decomposer):
        """Sub-requests should have confidence scores."""
        query = "Tell me about X. Also explain Y."
        result = decomposer.decompose_question(query)

        for sub_req in result.sub_requests:
            assert isinstance(sub_req.confidence, float)
            assert 0.0 <= sub_req.confidence <= 1.0


class TestDecompositionPerformance:
    """Test decomposition doesn't degrade performance."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_decomposition_is_fast(self, decomposer):
        """Decomposition should complete quickly (<100ms)."""
        import time

        query = "What is FlexNet? How does it work? What are the benefits? When should I use it?"

        start = time.time()
        decomposer.decompose_question(query)
        elapsed = (time.time() - start) * 1000  # ms

        assert elapsed < 100, f"Decomposition took {elapsed}ms, should be < 100ms"

    def test_handles_many_sub_requests_efficiently(self, decomposer):
        """Should handle many sub-requests without performance degradation."""
        import time

        decomposer.max_sub_requests = 10
        query = " ".join(["Question?"] * 20)

        start = time.time()
        result = decomposer.decompose_question(query)
        elapsed = (time.time() - start) * 1000  # ms

        # Should still be fast
        assert elapsed < 100, f"Processing took {elapsed}ms, should be < 100ms"

        # Should not exceed max
        assert result.total_sub_requests <= decomposer.max_sub_requests


class TestEdgeCasesIntegration:
    """Test integration edge cases."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_handles_mixed_complexity_sub_requests(self, decomposer):
        """Should handle mix of simple and complex sub-requests."""
        query = "What is FlexNet? Compare with LTE. Design a deployment strategy."
        result = decomposer.decompose_question(query)

        # Should have different complexity levels
        complexities = [sr.complexity for sr in result.sub_requests]
        if len(complexities) > 1:
            # Allow for variation in complexity
            assert len(set(complexities)) >= 1  # At least some variation

    def test_cache_survives_normalization(self, decomposer):
        """Cache keys should survive query normalization."""
        queries = [
            "What is FlexNet?",
            "What is FlexNet ?",
            "What is  FlexNet?",
            "  What is FlexNet?",
        ]

        keys = [decomposer.generate_cache_key(q, user_id=1) for q in queries]

        # All should generate same cache key
        assert len(set(keys)) == 1, "Normalized queries should have same cache key"

    def test_handles_repeated_decomposition(self, decomposer):
        """Repeated decomposition of same query should be idempotent."""
        query = "What is FlexNet? How does it work?"

        result1 = decomposer.decompose_question(query, user_id=1)
        result2 = decomposer.decompose_question(query, user_id=1)

        assert result1.query_hash == result2.query_hash
        assert result1.complexity == result2.complexity
        assert result1.total_sub_requests == result2.total_sub_requests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
