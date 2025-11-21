#!/usr/bin/env python3
"""
Comprehensive Stress Test for Technical Service Assistant
Tests Q&A functionality with varying complexity to exercise all models
"""

import json
import random
import time
from typing import Any, Dict, Tuple

import requests

from utils.token_provider import TokenOptions, resolve_bearer_token
# Comprehensive test questions with varying complexity
COMPREHENSIVE_QA_PAIRS = [
    # SIMPLE/FACTUAL (tests basic retrieval)
    {
        "question": "What is RNI?",
        "expected": "Radio Network Interface - a system for managing AMI networks and devices",
        "complexity": "simple",
        "expected_model": "factual",
    },
    {
        "question": "What does AMI stand for?",
        "expected": "Advanced Metering Infrastructure",
        "complexity": "simple",
        "expected_model": "factual",
    },
    # TECHNICAL (tests technical understanding)
    {
        "question": "How do I configure device managers in RNI?",
        "expected": "Use the Device Manager interfaces for electric, gas, and water meters",
        "complexity": "technical",
        "expected_model": "technical",
    },
    {
        "question": "What security features does RNI provide?",
        "expected": "Base station security, device authentication, encryption management",
        "complexity": "technical",
        "expected_model": "technical",
    },
    # CODE (tests programming capabilities)
    {
        "question": "Write Python code to parse a CSV file",
        "expected": "import csv; with open('file.csv') as f: reader = csv.reader(f)",
        "complexity": "code",
        "expected_model": "code",
    },
    # MATH (tests mathematical reasoning)
    {"question": "Solve: 2x + 3 = 7", "expected": "x = 2", "complexity": "math", "expected_model": "math"},
    # CREATIVE (tests creative writing)
    {
        "question": "Write a short story about a robot learning to paint",
        "expected": "A creative story involving a robot and painting",
        "complexity": "creative",
        "expected_model": "creative",
    },
]


def send_question(question: str) -> Tuple[str, float, Dict]:
    """Send a question and return response, timing, and routing info."""
    url = "http://localhost:8008/api/chat"
    token = resolve_bearer_token(TokenOptions(email="admin@example.com", role="admin", env_var="STRESS_TEST_BEARER_TOKEN"))
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"message": question}

    start_time = time.time()

    # First get routing info
    route_url = "http://localhost:8008/api/intelligent-route"
    route_payload = {"query": question}
    try:
        route_response = requests.post(route_url, json=route_payload, headers=headers, timeout=10)
        routing_info = route_response.json() if route_response.status_code == 200 else {}
    except:
        routing_info = {}

    # Then get the actual response (streaming)
    try:
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        full_response = ""
        for line in response.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "token":
                            full_response += data.get("token", "")
                        elif data.get("type") == "done":
                            break  # Stop when we get the done signal
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        return f"Error: {str(e)}", time.time() - start_time, routing_info

    end_time = time.time()
    return full_response.strip(), end_time - start_time, routing_info


def score_response(response: str, expected: str) -> Dict[str, Any]:
    """Score the response against expected answer."""
    response_lower = response.lower()
    expected_lower = expected.lower()

    expected_words = set(expected_lower.split())
    response_words = set(response_lower.split())

    overlap = len(expected_words.intersection(response_words))
    precision = overlap / len(response_words) if response_words else 0
    recall = overlap / len(expected_words) if expected_words else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    exact_match = response_lower.strip() == expected_lower.strip()

    return {
        "score": f1,
        "precision": precision,
        "recall": recall,
        "exact_match": exact_match,
        "response_length": len(response),
        "expected_length": len(expected),
    }


def run_single_test(qa_pair: Dict) -> Dict:
    """Run a single question test."""
    try:
        response, timing, routing = send_question(qa_pair["question"])
        scores = score_response(response, qa_pair["expected"])

        return {
            "question": qa_pair["question"],
            "expected": qa_pair["expected"],
            "complexity": qa_pair["complexity"],
            "expected_model": qa_pair["expected_model"],
            "response": response,
            "timing": timing,
            "routing": routing,
            "scores": scores,
            "success": True,
        }
    except Exception as e:
        return {
            "question": qa_pair["question"],
            "expected": qa_pair["expected"],
            "complexity": qa_pair["complexity"],
            "expected_model": qa_pair["expected_model"],
            "error": str(e),
            "success": False,
        }


def run_stress_test(num_iterations: int = 3, max_workers: int = 5):
    """Run comprehensive stress test with multiple iterations."""
    print("🚀 Starting Comprehensive Stress Test")
    print(f"Questions: {len(COMPREHENSIVE_QA_PAIRS)}")
    print(f"Iterations: {num_iterations}")
    print(f"Total Tests: {len(COMPREHENSIVE_QA_PAIRS) * num_iterations}")
    print(f"Concurrent Workers: {max_workers}")
    print("=" * 60)

    all_results = []

    for iteration in range(num_iterations):
        print(f"\n📊 Iteration {iteration + 1}/{num_iterations}")
        print("-" * 40)

        # Shuffle questions for each iteration
        test_questions = COMPREHENSIVE_QA_PAIRS.copy()
        random.shuffle(test_questions)

        # Run tests sequentially for debugging
        results = []
        for i, qa in enumerate(test_questions):
            result = run_single_test(qa)
            results.append(result)

            status = "✅" if result.get("success", False) else "❌"
            complexity = result.get("complexity", "unknown")
            timing = result.get("timing", 0) if result.get("success", False) else 0
            print(f"Test {i+1:2d}: {status} {complexity} ({timing:.2f}s)")
        all_results.extend(results)

    # Analysis
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE STRESS TEST RESULTS")
    print("=" * 60)

    successful_tests = [r for r in all_results if r.get("success", False)]
    failed_tests = [r for r in all_results if not r.get("success", False)]

    print(f"Total Tests: {len(all_results)}")
    print(f"Successful: {len(successful_tests)}")
    print(f"Failed: {len(failed_tests)}")

    avg_score = 0.0
    avg_timing = 0.0
    exact_matches = 0

    if successful_tests:
        avg_score = sum(r["scores"]["score"] for r in successful_tests) / len(successful_tests)
        avg_timing = sum(r["timing"] for r in successful_tests) / len(successful_tests)
        exact_matches = sum(1 for r in successful_tests if r["scores"]["exact_match"])

        print(f"Average F1 Score: {avg_score:.3f}")
        print(f"Average Response Time: {avg_timing:.2f}s")
        print(
            f"Exact Matches: {exact_matches}/{len(successful_tests)} ({exact_matches/len(successful_tests)*100:.1f}%)"
        )

        # Performance by complexity
        print("\n🎯 Performance by Complexity:")
        complexities = {}
        for result in successful_tests:
            comp = result.get("complexity", "unknown")
            if comp not in complexities:
                complexities[comp] = []
            complexities[comp].append(result)

        for comp, results in complexities.items():
            sum(r["scores"]["score"] for r in results) / len(results)
            sum(r["timing"] for r in results) / len(results)
            print("15")

        # Model routing analysis
        print("\n🤖 Model Routing Analysis:")
        model_usage = {}
        for result in successful_tests:
            routing = result.get("routing", {})
            model = routing.get("selected_model", "unknown")
            if model not in model_usage:
                model_usage[model] = 0
            model_usage[model] += 1

        for model, count in sorted(model_usage.items(), key=lambda x: x[1], reverse=True):
            print("15")

    # Save detailed results
    with open("comprehensive_stress_test_results.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n📁 Detailed results saved to comprehensive_stress_test_results.json")

    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 30)

    if len(successful_tests) / len(all_results) < 0.95:
        print("❌ Reliability Issues: High failure rate detected")
    else:
        print("✅ Good Reliability: Low failure rate")

    if successful_tests and avg_timing > 1.0:
        print("🐌 Performance Issues: Slow response times")
    else:
        print("✅ Good Performance: Fast response times")

    if successful_tests and avg_score < 0.3:
        print("📚 Content Issues: Low accuracy on retrieved information")
    else:
        print("✅ Good Content: Reasonable accuracy levels")

    print("🎯 Model Distribution: Check that all models are being utilized appropriately")


if __name__ == "__main__":
    run_stress_test(num_iterations=10000, max_workers=4)
