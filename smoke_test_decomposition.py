#!/usr/bin/env python
"""Automated E2E smoke test for decomposition + rerank pipeline.

This script validates the full workflow:
1. Decompose a complex question
2. Cache decomposition metadata (using in-memory fallback if Redis unavailable)
3. Generate or cache sub-responses
4. Call rethink_pipeline to rerank and synthesize
5. Verify final output and cache state

Run without external dependencies (no redis-cli required).
"""

import sys
import os
import json

# Ensure repo is in path
sys.path.insert(0, "/home/kmccullor/Projects/Technical-Service-Assistant")

from reranker.question_decomposer import QuestionDecomposer, ComplexityLevel
from utils.redis_cache import (
    cache_decomposed_response,
    get_decomposed_response,
    cache_sub_request_result,
    get_sub_request_result,
)
from reranker.rethink_reranker import rethink_pipeline


def test_decomposition_smoke():
    """Test 1: Question decomposition and classification."""
    print("\n" + "=" * 70)
    print("TEST 1: Question Decomposition")
    print("=" * 70)

    decomposer = QuestionDecomposer()

    # Test simple query (should not decompose)
    simple_q = "What is FlexNet?"
    simple_result = decomposer.decompose_question(simple_q, user_id=1)
    print(f"✓ Simple query: '{simple_q[:40]}...'")
    print(f"  - Complexity: {simple_result.complexity}")
    print(f"  - Sub-requests: {simple_result.total_sub_requests}")
    assert simple_result.complexity == ComplexityLevel.SIMPLE
    assert simple_result.total_sub_requests == 0

    # Test complex query (should decompose)
    complex_q = "Explain FlexNet architecture, components, deployment scenarios, and limitations. Compare to LTE in terms of latency, range, and cost."
    complex_result = decomposer.decompose_question(complex_q, user_id=1)
    print(f"\n✓ Complex query: '{complex_q[:40]}...'")
    print(f"  - Complexity: {complex_result.complexity}")
    print(f"  - Sub-requests: {complex_result.total_sub_requests}")
    if complex_result.total_sub_requests > 0:
        for i, sr in enumerate(complex_result.sub_requests, 1):
            print(f"    [{i}] {sr.sub_query[:50]}... (complexity: {sr.complexity})")

    assert complex_result.complexity in {ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX}
    assert complex_result.total_sub_requests > 0, "Complex query should decompose"

    print("\n✓ PASS: Decomposition logic working correctly")
    return complex_result, decomposer


def test_caching_smoke(decomposition, decomposer):
    """Test 2: Caching and retrieval with in-memory fallback."""
    print("\n" + "=" * 70)
    print("TEST 2: Caching with In-Memory Fallback")
    print("=" * 70)

    user_id = 1
    query_hash = decomposition.query_hash

    # Cache decomposition metadata
    cached = cache_decomposed_response(query_hash, user_id, decomposition.to_dict())
    print(f"✓ Cached decomposition: {cached}")

    # Retrieve it back
    retrieved = get_decomposed_response(query_hash, user_id)
    print(f"✓ Retrieved decomposition: {retrieved is not None}")
    assert retrieved is not None
    assert retrieved["query_hash"] == query_hash
    assert len(retrieved["sub_requests"]) == decomposition.total_sub_requests

    # Cache sub-responses
    print(f"\n✓ Caching {len(decomposition.sub_requests)} sub-request responses:")
    for sr in decomposition.sub_requests:
        sub_data = {
            "id": sr.id,
            "sub_query": sr.sub_query,
            "response": f"Simulated response to: {sr.sub_query}",
            "model": decomposer.select_model_for_complexity(sr.complexity),
            "time_ms": 100,
            "confidence": 0.95,
        }
        cached_sub = cache_sub_request_result(sr.id, sub_data)
        retrieved_sub = get_sub_request_result(sr.id)
        print(f"  - {sr.sub_query[:40]}... : cached={cached_sub}, retrieved={retrieved_sub is not None}")
        assert cached_sub
        assert retrieved_sub is not None
        assert retrieved_sub["response"] == sub_data["response"]

    print("\n✓ PASS: Caching and retrieval working correctly")


def test_rerank_smoke(decomposition):
    """Test 3: Rerank and synthesize pipeline."""
    print("\n" + "=" * 70)
    print("TEST 3: Rerank and Synthesize Pipeline")
    print("=" * 70)

    user_id = 1
    original_query = decomposition.original_query

    # Call rethink_pipeline
    final_result = rethink_pipeline(decomposition.query_hash, user_id, original_query)

    print(f"✓ Rethink pipeline executed")
    print(f"  - Decomposition found: {'decomposition' in final_result}")
    print(f"  - Reranked components: {len(final_result.get('reranked_components', []))}")

    synthesized = final_result.get("synthesized", {})
    print(f"  - Synthesized text length: {len(synthesized.get('synthesized_text', ''))}")
    print(f"  - Aggregate relevance: {synthesized.get('aggregate_relevance', 0.0):.2f}")

    if synthesized.get("synthesized_text"):
        print(f"  - Sample text: {synthesized['synthesized_text'][:80]}...")

    final_relevance = final_result.get("final_relevance", 0.0)
    print(f"  - Final relevance score: {final_relevance:.2f}")

    assert "decomposition" in final_result
    assert "reranked_components" in final_result
    assert "synthesized" in final_result
    assert isinstance(synthesized, dict)
    assert synthesized.get("synthesized_text") is not None

    print("\n✓ PASS: Reranking and synthesis working correctly")


def test_fallback_synthesis():
    """Test 4: Fallback synthesis when no cached decomposition."""
    print("\n" + "=" * 70)
    print("TEST 4: Fallback Synthesis (No Cached Decomposition)")
    print("=" * 70)

    # Simulate a scenario where rethink_pipeline gets no cached decomposition
    # by calling it with a non-existent hash
    fake_hash = "nonexistent:hash:12345"
    user_id = 999

    result = rethink_pipeline(fake_hash, user_id, "Some query")
    print(f"✓ Called rethink_pipeline with non-existent cache")
    print(f"  - Result contains error: {'error' in result}")
    print(f"  - Error message: {result.get('error', 'N/A')}")

    assert "error" in result, "Should return error dict when decomposition not found"

    print("\n✓ PASS: Fallback behavior handles missing cache gracefully")


def test_model_routing():
    """Test 5: Model selection based on complexity."""
    print("\n" + "=" * 70)
    print("TEST 5: Model Routing by Complexity")
    print("=" * 70)

    decomposer = QuestionDecomposer()

    test_cases = [
        ("What is X?", ComplexityLevel.SIMPLE),
        ("Compare X and Y", ComplexityLevel.MODERATE),
        ("Design a comprehensive monitoring and alerting strategy for 50,000 AMI meter endpoints spread across multiple geographic regions. Include error detection mechanisms, performance threshold definitions for different meter types, automated escalation procedures based on severity, integration with existing SCADA systems, redundancy planning, and cost-benefit analysis of different approaches.", ComplexityLevel.MODERATE),
    ]

    for query, expected_complexity in test_cases:
        result = decomposer.decompose_question(query, user_id=1)
        model = decomposer.select_model_for_complexity(result.complexity)
        print(f"✓ Query: '{query[:40]}...'")
        print(f"  - Complexity: {result.complexity} (expected: {expected_complexity})")
        print(f"  - Selected model: {model}")
        assert result.complexity == expected_complexity, f"Expected {expected_complexity}, got {result.complexity}"
        assert model is not None

    print("\n✓ PASS: Model routing working correctly")


def main():
    """Run all smoke tests."""
    print("\n" + "=" * 70)
    print("DECOMPOSITION + RERANK PIPELINE E2E SMOKE TEST")
    print("=" * 70)
    print("Testing: decomposition, caching (with in-memory fallback), reranking, synthesis")
    print("Environment: No external Redis CLI required; uses in-memory fallback")

    try:
        # Test 1: Decomposition
        decomposition, decomposer = test_decomposition_smoke()

        # Test 2: Caching
        test_caching_smoke(decomposition, decomposer)

        # Test 3: Rerank
        test_rerank_smoke(decomposition)

        # Test 4: Fallback
        test_fallback_synthesis()

        # Test 5: Model routing
        test_model_routing()

        # Summary
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        print("✓ Decomposition: Working correctly")
        print("✓ Caching (in-memory fallback): Working correctly")
        print("✓ Rerank & synthesis: Working correctly")
        print("✓ Fallback synthesis: Working correctly")
        print("✓ Model routing: Working correctly")
        print("\nThe full decomposition + rerank pipeline is ready for deployment.")
        print("=" * 70 + "\n")
        return 0

    except AssertionError as e:
        print(f"\n✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
