import os
import sys

import psycopg2
import requests

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_settings

settings = get_settings()


def get_db_connection():
    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


def get_embedding(text):
    try:
        # Use configured Ollama URL and model
        ollama_url = settings.ollama_url
        if not ollama_url.endswith("/embeddings"):
            if ollama_url.rstrip("/").endswith("/api"):
                ollama_url = ollama_url.rstrip("/") + "/embeddings"
            else:
                ollama_url = ollama_url.rstrip("/") + "/api/embed"

        response = requests.post(ollama_url, json={"model": settings.embedding_model.split(":")[0], "prompt": text})
        response.raise_for_status()
        return response.json()["embedding"]
    except requests.exceptions.RequestException as e:
        print(f"Error getting embedding: {e}")
        return None


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Get a random chunk from the database
    cur.execute("SELECT id, content FROM document_chunks ORDER BY random() LIMIT 1;")
    random_chunk = cur.fetchone()
    if not random_chunk:
        print("No document chunks found in the database.")
        return

    chunk_id, chunk_content = random_chunk
    print(f"Testing with chunk ID: {chunk_id}")
    print(f"Content: {chunk_content[:200]}...")

    # 2. Generate a new embedding for this chunk's content
    print("\nGenerating a new embedding for this content...")
    query_embedding = get_embedding(chunk_content)

    if not query_embedding:
        print("Failed to generate embedding. Aborting test.")
        return

    # 3. Query the database to find the most similar chunks
    print("Querying for similar chunks...")
    cur.execute("SELECT id, content, similarity FROM match_document_chunks(%s, 0.5, 5);", (query_embedding,))
    results = cur.fetchall()

    # 4. Check the results
    print("\nTop 5 similar chunks found:")
    for r_id, r_content, r_similarity in results:
        print(f"  - ID: {r_id}, Similarity: {r_similarity:.4f}, Content: {r_content[:100]}...")

    if results and results[0][0] == chunk_id:
        print("\n✅ Accuracy test passed! The most similar chunk is the original chunk.")
    else:
        print("\n❌ Accuracy test failed. The top result did not match the original chunk.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
