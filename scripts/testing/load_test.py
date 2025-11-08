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
from typing import List, Sequence

import requests
import shutil
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

DEFAULT_TARGET = os.getenv("LOAD_TEST_TARGET_URL", "https://rni-llm-01.lab.sensus.net")
DEFAULT_PUBLIC_ENDPOINTS = [
    "/health",
    "/api/ollama-health",
    "/api/auth/health",
]
DEFAULT_CHAT_ENDPOINT = "/api/chat"
DEFAULT_DOC_ENDPOINT = "/api/temp-upload"


def build_k6_script(
    target: str,
    vus: int,
    duration: str,
    timeout: str,
    public_endpoints: Sequence[str],
    chat_endpoint: str,
    doc_endpoint: str,
    api_key: str,
    bearer_token: str,
) -> str:
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    headers_js = json.dumps(headers)

    return f"""
import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
  scenarios: {{
    public: {{
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
const PUBLIC_ENDPOINTS = {json.dumps(list(public_endpoints))};
const CHAT_ENDPOINT = '{chat_endpoint}';
const DOC_ENDPOINT = '{doc_endpoint}';
const HEADERS = {headers_js};

function chatPayload(vu) {{
  return JSON.stringify({{
    conversationId: null,
    message: `Provide a short summary of the Technical Service Assistant. Request #${{vu}}`,
    displayMessage: `Provide a short summary of the Technical Service Assistant. Request #${{vu}}`
  }});
}}

function docPayload() {{
  const boundary = '----k6boundary';
  const body = `--${{boundary}}\r\n` +
    `Content-Disposition: form-data; name="file"; filename="test.txt"\r\n` +
    `Content-Type: text/plain\r\n\r\n` +
    `temporary content\r\n` +
    `--${{boundary}}--\r\n`;
  return {{ body, boundary }};
}}

export default function () {{
  for (const endpoint of PUBLIC_ENDPOINTS) {{
    const res = http.get(`${{BASE_URL}}${{endpoint}}`, {{ timeout: '{timeout}', headers: HEADERS }});
    check(res, {{ 'status is 200': (r) => r.status === 200 }});
  }}

  const chatRes = http.post(`${{BASE_URL}}${{CHAT_ENDPOINT}}`, chatPayload(__VU), {{
    timeout: '{timeout}',
    headers: {{ ...HEADERS, 'Content-Type': 'application/json', Accept: 'text/event-stream' }},
  }});
  check(chatRes, {{ 'chat 200': (r) => r.status === 200 }});

  const doc = docPayload();
  const docRes = http.post(`${{BASE_URL}}${{DOC_ENDPOINT}}`, doc.body, {{
    headers: {{
      ...HEADERS,
      'Content-Type': `multipart/form-data; boundary=${{doc.boundary}}`
    }},
    timeout: '{timeout}',
  }});
  check(docRes, {{ 'doc 200/202': (r) => r.status === 200 || r.status === 202 }});

  sleep(0.1);
}}
"""


def run_k6(script_path: Path, summary_path: Path, use_docker: bool) -> subprocess.CompletedProcess[str]:
    if use_docker:
        script_dir = script_path.parent.resolve()
        summary_dir = summary_path.parent.resolve()
        env = os.environ.copy()
        env.setdefault("K6_INSECURE_SKIP_TLS_VERIFY", "true")
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{script_dir}:/scripts",
            "-v",
            f"{summary_dir}:/results",
            "-e",
            f"K6_INSECURE_SKIP_TLS_VERIFY={env['K6_INSECURE_SKIP_TLS_VERIFY']}",
            "grafana/k6",
            "run",
            "--summary-export",
            f"/results/{summary_path.name}",
            f"/scripts/{script_path.name}",
        ]
    else:
        env = os.environ.copy()
        cmd = [
            "k6",
            "run",
            "--quiet",
            "--summary-export",
            str(summary_path),
            str(script_path),
        ]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def summarize(summary_path: Path) -> dict:
    if not summary_path.exists():
        return {}
    with summary_path.open() as f:
        return json.load(f)


def fetch_prometheus_snapshot(url: str, out_dir: Path) -> Path | None:
    if not url:
        return None
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f'prometheus_snapshot_{timestamp}.json'
        out_path.write_text(response.text)
        return out_path
    except Exception as exc:
        print(f'Warning: failed to fetch Prometheus snapshot: {exc}')
        return None


def write_report(report_dir: Path, summary: dict) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    out_path = report_dir / f'load_test_summary_{timestamp}.json'
    with out_path.open('w') as f:
        json.dump(summary, f, indent=2)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Run K6 load test against TSA stack')
    parser.add_argument('--target', default=DEFAULT_TARGET)
    parser.add_argument('--vus', type=int, default=100)
    parser.add_argument('--duration', default='2m')
    parser.add_argument('--timeout', default='30s')
    parser.add_argument('--public-endpoints', nargs='+', default=DEFAULT_PUBLIC_ENDPOINTS)
    parser.add_argument('--chat-endpoint', default=DEFAULT_CHAT_ENDPOINT)
    parser.add_argument('--doc-endpoint', default=DEFAULT_DOC_ENDPOINT)
    parser.add_argument('--api-key', default=os.getenv('LOAD_TEST_API_KEY', os.getenv('API_KEY', '')))
    parser.add_argument('--bearer-token', default=os.getenv('LOAD_TEST_BEARER_TOKEN', ''))
    parser.add_argument('--report-dir', default='load_test_results')
    parser.add_argument('--prometheus-url', default=os.getenv('LOAD_TEST_PROM_URL', ''))
    parser.add_argument('--use-docker', action='store_true', help='Run k6 via grafana/k6 Docker image')
    args = parser.parse_args()

    script = build_k6_script(
        args.target,
        args.vus,
        args.duration,
        args.timeout,
        args.public_endpoints,
        args.chat_endpoint,
        args.doc_endpoint,
        args.api_key,
        args.bearer_token,
    )

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    script_path = report_dir / f'k6_script_{timestamp}.js'
    script_path.write_text(script)
    summary_path = report_dir / f'k6_raw_summary_{timestamp}.json'

    use_docker = args.use_docker or shutil.which('k6') is None
    if use_docker and shutil.which('docker') is None:
        print('Docker is required to run k6 via container. Install docker or provide a native k6 binary.', file=sys.stderr)
        return 1

    try:
        result = run_k6(script_path, summary_path, use_docker)
    finally:
        script_path.unlink(missing_ok=True)

    summary = summarize(summary_path)

    if summary:
        saved = write_report(Path(args.report_dir), summary)
        print(f'📁 Summary saved to {saved}')
        try:
            metrics = summary.get('metrics', {})
            http_req_duration = metrics.get('http_req_duration', {})
            http_req_failed = metrics.get('http_req_failed', {})
            p95 = http_req_duration.get('percentiles', {}).get('95.0')
            fail_rate = http_req_failed.get('rate')
            if p95 is not None:
                print(f'  P95 latency: {p95:.0f} ms')
            if fail_rate is not None:
                print(f'  Failure rate: {fail_rate * 100:.2f}%')
        except Exception:
            pass

    if args.prometheus_url:
        snapshot = fetch_prometheus_snapshot(args.prometheus_url, Path(args.report_dir))
        if snapshot:
            print(f'Prometheus snapshot saved to {snapshot}')

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
