#!/usr/bin/env python3
"""Summarize load-test results and enforce thresholds."""

from __future__ import annotations

import argparse
import json
import os
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Metrics:
    p95_ms: Optional[float]
    fail_rate: Optional[float]
    req_count: Optional[float]


def parse_summary(path: Path) -> Metrics:
    data = json.loads(path.read_text())
    metrics = data.get("metrics", {})
    duration = metrics.get("http_req_duration", {})
    fails = metrics.get("http_req_failed", {})
    reqs = metrics.get("http_reqs", {})
    p95 = duration.get("percentiles", {}).get("95.0")
    if p95 is None:
        p95 = duration.get("p(95)")
    fail_rate = fails.get("rate")
    if fail_rate is None:
        fail_rate = fails.get("value")
    req_count = reqs.get("count")
    return Metrics(p95, fail_rate, req_count)


def find_latest_summary(directory: Path) -> Path:
    summaries = sorted(directory.glob("load_test_summary_*.json"), key=lambda p: p.stat().st_mtime)
    if not summaries:
        raise FileNotFoundError(f"No load_test_summary_*.json files found in {directory}")
    return summaries[-1]


def send_alert(subject: str, body: str) -> None:
    script = Path(__file__).resolve().parents[1] / "send_email.py"
    if not script.exists():
        print("send_email.py not found; skipping alert", file=sys.stderr)
        return
    subprocess.run([sys.executable, str(script), subject, body], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate latest load test summary against thresholds")
    parser.add_argument("--dir", default="load_test_results", help="Directory containing load_test_summary_*.json")
    parser.add_argument(
        "--p95-threshold",
        type=float,
        default=float(os.getenv("LOAD_TEST_P95_THRESHOLD", "2000")),
        help="P95 latency threshold (ms)",
    )
    parser.add_argument(
        "--fail-threshold",
        type=float,
        default=float(os.getenv("LOAD_TEST_FAIL_THRESHOLD", "0.05")),
        help="Failure rate threshold (0-1)",
    )
    args = parser.parse_args()

    base_dir = Path(args.dir)
    summary_path = find_latest_summary(base_dir)
    metrics = parse_summary(summary_path)

    print(f"Evaluating {summary_path}")
    print(f"  Requests: {metrics.req_count}")
    print(f"  P95 latency: {metrics.p95_ms} ms (threshold {args.p95_threshold} ms)")
    print(f"  Failure rate: {metrics.fail_rate} (threshold {args.fail_threshold})")

    failed = False
    reasons = []
    if metrics.p95_ms is not None and metrics.p95_ms > args.p95_threshold:
        msg = "P95 latency exceeded threshold"
        print(f"⚠️  {msg}", file=sys.stderr)
        failed = True
        reasons.append(msg)
    if metrics.fail_rate is not None and metrics.fail_rate > args.fail_threshold:
        msg = "Failure rate exceeded threshold"
        print(f"⚠️  {msg}", file=sys.stderr)
        failed = True
        reasons.append(msg)

    if failed:
        subject = "Load Test Alert: thresholds exceeded"
        body = f"""Load test summary: {summary_path}
Requests: {metrics.req_count}
P95 latency: {metrics.p95_ms} ms (threshold {args.p95_threshold} ms)
Failure rate: {metrics.fail_rate} (threshold {args.fail_threshold})

Reasons:
- {"; ".join(reasons)}
"""
        send_alert(subject, body)
        return 1

    print("✅ Load test within thresholds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
