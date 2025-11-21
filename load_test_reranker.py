#!/usr/bin/env python3
"""Simple async load tester for the reranker /api/chat endpoint.

Defaults: 30 minute run, low RPS to avoid overloading local Ollama instances.

Usage:
    python load_test_reranker.py --duration 1800 --rps 2 --concurrency 8

Outputs a final summary (requests, success, errors, latency percentiles).
"""
import argparse
import asyncio
import random
import time
from statistics import mean

import httpx

from utils.token_provider import TokenOptions, resolve_bearer_token
QUERIES = [
    "What is FlexNet?",
    "Compare FlexNet and LTE in terms of latency, range, and cost.",
    "Design a comprehensive monitoring and alerting strategy for 50,000 AMI meter endpoints spread across multiple geographic regions. Include error detection mechanisms, performance threshold definitions for different meter types, automated escalation procedures based on severity, integration with existing SCADA systems, redundancy planning, and cost-benefit analysis of different approaches.",
]


class Metrics:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.total = 0
        self.success = 0
        self.errors = 0
        self.latencies = []

    async def add_success(self, latency):
        async with self.lock:
            self.total += 1
            self.success += 1
            self.latencies.append(latency)

    async def add_error(self):
        async with self.lock:
            self.total += 1
            self.errors += 1


async def worker(name, client, url, headers, q, interval, stop_at, metrics: Metrics):
    """Worker that issues a request every `interval` seconds until stop_at timestamp."""
    while time.time() < stop_at:
        payload = {"message": random.choice(q)}
        start = time.time()
        try:
            async with client.stream("POST", url, json=payload, headers=headers, timeout=None) as resp:
                # read stream fully
                body = b""
                async for chunk in resp.aiter_bytes():
                    body += chunk
                latency = time.time() - start
                if resp.status_code == 200:
                    await metrics.add_success(latency)
                else:
                    print(f"[{name}] ERROR: status_code={resp.status_code}, latency={latency:.1f}s")
                    await metrics.add_error()
        except Exception as e:
            print(f"[{name}] EXCEPTION: {type(e).__name__}: {e}")
            await metrics.add_error()
        # sleep until next interval
        await asyncio.sleep(interval)


async def monitor_ollama_health(interval, stop_at):
    async with httpx.AsyncClient() as client:
        while time.time() < stop_at:
            try:
                r = await client.get("http://127.0.0.1:8008/api/ollama-health", timeout=10.0)
                if r.status_code == 200:
                    data = r.json()
                    healthy = data.get("healthy_instances")
                    print(
                        f"[health] {time.strftime('%H:%M:%S')} Ollama healthy instances: {healthy}/{data.get('total_instances')}"
                    )
                else:
                    print(f"[health] {time.strftime('%H:%M:%S')} health check returned {r.status_code}")
            except Exception as e:
                print(f"[health] {time.strftime('%H:%M:%S')} health check error: {e}")
            await asyncio.sleep(interval)


async def run(duration, rps, concurrency):
    url = "http://127.0.0.1:8008/api/chat"
    token = resolve_bearer_token(TokenOptions(email="admin@example.com", role="admin", env_var="LOAD_TEST_BEARER_TOKEN"))
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    metrics = Metrics()
    stop_at = time.time() + duration

    # per-worker interval computed from desired rps
    if rps <= 0:
        raise SystemExit("rps must be > 0")
    interval = concurrency / rps  # seconds between requests per worker

    print(
        f"Starting load test: duration={duration}s, target_rps={rps}, concurrency={concurrency}, interval_per_worker={interval:.2f}s"
    )

    async with httpx.AsyncClient(timeout=300.0) as client:
        # start health monitor
        health_task = asyncio.create_task(monitor_ollama_health(30, stop_at))

        # start workers
        tasks = []
        for i in range(concurrency):
            tasks.append(
                asyncio.create_task(worker(f"w{i+1}", client, url, headers, QUERIES, interval, stop_at, metrics))
            )

        # wait until done
        await asyncio.gather(*tasks, return_exceptions=True)
        health_task.cancel()

    # summarize
    total = metrics.total
    success = metrics.success
    errors = metrics.errors
    latencies = metrics.latencies

    print("\n=== LOAD TEST SUMMARY ===")
    print(f"Total requests: {total}")
    print(f"Success: {success}")
    print(f"Errors: {errors}")
    if latencies:
        lat_ms = [l * 1000 for l in latencies]
        print(f"Avg latency (ms): {mean(lat_ms):.1f}")
        print(f"P50 latency (ms): {sorted(lat_ms)[int(len(lat_ms)*0.5)]:.1f}")
        print(f"P95 latency (ms): {sorted(lat_ms)[int(len(lat_ms)*0.95) -1]:.1f}")
        print(f"Max latency (ms): {max(lat_ms):.1f}")
    else:
        print("No successful requests to report latencies")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=1800, help="Duration in seconds (default 1800 = 30m)")
    parser.add_argument(
        "--rps", type=float, default=2.0, help="Total target requests per second across all workers (default 2)"
    )
    parser.add_argument("--concurrency", type=int, default=8, help="Number of concurrent workers (default 8)")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.duration, args.rps, args.concurrency))
    except KeyboardInterrupt:
        print("Load test interrupted")


if __name__ == "__main__":
    main()
