#!/usr/bin/env python3
"""
Phase 2C Performance Benchmarking and Evaluation Suite

This module provides comprehensive benchmarking tools for evaluating:
1. Retrieval accuracy improvements across different methods
2. Response time and throughput performance
3. A/B testing with statistical significance
4. Real-time performance monitoring integration
5. Comprehensive accuracy validation framework

Integrates with Phase 2B monitoring for production insights.
"""

import asyncio
import json
import math
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable
import random

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

from config import get_settings
from utils.logging_config import setup_logging

# Import Phase 2C components
from phase2c_accuracy_system import (
    Phase2CAccuracySystem, SearchMethod, SearchResult, AccuracyMetrics,
    AdvancedConfidenceScorer
)
from advanced_semantic_chunking import AdvancedSemanticChunker, ContentPattern

# Setup logging
logger = setup_logging(
    program_name="phase2c_benchmarking",
    log_level="INFO",
    console_output=True,
)

settings = get_settings()

class BenchmarkType(str, Enum):
    """Types of benchmarks to run."""
    ACCURACY = "accuracy"
    PERFORMANCE = "performance"
    SCALABILITY = "scalability"
    AB_TESTING = "ab_testing"
    COMPREHENSIVE = "comprehensive"

class MetricType(str, Enum):
    """Types of metrics to collect."""
    RECALL_AT_K = "recall_at_k"
    PRECISION_AT_K = "precision_at_k"
    NDCG = "ndcg"
    MRR = "mrr"  # Mean Reciprocal Rank
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    CONFIDENCE_SCORE = "confidence_score"
    SEMANTIC_COVERAGE = "semantic_coverage"

@dataclass
class BenchmarkQuery:
    """A query with ground truth for evaluation."""
    query: str
    expected_documents: List[str]  # Expected relevant document names
    query_complexity: str  # simple, moderate, complex, expert
    domain: str  # technical area (networking, database, etc.)
    ideal_confidence: float = 0.8  # Expected confidence score

@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    query: str
    method: str
    results: List[SearchResult]
    metrics: AccuracyMetrics
    ground_truth_match: float  # How well results match expected
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class StatisticalTest:
    """Statistical test results for comparing methods."""
    test_name: str
    method_a: str
    method_b: str
    metric: str
    p_value: float
    effect_size: float
    confidence_interval: Tuple[float, float]
    is_significant: bool
    recommendation: str

class GroundTruthGenerator:
    """Generate and manage ground truth data for evaluation."""
    
    def __init__(self):
        """Initialize ground truth generator."""
        self.technical_queries = [
            {
                "query": "RNI network configuration parameters",
                "expected_docs": ["RNI_Config_Manual.pdf", "Network_Setup_Guide.pdf"],
                "complexity": "moderate",
                "domain": "networking"
            },
            {
                "query": "FlexNet database connection troubleshooting",
                "expected_docs": ["FlexNet_Database_Guide.pdf", "Troubleshooting_Manual.pdf"],
                "complexity": "complex",
                "domain": "database"
            },
            {
                "query": "AMDS installation requirements Windows Server",
                "expected_docs": ["AMDS_Installation_Guide.pdf", "System_Requirements.pdf"],
                "complexity": "moderate",
                "domain": "installation"
            },
            {
                "query": "Router firmware update procedure version 2.5",
                "expected_docs": ["Router_Firmware_Guide.pdf", "Update_Procedures.pdf"],
                "complexity": "complex",
                "domain": "firmware"
            },
            {
                "query": "TCP/IP port configuration for FlexNet",
                "expected_docs": ["Network_Configuration.pdf", "Port_Settings_Guide.pdf"],
                "complexity": "expert",
                "domain": "networking"
            },
            {
                "query": "SQL Server authentication setup",
                "expected_docs": ["Database_Security_Guide.pdf", "SQL_Configuration.pdf"],
                "complexity": "expert",
                "domain": "database"
            },
            {
                "query": "System requirements minimum hardware",
                "expected_docs": ["System_Requirements.pdf", "Hardware_Specifications.pdf"],
                "complexity": "simple",
                "domain": "hardware"
            },
            {
                "query": "Error code 1001 resolution",
                "expected_docs": ["Error_Codes_Reference.pdf", "Troubleshooting_Manual.pdf"],
                "complexity": "moderate",
                "domain": "troubleshooting"
            }
        ]
    
    def generate_benchmark_queries(self, count: int = None) -> List[BenchmarkQuery]:
        """Generate benchmark queries with ground truth."""
        
        if count is None:
            count = len(self.technical_queries)
        
        queries = []
        selected_queries = random.sample(self.technical_queries, min(count, len(self.technical_queries)))
        
        for query_data in selected_queries:
            benchmark_query = BenchmarkQuery(
                query=query_data["query"],
                expected_documents=query_data["expected_docs"],
                query_complexity=query_data["complexity"],
                domain=query_data["domain"],
                ideal_confidence=self._calculate_ideal_confidence(query_data["complexity"])
            )
            queries.append(benchmark_query)
        
        return queries
    
    def _calculate_ideal_confidence(self, complexity: str) -> float:
        """Calculate ideal confidence score based on query complexity."""
        complexity_scores = {
            "simple": 0.9,
            "moderate": 0.8,
            "complex": 0.7,
            "expert": 0.65
        }
        return complexity_scores.get(complexity, 0.75)

class AccuracyEvaluator:
    """Evaluate retrieval accuracy using standard IR metrics."""
    
    def __init__(self):
        """Initialize accuracy evaluator."""
        pass
    
    def calculate_recall_at_k(
        self, 
        results: List[SearchResult], 
        ground_truth: List[str], 
        k: int = 5
    ) -> float:
        """Calculate Recall@K metric."""
        
        if not ground_truth:
            return 0.0
        
        top_k_results = results[:k]
        retrieved_docs = {result.document_name for result in top_k_results}
        relevant_docs = set(ground_truth)
        
        relevant_retrieved = len(retrieved_docs.intersection(relevant_docs))
        recall = relevant_retrieved / len(relevant_docs)
        
        return recall
    
    def calculate_precision_at_k(
        self, 
        results: List[SearchResult], 
        ground_truth: List[str], 
        k: int = 5
    ) -> float:
        """Calculate Precision@K metric."""
        
        if not results:
            return 0.0
        
        top_k_results = results[:k]
        retrieved_docs = {result.document_name for result in top_k_results}
        relevant_docs = set(ground_truth)
        
        relevant_retrieved = len(retrieved_docs.intersection(relevant_docs))
        precision = relevant_retrieved / len(top_k_results)
        
        return precision
    
    def calculate_ndcg(
        self, 
        results: List[SearchResult], 
        ground_truth: List[str], 
        k: int = 5
    ) -> float:
        """Calculate Normalized Discounted Cumulative Gain (NDCG)."""
        
        if not results or not ground_truth:
            return 0.0
        
        # Create relevance scores (1 for relevant, 0 for irrelevant)
        relevance_scores = []
        for i, result in enumerate(results[:k]):
            if result.document_name in ground_truth:
                relevance_scores.append(1.0)
            else:
                relevance_scores.append(0.0)
        
        # Calculate DCG
        dcg = 0.0
        for i, relevance in enumerate(relevance_scores):
            if i == 0:
                dcg += relevance
            else:
                dcg += relevance / math.log2(i + 1)
        
        # Calculate IDCG (ideal DCG)
        ideal_scores = [1.0] * min(len(ground_truth), k) + [0.0] * max(0, k - len(ground_truth))
        idcg = 0.0
        for i, relevance in enumerate(ideal_scores):
            if i == 0:
                idcg += relevance
            else:
                idcg += relevance / math.log2(i + 1)
        
        # Calculate NDCG
        ndcg = dcg / idcg if idcg > 0 else 0.0
        return ndcg
    
    def calculate_mrr(
        self, 
        results: List[SearchResult], 
        ground_truth: List[str]
    ) -> float:
        """Calculate Mean Reciprocal Rank (MRR)."""
        
        for i, result in enumerate(results):
            if result.document_name in ground_truth:
                return 1.0 / (i + 1)
        
        return 0.0
    
    def calculate_ground_truth_match(
        self, 
        results: List[SearchResult], 
        ground_truth: List[str]
    ) -> float:
        """Calculate overall match with ground truth."""
        
        if not ground_truth:
            return 0.0
        
        # Weighted scoring based on position
        total_score = 0.0
        max_possible_score = 0.0
        
        for i, result in enumerate(results[:10]):  # Top 10 results
            position_weight = 1.0 / (i + 1)  # Higher weight for top results
            max_possible_score += position_weight
            
            if result.document_name in ground_truth:
                total_score += position_weight
        
        return total_score / max_possible_score if max_possible_score > 0 else 0.0

class PerformanceBenchmarker:
    """Benchmark performance metrics like response time and throughput."""
    
    def __init__(self):
        """Initialize performance benchmarker."""
        pass
    
    async def benchmark_response_time(
        self,
        accuracy_system: Phase2CAccuracySystem,
        queries: List[str],
        method: SearchMethod,
        iterations: int = 10
    ) -> Dict[str, float]:
        """Benchmark response time for a set of queries."""
        
        response_times = []
        
        for iteration in range(iterations):
            for query in queries:
                start_time = time.time()
                
                try:
                    results, metrics = await accuracy_system.comprehensive_search(
                        query, method=method
                    )
                    response_time = time.time() - start_time
                    response_times.append(response_time)
                    
                except Exception as e:
                    logger.error(f"Response time test failed for query '{query}': {e}")
                    response_times.append(float('inf'))  # Mark as failed
        
        # Calculate statistics
        valid_times = [t for t in response_times if t != float('inf')]
        
        if not valid_times:
            return {"error": "All requests failed"}
        
        return {
            "mean": statistics.mean(valid_times),
            "median": statistics.median(valid_times),
            "p95": np.percentile(valid_times, 95),
            "p99": np.percentile(valid_times, 99),
            "min": min(valid_times),
            "max": max(valid_times),
            "std": statistics.stdev(valid_times) if len(valid_times) > 1 else 0.0,
            "success_rate": len(valid_times) / len(response_times)
        }
    
    async def benchmark_throughput(
        self,
        accuracy_system: Phase2CAccuracySystem,
        queries: List[str],
        method: SearchMethod,
        concurrent_requests: int = 10,
        duration_seconds: int = 60
    ) -> Dict[str, float]:
        """Benchmark throughput under concurrent load."""
        
        results = []
        start_time = time.time()
        
        async def worker():
            """Worker function for concurrent requests."""
            request_count = 0
            while time.time() - start_time < duration_seconds:
                query = random.choice(queries)
                
                try:
                    worker_start = time.time()
                    await accuracy_system.comprehensive_search(query, method=method)
                    response_time = time.time() - worker_start
                    
                    results.append({
                        "success": True,
                        "response_time": response_time,
                        "timestamp": time.time()
                    })
                    request_count += 1
                    
                except Exception as e:
                    results.append({
                        "success": False,
                        "error": str(e),
                        "timestamp": time.time()
                    })
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.01)
        
        # Run concurrent workers
        tasks = [worker() for _ in range(concurrent_requests)]
        await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        successful_requests = [r for r in results if r.get("success", False)]
        
        return {
            "total_requests": len(results),
            "successful_requests": len(successful_requests),
            "failed_requests": len(results) - len(successful_requests),
            "success_rate": len(successful_requests) / len(results) if results else 0.0,
            "requests_per_second": len(successful_requests) / total_time,
            "avg_response_time": statistics.mean([r["response_time"] for r in successful_requests]) if successful_requests else 0.0,
            "concurrent_users": concurrent_requests,
            "test_duration": total_time
        }

class StatisticalAnalyzer:
    """Perform statistical analysis and comparison of different methods."""
    
    def __init__(self):
        """Initialize statistical analyzer."""
        pass
    
    def compare_methods(
        self,
        results_a: List[BenchmarkResult],
        results_b: List[BenchmarkResult],
        metric: MetricType,
        alpha: float = 0.05
    ) -> StatisticalTest:
        """Compare two methods using statistical tests."""
        
        # Extract metric values
        values_a = self._extract_metric_values(results_a, metric)
        values_b = self._extract_metric_values(results_b, metric)
        
        if not values_a or not values_b:
            return StatisticalTest(
                test_name="insufficient_data",
                method_a="method_a",
                method_b="method_b",
                metric=metric.value,
                p_value=1.0,
                effect_size=0.0,
                confidence_interval=(0.0, 0.0),
                is_significant=False,
                recommendation="Insufficient data for comparison"
            )
        
        # Perform t-test
        t_stat, p_value = stats.ttest_ind(values_a, values_b)
        
        # Calculate effect size (Cohen's d)
        pooled_std = math.sqrt(((len(values_a) - 1) * np.var(values_a) + 
                               (len(values_b) - 1) * np.var(values_b)) / 
                              (len(values_a) + len(values_b) - 2))
        
        effect_size = (np.mean(values_a) - np.mean(values_b)) / pooled_std if pooled_std > 0 else 0.0
        
        # Calculate confidence interval for difference
        diff_mean = np.mean(values_a) - np.mean(values_b)
        diff_se = math.sqrt(np.var(values_a)/len(values_a) + np.var(values_b)/len(values_b))
        ci_margin = stats.t.ppf(1 - alpha/2, len(values_a) + len(values_b) - 2) * diff_se
        
        confidence_interval = (diff_mean - ci_margin, diff_mean + ci_margin)
        is_significant = p_value < alpha
        
        # Generate recommendation
        if is_significant:
            if effect_size > 0.8:
                effect_desc = "large"
            elif effect_size > 0.5:
                effect_desc = "medium"
            elif effect_size > 0.2:
                effect_desc = "small"
            else:
                effect_desc = "negligible"
            
            better_method = "method_a" if np.mean(values_a) > np.mean(values_b) else "method_b"
            recommendation = f"Statistically significant difference detected. {better_method} performs better with {effect_desc} effect size."
        else:
            recommendation = "No statistically significant difference detected."
        
        return StatisticalTest(
            test_name="independent_t_test",
            method_a="method_a",
            method_b="method_b",
            metric=metric.value,
            p_value=p_value,
            effect_size=abs(effect_size),
            confidence_interval=confidence_interval,
            is_significant=is_significant,
            recommendation=recommendation
        )
    
    def _extract_metric_values(self, results: List[BenchmarkResult], metric: MetricType) -> List[float]:
        """Extract metric values from benchmark results."""
        
        values = []
        
        for result in results:
            if metric == MetricType.CONFIDENCE_SCORE:
                values.append(result.metrics.confidence_score)
            elif metric == MetricType.RESPONSE_TIME:
                values.append(result.metrics.response_time)
            elif metric == MetricType.SEMANTIC_COVERAGE:
                values.append(result.metrics.semantic_coverage)
            elif metric == MetricType.RECALL_AT_K:
                values.append(result.ground_truth_match)  # Using as proxy
            # Add more metrics as needed
        
        return values

class ComprehensiveBenchmarkSuite:
    """Main benchmarking suite coordinating all evaluation components."""
    
    def __init__(self):
        """Initialize comprehensive benchmark suite."""
        self.ground_truth_generator = GroundTruthGenerator()
        self.accuracy_evaluator = AccuracyEvaluator()
        self.performance_benchmarker = PerformanceBenchmarker()
        self.statistical_analyzer = StatisticalAnalyzer()
        self.accuracy_system = Phase2CAccuracySystem()
        
        # Results storage
        self.benchmark_results = []
        self.performance_results = []
        
        logger.info("Comprehensive benchmark suite initialized")
    
    async def run_accuracy_benchmark(
        self, 
        methods: List[SearchMethod],
        query_count: int = 20
    ) -> Dict[str, Any]:
        """Run comprehensive accuracy benchmark."""
        
        logger.info(f"Starting accuracy benchmark with {len(methods)} methods and {query_count} queries")
        
        # Generate benchmark queries
        benchmark_queries = self.ground_truth_generator.generate_benchmark_queries(query_count)
        
        # Results storage
        method_results = {method.value: [] for method in methods}
        
        # Run benchmarks for each method
        for method in methods:
            logger.info(f"Benchmarking method: {method.value}")
            
            for benchmark_query in benchmark_queries:
                try:
                    # Get search results
                    results, metrics = await self.accuracy_system.comprehensive_search(
                        benchmark_query.query,
                        method=method
                    )
                    
                    # Calculate accuracy metrics
                    recall_at_5 = self.accuracy_evaluator.calculate_recall_at_k(
                        results, benchmark_query.expected_documents, k=5
                    )
                    precision_at_5 = self.accuracy_evaluator.calculate_precision_at_k(
                        results, benchmark_query.expected_documents, k=5
                    )
                    ndcg_at_5 = self.accuracy_evaluator.calculate_ndcg(
                        results, benchmark_query.expected_documents, k=5
                    )
                    mrr = self.accuracy_evaluator.calculate_mrr(
                        results, benchmark_query.expected_documents
                    )
                    ground_truth_match = self.accuracy_evaluator.calculate_ground_truth_match(
                        results, benchmark_query.expected_documents
                    )
                    
                    # Create benchmark result
                    benchmark_result = BenchmarkResult(
                        query=benchmark_query.query,
                        method=method.value,
                        results=results,
                        metrics=metrics,
                        ground_truth_match=ground_truth_match
                    )
                    
                    # Store additional metrics
                    benchmark_result.recall_at_5 = recall_at_5
                    benchmark_result.precision_at_5 = precision_at_5
                    benchmark_result.ndcg_at_5 = ndcg_at_5
                    benchmark_result.mrr = mrr
                    
                    method_results[method.value].append(benchmark_result)
                    
                except Exception as e:
                    logger.error(f"Benchmark failed for query '{benchmark_query.query}' with method {method.value}: {e}")
        
        # Calculate aggregate results
        aggregate_results = {}
        for method_name, results in method_results.items():
            if results:
                aggregate_results[method_name] = {
                    "avg_recall_at_5": statistics.mean([r.recall_at_5 for r in results]),
                    "avg_precision_at_5": statistics.mean([r.precision_at_5 for r in results]),
                    "avg_ndcg_at_5": statistics.mean([r.ndcg_at_5 for r in results]),
                    "avg_mrr": statistics.mean([r.mrr for r in results]),
                    "avg_confidence": statistics.mean([r.metrics.confidence_score for r in results]),
                    "avg_response_time": statistics.mean([r.metrics.response_time for r in results]),
                    "avg_ground_truth_match": statistics.mean([r.ground_truth_match for r in results]),
                    "query_count": len(results)
                }
        
        # Statistical comparisons
        statistical_tests = []
        if len(methods) >= 2:
            method_names = list(method_results.keys())
            for i in range(len(method_names)):
                for j in range(i + 1, len(method_names)):
                    method_a_results = method_results[method_names[i]]
                    method_b_results = method_results[method_names[j]]
                    
                    if method_a_results and method_b_results:
                        test = self.statistical_analyzer.compare_methods(
                            method_a_results,
                            method_b_results,
                            MetricType.CONFIDENCE_SCORE
                        )
                        test.method_a = method_names[i]
                        test.method_b = method_names[j]
                        statistical_tests.append(test)
        
        return {
            "benchmark_type": "accuracy",
            "timestamp": datetime.now().isoformat(),
            "methods_tested": [m.value for m in methods],
            "queries_tested": query_count,
            "aggregate_results": aggregate_results,
            "statistical_tests": [
                {
                    "test_name": test.test_name,
                    "method_a": test.method_a,
                    "method_b": test.method_b,
                    "metric": test.metric,
                    "p_value": test.p_value,
                    "effect_size": test.effect_size,
                    "is_significant": test.is_significant,
                    "recommendation": test.recommendation
                }
                for test in statistical_tests
            ],
            "detailed_results": method_results
        }
    
    async def run_performance_benchmark(
        self,
        methods: List[SearchMethod],
        test_queries: List[str] = None
    ) -> Dict[str, Any]:
        """Run performance benchmark for response time and throughput."""
        
        if test_queries is None:
            benchmark_queries = self.ground_truth_generator.generate_benchmark_queries(10)
            test_queries = [q.query for q in benchmark_queries]
        
        logger.info(f"Starting performance benchmark with {len(methods)} methods")
        
        performance_results = {}
        
        for method in methods:
            logger.info(f"Performance testing method: {method.value}")
            
            # Response time benchmark
            response_time_results = await self.performance_benchmarker.benchmark_response_time(
                self.accuracy_system,
                test_queries,
                method,
                iterations=5
            )
            
            # Throughput benchmark
            throughput_results = await self.performance_benchmarker.benchmark_throughput(
                self.accuracy_system,
                test_queries,
                method,
                concurrent_requests=5,
                duration_seconds=30
            )
            
            performance_results[method.value] = {
                "response_time": response_time_results,
                "throughput": throughput_results
            }
        
        return {
            "benchmark_type": "performance",
            "timestamp": datetime.now().isoformat(),
            "methods_tested": [m.value for m in methods],
            "test_queries_count": len(test_queries),
            "results": performance_results
        }
    
    async def run_comprehensive_benchmark(
        self,
        methods: List[SearchMethod] = None,
        query_count: int = 15
    ) -> Dict[str, Any]:
        """Run comprehensive benchmark including accuracy and performance."""
        
        if methods is None:
            methods = [
                SearchMethod.VECTOR_ONLY,
                SearchMethod.ENHANCED_RETRIEVAL,
                SearchMethod.HYBRID_SEARCH
            ]
        
        logger.info(f"Starting comprehensive benchmark with {len(methods)} methods")
        
        # Run accuracy benchmark
        accuracy_results = await self.run_accuracy_benchmark(methods, query_count)
        
        # Run performance benchmark
        performance_results = await self.run_performance_benchmark(methods)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(accuracy_results, performance_results)
        
        return {
            "benchmark_type": "comprehensive",
            "timestamp": datetime.now().isoformat(),
            "methods_tested": [m.value for m in methods],
            "accuracy_results": accuracy_results,
            "performance_results": performance_results,
            "recommendations": recommendations
        }
    
    def _generate_recommendations(
        self,
        accuracy_results: Dict[str, Any],
        performance_results: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on benchmark results."""
        
        recommendations = []
        
        # Find best accuracy method
        accuracy_data = accuracy_results.get("aggregate_results", {})
        if accuracy_data:
            best_accuracy_method = max(
                accuracy_data.keys(),
                key=lambda m: accuracy_data[m].get("avg_confidence", 0)
            )
            best_accuracy_score = accuracy_data[best_accuracy_method].get("avg_confidence", 0)
            
            recommendations.append(
                f"Best accuracy method: {best_accuracy_method} "
                f"(avg confidence: {best_accuracy_score:.3f})"
            )
        
        # Find best performance method
        performance_data = performance_results.get("results", {})
        if performance_data:
            best_performance_method = min(
                performance_data.keys(),
                key=lambda m: performance_data[m].get("response_time", {}).get("mean", float('inf'))
            )
            best_response_time = performance_data[best_performance_method].get("response_time", {}).get("mean", 0)
            
            recommendations.append(
                f"Best performance method: {best_performance_method} "
                f"(avg response time: {best_response_time:.3f}s)"
            )
        
        # Statistical significance recommendations
        statistical_tests = accuracy_results.get("statistical_tests", [])
        significant_tests = [t for t in statistical_tests if t.get("is_significant", False)]
        
        if significant_tests:
            recommendations.append(
                f"Found {len(significant_tests)} statistically significant differences"
            )
        
        # Overall recommendations
        if accuracy_data and performance_data:
            # Balance accuracy and performance
            method_scores = {}
            for method in accuracy_data.keys():
                if method in performance_data:
                    accuracy_score = accuracy_data[method].get("avg_confidence", 0)
                    response_time = performance_data[method].get("response_time", {}).get("mean", float('inf'))
                    
                    # Normalize scores (higher is better)
                    perf_score = 1.0 / (response_time + 0.1)  # Avoid division by zero
                    combined_score = accuracy_score * 0.7 + perf_score * 0.3  # Weight accuracy higher
                    
                    method_scores[method] = combined_score
            
            if method_scores:
                best_overall = max(method_scores.keys(), key=lambda m: method_scores[m])
                recommendations.append(
                    f"Recommended method (balanced accuracy/performance): {best_overall}"
                )
        
        return recommendations
    
    def export_results(self, results: Dict[str, Any], filename: str = None) -> str:
        """Export benchmark results to JSON file."""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_results_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Benchmark results exported to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Failed to export results: {e}")
            return ""

# Main usage example and testing
async def main():
    """Main function for testing the benchmarking suite."""
    
    logger.info("Starting Phase 2C Benchmarking Suite test")
    
    # Initialize benchmark suite
    suite = ComprehensiveBenchmarkSuite()
    
    # Methods to test
    test_methods = [
        SearchMethod.ENHANCED_RETRIEVAL,
        SearchMethod.HYBRID_SEARCH
    ]
    
    # Run comprehensive benchmark
    results = await suite.run_comprehensive_benchmark(
        methods=test_methods,
        query_count=8  # Reduced for testing
    )
    
    # Display results summary
    logger.info("Benchmark Results Summary:")
    logger.info(f"Methods tested: {results['methods_tested']}")
    
    # Accuracy results
    accuracy_results = results.get("accuracy_results", {}).get("aggregate_results", {})
    for method, metrics in accuracy_results.items():
        logger.info(f"{method}: confidence={metrics.get('avg_confidence', 0):.3f}, "
                   f"response_time={metrics.get('avg_response_time', 0):.3f}s")
    
    # Recommendations
    recommendations = results.get("recommendations", [])
    logger.info("Recommendations:")
    for rec in recommendations:
        logger.info(f"  - {rec}")
    
    # Export results
    filename = suite.export_results(results)
    logger.info(f"Results exported to: {filename}")
    
    logger.info("Phase 2C benchmarking test completed successfully")

if __name__ == "__main__":
    asyncio.run(main())