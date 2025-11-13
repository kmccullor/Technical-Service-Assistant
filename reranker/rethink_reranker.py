"""Rerank and rethink utilities for decomposed chat responses.

Provides helpers to aggregate cached components from Redis, compute simple
relevance scores comparing the original user question to sub-responses, rerank
sub-responses, and produce an enhanced combined response structure that includes
relevance metadata.

This is intentionally lightweight and deterministic: it uses string similarity
and token-overlap heuristics so it can run without external models. It is
meant to be integrated into the chat synthesis step after sub-requests are
processed (and/or retrieved from Redis).
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from utils.redis_cache import get_decomposed_response, get_sub_request_result

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Basic normalization: lowercasing, collapse whitespace, remove punctuation."""
    if not text:
        return ""
    text = text.lower()
    # Remove punctuation except question marks
    text = re.sub(r"[\.,;:\-()\[\]]", "", text)
    text = " ".join(text.split())
    return text


def _token_overlap(a: str, b: str) -> float:
    """Compute token overlap ratio between two texts.

    Returns fraction of tokens in 'a' that also appear in 'b'.
    """
    atoks = set(_normalize_text(a).split())
    btoks = set(_normalize_text(b).split())
    if not atoks:
        return 0.0
    overlap = atoks.intersection(btoks)
    return len(overlap) / max(1, len(atoks))


def _sequence_similarity(a: str, b: str) -> float:
    """Return a 0.0-1.0 similarity score using difflib.SequenceMatcher."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def score_subresponse_relevance(original_query: str, subresponse_text: str) -> float:
    """Compute a combined relevance score between original question and a subresponse.

    The score is a weighted combination of token overlap and sequence similarity.
    """
    if not subresponse_text:
        return 0.0

    norm_q = _normalize_text(original_query)
    norm_r = _normalize_text(subresponse_text)

    overlap = _token_overlap(norm_q, norm_r)
    seq = _sequence_similarity(norm_q, norm_r)

    # Weighting: give slightly more weight to overlap (exact terms matter)
    score = (0.6 * overlap) + (0.4 * seq)
    return float(max(0.0, min(1.0, score)))


def aggregate_cached_subresponses(query_hash: str, user_id: int) -> Tuple[Optional[dict], List[dict]]:
    """Retrieve decomposition metadata and cached sub-responses from Redis.

    Returns (decomposition_result, list_of_subresponses)
    - decomposition_result: dict from get_decomposed_response or None
    - list_of_subresponses: list of dicts for each sub-request (cached or empty)

    Each subresponse dict contains at least: id, sub_query, response, model, time_ms
    """
    decomposition = get_decomposed_response(query_hash, user_id)
    if not decomposition:
        return None, []

    subresponses: List[dict] = []
    for sr in decomposition.get("sub_requests", []):
        sr_id = sr.get("id")
        if not sr_id:
            continue
        cached = get_sub_request_result(sr_id)
        if cached:
            # Ensure minimal fields
            subresponses.append(
                {
                    "id": sr_id,
                    "sub_query": sr.get("sub_query") or sr.get("sub_query") or "",
                    "response": cached.get("response") or cached.get("answer") or "",
                    "model": cached.get("model"),
                    "time_ms": cached.get("time_ms") or cached.get("generation_time_ms") or 0,
                    "confidence": cached.get("confidence", 1.0),
                    "cached": True,
                }
            )
        else:
            # no cached result available
            subresponses.append(
                {
                    "id": sr_id,
                    "sub_query": sr.get("sub_query") or "",
                    "response": "",
                    "model": None,
                    "time_ms": 0,
                    "confidence": sr.get("confidence", 0.5),
                    "cached": False,
                }
            )

    return decomposition, subresponses


def rerank_subresponses(original_query: str, subresponses: List[dict]) -> List[dict]:
    """Rerank subresponses by relevance to original query.

    Adds a `relevance` score to each subresponse and returns them sorted
    descending by relevance. Also computes an aggregate relevance score.
    """
    scored: List[dict] = []
    for sr in subresponses:
        resp_text = sr.get("response", "")
        # If a subresponse has no response yet, keep low score
        relevance = score_subresponse_relevance(original_query, resp_text) if resp_text else 0.0
        # Combine with model confidence if present
        conf = float(sr.get("confidence", 1.0) or 1.0)
        combined = 0.8 * relevance + 0.2 * conf
        sr_copy = dict(sr)
        sr_copy["relevance"] = float(max(0.0, min(1.0, combined)))
        scored.append(sr_copy)

    scored_sorted = sorted(scored, key=lambda x: x.get("relevance", 0.0), reverse=True)
    return scored_sorted


def synthesize_reranked_response(original_query: str, reranked_subresponses: List[dict]) -> dict:
    """Combine reranked subresponses into a final synthesized response.

    Returns a dict with:
    - 'synthesized_text': combined text
    - 'components': list of reranked subresponses with relevance
    - 'aggregate_relevance': average relevance
    - 'notes': short diagnostic notes
    """
    texts = [sr.get("response", "") for sr in reranked_subresponses if sr.get("response")]
    # Simple synthesis: join top N responses, prefer highest relevance
    top_texts = texts[:5]
    synthesized = "\n\n".join(top_texts).strip()

    relevances = [sr.get("relevance", 0.0) for sr in reranked_subresponses]
    agg = sum(relevances) / max(1, len(relevances))

    notes = []
    if not synthesized:
        notes.append("No sub-responses available to synthesize.")
    else:
        notes.append(f"Synthesized {len(top_texts)} component(s);")
        notes.append(f"Aggregate relevance: {agg:.2f}")

    return {
        "synthesized_text": synthesized,
        "components": reranked_subresponses,
        "aggregate_relevance": float(agg),
        "notes": notes,
    }


def evaluate_response_relevance(original_query: str, final_text: str) -> float:
    """Compute relevance between original question and final synthesized text.

    Returns a 0.0-1.0 score. This is useful as a post-hoc quality check.
    """
    if not final_text:
        return 0.0
    return score_subresponse_relevance(original_query, final_text)


# Convenience helper: full pipeline given query_hash and user_id
def rethink_pipeline(query_hash: str, user_id: int, original_query: Optional[str] = None) -> dict:
    """Retrieve cached components, rerank, synthesize, and evaluate relevance.

    Returns dict with decomposition, reranked components, synthesized text and relevance.
    """
    decomposition, subs = aggregate_cached_subresponses(query_hash, user_id)
    if decomposition is None:
        return {"error": "No decomposition metadata found", "query_hash": query_hash}

    orig = original_query or decomposition.get("original_query", "")
    reranked = rerank_subresponses(orig, subs)
    synthesized = synthesize_reranked_response(orig, reranked)
    final_relevance = evaluate_response_relevance(orig, synthesized.get("synthesized_text", ""))

    return {
        "decomposition": decomposition,
        "reranked_components": reranked,
        "synthesized": synthesized,
        "final_relevance": float(final_relevance),
    }
