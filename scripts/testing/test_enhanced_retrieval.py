#!/usr/bin/env python3
"""
Enhanced Retrieval Testing and Comparison

This script compares the new enhanced retrieval system (with reranker fallback)
against the baseline system to demonstrate accuracy improvements.
"""

import json
import sys
import time
from typing import Any, Dict

from enhanced_retrieval import EnhancedRetrieval

# Add project root to path
sys.path.insert(0, "/home/kmccullor/Projects/Technical-Service-Assistant")


class RetrievalComparison:
    """Compare enhanced retrieval against baseline system."""

    def __init__(self):
        self.enhanced_retrieval = EnhancedRetrieval(enable_reranking=True)
        self.baseline_retrieval = EnhancedRetrieval(enable_reranking=False)  # Vector only

        # Test questions from our previous analysis
        self.test_queries = [
            {"query": "What is the RNI 4.16 release date?", "expected_doc": "RNI 4.16.1 Release Notes.pdf"},
            {
                "query": "How do you configure the security system?",
                "expected_doc": "RNI 4.16 System Security User Guide.pdf",
            },
            {
                "query": "What are the installation requirements?",
                "expected_doc": "RNI 4.16 Hardware Security Module Installation Guide.pdf",
            },
            {
                "query": "How do you setup Active Directory integration?",
                "expected_doc": "RNI 4.16 Microsoft Active Directory Integration Guide.pdf",
            },
            {
                "query": "What reporting features are available?",
                "expected_doc": "RNI 4.16 Reports Operation Reference Manual.pdf",
            },
        ]

    def evaluate_retrieval(self, retrieval_system: EnhancedRetrieval, system_name: str) -> Dict[str, Any]:
        """Evaluate a retrieval system against test queries."""
        print(f"\n🔍 Testing {system_name}")
        print("=" * 50)

        results = {
            "system_name": system_name,
            "queries": [],
            "metrics": {
                "recall_at_1": 0,
                "recall_at_5": 0,
                "recall_at_10": 0,
                "avg_response_time": 0,
                "total_queries": len(self.test_queries),
            },
        }

        recall_1_hits = 0
        recall_5_hits = 0
        recall_10_hits = 0
        total_time = 0

        for i, test_case in enumerate(self.test_queries, 1):
            query = test_case["query"]
            expected_doc = test_case["expected_doc"]

            print(f"\nQuery {i}: {query}")

            # Run retrieval
            time.time()
            result = retrieval_system.search(query, top_k=10, candidate_pool=50)
            response_time = result.total_time
            total_time += response_time

            # Check if expected document appears in results
            found_positions = []
            for j, doc in enumerate(result.documents):
                if expected_doc in doc.get("document_name", ""):
                    found_positions.append(j + 1)  # 1-indexed position

            # Calculate recall metrics
            recall_1 = 1 if any(pos <= 1 for pos in found_positions) else 0
            recall_5 = 1 if any(pos <= 5 for pos in found_positions) else 0
            recall_10 = 1 if any(pos <= 10 for pos in found_positions) else 0

            recall_1_hits += recall_1
            recall_5_hits += recall_5
            recall_10_hits += recall_10

            # Store query results
            query_result = {
                "query": query,
                "expected_doc": expected_doc,
                "found_positions": found_positions,
                "recall_1": recall_1,
                "recall_5": recall_5,
                "recall_10": recall_10,
                "response_time": response_time,
                "top_result": result.documents[0]["content"][:100] + "..." if result.documents else "No results",
                "quality_metrics": result.metrics,
            }
            results["queries"].append(query_result)

            # Print immediate results
            if found_positions:
                print(f"✅ Found at positions: {found_positions}")
            else:
                print("❌ Expected document not found in top 10")

            print(f"⏱️ Response time: {response_time:.3f}s")
            if result.documents:
                print(f"📄 Top result: {result.documents[0]['content'][:80]}...")

        # Calculate final metrics
        results["metrics"]["recall_at_1"] = recall_1_hits / len(self.test_queries)
        results["metrics"]["recall_at_5"] = recall_5_hits / len(self.test_queries)
        results["metrics"]["recall_at_10"] = recall_10_hits / len(self.test_queries)
        results["metrics"]["avg_response_time"] = total_time / len(self.test_queries)

        return results

    def run_comparison(self) -> Dict[str, Any]:
        """Run complete comparison between systems."""
        print("🚀 Enhanced Retrieval System Comparison")
        print("=" * 60)

        # Test both systems
        baseline_results = self.evaluate_retrieval(self.baseline_retrieval, "Baseline (Vector Only)")
        enhanced_results = self.evaluate_retrieval(self.enhanced_retrieval, "Enhanced (Vector + Reranker Fallback)")

        # Calculate improvements
        comparison = {
            "baseline": baseline_results,
            "enhanced": enhanced_results,
            "improvements": {
                "recall_1_improvement": enhanced_results["metrics"]["recall_at_1"]
                - baseline_results["metrics"]["recall_at_1"],
                "recall_5_improvement": enhanced_results["metrics"]["recall_at_5"]
                - baseline_results["metrics"]["recall_at_5"],
                "recall_10_improvement": enhanced_results["metrics"]["recall_at_10"]
                - baseline_results["metrics"]["recall_at_10"],
                "response_time_change": enhanced_results["metrics"]["avg_response_time"]
                - baseline_results["metrics"]["avg_response_time"],
            },
        }

        # Print summary
        self.print_comparison_summary(comparison)

        return comparison

    def print_comparison_summary(self, comparison: Dict[str, Any]):
        """Print formatted comparison summary."""
        baseline = comparison["baseline"]["metrics"]
        enhanced = comparison["enhanced"]["metrics"]
        improvements = comparison["improvements"]

        print(f"\n📊 COMPARISON SUMMARY")
        print("=" * 60)

        print(f"{'Metric':<25} {'Baseline':<15} {'Enhanced':<15} {'Improvement':<15}")
        print("-" * 70)

        print(
            f"{'Recall@1':<25} {baseline['recall_at_1']:<15.1%} {enhanced['recall_at_1']:<15.1%} {improvements['recall_1_improvement']:+.1%}"
        )
        print(
            f"{'Recall@5':<25} {baseline['recall_at_5']:<15.1%} {enhanced['recall_at_5']:<15.1%} {improvements['recall_5_improvement']:+.1%}"
        )
        print(
            f"{'Recall@10':<25} {baseline['recall_at_10']:<15.1%} {enhanced['recall_at_10']:<15.1%} {improvements['recall_10_improvement']:+.1%}"
        )
        print(
            f"{'Avg Response Time':<25} {baseline['avg_response_time']:<15.3f}s {enhanced['avg_response_time']:<15.3f}s {improvements['response_time_change']:+.3f}s"
        )

        print(f"\n🎯 KEY INSIGHTS:")
        if improvements["recall_1_improvement"] > 0:
            print(f"✅ Enhanced system shows {improvements['recall_1_improvement']:.1%} improvement in Recall@1")
        else:
            print(f"⚠️ Enhanced system shows {improvements['recall_1_improvement']:.1%} change in Recall@1")

        if improvements["response_time_change"] < 0.05:  # Less than 50ms increase
            print(f"✅ Response time impact minimal: {improvements['response_time_change']:+.3f}s")
        else:
            print(f"⚠️ Response time increased by {improvements['response_time_change']:.3f}s")

        print(f"\n💡 NEXT STEPS:")
        print("- Enable reranker service to test full enhanced pipeline")
        print("- Implement hybrid search for additional improvements")
        print("- Test semantic chunking for better context preservation")


def main():
    """Run the retrieval comparison test."""
    try:
        comparison = RetrievalComparison()
        results = comparison.run_comparison()

        # Save detailed results
        with open("retrieval_comparison_results.json", "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n💾 Detailed results saved to: retrieval_comparison_results.json")

    except Exception as e:
        print(f"❌ Comparison failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
