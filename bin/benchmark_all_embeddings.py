#!/usr/bin/env python3
"""
Automate download and benchmarking of all available Ollama embedding models.
- Checks if model is downloaded (ollama list)
- Downloads if missing (ollama pull <model>)
- Runs embedding_model_test.py for each model
- Logs results to embedding_model_test_results.md
"""
import json
import os
import subprocess
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(program_name="benchmark_embeddings", log_level="INFO", console_output=True)

# List of embedding models from Ollama library (expand as needed)
EMBEDDING_MODELS = [
    "nomic-embed-text:v1.5",
    "mxbai-embed-large:v1",
    "bge-m3:567m",
    "all-minilm:l6-v2",
    "snowflake-arctic-embed:m",
    "paraphrase-multilingual:mpnet-base-v2",
    "bge-large:en-v1.5",
    "granite-embedding:30m-english",
]

OLLAMA_LIST_CMD = ["docker", "exec", "ollama", "ollama", "list"]
OLLAMA_PULL_CMD = ["docker", "exec", "ollama", "ollama", "pull"]
PYTHON = sys.executable or "python3"
TEST_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "embedding_model_test.py")
RESULTS_JSON = os.path.join(os.path.dirname(__file__), "..", "embedding_test_results.json")
RESULTS_MD = os.path.join(os.path.dirname(__file__), "..", "embedding_model_test_results.md")


def get_downloaded_models():
    try:
        result = subprocess.run(OLLAMA_LIST_CMD, capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        models = [line.split()[0] for line in lines if line.strip() and not line.startswith("NAME")]  # skip header
        return set(models)
    except Exception as e:
        print(f"Error running ollama list: {e}")
        return set()


def pull_model(model):
    print(f"Pulling model: {model}")
    try:
        subprocess.run(OLLAMA_PULL_CMD + [model], check=True)
        print(f"Downloaded: {model}")
    except Exception as e:
        print(f"Failed to download {model}: {e}")


def run_benchmark(model):
    print(f"Benchmarking model: {model}")
    try:
        subprocess.run([PYTHON, TEST_SCRIPT, model], check=True)
    except Exception as e:
        print(f"Benchmark failed for {model}: {e}")


def update_docs(all_results):
    # Write combined results to JSON
    try:
        with open(RESULTS_JSON, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"All results saved to {RESULTS_JSON}")
    except Exception as e:
        print(f"Could not write combined JSON: {e}")

    # Overwrite and regenerate the markdown summary
    try:
        with open(RESULTS_MD, "w") as md:
            md.write("# Embedding Model Benchmark Results\n")
            for model, results in all_results.items():
                md.write(f"\n### {model}\n")
                if results:
                    for entry in results:
                        md.write(f"- Text: `{entry['text']}`\n")
                        md.write(f"  - Embedding (first 5 dims): `{entry['embedding'][:5]}`\n")
                else:
                    md.write("- No results generated for this model.\n")
        print(f"Results summary updated in {RESULTS_MD}")
    except Exception as e:
        print(f"Could not write results to markdown file: {e}")


def main():
    downloaded = get_downloaded_models()
    all_results = {}
    for model in EMBEDDING_MODELS:
        if model not in downloaded:
            pull_model(model)
        run_benchmark(model)
        try:
            with open(RESULTS_JSON) as f:
                single_model_result = json.load(f)
                all_results.update(single_model_result)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Could not read results for {model}. Error: {e}")

    update_docs(all_results)


if __name__ == "__main__":
    main()
