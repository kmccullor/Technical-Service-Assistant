#!/usr/bin/env python3
"""
Automated Test Maintenance Dashboard

Comprehensive web-based dashboard for test suite health monitoring, optimization,
and intelligent maintenance. Provides real-time insights into test performance,
quality metrics, and automated maintenance recommendations.

Features:
- Real-time test execution monitoring
- Flaky test detection and tracking
- Performance trend analysis
- Optimization recommendations
- Test coverage visualization
- Automated maintenance scheduling

Usage:
    python test_dashboard.py --port 8090
    Open http://localhost:8090 for dashboard interface
"""

import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta
from typing import Dict

import schedule
from flask import Flask, jsonify, render_template_string


class TestMaintenanceDashboard:
    """Web-based dashboard for comprehensive test maintenance."""

    def __init__(self, port: int = 8090, db_path: str = "test_optimization.db"):
        """Initialize test maintenance dashboard."""
        self.app = Flask(__name__)
        self.port = port
        self.db_path = db_path
        self.setup_routes()
        self.setup_background_tasks()

        # Initialize background data collection
        self.collecting_data = False
        self.last_analysis = None

    def setup_routes(self):
        """Setup Flask routes for dashboard."""

        @self.app.route("/")
        def dashboard():
            """Main dashboard page."""
            return render_template_string(DASHBOARD_HTML_TEMPLATE)

        @self.app.route("/api/suite-health")
        def suite_health():
            """Get current test suite health metrics."""
            try:
                # Run quick analysis
                result = subprocess.run(
                    ["python", "test_optimizer.py", "--analyze"], capture_output=True, text=True, timeout=60
                )

                health_data = self.parse_health_output(result.stdout)
                return jsonify(health_data)

            except Exception as e:
                return jsonify({"error": f"Health check failed: {e}"}), 500

        @self.app.route("/api/flaky-tests")
        def flaky_tests():
            """Get current flaky test data."""
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT test_name, failure_rate, total_runs, failed_runs,
                       last_failure, confidence_score, status
                FROM flaky_tests
                WHERE status = 'active'
                ORDER BY confidence_score DESC
                LIMIT 20
            """
            )

            flaky_data = []
            for row in cursor.fetchall():
                flaky_data.append(
                    {
                        "test_name": row[0],
                        "failure_rate": row[1],
                        "total_runs": row[2],
                        "failed_runs": row[3],
                        "last_failure": row[4],
                        "confidence_score": row[5],
                        "status": row[6],
                    }
                )

            conn.close()
            return jsonify(flaky_data)

        @self.app.route("/api/performance-trends")
        def performance_trends():
            """Get test performance trend data."""
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get performance data for last 30 days
            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

            cursor.execute(
                """
                SELECT DATE(timestamp) as date,
                       AVG(execution_time) as avg_time,
                       COUNT(*) as test_count
                FROM test_performance
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            """,
                (thirty_days_ago,),
            )

            trend_data = []
            for row in cursor.fetchall():
                trend_data.append({"date": row[0], "avg_execution_time": row[1], "test_count": row[2]})

            conn.close()
            return jsonify(trend_data)

        @self.app.route("/api/optimization-recommendations")
        def optimization_recommendations():
            """Get current optimization recommendations."""
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT test_name, recommendation_type, description, priority, status
                FROM optimization_recommendations
                WHERE status = 'pending'
                ORDER BY priority DESC, timestamp DESC
                LIMIT 50
            """
            )

            recommendations = []
            for row in cursor.fetchall():
                recommendations.append(
                    {"test_name": row[0], "type": row[1], "description": row[2], "priority": row[3], "status": row[4]}
                )

            conn.close()
            return jsonify(recommendations)

        @self.app.route("/api/run-optimization", methods=["POST"])
        def run_optimization():
            """Trigger test suite optimization."""
            try:
                if self.collecting_data:
                    return jsonify({"error": "Optimization already in progress"}), 409

                # Start optimization in background
                threading.Thread(target=self.run_background_optimization).start()

                return jsonify({"message": "Optimization started", "status": "running"})

            except Exception as e:
                return jsonify({"error": f"Failed to start optimization: {e}"}), 500

        @self.app.route("/api/test-execution-status")
        def test_execution_status():
            """Get current test execution status."""
            return jsonify(
                {
                    "collecting_data": self.collecting_data,
                    "last_analysis": self.last_analysis,
                    "background_tasks_active": len(schedule.jobs) > 0,
                }
            )

        @self.app.route("/api/coverage-data")
        def coverage_data():
            """Get test coverage data."""
            try:
                # Run coverage analysis
                result = subprocess.run(
                    ["python", "test_runner.py", "--all", "--coverage"], capture_output=True, text=True, timeout=120
                )

                coverage_data = self.parse_coverage_output(result.stdout)
                return jsonify(coverage_data)

            except Exception as e:
                return jsonify({"error": f"Coverage analysis failed: {e}"}), 500

    def parse_health_output(self, output: str) -> Dict:
        """Parse test suite health output."""
        health_data = {
            "total_files": 0,
            "total_tests": 0,
            "complexity_distribution": {},
            "duplicates": 0,
            "status": "unknown",
        }

        lines = output.split("\n")
        for line in lines:
            if "Total test files:" in line:
                health_data["total_files"] = int(line.split(":")[1].strip())
            elif "Total tests:" in line:
                health_data["total_tests"] = int(line.split(":")[1].strip())
            elif "Duplicate tests detected:" in line:
                health_data["duplicates"] = int(line.split(":")[1].strip())
            elif "Complexity" in line and ":" in line:
                parts = line.strip().split(":")
                if len(parts) == 2:
                    complexity = parts[0].replace("Complexity", "").strip()
                    count = int(parts[1].replace("tests", "").strip())
                    health_data["complexity_distribution"][complexity] = count

        # Determine overall health status
        if health_data["total_tests"] > 0:
            if health_data["duplicates"] == 0:
                health_data["status"] = "excellent"
            elif health_data["duplicates"] < 5:
                health_data["status"] = "good"
            else:
                health_data["status"] = "needs_attention"

        return health_data

    def parse_coverage_output(self, output: str) -> Dict:
        """Parse coverage analysis output."""
        coverage_data = {"overall_coverage": 0.0, "file_coverage": [], "missing_coverage": []}

        lines = output.split("\n")
        for line in lines:
            if "TOTAL" in line and "%" in line:
                # Extract overall coverage percentage
                parts = line.split()
                for part in parts:
                    if "%" in part:
                        coverage_data["overall_coverage"] = float(part.replace("%", ""))
                        break

        return coverage_data

    def setup_background_tasks(self):
        """Setup background maintenance tasks."""
        # Schedule regular health checks
        schedule.every(30).minutes.do(self.background_health_check)

        # Schedule daily flaky test detection
        schedule.every().day.at("02:00").do(self.background_flaky_detection)

        # Schedule weekly optimization
        schedule.every().week.do(self.background_optimization)

        # Start scheduler thread
        scheduler_thread = threading.Thread(target=self.run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()

    def run_scheduler(self):
        """Run background scheduler."""
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def background_health_check(self):
        """Perform background health check."""
        try:
            subprocess.run(["python", "test_optimizer.py", "--analyze"], capture_output=True, text=True, timeout=60)
            self.last_analysis = datetime.now().isoformat()
        except Exception as e:
            print(f"Background health check failed: {e}")

    def background_flaky_detection(self):
        """Perform background flaky test detection."""
        try:
            subprocess.run(
                ["python", "test_optimizer.py", "--detect-flaky", "--days", "7"],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except Exception as e:
            print(f"Background flaky detection failed: {e}")

    def background_optimization(self):
        """Perform background optimization."""
        try:
            subprocess.run(["python", "test_optimizer.py", "--optimize"], capture_output=True, text=True, timeout=300)
        except Exception as e:
            print(f"Background optimization failed: {e}")

    def run_background_optimization(self):
        """Run optimization in background thread."""
        self.collecting_data = True

        try:
            # Run comprehensive optimization
            subprocess.run(["python", "test_optimizer.py", "--optimize"], capture_output=True, text=True, timeout=300)

            self.last_analysis = datetime.now().isoformat()

        except Exception as e:
            print(f"Background optimization failed: {e}")

        finally:
            self.collecting_data = False

    def run(self):
        """Start the dashboard server."""
        print(f"🚀 Starting Test Maintenance Dashboard on http://localhost:{self.port}")
        self.app.run(host="0.0.0.0", port=self.port, debug=False)


# HTML Template for Dashboard
DASHBOARD_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Maintenance Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f7fa; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 2.5em; }
        .header p { margin: 5px 0 0 0; opacity: 0.8; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
        .card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card h3 { margin-top: 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        .metric { display: flex; justify-content: space-between; margin: 10px 0; }
        .metric-value { font-weight: bold; color: #27ae60; }
        .status-excellent { color: #27ae60; }
        .status-good { color: #f39c12; }
        .status-needs_attention { color: #e74c3c; }
        .flaky-test { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; padding: 10px; margin: 5px 0; }
        .recommendation { background: #e8f4f8; border: 1px solid #b8daff; border-radius: 4px; padding: 10px; margin: 5px 0; }
        .btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #2980b9; }
        .btn:disabled { background: #bdc3c7; cursor: not-allowed; }
        .loading { display: none; text-align: center; padding: 20px; }
        .chart-container { height: 300px; margin-top: 20px; }
        #performanceChart { max-height: 300px; }
        .refresh-indicator { float: right; font-size: 0.8em; color: #7f8c8d; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 Test Maintenance Dashboard</h1>
            <p>Comprehensive test suite health monitoring and intelligent optimization</p>
            <span class="refresh-indicator">Last updated: <span id="lastUpdate">Loading...</span></span>
        </div>

        <div class="grid">
            <!-- Suite Health Card -->
            <div class="card">
                <h3>📊 Suite Health Overview</h3>
                <div id="suiteHealth">
                    <div class="loading">Loading health data...</div>
                </div>
                <button class="btn" onclick="refreshHealth()">Refresh Health Check</button>
            </div>

            <!-- Flaky Tests Card -->
            <div class="card">
                <h3>⚠️ Flaky Tests Detection</h3>
                <div id="flakyTests">
                    <div class="loading">Loading flaky test data...</div>
                </div>
                <button class="btn" onclick="runFlakyDetection()">Run Flaky Detection</button>
            </div>

            <!-- Performance Trends Card -->
            <div class="card">
                <h3>📈 Performance Trends</h3>
                <div class="chart-container">
                    <canvas id="performanceChart"></canvas>
                </div>
            </div>

            <!-- Optimization Recommendations Card -->
            <div class="card">
                <h3>💡 Optimization Recommendations</h3>
                <div id="recommendations">
                    <div class="loading">Loading recommendations...</div>
                </div>
                <button class="btn" onclick="runOptimization()" id="optimizeBtn">Run Optimization</button>
            </div>

            <!-- Test Coverage Card -->
            <div class="card">
                <h3>🎯 Test Coverage Analysis</h3>
                <div id="coverage">
                    <div class="loading">Loading coverage data...</div>
                </div>
                <button class="btn" onclick="refreshCoverage()">Refresh Coverage</button>
            </div>

            <!-- System Status Card -->
            <div class="card">
                <h3>⚙️ System Status</h3>
                <div id="systemStatus">
                    <div class="loading">Loading system status...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let performanceChart;

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            loadAllData();

            // Auto-refresh every 5 minutes
            setInterval(loadAllData, 300000);
        });

        function loadAllData() {
            loadSuiteHealth();
            loadFlakyTests();
            loadPerformanceTrends();
            loadRecommendations();
            loadCoverage();
            loadSystemStatus();
            updateLastUpdate();
        }

        function updateLastUpdate() {
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        }

        function loadSuiteHealth() {
            fetch('/api/suite-health')
                .then(response => response.json())
                .then(data => {
                    const healthDiv = document.getElementById('suiteHealth');

                    if (data.error) {
                        healthDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                        return;
                    }

                    const statusClass = `status-${data.status}`;

                    healthDiv.innerHTML = `
                        <div class="metric">
                            <span>Overall Status:</span>
                            <span class="metric-value ${statusClass}">${data.status.replace('_', ' ').toUpperCase()}</span>
                        </div>
                        <div class="metric">
                            <span>Total Test Files:</span>
                            <span class="metric-value">${data.total_files}</span>
                        </div>
                        <div class="metric">
                            <span>Total Tests:</span>
                            <span class="metric-value">${data.total_tests}</span>
                        </div>
                        <div class="metric">
                            <span>Duplicate Tests:</span>
                            <span class="metric-value">${data.duplicates}</span>
                        </div>
                        <h4>Complexity Distribution:</h4>
                        ${Object.entries(data.complexity_distribution || {}).map(([complexity, count]) =>
                            `<div class="metric">
                                <span>Complexity ${complexity}:</span>
                                <span class="metric-value">${count} tests</span>
                            </div>`
                        ).join('')}
                    `;
                })
                .catch(error => {
                    document.getElementById('suiteHealth').innerHTML = `<div class="error">Failed to load health data: ${error}</div>`;
                });
        }

        function loadFlakyTests() {
            fetch('/api/flaky-tests')
                .then(response => response.json())
                .then(data => {
                    const flakyDiv = document.getElementById('flakyTests');

                    if (!data || data.length === 0) {
                        flakyDiv.innerHTML = '<div class="status-excellent">✅ No flaky tests detected</div>';
                        return;
                    }

                    flakyDiv.innerHTML = data.map(flaky => `
                        <div class="flaky-test">
                            <strong>${flaky.test_name}</strong><br>
                            Failure Rate: ${(flaky.failure_rate * 100).toFixed(1)}%
                            (${flaky.failed_runs}/${flaky.total_runs} runs)<br>
                            Confidence: ${flaky.confidence_score.toFixed(2)}
                        </div>
                    `).join('');
                })
                .catch(error => {
                    document.getElementById('flakyTests').innerHTML = `<div class="error">Failed to load flaky tests: ${error}</div>`;
                });
        }

        function loadPerformanceTrends() {
            fetch('/api/performance-trends')
                .then(response => response.json())
                .then(data => {
                    const ctx = document.getElementById('performanceChart').getContext('2d');

                    if (performanceChart) {
                        performanceChart.destroy();
                    }

                    performanceChart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: data.map(d => d.date),
                            datasets: [{
                                label: 'Average Execution Time (seconds)',
                                data: data.map(d => d.avg_execution_time),
                                borderColor: '#3498db',
                                backgroundColor: 'rgba(52, 152, 219, 0.1)',
                                tension: 0.4
                            }, {
                                label: 'Test Count',
                                data: data.map(d => d.test_count),
                                borderColor: '#e74c3c',
                                backgroundColor: 'rgba(231, 76, 60, 0.1)',
                                yAxisID: 'y1',
                                tension: 0.4
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    title: { display: true, text: 'Execution Time (s)' }
                                },
                                y1: {
                                    type: 'linear',
                                    display: true,
                                    position: 'right',
                                    title: { display: true, text: 'Test Count' },
                                    grid: { drawOnChartArea: false }
                                }
                            }
                        }
                    });
                })
                .catch(error => {
                    document.getElementById('performanceChart').innerHTML = `<div class="error">Failed to load performance trends: ${error}</div>`;
                });
        }

        function loadRecommendations() {
            fetch('/api/optimization-recommendations')
                .then(response => response.json())
                .then(data => {
                    const recDiv = document.getElementById('recommendations');

                    if (!data || data.length === 0) {
                        recDiv.innerHTML = '<div class="status-excellent">✅ No optimization recommendations</div>';
                        return;
                    }

                    recDiv.innerHTML = data.slice(0, 10).map(rec => `
                        <div class="recommendation">
                            <strong>${rec.type.replace('_', ' ').toUpperCase()}</strong><br>
                            ${rec.description}<br>
                            <small>Test: ${rec.test_name} | Priority: ${rec.priority}</small>
                        </div>
                    `).join('');
                })
                .catch(error => {
                    document.getElementById('recommendations').innerHTML = `<div class="error">Failed to load recommendations: ${error}</div>`;
                });
        }

        function loadCoverage() {
            fetch('/api/coverage-data')
                .then(response => response.json())
                .then(data => {
                    const coverageDiv = document.getElementById('coverage');

                    if (data.error) {
                        coverageDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                        return;
                    }

                    const coverageClass = data.overall_coverage >= 80 ? 'status-excellent' :
                                         data.overall_coverage >= 60 ? 'status-good' : 'status-needs_attention';

                    coverageDiv.innerHTML = `
                        <div class="metric">
                            <span>Overall Coverage:</span>
                            <span class="metric-value ${coverageClass}">${data.overall_coverage.toFixed(1)}%</span>
                        </div>
                    `;
                })
                .catch(error => {
                    document.getElementById('coverage').innerHTML = `<div class="error">Failed to load coverage: ${error}</div>`;
                });
        }

        function loadSystemStatus() {
            fetch('/api/test-execution-status')
                .then(response => response.json())
                .then(data => {
                    const statusDiv = document.getElementById('systemStatus');

                    statusDiv.innerHTML = `
                        <div class="metric">
                            <span>Data Collection:</span>
                            <span class="metric-value ${data.collecting_data ? 'status-good' : 'status-excellent'}">
                                ${data.collecting_data ? 'Active' : 'Idle'}
                            </span>
                        </div>
                        <div class="metric">
                            <span>Last Analysis:</span>
                            <span class="metric-value">${data.last_analysis || 'Never'}</span>
                        </div>
                        <div class="metric">
                            <span>Background Tasks:</span>
                            <span class="metric-value ${data.background_tasks_active ? 'status-excellent' : 'status-needs_attention'}">
                                ${data.background_tasks_active ? 'Active' : 'Inactive'}
                            </span>
                        </div>
                    `;
                })
                .catch(error => {
                    document.getElementById('systemStatus').innerHTML = `<div class="error">Failed to load system status: ${error}</div>`;
                });
        }

        function refreshHealth() {
            loadSuiteHealth();
        }

        function runFlakyDetection() {
            alert('Flaky test detection will run in background. Check back in a few minutes.');
        }

        function runOptimization() {
            const btn = document.getElementById('optimizeBtn');
            btn.disabled = true;
            btn.textContent = 'Running Optimization...';

            fetch('/api/run-optimization', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    alert(data.message || 'Optimization started');

                    // Re-enable button after 30 seconds
                    setTimeout(() => {
                        btn.disabled = false;
                        btn.textContent = 'Run Optimization';
                    }, 30000);
                })
                .catch(error => {
                    alert('Failed to start optimization: ' + error);
                    btn.disabled = false;
                    btn.textContent = 'Run Optimization';
                });
        }

        function refreshCoverage() {
            loadCoverage();
            alert('Coverage analysis will run in background. Results will update when complete.');
        }
    </script>
</body>
</html>
"""


def main():
    """Main entry point for test maintenance dashboard."""
    import argparse

    parser = argparse.ArgumentParser(description="Test Maintenance Dashboard")
    parser.add_argument("--port", type=int, default=8090, help="Dashboard port")
    parser.add_argument("--db-path", default="test_optimization.db", help="Database path")

    args = parser.parse_args()

    dashboard = TestMaintenanceDashboard(port=args.port, db_path=args.db_path)
    dashboard.run()


if __name__ == "__main__":
    main()
