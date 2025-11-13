#!/usr/bin/env python3
"""
Comprehensive Q&A Load Test for Reranker Pipeline
Tests different complexity levels with realistic knowledge-base queries.

This script:
1. Uses knowledge-base Q&A from the technical documentation
2. Distributes queries across complexity levels (SIMPLE, MODERATE, COMPLEX, VERY_COMPLEX)
3. Tests model routing and decomposition pipeline
4. Collects detailed metrics on latency, success rate, model usage
5. Tracks errors and edge cases

Usage:
    python qa_load_test.py --duration 1800 --rps 3 --concurrency 6 --complexity-mix 40,40,15,5

Output:
    Detailed summary with per-complexity metrics, model usage, and latency percentiles
"""

import argparse
import asyncio
import json
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Optional

import httpx

# ============================================================================
# Knowledge Base Q&A Dataset (Complexity-Tiered)
# ============================================================================

SIMPLE_QUERIES = [
    "What is FlexNet?",
    "What does RNI stand for?",
    "What is an AMI meter?",
    "What is SCADA?",
    "What is the Sensus system?",
    "What is a communications protocol?",
    "What is message format?",
    "What is a network interface?",
    "What is data transmission?",
    "What is a meter endpoint?",
]

MODERATE_QUERIES = [
    "Compare FlexNet and LTE in terms of latency, range, and cost.",
    "Describe the RNI 4.16 integration process.",
    "How does Multispeak v3.0 relate to RNI?",
    "What are the key features of AMI systems?",
    "Explain the difference between FlexNet and cellular networks.",
    "What are the main components of an AMI infrastructure?",
    "How does message routing work in Sensus systems?",
    "What is the role of a reranker in RAG pipelines?",
    "How does semantic chunking improve retrieval?",
    "What are confidence thresholds in hybrid search?",
]

COMPLEX_QUERIES = [
    "Design a comprehensive monitoring and alerting strategy for 50,000 AMI meter endpoints spread across multiple geographic regions. Include error detection mechanisms, performance threshold definitions for different meter types, automated escalation procedures based on severity, integration with existing SCADA systems, redundancy planning, and cost-benefit analysis of different approaches.",
    "Explain how the FlexNet communications protocol handles message fragmentation, reassembly, and error recovery in high-latency environments. Include discussion of retry mechanisms, timeout handling, and performance implications for real-time metering data.",
    "Design a system architecture for integrating legacy SCADA systems with modern AMI infrastructure. Address protocol translation, data consistency, failover mechanisms, and security considerations.",
    "Analyze the trade-offs between deploying FlexNet versus cellular-based AMI solutions in rural areas. Consider coverage, cost, scalability, maintenance, and performance metrics.",
    "Create a detailed data pipeline architecture for processing, validating, and storing meter readings from 100,000+ endpoints. Include deduplication, anomaly detection, and compliance with regulatory standards.",
]

VERY_COMPLEX_QUERIES = [
    "Develop a machine learning-based anomaly detection system for AMI meter data that can identify meter tampering, data transmission errors, and infrastructure faults. Include model architecture, training methodology, feature engineering strategies, false-positive mitigation, and real-time inference requirements. Address how this integrates with the existing hybrid search and decomposition pipeline, and how confidence thresholds would be applied to model predictions.",
    "Design a multi-layer security architecture for a distributed AMI system serving 250,000+ meter endpoints across 5+ geographic regions. Address authentication, encryption, intrusion detection, regulatory compliance (NERC CIP, GDPR), secure key management, incident response, and audit logging. Explain how this architecture would interact with the existing decomposition and intelligent routing system.",
    "Propose a comprehensive business continuity and disaster recovery plan for a critical AMI infrastructure supporting essential services. Include RTO/RPO targets, failover mechanisms, data replication strategies, backup systems, testing procedures, and cost optimization. How would this impact the routing and model selection strategy in the reranker?",
]


@dataclass
class QueryMetrics:
    """Metrics for a single query."""

    query: str
    complexity: str
    status_code: int
    latency: float
    tokens_generated: Optional[int] = None
    model_selected: Optional[str] = None
    decomposition_used: bool = False
    error: Optional[str] = None

    def to_dict(self):
        return {
            "complexity": self.complexity,
            "status_code": self.status_code,
            "latency_ms": self.latency * 1000,
            "tokens": self.tokens_generated,
            "model": self.model_selected,
            "decomposition": self.decomposition_used,
            "error": self.error,
        }


@dataclass
class LoadTestMetrics:
    """Aggregated metrics for the entire load test."""

    total: int = 0
    success: int = 0
    errors: int = 0
    latencies: list = field(default_factory=list)
    by_complexity: dict = field(
        default_factory=lambda: defaultdict(lambda: {"count": 0, "success": 0, "errors": 0, "latencies": []})
    )
    by_model: dict = field(default_factory=lambda: defaultdict(lambda: {"count": 0, "success": 0, "latencies": []}))
    decompositions: int = 0
    query_details: list = field(default_factory=list)

    async def add_result(self, metrics: QueryMetrics):
        async with asyncio.Lock():
            self.total += 1
            self.latencies.append(metrics.latency)
            self.query_details.append(metrics.to_dict())

            complexity = metrics.complexity
            self.by_complexity[complexity]["count"] += 1
            self.by_complexity[complexity]["latencies"].append(metrics.latency)

            if metrics.status_code == 200:
                self.success += 1
                self.by_complexity[complexity]["success"] += 1
                if metrics.model_selected:
                    self.by_model[metrics.model_selected]["count"] += 1
                    self.by_model[metrics.model_selected]["latencies"].append(metrics.latency)
                    self.by_model[metrics.model_selected]["success"] += 1
            else:
                self.errors += 1
                self.by_complexity[complexity]["errors"] += 1

            if metrics.decomposition_used:
                self.decompositions += 1


async def worker(
    name: str,
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    queries_by_complexity: dict,
    complexity_weights: dict,
    interval: float,
    stop_at: float,
    metrics: LoadTestMetrics,
):
    """Worker that issues queries with specified complexity distribution."""
    while time.time() < stop_at:
        # Select complexity based on weights
        complexity = random.choices(list(complexity_weights.keys()), weights=list(complexity_weights.values()), k=1)[0]

        query = random.choice(queries_by_complexity[complexity])
        payload = {"message": query}
        start = time.time()

        try:
            async with client.stream("POST", url, json=payload, headers=headers, timeout=None) as resp:
                body = b""
                decomposition_used = False
                model_selected = None

                async for chunk in resp.aiter_bytes():
                    body += chunk

                latency = time.time() - start

                # Parse response metadata (if available in streaming response)
                try:
                    # Try to extract model from response (simple heuristic)
                    if b"selected_model" in body or b"model_selected" in body:
                        model_selected = "router_selected"
                    if b"decomposition" in body or b"sub_question" in body:
                        decomposition_used = True
                except:
                    pass

                query_metrics = QueryMetrics(
                    query=query[:100],  # Truncate for logging
                    complexity=complexity,
                    status_code=resp.status_code,
                    latency=latency,
                    model_selected=model_selected or "unknown",
                    decomposition_used=decomposition_used,
                )

                if resp.status_code != 200:
                    query_metrics.error = f"HTTP {resp.status_code}"

                await metrics.add_result(query_metrics)

        except asyncio.TimeoutError:
            latency = time.time() - start
            query_metrics = QueryMetrics(
                query=query[:100],
                complexity=complexity,
                status_code=408,
                latency=latency,
                error="Timeout",
            )
            await metrics.add_result(query_metrics)
        except Exception as e:
            latency = time.time() - start
            query_metrics = QueryMetrics(
                query=query[:100],
                complexity=complexity,
                status_code=0,
                latency=latency,
                error=f"{type(e).__name__}: {str(e)[:50]}",
            )
            await metrics.add_result(query_metrics)

        # Sleep until next interval
        await asyncio.sleep(interval)


async def monitor_health(client: httpx.AsyncClient, interval: int, stop_at: float):
    """Monitor Ollama health status."""
    while time.time() < stop_at:
        try:
            r = await client.get("http://127.0.0.1:8008/api/ollama-health", timeout=10.0)
            if r.status_code == 200:
                data = r.json()
                healthy = data.get("healthy_instances", 0)
                total = data.get("total_instances", 8)
                print(f"[health] {time.strftime('%H:%M:%S')} Ollama healthy: {healthy}/{total}")
        except Exception as e:
            print(f"[health] {time.strftime('%H:%M:%S')} Health check failed: {type(e).__name__}")

        await asyncio.sleep(interval)


def print_metrics_summary(metrics: LoadTestMetrics):
    """Print comprehensive metrics summary."""
    print("\n" + "=" * 80)
    print("LOAD TEST SUMMARY - Comprehensive Q&A with Complexity Levels")
    print("=" * 80)

    # Overall metrics
    print(f"\nOVERALL METRICS:")
    print(f"  Total requests: {metrics.total}")
    print(f"  Successful: {metrics.success} ({metrics.success/metrics.total*100:.1f}%)")
    print(f"  Errors: {metrics.errors} ({metrics.errors/metrics.total*100:.1f}%)")
    print(f"  Decompositions used: {metrics.decompositions}")

    # Latency metrics
    if metrics.latencies:
        lat_ms = [l * 1000 for l in metrics.latencies]
        lat_sorted = sorted(lat_ms)
        print(f"\nLATENCY METRICS (milliseconds):")
        print(f"  Min: {min(lat_ms):.1f} ms")
        print(f"  Avg: {mean(lat_ms):.1f} ms")
        print(f"  Median: {median(lat_ms):.1f} ms")
        print(f"  P95: {lat_sorted[int(len(lat_sorted)*0.95)]:.1f} ms")
        print(f"  P99: {lat_sorted[int(len(lat_sorted)*0.99)-1]:.1f} ms")
        print(f"  Max: {max(lat_ms):.1f} ms")

    # By complexity
    print(f"\nMETRICS BY COMPLEXITY:")
    for complexity in ["SIMPLE", "MODERATE", "COMPLEX", "VERY_COMPLEX"]:
        if complexity in metrics.by_complexity:
            stats = metrics.by_complexity[complexity]
            success_rate = stats["success"] / stats["count"] * 100 if stats["count"] > 0 else 0
            avg_latency = mean(stats["latencies"]) * 1000 if stats["latencies"] else 0
            print(f"\n  {complexity}:")
            print(f"    Count: {stats['count']}")
            print(f"    Success: {stats['success']} ({success_rate:.1f}%)")
            print(f"    Errors: {stats['errors']}")
            if stats["latencies"]:
                lat_sorted = sorted([l * 1000 for l in stats["latencies"]])
                print(f"    Avg latency: {avg_latency:.1f} ms")
                print(f"    P95 latency: {lat_sorted[int(len(lat_sorted)*0.95)]:.1f} ms")

    # By model (if tracked)
    if metrics.by_model:
        print(f"\nMETRICS BY MODEL:")
        for model, stats in sorted(metrics.by_model.items()):
            success_rate = stats["success"] / stats["count"] * 100 if stats["count"] > 0 else 0
            avg_latency = mean(stats["latencies"]) * 1000 if stats["latencies"] else 0
            print(f"\n  {model}:")
            print(f"    Count: {stats['count']}")
            print(f"    Success: {stats['success']} ({success_rate:.1f}%)")
            print(f"    Avg latency: {avg_latency:.1f} ms")

    print("\n" + "=" * 80)


async def run(duration: int, rps: float, concurrency: int, complexity_mix: str):
    """Run the comprehensive load test."""
    url = "http://127.0.0.1:8008/api/chat"
    headers = {
        "Authorization": "Bearer mock_access_token_admin@example.com",
        "Content-Type": "application/json",
    }

    # Parse complexity distribution
    mix_parts = [int(x) for x in complexity_mix.split(",")]
    total_mix = sum(mix_parts)
    complexity_weights = {
        "SIMPLE": mix_parts[0] / total_mix,
        "MODERATE": mix_parts[1] / total_mix if len(mix_parts) > 1 else 0,
        "COMPLEX": mix_parts[2] / total_mix if len(mix_parts) > 2 else 0,
        "VERY_COMPLEX": mix_parts[3] / total_mix if len(mix_parts) > 3 else 0,
    }
    # Remove zero weights
    complexity_weights = {k: v for k, v in complexity_weights.items() if v > 0}

    queries_by_complexity = {
        "SIMPLE": SIMPLE_QUERIES,
        "MODERATE": MODERATE_QUERIES,
        "COMPLEX": COMPLEX_QUERIES,
        "VERY_COMPLEX": VERY_COMPLEX_QUERIES,
    }

    metrics = LoadTestMetrics()
    stop_at = time.time() + duration

    if rps <= 0:
        raise SystemExit("rps must be > 0")
    interval = concurrency / rps

    print(f"Starting Q&A Load Test")
    print(f"  Duration: {duration}s ({duration/60:.1f} minutes)")
    print(f"  Target RPS: {rps}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Per-worker interval: {interval:.2f}s")
    print(
        f"  Complexity mix: SIMPLE={complexity_weights.get('SIMPLE', 0)*100:.0f}%, "
        f"MODERATE={complexity_weights.get('MODERATE', 0)*100:.0f}%, "
        f"COMPLEX={complexity_weights.get('COMPLEX', 0)*100:.0f}%, "
        f"VERY_COMPLEX={complexity_weights.get('VERY_COMPLEX', 0)*100:.0f}%"
    )
    print()

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Start health monitor
        health_task = asyncio.create_task(monitor_health(client, 30, stop_at))

        # Start workers
        tasks = []
        for i in range(concurrency):
            tasks.append(
                asyncio.create_task(
                    worker(
                        f"w{i+1}",
                        client,
                        url,
                        headers,
                        queries_by_complexity,
                        complexity_weights,
                        interval,
                        stop_at,
                        metrics,
                    )
                )
            )

        # Wait until done
        await asyncio.gather(*tasks, return_exceptions=True)
        health_task.cancel()

    # Print summary
    print_metrics_summary(metrics)

    # Save detailed results
    results_file = f"qa_load_test_results_{int(time.time())}.json"
    with open(results_file, "w") as f:
        json.dump(
            {
                "summary": {
                    "total": metrics.total,
                    "success": metrics.success,
                    "errors": metrics.errors,
                    "decompositions": metrics.decompositions,
                },
                "by_complexity": dict(metrics.by_complexity),
                "by_model": dict(metrics.by_model),
            },
            f,
            indent=2,
        )
    print(f"\nDetailed results saved to: {results_file}")


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Q&A load test with complexity levels")
    parser.add_argument(
        "--duration",
        type=int,
        default=1800,
        help="Duration in seconds (default 1800 = 30 minutes)",
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=2.0,
        help="Total target requests per second (default 2)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Number of concurrent workers (default 8)",
    )
    parser.add_argument(
        "--complexity-mix",
        type=str,
        default="40,40,15,5",
        help="Percentage mix for SIMPLE,MODERATE,COMPLEX,VERY_COMPLEX (default 40,40,15,5)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args.duration, args.rps, args.concurrency, args.complexity_mix))
    except KeyboardInterrupt:
        print("\nLoad test interrupted by user")


if __name__ == "__main__":
    main()
