#!/usr/bin/env python3
"""
Simple metrics monitoring dashboard for the Technical Service Assistant.
Displays key performance metrics from the Prometheus metrics endpoint.
"""

import os
import time
from datetime import datetime
from typing import Dict, List

import requests


class MetricsDashboard:
    def __init__(self, metrics_url: str | None = None):
        # Allow remote override via RERANKER_URL env var; append /metrics if not provided explicitly
        base = metrics_url or os.getenv("RERANKER_URL", "http://localhost:8008")
        if base.endswith("/metrics"):
            self.metrics_url = base
        else:
            self.metrics_url = f"{base.rstrip('/')}/metrics"

    def fetch_metrics(self) -> Dict[str, List[str]]:
        """Fetch and parse metrics from the endpoint."""
        try:
            response = requests.get(self.metrics_url, timeout=5)
            response.raise_for_status()

            metrics = {}
            current_help = ""
            current_type = ""

            for line in response.text.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    if line.startswith("# HELP"):
                        current_help = line.replace("# HELP ", "")
                    elif line.startswith("# TYPE"):
                        current_type = line.replace("# TYPE ", "")
                    continue

                # Parse metric line
                if " " in line:
                    metric_part, value = line.rsplit(" ", 1)
                    metric_name = metric_part.split("{")[0]

                    if metric_name not in metrics:
                        metrics[metric_name] = []
                    metrics[metric_name].append(line)

            return metrics
        except Exception as e:
            print(f"Error fetching metrics: {e}")
            return {}

    def display_specialized_model_performance(self, metrics: Dict[str, List[str]]):
        """Display specialized model performance metrics."""
        print("🎯 SPECIALIZED MODEL PERFORMANCE")
        print("=" * 50)

        # Model requests
        if "model_requests_total" in metrics:
            print("\n📊 Model Request Counts:")
            for line in metrics["model_requests_total"]:
                if "success" in line and not line.startswith("#"):
                    # Parse the line to extract model, instance, question type
                    parts = line.split("{")[1].split("}")[0]
                    value = line.split(" ")[-1]

                    # Extract key info
                    info = {}
                    for part in parts.split(","):
                        key, val = part.split("=")
                        info[key] = val.strip('"')

                    print(
                        f"  • {info.get('model_name', 'unknown')} ({info.get('question_type', 'unknown')}) "
                        f"on {info.get('instance', 'unknown')}: {value.strip()} requests"
                    )

        # Request duration
        if "model_request_duration_seconds_sum" in metrics:
            print("\n⏱️  Model Response Times:")
            for line in metrics["model_request_duration_seconds_sum"]:
                if not line.startswith("#"):
                    parts = line.split("{")[1].split("}")[0]
                    value = float(line.split(" ")[-1])

                    info = {}
                    for part in parts.split(","):
                        key, val = part.split("=")
                        info[key] = val.strip('"')

                    print(f"  • {info.get('model_name', 'unknown')}: {value:.3f}s total")

    def display_instance_health(self, metrics: Dict[str, List[str]]):
        """Display Ollama instance health status."""
        print("\n🏥 OLLAMA INSTANCE HEALTH")
        print("=" * 50)

        if "ollama_instance_health_status" in metrics:
            for line in metrics["ollama_instance_health_status"]:
                if not line.startswith("#"):
                    parts = line.split("{")[1].split("}")[0]
                    value = float(line.split(" ")[-1])

                    info = {}
                    for part in parts.split(","):
                        key, val = part.split("=")
                        info[key] = val.strip('"')

                    status = "🟢 HEALTHY" if value == 1.0 else "🔴 UNHEALTHY"
                    instance = info.get("instance_name", "unknown").replace("ollama-server-", "")
                    print(f"  • Instance {instance}: {status}")

    def display_system_resources(self, metrics: Dict[str, List[str]]):
        """Display system resource utilization."""
        print("\n💻 SYSTEM RESOURCES")
        print("=" * 50)

        # Memory usage
        if "system_memory_usage_percent" in metrics:
            for line in metrics["system_memory_usage_percent"]:
                if not line.startswith("#"):
                    value = float(line.split(" ")[-1])
                    print(f"  • Memory Usage: {value:.1f}%")

        # CPU usage
        if "system_cpu_usage_percent" in metrics:
            for line in metrics["system_cpu_usage_percent"]:
                if not line.startswith("#"):
                    value = float(line.split(" ")[-1])
                    print(f"  • CPU Usage: {value:.1f}%")

    def display_api_performance(self, metrics: Dict[str, List[str]]):
        """Display API endpoint performance."""
        print("\n🌐 API PERFORMANCE")
        print("=" * 50)

        if "api_request_duration_seconds_sum" in metrics:
            endpoint_totals = {}
            endpoint_counts = {}

            # Sum up durations per endpoint
            for line in metrics.get("api_request_duration_seconds_sum", []):
                if not line.startswith("#"):
                    parts = line.split("{")[1].split("}")[0]
                    value = float(line.split(" ")[-1])

                    info = {}
                    for part in parts.split(","):
                        key, val = part.split("=")
                        info[key] = val.strip('"')

                    endpoint = info.get("endpoint", "unknown")
                    endpoint_totals[endpoint] = endpoint_totals.get(endpoint, 0) + value

            # Get counts
            for line in metrics.get("api_request_duration_seconds_count", []):
                if not line.startswith("#"):
                    parts = line.split("{")[1].split("}")[0]
                    value = float(line.split(" ")[-1])

                    info = {}
                    for part in parts.split(","):
                        key, val = part.split("=")
                        info[key] = val.strip('"')

                    endpoint = info.get("endpoint", "unknown")
                    endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + value

            # Calculate averages
            print("\n📈 Average Response Times:")
            for endpoint in endpoint_totals:
                if endpoint in endpoint_counts and endpoint_counts[endpoint] > 0:
                    avg_time = endpoint_totals[endpoint] / endpoint_counts[endpoint]
                    count = int(endpoint_counts[endpoint])
                    print(f"  • {endpoint}: {avg_time:.3f}s avg ({count} requests)")

    def run_dashboard(self, refresh_interval: int = 10):
        """Run the dashboard with periodic updates."""
        print("🚀 Technical Service Assistant - Monitoring Dashboard")
        print(f"⏰ Refreshing every {refresh_interval} seconds (Ctrl+C to exit)")
        print("=" * 70)

        try:
            while True:
                # Clear screen (works on most terminals)
                print("\n" * 50)
                print(f"📊 METRICS DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 70)

                metrics = self.fetch_metrics()
                if metrics:
                    self.display_specialized_model_performance(metrics)
                    self.display_instance_health(metrics)
                    self.display_system_resources(metrics)
                    self.display_api_performance(metrics)
                else:
                    print("❌ Unable to fetch metrics")

                print(f"\n⏰ Next update in {refresh_interval} seconds... (Ctrl+C to exit)")
                time.sleep(refresh_interval)

        except KeyboardInterrupt:
            print("\n👋 Dashboard stopped")


if __name__ == "__main__":
    dashboard = MetricsDashboard()
    dashboard.run_dashboard(refresh_interval=5)
