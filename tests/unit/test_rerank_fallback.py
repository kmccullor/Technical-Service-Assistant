"""Unit tests for rerank fallback behavior when Redis is not available.

This test uses the in-memory fallback implemented in utils.redis_cache to ensure
that the `rethink_pipeline` can aggregate cached sub-responses and synthesize a
final response without a real Redis server.
"""

from reranker.question_decomposer import QuestionDecomposer
from reranker.rethink_reranker import rethink_pipeline
from utils.redis_cache import cache_decomposed_response, cache_sub_request_result


def test_rethink_pipeline_with_inmemory_cache():
    q = "Explain FlexNet in detail including its architecture, components, common deployment scenarios, and limitations. Then compare it with LTE in terms of latency, range, and deployment complexity."
    user_id = 42

    decomposer = QuestionDecomposer()
    decomposition = decomposer.decompose_question(q, user_id)

    # Cache decomposition metadata using in-memory fallback
    assert cache_decomposed_response(decomposition.query_hash, user_id, decomposition.to_dict())

    # Create and cache sub-responses
    for sr in decomposition.sub_requests:
        sub_data = {
            "id": sr.id,
            "sub_query": sr.sub_query,
            "response": f"Answer for: {sr.sub_query}",
            "model": "llama3.2:3b",
            "time_ms": 10,
            "confidence": 0.9,
        }
        assert cache_sub_request_result(sr.id, sub_data)

    # Now call rethink_pipeline which should read from the in-memory cache
    final = rethink_pipeline(decomposition.query_hash, user_id, q)

    assert "synthesized" in final
    synth = final.get("synthesized")
    assert isinstance(synth, dict)
    assert synth.get("synthesized_text") is not None
    assert "Answer for" in synth.get("synthesized_text")
