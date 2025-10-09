#!/usr/bin/env python3
"""
Automated Test Maintenance and Intelligent Optimization System

Advanced test lifecycle management system that provides:
- Automated test maintenance and cleanup
- Intelligent test optimization and deduplication
- Performance-based test prioritization
- Flaky test detection and stabilization
- Test suite health monitoring and recommendations

Usage:
    python test_optimizer.py --analyze                    # Analyze test suite health
    python test_optimizer.py --optimize                   # Optimize existing tests
    python test_optimizer.py --detect-flaky --days 30    # Detect flaky tests
    python test_optimizer.py --deduplicate               # Remove duplicate tests
    python test_optimizer.py --prioritize                # Prioritize tests by value
"""

import subprocess
import json
import time
import sqlite3
import statistics
import argparse
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import ast


class TestSuiteAnalyzer:
    """Analyze test suite structure, performance, and health metrics."""
    
    def __init__(self, test_dir: str = "tests", db_path: str = "test_optimization.db"):
        """Initialize test suite analyzer."""
        self.test_dir = Path(test_dir)
        self.db_path = db_path
        self.init_database()
        self.test_files = []
        self.test_metrics = {}
    
    def init_database(self):
        """Initialize SQLite database for test optimization data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Test execution history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                test_name TEXT NOT NULL,
                test_file TEXT NOT NULL,
                status TEXT NOT NULL,
                duration REAL,
                error_message TEXT,
                git_commit TEXT
            )
        """)
        
        # Test performance metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                test_name TEXT NOT NULL,
                execution_time REAL NOT NULL,
                memory_usage INTEGER,
                cpu_usage REAL,
                complexity_score INTEGER
            )
        """)
        
        # Flaky test detection
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flaky_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL UNIQUE,
                failure_rate REAL NOT NULL,
                total_runs INTEGER NOT NULL,
                failed_runs INTEGER NOT NULL,
                last_failure TEXT,
                confidence_score REAL,
                status TEXT DEFAULT 'active'
            )
        """)
        
        # Test optimization recommendations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimization_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                test_name TEXT NOT NULL,
                recommendation_type TEXT NOT NULL,
                description TEXT NOT NULL,
                priority INTEGER NOT NULL,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        conn.commit()
        conn.close()
    
    def scan_test_suite(self) -> Dict:
        """Scan and analyze complete test suite structure."""
        print("🔍 Scanning test suite structure...")
        
        # Find all test files
        self.test_files = list(self.test_dir.rglob("test_*.py"))
        
        suite_analysis = {
            "total_files": len(self.test_files),
            "test_count": 0,
            "file_analysis": {},
            "duplicate_tests": [],
            "performance_metrics": {},
            "complexity_distribution": defaultdict(int)
        }
        
        # Analyze each test file
        for test_file in self.test_files:
            try:
                file_analysis = self.analyze_test_file(test_file)
                if file_analysis:
                    relative_path = test_file.relative_to(self.test_dir)
                    suite_analysis["file_analysis"][str(relative_path)] = file_analysis
                    suite_analysis["test_count"] += file_analysis["test_count"]
                    
                    # Track complexity distribution
                    for complexity in file_analysis.get("complexity_scores", []):
                        suite_analysis["complexity_distribution"][complexity] += 1
                        
            except Exception as e:
                print(f"⚠️  Error analyzing {test_file}: {e}")
        
        # Detect duplicate tests
        suite_analysis["duplicate_tests"] = self.detect_duplicate_tests()
        
        return suite_analysis
    
    def analyze_test_file(self, file_path: Path) -> Optional[Dict]:
        """Analyze individual test file for structure and metrics."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content)
            
            file_analysis = {
                "file_path": str(file_path),
                "test_count": 0,
                "test_functions": [],
                "test_classes": [],
                "imports": [],
                "complexity_scores": [],
                "fixtures": [],
                "parametrized_tests": [],
                "performance_tests": [],
                "file_size": len(content),
                "line_count": len(content.split('\n'))
            }
            
            # Analyze AST nodes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.name.startswith('test_'):
                        test_info = self.analyze_test_function(node, content)
                        file_analysis["test_functions"].append(test_info)
                        file_analysis["test_count"] += 1
                        file_analysis["complexity_scores"].append(test_info["complexity"])
                    
                    # Check for fixtures
                    if any(d.id == 'fixture' if isinstance(d, ast.Name) else False 
                          for d in node.decorator_list):
                        file_analysis["fixtures"].append(node.name)
                
                elif isinstance(node, ast.ClassDef):
                    if node.name.startswith('Test'):
                        class_info = self.analyze_test_class(node)
                        file_analysis["test_classes"].append(class_info)
                        file_analysis["test_count"] += len(class_info["methods"])
                        file_analysis["complexity_scores"].extend(class_info["method_complexities"])
                
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_info = self.analyze_import(node)
                    if import_info:
                        file_analysis["imports"].extend(import_info)
            
            # Detect parametrized and performance tests
            file_analysis["parametrized_tests"] = self.detect_parametrized_tests(content)
            file_analysis["performance_tests"] = self.detect_performance_tests(content)
            
            return file_analysis
            
        except Exception as e:
            print(f"❌ Error parsing {file_path}: {e}")
            return None
    
    def analyze_test_function(self, node: ast.FunctionDef, content: str) -> Dict:
        """Analyze individual test function."""
        func_lines = content.split('\n')[node.lineno-1:node.end_lineno if hasattr(node, 'end_lineno') else node.lineno+10]
        func_content = '\n'.join(func_lines)
        
        return {
            "name": node.name,
            "line_number": node.lineno,
            "complexity": self.calculate_function_complexity(node),
            "has_docstring": ast.get_docstring(node) is not None,
            "assertion_count": func_content.count('assert'),
            "mock_usage": 'mock' in func_content.lower() or 'patch' in func_content.lower(),
            "async": isinstance(node, ast.AsyncFunctionDef),
            "parametrized": '@pytest.mark.parametrize' in func_content,
            "slow_test": '@pytest.mark.slow' in func_content,
            "decorators": [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
            "estimated_runtime": self.estimate_test_runtime(func_content)
        }
    
    def analyze_test_class(self, node: ast.ClassDef) -> Dict:
        """Analyze test class structure."""
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
        
        return {
            "name": node.name,
            "line_number": node.lineno,
            "method_count": len(methods),
            "methods": [self.analyze_test_function(method, "") for method in methods],
            "method_complexities": [self.calculate_function_complexity(method) for method in methods],
            "has_setup": any(method.name in ['setUp', 'setup_method'] for method in node.body if isinstance(method, ast.FunctionDef)),
            "has_teardown": any(method.name in ['tearDown', 'teardown_method'] for method in node.body if isinstance(method, ast.FunctionDef))
        }
    
    def analyze_import(self, node) -> List[str]:
        """Analyze imports for dependency tracking."""
        imports = []
        
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")
        
        return imports
    
    def calculate_function_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of test function."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.Assert):
                complexity += 0.5  # Assertions add minor complexity
        
        return int(complexity)
    
    def detect_parametrized_tests(self, content: str) -> List[str]:
        """Detect parametrized tests in file content."""
        parametrized_pattern = r'@pytest\.mark\.parametrize.*?def (test_\w+)'
        matches = re.findall(parametrized_pattern, content, re.DOTALL)
        return matches
    
    def detect_performance_tests(self, content: str) -> List[str]:
        """Detect performance-related tests."""
        performance_patterns = [
            r'def (test_\w*performance\w*)',
            r'def (test_\w*timing\w*)',
            r'def (test_\w*speed\w*)',
            r'def (test_\w*benchmark\w*)'
        ]
        
        performance_tests = []
        for pattern in performance_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            performance_tests.extend(matches)
        
        return performance_tests
    
    def estimate_test_runtime(self, func_content: str) -> float:
        """Estimate test runtime based on content analysis."""
        base_time = 0.01  # 10ms base
        
        # Add time for various operations
        if 'time.sleep' in func_content:
            sleep_matches = re.findall(r'time\.sleep\((\d+(?:\.\d+)?)\)', func_content)
            for match in sleep_matches:
                base_time += float(match)
        
        if 'subprocess' in func_content:
            base_time += 0.5  # Subprocess calls are slow
        
        if 'requests.' in func_content or 'http' in func_content.lower():
            base_time += 1.0  # Network calls
        
        if 'database' in func_content.lower() or 'sql' in func_content.lower():
            base_time += 0.2  # Database operations
        
        # Mock usage reduces time
        if 'mock' in func_content.lower() or 'patch' in func_content.lower():
            base_time *= 0.8
        
        return round(base_time, 3)
    
    def detect_duplicate_tests(self) -> List[Dict]:
        """Detect potentially duplicate tests across the suite."""
        duplicates = []
        test_signatures = defaultdict(list)
        
        # Build test signatures
        for file_path, file_analysis in self.test_metrics.get("file_analysis", {}).items():
            for test_func in file_analysis.get("test_functions", []):
                # Create signature based on test name and assertion patterns
                signature = self.create_test_signature(test_func)
                test_signatures[signature].append({
                    "file": file_path,
                    "test": test_func["name"],
                    "complexity": test_func["complexity"]
                })
        
        # Find duplicates
        for signature, tests in test_signatures.items():
            if len(tests) > 1:
                duplicates.append({
                    "signature": signature,
                    "tests": tests,
                    "duplicate_count": len(tests)
                })
        
        return duplicates
    
    def create_test_signature(self, test_func: Dict) -> str:
        """Create unique signature for test function."""
        # Normalize test name to detect similar tests
        name_parts = test_func["name"].replace("test_", "").split("_")
        normalized_name = "_".join(sorted(name_parts))
        
        signature_parts = [
            normalized_name,
            str(test_func["assertion_count"]),
            str(test_func["complexity"]),
            str(test_func["mock_usage"])
        ]
        
        return "|".join(signature_parts)


class FlakyTestDetector:
    """Detect and analyze flaky tests using historical execution data."""
    
    def __init__(self, db_path: str = "test_optimization.db"):
        """Initialize flaky test detector."""
        self.db_path = db_path
    
    def collect_test_execution_data(self, days: int = 30) -> Dict:
        """Collect test execution data for flaky test analysis."""
        print(f"📊 Collecting test execution data for last {days} days...")
        
        # Run test suite multiple times to collect data
        execution_data = {}
        
        for run in range(5):  # Run tests 5 times for flaky detection
            print(f"   Execution run {run + 1}/5...")
            
            try:
                # Run comprehensive test suite
                result = subprocess.run(
                    ["python", "test_runner.py", "--all", "--report", f"flaky_run_{run}.json"],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                # Parse results
                if result.returncode in [0, 1]:  # Success or some failures
                    run_data = self.parse_test_execution_results(result.stdout, run)
                    self.merge_execution_data(execution_data, run_data)
                
            except subprocess.TimeoutExpired:
                print(f"   ⚠️  Run {run + 1} timed out")
            except Exception as e:
                print(f"   ❌ Run {run + 1} failed: {e}")
        
        return execution_data
    
    def parse_test_execution_results(self, stdout: str, run_id: int) -> Dict:
        """Parse test execution results for flaky analysis."""
        run_data = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "tests": {}
        }
        
        # Parse pytest output for test results
        lines = stdout.split('\n')
        current_test = None
        
        for line in lines:
            # Test execution line
            if '::test_' in line:
                test_match = re.search(r'(.*::test_\w+)', line)
                if test_match:
                    current_test = test_match.group(1)
                    
                    # Determine status
                    if 'PASSED' in line:
                        status = 'passed'
                    elif 'FAILED' in line:
                        status = 'failed'
                    elif 'SKIPPED' in line:
                        status = 'skipped'
                    else:
                        status = 'unknown'
                    
                    run_data["tests"][current_test] = {
                        "status": status,
                        "duration": self.extract_duration(line),
                        "run_id": run_id
                    }
        
        return run_data
    
    def extract_duration(self, line: str) -> float:
        """Extract test duration from pytest output line."""
        duration_match = re.search(r'(\d+\.\d+)s', line)
        if duration_match:
            return float(duration_match.group(1))
        return 0.0
    
    def merge_execution_data(self, master_data: Dict, run_data: Dict):
        """Merge execution run data into master dataset."""
        for test_name, test_result in run_data["tests"].items():
            if test_name not in master_data:
                master_data[test_name] = []
            
            master_data[test_name].append(test_result)
    
    def analyze_flaky_tests(self, execution_data: Dict) -> List[Dict]:
        """Analyze execution data to identify flaky tests."""
        print("🔍 Analyzing tests for flaky behavior...")
        
        flaky_tests = []
        
        for test_name, executions in execution_data.items():
            if len(executions) < 3:  # Need at least 3 runs for analysis
                continue
            
            # Calculate failure statistics
            total_runs = len(executions)
            failed_runs = sum(1 for exec in executions if exec["status"] == "failed")
            failure_rate = failed_runs / total_runs
            
            # Identify flaky tests (intermittent failures)
            if 0 < failure_rate < 1.0 and failed_runs >= 1:
                # Calculate additional metrics
                durations = [exec["duration"] for exec in executions if exec["duration"] > 0]
                duration_variance = statistics.variance(durations) if len(durations) > 1 else 0
                
                flaky_test = {
                    "test_name": test_name,
                    "failure_rate": failure_rate,
                    "total_runs": total_runs,
                    "failed_runs": failed_runs,
                    "duration_variance": duration_variance,
                    "avg_duration": statistics.mean(durations) if durations else 0,
                    "confidence_score": self.calculate_flaky_confidence(failure_rate, total_runs, duration_variance),
                    "last_failure": max([exec["timestamp"] for exec in executions if exec["status"] == "failed"], default=None)
                }
                
                flaky_tests.append(flaky_test)
        
        # Sort by confidence score
        flaky_tests.sort(key=lambda x: x["confidence_score"], reverse=True)
        
        return flaky_tests
    
    def calculate_flaky_confidence(self, failure_rate: float, total_runs: int, duration_variance: float) -> float:
        """Calculate confidence score for flaky test detection."""
        # Base confidence on failure rate pattern
        if 0.2 <= failure_rate <= 0.8:  # Most likely flaky range
            base_confidence = 0.8
        elif 0.1 <= failure_rate <= 0.9:
            base_confidence = 0.6
        else:
            base_confidence = 0.3
        
        # Adjust for sample size
        sample_bonus = min(0.2, total_runs * 0.02)
        
        # Adjust for duration variance (high variance suggests instability)
        variance_bonus = min(0.1, duration_variance * 0.1)
        
        return min(1.0, base_confidence + sample_bonus + variance_bonus)
    
    def store_flaky_test_data(self, flaky_tests: List[Dict]):
        """Store flaky test data in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for flaky_test in flaky_tests:
            cursor.execute("""
                INSERT OR REPLACE INTO flaky_tests 
                (test_name, failure_rate, total_runs, failed_runs, last_failure, confidence_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                flaky_test["test_name"],
                flaky_test["failure_rate"],
                flaky_test["total_runs"],
                flaky_test["failed_runs"],
                flaky_test.get("last_failure"),
                flaky_test["confidence_score"]
            ))
        
        conn.commit()
        conn.close()
        
        print(f"💾 Stored {len(flaky_tests)} flaky test records")


class TestOptimizer:
    """Optimize test suite for performance and maintainability."""
    
    def __init__(self, analyzer: TestSuiteAnalyzer, flaky_detector: FlakyTestDetector):
        """Initialize test optimizer."""
        self.analyzer = analyzer
        self.flaky_detector = flaky_detector
        self.optimization_recommendations = []
    
    def optimize_test_suite(self) -> Dict:
        """Perform comprehensive test suite optimization."""
        print("⚡ Optimizing test suite...")
        
        # Analyze current state
        suite_analysis = self.analyzer.scan_test_suite()
        
        optimization_results = {
            "analyzed_files": suite_analysis["total_files"],
            "analyzed_tests": suite_analysis["test_count"],
            "recommendations": [],
            "performance_improvements": [],
            "deduplication_opportunities": [],
            "prioritization_suggestions": []
        }
        
        # Generate optimization recommendations
        optimization_results["recommendations"] = self.generate_optimization_recommendations(suite_analysis)
        optimization_results["performance_improvements"] = self.identify_performance_improvements(suite_analysis)
        optimization_results["deduplication_opportunities"] = self.identify_deduplication_opportunities(suite_analysis)
        optimization_results["prioritization_suggestions"] = self.generate_prioritization_suggestions(suite_analysis)
        
        return optimization_results
    
    def generate_optimization_recommendations(self, suite_analysis: Dict) -> List[Dict]:
        """Generate specific optimization recommendations."""
        recommendations = []
        
        # Analyze file-level recommendations
        for file_path, file_analysis in suite_analysis["file_analysis"].items():
            
            # Large test files
            if file_analysis["test_count"] > 20:
                recommendations.append({
                    "type": "file_organization",
                    "file": file_path,
                    "priority": "medium",
                    "description": f"Large test file with {file_analysis['test_count']} tests - consider splitting",
                    "suggestion": "Split into multiple focused test files"
                })
            
            # Complex tests
            high_complexity_tests = [
                test for test in file_analysis.get("test_functions", [])
                if test["complexity"] > 5
            ]
            
            if high_complexity_tests:
                recommendations.append({
                    "type": "complexity_reduction",
                    "file": file_path,
                    "priority": "high",
                    "description": f"{len(high_complexity_tests)} tests with high complexity",
                    "suggestion": "Refactor complex tests into smaller, focused test cases",
                    "affected_tests": [test["name"] for test in high_complexity_tests]
                })
            
            # Missing fixtures
            if file_analysis["test_count"] > 5 and not file_analysis["fixtures"]:
                recommendations.append({
                    "type": "fixture_opportunity",
                    "file": file_path,
                    "priority": "low",
                    "description": "Multiple tests without shared fixtures",
                    "suggestion": "Consider adding fixtures for common test setup"
                })
        
        return recommendations
    
    def identify_performance_improvements(self, suite_analysis: Dict) -> List[Dict]:
        """Identify performance improvement opportunities."""
        improvements = []
        
        # Analyze estimated runtimes
        for file_path, file_analysis in suite_analysis["file_analysis"].items():
            slow_tests = [
                test for test in file_analysis.get("test_functions", [])
                if test["estimated_runtime"] > 1.0
            ]
            
            if slow_tests:
                total_slow_time = sum(test["estimated_runtime"] for test in slow_tests)
                improvements.append({
                    "type": "slow_test_optimization",
                    "file": file_path,
                    "slow_tests": len(slow_tests),
                    "estimated_time_savings": total_slow_time * 0.5,  # Assume 50% improvement
                    "suggestion": "Optimize slow tests with better mocking or test data",
                    "affected_tests": [test["name"] for test in slow_tests]
                })
        
        # Identify parallel execution opportunities
        total_tests = suite_analysis["test_count"]
        if total_tests > 50:
            improvements.append({
                "type": "parallel_execution",
                "estimated_time_savings": total_tests * 0.3,  # Assume 30% improvement
                "suggestion": "Implement parallel test execution with pytest-xdist",
                "priority": "high"
            })
        
        return improvements
    
    def identify_deduplication_opportunities(self, suite_analysis: Dict) -> List[Dict]:
        """Identify test deduplication opportunities."""
        return suite_analysis.get("duplicate_tests", [])
    
    def generate_prioritization_suggestions(self, suite_analysis: Dict) -> List[Dict]:
        """Generate test prioritization suggestions."""
        suggestions = []
        
        # Critical path tests (high complexity, important functionality)
        critical_tests = []
        fast_tests = []
        
        for file_path, file_analysis in suite_analysis["file_analysis"].items():
            for test in file_analysis.get("test_functions", []):
                if test["complexity"] > 3 and not test["mock_usage"]:
                    critical_tests.append({
                        "file": file_path,
                        "test": test["name"],
                        "complexity": test["complexity"],
                        "estimated_runtime": test["estimated_runtime"]
                    })
                elif test["estimated_runtime"] < 0.1:
                    fast_tests.append({
                        "file": file_path,
                        "test": test["name"],
                        "estimated_runtime": test["estimated_runtime"]
                    })
        
        if critical_tests:
            suggestions.append({
                "type": "critical_path_prioritization",
                "description": f"Prioritize {len(critical_tests)} critical tests for CI/CD",
                "tests": critical_tests[:10],  # Top 10
                "suggestion": "Run these tests first in CI pipeline"
            })
        
        if fast_tests:
            suggestions.append({
                "type": "fast_feedback_loop",
                "description": f"Create fast feedback loop with {len(fast_tests)} quick tests",
                "tests": fast_tests[:20],  # Top 20
                "suggestion": "Group fast tests for immediate developer feedback"
            })
        
        return suggestions
    
    def apply_optimizations(self, optimization_results: Dict) -> Dict:
        """Apply automated optimizations where possible."""
        print("🔧 Applying automated optimizations...")
        
        applied_optimizations = {
            "automated_fixes": 0,
            "manual_recommendations": 0,
            "performance_improvements": 0
        }
        
        # Apply safe automated optimizations
        for recommendation in optimization_results["recommendations"]:
            if recommendation["type"] == "fixture_opportunity":
                # This would require manual review
                applied_optimizations["manual_recommendations"] += 1
            elif recommendation["type"] == "file_organization":
                # This would require manual intervention
                applied_optimizations["manual_recommendations"] += 1
        
        return applied_optimizations


def main():
    """Main entry point for test optimization system."""
    parser = argparse.ArgumentParser(description="Automated Test Maintenance and Optimization")
    parser.add_argument("--analyze", action="store_true", help="Analyze test suite health")
    parser.add_argument("--optimize", action="store_true", help="Optimize existing tests")
    parser.add_argument("--detect-flaky", action="store_true", help="Detect flaky tests")
    parser.add_argument("--days", type=int, default=7, help="Days of history for flaky detection")
    parser.add_argument("--deduplicate", action="store_true", help="Remove duplicate tests")
    parser.add_argument("--prioritize", action="store_true", help="Prioritize tests by value")
    parser.add_argument("--report", type=str, help="Generate optimization report")
    
    args = parser.parse_args()
    
    # Initialize components
    analyzer = TestSuiteAnalyzer()
    flaky_detector = FlakyTestDetector()
    optimizer = TestOptimizer(analyzer, flaky_detector)
    
    if args.analyze:
        print("🔍 Analyzing test suite health...")
        analysis = analyzer.scan_test_suite()
        
        print(f"\n📊 Test Suite Analysis Results:")
        print(f"   Total test files: {analysis['total_files']}")
        print(f"   Total tests: {analysis['test_count']}")
        print(f"   Duplicate tests detected: {len(analysis['duplicate_tests'])}")
        
        # Show complexity distribution
        print(f"\n📈 Complexity Distribution:")
        for complexity, count in sorted(analysis['complexity_distribution'].items()):
            print(f"   Complexity {complexity}: {count} tests")
    
    elif args.detect_flaky:
        print(f"🔍 Detecting flaky tests over last {args.days} days...")
        execution_data = flaky_detector.collect_test_execution_data(args.days)
        flaky_tests = flaky_detector.analyze_flaky_tests(execution_data)
        
        if flaky_tests:
            print(f"\n⚠️  Detected {len(flaky_tests)} potentially flaky tests:")
            for flaky in flaky_tests[:10]:  # Show top 10
                print(f"   - {flaky['test_name']}: {flaky['failure_rate']:.1%} failure rate "
                      f"(confidence: {flaky['confidence_score']:.2f})")
            
            flaky_detector.store_flaky_test_data(flaky_tests)
        else:
            print("✅ No flaky tests detected")
    
    elif args.optimize:
        print("⚡ Optimizing test suite...")
        optimization_results = optimizer.optimize_test_suite()
        
        print(f"\n📊 Optimization Results:")
        print(f"   Files analyzed: {optimization_results['analyzed_files']}")
        print(f"   Tests analyzed: {optimization_results['analyzed_tests']}")
        print(f"   Recommendations: {len(optimization_results['recommendations'])}")
        print(f"   Performance improvements: {len(optimization_results['performance_improvements'])}")
        print(f"   Deduplication opportunities: {len(optimization_results['deduplication_opportunities'])}")
        
        # Show top recommendations
        print(f"\n💡 Top Optimization Recommendations:")
        for i, rec in enumerate(optimization_results['recommendations'][:5], 1):
            print(f"   {i}. {rec['type'].title()}: {rec['description']}")
        
        # Apply optimizations
        applied = optimizer.apply_optimizations(optimization_results)
        print(f"\n✅ Applied {applied['automated_fixes']} automated optimizations")
        print(f"📋 {applied['manual_recommendations']} recommendations require manual review")
    
    else:
        print("Please specify --analyze, --optimize, --detect-flaky, --deduplicate, or --prioritize")
        sys.exit(1)


if __name__ == "__main__":
    main()