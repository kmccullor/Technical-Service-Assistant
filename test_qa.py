#!/usr/bin/env python3
"""
Test Q&A pairs against the Technical Service Assistant API
"""

import json
import time
from typing import Dict, Tuple

import requests

# Test Q&A pairs based on RNI documentation in archive/
QA_PAIRS = [
    {
        "question": "What is RNI?",
        "expected": "Radio Network Interface - a system for managing AMI (Advanced Metering Infrastructure) networks and devices",
    },
    {
        "question": "How do I install RNI 4.10?",
        "expected": "Follow the installation guide which includes prerequisites, system requirements, and step-by-step installation procedures",
    },
    {
        "question": "What security features does RNI provide?",
        "expected": "Base station security, device authentication, encryption management, hardware security modules, and user access controls",
    },
    {
        "question": "How do I configure device managers in RNI?",
        "expected": "Use the Device Manager interfaces for electric, gas, and water meters with specific configuration settings for each device type",
    },
    {
        "question": "What is MultiSpeak integration?",
        "expected": "A standard protocol for utility system integration supporting meter reading, outage detection, connect/disconnect operations, and demand response",
    },
    {
        "question": "How do I troubleshoot API connectivity issues?",
        "expected": "Check API troubleshooting guide for common issues, verify endpoint configurations, and use diagnostic tools",
    },
    {
        "question": "What are the key features of RNI 4.12?",
        "expected": "Enhanced encryption management, improved device manager interfaces, updated MultiSpeak support, and security enhancements",
    },
    {
        "question": "How do I set up Active Directory integration?",
        "expected": "Configure Microsoft Active Directory integration guide for user authentication and authorization",
    },
]


def send_question(question: str) -> Tuple[str, float]:
    """Send a question to the API and return response and timing."""
    url = "http://localhost:8008/api/chat"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer mock_access_token_admin@example.com"}
    payload = {"message": question}

    start_time = time.time()
    response = requests.post(url, json=payload, headers=headers, stream=True)
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
                except json.JSONDecodeError:
                    continue

    end_time = time.time()
    return full_response.strip(), end_time - start_time


def score_response(response: str, expected: str) -> Dict:
    """Score the response against expected answer."""
    response_lower = response.lower()
    expected_lower = expected.lower()

    # Simple scoring based on keyword matching
    expected_words = set(expected_lower.split())
    response_words = set(response_lower.split())

    overlap = len(expected_words.intersection(response_words))
    precision = overlap / len(response_words) if response_words else 0
    recall = overlap / len(expected_words) if expected_words else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # Exact match bonus
    exact_match = response_lower.strip() == expected_lower.strip()

    return {
        "score": f1,
        "precision": precision,
        "recall": recall,
        "exact_match": exact_match,
        "response_length": len(response),
        "expected_length": len(expected),
    }


def main():
    print("🧪 Testing Q&A Pairs Against Technical Service Assistant")
    print("=" * 60)

    results = []

    for i, qa in enumerate(QA_PAIRS, 1):
        print(f"\n📋 Question {i}: {qa['question']}")
        print(f"Expected: {qa['expected'][:100]}{'...' if len(qa['expected']) > 100 else ''}")

        try:
            response, timing = send_question(qa["question"])
            scores = score_response(response, qa["expected"])

            print(f"Timing: {timing:.2f}s")
            print(f"Response: {response[:200]}{'...' if len(response) > 200 else ''}")
            print(f"F1 Score: {scores['score']:.3f} (P: {scores['precision']:.3f}, R: {scores['recall']:.3f})")
            print(f"Exact Match: {'✅' if scores['exact_match'] else '❌'}")

            results.append(
                {
                    "question": qa["question"],
                    "expected": qa["expected"],
                    "response": response,
                    "timing": timing,
                    "scores": scores,
                }
            )

        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({"question": qa["question"], "expected": qa["expected"], "error": str(e)})

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    successful_tests = [r for r in results if "error" not in r]
    avg_score = sum(r["scores"]["score"] for r in successful_tests) / len(successful_tests) if successful_tests else 0
    avg_timing = sum(r["timing"] for r in successful_tests) / len(successful_tests) if successful_tests else 0
    exact_matches = sum(1 for r in successful_tests if r["scores"]["exact_match"])

    print(f"Total Tests: {len(results)}")
    print(f"Successful: {len(successful_tests)}")
    print(f"Failed: {len(results) - len(successful_tests)}")
    print(".3f")
    print(".2f")
    print(f"Exact Matches: {exact_matches}/{len(successful_tests)} ({exact_matches/len(successful_tests)*100:.1f}%)")

    # Save detailed results
    with open("qa_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n📁 Detailed results saved to qa_test_results.json")

    # Recommendations
    print("\n💡 RECOMMENDATIONS FOR IMPROVEMENT")
    print("-" * 40)

    if avg_score < 0.5:
        print("❌ Low accuracy - Consider improving document ingestion and chunking")
    elif avg_score < 0.7:
        print("⚠️ Moderate accuracy - Fine-tune embeddings and retrieval parameters")
    else:
        print("✅ Good accuracy - Focus on edge cases and complex queries")

    if avg_timing > 30:
        print("🐌 Slow responses - Optimize model selection and caching")
    elif avg_timing > 10:
        print("⚠️ Moderate latency - Consider faster models or caching")
    else:
        print("✅ Fast responses - Good performance")

    if exact_matches / len(successful_tests) < 0.3:
        print("📝 Low exact matches - Improve answer formatting and precision")


if __name__ == "__main__":
    main()
