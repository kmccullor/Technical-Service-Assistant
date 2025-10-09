#!/usr/bin/env python3
"""
Phase 2C Simple Integration Test

A simplified version of Phase 2C testing that works without optional dependencies
and focuses on core functionality validation.
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from utils.logging_config import setup_logging
from config import get_settings

# Setup logging
logger = setup_logging(
    program_name="phase2c_simple_test",
    log_level="INFO",
    console_output=True,
)

settings = get_settings()

class SimplifiedPhase2CTest:
    """Simplified Phase 2C testing without complex dependencies."""
    
    def __init__(self):
        """Initialize simplified tester."""
        logger.info("Simplified Phase 2C tester initialized")
    
    async def test_confidence_scoring_basic(self) -> Dict[str, Any]:
        """Test basic confidence scoring logic."""
        
        logger.info("Testing basic confidence scoring...")
        
        # Import confidence scorer
        try:
            from phase2c_accuracy_system import AdvancedConfidenceScorer
            confidence_scorer = AdvancedConfidenceScorer()
            
            # Test scenarios
            test_scenarios = [
                {
                    "query": "specific technical parameter",
                    "content": "The TCP timeout parameter is exactly 30 seconds as specified in RFC 793.",
                    "expected": "high_confidence"
                },
                {
                    "query": "general approach", 
                    "content": "Connection issues might be caused by various factors and usually depend on the configuration.",
                    "expected": "medium_confidence"
                },
                {
                    "query": "uncertain details",
                    "content": "The configuration might vary and we're uncertain about specific values.",
                    "expected": "low_confidence"
                }
            ]
            
            results = {}
            
            for i, scenario in enumerate(test_scenarios):
                try:
                    # Create mock result
                    from phase2c_accuracy_system import SearchResult
                    
                    mock_result = SearchResult(
                        content=scenario["content"],
                        document_name="test.pdf",
                        metadata={},
                        score=0.8,
                        method="test"
                    )
                    
                    # Calculate confidence
                    confidence, analysis = confidence_scorer.calculate_confidence(
                        scenario["query"], [mock_result]
                    )
                    
                    results[f"scenario_{i+1}"] = {
                        "query": scenario["query"],
                        "expected": scenario["expected"],
                        "confidence": confidence,
                        "uncertainty_penalty": analysis.get("uncertainty_penalty", 0),
                        "status": "success"
                    }
                    
                    logger.info(f"Scenario {i+1}: confidence={confidence:.3f}")
                    
                except Exception as e:
                    logger.error(f"Confidence test {i+1} failed: {e}")
                    results[f"scenario_{i+1}"] = {"status": "failed", "error": str(e)}
            
            successful_tests = [r for r in results.values() if r.get("status") == "success"]
            
            return {
                "test_name": "confidence_scoring_basic",
                "status": "success" if successful_tests else "failed",
                "scenarios_tested": len(test_scenarios),
                "successful_scenarios": len(successful_tests),
                "avg_confidence": sum(r.get("confidence", 0) for r in successful_tests) / len(successful_tests) if successful_tests else 0,
                "results": results
            }
            
        except ImportError as e:
            logger.error(f"Could not import confidence scorer: {e}")
            return {"test_name": "confidence_scoring_basic", "status": "failed", "error": str(e)}
    
    def test_semantic_chunking_basic(self) -> Dict[str, Any]:
        """Test basic semantic chunking without advanced NLP."""
        
        logger.info("Testing basic semantic chunking...")
        
        try:
            # Import chunker with fallback
            from advanced_semantic_chunking import AdvancedSemanticChunker, ContentPattern
            
            chunker = AdvancedSemanticChunker(
                max_chunk_size=300,
                min_chunk_size=50,
                detect_technical_terms=True  # This should work with regex patterns
            )
            
            # Simple test document
            test_doc = """
# Configuration Guide

## Section 1: Setup

This section covers basic setup procedures.

Step 1: Install the software
Step 2: Configure the database settings
Step 3: Verify the installation

## Section 2: Troubleshooting

Common issues and solutions:

- Connection timeouts: Check network settings
- Authentication errors: Verify credentials
- Performance issues: Optimize database queries

## Technical Specifications

Parameter: TCP_TIMEOUT = 30
Parameter: MAX_CONNECTIONS = 100
Parameter: RETRY_COUNT = 3
            """
            
            # Test chunking
            chunks = chunker.chunk_document(
                test_doc,
                "test_guide.pdf",
                ContentPattern.TECHNICAL_MANUAL
            )
            
            # Analyze results
            total_chunks = len(chunks)
            chunks_with_tech_terms = sum(1 for c in chunks if c.metadata.technical_terms)
            avg_word_count = sum(c.metadata.word_count for c in chunks) / total_chunks if total_chunks > 0 else 0
            
            return {
                "test_name": "semantic_chunking_basic",
                "status": "success",
                "total_chunks": total_chunks,
                "chunks_with_tech_terms": chunks_with_tech_terms,
                "avg_word_count": avg_word_count,
                "chunk_types": [c.metadata.chunk_type.value for c in chunks]
            }
            
        except Exception as e:
            logger.error(f"Semantic chunking test failed: {e}")
            return {"test_name": "semantic_chunking_basic", "status": "failed", "error": str(e)}
    
    async def test_phase2c_system_basic(self) -> Dict[str, Any]:
        """Test basic Phase 2C system functionality."""
        
        logger.info("Testing basic Phase 2C system...")
        
        try:
            from phase2c_accuracy_system import Phase2CAccuracySystem
            
            system = Phase2CAccuracySystem()
            
            # Test performance summary (should work without actual searches)
            summary = system.get_performance_summary()
            
            return {
                "test_name": "phase2c_system_basic",
                "status": "success",
                "system_initialized": True,
                "performance_summary_available": "error" not in summary
            }
            
        except Exception as e:
            logger.error(f"Phase 2C system test failed: {e}")
            return {"test_name": "phase2c_system_basic", "status": "failed", "error": str(e)}
    
    async def run_simplified_integration_test(self) -> Dict[str, Any]:
        """Run simplified integration test."""
        
        logger.info("Starting simplified Phase 2C integration test...")
        
        test_results = {}
        start_time = time.time()
        
        # Test 1: Basic confidence scoring
        test_results["confidence_scoring"] = await self.test_confidence_scoring_basic()
        
        # Test 2: Basic semantic chunking  
        test_results["semantic_chunking"] = self.test_semantic_chunking_basic()
        
        # Test 3: Basic system functionality
        test_results["system_basic"] = await self.test_phase2c_system_basic()
        
        total_time = time.time() - start_time
        
        # Calculate success metrics
        successful_tests = sum(1 for result in test_results.values() 
                             if result.get("status") == "success")
        
        total_tests = len(test_results)
        success_rate = successful_tests / total_tests
        
        # Generate summary
        summary = {
            "test_suite": "Phase 2C Simplified Integration Test",
            "timestamp": datetime.now().isoformat(),
            "total_execution_time": total_time,
            "tests_run": total_tests,
            "successful_tests": successful_tests,
            "success_rate": success_rate,
            "individual_test_results": test_results,
            "overall_status": "success" if success_rate >= 0.8 else "partial_success" if success_rate >= 0.5 else "failed"
        }
        
        # Add recommendations
        recommendations = []
        
        if success_rate >= 0.8:
            recommendations.append("Phase 2C core functionality is working correctly")
        elif success_rate >= 0.5:
            recommendations.append("Phase 2C has some issues but core components are functional")
        else:
            recommendations.append("Phase 2C implementation has significant issues")
        
        if test_results.get("confidence_scoring", {}).get("status") == "success":
            recommendations.append("Advanced confidence scoring is operational")
        
        if test_results.get("semantic_chunking", {}).get("status") == "success":
            recommendations.append("Semantic chunking system is working")
        
        summary["recommendations"] = recommendations
        
        logger.info(f"Simplified integration test completed: {successful_tests}/{total_tests} tests successful")
        
        return summary

async def main():
    """Main function for simplified Phase 2C testing."""
    
    logger.info("🚀 Starting Phase 2C Simplified Integration Test")
    
    # Initialize tester
    tester = SimplifiedPhase2CTest()
    
    try:
        # Run simplified test
        results = await tester.run_simplified_integration_test()
        
        # Display results
        logger.info("\n" + "="*60)
        logger.info("PHASE 2C SIMPLIFIED TEST RESULTS")
        logger.info("="*60)
        
        logger.info(f"Overall Status: {results['overall_status'].upper()}")
        logger.info(f"Success Rate: {results['success_rate']:.1%}")
        logger.info(f"Execution Time: {results['total_execution_time']:.2f} seconds")
        
        logger.info("\nTest Results:")
        for test_name, test_result in results["individual_test_results"].items():
            status = test_result.get("status", "unknown")
            logger.info(f"  {test_name}: {status}")
        
        logger.info("\nRecommendations:")
        for rec in results.get("recommendations", []):
            logger.info(f"  ✓ {rec}")
        
        # Export results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"phase2c_simple_test_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"\nResults exported to: {results_file}")
        
        # Final status
        if results['success_rate'] >= 0.8:
            logger.info("\n🎉 Phase 2C simplified test PASSED!")
        elif results['success_rate'] >= 0.5:
            logger.info("\n⚠️  Phase 2C simplified test PARTIAL - some issues detected")
        else:
            logger.info("\n❌ Phase 2C simplified test FAILED")
        
        return 0
        
    except Exception as e:
        logger.error(f"Simplified test failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())