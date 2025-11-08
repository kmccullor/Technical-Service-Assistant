#!/usr/bin/env python3
"""Aggregate latest load-test and accuracy results into a markdown summary."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
LOAD_DIR = REPO_ROOT / "load_test_results"
ACCURACY_DIR = REPO_ROOT / "tests" / "accuracy_logs"
OUTPUT_DIR = REPO_ROOT / "reports"


def latest_file(pattern_dir: Path, pattern: str) -> Optional[Path]:
    files = sorted(pattern_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def load_loadtest_summary(path: Path) -> dict:
    data = json.loads(path.read_text())
    metrics = data.get("metrics", {})
    duration = metrics.get("http_req_duration", {})
    fails = metrics.get("http_req_failed", {})
    return {
        "file": path.name,
        "p95": duration.get("percentiles", {}).get("95.0"),
        "fail_rate": fails.get("rate"),
        "total_requests": metrics.get("http_reqs", {}).get("count"),
    }


def load_accuracy_summary(path: Path) -> dict:
    data = json.loads(path.read_text())
    return {
        "file": path.name,
        "accuracy": data.get("accuracy"),
        "passed": sum(1 for r in data.get("results", []) if r.get("passed")),
        "total": len(data.get("results", [])),
    }


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)

    load_summary_path = latest_file(LOAD_DIR, "load_test_summary_*.json") if LOAD_DIR.exists() else None
    accuracy_summary_path = latest_file(ACCURACY_DIR, "accuracy_results_*.json") if ACCURACY_DIR.exists() else None

    if not load_summary_path and not accuracy_summary_path:
        print("No load test or accuracy summaries found; aborting")
        return 1

    load_summary = load_loadtest_summary(load_summary_path) if load_summary_path else None
    accuracy_summary = load_accuracy_summary(accuracy_summary_path) if accuracy_summary_path else None

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    md = [f"# Nightly QA Summary ({timestamp})", ""]

    if load_summary:
        md.append("## Load Test")
        md.append(f"- File: `{load_summary['file']}`")
        md.append(f"- Total Requests: {load_summary['total_requests']}")
        md.append(f"- P95 Latency: {load_summary['p95']} ms")
        md.append(f"- Failure Rate: {load_summary['fail_rate']}")
        md.append("")
    else:
        md.append("## Load Test\n- _No summary found_\n")

    if accuracy_summary:
        md.append("## Accuracy Evaluation")
        md.append(f"- File: `{accuracy_summary['file']}`")
        md.append(f"- Accuracy: {accuracy_summary['accuracy']}%")
        md.append(f"- Pass/Total: {accuracy_summary['passed']}/{accuracy_summary['total']}")
        md.append("")
    else:
        md.append("## Accuracy Evaluation\n- _No summary found_\n")

    out_path = OUTPUT_DIR / f"nightly_summary_{time.strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text("\n".join(md))
    print(f"Summary written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
