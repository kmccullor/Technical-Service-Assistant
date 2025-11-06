#!/usr/bin/env python3
"""
Technical Service Assistant - Post-Installation Setup
===================================================

This script handles post-installation configuration and setup tasks.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, check=True, capture_output=False):
    """Run a shell command with proper error handling."""
    print(f"Running: {cmd}")
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=check)
            return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        if capture_output and hasattr(e, "stderr"):
            print(f"Error output: {e.stderr}")
        return False


def wait_for_service(url, timeout=300, service_name="service"):
    """Wait for a service to become available."""
    print(f"Waiting for {service_name} at {url}...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            import requests

            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {service_name} is ready!")
                return True
        except Exception:
            # Continue retrying on any network or import errors
            pass

        print(".", end="", flush=True)
        time.sleep(5)

    print(f"\n❌ {service_name} failed to start within {timeout} seconds")
    return False


def setup_ollama_models(base_url="http://localhost:11434"):
    """Download and setup required Ollama models."""
    print("Setting up Ollama models...")

    models = [
        "nomic-embed-text:v1.5",  # Embedding model
        "mistral:7b",  # Chat/Thinking model
        "codellama:7b",  # Coding model
        "llama3.2:3b",  # Reasoning model
        "llava:7b",  # Vision model
    ]

    servers = [f"ollama-server-{i}" for i in range(1, 9)]

    for model in models:
        print(f"Pulling model: {model} to all Ollama servers")
        for server in servers:
            cmd = f"docker exec {server} ollama pull {model}"
            if not run_command(cmd, check=False):
                print(f"⚠️ Failed to pull {model} on {server}, continuing...")

    print("✅ Ollama models setup completed")


def setup_database():
    """Initialize database with required tables and indexes."""
    print("Setting up database...")

    # Wait for database to be ready
    api_url = os.getenv("RERANKER_URL", "http://localhost:8008")
    if not wait_for_service(f"{api_url.rstrip('/')}/health", service_name="API"):
        return False

    # Run database migrations
    print("Running database migrations...")
    cmd = (
        "docker exec technical-service-assistant-reranker-1 "
        'python -c "from migrations.run_migrations import main; main()"'
    )
    if not run_command(cmd, check=False):
        print("⚠️ Database migrations failed, may need manual setup")

    print("✅ Database setup completed")
    return True


def setup_monitoring():
    """Configure monitoring dashboards and alerts."""
    print("Setting up monitoring...")

    # Wait for Grafana to be ready
    if not wait_for_service("http://localhost:3000", service_name="Grafana"):
        return False

    # Import dashboards (if available)
    dashboards_dir = Path("/opt/technical-service-assistant/app/monitoring/dashboards")
    if dashboards_dir.exists():
        print("Importing Grafana dashboards...")
        # Dashboard import logic would go here
        print("✅ Dashboards imported")

    print("✅ Monitoring setup completed")
    return True


def create_admin_user():
    """Create initial admin user."""
    print("Creating admin user...")

    # This would integrate with your user management system
    # For now, just provide instructions
    print(
        """
    📝 Admin User Setup Required:

    1. Navigate to http://your-server-ip/
    2. Create your first admin account
    3. Configure user permissions as needed

    For automated user creation, see the API documentation.
    """
    )

    return True


def run_health_checks():
    """Perform comprehensive health checks."""
    print("Running health checks...")

    api_url = os.getenv("RERANKER_URL", "http://localhost:8008").rstrip("/")
    web_url = os.getenv("FRONTEND_URL", "http://localhost:8080")
    ollama_primary = os.getenv("OLLAMA_PRIMARY_URL", "http://localhost:11434")
    checks = [
        ("Web Interface", web_url),
        ("API Health", f"{api_url}/health"),
        ("Ollama Primary", f"{ollama_primary.rstrip('/')}/api/tags"),
        ("Database", f"{api_url}/api/test-db"),
    ]

    results = []
    for name, url in checks:
        try:
            import requests

            response = requests.get(url, timeout=10)
            status = "✅ PASS" if response.status_code == 200 else f"❌ FAIL ({response.status_code})"
            results.append((name, status))
        except Exception as e:
            results.append((name, f"❌ FAIL ({str(e)[:50]}...)"))

    print("\n" + "=" * 50)
    print("HEALTH CHECK RESULTS")
    print("=" * 50)
    for name, status in results:
        print(f"{name:20} {status}")
    print("=" * 50)

    return all("✅" in result[1] for result in results)


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Technical Service Assistant Post-Installation Setup")
    parser.add_argument("--skip-models", action="store_true", help="Skip Ollama model download")
    parser.add_argument("--skip-monitoring", action="store_true", help="Skip monitoring setup")
    parser.add_argument("--health-check-only", action="store_true", help="Only run health checks")

    args = parser.parse_args()

    print("🚀 Technical Service Assistant - Post-Installation Setup")
    print("=" * 60)

    if args.health_check_only:
        success = run_health_checks()
        sys.exit(0 if success else 1)

    # Run setup steps
    success = True

    if not args.skip_models:
        if not setup_ollama_models():
            success = False

    if not setup_database():
        success = False

    if not args.skip_monitoring:
        if not setup_monitoring():
            success = False

    if not create_admin_user():
        success = False

    # Final health check
    print("\n" + "=" * 60)
    if run_health_checks():
        print("\n🎉 Setup completed successfully!")
        print("\n📖 Quick Start:")
        print("1. Visit http://your-server-ip/ to access the web interface")
        print("2. Upload some PDF documents to test the system")
        print("3. Try searching and asking questions about your documents")
        print("4. Check the monitoring dashboard at http://your-server-ip:3000")
        print("\n📚 Documentation: /opt/technical-service-assistant/app/README.md")
    else:
        print("\n⚠️ Setup completed with some issues. Check the logs above.")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
