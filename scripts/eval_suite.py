#!/usr/bin/env python3
"""Evaluation harness for embedding retrieval quality.

Current capabilities:
- Loads a small YAML/JSON evaluation set of queries and relevant chunk text snippets or IDs.
- Computes embedding for each query via Ollama.
- Performs similarity search in Postgres (vector_l2_ops) retrieving top-N.
- Calculates Recall@K for configured K values.
- (Future) MRR, nDCG, rerank impact.

Usage:
  python scripts/eval_suite.py --eval-file eval/sample_eval.json --k 5 10 20

Evaluation file format (JSON list):
[
  {
    "query": "What is the warranty period?",
    "relevant_substrings": ["warranty period is 12 months"],
    // OR alternatively: "relevant_chunk_ids": [123, 124]
  }
]

Environment variables reused from config.py (DB + EMBEDDING_MODEL + OLLAMA_URL)

Outputs summary metrics and per-query results table.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

import psycopg2
import requests
from psycopg2.extras import RealDictCursor

from config import get_settings

settings = get_settings()

DEFAULT_TOP_N = 100


def load_eval(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".json"):
            return json.load(f)
        raise ValueError("Only JSON supported for now.")


def get_embedding(text: str) -> List[float]:
    url = settings.ollama_url
    # Accept both base or full embeddings endpoint forms
    if not url.endswith("/embeddings"):
        if url.rstrip("/").endswith("/api"):
            url = url.rstrip("/") + "/embeddings"
        else:
            url = url.rstrip("/") + "/api/embeddings"
    model = settings.embedding_model.split(":")[0]
    resp = requests.post(url, json={"model": model, "prompt": text}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["embedding"] if "embedding" in data else data.get("data", {}).get("embedding")


def connect_db():
    return psycopg2.connect(
        host=settings.db_host,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        port=settings.db_port,
    )


def similarity_search(conn, embedding: Sequence[float], limit: int) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT c.id, c.content as content
            FROM document_chunks c
            JOIN embeddings e ON c.id = e.chunk_id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <-> %s::vector
            LIMIT %s
            """,
            (embedding, limit),
        )
        return cur.fetchall()


def match_relevance(hit_text: str, relevant_substrings: List[str]) -> bool:
    lower = hit_text.lower()
    return any(sub.lower() in lower for sub in relevant_substrings)


def compute_recall_at_k(hits: List[Dict[str, Any]], relevant: List[str], ks: List[int]) -> Dict[int, float]:
    results = {}
    for k in ks:
        top = hits[:k]
        found = any(match_relevance(h["content"], relevant) for h in top)
        results[k] = 1.0 if found else 0.0
    return results


def compute_mrr(hits: List[Dict[str, Any]], relevant: List[str]) -> float:
    for idx, h in enumerate(hits, start=1):
        if match_relevance(h["content"], relevant):
            return 1.0 / idx
    return 0.0


def compute_ndcg(hits: List[Dict[str, Any]], relevant: List[str], k: int) -> float:
    # Binary relevance: 1 if any relevant substring appears
    def rel(h):
        return 1 if match_relevance(h["content"], relevant) else 0

    dcg = 0.0
    for i, h in enumerate(hits[:k], start=1):
        r = rel(h)
        if r:
            import math

            dcg += (2**r - 1) / math.log2(i + 1)
    # Ideal DCG: best ordering places all relevant first
    ideal_rels = [1] * min(sum(rel(h) for h in hits), k)
    idcg = 0.0
    for i, r in enumerate(ideal_rels, start=1):
        import math

        idcg += (2**r - 1) / math.log2(i + 1)
    return dcg / idcg if idcg > 0 else 0.0


def main():
    parser = argparse.ArgumentParser(description="Embedding retrieval evaluation suite")
    parser.add_argument("--eval-file", required=True)
    parser.add_argument("--k", nargs="+", type=int, default=[5, 10, 20], help="K values for Recall@K")
    parser.add_argument("--limit", type=int, default=DEFAULT_TOP_N, help="Search candidate pool size")
    parser.add_argument("--ndcg-k", type=int, default=20, help="Cutoff for nDCG calculation")
    parser.add_argument(
        "--rerank-endpoint",
        type=str,
        default=None,
        help="Optional reranker endpoint (POST /rerank) to evaluate post-rerank metrics",
    )
    parser.add_argument("--api-key", type=str, default=None, help="API key for rerank endpoint if required")
    args = parser.parse_args()

    eval_items = load_eval(args.eval_file)
    if not eval_items:
        print("Empty evaluation set.")
        return 1

    conn = connect_db()
    per_query = []

    try:
        for item in eval_items:
            query = item["query"]
            relevant_substrings = item.get("relevant_substrings") or []
            relevant_ids = item.get("relevant_chunk_ids") or []
            if not relevant_substrings and not relevant_ids:
                print(f"Skipping query without relevance spec: {query}")
                continue
            t0 = time.perf_counter()
            emb = get_embedding(query)
            t_embed = time.perf_counter() - t0
            t1 = time.perf_counter()
            hits = similarity_search(conn, emb, args.limit)
            t_search = time.perf_counter() - t1

            # If relevant IDs provided, translate to substring check by fetching those contents once (future opt)
            if relevant_ids and not relevant_substrings:
                relevant_texts = [h["content"] for h in hits if h["id"] in relevant_ids]
                relevant_substrings = relevant_texts

            recall_map = compute_recall_at_k(hits, relevant_substrings, args.k)
            mrr = compute_mrr(hits, relevant_substrings)
            ndcg = compute_ndcg(hits, relevant_substrings, args.ndcg_k)

            rerank_metrics: Optional[Dict[str, Any]] = None
            if args.rerank_endpoint:
                try:
                    passages = [h["content"] for h in hits]
                    headers = {"Content-Type": "application/json"}
                    if args.api_key:
                        headers["X-API-Key"] = args.api_key
                    r_start = time.perf_counter()
                    resp = requests.post(
                        args.rerank_endpoint.rstrip("/"),
                        headers=headers,
                        json={"query": query, "passages": passages, "top_k": max(args.k)},
                        timeout=120,
                    )
                    r_elapsed = time.perf_counter() - r_start
                    if resp.status_code == 200:
                        data = resp.json()
                        reranked_passages = data.get("reranked", [])
                        rerank_hits = [{"content": p} for p in reranked_passages]
                        rerank_recall = compute_recall_at_k(rerank_hits, relevant_substrings, args.k)
                        rerank_mrr = compute_mrr(rerank_hits, relevant_substrings)
                        rerank_ndcg = compute_ndcg(rerank_hits, relevant_substrings, args.ndcg_k)
                        rerank_metrics = {
                            "recall": rerank_recall,
                            "mrr": rerank_mrr,
                            "ndcg": rerank_ndcg,
                            "latency_seconds": r_elapsed,
                        }
                    else:
                        rerank_metrics = {"error": f"HTTP {resp.status_code}", "latency_seconds": r_elapsed}
                except Exception as e:
                    rerank_metrics = {"error": str(e)}

            per_query.append(
                {
                    "query": query,
                    "recall": recall_map,
                    "mrr": mrr,
                    "ndcg": ndcg,
                    "timing_seconds": {"embed": t_embed, "search": t_search, "total": t_embed + t_search},
                    "rerank": rerank_metrics,
                }
            )
    finally:
        conn.close()

    # Aggregate
    agg = {k: statistics.mean([pq["recall"][k] for pq in per_query]) for k in args.k}
    agg_mrr = statistics.mean([pq["mrr"] for pq in per_query]) if per_query else 0.0
    agg_ndcg = statistics.mean([pq["ndcg"] for pq in per_query]) if per_query else 0.0
    avg_embed = statistics.mean([pq["timing_seconds"]["embed"] for pq in per_query]) if per_query else 0.0
    avg_search = statistics.mean([pq["timing_seconds"]["search"] for pq in per_query]) if per_query else 0.0
    avg_total = statistics.mean([pq["timing_seconds"]["total"] for pq in per_query]) if per_query else 0.0

    # Rerank aggregate (if present)
    rerank_present = [pq for pq in per_query if pq.get("rerank") and not pq["rerank"].get("error")]
    rerank_agg = None
    if rerank_present:
        rerank_agg = {
            f"rerank_recall@{k}": statistics.mean([pq["rerank"]["recall"][k] for pq in rerank_present]) for k in args.k
        }
        rerank_agg["rerank_mrr"] = statistics.mean([pq["rerank"]["mrr"] for pq in rerank_present])
        rerank_agg[f"rerank_ndcg@{args.ndcg_k}"] = statistics.mean([pq["rerank"]["ndcg"] for pq in rerank_present])
        rerank_agg["rerank_latency_avg_s"] = statistics.mean([pq["rerank"]["latency_seconds"] for pq in rerank_present])

    print("=== Retrieval Evaluation Summary ===")
    for k in args.k:
        print(f"Recall@{k}: {agg[k]:.3f}")
    print(f"MRR: {agg_mrr:.3f}")
    print(f"nDCG@{args.ndcg_k}: {agg_ndcg:.3f}")
    print(f"Avg Embed Time (s): {avg_embed:.4f}")
    print(f"Avg Search Time (s): {avg_search:.4f}")
    print(f"Avg Total Query Time (s): {avg_total:.4f}")
    if rerank_agg:
        print("-- Rerank Aggregate --")
        for k in args.k:
            print(f"Rerank Recall@{k}: {rerank_agg[f'rerank_recall@{k}']:.3f}")
        print(f"Rerank MRR: {rerank_agg['rerank_mrr']:.3f}")
        print(f"Rerank nDCG@{args.ndcg_k}: {rerank_agg[f'rerank_ndcg@{args.ndcg_k}']:.3f}")
        print(f"Rerank Avg Latency (s): {rerank_agg['rerank_latency_avg_s']:.4f}")
    print("\nPer-query results:")
    for pq in per_query:
        parts = ", ".join([f"R@{k}={pq['recall'][k]:.0f}" for k in args.k])
        base_line = f"- {pq['query']} :: {parts}, MRR={pq['mrr']:.2f}, nDCG={pq['ndcg']:.2f}, t_total={pq['timing_seconds']['total']:.3f}s"
        if pq.get("rerank") and not pq["rerank"].get("error"):
            base_line += f", RR_MRR={pq['rerank']['mrr']:.2f}"
        elif pq.get("rerank") and pq["rerank"].get("error"):
            base_line += f", RR_ERR={pq['rerank']['error']}"
        print(base_line)

    # JSON export optional
    out_path = "eval_results.json"
    summary_payload = {
        **agg,
        "mrr": agg_mrr,
        f"ndcg@{args.ndcg_k}": agg_ndcg,
        "avg_embed_s": avg_embed,
        "avg_search_s": avg_search,
        "avg_total_s": avg_total,
    }
    if rerank_agg:
        summary_payload.update(rerank_agg)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary_payload, "queries": per_query}, f, indent=2)
    print(f"\nWrote results -> {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
