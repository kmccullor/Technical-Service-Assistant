#!/usr/bin/env python3
"""
Migrate models from backup to consolidated Ollama containers.
"""

import json
import time
from pathlib import Path

import requests


def pull_model_to_container(host, port, model_name):
    """Pull a model to a specific container."""
    url = f"http://{host}:{port}/api/pull"
    data = {"name": model_name}

    print(f"Pulling {model_name} to {host}:{port}...")

    try:
        response = requests.post(url, json=data, timeout=300)
        if response.status_code == 200:
            print(f"✅ Successfully pulled {model_name} to {host}:{port}")
            return True
        else:
            print(f"❌ Failed to pull {model_name} to {host}:{port} (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error pulling {model_name} to {host}:{port}: {e}")
        return False


def migrate_models():
    """Migrate models from backup to new containers."""
    # Load backup data
    backup_file = Path("/home/kmccullor/Projects/ollama_benchmark_results/model_backup.json")

    if not backup_file.exists():
        print("❌ Backup file not found!")
        return

    with open(backup_file, "r") as f:
        backup_data = json.load(f)

    models_to_migrate = backup_data["all_models"]
    print(f"📋 Models to migrate: {len(models_to_migrate)}")
    for model in models_to_migrate:
        print(f"  - {model}")

    # Benchmark containers (ports 11435-11438)
    benchmark_containers = [
        ("localhost", 11435, "ollama-benchmark-1"),
        ("localhost", 11436, "ollama-benchmark-2"),
        ("localhost", 11437, "ollama-benchmark-3"),
        ("localhost", 11438, "ollama-benchmark-4"),
    ]

    print(f"\n🚀 Starting migration to {len(benchmark_containers)} containers...")

    successful_migrations = 0
    total_attempts = len(models_to_migrate) * len(benchmark_containers)

    for model in models_to_migrate:
        for host, port, container_name in benchmark_containers:
            if pull_model_to_container(host, port, model):
                successful_migrations += 1
            time.sleep(2)  # Small delay between pulls

    print(f"\n📊 Migration Summary:")
    print(f"  Total attempts: {total_attempts}")
    print(f"  Successful: {successful_migrations}")
    print(f"  Failed: {total_attempts - successful_migrations}")
    print(f"  Success rate: {successful_migrations/total_attempts*100:.1f}%")


if __name__ == "__main__":
    migrate_models()
