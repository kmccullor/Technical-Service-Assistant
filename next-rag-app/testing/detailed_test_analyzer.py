#!/usr/bin/env python3
"""
Detailed Analysis of RAG System Test Results
Examines failures, performance bottlenecks, and provides optimization recommendations
"""

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class RAGTestAnalyzer:
    def __init__(self, report_file: str):
        """Initialize analyzer with test report"""
        self.report_file = report_file
        self.report = self.load_report()

    def load_report(self) -> Dict[str, Any]:
        """Load the test report JSON"""
        try:
            with open(self.report_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading report: {e}")
            return {}

    def analyze_failed_tests(self) -> Dict[str, Any]:
        """Analyze all failed tests to identify patterns"""
        failed_tests = []

        for suite_name, suite_data in self.report.get("detailed_results", {}).items():
            for test in suite_data.get("individual_results", []):
                if not test.get("success", True):
                    failed_tests.append(
                        {
                            "suite": suite_name,
                            "test_name": test.get("test_name"),
                            "question": test.get("question"),
                            "error_message": test.get("error_message"),
                            "response_time": test.get("response_time", 0),
                            "sources_found": test.get("sources_found", 0),
                            "confidence_score": test.get("confidence_score"),
                        }
                    )

        # Categorize failures
        failure_categories = {
            "timeout_errors": [],
            "no_response_errors": [],
            "api_errors": [],
            "low_confidence": [],
            "other_errors": [],
        }

        for test in failed_tests:
            error_msg = test.get("error_message", "").lower()
            response_time = test.get("response_time", 0)

            if "timeout" in error_msg or response_time > 30:
                failure_categories["timeout_errors"].append(test)
            elif "connection" in error_msg or "refused" in error_msg:
                failure_categories["no_response_errors"].append(test)
            elif "status" in error_msg or "code" in error_msg:
                failure_categories["api_errors"].append(test)
            elif test.get("confidence_score") and test["confidence_score"] < 0.01:
                failure_categories["low_confidence"].append(test)
            else:
                failure_categories["other_errors"].append(test)

        return {
            "total_failed": len(failed_tests),
            "failed_tests": failed_tests,
            "failure_categories": failure_categories,
            "failure_patterns": self.identify_failure_patterns(failed_tests),
        }

    def identify_failure_patterns(self, failed_tests: List[Dict]) -> Dict[str, Any]:
        """Identify patterns in failed tests"""
        patterns = {
            "common_error_messages": {},
            "question_types_failing": {},
            "response_time_distribution": [],
            "suites_with_most_failures": {},
        }

        for test in failed_tests:
            # Count error message patterns
            error = test.get("error_message", "Unknown")
            patterns["common_error_messages"][error] = patterns["common_error_messages"].get(error, 0) + 1

            # Analyze question types
            question = test.get("question", "").lower()
            if "what" in question:
                question_type = "What questions"
            elif "how" in question:
                question_type = "How questions"
            elif "configure" in question or "configuration" in question:
                question_type = "Configuration questions"
            elif "install" in question or "installation" in question:
                question_type = "Installation questions"
            else:
                question_type = "Other questions"

            patterns["question_types_failing"][question_type] = (
                patterns["question_types_failing"].get(question_type, 0) + 1
            )

            # Response times
            patterns["response_time_distribution"].append(test.get("response_time", 0))

            # Suite failure counts
            suite = test.get("suite", "Unknown")
            patterns["suites_with_most_failures"][suite] = patterns["suites_with_most_failures"].get(suite, 0) + 1

        return patterns

    def analyze_performance_issues(self) -> Dict[str, Any]:
        """Analyze performance bottlenecks"""
        all_response_times = []
        slow_tests = []

        for suite_name, suite_data in self.report.get("detailed_results", {}).items():
            for test in suite_data.get("individual_results", []):
                response_time = test.get("response_time", 0)
                all_response_times.append(response_time)

                if response_time > 10:  # Tests taking more than 10 seconds
                    slow_tests.append(
                        {
                            "suite": suite_name,
                            "test_name": test.get("test_name"),
                            "question": test.get("question"),
                            "response_time": response_time,
                            "sources_found": test.get("sources_found", 0),
                            "success": test.get("success", False),
                        }
                    )

        # Performance metrics
        performance_analysis = {
            "avg_response_time": statistics.mean(all_response_times) if all_response_times else 0,
            "median_response_time": statistics.median(all_response_times) if all_response_times else 0,
            "max_response_time": max(all_response_times) if all_response_times else 0,
            "min_response_time": min(all_response_times) if all_response_times else 0,
            "tests_over_5s": len([t for t in all_response_times if t > 5]),
            "tests_over_10s": len([t for t in all_response_times if t > 10]),
            "tests_over_20s": len([t for t in all_response_times if t > 20]),
            "slow_tests": slow_tests,
            "response_time_percentiles": self.calculate_percentiles(all_response_times),
        }

        return performance_analysis

    def calculate_percentiles(self, data: List[float]) -> Dict[str, float]:
        """Calculate response time percentiles"""
        if not data:
            return {}

        sorted_data = sorted(data)
        n = len(sorted_data)

        return {
            "p50": sorted_data[int(0.5 * n)] if n > 0 else 0,
            "p75": sorted_data[int(0.75 * n)] if n > 0 else 0,
            "p90": sorted_data[int(0.9 * n)] if n > 0 else 0,
            "p95": sorted_data[int(0.95 * n)] if n > 0 else 0,
            "p99": sorted_data[int(0.99 * n)] if n > 0 else 0,
        }

    def analyze_confidence_scores(self) -> Dict[str, Any]:
        """Analyze confidence score patterns"""
        confidence_scores = []
        low_confidence_tests = []

        for suite_name, suite_data in self.report.get("detailed_results", {}).items():
            for test in suite_data.get("individual_results", []):
                confidence = test.get("confidence_score")
                if confidence is not None:
                    confidence_scores.append(confidence)

                    if confidence < 0.01:  # Very low confidence
                        low_confidence_tests.append(
                            {
                                "suite": suite_name,
                                "test_name": test.get("test_name"),
                                "question": test.get("question"),
                                "confidence_score": confidence,
                                "sources_found": test.get("sources_found", 0),
                                "success": test.get("success", False),
                            }
                        )

        return {
            "avg_confidence": statistics.mean(confidence_scores) if confidence_scores else 0,
            "median_confidence": statistics.median(confidence_scores) if confidence_scores else 0,
            "min_confidence": min(confidence_scores) if confidence_scores else 0,
            "max_confidence": max(confidence_scores) if confidence_scores else 0,
            "tests_with_very_low_confidence": len(low_confidence_tests),
            "low_confidence_tests": low_confidence_tests,
            "confidence_distribution": self.calculate_percentiles(confidence_scores),
        }

    def analyze_source_retrieval(self) -> Dict[str, Any]:
        """Analyze source retrieval effectiveness"""
        tests_with_sources = 0
        tests_without_sources = 0
        source_counts = []

        for suite_name, suite_data in self.report.get("detailed_results", {}).items():
            for test in suite_data.get("individual_results", []):
                sources = test.get("sources_found", 0)
                source_counts.append(sources)

                if sources > 0:
                    tests_with_sources += 1
                else:
                    tests_without_sources += 1

        return {
            "tests_with_sources": tests_with_sources,
            "tests_without_sources": tests_without_sources,
            "source_retrieval_rate": (tests_with_sources / (tests_with_sources + tests_without_sources)) * 100
            if (tests_with_sources + tests_without_sources) > 0
            else 0,
            "avg_sources_per_test": statistics.mean(source_counts) if source_counts else 0,
            "max_sources_found": max(source_counts) if source_counts else 0,
        }

    def generate_recommendations(
        self, failure_analysis: Dict, performance_analysis: Dict, confidence_analysis: Dict
    ) -> List[str]:
        """Generate specific recommendations based on analysis"""
        recommendations = []

        # Performance recommendations
        if performance_analysis["avg_response_time"] > 10:
            recommendations.append("🚨 CRITICAL: Average response time (19s+) is too high. Consider:")
            recommendations.append("   • Optimize Ollama model configuration for faster inference")
            recommendations.append("   • Implement response caching for common queries")
            recommendations.append("   • Add request queuing and load balancing")
            recommendations.append("   • Profile and optimize database query performance")

        # Failure pattern recommendations
        if failure_analysis["total_failed"] > 10:
            most_common_error = (
                max(failure_analysis["failure_patterns"]["common_error_messages"].items(), key=lambda x: x[1])[0]
                if failure_analysis["failure_patterns"]["common_error_messages"]
                else None
            )
            if most_common_error:
                recommendations.append(f"🔧 Address most common error: '{most_common_error}'")

        # Confidence score recommendations
        if confidence_analysis["avg_confidence"] < 0.05:
            recommendations.append("📊 CONFIDENCE: Very low confidence scores indicate:")
            recommendations.append("   • Possible embedding model mismatch with search queries")
            recommendations.append("   • Need to retune confidence threshold (currently 0.01)")
            recommendations.append("   • Consider hybrid search improvements")
            recommendations.append("   • Evaluate document chunking strategy")

        # Source retrieval recommendations
        if len(failure_analysis["failure_categories"]["no_response_errors"]) > 0:
            recommendations.append("🔌 CONNECTION: Multiple connection errors detected:")
            recommendations.append("   • Check Docker container health and networking")
            recommendations.append("   • Verify Ollama service stability")
            recommendations.append("   • Implement retry logic with exponential backoff")

        # Load testing recommendations
        if performance_analysis["tests_over_20s"] > 5:
            recommendations.append("⚡ PERFORMANCE: Many slow tests detected:")
            recommendations.append("   • Implement async processing for heavy operations")
            recommendations.append("   • Add request timeouts and circuit breakers")
            recommendations.append("   • Consider horizontal scaling for Ollama instances")

        return recommendations

    def create_detailed_analysis_report(self) -> Dict[str, Any]:
        """Create comprehensive analysis report"""
        failure_analysis = self.analyze_failed_tests()
        performance_analysis = self.analyze_performance_issues()
        confidence_analysis = self.analyze_confidence_scores()
        source_analysis = self.analyze_source_retrieval()
        recommendations = self.generate_recommendations(failure_analysis, performance_analysis, confidence_analysis)

        return {
            "report_metadata": {
                "analysis_timestamp": datetime.now().isoformat(),
                "original_report_file": self.report_file,
                "test_execution_time": self.report.get("timestamp", "Unknown"),
            },
            "failure_analysis": failure_analysis,
            "performance_analysis": performance_analysis,
            "confidence_analysis": confidence_analysis,
            "source_retrieval_analysis": source_analysis,
            "recommendations": recommendations,
            "executive_summary": self.create_executive_summary(
                failure_analysis, performance_analysis, confidence_analysis
            ),
        }

    def create_executive_summary(
        self, failure_analysis: Dict, performance_analysis: Dict, confidence_analysis: Dict
    ) -> Dict[str, Any]:
        """Create executive summary of findings"""
        total_tests = self.report.get("test_summary", {}).get("total_tests", 0)
        success_rate = self.report.get("test_summary", {}).get("success_rate", 0)

        # Determine overall system health
        if success_rate >= 95 and performance_analysis["avg_response_time"] <= 5:
            health_status = "EXCELLENT"
        elif success_rate >= 85 and performance_analysis["avg_response_time"] <= 10:
            health_status = "GOOD"
        elif success_rate >= 70 and performance_analysis["avg_response_time"] <= 20:
            health_status = "NEEDS_IMPROVEMENT"
        else:
            health_status = "CRITICAL"

        return {
            "overall_health": health_status,
            "total_tests_executed": total_tests,
            "success_rate_percentage": success_rate,
            "avg_response_time_seconds": performance_analysis["avg_response_time"],
            "primary_issues": [
                f"{failure_analysis['total_failed']} failed tests" if failure_analysis["total_failed"] > 0 else None,
                f"Slow response times ({performance_analysis['avg_response_time']:.1f}s avg)"
                if performance_analysis["avg_response_time"] > 5
                else None,
                f"Low confidence scores ({confidence_analysis['avg_confidence']:.3f} avg)"
                if confidence_analysis["avg_confidence"] < 0.05
                else None,
            ],
            "key_strengths": [
                f"{self.report.get('test_summary', {}).get('sources_stats', {}).get('tests_with_sources', 0)} tests successfully retrieved sources",
                f"System handled {total_tests} comprehensive tests",
                f"Multiple test categories passed (API health, search, edge cases)",
            ],
        }

    def print_analysis_summary(self, analysis: Dict[str, Any]):
        """Print a formatted summary of the analysis"""
        print("\n" + "=" * 80)
        print("🔍 DETAILED RAG SYSTEM ANALYSIS")
        print("=" * 80)

        # Executive Summary
        summary = analysis["executive_summary"]
        print(f"\n📊 OVERALL SYSTEM HEALTH: {summary['overall_health']}")
        print(f"   Total Tests: {summary['total_tests_executed']}")
        print(f"   Success Rate: {summary['success_rate_percentage']:.1f}%")
        print(f"   Avg Response Time: {summary['avg_response_time_seconds']:.1f}s")

        # Primary Issues
        print(f"\n⚠️ PRIMARY ISSUES:")
        for issue in summary["primary_issues"]:
            if issue:
                print(f"   • {issue}")

        # Key Strengths
        print(f"\n✅ KEY STRENGTHS:")
        for strength in summary["key_strengths"]:
            print(f"   • {strength}")

        # Failure Analysis
        failure = analysis["failure_analysis"]
        if failure["total_failed"] > 0:
            print(f"\n❌ FAILURE BREAKDOWN:")
            print(f"   Total Failed: {failure['total_failed']}")
            for category, tests in failure["failure_categories"].items():
                if tests:
                    print(f"   {category.replace('_', ' ').title()}: {len(tests)}")

        # Performance Analysis
        perf = analysis["performance_analysis"]
        print(f"\n⏱️ PERFORMANCE ANALYSIS:")
        print(f"   Average Response Time: {perf['avg_response_time']:.2f}s")
        print(f"   Tests over 10s: {perf['tests_over_10s']}")
        print(f"   Tests over 20s: {perf['tests_over_20s']}")
        print(f"   95th Percentile: {perf['response_time_percentiles'].get('p95', 0):.2f}s")

        # Confidence Analysis
        conf = analysis["confidence_analysis"]
        print(f"\n📈 CONFIDENCE ANALYSIS:")
        print(f"   Average Confidence: {conf['avg_confidence']:.4f}")
        print(f"   Tests with Very Low Confidence: {conf['tests_with_very_low_confidence']}")
        print(f"   Max Confidence Achieved: {conf['max_confidence']:.4f}")

        # Recommendations
        print(f"\n🔧 RECOMMENDATIONS:")
        for rec in analysis["recommendations"]:
            print(f"   {rec}")

        print("\n" + "=" * 80)


def main():
    """Main execution function"""
    # Find the most recent test report
    testing_dir = Path("/home/kmccullor/Projects/Technical-Service-Assistant/next-rag-app/testing")
    report_files = list(testing_dir.glob("comprehensive_test_report_*.json"))

    if not report_files:
        print("❌ No test report files found!")
        return

    # Use the most recent report
    latest_report = max(report_files, key=lambda x: x.stat().st_mtime)
    print(f"📊 Analyzing test report: {latest_report}")

    # Analyze the report
    analyzer = RAGTestAnalyzer(str(latest_report))
    analysis = analyzer.create_detailed_analysis_report()

    # Save detailed analysis
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    analysis_file = testing_dir / f"detailed_analysis_report_{timestamp}.json"

    with open(analysis_file, "w") as f:
        json.dump(analysis, f, indent=2, default=str)

    print(f"💾 Detailed analysis saved to: {analysis_file}")

    # Print summary
    analyzer.print_analysis_summary(analysis)

    return analysis


if __name__ == "__main__":
    main()
