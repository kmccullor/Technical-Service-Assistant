#!/usr/bin/env python3
"""
Distribute models across specialized Ollama containers.
"""

import time

import requests


def remove_model_from_container(host, port, model_name):
    """Remove a model from a container."""
    url = f"http://{host}:{port}/api/delete"
    data = {"name": model_name}

    try:
        response = requests.post(url, json=data, timeout=30)
        if response.status_code == 200:
            print(f"✅ Removed {model_name} from {host}:{port}")
            return True
        else:
            print(f"❌ Failed to remove {model_name} from {host}:{port}")
            return False
    except Exception as e:
        print(f"❌ Error removing {model_name} from {host}:{port}: {e}")
        return False


def pull_model_to_container(host, port, model_name):
    """Pull a model to a specific container."""
    url = f"http://{host}:{port}/api/pull"
    data = {"name": model_name}

    try:
        response = requests.post(url, json=data, timeout=300)
        if response.status_code == 200:
            print(f"✅ Pulled {model_name} to {host}:{port}")
            return True
        else:
            print(f"❌ Failed to pull {model_name} to {host}:{port}")
            return False
    except Exception as e:
        print(f"❌ Error pulling {model_name} to {host}:{port}: {e}")
        return False


def distribute_models():
    """Distribute models across specialized containers."""

    # Define specialized containers
    containers = {
        "thinking": ("localhost", 11435, ["steamdj/llama3.1-cpu-only:8b"]),
        "reasoning": ("localhost", 11436, ["DeepSeek-R1:8B", "DeepSeek-R1:7B"]),
        "tools": ("localhost", 11437, ["codellama:7B", "deepseek-coder:6.7b"]),
        "embedding": ("localhost", 11438, ["nomic-embed-text:v1.5", "nomic-embed-text:v1.5"]),
    }

    # All models to distribute
    all_models = [
        "steamdj/llama3.1-cpu-only:8b",
        "DeepSeek-R1:8B",
        "DeepSeek-R1:7B",
        "codellama:7B",
        "deepseek-coder:6.7b",
        "nomic-embed-text:v1.5",
        "nomic-embed-text:v1.5",
        "mistral:7B",
        "alfred:v1",
    ]

    print("🎯 Distributing models across specialized containers...")

    # First, remove all models from all containers
    print("\n🧹 Cleaning all containers...")
    for container_type, (host, port, models) in containers.items():
        print(f"\nCleaning {container_type} container ({host}:{port})...")
        for model in all_models:
            remove_model_from_container(host, port, model)
            time.sleep(1)

    # Then, distribute models to their specialized containers
    print("\n📦 Distributing models to specialized containers...")
    for container_type, (host, port, models) in containers.items():
        print(f"\nSetting up {container_type} container ({host}:{port})...")
        for model in models:
            pull_model_to_container(host, port, model)
            time.sleep(2)

    print("\n✅ Model distribution complete!")
    print("\n📊 Final Distribution:")
    for container_type, (host, port, models) in containers.items():
        print(f"  {container_type.title()} ({host}:{port}): {len(models)} models")
        for model in models:
            print(f"    - {model}")


if __name__ == "__main__":
    distribute_models()
