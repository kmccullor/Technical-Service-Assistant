#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path to import from other modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bin.create_chunks import chunk_text
from pdf_processor.extract_text import extract_text

# Read API key from environment for safety. Don't hard-code secrets in source.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

REMOTE_EMBEDDING_MODELS = ["sentence-transformers/all-minilm-l6-v2", "text-embedding-ada-002"]


# Pydantic Models for API validation
class Embedding(BaseModel):
    embedding: List[float]


class EmbeddingResponse(BaseModel):
    data: List[Embedding]


class Chunk(BaseModel):
    metadata: Dict[str, Any]
    text: str
    embedding: List[float]


class ModelResult(BaseModel):
    document: str
    chunks: List[Chunk]


def get_remote_embedding(model: str, text: str) -> Optional[List[float]]:
    # Read API key from environment for safety. Don't hard-code secrets in source.
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    if not OPENROUTER_API_KEY:
        # Fail fast if key is not available
        print("Error: OPENROUTER_API_KEY environment variable not set.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}

    payload = {"model": model, "input": text}

    embedding_url = "https://openrouter.ai/api/v1/embeddings"

    log_dir = "/home/kmccullor/Projects/Technical-Service-Assistant/logs"
    os.makedirs(log_dir, exist_ok=True)
    error_log_file = os.path.join(log_dir, "remote_embedding_errors.log")

    # Use a simple retry loop for transient errors (5xx, 429). Keep retries small to avoid spamming the API.
    max_retries = 3
    backoff_seconds = 1
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Requesting embedding (attempt {attempt}/{max_retries}) from {embedding_url} with model {model}")
            response = requests.post(embedding_url, headers=headers, data=json.dumps(payload), timeout=30)

            # If the server returns an HTML page (authentication, error page, etc.) save it for debugging and don't retry.
            content_type = response.headers.get("Content-Type", "")
            body_lower = response.text.lower() if isinstance(response.text, str) else ""
            if "text/html" in content_type or body_lower.strip().startswith("<!doctype html>") or "<html" in body_lower:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                html_error_file = os.path.join(log_dir, f"error_{model.replace('/', '_')}_{timestamp}.html")
                with open(html_error_file, "w") as f:
                    f.write(response.text)
                error_message = f"Received HTML response for model {model}. Details saved to {html_error_file}"
                print(error_message)
                with open(error_log_file, "a") as f:
                    f.write(f"{datetime.datetime.now()}: {error_message}\n")
                return None

            # Raise for HTTP errors so we can handle retries for 5xx/429
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                status = response.status_code
                # Retry on 5xx and 429
                if status >= 500 or status == 429:
                    if attempt < max_retries:
                        print(f"Transient HTTP error {status}, backing off {backoff_seconds}s and retrying...")
                        time.sleep(backoff_seconds)
                        backoff_seconds *= 2
                        continue
                    else:
                        error_message = (
                            f"HTTP error {status} from OpenRouter for model {model} after {attempt} attempts."
                        )
                        print(error_message)
                        with open(error_log_file, "a") as f:
                            f.write(
                                f"{datetime.datetime.now()}: {error_message}\nResponse Status: {status}\nResponse Body: {response.text}\n\n"
                            )
                        return None
                else:
                    # Non-retryable HTTP error (4xx) — log and return
                    error_message = f"HTTP error {status} from OpenRouter for model {model}."
                    print(error_message)
                    with open(error_log_file, "a") as f:
                        f.write(
                            f"{datetime.datetime.now()}: {error_message}\nResponse Status: {status}\nResponse Body: {response.text}\n\n"
                        )
                    return None

            # Try to parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError:
                error_message = f"Failed to decode JSON from OpenRouter for model {model}."
                print(error_message)
                # Save body for debugging
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                text_error_file = os.path.join(log_dir, f"error_jsondecode_{model.replace('/', '_')}_{timestamp}.txt")
                with open(text_error_file, "w") as f:
                    f.write(response.text)
                with open(error_log_file, "a") as f:
                    f.write(f"{datetime.datetime.now()}: {error_message} Body saved to {text_error_file}\n\n")
                return None

            # Extract embedding if present
            try:
                embedding = data["data"][0]["embedding"]
                return embedding
            except (KeyError, IndexError, TypeError) as e:
                error_message = f"Error parsing response from OpenRouter for model {model}: {e}"
                print(error_message)
                with open(error_log_file, "a") as f:
                    f.write(
                        f"{datetime.datetime.now()}: {error_message}\nResponse Body: {json.dumps(data) if isinstance(data, (dict, list)) else str(data)}\n\n"
                    )
                return None
        except requests.exceptions.RequestException as e:
            # Network-level error — retry a few times
            print(f"RequestException on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(backoff_seconds)
                backoff_seconds *= 2
                continue
            else:
                error_message = f"Error calling OpenRouter API for model {model}: {e}"
                print(error_message)
                with open(error_log_file, "a") as f:
                    f.write(f"{datetime.datetime.now()}: {error_message}\n\n")
                return None
    # If we exit the retry loop without returning, treat it as a failure
    error_message = f"Failed to obtain embedding for model {model} after {max_retries} attempts."
    print(error_message)
    with open(error_log_file, "a") as f:
        f.write(f"{datetime.datetime.now()}: {error_message}\n\n")
    return None


def main():
    parser = argparse.ArgumentParser(description="Create embeddings for a PDF document.")
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=os.getenv("PDF_PATH"),
        help="Path to the PDF file. Defaults to the value of the PDF_PATH environment variable.",
    )
    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not pdf_path:
        print("Error: PDF path not provided as an argument or in the PDF_PATH environment variable.")
        sys.exit(1)

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

    results_file = "embedding_test_results.json"
    all_results: Dict[str, ModelResult] = {}
    if os.path.exists(results_file):
        with open(results_file, "r") as f:
            try:
                # Load and validate existing data
                raw_data = json.load(f)
                for model_key, data in raw_data.items():
                    all_results[model_key] = ModelResult.parse_obj(data)
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Could not parse or validate existing results file, will create a new one. Error: {e}")
                all_results = {}

    for model in REMOTE_EMBEDDING_MODELS:
        print(f"\nTesting remote model: {model}")
        model_key = f"openrouter/{model}"

        if model_key not in all_results:
            all_results[model_key] = ModelResult(document=document_name, chunks=[])

        existing_chunks = all_results[model_key].chunks

        for i, chunk_data in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}...")

            # Check if a chunk with the same text already exists
            if any(c.text == chunk_data["text"] for c in existing_chunks):
                print(f"Chunk {i+1} with same text already has an embedding for model {model}. Skipping.")
                continue

            embedding = get_remote_embedding(model, chunk_data["text"])

            if embedding:
                print(f"  Embedding created for chunk {i+1}.")
                try:
                    chunk_result = Chunk(metadata=chunk_data["metadata"], text=chunk_data["text"], embedding=embedding)
                    all_results[model_key].chunks.append(chunk_result)
                except ValidationError as e:
                    print(f"  Failed to validate chunk data for chunk {i+1}: {e}")
            else:
                print(f"  Failed to get embedding for chunk {i+1}.")

            time.sleep(1)  # Add a 1-second delay between requests

        with open(results_file, "w") as f:
            # Use model_dump to convert Pydantic models to dictionaries for JSON serialization
            dumped_results = {k: v.model_dump() for k, v in all_results.items()}
            json.dump(dumped_results, f, indent=2)
        print(f"Results for model {model} saved to {results_file}")

    print(f"\nAll results saved to {results_file}")


if __name__ == "__main__":
    main()
