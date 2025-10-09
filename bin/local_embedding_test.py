#!/usr/bin/env python3
import argparse
import json
import os
import sys

import requests
import tiktoken

# Add parent directory to path to import from other modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bin.create_chunks import chunk_text
from pdf_processor.extract_text import extract_text

OLLAMA_URL = "http://localhost:11434/api/embeddings"

LOCAL_EMBEDDING_MODELS = ["nomic-embed-text:v1.5", "mxbai-embed-large:v1"]


def get_local_embedding(model, text):
    """
    Gets embedding from a local Ollama model and counts tokens.
    """
    try:
        # Token counting using tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        token_count = len(tokens)
    except Exception as e:
        print(f"Could not count tokens for model {model}: {e}")
        token_count = 0

    payload = {"model": model, "prompt": text}

    try:
        print(f"Requesting embedding from {OLLAMA_URL} with model {model}")
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()

        embedding = response.json().get("embedding")
        return embedding, token_count
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API for model {model}: {e}")
        if "response" in locals() and response is not None:
            print(f"Response status code: {response.status_code}")
            print(f"Response body: {response.text}")
        return None, token_count
    except json.JSONDecodeError:
        print(f"Failed to decode JSON from Ollama for model {model}.")
        if "response" in locals() and response is not None:
            print(f"Response body: {response.text}")
        return None, token_count
    except (KeyError, IndexError) as e:
        print(f"Error parsing response from Ollama for model {model}: {e}")
        if "response" in locals() and response is not None:
            print(f"Response body: {response.text}")
        return None, token_count


def main():
    parser = argparse.ArgumentParser(description="Create embeddings for a PDF document using local models.")
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    args = parser.parse_args()

    pdf_path = args.pdf_path
    document_name = os.path.basename(pdf_path)

    print(f"Processing {document_name}...")

    # 1. Extract text
    full_text = extract_text(pdf_path)
    if not full_text:
        print("No text extracted from the PDF. Exiting.")
        return

    # 2. Chunk text
    chunks = chunk_text(full_text, document_name)
    if not chunks:
        print("No chunks created from the text. Exiting.")
        return

    print(f"Created {len(chunks)} chunks.")

    models = LOCAL_EMBEDDING_MODELS

    results_file = "embedding_test_results.json"
    all_results = {}
    if os.path.exists(results_file):
        with open(results_file, "r") as f:
            try:
                all_results = json.load(f)
            except json.JSONDecodeError:
                print("Could not parse existing results file, will create a new one.")

    for model in models:
        print(f"\nTesting local model: {model}")
        model_key = model  # Use model name directly as key

        if (
            model_key not in all_results
            or not isinstance(all_results.get(model_key), dict)
            or "chunks" not in all_results.get(model_key)
        ):
            all_results[model_key] = {"document": document_name, "total_tokens": 0, "chunks": []}

        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}...")

            if i < len(all_results[model_key]["chunks"]):
                print(f"Chunk {i+1} already has an embedding for model {model}. Skipping.")
                continue

            embedding, tokens = get_local_embedding(model, chunk["text"])

            if embedding:
                print(f"  Embedding created for chunk {i+1}. Tokens: {tokens}")
                chunk_result = {
                    "metadata": chunk["metadata"],
                    "text": chunk["text"],
                    "embedding": embedding,
                    "tokens": tokens,
                }
                all_results[model_key]["chunks"].append(chunk_result)
                all_results[model_key]["total_tokens"] += tokens
            else:
                print(f"  Failed to get embedding for chunk {i+1}.")

        with open(results_file, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"Results for model {model} saved to {results_file}")

    print(f"\nAll results saved to {results_file}")


if __name__ == "__main__":
    main()
