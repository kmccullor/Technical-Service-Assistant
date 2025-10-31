#!/usr/bin/env python3
"""
Debug script to identify what's causing node-exporter connection storms.
This will help identify the pattern and frequency of connections.
"""

import subprocess
import time
from datetime import datetime

import requests


def test_node_exporter_access():
    """Test if we can access node-exporter normally"""
    try:
        response = requests.get("http://localhost:9100/metrics", timeout=5)
        print(f"✓ Node-exporter accessible: {response.status_code}")
        return True
    except Exception as e:
        print(f"✗ Node-exporter access failed: {e}")
        return False


def monitor_connections():
    """Monitor active connections to port 9100"""
    try:
        result = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True)
        connections = [line for line in result.stdout.split("\n") if "9100" in line]
        print(f"Active connections to port 9100: {len(connections)}")
        for conn in connections:
            print(f"  {conn.strip()}")
    except Exception as e:
        print(f"Error monitoring connections: {e}")


def check_prometheus_targets():
    """Check if Prometheus is properly configured"""
    try:
        response = requests.get("http://localhost:9091/api/v1/targets", timeout=5)
        targets = response.json()
        node_targets = [
            t
            for t in targets.get("data", {}).get("activeTargets", [])
            if "node-exporter" in t.get("discoveredLabels", {}).get("__address__", "")
        ]
        print(f"Prometheus node-exporter targets: {len(node_targets)}")
        for target in node_targets:
            print(f"  State: {target.get('health')} - {target.get('lastError', 'No error')}")
    except Exception as e:
        print(f"Error checking Prometheus targets: {e}")


def main():
    print(f"=== Node-exporter Connection Debug - {datetime.now()} ===")

    print("\n1. Testing direct access:")
    test_node_exporter_access()

    print("\n2. Monitoring network connections:")
    monitor_connections()

    print("\n3. Checking Prometheus configuration:")
    check_prometheus_targets()

    print("\n4. Monitoring for 30 seconds...")
    for i in range(6):
        time.sleep(5)
        print(f"  Check {i+1}/6: ", end="")
        accessible = test_node_exporter_access()
        if not accessible:
            break


if __name__ == "__main__":
    main()
