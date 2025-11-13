#!/usr/bin/env python3
"""Comprehensive smoke test to ensure core services are operational."""

from __future__ import annotations

import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Union

import httpx
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for env_path in (ROOT / ".env", ROOT.parent / ".env"):
    if env_path.exists():
        load_dotenv(env_path, override=False)
        break

from config import get_settings


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


HttpTarget = tuple[str, str, Union[Sequence[int], int]]
TcpTarget = tuple[str, str, int]

settings = get_settings()


HTTP_TARGETS: Sequence[HttpTarget] = (
    ("Reranker API /health", "http://localhost:8008/health", (200,)),
    ("Auth API /api/auth/health", "http://localhost:8008/api/auth/health", (200,)),
    ("Ollama aggregation /api/ollama-health", "http://localhost:8008/api/ollama-health", (200,)),
    ("Frontend (nginx) :80", "http://localhost", (200, 301, 302)),
)

OLLAMA_PORTS: Sequence[int] = tuple(range(11434, 11442))
TCP_TARGETS: Sequence[TcpTarget] = (
    ("Redis", "localhost", 6379),
    ("Prometheus", "localhost", 9091),
    ("Grafana", "localhost", 3001),
)


def check_http_targets() -> List[CheckResult]:
    results: List[CheckResult] = []
    with httpx.Client(timeout=5.0) as client:
        for name, url, expected in HTTP_TARGETS:
            expected_statuses = set(expected if isinstance(expected, Sequence) else (expected,))
            try:
                resp = client.get(url)
                if resp.status_code not in expected_statuses:
                    results.append(
                        CheckResult(
                            name=name,
                            passed=False,
                            detail=f"HTTP {resp.status_code} not in {sorted(expected_statuses)}",
                        )
                    )
                else:
                    results.append(CheckResult(name=name, passed=True))
            except Exception as exc:  # pragma: no cover - network call
                results.append(CheckResult(name=name, passed=False, detail=str(exc)))

        for port in OLLAMA_PORTS:
            target_name = f"Ollama {port}"
            url = f"http://localhost:{port}/api/tags"
            try:
                resp = client.get(url)
                if resp.status_code == 200:
                    results.append(CheckResult(name=target_name, passed=True))
                else:
                    results.append(CheckResult(name=target_name, passed=False, detail=f"HTTP {resp.status_code}"))
            except Exception as exc:  # pragma: no cover - network call
                results.append(CheckResult(name=target_name, passed=False, detail=str(exc)))
    return results


def check_tcp_targets(targets: Iterable[TcpTarget]) -> List[CheckResult]:
    results: List[CheckResult] = []
    for name, host, port in targets:
        try:
            with socket.create_connection((host, port), timeout=3.0):
                results.append(CheckResult(name=f"{name} TCP {port}", passed=True))
        except Exception as exc:  # pragma: no cover - network call
            results.append(CheckResult(name=f"{name} TCP {port}", passed=False, detail=str(exc)))
    return results


def _postgres_connection_params() -> dict:
    host_candidates = []
    if os.getenv("SMOKE_DB_HOST"):
        host_candidates.append(os.getenv("SMOKE_DB_HOST"))
    if os.getenv("DB_HOST"):
        host_candidates.append(os.getenv("DB_HOST"))
    host_candidates.append(settings.db_host)
    host_candidates.append("localhost")
    return {
        "candidates": host_candidates,
        "port": int(os.getenv("SMOKE_DB_PORT") or os.getenv("DB_PORT", str(settings.db_port))),
        "dbname": os.getenv("SMOKE_DB_NAME") or os.getenv("DB_NAME", settings.db_name),
        "user": os.getenv("SMOKE_DB_USER") or os.getenv("DB_USER", settings.db_user),
        "password": os.getenv("SMOKE_DB_PASSWORD") or os.getenv("DB_PASSWORD", settings.db_password),
    }


def check_postgres() -> CheckResult:
    params = _postgres_connection_params()
    try:
        last_error: str | None = None
        for host in params["candidates"]:
            try:
                conn = psycopg2.connect(
                    dbname=params["dbname"],
                    user=params["user"],
                    password=params["password"],
                    host=host,
                    port=params["port"],
                )
                break
            except psycopg2.Error as exc:
                last_error = str(exc)
                conn = None
        if conn is None:
            raise psycopg2.Error(last_error or "Unable to connect to Postgres")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM conversations")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return CheckResult(name="Postgres vector_db", passed=True, detail=f"{count} conversations")
    except psycopg2.Error as exc:
        return CheckResult(name="Postgres vector_db", passed=False, detail=str(exc))


def summarize(results: Sequence[CheckResult]) -> None:
    print("=== Service Smoke Test ===")
    for result in results:
        icon = "✅" if result.passed else "❌"
        if result.detail:
            print(f"{icon} {result.name}: {result.detail}")
        else:
            print(f"{icon} {result.name}")
    failed = [r for r in results if not r.passed]
    print("\nSummary:")
    print(f"  Passed: {len(results) - len(failed)}")
    print(f"  Failed: {len(failed)}")
    if failed:
        print("  Failing checks:")
        for result in failed:
            print(f"   • {result.name} — {result.detail or 'no detail'}")


def main() -> int:
    results: List[CheckResult] = []
    results.extend(check_http_targets())
    results.extend(check_tcp_targets(TCP_TARGETS))
    results.append(check_postgres())
    summarize(results)
    failed = any(not r.passed for r in results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
