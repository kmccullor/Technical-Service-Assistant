#!/usr/bin/env python3
"""
Stress test script for Technical Service Assistant
Tests multiple endpoints under concurrent load
"""

import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

import requests

# Test configuration
TARGET_URL = os.getenv("APP_URL", "https://rni-llm-01.lab.sensus.net")
ENDPOINTS = ["/health", "/api/ollama-health", "/api/auth/health"]

CONCURRENT_USERS = 50
REQUESTS_PER_USER = 10
TIMEOUT = 30


class StressTest:
    def __init__(self):
        self.session = requests.Session()
        # Disable SSL verification for self-signed cert
        self.session.verify = False
        # Suppress SSL warnings
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make a single request and return timing data."""
        start_time = time.time()
        try:
            url = f"{TARGET_URL}{endpoint}"
            response = self.session.get(url, timeout=TIMEOUT)
            end_time = time.time()

            return {
                "endpoint": endpoint,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200,
                "error": None,
            }
        except Exception as e:
            end_time = time.time()
            return {
                "endpoint": endpoint,
                "status_code": None,
                "response_time": end_time - start_time,
                "success": False,
                "error": str(e),
            }

    def run_user_simulation(self, user_id: int) -> List[Dict[str, Any]]:
        """Simulate a single user's requests."""
        results = []
        for _ in range(REQUESTS_PER_USER):
            for endpoint in ENDPOINTS:
                result = self.make_request(endpoint)
                result["user_id"] = user_id
                results.append(result)
                # Small delay between requests
                time.sleep(0.1)
        return results

    def run_stress_test(self) -> Dict[str, Any]:
        """Run the full stress test."""
        print(f"🚀 Starting stress test: {CONCURRENT_USERS} users, {REQUESTS_PER_USER} requests each")
        print(f"Target: {TARGET_URL}")
        print(f"Endpoints: {', '.join(ENDPOINTS)}")
        print("-" * 60)

        start_time = time.time()

        # Run concurrent users
        with ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
            futures = [executor.submit(self.run_user_simulation, i) for i in range(CONCURRENT_USERS)]
            all_results = []
            for future in futures:
                all_results.extend(future.result())

        total_time = time.time() - start_time

        # Analyze results
        analysis = self.analyze_results(all_results, total_time)

        return {
            "config": {
                "target_url": TARGET_URL,
                "endpoints": ENDPOINTS,
                "concurrent_users": CONCURRENT_USERS,
                "requests_per_user": REQUESTS_PER_USER,
                "total_requests": len(all_results),
                "total_time": total_time,
            },
            "results": all_results,
            "analysis": analysis,
        }

    def analyze_results(self, results: List[Dict[str, Any]], total_time: float) -> Dict[str, Any]:
        """Analyze the test results."""
        if not results:
            return {"error": "No results to analyze"}

        # Group by endpoint
        endpoint_stats = {}
        for endpoint in ENDPOINTS:
            endpoint_results = [r for r in results if r["endpoint"] == endpoint]

            if not endpoint_results:
                continue

            response_times = [r["response_time"] for r in endpoint_results]
            success_count = sum(1 for r in endpoint_results if r["success"])
            total_count = len(endpoint_results)

            endpoint_stats[endpoint] = {
                "total_requests": total_count,
                "successful_requests": success_count,
                "success_rate": success_count / total_count * 100,
                "avg_response_time": statistics.mean(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "median_response_time": statistics.median(response_times),
                "p95_response_time": statistics.quantiles(response_times, n=20)[18]
                if len(response_times) >= 20
                else max(response_times),
                "errors": [r["error"] for r in endpoint_results if r["error"]],
            }

        # Overall stats
        all_response_times = [r["response_time"] for r in results]
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r["success"])

        overall_stats = {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate": successful_requests / total_requests * 100,
            "requests_per_second": total_requests / total_time,
            "avg_response_time": statistics.mean(all_response_times),
            "min_response_time": min(all_response_times),
            "max_response_time": max(all_response_times),
            "median_response_time": statistics.median(all_response_times),
            "p95_response_time": statistics.quantiles(all_response_times, n=20)[18]
            if len(all_response_times) >= 20
            else max(all_response_times),
            "total_errors": total_requests - successful_requests,
        }

        return {"overall": overall_stats, "by_endpoint": endpoint_stats}


def main():
    tester = StressTest()
    results = tester.run_stress_test()

    # Print summary
    print("\n📊 STRESS TEST RESULTS")
    print("=" * 60)
    config = results["config"]
    analysis = results["analysis"]

    print(f"Configuration:")
    print(f"  Target: {config['target_url']}")
    print(f"  Concurrent Users: {config['concurrent_users']}")
    print(f"  Requests per User: {config['requests_per_user']}")
    print(f"  Total Requests: {config['total_requests']}")
    print(".2f")
    print()

    overall = analysis["overall"]
    print(f"Overall Performance:")
    print(f"  Success Rate: {overall['success_rate']:.1f}%")
    print(f"  Requests/sec: {overall['requests_per_second']:.1f}")
    print(f"  Avg Response Time: {overall['avg_response_time']:.3f}s")
    print(f"  Median Response Time: {overall['median_response_time']:.3f}s")
    print(f"  P95 Response Time: {overall['p95_response_time']:.3f}s")
    print(f"  Total Errors: {overall['total_errors']}")
    print()

    print("By Endpoint:")
    for endpoint, stats in analysis["by_endpoint"].items():
        print(f"  {endpoint}:")
        print(f"    Success Rate: {stats['success_rate']:.1f}%")
        print(f"    Avg Response Time: {stats['avg_response_time']:.3f}s")
        if stats["errors"]:
            unique_errors = list(set(stats["errors"][:3]))  # Show up to 3 unique errors
            print(f"    Sample Errors: {', '.join(unique_errors)}")
    print()

    # Save detailed results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"stress_test_results_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"📁 Detailed results saved to {filename}")

    # Performance assessment
    print("🎯 Performance Assessment:")
    if overall["success_rate"] >= 99:
        print("  ✅ Excellent: High success rate")
    elif overall["success_rate"] >= 95:
        print("  ⚠️ Good: Acceptable success rate")
    else:
        print("  ❌ Poor: High error rate")

    if overall["avg_response_time"] < 1.0:
        print("  ✅ Fast: Good average response time")
    elif overall["avg_response_time"] < 5.0:
        print("  ⚠️ Moderate: Acceptable response time")
    else:
        print("  ❌ Slow: Poor response time")

    if overall["requests_per_second"] > 100:
        print("  ✅ High Throughput: Good requests per second")
    elif overall["requests_per_second"] > 50:
        print("  ⚠️ Moderate Throughput: Acceptable throughput")
    else:
        print("  ❌ Low Throughput: Poor throughput")


if __name__ == "__main__":
    main()
