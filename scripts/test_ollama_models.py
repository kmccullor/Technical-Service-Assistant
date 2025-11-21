"""Smoke-test Ollama models across one or more instances.

For each resolved base URL, fetches `/api/tags` and sends a short generation
request to every model to validate basic functionality. Responses are truncated
for readability.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests

# Optional config import for backwards compatibility; script still works without it.
try:  # pragma: no cover - best-effort import
    from config import get_settings
except Exception:
    get_settings = None  # type: ignore


def _default_instances() -> List[str]:
    # Host-mapped ports from docker-compose.yml (ollama-server-1..8)
    return [f"http://localhost:{port}" for port in range(11434, 11442)]


def _resolve_instances(cli_value: Optional[str]) -> List[str]:
    # CLI override
    if cli_value:
        return [entry.strip() for entry in cli_value.split(",") if entry.strip()]

    # Environment-supplied list
    env_instances = os.getenv("OLLAMA_INSTANCES")
    if env_instances:
        parsed = [entry.strip() for entry in env_instances.split(",") if entry.strip()]
        if parsed:
            return parsed

    # Single env base URL
    env_single = os.getenv("OLLAMA_URL")
    if env_single:
        return [env_single.rstrip("/")]

    # Config fallback
    if get_settings is not None:
        try:
            settings = get_settings()
            base = settings.ollama_url
            if base:
                return [base.rstrip("/")]
        except Exception:
            pass

    # Final fallback: mapped docker ports
    return _default_instances()


def fetch_models(base_url: str, timeout_s: int) -> List[str]:
    response = requests.get(f"{base_url}/api/tags", timeout=timeout_s)
    response.raise_for_status()
    data = response.json()
    models = data.get("models") or []
    return [entry.get("name") for entry in models if entry.get("name")]


def _is_embedding_model(model: str) -> bool:
    lowered = model.lower()
    return any(key in lowered for key in ["embed", "minilm", "embedding", "nomi"])


def _test_embedding_model(base_url: str, model: str, timeout_s: int) -> Tuple[str, bool, str]:
    payload = {
        "model": model,
        "prompt": "Generate an embedding for the phrase: renewable energy adoption rose 15 percent last year.",
    }
    try:
        response = requests.post(
            f"{base_url}/api/embeddings",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        length = len(embedding) if isinstance(embedding, list) else 0
        return model, True, f"embedding length={length}"
    except Exception as exc:
        return model, False, str(exc)


def test_model(base_url: str, model: str, prompt: str, timeout_s: int) -> Tuple[str, bool, str]:
    if _is_embedding_model(model):
        return _test_embedding_model(base_url, model, timeout_s)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }
    try:
        response = requests.post(
            f"{base_url}/api/generate",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        output = (data.get("response") or "").strip()
        return model, True, output[:200]
    except Exception as exc:  # pragma: no cover - defensive logging only
        return model, False, str(exc)


def run(prompt: str, instance_list: Optional[str], timeout_s: int) -> int:
    bases = _resolve_instances(instance_list)
    if not bases:
        print("[ERROR] No Ollama instances resolved.")
        return 1

    overall_failed: List[Tuple[str, str, str]] = []

    for base_url in bases:
        print(f"\n[INFO] Using Ollama base URL: {base_url}")
        try:
            models = fetch_models(base_url, timeout_s)
        except Exception as exc:
            print(f"[ERROR] Failed to fetch models: {exc}")
            overall_failed.append((base_url, "<fetch>", str(exc)))
            continue

        if not models:
            print("[WARN] No models returned from /api/tags")
            overall_failed.append((base_url, "<none>", "No models reported"))
            continue

        print(f"[INFO] Testing {len(models)} models on {base_url} ...")
        failed: List[Tuple[str, str]] = []
        for model in models:
            name, ok, snippet = test_model(base_url, model, prompt, timeout_s)
            status = "OK" if ok else "FAIL"
            print(f"[{status}] {name}: {snippet}")
            if not ok:
                failed.append((name, snippet))

        if failed:
            overall_failed.extend([(base_url, name, msg) for name, msg in failed])
            print("[WARN] One or more models failed on this instance.")
        else:
            print("[INFO] All models responded successfully on this instance.")

    if overall_failed:
        print("\n[SUMMARY] Failures:")
        for base, name, msg in overall_failed:
            print(f" - {base} :: {name} -> {msg}")
        return 1

    print("\n[SUMMARY] All instances responded successfully.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke-test all Ollama instances/models.")
    parser.add_argument(
        "--instances",
        help="Comma separated list of base URLs (e.g., http://localhost:11434,http://localhost:11435). "
        "Defaults to OLLAMA_INSTANCES, then OLLAMA_URL, then docker-mapped ports 11434-11441.",
    )
    parser.add_argument(
        "--prompt",
        default="Deliver one factual sentence about renewable energy adoption with a percentage.",
        help="Prompt to send to each model.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-request timeout in seconds for model listing and generation (default: 120s).",
    )
    args = parser.parse_args()
    sys.exit(run(args.prompt, args.instances, args.timeout))
