#!/usr/bin/env python3
"""
Lightweight A/B test harness for Hybrid Search vs Vector vs BM25.
Saves results to eval/hybrid_ab_results_<timestamp>.json

Usage:
    python3 scripts/analysis/run_hybrid_ab_test.py --top_k 3 --alphas 0.3 0.5 0.7 0.9
"""
import argparse
import json
import os
import sys
import time
from typing import List, Dict

# Ensure project root is on path so imports from scripts/analysis work when run directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.analysis.hybrid_search import HybridSearch


def normalize_text(s: str) -> List[str]:
    import re

    tokens = re.findall(r"\b\w+\b", s.lower())
    return tokens


def keyword_match_score(query: str, texts: List[str]) -> float:
    """Simple heuristic: fraction of returned texts that contain any keyword from query."""
    qtokens = set(normalize_text(query))
    if not qtokens:
        return 0.0
    matched = 0
    for t in texts:
        tkn = set(normalize_text(t))
        if qtokens & tkn:
            matched += 1
    return matched / max(1, len(texts))


def run_ab_test(queries: List[str], top_k: int, alphas: List[float]) -> Dict:
    results = {
        "timestamp": time.strftime("%Y%m%d_%H%M%S"),
        "top_k": top_k,
        "alphas": alphas,
        "queries": queries,
        "results": {},
    }

    for alpha in alphas:
        print(f"Building HybridSearch index with alpha={alpha} (this may take a moment)...")
        hs = HybridSearch(alpha=alpha)
        # Build index from current `document_chunks` table to match project schema
        print("Indexing documents from database (document_chunks)...")
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            from config import get_settings

            settings = get_settings()
            db_host = settings.db_host
            db_name = settings.db_name
            db_user = settings.db_user
            db_password = settings.db_password
            db_port = settings.db_port

            conn = psycopg2.connect(host=db_host, database=db_name, user=db_user, password=db_password, port=db_port)
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        dc.id as id,
                        dc.content as text,
                        dc.embedding as embedding,
                        d.file_name as document_name,
                        d.document_type as document_type
                    FROM document_chunks dc
                    JOIN documents d ON dc.document_id = d.id
                    WHERE dc.embedding IS NOT NULL
                    ORDER BY dc.id
                    LIMIT 10000
                    """
                )
                rows = cursor.fetchall()

            conn.close()

            hs.document_texts = [row['text'] for row in rows]
            hs.document_metadata = [
                {
                    'id': row['id'],
                    'document_name': row.get('document_name'),
                    'metadata': {'document_type': row.get('document_type')},
                    'embedding': row.get('embedding'),
                }
                for row in rows
            ]

            # Build BM25 index
            hs.bm25.fit(hs.document_texts)
            hs.corpus_indexed = True
        except Exception as e:
            print(f"Failed to build index from document_chunks: {e}")
            # fallback to hybrid internal build (may fail)

        alpha_key = f"alpha_{alpha}"
        results["results"][alpha_key] = {"per_query": [], "aggregate": {}}

        agg_scores = {"vector": [], "bm25": [], "hybrid": []}

        for q in queries:
            print(f"Query: {q}")
            comp = hs.compare_methods(q, top_k=top_k)

            vect_texts = [r["text"] for r in comp.get("vector_only", [])[:top_k]]
            bm25_texts = [r["text"] for r in comp.get("bm25_only", [])[:top_k]]
            hybrid_texts = [r["text"] for r in comp.get("hybrid", [])[:top_k]]

            vect_score = keyword_match_score(q, vect_texts)
            bm25_score = keyword_match_score(q, bm25_texts)
            hybrid_score = keyword_match_score(q, hybrid_texts)

            agg_scores["vector"].append(vect_score)
            agg_scores["bm25"].append(bm25_score)
            agg_scores["hybrid"].append(hybrid_score)

            results["results"][alpha_key]["per_query"].append(
                {
                    "query": q,
                    "vector_score": vect_score,
                    "bm25_score": bm25_score,
                    "hybrid_score": hybrid_score,
                }
            )

        # compute aggregates
        results["results"][alpha_key]["aggregate"] = {
            "vector_mean": sum(agg_scores["vector"]) / len(agg_scores["vector"]) if agg_scores["vector"] else 0,
            "bm25_mean": sum(agg_scores["bm25"]) / len(agg_scores["bm25"]) if agg_scores["bm25"] else 0,
            "hybrid_mean": sum(agg_scores["hybrid"]) / len(agg_scores["hybrid"]) if agg_scores["hybrid"] else 0,
        }

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--top_k", type=int, default=3)
    parser.add_argument("--alphas", type=float, nargs="*", default=[0.3, 0.5, 0.7, 0.9])
    parser.add_argument("--out_dir", type=str, default="eval")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # Small default query set (representative RNI questions)
    queries = [
        "RNI 4.16 release date",
        "security configuration requirements",
        "Active Directory integration setup",
        "installation prerequisites",
        "reporting features available",
    ]

    result = run_ab_test(queries, top_k=args.top_k, alphas=args.alphas)

    out_path = os.path.join(args.out_dir, f"hybrid_ab_results_{result['timestamp']}.json")
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)

    print("\nA/B test complete. Summary:")
    for alpha_key, info in result["results"].items():
        agg = info["aggregate"]
        print(f"{alpha_key}: vector_mean={agg['vector_mean']:.3f}, bm25_mean={agg['bm25_mean']:.3f}, hybrid_mean={agg['hybrid_mean']:.3f}")

    print(f"Results written to: {out_path}")
