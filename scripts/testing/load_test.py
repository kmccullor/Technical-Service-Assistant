#!/usr/bin/env python3
"""K6-based load/stress test harness."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

harness = {
    "vus": 100,
    "duration": "2m",
    "endpoints": ["/health", "/api/ollama-health", "/api/auth/health"],
    "target": "https://rni-llm-01.lab.sensus.net",
}


def run_k6(script_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["k6", "run", str(script_path)], capture_output=True, text=True)


def main() -> int:
    k6_script = """
import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';

export const options = {
  scenarios: {
    constant: {
      executor: 'constant-vus',
      vus: %(vus)d,
      duration: '%(duration)s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.05'],
  },
};

const BASE_URL = '%(target)s';
const ENDPOINTS = %(endpoints)s;

export default function () {
  for (const endpoint of ENDPOINTS) {
    const res = http.get(`${BASE_URL}${endpoint}`, { timeout: '30s' });
    check(res, {
      'status is 200': (r) => r.status === 200,
    });
  }
}
""" % harness

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".js") as tmp:
        tmp.write(k6_script)
        tmp_path = Path(tmp.name)

    try:
        result = run_k6(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
