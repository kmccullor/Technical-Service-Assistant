#!/usr/bin/env python3
"""
Comprehensive System Validation Test

Tests all components of the Technical Service Assistant with proper performance constraints
and initialization time allowances.
"""

import logging
import os
import time
from typing import Any, Dict, List

import psycopg2
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SystemValidator:
    """Comprehensive system validation with performance monitoring."""

    def __init__(self):
        # Support remote deployments via RERANKER_URL environment variable
        self.base_url = os.getenv("RERANKER_URL", "http://localhost:8008")
        self.results = []
        self.performance_targets = {
            "health": 2,  # 2 seconds
            "fast_test": 5,  # 5 seconds
            "intelligent_route": 10,  # 10 seconds
            "chat_simple": 30,  # 30 seconds (with model loading)
            "reasoning_simple": 45,  # 45 seconds (first call with initialization)
        }

    def test_endpoint(
        self, name: str, method: str, endpoint: str, data: Dict = None, timeout: int = 30
    ) -> Dict[str, Any]:
        """Test an endpoint with timing and error handling."""
        logger.info(f"Testing {name}...")
        start_time = time.time()

        try:
            if method.upper() == "GET":
                response = requests.get(f"{self.base_url}{endpoint}", timeout=timeout)
            else:
                headers = {"Content-Type": "application/json"}
                response = requests.post(f"{self.base_url}{endpoint}", json=data, headers=headers, timeout=timeout)

            elapsed = time.time() - start_time

            result = {
                "name": name,
                "endpoint": endpoint,
                "status": "PASS" if response.status_code == 200 else "FAIL",
                "status_code": response.status_code,
                "response_time": round(elapsed, 2),
                "target_time": self.performance_targets.get(name.lower().replace(" ", "_").replace("-", "_"), timeout),
                "performance": (
                    "GOOD"
                    if elapsed
                    <= self.performance_targets.get(name.lower().replace(" ", "_").replace("-", "_"), timeout)
                    else "SLOW"
                ),
                "response_size": len(response.text) if response.text else 0,
                "error": None,
            }

            if response.status_code == 200:
                try:
                    result["response_preview"] = response.text[:200]
                except (UnicodeDecodeError, ValueError):
                    result["response_preview"] = "Binary or invalid response"
            else:
                result["error"] = response.text[:200]

        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            result = {
                "name": name,
                "endpoint": endpoint,
                "status": "TIMEOUT",
                "status_code": "TIMEOUT",
                "response_time": round(elapsed, 2),
                "target_time": timeout,
                "performance": "TIMEOUT",
                "response_size": 0,
                "error": f"Timeout after {timeout} seconds",
            }
        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                "name": name,
                "endpoint": endpoint,
                "status": "ERROR",
                "status_code": "ERROR",
                "response_time": round(elapsed, 2),
                "target_time": timeout,
                "performance": "ERROR",
                "response_size": 0,
                "error": str(e),
            }

        self.results.append(result)
        logger.info(f"{name}: {result['status']} ({result['response_time']}s)")
        return result

    def test_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity and basic operations."""
        logger.info("Testing database connectivity...")
        start_time = time.time()

        try:
            conn = psycopg2.connect(
                host="localhost", port=5432, database="postgres", user="postgres", password="postgres"
            )
            cursor = conn.cursor()

            # Test basic query
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]

            # Test vector extension
            cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            vector_ext = cursor.fetchone()

            # Test document chunks table
            cursor.execute("SELECT COUNT(*) FROM document_chunks")
            chunk_count = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            elapsed = time.time() - start_time

            result = {
                "name": "Database Connectivity",
                "status": "PASS",
                "response_time": round(elapsed, 2),
                "target_time": 5,
                "performance": "GOOD" if elapsed <= 5 else "SLOW",
                "details": {
                    "postgres_version": version[:50],
                    "vector_extension": "Present" if vector_ext else "Missing",
                    "document_chunks": chunk_count,
                },
                "error": None,
            }

        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                "name": "Database Connectivity",
                "status": "FAIL",
                "response_time": round(elapsed, 2),
                "target_time": 5,
                "performance": "ERROR",
                "details": {},
                "error": str(e),
            }

        self.results.append(result)
        logger.info(f"Database: {result['status']} ({result['response_time']}s)")
        return result

    def test_ollama_instances(self) -> List[Dict[str, Any]]:
        """Test all Ollama instances."""
        logger.info("Testing Ollama instances...")
        results = []

        instances = [("Ollama-1", 11434), ("Ollama-2", 11435), ("Ollama-3", 11436), ("Ollama-4", 11437)]

        for name, port in instances:
            start_time = time.time()
            try:
                response = requests.get(f"http://localhost:{port}/api/tags", timeout=10)
                elapsed = time.time() - start_time

                result = {
                    "name": name,
                    "port": port,
                    "status": "PASS" if response.status_code == 200 else "FAIL",
                    "response_time": round(elapsed, 2),
                    "target_time": 5,
                    "performance": "GOOD" if elapsed <= 5 else "SLOW",
                    "models": len(response.json().get("models", [])) if response.status_code == 200 else 0,
                    "error": None,
                }

            except Exception as e:
                elapsed = time.time() - start_time
                result = {
                    "name": name,
                    "port": port,
                    "status": "FAIL",
                    "response_time": round(elapsed, 2),
                    "target_time": 5,
                    "performance": "ERROR",
                    "models": 0,
                    "error": str(e),
                }

            results.append(result)
            self.results.append(result)
            logger.info(f"{name}: {result['status']} ({result['response_time']}s)")

        return results

    def run_all_tests(self):
        """Run comprehensive system validation."""
        logger.info("Starting comprehensive system validation...")
        logger.info("=" * 60)

        # 1. Test basic infrastructure
        logger.info("Phase 1: Infrastructure Tests")
        self.test_database_connectivity()
        self.test_ollama_instances()

        # 2. Test basic endpoints
        logger.info("\nPhase 2: Basic API Tests")
        self.test_endpoint("Health", "GET", "/health", timeout=5)
        self.test_endpoint("Fast-Test", "POST", "/api/fast-test", {"query": "test"}, timeout=5)

        # 3. Test intermediate complexity endpoints
        logger.info("\nPhase 3: Intermediate API Tests")
        self.test_endpoint(
            "Intelligent-Route", "POST", "/api/intelligent-route", {"query": "What is machine learning?"}, timeout=15
        )

        # 4. Test complex endpoints (with longer timeouts for initialization)
        logger.info("\nPhase 4: Complex API Tests (allowing for initialization)")
        self.test_endpoint("Chat-Simple", "POST", "/chat", {"message": "Hello"}, timeout=45)

        self.test_endpoint(
            "Reasoning-Simple",
            "POST",
            "/api/reasoning",
            {"query": "What is AI?", "reasoning_type": "analytical", "max_steps": 1},
            timeout=60,
        )

        # 5. Generate report
        self.generate_report()

    def generate_report(self):
        """Generate a comprehensive validation report."""
        logger.info("\n" + "=" * 60)
        logger.info("SYSTEM VALIDATION REPORT")
        logger.info("=" * 60)

        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["status"] == "PASS")
        failed_tests = sum(1 for r in self.results if r["status"] in ["FAIL", "ERROR", "TIMEOUT"])

        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        logger.info("\nDETAILED RESULTS:")
        logger.info("-" * 60)

        for result in self.results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            perf_icon = (
                "🟢" if result.get("performance") == "GOOD" else "🟡" if result.get("performance") == "SLOW" else "🔴"
            )

            logger.info(
                f"{status_icon} {perf_icon} {result['name']:<25} | "
                f"{result['response_time']:>6.2f}s | "
                f"Target: {result.get('target_time', 'N/A'):>4}s | "
                f"Status: {result['status']}"
            )

            if result.get("error"):
                logger.info(f"    Error: {result['error']}")

        # Performance Analysis
        logger.info(f"\nPERFORMANCE ANALYSIS:")
        logger.info("-" * 60)

        good_performance = sum(1 for r in self.results if r.get("performance") == "GOOD")
        slow_performance = sum(1 for r in self.results if r.get("performance") == "SLOW")

        logger.info(f"Within Performance Targets: {good_performance}/{total_tests}")
        logger.info(f"Slower Than Target: {slow_performance}/{total_tests}")

        # Critical Issues
        critical_issues = [r for r in self.results if r["status"] in ["FAIL", "ERROR", "TIMEOUT"]]
        if critical_issues:
            logger.info(f"\nCRITICAL ISSUES:")
            logger.info("-" * 60)
            for issue in critical_issues:
                logger.info(f"❗ {issue['name']}: {issue.get('error', 'Unknown error')}")

        # Recommendations
        logger.info(f"\nRECOMMENDATIONS:")
        logger.info("-" * 60)

        if failed_tests == 0:
            logger.info("✅ All systems operational - ready for Phase 3 development")
        else:
            logger.info("⚠️  Address critical issues before proceeding to Phase 3")

        slow_tests = [r for r in self.results if r.get("performance") == "SLOW"]
        if slow_tests:
            logger.info("🟡 Consider optimizing endpoints with slow performance")

        logger.info("📊 Monitor performance continuously during development")
        logger.info("🔧 Implement caching and optimization for complex reasoning operations")


if __name__ == "__main__":
    validator = SystemValidator()
    validator.run_all_tests()
