#!/usr/bin/env python3
"""K6-based load/stress test harness."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

DEFAULT_TARGET = os.getenv("LOAD_TEST_TARGET_URL", "https://rni-llm-01.lab.sensus.net")
DEFAULT_ENDPOINTS = [
    "/health",
    "/api/ollama-health",
    "/api/auth/health",
    "/api/chat",
]


def build_k6_script(target: str, endpoints: List[str], vus: int, duration: str, timeout: str) -> str:
    return f"""
import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
  scenarios: {{
    constant: {{
      executor: 'constant-vus',
      vus: {vus},
      duration: '{duration}',
    }},
  }},
  thresholds: {{
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.05'],
  }},
}};

const BASE_URL = '{target}';
const ENDPOINTS = {json.dumps(endpoints)};

export default function () {{
  for (const endpoint of ENDPOINTS) {{
    const res = http.get(`${{BASE_URL}}${{endpoint}}`, {{ timeout: '{timeout}' }});
    check(res, {{
      'status is 200': (r) => r.status === 200,
    }});
  }}
  sleep(0.1);
}}
"""


def run_k6(script_path: Path, summary_path: Path) -> subprocess.CompletedProcess[str]:
    cmd = [
        "k6",
        "run",
        "--quiet",
        "--summary-export",
        str(summary_path),
        str(script_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def summarize(summary_path: Path) -> dict:
    if not summary_path.exists():
        return {}
    with summary_path.open() as f:
        return json.load(f)


def write_report(report_dir: Path, summary: dict) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = report_dir / f"load_test_summary_{timestamp}.json"
    with out_path.open("w") as f:
        json.dump(summary, f, indent=2)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run K6 load test against TSA stack")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="Base URL for requests")
    parser.add_argument("--endpoints", nargs="+", default=DEFAULT_ENDPOINTS, help="Endpoints to hit")
    parser.add_argument("--vus", type=int, default=100, help="Concurrent virtual users")
    parser.add_argument("--duration", default="2m", help="Test duration (e.g. 1m, 5m)")
    parser.add_argument("--timeout", default="30s", help="Per-request timeout")
    parser.add_argument("--report-dir", default="load_test_results", help="Directory for summary output")
    args = parser.parse_args()

    k6_script = build_k6_script(args.target, args.endpoints, args.vus, args.duration, args.timeout)

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".js") as tmp:
        tmp.write(k6_script)
        script_path = Path(tmp.name)

    summary_path = Path(tempfile.mktemp(suffix=".json"))

    try:
        result = run_k6(script_path, summary_path)
    finally:
        script_path.unlink(missing_ok=True)

    summary = summarize(summary_path)
    summary_path.unlink(missing_ok=True)

    if summary:
        saved = write_report(Path(args.report_dir), summary)
        print(f"📁 Summary saved to {saved}")
        try:
            metrics = summary.get("metrics", {})
            http_req_duration = metrics.get("http_req_duration", {})
            http_req_failed = metrics.get("http_req_failed", {})
            p95 = http_req_duration.get("percentiles", {}).get("95.0")
            fail_rate = http_req_failed.get("rate")
            if p95 is not None:
                print(f"  P95 latency: {p95:.0f} ms")
            if fail_rate is not None:
                print(f"  Failure rate: {fail_rate * 100:.2f}%")
        except Exception:
            pass

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
