import argparse
import json
import os
import sys

import psycopg2
import requests

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from config import get_settings

settings = get_settings()


def get_database_connection():
    return psycopg2.connect(
        host="localhost" if settings.db_host == "pgvector" else settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


def get_embedding(text, model="nomic-embed-text:v1.5"):
    """Generates an embedding for the given text using a local Ollama model."""
    try:
        response = requests.post("http://localhost:11434/api/embeddings", json={"model": model, "prompt": text})
        response.raise_for_status()
        embedding = response.json()["embedding"]
        return embedding
    except requests.exceptions.RequestException as e:
        print(f"Error getting embedding: {e}")
        return None


def find_similar_chunks(question_embedding, conn, model_name="nomic-embed-text:v1.5", top_k=5):
    """Finds the most similar text chunks from the database for a specific model."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM models WHERE name = %s;", (model_name,))
        model_id_res = cur.fetchone()
        if not model_id_res:
            print(f"Model '{model_name}' not found in the database.")
            return []
        model_id = model_id_res[0]

        cur.execute(
            """
            SELECT c.content
            FROM document_chunks c
            JOIN embeddings e ON c.id = e.chunk_id
            WHERE e.model_id = %s
            ORDER BY c.embedding <-> %s::vector
            LIMIT %s
            """,
            (model_id, json.dumps(question_embedding), top_k),
        )
        results = [row[0] for row in cur.fetchall()]
        return results


def ask_local_llm(question, context, model="mistral:7B"):
    """Asks a question to a local LLM with provided context."""
    prompt = f"Using the following context, please answer the question.\n\nContext:\n{''.join(context)}\n\nQuestion: {question}\n\nAnswer:"
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},  # Add stream=False for simpler response handling
        )
        response.raise_for_status()
        return response.json().get("response", "No response")
    except requests.exceptions.RequestException as e:
        print(f"Error asking local LLM: {e}")
        return "Error generating answer."


def main():
    parser = argparse.ArgumentParser(description="Ask questions to a local LLM using context from a vector database.")
    parser.add_argument("questions_file", help="Path to the JSON file containing the generated questions.")
    args = parser.parse_args()

    try:
        with open(args.questions_file, "r") as f:
            questions = json.load(f)
    except FileNotFoundError:
        print(f"Error: Questions file not found at {args.questions_file}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {args.questions_file}")
        return

    conn = get_database_connection()
    qa_results = []

    for question in questions:
        print(f"Processing question: {question}")

        # 1. Generate embedding for the question
        question_embedding = get_embedding(question)
        if not question_embedding:
            continue

        # 2. Find similar chunks from the database
        context_chunks = find_similar_chunks(question_embedding, conn)
        if not context_chunks:
            print("Could not find relevant context.")
            context_chunks = []  # Proceed without context if none is found

        # 3. Ask the local LLM
        answer = ask_local_llm(question, context_chunks)

        # 4. Store results
        qa_results.append({"question": question, "context": context_chunks, "answer": answer})
        print(f"  Answer: {answer}\n")

    conn.close()

    # Save all results to a file
    output_filename = "qa_results.json"
    with open(output_filename, "w") as f:
        json.dump(qa_results, f, indent=2)

    print(f"Successfully generated answers and saved them to {output_filename}")


if __name__ == "__main__":
    main()
