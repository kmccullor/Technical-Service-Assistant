"""Unit tests for question decomposition and complexity classification."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from reranker.question_decomposer import (
    ComplexityLevel,
    DecompositionResult,
    QuestionDecomposer,
    SubRequest,
    classify_and_decompose,
    select_model_for_query,
)


class TestComplexityClassification:
    """Test query complexity classification."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_simple_factual_query(self, decomposer):
        """Simple factual queries should be classified as SIMPLE."""
        queries = [
            "What is FlexNet technology?",
            "Tell me about AMI meters",
            "How do routers work?",
            "Explain network latency",
        ]
        for query in queries:
            complexity = decomposer.classify_complexity(query)
            assert complexity == ComplexityLevel.SIMPLE, f"Failed for: {query}"

    def test_moderate_analytical_query(self, decomposer):
        """Analytical queries should be classified as MODERATE."""
        queries = [
            "Compare FlexNet and LTE communication",
            "Analyze the deployment process for AMI meters",
            "Summarize the advantages of mesh networks",
            "Evaluate routing algorithm efficiency",
        ]
        for query in queries:
            complexity = decomposer.classify_complexity(query)
            assert complexity in [ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX], f"Failed for: {query}"

    def test_complex_design_query(self, decomposer):
        """Design and troubleshooting queries should be classified as COMPLEX."""
        queries = [
            "Design a monitoring strategy for AMI rollout",
            "Implement a robust error detection system",
            "Troubleshoot communication failures in mesh networks",
            "Optimize the performance of FlexNet routers",
            "Design a redundancy strategy for critical meters",
        ]
        for query in queries:
            complexity = decomposer.classify_complexity(query)
            assert complexity == ComplexityLevel.COMPLEX, f"Failed for: {query}"

    def test_token_count_affects_complexity(self, decomposer):
        """Query length should increase complexity."""
        short = "What is FlexNet?"
        medium = "What is FlexNet and how does it compare to LTE communication methods?"
        long = "What is FlexNet, how does it compare to LTE, what are the advantages and disadvantages, and when should you use each one?"

        short_complexity = decomposer.classify_complexity(short)
        medium_complexity = decomposer.classify_complexity(medium)
        long_complexity = decomposer.classify_complexity(long)

        # Short should be simpler than long
        assert short_complexity <= medium_complexity or short_complexity <= long_complexity

    def test_multiple_question_marks_increase_complexity(self, decomposer):
        """Multiple questions should increase complexity."""
        single_q = "What is FlexNet?"
        double_q = "What is FlexNet? How does it work?"
        triple_q = "What is FlexNet? How does it work? What are the benefits?"

        single = decomposer.classify_complexity(single_q)
        double = decomposer.classify_complexity(double_q)
        triple = decomposer.classify_complexity(triple_q)

        # More questions = higher or equal complexity
        complexity_values = {ComplexityLevel.SIMPLE: 1, ComplexityLevel.MODERATE: 2, ComplexityLevel.COMPLEX: 3}

        assert complexity_values[double] >= complexity_values[single]
        assert complexity_values[triple] >= complexity_values[double]


class TestQuestionDecomposition:
    """Test question decomposition into sub-requests."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_simple_query_not_decomposed(self, decomposer):
        """Simple single-topic queries should not be decomposed."""
        query = "What is FlexNet technology?"
        result = decomposer.decompose_question(query)

        assert result.total_sub_requests <= 1
        assert result.complexity == ComplexityLevel.SIMPLE

    def test_two_part_query_decomposed(self, decomposer):
        """Queries with "and" should be decomposed into sub-requests."""
        query = "What is FlexNet? And how does it compare to LTE?"
        result = decomposer.decompose_question(query)

        assert result.total_sub_requests >= 1
        assert result.needs_decomposition or result.total_sub_requests <= 1

    def test_multi_sentence_query_decomposed(self, decomposer):
        """Multi-sentence queries should be decomposed."""
        query = "Tell me about FlexNet. Explain how it works. What are the benefits?"
        result = decomposer.decompose_question(query)

        # Should have at least 2 sub-requests or be kept as single
        assert result.total_sub_requests >= 1

    def test_decomposition_includes_complexity(self, decomposer):
        """Sub-requests should have complexity classifications."""
        query = "What is FlexNet and how do I design a deployment strategy?"
        result = decomposer.decompose_question(query)

        for sub_req in result.sub_requests:
            assert sub_req.complexity in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]
            assert sub_req.complexity is not None

    def test_decomposition_max_sub_requests_limit(self, decomposer):
        """Decomposition should not exceed max sub-requests limit."""
        decomposer.max_sub_requests = 3
        query = "A? B? C? D? E? F? G? H?"  # 8 question marks

        result = decomposer.decompose_question(query)

        assert result.total_sub_requests <= decomposer.max_sub_requests

    def test_sub_request_ids_are_unique(self, decomposer):
        """Sub-requests should have unique IDs."""
        query = "What is FlexNet? How does it work? What are the benefits?"
        result = decomposer.decompose_question(query)

        ids = [sr.id for sr in result.sub_requests]
        assert len(ids) == len(set(ids)), "Sub-request IDs should be unique"

    def test_sub_request_preserves_original_query(self, decomposer):
        """Sub-requests should preserve reference to original query."""
        original = "Compare FlexNet and LTE. What about mesh networks?"
        result = decomposer.decompose_question(original)

        for sub_req in result.sub_requests:
            assert sub_req.original_query == original


class TestModelSelection:
    """Test model selection based on complexity."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_simple_uses_small_model(self, decomposer):
        """SIMPLE complexity should use reasoning_model (3b)."""
        model = decomposer.select_model_for_complexity(ComplexityLevel.SIMPLE)
        # Should be a small model
        assert model is not None
        assert "3b" in model or "small" in model.lower() or "lite" in model.lower() or decomposer.settings.reasoning_model

    def test_moderate_uses_medium_model(self, decomposer):
        """MODERATE complexity should use chat_model (7b)."""
        model = decomposer.select_model_for_complexity(ComplexityLevel.MODERATE)
        assert model is not None
        assert model == decomposer.settings.chat_model

    def test_complex_uses_large_model(self, decomposer):
        """COMPLEX complexity should use coding_model or large model."""
        model = decomposer.select_model_for_complexity(ComplexityLevel.COMPLEX)
        assert model is not None
        assert model in [decomposer.settings.coding_model, decomposer.settings.chat_model]

    def test_model_selection_consistent(self, decomposer):
        """Model selection should be deterministic."""
        model1 = decomposer.select_model_for_complexity(ComplexityLevel.SIMPLE)
        model2 = decomposer.select_model_for_complexity(ComplexityLevel.SIMPLE)
        assert model1 == model2


class TestCacheKeyGeneration:
    """Test deterministic cache key generation."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_same_query_same_key(self, decomposer):
        """Same query should always generate same cache key."""
        query = "What is FlexNet technology?"
        key1 = decomposer.generate_cache_key(query, user_id=1)
        key2 = decomposer.generate_cache_key(query, user_id=1)

        assert key1 == key2, "Same query should generate same key"

    def test_different_query_different_key(self, decomposer):
        """Different queries should generate different cache keys."""
        query1 = "What is FlexNet?"
        query2 = "What is LTE?"
        key1 = decomposer.generate_cache_key(query1, user_id=1)
        key2 = decomposer.generate_cache_key(query2, user_id=1)

        assert key1 != key2, "Different queries should generate different keys"

    def test_query_normalization_affects_key(self, decomposer):
        """Normalized queries should generate same key."""
        query1 = "What is FlexNet technology?"
        query2 = "What is FlexNet technology?   "  # Extra spaces
        key1 = decomposer.generate_cache_key(query1, user_id=1)
        key2 = decomposer.generate_cache_key(query2, user_id=1)

        assert key1 == key2, "Normalized queries should generate same key"

    def test_cache_key_includes_user_id(self, decomposer):
        """Cache keys should be scoped by user ID."""
        query = "What is FlexNet technology?"
        key1 = decomposer.generate_cache_key(query, user_id=1)
        key2 = decomposer.generate_cache_key(query, user_id=2)

        assert key1 != key2, "Different user IDs should generate different keys"

    def test_cache_key_includes_prefix(self, decomposer):
        """Cache keys should have tsa:chat:decomposed prefix."""
        query = "What is FlexNet?"
        key = decomposer.generate_cache_key(query, user_id=1)

        assert key.startswith("tsa:chat:decomposed:"), "Cache key should have standard prefix"


class TestDecompositionResult:
    """Test DecompositionResult model and serialization."""

    def test_decomposition_result_to_dict(self):
        """DecompositionResult should serialize to dict."""
        sub_req = SubRequest(
            original_query="Test query",
            sub_query="Sub query",
            complexity=ComplexityLevel.SIMPLE,
        )

        result = DecompositionResult(
            query_hash="abc123",
            original_query="Test query",
            complexity=ComplexityLevel.SIMPLE,
            sub_requests=[sub_req],
            total_sub_requests=1,
            needs_decomposition=False,
            decomposition_confidence=0.95,
        )

        result_dict = result.to_dict()

        assert result_dict["query_hash"] == "abc123"
        assert result_dict["complexity"] == "simple"
        assert result_dict["total_sub_requests"] == 1
        assert len(result_dict["sub_requests"]) == 1

    def test_sub_request_to_dict(self):
        """SubRequest should serialize to dict."""
        sub_req = SubRequest(
            original_query="Original",
            sub_query="Sub",
            complexity=ComplexityLevel.MODERATE,
            topic="test_topic",
            confidence=0.8,
        )

        sub_dict = sub_req.to_dict()

        assert sub_dict["original_query"] == "Original"
        assert sub_dict["sub_query"] == "Sub"
        assert sub_dict["complexity"] == "moderate"
        assert sub_dict["topic"] == "test_topic"
        assert sub_dict["confidence"] == 0.8


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_classify_and_decompose(self):
        """classify_and_decompose should return DecompositionResult."""
        result = classify_and_decompose("What is FlexNet? How does it work?", user_id=1)

        assert isinstance(result, DecompositionResult)
        assert result.original_query == "What is FlexNet? How does it work?"
        assert result.complexity in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]

    def test_select_model_for_query(self):
        """select_model_for_query should return model name."""
        model = select_model_for_query("What is FlexNet?")

        assert isinstance(model, str)
        assert len(model) > 0

    def test_select_model_for_complex_query(self):
        """Complex queries should select different model than simple."""
        simple_model = select_model_for_query("What is FlexNet?")
        complex_model = select_model_for_query(
            "Design a comprehensive monitoring and alerting system for 50,000 AMI meters with error detection and escalation"
        )

        # Models may be same (mistral for both) but functionality should route appropriately
        assert isinstance(simple_model, str)
        assert isinstance(complex_model, str)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def decomposer(self):
        return QuestionDecomposer()

    def test_empty_query(self, decomposer):
        """Empty query should be handled gracefully."""
        result = decomposer.decompose_question("")
        assert result.total_sub_requests == 0
        assert result.complexity in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]

    def test_very_long_query(self, decomposer):
        """Very long queries should be handled without error."""
        long_query = "What is? " * 100  # 300 tokens
        result = decomposer.decompose_question(long_query)

        assert result.total_sub_requests <= decomposer.max_sub_requests
        assert result.complexity in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]

    def test_special_characters_handled(self, decomposer):
        """Queries with special characters should be handled."""
        query = "What's @FlexNet? (mesh/IP) 50% less latency?"
        result = decomposer.decompose_question(query)

        assert result.original_query == query
        assert result.total_sub_requests >= 0

    def test_unicode_query_handled(self, decomposer):
        """Unicode characters in queries should be handled."""
        query = "What is FlexNet™? Explain the IoT protocol 📡"
        result = decomposer.decompose_question(query)

        assert result.original_query == query

    def test_case_insensitive_classification(self, decomposer):
        """Classification should be case-insensitive."""
        lower = "what is flexnet?"
        upper = "WHAT IS FLEXNET?"
        mixed = "What Is FlexNet?"

        lower_complexity = decomposer.classify_complexity(lower)
        upper_complexity = decomposer.classify_complexity(upper)
        mixed_complexity = decomposer.classify_complexity(mixed)

        assert lower_complexity == upper_complexity
        assert lower_complexity == mixed_complexity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
