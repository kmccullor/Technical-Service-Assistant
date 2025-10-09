import json
import os
import sys

import psycopg2
from psycopg2.extras import Json

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_settings

settings = get_settings()


def get_db_connection():
    return psycopg2.connect(
        host="localhost" if settings.db_host == "pgvector" else settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


def create_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        """
        )
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS models (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        """
        )
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS chunks (
            id SERIAL PRIMARY KEY,
            document_id INTEGER REFERENCES documents(id),
            chunk_index INTEGER,
            text TEXT,
            metadata JSONB,
            UNIQUE(document_id, chunk_index)
        );
        """
        )
        # Set a fixed, larger vector size to accommodate different models
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS embeddings (
            id SERIAL PRIMARY KEY,
            chunk_id INTEGER REFERENCES chunks(id),
            model_id INTEGER REFERENCES models(id),
            embedding vector(1536),
            UNIQUE(chunk_id, model_id)
        );
        """
        )
        conn.commit()


def main():
    conn = get_db_connection()
    create_tables(conn)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    results_file = os.path.join(project_root, "embedding_test_results.json")

    try:
        with open(results_file, "r") as f:
            all_results = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading or parsing JSON file: {e}")
        return

    with conn.cursor() as cur:
        for model_name, data in all_results.items():
            if not data:
                print(f"Skipping model '{model_name}' as it has no data.")
                continue

            # --- Get or Create Model ID ---
            cur.execute("INSERT INTO models (name) VALUES (%s) ON CONFLICT (name) DO NOTHING;", (model_name,))
            cur.execute("SELECT id FROM models WHERE name = %s;", (model_name,))
            model_id_result = cur.fetchone()
            if not model_id_result:
                print(f"Error: Could not find or create model '{model_name}'.")
                continue
            model_id = model_id_result[0]

            document_name = "Unknown Document"
            chunks_to_process = []

            # Heuristic to detect data format
            if isinstance(data, dict) and "chunks" in data and isinstance(data["chunks"], list):
                # Format: { "document": "...", "chunks": [...] }
                document_name = data.get("document", "Unknown Document")
                chunks_to_process = data["chunks"]
            elif isinstance(data, list) and all(isinstance(item, dict) for item in data):
                # Format: [ { "text": "...", "embedding": [...] }, ... ]
                chunks_to_process = data
            else:
                print(f"Skipping model '{model_name}' due to unrecognized data format.")
                continue

            if not chunks_to_process:
                print(f"No chunks to process for model '{model_name}'.")
                continue

            # --- Get or Create Document ID ---
            cur.execute("INSERT INTO documents (name) VALUES (%s) ON CONFLICT (name) DO NOTHING;", (document_name,))
            cur.execute("SELECT id from pdf_documents WHERE name = %s;", (document_name,))
            document_id_result = cur.fetchone()
            if not document_id_result:
                print(f"Error: Could not find or create document '{document_name}'.")
                continue
            document_id = document_id_result[0]

            # --- Process Chunks ---
            for i, chunk_data in enumerate(chunks_to_process):
                if not isinstance(chunk_data, dict):
                    print(f"Skipping a chunk for model '{model_name}' because it is not a dictionary.")
                    continue

                embedding_vector = chunk_data.get("embedding")
                text = chunk_data.get("text")

                if not embedding_vector or not text:
                    print(f"Skipping chunk {i} for model '{model_name}' due to missing 'embedding' or 'text'.")
                    continue

                # Pad or truncate vector to the required dimension
                if len(embedding_vector) < 1536:
                    embedding_vector.extend([0] * (1536 - len(embedding_vector)))
                elif len(embedding_vector) > 1536:
                    embedding_vector = embedding_vector[:1536]

                metadata = chunk_data.get("metadata", {})
                # Use list index as a fallback for chunk_index
                chunk_index = metadata.get("chunk_index", i)

                # --- Insert Chunk and Embedding ---
                cur.execute(
                    """
                    INSERT INTO chunks (document_id, chunk_index, text, metadata)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (document_id, chunk_index)
                    DO UPDATE SET text = EXCLUDED.text, metadata = EXCLUDED.metadata
                    RETURNING id;
                    """,
                    (document_id, chunk_index, text, Json(metadata)),
                )
                chunk_id_result = cur.fetchone()
                if not chunk_id_result:
                    # If the chunk already existed, we need to fetch its ID
                    cur.execute(
                        "SELECT id from document_chunks WHERE document_id = %s AND chunk_index = %s;",
                        (document_id, chunk_index),
                    )
                    chunk_id_result = cur.fetchone()

                if not chunk_id_result:
                    print(
                        f"Failed to insert or retrieve chunk_id for model '{model_name}', chunk_index {chunk_index}. Skipping embedding."
                    )
                    continue
                chunk_id = chunk_id_result[0]

                cur.execute(
                    """
                    INSERT INTO embeddings (chunk_id, model_id, embedding)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (chunk_id, model_id)
                    DO NOTHING;
                    """,
                    (chunk_id, model_id, embedding_vector),
                )

    conn.commit()
    conn.close()
    print("Embeddings loaded into the database.")


if __name__ == "__main__":
    main()
