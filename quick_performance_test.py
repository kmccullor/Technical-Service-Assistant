#!/usr/bin/env python3
"""
Quick performance test for Technical Service Assistant improvements
"""

import json
import statistics
import time
from typing import Any, Dict

import requests


def test_routing_performance(num_tests: int = 10) -> Dict[str, Any]:
    """Test intelligent routing performance."""
    print(f"Testing routing performance with {num_tests} requests...")

    url = "http://localhost:8008/api/intelligent-route"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer mock_access_token_admin@example.com"}

    test_questions = [
        "What is RNI?",
        "How do I configure device managers?",
        "Write Python code to parse CSV",
        "Solve: 2x + 3 = 7",
    ]

    results = []
    start_time = time.time()

    for i in range(num_tests):
        question = test_questions[i % len(test_questions)]
        payload = {"query": question}

        req_start = time.time()
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            req_end = time.time()

            if response.status_code == 200:
                result = response.json()
                results.append(
                    {
                        "success": True,
                        "response_time": req_end - req_start,
                        "question": question,
                        "model": result.get("selected_model"),
                        "question_type": result.get("question_type"),
                    }
                )
            else:
                results.append(
                    {"success": False, "response_time": req_end - req_start, "error": f"HTTP {response.status_code}"}
                )
        except Exception as e:
            req_end = time.time()
            results.append({"success": False, "response_time": req_end - req_start, "error": str(e)})

    total_time = time.time() - start_time

    successful = [r for r in results if r["success"]]
    response_times = [r["response_time"] for r in results]

    return {
        "total_requests": num_tests,
        "successful_requests": len(successful),
        "success_rate": len(successful) / num_tests * 100,
        "total_time": total_time,
        "requests_per_second": num_tests / total_time,
        "avg_response_time": statistics.mean(response_times) if response_times else 0,
        "min_response_time": min(response_times) if response_times else 0,
        "max_response_time": max(response_times) if response_times else 0,
        "results": results,
    }


def test_chat_simple_performance(num_tests: int = 5) -> Dict[str, Any]:
    """Test simple chat performance."""
    print(f"Testing chat performance with {num_tests} requests...")

    url = "http://localhost:8008/api/chat"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer mock_access_token_admin@example.com"}

    results = []
    start_time = time.time()

    for i in range(num_tests):
        payload = {"message": "What is RNI?"}

        req_start = time.time()
        try:
            response = requests.post(url, json=payload, headers=headers, stream=True, timeout=10)

            if response.status_code == 200:
                # Just check if we get a response, don't wait for full stream
                content_length = len(response.content)
                req_end = time.time()

                results.append(
                    {"success": True, "response_time": req_end - req_start, "content_length": content_length}
                )
            else:
                req_end = time.time()
                results.append(
                    {"success": False, "response_time": req_end - req_start, "error": f"HTTP {response.status_code}"}
                )
        except Exception as e:
            req_end = time.time()
            results.append({"success": False, "response_time": req_end - req_start, "error": str(e)})

    total_time = time.time() - start_time

    successful = [r for r in results if r["success"]]
    response_times = [r["response_time"] for r in results]

    return {
        "total_requests": num_tests,
        "successful_requests": len(successful),
        "success_rate": len(successful) / num_tests * 100,
        "total_time": total_time,
        "requests_per_second": num_tests / total_time,
        "avg_response_time": statistics.mean(response_times) if response_times else 0,
        "min_response_time": min(response_times) if response_times else 0,
        "max_response_time": max(response_times) if response_times else 0,
        "results": results,
    }


def main():
    print("🚀 Quick Performance Test for Technical Service Assistant")
    print("=" * 60)

    # Test routing performance
    routing_results = test_routing_performance(20)

    print("\n📊 Routing Performance Results:")
    print(f"  Total Requests: {routing_results['total_requests']}")
    print(f"  Success Rate: {routing_results['success_rate']:.1f}%")
    print(f"  Requests/sec: {routing_results['requests_per_second']:.2f}")
    print(f"  Avg Response Time: {routing_results['avg_response_time']:.3f}s")
    print(f"  Min Response Time: {routing_results['min_response_time']:.3f}s")
    print(f"  Max Response Time: {routing_results['max_response_time']:.3f}s")

    # Test chat performance
    chat_results = test_chat_simple_performance(10)

    print("\n📊 Chat Performance Results:")
    print(f"  Total Requests: {chat_results['total_requests']}")
    print(f"  Success Rate: {chat_results['success_rate']:.1f}%")
    print(f"  Requests/sec: {chat_results['requests_per_second']:.2f}")
    print(f"  Avg Response Time: {chat_results['avg_response_time']:.3f}s")
    print(f"  Min Response Time: {chat_results['min_response_time']:.3f}s")
    print(f"  Max Response Time: {chat_results['max_response_time']:.3f}s")

    # Overall assessment
    print("\n🎯 Performance Assessment:")
    if routing_results["success_rate"] >= 95:
        print("  ✅ Excellent routing reliability")
    elif routing_results["success_rate"] >= 80:
        print("  ⚠️ Good routing reliability")
    else:
        print("  ❌ Poor routing reliability")

    if routing_results["avg_response_time"] < 0.5:
        print("  ✅ Fast routing responses")
    elif routing_results["avg_response_time"] < 2.0:
        print("  ⚠️ Moderate routing speed")
    else:
        print("  ❌ Slow routing responses")

    if chat_results["success_rate"] >= 90:
        print("  ✅ Good chat reliability")
    else:
        print("  ❌ Poor chat reliability")

    if chat_results["avg_response_time"] < 5.0:
        print("  ✅ Reasonable chat response times")
    else:
        print("  ❌ Slow chat responses")

    print("\n📁 Detailed results saved to quick_performance_test.json")

    # Save results
    with open("quick_performance_test.json", "w") as f:
        json.dump(
            {"routing": routing_results, "chat": chat_results, "timestamp": time.time()}, f, indent=2, default=str
        )


if __name__ == "__main__":
    main()
