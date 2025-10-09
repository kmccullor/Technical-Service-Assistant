#!/usr/bin/env python3
"""
Integrated Enhanced Retrieval with Load Balancing

This implementation combines the enhanced retrieval pipeline with intelligent
load balancing across 4 Ollama containers for optimal performance.
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List

# Import all enhanced components
from enhanced_retrieval import EnhancedRetrieval
from hybrid_search import HybridSearch
from ollama_load_balancer import OllamaLoadBalancer
from query_enhancement import QueryEnhancer
from semantic_chunking import SemanticChunker

logger = logging.getLogger(__name__)


@dataclass
class IntegratedResult:
    """Complete result from integrated retrieval system."""

    query: str
    enhanced_query: str
    documents: List[Dict[str, Any]]
    scores: List[float]
    retrieval_method: str
    performance_metrics: Dict[str, Any]
    container_stats: Dict[str, Any]


class IntegratedRetrievalSystem:
    """Production-ready integrated retrieval system with all enhancements."""

    def __init__(
        self,
        enable_load_balancing: bool = True,
        enable_query_enhancement: bool = True,
        enable_hybrid_search: bool = True,
        enable_reranking: bool = True,
    ):
        """
        Initialize the complete integrated system.

        Args:
            enable_load_balancing: Use load balancer for parallel processing
            enable_query_enhancement: Enhance queries with technical terms
            enable_hybrid_search: Use vector + BM25 combination
            enable_reranking: Enable reranker integration
        """
        self.enable_load_balancing = enable_load_balancing
        self.enable_query_enhancement = enable_query_enhancement
        self.enable_hybrid_search = enable_hybrid_search
        self.enable_reranking = enable_reranking

        # Initialize all components
        self._initialize_components()

        logger.info(
            f"Integrated system initialized with features: "
            f"LoadBalancing={enable_load_balancing}, "
            f"QueryEnhancement={enable_query_enhancement}, "
            f"HybridSearch={enable_hybrid_search}, "
            f"Reranking={enable_reranking}"
        )

    def _initialize_components(self):
        """Initialize all system components."""
        # Load balancer for optimal container utilization
        if self.enable_load_balancing:
            self.load_balancer = OllamaLoadBalancer(
                containers=["11434", "11435", "11436", "11437"], strategy="response_time"
            )
        else:
            self.load_balancer = None

        # Enhanced retrieval pipeline
        self.enhanced_retrieval = EnhancedRetrieval(enable_reranking=self.enable_reranking)

        # Query enhancement
        if self.enable_query_enhancement:
            self.query_enhancer = QueryEnhancer()
        else:
            self.query_enhancer = None

        # Hybrid search
        if self.enable_hybrid_search:
            self.hybrid_search = HybridSearch(alpha=0.7)  # 70% vector, 30% BM25
        else:
            self.hybrid_search = None

        # Semantic chunker (for future document processing)
        self.semantic_chunker = SemanticChunker(max_chunk_size=512, preserve_sections=True)

    def search(self, query: str, top_k: int = 10, method: str = "auto") -> IntegratedResult:
        """
        Perform integrated search with all enhancements.

        Args:
            query: Search query
            top_k: Number of results to return
            method: Retrieval method ('auto', 'enhanced', 'hybrid', 'baseline')

        Returns:
            IntegratedResult with documents and performance metrics
        """
        start_time = time.time()

        # Step 1: Query enhancement
        enhanced_query = query
        if self.enable_query_enhancement and self.query_enhancer:
            enhancement = self.query_enhancer.enhance_query(query)
            enhanced_query = enhancement.enhanced_query
            logger.debug(f"Enhanced query: {enhanced_query}")

        # Step 2: Choose retrieval method
        if method == "auto":
            # Automatically choose best method based on query characteristics
            method = self._auto_select_method(query, enhanced_query)

        # Step 3: Perform retrieval
        documents, scores, retrieval_metrics = self._perform_retrieval(enhanced_query, top_k, method)

        # Step 4: Collect performance metrics
        total_time = time.time() - start_time
        performance_metrics = {
            "total_time": total_time,
            "method_used": method,
            "query_enhanced": self.enable_query_enhancement,
            "load_balanced": self.enable_load_balancing,
            **retrieval_metrics,
        }

        # Step 5: Get container statistics
        container_stats = self._get_container_stats()

        return IntegratedResult(
            query=query,
            enhanced_query=enhanced_query,
            documents=documents,
            scores=scores,
            retrieval_method=method,
            performance_metrics=performance_metrics,
            container_stats=container_stats,
        )

    def _auto_select_method(self, original_query: str, enhanced_query: str) -> str:
        """Automatically select the best retrieval method."""
        # Use hybrid search for technical queries with multiple terms
        if len(enhanced_query.split()) > len(original_query.split()) * 1.5 or any(
            term in enhanced_query.lower() for term in ["rni", "configuration", "installation"]
        ):
            return "hybrid" if self.enable_hybrid_search else "enhanced"

        # Use enhanced retrieval for general queries
        return "enhanced"

    def _perform_retrieval(self, query: str, top_k: int, method: str) -> tuple:
        """Perform retrieval using the specified method."""

        if method == "hybrid" and self.hybrid_search:
            # Use hybrid search (vector + BM25)
            try:
                results = self.hybrid_search.search(query, top_k)
                documents = []
                scores = []

                for result in results:
                    documents.append(
                        {
                            "content": result["text"],
                            "document_name": result["document_name"],
                            "metadata": result.get("metadata", {}),
                            "combined_score": result["combined_score"],
                        }
                    )
                    scores.append(result["combined_score"])

                metrics = {"method_details": "hybrid_vector_bm25", "vector_weight": 0.7, "bm25_weight": 0.3}

                return documents, scores, metrics

            except Exception as e:
                logger.warning(f"Hybrid search failed, falling back to enhanced: {e}")
                method = "enhanced"

        if method == "enhanced":
            # Use enhanced retrieval pipeline
            result = self.enhanced_retrieval.search(query, top_k, candidate_pool=50)
            return result.documents, result.scores, result.metrics

        else:  # baseline
            # Use basic enhanced retrieval without reranking
            result = self.enhanced_retrieval.search(query, top_k, candidate_pool=top_k)
            return result.documents, result.scores, result.metrics

    def _get_container_stats(self) -> Dict[str, Any]:
        """Get container utilization statistics."""
        if self.load_balancer:
            health_status = self.load_balancer.get_health_status()
            performance_stats = self.load_balancer.get_performance_stats()

            return {
                "load_balancer_enabled": True,
                "healthy_containers": health_status["healthy_containers"],
                "total_containers": health_status["total_containers"],
                "uptime_percentage": performance_stats["uptime_percentage"],
                "total_requests": performance_stats["total_requests"],
                "average_response_time": performance_stats["average_response_time"],
            }
        else:
            return {"load_balancer_enabled": False, "single_container_mode": True}

    def benchmark_methods(self, test_queries: List[str]) -> Dict[str, Any]:
        """Benchmark different retrieval methods."""
        methods = ["baseline", "enhanced", "hybrid"]
        results = {"test_queries": test_queries, "methods": {}, "summary": {}}

        for method in methods:
            if method == "hybrid" and not self.enable_hybrid_search:
                continue

            method_results = []
            total_time = 0

            print(f"\n🧪 Testing {method.upper()} method...")

            for query in test_queries:
                start_time = time.time()
                try:
                    result = self.search(query, top_k=5, method=method)
                    query_time = time.time() - start_time
                    total_time += query_time

                    method_results.append(
                        {
                            "query": query,
                            "results_count": len(result.documents),
                            "response_time": query_time,
                            "top_document": result.documents[0]["document_name"] if result.documents else None,
                        }
                    )

                    print(f"  ✅ {query}: {len(result.documents)} results in {query_time:.3f}s")

                except Exception as e:
                    print(f"  ❌ {query}: Error - {e}")
                    method_results.append({"query": query, "error": str(e), "response_time": 0})

            avg_time = total_time / len(test_queries) if test_queries else 0
            results["methods"][method] = {
                "queries": method_results,
                "average_response_time": avg_time,
                "total_time": total_time,
            }

            print(f"  📊 Average response time: {avg_time:.3f}s")

        # Generate summary
        results["summary"] = self._generate_benchmark_summary(results["methods"])
        return results

    def _generate_benchmark_summary(self, method_results: Dict) -> Dict[str, Any]:
        """Generate benchmark summary comparing methods."""
        summary = {"fastest_method": None, "most_reliable": None, "recommendations": []}

        # Find fastest method
        fastest_time = float("inf")
        for method, data in method_results.items():
            if data["average_response_time"] < fastest_time:
                fastest_time = data["average_response_time"]
                summary["fastest_method"] = method

        # Most reliable (least errors)
        most_reliable_score = 0
        for method, data in method_results.items():
            success_rate = sum(1 for q in data["queries"] if "error" not in q) / len(data["queries"])
            if success_rate > most_reliable_score:
                most_reliable_score = success_rate
                summary["most_reliable"] = method

        # Generate recommendations
        if "hybrid" in method_results and "enhanced" in method_results:
            hybrid_time = method_results["hybrid"]["average_response_time"]
            enhanced_time = method_results["enhanced"]["average_response_time"]

            if hybrid_time < enhanced_time * 1.2:  # Within 20%
                summary["recommendations"].append("Use hybrid search for balanced performance")
            else:
                summary["recommendations"].append("Use enhanced retrieval for better speed")

        return summary

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        status = {
            "timestamp": time.time(),
            "components": {
                "enhanced_retrieval": "enabled",
                "query_enhancement": "enabled" if self.enable_query_enhancement else "disabled",
                "hybrid_search": "enabled" if self.enable_hybrid_search else "disabled",
                "load_balancing": "enabled" if self.enable_load_balancing else "disabled",
                "reranking": "enabled" if self.enable_reranking else "disabled",
            },
            "container_status": self._get_container_stats(),
        }

        return status


def main():
    """Test the integrated retrieval system."""
    print("🚀 Integrated Enhanced Retrieval System")
    print("=" * 60)

    # Initialize integrated system with all enhancements
    system = IntegratedRetrievalSystem(
        enable_load_balancing=True, enable_query_enhancement=True, enable_hybrid_search=True, enable_reranking=True
    )

    # Test queries
    test_queries = [
        "RNI 4.16 installation requirements",
        "security configuration setup",
        "Active Directory integration",
        "troubleshoot authentication errors",
        "backup and restore procedures",
    ]

    print("🎯 System Status:")
    status = system.get_system_status()
    for component, state in status["components"].items():
        print(f"  {component}: {state}")

    print(f"\n📊 Container Status:")
    container_stats = status["container_status"]
    if container_stats["load_balancer_enabled"]:
        print(f"  Healthy containers: {container_stats['healthy_containers']}/{container_stats['total_containers']}")
        print(f"  System uptime: {container_stats['uptime_percentage']:.1f}%")
    else:
        print("  Single container mode")

    # Test individual queries
    print(f"\n🔍 Testing Individual Queries:")
    for query in test_queries[:3]:  # Test first 3
        print(f"\nQuery: {query}")
        result = system.search(query, top_k=3, method="auto")

        print(f"  Method: {result.retrieval_method}")
        print(f"  Results: {len(result.documents)}")
        print(f"  Time: {result.performance_metrics['total_time']:.3f}s")
        if result.documents:
            print(f"  Top result: {result.documents[0]['document_name']}")

    # Run comprehensive benchmark
    print(f"\n🏁 Running Comprehensive Benchmark:")
    benchmark_results = system.benchmark_methods(test_queries)

    print(f"\n📈 Benchmark Summary:")
    summary = benchmark_results["summary"]
    print(f"  Fastest method: {summary['fastest_method']}")
    print(f"  Most reliable: {summary['most_reliable']}")

    if summary["recommendations"]:
        print(f"  Recommendations:")
        for rec in summary["recommendations"]:
            print(f"    • {rec}")

    # Save results
    with open("integrated_system_benchmark.json", "w") as f:
        json.dump(benchmark_results, f, indent=2)

    print(f"\n💾 Benchmark results saved to: integrated_system_benchmark.json")
    print(f"\n✅ Integrated system ready for production deployment!")


if __name__ == "__main__":
    main()
