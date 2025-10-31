#!/usr/bin/env python3
import json
import os

# Add parent directory to path to import from other modules
import sys

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from pdf_processor.utils import get_db_connection


def cosine_similarity(v1, v2):
    """Compute cosine similarity between two vectors."""
    if not isinstance(v1, np.ndarray):
        v1 = np.array(v1)
    if not isinstance(v2, np.ndarray):
        v2 = np.array(v2)

    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)

    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0

    return dot_product / (norm_v1 * norm_v2)


def verify_ingestion(conn, model_name: str, expected_chunks: int):
    """Verify that data has been ingested correctly into the database."""

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 1. Verify counts
        cur.execute("SELECT COUNT(*) as count from pdf_documents;")
        doc_count = cur.fetchone()["count"]
        print(f"Found {doc_count} documents.")
        assert doc_count > 0, "No documents found in the database."

        cur.execute("SELECT COUNT(*) as count FROM models;")
        model_count = cur.fetchone()["count"]
        print(f"Found {model_count} models.")
        assert model_count > 0, "No models found in the database."

        cur.execute("SELECT COUNT(*) as count FROM document_chunks;")
        chunk_count = cur.fetchone()["count"]
        print(f"Found {chunk_count} chunks.")
        assert chunk_count >= expected_chunks, f"Expected at least {expected_chunks} chunks, but found {chunk_count}."

        cur.execute("SELECT COUNT(*) as count FROM embeddings;")
        embedding_count = cur.fetchone()["count"]
        print(f"Found {embedding_count} embeddings.")
        assert (
            embedding_count >= expected_chunks
        ), f"Expected at least {expected_chunks} embeddings, but found {embedding_count}."

        # 2. Verify a sample embedding
        cur.execute(
            """
            SELECT c.content, c.embedding
            FROM embeddings e
            JOIN chunks c ON e.chunk_id = c.id
            JOIN models m ON e.model_id = m.id
            WHERE m.name = %s
            ORDER BY c.id
            LIMIT 1;
        """,
            (model_name,),
        )

        sample = cur.fetchone()
        assert sample, f"No embeddings found for model {model_name}."

        print(f"\nVerifying a sample embedding for model '{model_name}'...")

        # Use the remote embedding function to get a fresh embedding for the same text
        # Note: This requires the remote_embedding_test script and its dependencies
        from bin.remote_embedding_test import get_remote_embedding

        retrieved_text = sample["text"]
        retrieved_embedding = sample["embedding"]

        print(f"  Retrieved text: '{retrieved_text[:80]}...'")

        # We need a valid API key to make a live request for verification
        if not os.getenv("OPENROUTER_API_KEY"):
            print("  Skipping live similarity check: OPENROUTER_API_KEY not set.")
            return

        # The model name in the DB might be 'openrouter/text-embedding-ada-002'
        # but the API expects 'text-embedding-ada-002'
        api_model_name = model_name.split("/")[-1]

        live_embedding = get_remote_embedding(api_model_name, retrieved_text)

        if live_embedding:
            similarity = cosine_similarity(retrieved_embedding, live_embedding)
            print(f"  Cosine similarity between stored and live embedding: {similarity:.4f}")
            assert similarity > 0.9, f"Cosine similarity {similarity} is below the threshold of 0.9."
            print("  Verification successful: High similarity.")
        else:
            print("  Could not get a live embedding to compare against. Skipping similarity check.")


if __name__ == "__main__":
    # This script assumes `load_embeddings_to_db.py` has been run
    # and `embedding_test_results.json` exists to determine expected counts.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    results_file = os.path.join(project_root, "embedding_test_results.json")
    if not os.path.exists(results_file):
        print(f"Error: Results file not found at {results_file}.")
        sys.exit(1)

    with open(results_file, "r") as f:
        all_results = json.load(f)

    # Choose one model to verify
    model_to_verify = next(iter(all_results.keys()), None)
    if not model_to_verify:
        print("No models found in the results file. Exiting.")
        sys.exit(1)

    model_data = all_results.get(model_to_verify, {})
    if isinstance(model_data, dict):
        expected_chunk_count = len(model_data.get("chunks", []))
    else:
        expected_chunk_count = 0

    db_conn = None
    try:
        db_conn = get_db_connection()
        print("Database connection successful.")

        verify_ingestion(db_conn, model_to_verify, expected_chunk_count)

    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
    finally:
        if db_conn:
            db_conn.close()
            print("\nDatabase connection closed.")
