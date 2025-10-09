"""
Fast Reasoning Performance Test

Test script to validate 15-second performance targets for all reasoning operations.
"""

import asyncio
import time

import requests

# Test configuration
RERANKER_URL = "http://localhost:8008"
PERFORMANCE_TARGET = 15.0  # 15 seconds
WARNING_THRESHOLD = 10.0  # 10 seconds


def measure_time(func):
    """Decorator to measure execution time."""

    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        elapsed = end - start
        return result, elapsed

    return wrapper


@measure_time
def test_basic_reasoning(query: str, reasoning_type: str = "analytical"):
    """Test basic reasoning endpoint."""
    try:
        response = requests.post(
            f"{RERANKER_URL}/api/reasoning",
            json={
                "query": query,
                "reasoning_type": reasoning_type,
                "max_steps": 3,  # Limit steps for performance
                "temperature": 0.3,
                "enable_caching": True,
            },
            timeout=PERFORMANCE_TARGET,
        )
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "Request timed out", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


@measure_time
def test_search_endpoint(query: str):
    """Test basic search endpoint."""
    try:
        response = requests.post(f"{RERANKER_URL}/search", json={"query": query, "top_k": 5}, timeout=5.0)
        return response.json()
    except Exception as e:
        return {"error": str(e), "success": False}


@measure_time
def test_chat_endpoint(message: str):
    """Test basic chat endpoint."""
    try:
        response = requests.post(f"{RERANKER_URL}/chat", json={"message": message}, timeout=10.0)
        return response.json()
    except Exception as e:
        return {"error": str(e), "success": False}


def run_performance_tests():
    """Run comprehensive performance tests."""
    print("🚀 Starting Fast Reasoning Performance Tests")
    print(f"📊 Target: All operations < {PERFORMANCE_TARGET}s")
    print(f"⚠️  Warning threshold: {WARNING_THRESHOLD}s")
    print("-" * 60)

    test_cases = [
        {
            "name": "Simple Question",
            "func": test_basic_reasoning,
            "args": ("What is machine learning?", "analytical"),
            "target": 5.0,
        },
        {
            "name": "Complex Analysis",
            "func": test_basic_reasoning,
            "args": ("Compare different neural network architectures", "analytical"),
            "target": 8.0,
        },
        {
            "name": "Synthesis Query",
            "func": test_basic_reasoning,
            "args": ("Synthesize information about AI safety", "synthesis"),
            "target": 12.0,
        },
        {"name": "Basic Search", "func": test_search_endpoint, "args": ("artificial intelligence",), "target": 3.0},
        {"name": "Basic Chat", "func": test_chat_endpoint, "args": ("Hello, how are you?",), "target": 8.0},
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")

        try:
            result, elapsed = test_case["func"](*test_case["args"])

            # Performance assessment
            if elapsed <= test_case["target"]:
                status = "✅ EXCELLENT"
            elif elapsed <= WARNING_THRESHOLD:
                status = "⚡ GOOD"
            elif elapsed <= PERFORMANCE_TARGET:
                status = "⚠️  WARNING"
            else:
                status = "❌ FAILED"

            print(f"   Time: {elapsed:.2f}s | Target: {test_case['target']:.1f}s | {status}")

            # Check if response is successful
            if isinstance(result, dict):
                if result.get("success", True) and not result.get("error"):
                    print(f"   Response: ✅ Success")
                    if "final_answer" in result:
                        answer_preview = result["final_answer"][:100]
                        print(f"   Preview: {answer_preview}...")
                else:
                    print(f"   Response: ❌ Error - {result.get('error', 'Unknown error')}")

            results.append(
                {
                    "test": test_case["name"],
                    "elapsed": elapsed,
                    "target": test_case["target"],
                    "success": elapsed <= PERFORMANCE_TARGET,
                    "result": result,
                }
            )

        except Exception as e:
            print(f"   ❌ Test failed with exception: {str(e)}")
            results.append(
                {
                    "test": test_case["name"],
                    "elapsed": float("inf"),
                    "target": test_case["target"],
                    "success": False,
                    "error": str(e),
                }
            )

    # Summary
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r["success"])
    total = len(results)

    print(f"Tests passed: {passed}/{total} ({passed/total*100:.1f}%)")

    avg_time = sum(r["elapsed"] for r in results if r["elapsed"] != float("inf")) / len(
        [r for r in results if r["elapsed"] != float("inf")]
    )
    print(f"Average response time: {avg_time:.2f}s")

    # Performance recommendations
    print("\n🔧 PERFORMANCE RECOMMENDATIONS:")

    slow_tests = [r for r in results if r["elapsed"] > WARNING_THRESHOLD]
    if slow_tests:
        print("⚠️  Slow operations detected:")
        for test in slow_tests:
            print(f"   - {test['test']}: {test['elapsed']:.2f}s (target: {test['target']:.1f}s)")

    failed_tests = [r for r in results if not r["success"]]
    if failed_tests:
        print("❌ Failed operations:")
        for test in failed_tests:
            print(f"   - {test['test']}: {test.get('error', 'Timeout or performance failure')}")

    if passed == total and avg_time <= WARNING_THRESHOLD:
        print("🎉 All tests passed! System meets performance targets.")
        return True
    else:
        print("⚡ System needs optimization to meet all performance targets.")
        return False


def test_reasoning_caching():
    """Test caching effectiveness."""
    print("\n🧪 Testing Reasoning Cache Performance")

    query = "What are the main types of machine learning?"

    # First call (cache miss)
    print("First call (cache miss):")
    result1, time1 = test_basic_reasoning(query, "analytical")
    print(f"Time: {time1:.2f}s")

    # Second call (should be cached)
    print("Second call (should be cached):")
    result2, time2 = test_basic_reasoning(query, "analytical")
    print(f"Time: {time2:.2f}s")

    if time2 < time1 * 0.5:  # Cache should be much faster
        print("✅ Caching is working effectively")
        return True
    else:
        print("⚠️  Caching may not be working optimally")
        return False


def test_concurrent_requests():
    """Test system performance under concurrent load."""
    print("\n🧪 Testing Concurrent Request Performance")

    async def make_concurrent_requests():
        queries = [
            "What is artificial intelligence?",
            "Explain machine learning algorithms",
            "What are neural networks?",
            "How does deep learning work?",
            "What is natural language processing?",
        ]

        tasks = []
        for query in queries:
            task = asyncio.create_task(asyncio.to_thread(test_basic_reasoning, query, "analytical"))
            tasks.append(task)

        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        return results, total_time

    results, total_time = asyncio.run(make_concurrent_requests())

    print(f"5 concurrent requests completed in {total_time:.2f}s")

    successful = sum(1 for r in results if isinstance(r, tuple) and r[1] <= PERFORMANCE_TARGET)
    print(f"Successful requests: {successful}/5")

    if total_time <= 20 and successful >= 4:  # Allow some tolerance for concurrent load
        print("✅ System handles concurrent load well")
        return True
    else:
        print("⚠️  System may struggle under concurrent load")
        return False


if __name__ == "__main__":
    print("🔥 Fast Reasoning Performance Validation")
    print("=" * 60)

    try:
        # Test basic connectivity first
        response = requests.get(f"{RERANKER_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Reranker service not healthy")
            exit(1)

        print("✅ Reranker service is healthy")

        # Run performance tests
        performance_ok = run_performance_tests()

        # Test caching
        cache_ok = test_reasoning_caching()

        # Test concurrent load
        concurrent_ok = test_concurrent_requests()

        # Final assessment
        print("\n" + "=" * 60)
        print("🏁 FINAL ASSESSMENT")
        print("=" * 60)

        if performance_ok and cache_ok and concurrent_ok:
            print("🎉 SUCCESS: System meets all performance requirements!")
            print("✅ Ready for production deployment")
        else:
            print("⚠️  NEEDS OPTIMIZATION: Some performance targets not met")
            print("📋 Recommendations:")
            if not performance_ok:
                print("   - Optimize reasoning algorithms for faster response")
            if not cache_ok:
                print("   - Improve caching mechanisms")
            if not concurrent_ok:
                print("   - Add load balancing and connection pooling")

    except Exception as e:
        print(f"❌ Test suite failed: {str(e)}")
        exit(1)
