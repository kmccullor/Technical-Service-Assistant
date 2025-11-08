#!/usr/bin/env python3
"""Collect recent logs from core Docker services for smoke-test failures."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import List

CONTAINERS: List[str] = [
    "reranker",
    "tsa-frontend",
    "pgvector",
    "redis-cache",
    "tsa-nginx",
]
DEFAULT_LINES = 500
DEFAULT_OUTPUT = Path("logs/smoke")


def docker_available() -> bool:
    try:
        subprocess.run(["docker", "ps"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def collect(container: str, lines: int, out_dir: Path) -> None:
    try:
        result = subprocess.run(
            ["docker", "logs", f"--tail={lines}", container], capture_output=True, text=True, check=False
        )
        logfile = out_dir / f"{container}.log"
        logfile.write_text(result.stdout or result.stderr or "")
        print(f"Saved logs for {container} -> {logfile}")
    except Exception as exc:
        print(f"Failed to collect logs for {container}: {exc}", file=sys.stderr)


def main() -> int:
    lines = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LINES
    if not docker_available():
        print("Docker daemon not available; skipping log collection")
        return 0
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = DEFAULT_OUTPUT / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in CONTAINERS:
        collect(name, lines, out_dir)
    print(f"Logs stored under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
