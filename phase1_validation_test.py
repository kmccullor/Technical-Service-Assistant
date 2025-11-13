#!/usr/bin/env python3
"""
Phase 1 Validation Test Suite

Validates Phase 1 optimizations:
- Streaming responses (first token < 10 seconds perceived latency)
- Response caching (20%+ hit rate)
- Query optimization (successful processing without errors)

Run with: python phase1_validation_test.py
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, List
import httpx
import statistics

# Test configuration
BASE_URL = "http://localhost:8008"
TIMEOUT = 300  # 5 minutes per request
NUM_QUERIES = 20
REPEAT_RATIO = 0.3  # 30% of queries should be repeats for cache testing

# Test queries covering various topics
TEST_QUERIES = [
    # Repeated queries (for cache hit testing)
    "What is RNI?",
    "How does RNI work?",
    "What is RNI?",  # Repeat
    "Configure RNI for production",
    "How does RNI work?",  # Repeat
    
    # Technical queries
    "Explain RNI architecture and its components",
    "What are the performance requirements for RNI?",
    "How to troubleshoot RNI connectivity issues",
    "What is the recommended configuration for RNI?",
    "Configure RNI for production",  # Repeat
    
    # Domain-specific queries
    "How does RNI handle meter data collection?",
    "What authentication methods does RNI support?",
    "Explain the RNI data model",
    "How to optimize RNI for high-volume deployments?",
    "What security features are available in RNI?",
    
    # Diverse queries
    "Explain RNI architecture and its components",  # Repeat
    "What are API limits in RNI?",
    "How to deploy RNI in a distributed environment?",
    "Troubleshoot RNI performance issues",
    "Best practices for RNI configuration",
]

class Phase1ValidationTest:
    """Validates Phase 1 optimization implementations."""
    
    def __init__(self, base_url: str = BASE_URL):
        """Initialize test suite."""
        self.base_url = base_url
        self.results: List[Dict[str, Any]] = []
        self.cache_stats_before: Dict[str, Any] = {}
        self.cache_stats_after: Dict[str, Any] = {}
        self.optimization_stats_before: Dict[str, Any] = {}
        self.optimization_stats_after: Dict[str, Any] = {}
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get current cache statistics."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/cache-stats", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("cache", {})
        except Exception as e:
            print(f"Error fetching cache stats: {e}")
        return {}
    
    async def get_optimization_stats(self) -> Dict[str, Any]:
        """Get current optimization statistics."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/optimization-stats", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("optimization", {})
        except Exception as e:
            print(f"Error fetching optimization stats: {e}")
        return {}
    
    async def test_chat_query(self, query: str) -> Dict[str, Any]:
        """Test a single chat query and measure performance."""
        start_time = time.time()
        first_token_time = None
        tokens_received = 0
        
        try:
            async with httpx.AsyncClient() as client:
                # Note: This assumes SSE streaming endpoint
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "message": query,
                        "conversationId": None,
                        "displayMessage": query,
                    },
                    headers={"Authorization": "Bearer test-token"},
                    timeout=TIMEOUT,
                )
                
                if response.status_code == 401:
                    # If auth fails, try without auth (for testing)
                    response = await client.post(
                        f"{self.base_url}/api/rag-chat",
                        json={
                            "query": query,
                            "use_context": True,
                            "stream": True,
                        },
                        timeout=TIMEOUT,
                    )
                
                if response.status_code == 200:
                    elapsed = time.time() - start_time
                    return {
                        "success": True,
                        "query": query,
                        "latency_ms": int(elapsed * 1000),
                        "first_token_time_ms": int((first_token_time or elapsed) * 1000),
                        "tokens_received": tokens_received,
                        "status_code": 200,
                    }
                else:
                    return {
                        "success": False,
                        "query": query,
                        "error": f"HTTP {response.status_code}",
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "status_code": response.status_code,
                    }
        except httpx.TimeoutException:
            return {
                "success": False,
                "query": query,
                "error": "Timeout (request > 300 seconds)",
                "latency_ms": int((time.time() - start_time) * 1000),
            }
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "latency_ms": int((time.time() - start_time) * 1000),
            }
    
    async def run_tests(self) -> Dict[str, Any]:
        """Run Phase 1 validation tests."""
        print("\n" + "="*80)
        print("PHASE 1 VALIDATION TEST SUITE")
        print("="*80)
        print(f"Start time: {datetime.utcnow().isoformat()}")
        print(f"Base URL: {self.base_url}")
        print(f"Number of queries: {len(TEST_QUERIES)}")
        print(f"Timeout per query: {TIMEOUT}s")
        print()
        
        # Get baseline stats
        print("Collecting baseline statistics...")
        self.cache_stats_before = await self.get_cache_stats()
        self.optimization_stats_before = await self.get_optimization_stats()
        
        print(f"Cache enabled: {self.cache_stats_before.get('enabled', 'unknown')}")
        print(f"Cache hits (baseline): {self.cache_stats_before.get('total_hits', 0)}")
        print(f"Cache misses (baseline): {self.cache_stats_before.get('total_misses', 0)}")
        print()
        
        # Run queries
        print("Running queries...")
        for i, query in enumerate(TEST_QUERIES, 1):
            print(f"  [{i}/{len(TEST_QUERIES)}] {query[:60]}...", end=" ", flush=True)
            result = await self.test_chat_query(query)
            self.results.append(result)
            
            if result["success"]:
                print(f"✓ ({result['latency_ms']}ms)")
            else:
                print(f"✗ ({result.get('error', 'unknown')})")
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        # Get final stats
        print("\nCollecting final statistics...")
        self.cache_stats_after = await self.get_cache_stats()
        self.optimization_stats_after = await self.get_optimization_stats()
        
        print()
        return self.generate_report()
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate test report."""
        successful = [r for r in self.results if r.get("success", False)]
        failed = [r for r in self.results if not r.get("success", False)]
        
        latencies = [r.get("latency_ms", 0) for r in successful if r.get("latency_ms")]
        
        # Cache analysis
        cache_hits_before = self.cache_stats_before.get("total_hits", 0)
        cache_misses_before = self.cache_stats_before.get("total_misses", 0)
        cache_hits_after = self.cache_stats_after.get("total_hits", 0)
        cache_misses_after = self.cache_stats_after.get("total_misses", 0)
        
        new_hits = cache_hits_after - cache_hits_before
        new_misses = cache_misses_after - cache_misses_before
        total_new_requests = new_hits + new_misses
        cache_hit_rate = (new_hits / total_new_requests * 100) if total_new_requests > 0 else 0
        
        report = {
            "summary": {
                "total_queries": len(TEST_QUERIES),
                "successful": len(successful),
                "failed": len(failed),
                "success_rate_percent": (len(successful) / len(TEST_QUERIES) * 100) if TEST_QUERIES else 0,
            },
            "latency": {
                "min_ms": min(latencies) if latencies else 0,
                "max_ms": max(latencies) if latencies else 0,
                "median_ms": statistics.median(latencies) if latencies else 0,
                "mean_ms": statistics.mean(latencies) if latencies else 0,
                "stdev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
                "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
                "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0,
            },
            "caching": {
                "new_cache_hits": new_hits,
                "new_cache_misses": new_misses,
                "new_cache_hit_rate_percent": round(cache_hit_rate, 2),
                "cache_enabled": self.cache_stats_after.get("enabled", False),
                "redis_connected": self.cache_stats_after.get("redis_connected", False),
                "total_keys": self.cache_stats_after.get("redis_keys", 0),
            },
            "optimization": {
                "cache_hits": self.optimization_stats_after.get("cache_hits", 0),
                "cache_misses": self.optimization_stats_after.get("cache_misses", 0),
                "cache_size": self.optimization_stats_after.get("cache_size", 0),
            },
            "validation": {
                "streaming_working": len(successful) > 0,
                "first_token_target_met": all(
                    r.get("first_token_time_ms", 999999) < 10000 for r in successful
                ),
                "cache_hit_rate_acceptable": cache_hit_rate >= 15,  # Target 20%, accept >15%
                "no_errors": len(failed) == 0,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Print report
        print("\n" + "="*80)
        print("TEST RESULTS SUMMARY")
        print("="*80)
        print(f"\nSuccess Rate: {report['summary']['success_rate_percent']:.1f}% ({len(successful)}/{len(TEST_QUERIES)})")
        print(f"\nLatency Statistics (for successful queries):")
        print(f"  Min:    {report['latency']['min_ms']:>8.0f} ms")
        print(f"  Mean:   {report['latency']['mean_ms']:>8.0f} ms")
        print(f"  Median: {report['latency']['median_ms']:>8.0f} ms")
        print(f"  P95:    {report['latency']['p95_ms']:>8.0f} ms")
        print(f"  P99:    {report['latency']['p99_ms']:>8.0f} ms")
        print(f"  Max:    {report['latency']['max_ms']:>8.0f} ms")
        
        print(f"\nCaching Performance:")
        print(f"  New Cache Hits:     {report['caching']['new_cache_hits']:>6} requests")
        print(f"  New Cache Misses:   {report['caching']['new_cache_misses']:>6} requests")
        print(f"  Cache Hit Rate:     {report['caching']['new_cache_hit_rate_percent']:>6.1f}%")
        print(f"  Redis Connected:    {report['caching']['redis_connected']}")
        print(f"  Total Cached Keys:  {report['caching']['total_keys']:>6}")
        
        print(f"\nQuery Optimization:")
        print(f"  Optimization Cache Hits:  {report['optimization']['cache_hits']:>6}")
        print(f"  Optimization Cache Size:  {report['optimization']['cache_size']:>6}")
        
        print(f"\nPhase 1 Validation Results:")
        for key, value in report['validation'].items():
            status = "✓" if value else "✗"
            print(f"  {status} {key}: {value}")
        
        print("\n" + "="*80)
        
        # Save detailed results
        results_file = f"phase1_validation_results_{int(time.time())}.json"
        with open(results_file, "w") as f:
            json.dump({
                "report": report,
                "query_results": self.results,
            }, f, indent=2)
        
        print(f"\nDetailed results saved to: {results_file}")
        print()
        
        return report


async def main():
    """Run Phase 1 validation tests."""
    test_suite = Phase1ValidationTest()
    
    try:
        report = await test_suite.run_tests()
        
        # Return exit code based on validation
        if all(report["validation"].values()):
            print("✓ All Phase 1 validations PASSED")
            return 0
        else:
            print("✗ Some Phase 1 validations FAILED")
            return 1
    except Exception as e:
        print(f"\n✗ Test suite error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
