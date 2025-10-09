import json
import sys

import requests

OLLAMA_URL = "http://localhost:11434/api/embeddings"


DEFAULT_MODELS = ["nomic-embed-text:v1.5", "gpt-oss:3b"]

SAMPLE_TEXTS = [
    "The quick brown fox jumps over the lazy dog.",
    "Artificial intelligence is transforming the world.",
    "Supabase provides a powerful Postgres backend with vector support.",
]


def get_embedding(model, text):
    payload = {"model": model, "prompt": text}
    response = requests.post(OLLAMA_URL, json=payload)
    if response.status_code == 200:
        return response.json().get("embedding")
    else:
        print(f"Error from model {model}: {response.text}")
        return None


def main():
    # Accept model names as command-line arguments, or use default list
    if len(sys.argv) > 1:
        models = sys.argv[1:]
    else:
        models = DEFAULT_MODELS
    results = {}
    for model in models:
        print(f"\nTesting model: {model}")
        model_results = []
        for text in SAMPLE_TEXTS:
            embedding = get_embedding(model, text)
            if embedding:
                print(f"Text: {text}\nEmbedding (first 5 dims): {embedding[:5]}")
                model_results.append({"text": text, "embedding": embedding})
            else:
                print(f"Failed to get embedding for: {text}")
        results[model] = model_results
    with open("embedding_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to embedding_test_results.json")


if __name__ == "__main__":
    main()
