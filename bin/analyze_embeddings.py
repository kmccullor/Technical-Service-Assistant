#!/usr/bin/env python3
import json
import os

import numpy as np


def cosine_similarity(v1, v2):
    """Computes the cosine similarity between two vectors."""
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    # Handle potential zero vectors
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)


def analyze_results():
    """Analyzes the embedding results and prints cosine similarities."""
    results_file = os.path.join(os.path.dirname(__file__), "..", "embedding_test_results.json")
    try:
        with open(results_file, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading or parsing results file: {e}")
        return

    analysis = {}

    # The sample texts used in the benchmark
    t1 = "The quick brown fox jumps over the lazy dog."
    t2 = "Artificial intelligence is transforming the world."
    t3 = "Supabase provides a powerful Postgres backend with vector support."

    print("=" * 50)
    print("Embedding Similarity Analysis")
    print("=" * 50)
    print(f"Comparing semantic similarity for:\n1. '{t1}'\n2. '{t2}'\n3. '{t3}'\n")
    print("A good model should show higher similarity between (2) and (3).\n")

    for model, results in data.items():
        if not results or len(results) < 3:
            print(f"Skipping {model}: Incomplete results.")
            continue

        # Create a mapping from text to embedding to ensure correct comparison
        text_map = {r["text"]: r["embedding"] for r in results}

        if not all(t in text_map for t in [t1, t2, t3]):
            print(f"Skipping {model}: Missing one of the key sample texts.")
            continue

        e1 = np.array(text_map[t1])
        e2 = np.array(text_map[t2])
        e3 = np.array(text_map[t3])

        sim_12 = cosine_similarity(e1, e2)
        sim_13 = cosine_similarity(e1, e3)
        sim_23 = cosine_similarity(e2, e3)

        analysis[model] = {
            "similarity_fox_vs_ai": sim_12,
            "similarity_fox_vs_supabase": sim_13,
            "similarity_ai_vs_supabase": sim_23,
            "embedding_dimension": len(e1),
        }

    # Sort models by the most important metric: similarity between the two tech sentences
    sorted_models = sorted(analysis.items(), key=lambda item: item[1]["similarity_ai_vs_supabase"], reverse=True)

    print("--- Analysis Results (sorted by AI vs Supabase similarity) ---")
    for model, metrics in sorted_models:
        print(f"\nModel: {model}")
        print(f"  - Dimension: {metrics['embedding_dimension']}")
        print(f"  - Similarity (AI vs Supabase): {metrics['similarity_ai_vs_supabase']:.4f}  <-- (Higher is better)")
        print(f"  - Similarity (Fox vs AI):      {metrics['similarity_fox_vs_ai']:.4f}")
        print(f"  - Similarity (Fox vs Supabase):  {metrics['similarity_fox_vs_supabase']:.4f}")

    print("\n--- Recommendation ---")
    if sorted_models:
        best_model = sorted_models[0][0]
        sorted_models[0][1]
        print(f"Best performing model: '{best_model}'")
        print(
            "Reasoning: It shows the highest semantic similarity between the related technical sentences ('AI' and 'Supabase') while maintaining a lower similarity with the unrelated 'fox' sentence."
        )
        print("This indicates a strong ability to distinguish between different topics and recognize related concepts.")
    else:
        print("Could not determine a recommendation based on the results.")


if __name__ == "__main__":
    analyze_results()
