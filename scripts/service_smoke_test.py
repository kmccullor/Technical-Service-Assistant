#!/usr/bin/env python3
"""Comprehensive smoke test to ensure core services are operational."""

from __future__ import annotations

import socket
import sys
from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence

import httpx
import psycopg2

from reranker.cache import get_db_connection


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


HttpTarget = tuple[str, str, int]
TcpTarget = tuple[str, str, int]


HTTP_TARGETS: Sequence[HttpTarget] = (
    ("Reranker API /health", "http://localhost:8008/health", 200),
    ("Auth API /api/auth/health", "http://localhost:8008/api/auth/health", 200),
    ("Ollama aggregation /api/ollama-health", "http://localhost:8008/api/ollama-health", 200),
    ("Frontend (nginx) :80", "http://localhost", 200),
    ("Frontend (app) :8080", "http://localhost:8080", 200),
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
            try:
                resp = client.get(url)
                if resp.status_code != expected:
                    results.append(
                        CheckResult(name=name, passed=False, detail=f"HTTP {resp.status_code} != {expected}")
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


def check_postgres() -> CheckResult:
    try:
        conn = get_db_connection()
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
