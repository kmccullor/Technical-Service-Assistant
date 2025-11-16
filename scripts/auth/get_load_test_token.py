#!/usr/bin/env python3
"""Fetch a bearer token for load/accuracy tests via /api/auth/login."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = os.getenv("LOAD_TEST_TARGET_URL", os.getenv("APP_URL", "https://rni-llm-01.lab.sensus.net"))


def main() -> int:
    email = os.getenv("LOAD_TEST_USERNAME")
    password = os.getenv("LOAD_TEST_PASSWORD")
    if not email or not password:
        print("LOAD_TEST_USERNAME and LOAD_TEST_PASSWORD env vars are required", file=sys.stderr)
        return 1

    base_url = DEFAULT_BASE.rstrip("/")
    url = f"{base_url}/api/auth/login"
    verify_tls = os.getenv("LOAD_TEST_VERIFY_TLS", "true").lower() not in {"0", "false", "no"}

    try:
        response = requests.post(
            url,
            json={"email": email, "password": password},
            timeout=30,
            verify=verify_tls,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1

    data = response.json()
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if not access:
        print(f"Unexpected response: {json.dumps(data, indent=2)}", file=sys.stderr)
        return 1

    print("export LOAD_TEST_BEARER_TOKEN='" + access + "'")
    if refresh:
        print("export LOAD_TEST_REFRESH_TOKEN='" + refresh + "'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
