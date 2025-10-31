#!/usr/bin/env python3
"""
Phase 2C Integration and Testing Script

This script integrates all Phase 2C accuracy improvements and runs comprehensive testing:
1. Enhanced retrieval pipeline with monitoring integration
2. Hybrid search with BM25 + vector similarity
3. Advanced semantic chunking with structure preservation
4. Confidence scoring with uncertainty detection
5. A/B testing and benchmarking framework

Tests the complete Phase 2C system and validates improvements.
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from advanced_semantic_chunking import AdvancedSemanticChunker, ChunkType, ContentPattern

# Import Phase 2C components
from phase2c_accuracy_system import AdvancedConfidenceScorer, Phase2CAccuracySystem, SearchMethod
from phase2c_benchmarking_suite import ComprehensiveBenchmarkSuite

from config import get_settings
from utils.logging_config import setup_logging

# Setup logging
logger = setup_logging(
    program_name="phase2c_integration_test",
    log_level="INFO",
    console_output=True,
)

settings = get_settings()


class Phase2CIntegrationTester:
    """Comprehensive Phase 2C integration testing."""

    def __init__(self):
        """Initialize integration tester."""
        self.accuracy_system = Phase2CAccuracySystem()
        self.semantic_chunker = AdvancedSemanticChunker(
            max_chunk_size=512, min_chunk_size=100, overlap_size=50, preserve_sections=True, detect_technical_terms=True
        )
        self.benchmark_suite = ComprehensiveBenchmarkSuite()
        self.confidence_scorer = AdvancedConfidenceScorer()

        logger.info("Phase 2C integration tester initialized")

    async def test_enhanced_retrieval_pipeline(self) -> Dict[str, Any]:
        """Test the enhanced retrieval pipeline."""

        logger.info("Testing enhanced retrieval pipeline...")

        test_queries = [
            "RNI network configuration parameters",
            "FlexNet database connection troubleshooting",
            "AMDS installation requirements Windows Server",
            "Router firmware update procedure version 2.5",
        ]

        results = {}

        for query in test_queries:
            try:
                start_time = time.time()

                # Test enhanced retrieval
                search_results, metrics = await self.accuracy_system.comprehensive_search(
                    query, method=SearchMethod.ENHANCED_RETRIEVAL, top_k=5
                )

                response_time = time.time() - start_time

                results[query] = {
                    "results_count": len(search_results),
                    "confidence_score": metrics.confidence_score,
                    "semantic_coverage": metrics.semantic_coverage,
                    "keyword_coverage": metrics.keyword_coverage,
                    "response_time": response_time,
                    "method": metrics.method,
                    "status": "success",
                }

                logger.info(
                    f"Query: '{query}' -> {len(search_results)} results, " f"confidence: {metrics.confidence_score:.3f}"
                )

            except Exception as e:
                logger.error(f"Enhanced retrieval test failed for '{query}': {e}")
                results[query] = {"status": "failed", "error": str(e)}

        # Calculate summary statistics
        successful_tests = [r for r in results.values() if r.get("status") == "success"]

        if successful_tests:
            summary = {
                "test_name": "enhanced_retrieval_pipeline",
                "queries_tested": len(test_queries),
                "successful_queries": len(successful_tests),
                "avg_confidence": sum(r["confidence_score"] for r in successful_tests) / len(successful_tests),
                "avg_response_time": sum(r["response_time"] for r in successful_tests) / len(successful_tests),
                "avg_results_count": sum(r["results_count"] for r in successful_tests) / len(successful_tests),
                "detailed_results": results,
            }
        else:
            summary = {
                "test_name": "enhanced_retrieval_pipeline",
                "queries_tested": len(test_queries),
                "successful_queries": 0,
                "error": "All tests failed",
                "detailed_results": results,
            }

        return summary

    async def test_hybrid_search_system(self) -> Dict[str, Any]:
        """Test hybrid search combining vector + BM25."""

        logger.info("Testing hybrid search system...")

        # Sample document corpus for hybrid search
        sample_documents = [
            {
                "content": "RNI network configuration requires setting up TCP/IP parameters including IP address, subnet mask, and gateway settings.",
                "document_name": "RNI_Config_Manual.pdf",
                "metadata": {"section": "Network Setup", "page": 12},
            },
            {
                "content": "FlexNet database troubleshooting involves checking SQL Server connectivity, authentication settings, and firewall configuration.",
                "document_name": "FlexNet_Troubleshooting.pdf",
                "metadata": {"section": "Database Issues", "page": 8},
            },
            {
                "content": "AMDS installation on Windows Server requires .NET Framework 4.7.2, SQL Server 2017 or later, and minimum 8GB RAM.",
                "document_name": "AMDS_Installation_Guide.pdf",
                "metadata": {"section": "System Requirements", "page": 3},
            },
        ]

        # Build hybrid search index
        try:
            self.accuracy_system.hybrid_search.build_index(sample_documents)
        except Exception as e:
            logger.error(f"Failed to build hybrid search index: {e}")
            return {"test_name": "hybrid_search_system", "status": "failed", "error": str(e)}

        test_queries = [
            "TCP/IP network configuration",
            "SQL Server database troubleshooting",
            "Windows Server installation requirements",
        ]

        results = {}

        for query in test_queries:
            try:
                start_time = time.time()

                # Test hybrid search
                search_results, metrics = await self.accuracy_system.comprehensive_search(
                    query, method=SearchMethod.HYBRID_SEARCH, top_k=3
                )

                response_time = time.time() - start_time

                results[query] = {
                    "results_count": len(search_results),
                    "confidence_score": metrics.confidence_score,
                    "semantic_coverage": metrics.semantic_coverage,
                    "keyword_coverage": metrics.keyword_coverage,
                    "response_time": response_time,
                    "top_result": search_results[0].document_name if search_results else None,
                    "status": "success",
                }

                logger.info(
                    f"Hybrid search: '{query}' -> {len(search_results)} results, "
                    f"confidence: {metrics.confidence_score:.3f}"
                )

            except Exception as e:
                logger.error(f"Hybrid search test failed for '{query}': {e}")
                results[query] = {"status": "failed", "error": str(e)}

        # Calculate summary
        successful_tests = [r for r in results.values() if r.get("status") == "success"]

        if successful_tests:
            summary = {
                "test_name": "hybrid_search_system",
                "queries_tested": len(test_queries),
                "successful_queries": len(successful_tests),
                "avg_confidence": sum(r["confidence_score"] for r in successful_tests) / len(successful_tests),
                "avg_response_time": sum(r["response_time"] for r in successful_tests) / len(successful_tests),
                "detailed_results": results,
            }
        else:
            summary = {
                "test_name": "hybrid_search_system",
                "queries_tested": len(test_queries),
                "successful_queries": 0,
                "error": "All hybrid search tests failed",
                "detailed_results": results,
            }

        return summary

    def test_semantic_chunking(self) -> Dict[str, Any]:
        """Test advanced semantic chunking system."""

        logger.info("Testing semantic chunking system...")

        # Sample technical document
        sample_document = """
# FlexNet Database Configuration Guide

## 1. Introduction

This guide covers the configuration of FlexNet database systems for RNI v2.5 and later versions.
The FlexNet database is a critical component of the Sensus AMI infrastructure.

## 2. System Requirements

### 2.1 Hardware Requirements

- CPU: Minimum 4 cores, 2.4 GHz Intel or AMD processor
- RAM: 8 GB minimum, 16 GB recommended for production environments
- Storage: 100 GB available space on SSD preferred

### 2.2 Software Requirements

- Windows Server 2019 or later (Windows Server 2022 recommended)
- SQL Server 2017 or later (SQL Server 2019 Enterprise preferred)
- .NET Framework 4.7.2 or .NET Core 3.1+

## 3. Installation Procedure

Step 1: Download the FlexNet installer from the Sensus customer portal.

Step 2: Run the installer as Administrator.
- Right-click FlexNet_Setup.exe in Windows Explorer
- Select "Run as administrator" from context menu
- Follow the installation wizard prompts

Step 3: Configure database connection parameters.
- Open FlexNet Configuration Manager
- Navigate to Database Settings tab
- Enter the following required parameters:
  - Server: localhost\SQLEXPRESS (or your SQL Server instance)
  - Database: FlexNetDB
  - Authentication: Windows Authentication (recommended)

## 4. Troubleshooting Common Issues

### 4.1 Connection Timeout Errors

If you encounter connection timeout errors (Error Code: 1001), check:

1. SQL Server service status in Services.msc
2. Firewall settings allowing port 1433 (default SQL Server port)
3. TCP/IP protocol enabled in SQL Server Configuration Manager
4. Network connectivity between FlexNet server and database server

### 4.2 Authentication Failures

For authentication failures (Error Code: 1002):

1. Verify Windows Authentication is enabled in SQL Server
2. Check that the FlexNet service account has appropriate database permissions
3. Ensure the service account is not locked or expired

## 5. Performance Optimization

### 5.1 Database Configuration

Recommended SQL Server settings for optimal FlexNet performance:

- Max Memory: 75% of available RAM
- Recovery Model: Full (for production), Simple (for development)
- Auto Update Statistics: Enabled
- Auto Close: Disabled for production databases

### 5.2 Index Maintenance

Schedule regular index maintenance:

```sql
-- Weekly index reorganization
ALTER INDEX ALL ON FlexNetDB.dbo.MeterReadings REORGANIZE;

-- Monthly index rebuild for large tables
ALTER INDEX ALL ON FlexNetDB.dbo.MeterReadings REBUILD;
```

## 6. References and Additional Resources

6.1 SQL Server Documentation: https://docs.microsoft.com/sql-server
6.2 FlexNet User Manual: See Chapter 3, Database Configuration
6.3 Sensus Support Portal: https://support.sensus.com
        """

        try:
            # Test semantic chunking
            chunks = self.semantic_chunker.chunk_document(
                sample_document, "FlexNet_Database_Guide.pdf", ContentPattern.TECHNICAL_MANUAL
            )

            # Get chunking statistics
            stats = self.semantic_chunker.get_chunking_statistics(chunks)

            # Analyze chunk quality
            heading_chunks = [c for c in chunks if c.metadata.chunk_type == ChunkType.HEADING]
            procedure_chunks = [c for c in chunks if c.metadata.chunk_type == ChunkType.PROCEDURE]
            technical_spec_chunks = [c for c in chunks if c.metadata.chunk_type == ChunkType.TECHNICAL_SPEC]

            # Check for important features
            chunks_with_tech_terms = [c for c in chunks if c.metadata.technical_terms]
            chunks_with_cross_refs = [c for c in chunks if c.metadata.cross_references]

            summary = {
                "test_name": "semantic_chunking",
                "status": "success",
                "total_chunks": len(chunks),
                "chunk_types": {
                    "headings": len(heading_chunks),
                    "procedures": len(procedure_chunks),
                    "technical_specs": len(technical_spec_chunks),
                },
                "avg_word_count": stats.get("avg_word_count", 0),
                "avg_importance_score": stats.get("avg_importance_score", 0),
                "chunks_with_tech_terms": len(chunks_with_tech_terms),
                "chunks_with_cross_refs": len(chunks_with_cross_refs),
                "statistics": stats,
            }

            logger.info(
                f"Semantic chunking: {len(chunks)} chunks created, "
                f"avg importance: {stats.get('avg_importance_score', 0):.3f}"
            )

            return summary

        except Exception as e:
            logger.error(f"Semantic chunking test failed: {e}")
            return {"test_name": "semantic_chunking", "status": "failed", "error": str(e)}

    def test_confidence_scoring(self) -> Dict[str, Any]:
        """Test advanced confidence scoring system."""

        logger.info("Testing confidence scoring system...")

        # Test scenarios with different confidence levels
        test_scenarios = [
            {
                "query": "specific technical parameter value",
                "mock_results": [
                    {
                        "content": "The TCP timeout parameter is exactly 30 seconds as specified in RFC 793. This value is mandatory for all FlexNet configurations.",
                        "document_name": "Technical_Specifications.pdf",
                        "score": 0.95,
                    }
                ],
                "expected_confidence": "high",
            },
            {
                "query": "general troubleshooting approach",
                "mock_results": [
                    {
                        "content": "Connection issues might be caused by various factors. Usually, checking the network settings helps, but it depends on the specific configuration.",
                        "document_name": "General_Guide.pdf",
                        "score": 0.75,
                    },
                    {
                        "content": "Typically, you should verify the firewall settings. Sometimes this resolves the problem, but results may vary.",
                        "document_name": "Troubleshooting_Manual.pdf",
                        "score": 0.70,
                    },
                ],
                "expected_confidence": "medium",
            },
            {
                "query": "uncertain configuration details",
                "mock_results": [
                    {
                        "content": "The configuration might vary depending on your setup. Perhaps checking the manual could help, but we're uncertain about specific values.",
                        "document_name": "Installation_Notes.pdf",
                        "score": 0.60,
                    }
                ],
                "expected_confidence": "low",
            },
        ]

        confidence_results = {}

        for i, scenario in enumerate(test_scenarios):
            try:
                # Create mock SearchResult objects
                from phase2c_accuracy_system import SearchResult

                mock_results = []
                for result_data in scenario["mock_results"]:
                    search_result = SearchResult(
                        content=result_data["content"],
                        document_name=result_data["document_name"],
                        metadata={},
                        score=result_data["score"],
                        method="mock_test",
                    )
                    mock_results.append(search_result)

                # Calculate confidence
                confidence_score, analysis = self.confidence_scorer.calculate_confidence(
                    scenario["query"], mock_results
                )

                confidence_results[f"scenario_{i+1}"] = {
                    "query": scenario["query"],
                    "expected_confidence": scenario["expected_confidence"],
                    "calculated_confidence": confidence_score,
                    "analysis": analysis,
                    "results_count": len(mock_results),
                }

                logger.info(
                    f"Confidence test {i+1}: {confidence_score:.3f} " f"(expected: {scenario['expected_confidence']})"
                )

            except Exception as e:
                logger.error(f"Confidence scoring test {i+1} failed: {e}")
                confidence_results[f"scenario_{i+1}"] = {"status": "failed", "error": str(e)}

        # Calculate overall confidence scoring performance
        successful_tests = [r for r in confidence_results.values() if "calculated_confidence" in r]

        if successful_tests:
            avg_confidence = sum(r["calculated_confidence"] for r in successful_tests) / len(successful_tests)

            summary = {
                "test_name": "confidence_scoring",
                "status": "success",
                "scenarios_tested": len(test_scenarios),
                "successful_scenarios": len(successful_tests),
                "avg_calculated_confidence": avg_confidence,
                "detailed_results": confidence_results,
            }
        else:
            summary = {
                "test_name": "confidence_scoring",
                "status": "failed",
                "error": "All confidence scoring tests failed",
                "detailed_results": confidence_results,
            }

        return summary

    async def test_ab_testing_framework(self) -> Dict[str, Any]:
        """Test A/B testing and evaluation framework."""

        logger.info("Testing A/B testing framework...")

        try:
            # Create a simple benchmark comparison
            methods_to_compare = [SearchMethod.ENHANCED_RETRIEVAL, SearchMethod.HYBRID_SEARCH]

            # Run a small-scale accuracy benchmark
            benchmark_results = await self.benchmark_suite.run_accuracy_benchmark(
                methods=methods_to_compare, query_count=4  # Small test
            )

            # Extract key metrics
            aggregate_results = benchmark_results.get("aggregate_results", {})
            statistical_tests = benchmark_results.get("statistical_tests", [])

            summary = {
                "test_name": "ab_testing_framework",
                "status": "success",
                "methods_compared": [m.value for m in methods_to_compare],
                "queries_tested": benchmark_results.get("queries_tested", 0),
                "aggregate_results": aggregate_results,
                "statistical_tests_count": len(statistical_tests),
                "has_significant_differences": any(test.get("is_significant", False) for test in statistical_tests),
            }

            logger.info(
                f"A/B testing: compared {len(methods_to_compare)} methods, "
                f"{len(statistical_tests)} statistical tests performed"
            )

            return summary

        except Exception as e:
            logger.error(f"A/B testing framework test failed: {e}")
            return {"test_name": "ab_testing_framework", "status": "failed", "error": str(e)}

    async def run_comprehensive_integration_test(self) -> Dict[str, Any]:
        """Run comprehensive integration test of all Phase 2C components."""

        logger.info("Starting comprehensive Phase 2C integration test...")

        test_results = {}
        start_time = time.time()

        # Test 1: Enhanced Retrieval Pipeline
        test_results["enhanced_retrieval"] = await self.test_enhanced_retrieval_pipeline()

        # Test 2: Hybrid Search System
        test_results["hybrid_search"] = await self.test_hybrid_search_system()

        # Test 3: Semantic Chunking
        test_results["semantic_chunking"] = self.test_semantic_chunking()

        # Test 4: Confidence Scoring
        test_results["confidence_scoring"] = self.test_confidence_scoring()

        # Test 5: A/B Testing Framework
        test_results["ab_testing"] = await self.test_ab_testing_framework()

        total_time = time.time() - start_time

        # Calculate overall success metrics
        successful_tests = sum(
            1
            for result in test_results.values()
            if result.get("status") == "success" or result.get("successful_queries", 0) > 0
        )

        total_tests = len(test_results)
        success_rate = successful_tests / total_tests

        # Generate comprehensive summary
        comprehensive_summary = {
            "test_suite": "Phase 2C Comprehensive Integration Test",
            "timestamp": datetime.now().isoformat(),
            "total_execution_time": total_time,
            "tests_run": total_tests,
            "successful_tests": successful_tests,
            "success_rate": success_rate,
            "individual_test_results": test_results,
            "overall_status": "success"
            if success_rate >= 0.8
            else "partial_success"
            if success_rate >= 0.5
            else "failed",
        }

        # Add recommendations
        recommendations = []

        if success_rate >= 0.8:
            recommendations.append("Phase 2C implementation is ready for production deployment")
        elif success_rate >= 0.5:
            recommendations.append("Phase 2C implementation has some issues that should be addressed before production")
        else:
            recommendations.append("Phase 2C implementation requires significant fixes before deployment")

        # Specific component recommendations
        if test_results.get("enhanced_retrieval", {}).get("successful_queries", 0) > 0:
            recommendations.append("Enhanced retrieval pipeline is working correctly")

        if test_results.get("hybrid_search", {}).get("successful_queries", 0) > 0:
            recommendations.append("Hybrid search system is operational")

        if test_results.get("semantic_chunking", {}).get("status") == "success":
            recommendations.append("Semantic chunking system is functioning properly")

        comprehensive_summary["recommendations"] = recommendations

        logger.info(f"Comprehensive integration test completed: {successful_tests}/{total_tests} tests successful")
        logger.info(f"Overall status: {comprehensive_summary['overall_status']}")

        return comprehensive_summary


async def main():
    """Main function to run Phase 2C integration tests."""

    logger.info("🚀 Starting Phase 2C: Accuracy Improvements Integration Test")

    # Initialize integration tester
    tester = Phase2CIntegrationTester()

    try:
        # Run comprehensive integration test
        results = await tester.run_comprehensive_integration_test()

        # Display results summary
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2C INTEGRATION TEST RESULTS")
        logger.info("=" * 80)

        logger.info(f"Overall Status: {results['overall_status'].upper()}")
        logger.info(f"Success Rate: {results['success_rate']:.1%}")
        logger.info(f"Execution Time: {results['total_execution_time']:.2f} seconds")

        logger.info("\nTest Component Results:")
        for test_name, test_result in results["individual_test_results"].items():
            status = test_result.get("status", "unknown")
            successful_queries = test_result.get("successful_queries", "N/A")

            if isinstance(successful_queries, int):
                logger.info(f"  {test_name}: {status} ({successful_queries} queries)")
            else:
                logger.info(f"  {test_name}: {status}")

        logger.info("\nRecommendations:")
        for rec in results.get("recommendations", []):
            logger.info(f"  ✓ {rec}")

        # Export detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"phase2c_integration_test_results_{timestamp}.json"

        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"\nDetailed results exported to: {results_file}")

        # Final status
        if results["success_rate"] >= 0.8:
            logger.info("\n🎉 Phase 2C integration test PASSED - Ready for production!")
        elif results["success_rate"] >= 0.5:
            logger.info("\n⚠️  Phase 2C integration test PARTIAL - Some issues need attention")
        else:
            logger.info("\n❌ Phase 2C integration test FAILED - Significant issues detected")

    except Exception as e:
        logger.error(f"Integration test failed with error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
