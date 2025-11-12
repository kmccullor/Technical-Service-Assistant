"""Unit tests for rerank/rethink pipeline."""

from __future__ import annotations

import pytest

from reranker.rethink_reranker import (
    _normalize_text,
    score_subresponse_relevance,
    rerank_subresponses,
    synthesize_reranked_response,
)


def test_normalize_text():
    assert _normalize_text("What is FlexNet?  ") == "what is flexnet?"


def test_token_overlap_and_similarity():
    q = "What is FlexNet technology?"
    r = "FlexNet technology is a mesh-based communication system for AMI meters."
    score = score_subresponse_relevance(q, r)
    assert 0.0 <= score <= 1.0
    assert score > 0.0


def test_rerank_subresponses_basic():
    orig = "Compare FlexNet and LTE"
    subs = [
        {"id": "1", "response": "FlexNet is a mesh network for AMI." , "confidence": 0.9},
        {"id": "2", "response": "LTE is cellular-based." , "confidence": 0.9},
        {"id": "3", "response": "Unrelated text about cooking." , "confidence": 0.5},
    ]
    reranked = rerank_subresponses(orig, subs)
    # Top result should not be the unrelated one
    assert reranked[0]["id"] in {"1", "2"}


def test_synthesize_reranked_response_empty():
    synthesized = synthesize_reranked_response("What?", [])
    assert synthesized["synthesized_text"] == ""
    assert "No sub-responses" in synthesized["notes"][0]


def test_synthesize_reranked_response_basic():
    subs = [
        {"id": "1", "response": "A","relevance": 0.9},
        {"id": "2", "response": "B","relevance": 0.8},
    ]
    synthesized = synthesize_reranked_response("Q", subs)
    assert synthesized["synthesized_text"] in {"A", "A\n\nB"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
