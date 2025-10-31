#!/usr/bin/env python3
"""
Automated Quality Monitoring and Continuous Improvement System

Advanced quality assurance system that provides:
- Historical test performance tracking
- Automated quality trend analysis
- Regression detection and alerting
- Performance degradation monitoring
- Quality improvement recommendations
- Automated report generation with trend analysis

Usage:
    python quality_monitor.py --track                    # Track current quality metrics
    python quality_monitor.py --analyze --days 30       # Analyze trends over 30 days
    python quality_monitor.py --report weekly.html      # Generate trend report
    python quality_monitor.py --alert-setup             # Setup quality alerting
"""

import argparse
import json
import os
import sqlite3
import statistics
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Dict, List


class QualityMetricsCollector:
    """Collect and store comprehensive quality metrics over time."""

    def __init__(self, db_path: str = "quality_metrics.db"):
        """Initialize quality metrics collector with SQLite storage."""
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize SQLite database for quality metrics storage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Quality metrics table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quality_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ring_id INTEGER NOT NULL,
                ring_name TEXT NOT NULL,
                tests_total INTEGER,
                tests_passed INTEGER,
                tests_failed INTEGER,
                pass_rate REAL,
                coverage_pct REAL,
                duration REAL,
                tests_per_second REAL,
                enforcement_level TEXT,
                git_commit TEXT,
                branch_name TEXT
            )
        """
        )

        # Performance trends table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metric_type TEXT NOT NULL,
                context TEXT
            )
        """
        )

        # Quality alerts table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quality_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                ring_id INTEGER,
                metric_value REAL,
                threshold_value REAL,
                resolved BOOLEAN DEFAULT FALSE
            )
        """
        )

        conn.commit()
        conn.close()

    def collect_current_metrics(self) -> Dict:
        """Collect current quality metrics from test execution."""
        print("📊 Collecting current quality metrics...")

        # Run comprehensive test validation
        cmd = ["python", "test_runner.py", "--all", "--performance", "--report", "temp_metrics.json"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            # Load generated report
            if os.path.exists("temp_metrics.json"):
                with open("temp_metrics.json", "r") as f:
                    metrics = json.load(f)
                os.remove("temp_metrics.json")  # Cleanup

                # Add git context
                metrics["git_context"] = self._get_git_context()

                return metrics
            else:
                return {"error": "Failed to generate metrics report"}

        except subprocess.TimeoutExpired:
            return {"error": "Metrics collection timeout"}
        except Exception as e:
            return {"error": str(e)}

    def _get_git_context(self) -> Dict:
        """Get current git context for metrics tracking."""
        try:
            # Get current commit hash
            commit_result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
            commit_hash = commit_result.stdout.strip()[:8] if commit_result.returncode == 0 else "unknown"

            # Get current branch
            branch_result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
            branch_name = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

            return {"commit_hash": commit_hash, "branch_name": branch_name}
        except Exception:
            return {"commit_hash": "unknown", "branch_name": "unknown"}

    def store_metrics(self, metrics: Dict):
        """Store collected metrics in database."""
        if "error" in metrics:
            print(f"❌ Cannot store metrics due to error: {metrics['error']}")
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()
        git_context = metrics.get("git_context", {})

        # Store ring-specific metrics
        for ring_id, ring_data in metrics.get("rings", {}).items():
            cursor.execute(
                """
                INSERT INTO quality_metrics (
                    timestamp, ring_id, ring_name, tests_total, tests_passed,
                    tests_failed, pass_rate, coverage_pct, duration,
                    tests_per_second, enforcement_level, git_commit, branch_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    timestamp,
                    int(ring_id),
                    ring_data.get("name", f"Ring {ring_id}"),
                    ring_data.get("tests_collected", 0),
                    ring_data.get("tests_passed", 0),
                    ring_data.get("tests_failed", 0),
                    (ring_data.get("tests_passed", 0) / ring_data.get("tests_collected", 1)) * 100
                    if ring_data.get("tests_collected", 0) > 0
                    else 0,
                    ring_data.get("coverage_achieved", 0),
                    ring_data.get("duration", 0),
                    ring_data.get("tests_collected", 0) / ring_data.get("duration", 1)
                    if ring_data.get("duration", 0) > 0
                    else 0,
                    ring_data.get("enforcement", "unknown"),
                    git_context.get("commit_hash", "unknown"),
                    git_context.get("branch_name", "unknown"),
                ),
            )

        # Store overall performance metrics
        summary = metrics.get("summary", {})
        performance = metrics.get("performance", {})

        perf_metrics = [
            ("overall_pass_rate", summary.get("pass_rate", 0), "percentage"),
            ("total_tests", summary.get("total_tests", 0), "count"),
            ("total_duration", summary.get("total_duration", 0), "seconds"),
            ("tests_per_second", performance.get("overall_tests_per_second", 0), "rate"),
            ("successful_rings", summary.get("successful_rings", 0), "count"),
        ]

        for metric_name, metric_value, metric_type in perf_metrics:
            cursor.execute(
                """
                INSERT INTO performance_trends (timestamp, metric_name, metric_value, metric_type, context)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    timestamp,
                    metric_name,
                    metric_value,
                    metric_type,
                    f"branch:{git_context.get('branch_name', 'unknown')}",
                ),
            )

        conn.commit()
        conn.close()

        print(f"✅ Stored quality metrics for {len(metrics.get('rings', {}))} rings")


class QualityTrendAnalyzer:
    """Analyze quality trends and detect regressions."""

    def __init__(self, db_path: str = "quality_metrics.db"):
        """Initialize trend analyzer with database connection."""
        self.db_path = db_path

    def analyze_trends(self, days: int = 30) -> Dict:
        """Analyze quality trends over specified number of days."""
        print(f"📈 Analyzing quality trends over last {days} days...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get date threshold
        threshold_date = (datetime.now() - timedelta(days=days)).isoformat()

        # Analyze pass rate trends by ring
        cursor.execute(
            """
            SELECT ring_id, ring_name, timestamp, pass_rate, duration, tests_per_second
            FROM quality_metrics
            WHERE timestamp >= ?
            ORDER BY ring_id, timestamp
        """,
            (threshold_date,),
        )

        ring_data = {}
        for row in cursor.fetchall():
            ring_id, ring_name, timestamp, pass_rate, duration, tps = row

            if ring_id not in ring_data:
                ring_data[ring_id] = {
                    "name": ring_name,
                    "pass_rates": [],
                    "durations": [],
                    "tests_per_second": [],
                    "timestamps": [],
                }

            ring_data[ring_id]["pass_rates"].append(pass_rate)
            ring_data[ring_id]["durations"].append(duration)
            ring_data[ring_id]["tests_per_second"].append(tps)
            ring_data[ring_id]["timestamps"].append(timestamp)

        # Analyze overall performance trends
        cursor.execute(
            """
            SELECT metric_name, metric_value, timestamp
            FROM performance_trends
            WHERE timestamp >= ?
            ORDER BY metric_name, timestamp
        """,
            (threshold_date,),
        )

        performance_trends = {}
        for row in cursor.fetchall():
            metric_name, metric_value, timestamp = row

            if metric_name not in performance_trends:
                performance_trends[metric_name] = {"values": [], "timestamps": []}

            performance_trends[metric_name]["values"].append(metric_value)
            performance_trends[metric_name]["timestamps"].append(timestamp)

        conn.close()

        # Calculate trend analysis
        analysis = {
            "analysis_period": f"{days} days",
            "ring_trends": {},
            "performance_trends": {},
            "quality_score": 0,
            "recommendations": [],
        }

        # Analyze ring trends
        for ring_id, data in ring_data.items():
            if len(data["pass_rates"]) < 2:
                continue

            ring_analysis = {
                "current_pass_rate": data["pass_rates"][-1] if data["pass_rates"] else 0,
                "average_pass_rate": statistics.mean(data["pass_rates"]) if data["pass_rates"] else 0,
                "pass_rate_trend": self._calculate_trend(data["pass_rates"]),
                "performance_trend": self._calculate_trend(data["tests_per_second"]),
                "stability": statistics.stdev(data["pass_rates"]) if len(data["pass_rates"]) > 1 else 0,
                "data_points": len(data["pass_rates"]),
            }

            analysis["ring_trends"][ring_id] = ring_analysis

        # Analyze performance trends
        for metric_name, data in performance_trends.items():
            if len(data["values"]) < 2:
                continue

            analysis["performance_trends"][metric_name] = {
                "current_value": data["values"][-1] if data["values"] else 0,
                "average_value": statistics.mean(data["values"]) if data["values"] else 0,
                "trend": self._calculate_trend(data["values"]),
                "stability": statistics.stdev(data["values"]) if len(data["values"]) > 1 else 0,
            }

        # Calculate overall quality score
        analysis["quality_score"] = self._calculate_quality_score(analysis)

        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis)

        return analysis

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values."""
        if len(values) < 2:
            return "insufficient_data"

        # Simple linear trend calculation
        n = len(values)
        x_vals = list(range(n))

        # Calculate slope
        x_mean = statistics.mean(x_vals)
        y_mean = statistics.mean(values)

        numerator = sum((x_vals[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x_vals[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return "stable"

        slope = numerator / denominator

        if abs(slope) < 0.1:
            return "stable"
        elif slope > 0:
            return "improving"
        else:
            return "declining"

    def _calculate_quality_score(self, analysis: Dict) -> float:
        """Calculate overall quality score from 0-100."""
        score_components = []

        # Ring pass rate scores
        for ring_id, ring_data in analysis["ring_trends"].items():
            pass_rate = ring_data["current_pass_rate"]
            stability = max(0, 10 - ring_data["stability"])  # Lower stability variance is better

            ring_score = (pass_rate * 0.8) + (stability * 0.2)
            score_components.append(ring_score)

        # Performance stability score
        perf_scores = []
        for metric_name, perf_data in analysis["performance_trends"].items():
            if metric_name in ["overall_pass_rate", "tests_per_second"]:
                trend_bonus = 5 if perf_data["trend"] == "improving" else 0
                stability_penalty = min(5, perf_data["stability"])

                perf_score = perf_data["current_value"] + trend_bonus - stability_penalty
                perf_scores.append(max(0, min(100, perf_score)))

        if perf_scores:
            score_components.extend(perf_scores)

        return statistics.mean(score_components) if score_components else 0

    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate quality improvement recommendations."""
        recommendations = []

        # Check ring performance
        for ring_id, ring_data in analysis["ring_trends"].items():
            if ring_data["current_pass_rate"] < 90:
                recommendations.append(
                    f"Ring {ring_id}: Pass rate ({ring_data['current_pass_rate']:.1f}%) below optimal - investigate failing tests"
                )

            if ring_data["pass_rate_trend"] == "declining":
                recommendations.append(f"Ring {ring_id}: Declining pass rate trend detected - review recent changes")

            if ring_data["stability"] > 5:
                recommendations.append(
                    f"Ring {ring_id}: High pass rate variance ({ring_data['stability']:.1f}) - stabilize flaky tests"
                )

        # Check performance trends
        perf_data = analysis["performance_trends"]
        if "tests_per_second" in perf_data and perf_data["tests_per_second"]["trend"] == "declining":
            recommendations.append("Performance: Test execution speed declining - optimize slow tests")

        if "total_duration" in perf_data and perf_data["total_duration"]["current_value"] > 10:
            recommendations.append("Performance: Total test duration exceeds 10 seconds - consider parallel execution")

        # Overall quality recommendations
        if analysis["quality_score"] < 80:
            recommendations.append("Overall: Quality score below 80% - prioritize test stability improvements")

        if not recommendations:
            recommendations.append("Excellent: All quality metrics within optimal ranges")

        return recommendations

    def detect_regressions(self, threshold_days: int = 7) -> List[Dict]:
        """Detect quality regressions in recent period."""
        print(f"🔍 Detecting regressions in last {threshold_days} days...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get recent vs baseline comparison
        recent_date = (datetime.now() - timedelta(days=threshold_days)).isoformat()
        baseline_date = (datetime.now() - timedelta(days=threshold_days * 2)).isoformat()

        regressions = []

        # Check pass rate regressions
        cursor.execute(
            """
            SELECT ring_id, ring_name,
                   AVG(CASE WHEN timestamp >= ? THEN pass_rate END) as recent_avg,
                   AVG(CASE WHEN timestamp < ? THEN pass_rate END) as baseline_avg
            FROM quality_metrics
            WHERE timestamp >= ?
            GROUP BY ring_id, ring_name
            HAVING recent_avg IS NOT NULL AND baseline_avg IS NOT NULL
        """,
            (recent_date, recent_date, baseline_date),
        )

        for row in cursor.fetchall():
            ring_id, ring_name, recent_avg, baseline_avg = row

            if recent_avg < baseline_avg - 5:  # 5% drop threshold
                regressions.append(
                    {
                        "type": "pass_rate_regression",
                        "ring_id": ring_id,
                        "ring_name": ring_name,
                        "recent_value": recent_avg,
                        "baseline_value": baseline_avg,
                        "severity": "high" if recent_avg < baseline_avg - 10 else "medium",
                    }
                )

        conn.close()
        return regressions


class QualityReportGenerator:
    """Generate comprehensive quality reports and dashboards."""

    def __init__(self, db_path: str = "quality_metrics.db"):
        """Initialize report generator."""
        self.db_path = db_path

    def generate_html_report(self, output_file: str, days: int = 30):
        """Generate comprehensive HTML quality report."""
        print(f"📋 Generating HTML quality report: {output_file}")

        # Collect data for report
        analyzer = QualityTrendAnalyzer(self.db_path)
        trends = analyzer.analyze_trends(days)
        regressions = analyzer.detect_regressions()

        # Generate HTML report
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Quality Monitoring Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .metric {{ display: inline-block; margin: 10px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .ring {{ margin: 20px 0; padding: 15px; background: #f9f9f9; border-radius: 5px; }}
        .trend-up {{ color: green; }}
        .trend-down {{ color: red; }}
        .trend-stable {{ color: blue; }}
        .regression {{ background: #ffe6e6; padding: 10px; margin: 5px 0; border-radius: 3px; }}
        .recommendation {{ background: #e6f3ff; padding: 10px; margin: 5px 0; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Quality Monitoring Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Analysis Period: {trends['analysis_period']}</p>
        <h2>Overall Quality Score: {trends['quality_score']:.1f}/100</h2>
    </div>

    <h2>📊 Ring Performance Summary</h2>
"""

        # Add ring analysis
        for ring_id, ring_data in trends["ring_trends"].items():
            trend_class = (
                f"trend-{ring_data['pass_rate_trend'].replace('improving', 'up').replace('declining', 'down')}"
            )

            html_content += f"""
    <div class="ring">
        <h3>Ring {ring_id}: {ring_data.get('name', f'Ring {ring_id}')}</h3>
        <div class="metric">
            <strong>Current Pass Rate:</strong> {ring_data['current_pass_rate']:.1f}%
        </div>
        <div class="metric">
            <strong>Average Pass Rate:</strong> {ring_data['average_pass_rate']:.1f}%
        </div>
        <div class="metric {trend_class}">
            <strong>Trend:</strong> {ring_data['pass_rate_trend'].title()}
        </div>
        <div class="metric">
            <strong>Stability:</strong> {ring_data['stability']:.2f} (lower is better)
        </div>
    </div>
"""

        # Add regressions section
        if regressions:
            html_content += """
    <h2>⚠️ Quality Regressions Detected</h2>
"""
            for regression in regressions:
                html_content += f"""
    <div class="regression">
        <strong>{regression['ring_name']}</strong>: {regression['type'].replace('_', ' ').title()}
        <br>Recent: {regression['recent_value']:.1f}% vs Baseline: {regression['baseline_value']:.1f}%
        <br>Severity: {regression['severity'].upper()}
    </div>
"""

        # Add recommendations
        html_content += """
    <h2>💡 Quality Improvement Recommendations</h2>
"""
        for recommendation in trends["recommendations"]:
            html_content += f"""
    <div class="recommendation">
        {recommendation}
    </div>
"""

        html_content += """
</body>
</html>
"""

        # Write report file
        with open(output_file, "w") as f:
            f.write(html_content)

        print(f"✅ HTML report generated: {output_file}")


class QualityMonitor:
    """Main quality monitoring orchestrator."""

    def __init__(self):
        """Initialize quality monitor with all components."""
        self.collector = QualityMetricsCollector()
        self.analyzer = QualityTrendAnalyzer()
        self.reporter = QualityReportGenerator()

    def track_current_quality(self):
        """Track current quality metrics."""
        print("🔍 Tracking current quality metrics...")

        metrics = self.collector.collect_current_metrics()
        self.collector.store_metrics(metrics)

        # Quick analysis
        if "error" not in metrics:
            summary = metrics.get("summary", {})
            print(f"✅ Quality tracking complete:")
            print(f"   Pass Rate: {summary.get('pass_rate', 0):.1f}%")
            print(f"   Total Tests: {summary.get('total_tests', 0)}")
            print(f"   Duration: {summary.get('total_duration', 0):.2f}s")

    def run_quality_analysis(self, days: int = 30):
        """Run comprehensive quality analysis."""
        trends = self.analyzer.analyze_trends(days)
        regressions = self.analyzer.detect_regressions()

        print(f"\n📈 Quality Analysis Results ({days} days):")
        print(f"   Overall Quality Score: {trends['quality_score']:.1f}/100")
        print(f"   Rings Analyzed: {len(trends['ring_trends'])}")

        if regressions:
            print(f"   ⚠️  Regressions Detected: {len(regressions)}")
            for reg in regressions:
                print(f"      - {reg['ring_name']}: {reg['type']} ({reg['severity']})")

        print(f"\n💡 Top Recommendations:")
        for i, rec in enumerate(trends["recommendations"][:3], 1):
            print(f"   {i}. {rec}")

        return trends, regressions


def main():
    """Main entry point for quality monitoring system."""
    parser = argparse.ArgumentParser(description="Quality Monitoring and Continuous Improvement System")
    parser.add_argument("--track", action="store_true", help="Track current quality metrics")
    parser.add_argument("--analyze", action="store_true", help="Analyze quality trends")
    parser.add_argument("--days", type=int, default=30, help="Analysis period in days")
    parser.add_argument("--report", type=str, help="Generate HTML report to specified file")
    parser.add_argument("--regressions", action="store_true", help="Check for recent regressions")

    args = parser.parse_args()

    monitor = QualityMonitor()

    if args.track:
        monitor.track_current_quality()
    elif args.analyze:
        monitor.run_quality_analysis(args.days)
    elif args.report:
        monitor.reporter.generate_html_report(args.report, args.days)
    elif args.regressions:
        regressions = monitor.analyzer.detect_regressions()
        if regressions:
            print(f"⚠️  {len(regressions)} regressions detected!")
            for reg in regressions:
                print(f"   - {reg['ring_name']}: {reg['recent_value']:.1f}% vs {reg['baseline_value']:.1f}%")
            sys.exit(1)
        else:
            print("✅ No regressions detected")
    else:
        print("Please specify --track, --analyze, --report, or --regressions")
        sys.exit(1)


if __name__ == "__main__":
    main()
