#!/usr/bin/env python3
"""
Test script to verify all models are working on all Ollama instances.
"""

import sys

import requests

# Model configurations
MODELS = {
    "embedding": "nomic-embed-text:v1.5",
    "chat": "mistral:7b",
    "coding": "codellama:7b",
    "reasoning": "llama3.2:3b",
    "vision": "llava:7b",
}

# Ollama servers
SERVERS = [f"http://localhost:{11434 + i}" for i in range(8)]


def test_model(server_base_url, model, model_type, prompt="Hello, test message"):
    """Test a model on a specific server."""
    try:
        if model_type == "embedding":
            url = f"{server_base_url}/api/embeddings"
            payload = {"model": model, "prompt": prompt}
        else:
            url = f"{server_base_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 10},  # Short response for testing
            }

        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if model_type == "embedding":
                # Check if embeddings are returned
                if "embedding" in data:
                    return True, "Embeddings generated"
                else:
                    return False, "No embeddings in response"
            else:
                return True, data.get("response", "").strip()
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)


def main():
    print("Testing all models on all Ollama instances...")
    print("=" * 60)

    results = {}

    for server_idx, server_base_url in enumerate(SERVERS):
        server_name = f"Server {server_idx + 1}"
        print(f"\n🖥️  {server_name} ({server_base_url})")
        print("-" * 40)

        server_results = {}
        for model_type, model_name in MODELS.items():
            print(f"Testing {model_type} model ({model_name})...", end=" ")
            sys.stdout.flush()

            success, result = test_model(server_base_url, model_name, model_type)
            if success:
                print("✅ PASS")
                server_results[model_type] = "PASS"
            else:
                print(f"❌ FAIL: {result}")
                server_results[model_type] = f"FAIL: {result}"

        results[server_name] = server_results

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_pass = True
    for server, tests in results.items():
        print(f"\n{server}:")
        for model_type, status in tests.items():
            print(f"  {model_type}: {status}")
            if not status.startswith("PASS"):
                all_pass = False

    print("\n" + "=" * 60)
    if all_pass:
        print("🎉 ALL TESTS PASSED! All models are working on all servers.")
    else:
        print("⚠️  SOME TESTS FAILED. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
