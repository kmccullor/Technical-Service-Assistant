#!/usr/bin/env python3
"""K6-based load/stress test harness."""

from __future__ import annotations

import argparse
import getpass
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

DEFAULT_TARGET = os.getenv("LOAD_TEST_TARGET_URL", os.getenv("APP_URL", "https://rni-llm-01.lab.sensus.net"))
DEFAULT_PUBLIC_ENDPOINTS = [
    "/health",
    "/api/ollama-health",
    "/api/auth/health",
]
DEFAULT_CHAT_ENDPOINT = "/api/chat"
DEFAULT_DOC_ENDPOINT = os.getenv("LOAD_TEST_DOC_ENDPOINT", "")
PROFILE_CHOICES = ("steady", "stress", "spike", "soak")
DEFAULT_CHAT_SCENARIOS = [
    {
        "key": "simple_chat",
        "label": "Simple Chat",
        "message": "Hi there! Can you summarize what the Technical Service Assistant helps engineers accomplish?",
        "displayMessage": None,
    },
    {
        "key": "deep_thinking",
        "label": "Deep Thinking",
        "message": (
            "Think deeply about rolling out the Technical Service Assistant to multiple regions with limited bandwidth. "
            "List the phases, risks, and mitigations in detail, and explain the reasoning for each recommendation."
        ),
        "displayMessage": None,
    },
    {
        "key": "reasoning",
        "label": "Reasoning",
        "message": (
            "Explain, step by step, how you would troubleshoot intermittent meter read failures where logs show checksum mismatches. "
            "Describe the reasoning process and call out required diagnostics."
        ),
        "displayMessage": None,
    },
    {
        "key": "code",
        "label": "Coding",
        "message": (
            "Provide a Python function that validates incoming JSON payloads for meter provisioning. "
            "The function should raise ValueError when required fields are missing and include inline comments."
        ),
        "displayMessage": None,
    },
    {
        "key": "vision",
        "label": "Vision",
        "message": (
            "Given this diagram description of a telemetry cabinet with a controller, power supply, and two radios, "
            "explain how signals flow between components. Treat it as if you are interpreting a provided diagram or image."
        ),
        "displayMessage": None,
    },
]
DEFAULT_CHAT_SCENARIO_KEYS = [scenario["key"] for scenario in DEFAULT_CHAT_SCENARIOS]
CHAT_SCENARIO_LOOKUP = {scenario["key"]: scenario for scenario in DEFAULT_CHAT_SCENARIOS}


def build_scenario_options(profile: str, vus: int, duration: str, graceful_stop: str) -> Dict[str, Any]:
    """Return a scenario definition compatible with k6 options.scenarios."""

    safe_vus = max(1, int(vus))
    burst_vus = max(safe_vus, int(round(safe_vus * 1.5)))
    spike_vus = max(safe_vus, int(round(safe_vus * 3)))

    scenario: Dict[str, Any] = {
        "public": {
            "tags": {"profile": profile},
            "gracefulStop": graceful_stop,
        }
    }

    public = scenario["public"]

    if profile == "steady":
        public.update(
            {
                "executor": "constant-vus",
                "vus": safe_vus,
                "duration": duration,
            }
        )
        return scenario

    # Shared defaults for ramping executors
    public.update(
        {
            "executor": "ramping-vus",
            "startVUs": max(1, safe_vus // 3),
        }
    )

    if profile == "stress":
        public["stages"] = [
            {"duration": "2m", "target": max(1, safe_vus // 2)},
            {"duration": duration, "target": safe_vus},
            {"duration": "2m", "target": burst_vus},
            {"duration": "2m", "target": 0},
        ]
    elif profile == "spike":
        public["stages"] = [
            {"duration": "1m", "target": safe_vus},
            {"duration": "1m", "target": spike_vus},
            {"duration": "30s", "target": safe_vus},
            {"duration": "2m", "target": 0},
        ]
    elif profile == "soak":
        public["stages"] = [
            {"duration": "5m", "target": safe_vus},
            {"duration": duration, "target": safe_vus},
            {"duration": "5m", "target": 0},
        ]
    else:
        raise ValueError(f"Unsupported profile: {profile}")

    return scenario


def load_custom_scenarios(path: str) -> Sequence[dict[str, Optional[str]]]:
    scenario_path = Path(path)
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")
    try:
        data = json.loads(scenario_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse scenario file {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"Scenario file {path} must contain a JSON list")
    validated: List[dict[str, Optional[str]]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        key = entry.get("key")
        label = entry.get("label")
        display = entry.get("displayMessage") or entry.get("display")
        if message and key:
            validated.append(
                {
                    "key": key,
                    "label": label or key,
                    "message": message,
                    "displayMessage": display,
                }
            )
    return validated


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
    chat_scenarios: Sequence[dict[str, Optional[str]]],
    profile: str,
    scenario_options: Dict[str, Any],
) -> str:
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    headers_js = json.dumps(headers)
    scenarios_js = json.dumps(list(chat_scenarios))
    scenario_options_js = json.dumps(scenario_options, indent=2)

    return f"""
import http from 'k6/http';
import {{ check, sleep }} from 'k6';
import {{ Counter, Rate, Trend }} from 'k6/metrics';

const SCENARIO_PROFILE = '{profile}';
const SCENARIO_OPTIONS = {scenario_options_js};
const chatLatency = new Trend('chat_latency_ms');
const chatFailureRate = new Rate('chat_failure_rate');
const chatRequests = new Counter('chat_requests_total');
const docLatency = new Trend('doc_upload_latency_ms');
const docFailureRate = new Rate('doc_upload_failure_rate');
const docRequests = new Counter('doc_upload_requests_total');

export const options = {{
  scenarios: SCENARIO_OPTIONS,
  thresholds: {{
    http_req_duration: ['p(95)<2000'],
    http_req_failed: ['rate<0.05'],
    chat_latency_ms: ['p(95)<5000'],
    chat_failure_rate: ['rate<0.10'],
  }},
}};

const BASE_URL = '{target}';
const PUBLIC_ENDPOINTS = {json.dumps(list(public_endpoints))};
const CHAT_ENDPOINT = '{chat_endpoint}';
const DOC_ENDPOINT = '{doc_endpoint}';
const ENABLE_DOC_UPLOAD = DOC_ENDPOINT && DOC_ENDPOINT.length > 0;
const HEADERS = {headers_js};
const CHAT_SCENARIOS = {scenarios_js};

function scenarioForIteration(vu, iteration) {{
  if (!CHAT_SCENARIOS.length) {{
    return null;
  }}
  const index = (vu + iteration) % CHAT_SCENARIOS.length;
  return CHAT_SCENARIOS[index];
}}

function chatPayload(vu, iteration) {{
  const scenario = scenarioForIteration(vu, iteration);
  const baseMessage = scenario ? scenario.message : `Provide a short summary of the Technical Service Assistant. Request #${{vu}}`;
  const baseDisplay = scenario && scenario.displayMessage ? scenario.displayMessage : baseMessage;
  return JSON.stringify({{
    conversationId: null,
    message: baseMessage,
    displayMessage: baseDisplay,
    metadata: {{
      scenarioKey: scenario ? scenario.key : 'default',
      scenarioLabel: scenario ? scenario.label : 'Default',
      scenarioProfile: SCENARIO_PROFILE,
    }},
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
  const iteration = typeof __ITER !== 'undefined' ? __ITER : 0;
  const vu = typeof __VU !== 'undefined' ? __VU : 0;

  for (const endpoint of PUBLIC_ENDPOINTS) {{
    const res = http.get(`${{BASE_URL}}${{endpoint}}`, {{ timeout: '{timeout}', headers: HEADERS }});
    check(res, {{ 'status is 200': (r) => r.status === 200 }});
  }}

  const chatStarted = Date.now();
  const chatRes = http.post(`${{BASE_URL}}${{CHAT_ENDPOINT}}`, chatPayload(vu, iteration), {{
    timeout: '{timeout}',
    headers: {{ ...HEADERS, 'Content-Type': 'application/json', Accept: 'text/event-stream' }},
  }});
  check(chatRes, {{ 'chat 200': (r) => r.status === 200 }});
  const chatDuration = Date.now() - chatStarted;
  chatLatency.add(chatDuration);
  chatFailureRate.add(chatRes.status !== 200);
  chatRequests.add(1);

  if (ENABLE_DOC_UPLOAD) {{
    const doc = docPayload();
    const docStarted = Date.now();
    const docRes = http.post(`${{BASE_URL}}${{DOC_ENDPOINT}}`, doc.body, {{
      headers: {{
        ...HEADERS,
        'Content-Type': `multipart/form-data; boundary=${{doc.boundary}}`
      }},
      timeout: '{timeout}',
    }});
    check(docRes, {{ 'doc 200/202': (r) => r.status === 200 || r.status === 202 }});
    const docDuration = Date.now() - docStarted;
    docLatency.add(docDuration);
    const docFailed = !(docRes.status === 200 || docRes.status === 202);
    docFailureRate.add(docFailed);
    docRequests.add(1);
  }}

  sleep(0.1);
}}
"""


def run_k6(
    script_path: Path,
    summary_path: Path,
    use_docker: bool,
    extra_env: Optional[Dict[str, str]] = None,
    enable_prometheus_rw: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_env:
        env.update({k: v for k, v in extra_env.items() if v})

    if use_docker:
        script_dir = script_path.parent.resolve()
        summary_dir = summary_path.parent.resolve()
        env.setdefault("K6_INSECURE_SKIP_TLS_VERIFY", "true")
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{script_dir}:/scripts",
            "-v",
            f"{summary_dir}:/results",
        ]
        docker_network = env.get("LOAD_TEST_DOCKER_NETWORK")
        if docker_network:
            cmd.extend(["--network", docker_network])
        else:
            cmd.extend(["--add-host", "host.docker.internal:host-gateway"])
        for key in ("K6_INSECURE_SKIP_TLS_VERIFY", "K6_PROMETHEUS_RW_SERVER_URL", "K6_PROMETHEUS_RW_TREND_STATS"):
            if key in env:
                cmd.extend(["-e", f"{key}={env[key]}"])
        cmd.extend(
            [
                "grafana/k6",
                "run",
                "--summary-export",
                f"/results/{summary_path.name}",
            ]
        )
        if enable_prometheus_rw:
            cmd.extend(["--out", "experimental-prometheus-rw"])
        cmd.append(f"/scripts/{script_path.name}")
    else:
        cmd = [
            "k6",
            "run",
            "--quiet",
            "--summary-export",
            str(summary_path),
        ]
        if enable_prometheus_rw:
            cmd.extend(["--out", "experimental-prometheus-rw"])
        cmd.append(str(script_path))
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
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"prometheus_snapshot_{timestamp}.json"
        out_path.write_text(response.text)
        return out_path
    except Exception as exc:
        print(f"Warning: failed to fetch Prometheus snapshot: {exc}")
        return None


def write_report(report_dir: Path, summary: dict) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = report_dir / f"load_test_summary_{timestamp}.json"
    with out_path.open("w") as f:
        json.dump(summary, f, indent=2)
    return out_path


def prompt(text: str, secret: bool = False) -> Optional[str]:
    if not sys.stdin.isatty():
        return None
    return (getpass.getpass(text) if secret else input(text)).strip()


def obtain_bearer_token(
    base_url: str,
    username: str,
    password: str,
    verify_tls: bool = True,
    attempted_insecure: bool = False,
) -> Optional[str]:
    url = f"{base_url.rstrip('/')}/api/auth/login"
    try:
        response = requests.post(
            url,
            json={"email": username, "password": password},
            timeout=30,
            verify=verify_tls,
        )
        response.raise_for_status()
    except requests.exceptions.SSLError as exc:
        if verify_tls and not attempted_insecure:
            print(
                "Login TLS verification failed; retrying without certificate check (use --insecure-login to skip warning).",
                file=sys.stderr,
            )
            return obtain_bearer_token(
                base_url,
                username,
                password,
                verify_tls=False,
                attempted_insecure=True,
            )
        print(f"Login failed: {exc}", file=sys.stderr)
        return None
    except requests.RequestException as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return None
    data = response.json()
    token = data.get("access_token")
    if not token:
        print(f"Unexpected login response: {json.dumps(data, indent=2)}", file=sys.stderr)
    return token


def main() -> int:
    parser = argparse.ArgumentParser(description="Run K6 load test against TSA stack")
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--vus", type=int, default=100)
    parser.add_argument("--duration", default="2m")
    parser.add_argument("--timeout", default="30s")
    parser.add_argument("--public-endpoints", nargs="+", default=DEFAULT_PUBLIC_ENDPOINTS)
    parser.add_argument("--chat-endpoint", default=DEFAULT_CHAT_ENDPOINT)
    parser.add_argument("--doc-endpoint", default=DEFAULT_DOC_ENDPOINT)
    parser.add_argument(
        "--profile", choices=PROFILE_CHOICES, default="steady", help="Load profile for scenario executor"
    )
    parser.add_argument("--graceful-stop", default="30s", help="Graceful stop window applied to k6 scenarios")
    parser.add_argument(
        "--chat-scenarios",
        nargs="+",
        default=DEFAULT_CHAT_SCENARIO_KEYS,
        choices=DEFAULT_CHAT_SCENARIO_KEYS,
        help="Chat scenario keys to cycle through for each request",
    )
    parser.add_argument("--api-key", default=os.getenv("LOAD_TEST_API_KEY", os.getenv("API_KEY", "")))
    parser.add_argument("--bearer-token", default=os.getenv("LOAD_TEST_BEARER_TOKEN", ""))
    parser.add_argument(
        "--mock-auth-email",
        default=os.getenv("LOAD_TEST_MOCK_EMAIL", ""),
        help="Optional email used to generate mock_access_token_<email> bearer tokens (avoids JWT expiry during long tests).",
    )
    parser.add_argument(
        "--scenario-file",
        default=os.getenv("LOAD_TEST_SCENARIO_FILE", ""),
        help="Optional path to a JSON file that defines chat scenarios to replace the defaults.",
    )
    parser.add_argument("--timeout-profile", default="", help="Path to model latency profile JSON")
    parser.add_argument("--report-dir", default="load_test_results")
    parser.add_argument("--prometheus-url", default=os.getenv("LOAD_TEST_PROM_URL", ""))
    parser.add_argument(
        "--prometheus-rw-url",
        default=os.getenv("K6_PROMETHEUS_RW_SERVER_URL", ""),
        help="Enable Prometheus remote write output (sets K6_PROMETHEUS_RW_SERVER_URL and --out experimental-prometheus-rw)",
    )
    parser.add_argument(
        "--prometheus-rw-trend-stats",
        default=os.getenv("K6_PROMETHEUS_RW_TREND_STATS", "p(95),p(99),min,max"),
        help="Comma separated trend stats to export via Prometheus remote write",
    )
    parser.add_argument("--use-docker", action="store_true", help="Run k6 via grafana/k6 Docker image")
    parser.add_argument(
        "--insecure-login", action="store_true", help="Skip TLS verification when prompting for credentials"
    )
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("LOAD_TEST_API_KEY")
    if not api_key:
        prompted = prompt("API key (X-API-Key) [leave blank for none]: ")
        api_key = prompted or ""

    mock_email = args.mock_auth_email

    bearer_token = args.bearer_token or os.getenv("LOAD_TEST_BEARER_TOKEN")
    if not bearer_token and mock_email:
        bearer_token = f"mock_access_token_{mock_email}"
    if not bearer_token:
        username = os.getenv("LOAD_TEST_USERNAME") or prompt("LOAD_TEST_USERNAME (email): ")
        password = os.getenv("LOAD_TEST_PASSWORD") or (
            prompt("LOAD_TEST_PASSWORD: ", secret=True) if username else None
        )
        if username and password:
            bearer_token = obtain_bearer_token(args.target, username, password, verify_tls=not args.insecure_login)
        else:
            print("No bearer token provided; chat/doc uploads may fail", file=sys.stderr)

    timeout_value = args.timeout
    if args.timeout_profile:
        profile_path = Path(args.timeout_profile)
        try:
            profile_data = json.loads(profile_path.read_text())
            recommended = profile_data.get("recommended_load_test_timeout_seconds")
            if recommended:
                timeout_value = f"{math.ceil(float(recommended))}s"
                print(f"Using timeout {timeout_value} derived from {profile_path.name}")
        except Exception as exc:
            print(f"Warning: failed to load timeout profile {profile_path}: {exc}", file=sys.stderr)

    scenario_file = args.scenario_file or os.getenv("LOAD_TEST_SCENARIO_FILE", "")
    if scenario_file:
        try:
            selected_scenarios = list(load_custom_scenarios(scenario_file))
        except Exception as exc:
            print(f"Warning: failed to load custom scenarios from {scenario_file}: {exc}", file=sys.stderr)
            selected_scenarios = [
                CHAT_SCENARIO_LOOKUP[key] for key in (args.chat_scenarios or DEFAULT_CHAT_SCENARIO_KEYS)
            ]
    else:
        selected_scenarios = [CHAT_SCENARIO_LOOKUP[key] for key in (args.chat_scenarios or DEFAULT_CHAT_SCENARIO_KEYS)]
    scenario_options = build_scenario_options(args.profile, args.vus, args.duration, args.graceful_stop)

    script = build_k6_script(
        args.target,
        args.vus,
        args.duration,
        timeout_value,
        args.public_endpoints,
        args.chat_endpoint,
        args.doc_endpoint,
        api_key,
        bearer_token or "",
        selected_scenarios,
        args.profile,
        scenario_options,
    )

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    script_path = report_dir / f"k6_script_{timestamp}.js"
    script_path.write_text(script)
    summary_path = report_dir / f"k6_raw_summary_{timestamp}.json"

    use_docker = args.use_docker or shutil.which("k6") is None
    if use_docker and shutil.which("docker") is None:
        print(
            "Docker is required to run k6 via container. Install docker or provide a native k6 binary.", file=sys.stderr
        )
        return 1

    extra_env: Dict[str, str] = {}
    if args.prometheus_rw_url:
        extra_env["K6_PROMETHEUS_RW_SERVER_URL"] = args.prometheus_rw_url
        if args.prometheus_rw_trend_stats:
            extra_env["K6_PROMETHEUS_RW_TREND_STATS"] = args.prometheus_rw_trend_stats

    enable_prom_rw = bool(args.prometheus_rw_url)

    try:
        result = run_k6(
            script_path,
            summary_path,
            use_docker,
            extra_env=extra_env,
            enable_prometheus_rw=enable_prom_rw,
        )
    finally:
        script_path.unlink(missing_ok=True)

    summary = summarize(summary_path)

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

    if args.prometheus_url:
        snapshot = fetch_prometheus_snapshot(args.prometheus_url, Path(args.report_dir))
        if snapshot:
            print(f"Prometheus snapshot saved to {snapshot}")

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
