#!/usr/bin/env python3
"""Evaluate chat accuracy against a curated question set."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import List

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


def str_to_bool(value: str) -> bool:
    return value.lower() not in {"0", "false", "no", "off", ""}


def stream_chat_response(url: str, headers: dict, payload: dict, timeout: int = 120, verify: bool = True) -> str:
    response = requests.post(url, json=payload, headers=headers, stream=True, timeout=timeout, verify=verify)
    response.raise_for_status()
    text_parts: List[str] = []
    for line in response.iter_lines():
        if not line:
            continue
        if line.startswith(b"data: "):
            chunk = line[6:]
            if chunk == b"[DONE]":
                break
            try:
                data = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "token":
                text_parts.append(data.get("token", ""))
    if not text_parts:
        # fallback to full body (non-streaming)
        if not response.content:
            return ""
        try:
            body = response.json()
            return body.get("response", "")
        except ValueError:
            return response.text
    return "".join(text_parts)


def evaluate_response(answer: str, required: list[str], optional: list[str], forbidden: list[str]) -> dict:
    answer_lower = answer.lower()
    required_hits = [kw for kw in required if kw.lower() in answer_lower]
    optional_hits = [kw for kw in optional if kw.lower() in answer_lower]
    forbidden_hits = [kw for kw in forbidden if kw.lower() in answer_lower]
    passed = len(required_hits) == len(required) and not forbidden_hits
    score = len(required_hits) / len(required) if required else 1.0
    return {
        "answer": answer,
        "required_hits": required_hits,
        "optional_hits": optional_hits,
        "forbidden_hits": forbidden_hits,
        "passed": passed,
        "score": score,
    }


def main() -> int:
    dataset_path = ROOT / "tests" / "data" / "accuracy_dataset.json"
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        return 1
    dataset = json.loads(dataset_path.read_text())

    base_url = os.getenv("ACCURACY_BASE_URL", os.getenv("PLAYWRIGHT_BASE_URL", "https://rni-llm-01.lab.sensus.net"))
    api_key = os.getenv("ACCURACY_API_KEY", os.getenv("API_KEY", ""))
    bearer_token = os.getenv("ACCURACY_BEARER_TOKEN", "")

    verify_tls = str_to_bool(os.getenv("ACCURACY_VERIFY_TLS", "true"))
    if not verify_tls:
        try:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if api_key:
        headers["X-API-Key"] = api_key
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    results = []
    for test_case in dataset:
        payload = {
            "conversationId": None,
            "message": test_case["question"],
            "displayMessage": test_case["question"],
        }
        try:
            answer = stream_chat_response(f"{base_url}/api/chat", headers, payload, verify=verify_tls)
        except Exception as exc:
            results.append(
                {
                    "id": test_case["id"],
                    "question": test_case["question"],
                    "error": str(exc),
                    "passed": False,
                    "score": 0.0,
                }
            )
            continue
        eval_result = evaluate_response(
            answer,
            test_case.get("required_keywords", []),
            test_case.get("optional_keywords", []),
            test_case.get("forbidden_keywords", []),
        )
        eval_result.update({"id": test_case["id"], "question": test_case["question"]})
        results.append(eval_result)
        status = "✅" if eval_result["passed"] else "❌"
        print(f"{status} {test_case['id']} — score {eval_result['score']:.2f}")

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    accuracy = passed / total * 100 if total else 0

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "tests" / "accuracy_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"accuracy_results_{timestamp}.json"
    out_path.write_text(json.dumps({"results": results, "accuracy": accuracy}, indent=2))
    print(f"Saved evaluation details to {out_path}")
    print(f"Overall accuracy: {accuracy:.1f}% ({passed}/{total})")

    threshold = float(os.getenv("ACCURACY_THRESHOLD", "90"))
    if accuracy < threshold:
        print(f"Accuracy {accuracy:.1f}% below threshold {threshold}%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
