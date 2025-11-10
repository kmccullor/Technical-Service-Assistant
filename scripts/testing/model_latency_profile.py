#!/usr/bin/env python3
"""Profile chat endpoint latency across scenario types.

Collects response timings for representative prompts (simple chat, deep thinking,
reasoning, code, and vision) and computes recommended timeout budgets for the K6
load test harness.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)

DEFAULT_TARGET = os.getenv("LOAD_TEST_TARGET_URL", "https://rni-llm-01.lab.sensus.net")
DEFAULT_CHAT_ENDPOINT = "/api/chat"


@dataclass(frozen=True)
class Scenario:
    """Scenario definition for latency probing."""

    key: str
    label: str
    message: str
    display_message: Optional[str] = None


SCENARIOS: Dict[str, Scenario] = {
    "simple_chat": Scenario(
        key="simple_chat",
        label="Simple Chat",
        message="Hi there! Can you summarize what the Technical Service Assistant helps engineers accomplish?",
    ),
    "deep_thinking": Scenario(
        key="deep_thinking",
        label="Deep Thinking",
        message=(
            "Think deeply about rolling out the Technical Service Assistant to multiple regions with limited bandwidth. "
            "List the phases, risks, and mitigations in detail, and explain the reasoning for each recommendation."
        ),
    ),
    "reasoning": Scenario(
        key="reasoning",
        label="Reasoning",
        message=(
            "Explain, step by step, how you would troubleshoot intermittent meter read failures where logs show checksum mismatches. "
            "Describe the reasoning process and call out required diagnostics."
        ),
    ),
    "code": Scenario(
        key="code",
        label="Code",
        message=(
            "Provide a Python function that validates incoming JSON payloads for meter provisioning. "
            "The function should raise ValueError when required fields are missing and include inline comments."
        ),
    ),
    "vision": Scenario(
        key="vision",
        label="Vision",
        message=(
            "Given this diagram description of a telemetry cabinet with a controller, power supply, and two radios, "
            "explain how signals flow between components. Treat it as if you are interpreting a provided diagram or image."
        ),
    ),
}


def prompt_value(text: str, secret: bool = False) -> Optional[str]:
    """Prompt user for input unless stdin is not a TTY."""

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
    """Authenticate against /api/auth/login and return a JWT access token."""

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
            print("TLS verification failed, retrying login without certificate validation...", file=sys.stderr)
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

    token = response.json().get("access_token")
    if not token:
        print(f"Unexpected login response: {response.text}", file=sys.stderr)
    return token


def quantile_95(samples: List[float]) -> Optional[float]:
    """Return the 95th percentile for the provided samples."""

    if not samples:
        return None
    if len(samples) < 20:
        return max(samples)
    return statistics.quantiles(samples, n=20)[18]


class LatencyProbe:
    """Measure chat endpoint latency for predefined scenarios."""

    def __init__(
        self,
        base_url: str,
        chat_endpoint: str,
        api_key: str,
        bearer_token: str,
        samples: int,
        request_timeout: float,
        verify_tls: bool,
        safety_factor: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_endpoint = chat_endpoint if chat_endpoint.startswith("/") else f"/{chat_endpoint}"
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.samples = max(1, samples)
        self.request_timeout = request_timeout
        self.verify_tls = verify_tls
        self.safety_factor = max(1.0, safety_factor)
        self.session = requests.Session()
        if not verify_tls:
            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

    def close(self) -> None:
        """Close the underlying requests session."""

        self.session.close()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _measure_once(self, message: str, display_message: Optional[str]) -> Dict[str, Optional[float]]:
        start = time.perf_counter()
        payload = {
            "conversationId": None,
            "message": message,
            "displayMessage": display_message or message,
        }

        with self.session.post(
            f"{self.base_url}{self.chat_endpoint}",
            json=payload,
            headers=self._headers(),
            stream=True,
            timeout=self.request_timeout,
            verify=self.verify_tls,
        ) as response:
            response.raise_for_status()
            first_token = None
            token_count = 0
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                if not raw_line.startswith("data: "):
                    continue
                data = raw_line[len("data: ") :]
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("type")
                if event_type == "token":
                    token_count += 1
                    if first_token is None:
                        first_token = time.perf_counter() - start
                if event_type == "done":
                    total = time.perf_counter() - start
                    return {
                        "total_seconds": total,
                        "first_token_seconds": first_token,
                        "tokens": token_count,
                    }

        raise RuntimeError("Stream ended before receiving done event")

    def run(self, scenarios: Iterable[Scenario]) -> Dict[str, dict]:
        """Execute latency probes for each scenario."""

        results: Dict[str, dict] = {}
        for scenario in scenarios:
            latencies: List[float] = []
            first_tokens: List[float] = []
            errors: List[str] = []
            tokens: List[int] = []
            print(f"→ Measuring {scenario.label} ({scenario.key})")
            for sample_idx in range(1, self.samples + 1):
                try:
                    measurement = self._measure_once(scenario.message, scenario.display_message)
                    latencies.append(measurement["total_seconds"])  # type: ignore[arg-type]
                    if measurement.get("first_token_seconds") is not None:
                        first_tokens.append(measurement["first_token_seconds"])  # type: ignore[arg-type]
                    tokens.append(int(measurement.get("tokens", 0)))
                    print(
                        f"  Sample {sample_idx}/{self.samples}: {measurement['total_seconds']:.2f}s total, "
                        f"{measurement.get('first_token_seconds') or 0:.2f}s to first token"
                    )
                except requests.RequestException as exc:
                    msg = f"HTTP error: {exc}"
                    errors.append(msg)
                    print(f"  Sample {sample_idx}/{self.samples}: {msg}")
                except RuntimeError as exc:
                    errors.append(str(exc))
                    print(f"  Sample {sample_idx}/{self.samples}: {exc}")

            stats = self._build_stats(latencies)
            first_token_stats = self._build_stats(first_tokens)
            token_stats = self._build_stats(tokens)
            recommended_timeout = self._recommend_timeout(latencies)

            results[scenario.key] = {
                "label": scenario.label,
                "samples": len(latencies),
                "errors": errors,
                "latencies_seconds": latencies,
                "first_token_seconds": first_tokens,
                "token_counts": tokens,
                "stats": stats,
                "first_token_stats": first_token_stats,
                "token_stats": token_stats,
                "recommended_timeout_seconds": recommended_timeout,
            }
        return results

    def _build_stats(self, samples: List[float]) -> Optional[Dict[str, float]]:
        if not samples:
            return None
        data = {
            "min": min(samples),
            "max": max(samples),
            "avg": statistics.mean(samples),
            "median": statistics.median(samples),
        }
        p95 = quantile_95(samples)
        if p95 is not None:
            data["p95"] = p95
        return data

    def _recommend_timeout(self, latencies: List[float]) -> Optional[float]:
        if not latencies:
            return None
        max_latency = max(latencies)
        return round(max_latency * self.safety_factor, 2)


def resolve_headers(args: argparse.Namespace) -> tuple[str, str]:
    api_key = args.api_key or os.getenv("LOAD_TEST_API_KEY") or os.getenv("API_KEY", "")
    bearer_token = args.bearer_token or os.getenv("LOAD_TEST_BEARER_TOKEN", "")

    if not bearer_token:
        username = os.getenv("LOAD_TEST_USERNAME") or prompt_value("LOAD_TEST_USERNAME (email): ")
        password: Optional[str] = None
        if username:
            password = os.getenv("LOAD_TEST_PASSWORD") or prompt_value("LOAD_TEST_PASSWORD: ", secret=True)
        if username and password:
            token = obtain_bearer_token(args.target, username, password, verify_tls=not args.insecure_login)
            if token:
                bearer_token = token
        elif username:
            print("Password required to obtain bearer token", file=sys.stderr)

    return api_key or "", bearer_token or ""


def write_profile(report_dir: Path, data: dict) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = report_dir / f"model_latency_profile_{timestamp}.json"
    out_path.write_text(json.dumps(data, indent=2))
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe model latency across chat scenarios")
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--chat-endpoint", default=DEFAULT_CHAT_ENDPOINT)
    parser.add_argument("--scenarios", nargs="*", default=list(SCENARIOS.keys()))
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--request-timeout", type=float, default=120.0)
    parser.add_argument("--safety-factor", type=float, default=1.5, help="Multiplier when computing timeouts")
    parser.add_argument("--report-dir", default="load_test_results")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--bearer-token", default="")
    parser.add_argument("--insecure", action="store_true", help="Skip TLS verification for probe requests")
    parser.add_argument("--insecure-login", action="store_true", help="Skip TLS verification when fetching JWT")
    args = parser.parse_args()

    scenario_keys = args.scenarios or list(SCENARIOS.keys())
    missing = [key for key in scenario_keys if key not in SCENARIOS]
    if missing:
        print(f"Unknown scenarios: {', '.join(missing)}", file=sys.stderr)
        return 1

    api_key, bearer_token = resolve_headers(args)
    verify_tls = not args.insecure

    probe = LatencyProbe(
        base_url=args.target,
        chat_endpoint=args.chat_endpoint,
        api_key=api_key,
        bearer_token=bearer_token,
        samples=args.samples,
        request_timeout=args.request_timeout,
        verify_tls=verify_tls,
        safety_factor=args.safety_factor,
    )

    try:
        scenario_results = probe.run(SCENARIOS[key] for key in scenario_keys)
    finally:
        probe.close()

    scenario_timeouts = [res.get("recommended_timeout_seconds") for res in scenario_results.values() if res.get("recommended_timeout_seconds")]
    overall_timeout = max(scenario_timeouts) if scenario_timeouts else None

    output = {
        "target": args.target,
        "chat_endpoint": args.chat_endpoint,
        "samples_per_scenario": args.samples,
        "request_timeout_seconds": args.request_timeout,
        "safety_factor": args.safety_factor,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenarios": scenario_results,
        "recommended_load_test_timeout_seconds": overall_timeout,
    }

    report_dir = Path(args.report_dir)
    output_path = write_profile(report_dir, output)

    print(f"📁 Latency profile saved to {output_path}")
    if overall_timeout is not None:
        print(f"Recommended K6 timeout: {overall_timeout:.2f}s")
    else:
        print("Unable to compute recommended timeout (no successful samples)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
