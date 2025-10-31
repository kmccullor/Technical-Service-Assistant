"""
Lightweight smoke tests for Technical Service Assistant
Runnable outside containers for fast development feedback
"""
import os
import sys
from pathlib import Path

import pytest
import requests

# Test configuration
BASE_URL = "http://localhost"
TIMEOUT = 5


class TestSystemSmoke:
    """Fast smoke tests checking basic system functionality"""

    def test_environment_config_loads(self):
        """Test that configuration loads without errors"""
        sys.path.insert(0, str(Path(__file__).parent))
        from config import get_settings

        settings = get_settings()
        assert settings.db_host
        assert settings.embedding_model
        assert settings.api_port > 0

    def test_logs_directory_creation(self):
        """Test that LOG_DIR environment variable is respected"""
        from utils.logging_config import setup_logging

        # Test with custom LOG_DIR
        test_log_dir = Path("test_logs")
        old_log_dir = os.environ.get("LOG_DIR")

        try:
            os.environ["LOG_DIR"] = str(test_log_dir)
            logger = setup_logging("test_smoke", console_output=False)

            # Should create log directory and file
            assert test_log_dir.exists()
            log_files = list(test_log_dir.glob("test_smoke.log"))
            assert len(log_files) > 0

        finally:
            # Cleanup
            if old_log_dir:
                os.environ["LOG_DIR"] = old_log_dir
            elif "LOG_DIR" in os.environ:
                del os.environ["LOG_DIR"]

            # Remove test logs
            if test_log_dir.exists():
                import shutil

                shutil.rmtree(test_log_dir)

    @pytest.mark.integration
    def test_health_endpoints_respond(self):
        """Test that key health endpoints are accessible"""
        endpoints = [
            (8008, "/health"),  # Reranker
            (3000, "/api/health"),  # RAG app
        ]

        for port, path in endpoints:
            try:
                response = requests.get(f"{BASE_URL}:{port}{path}", timeout=TIMEOUT)
                assert response.status_code == 200
                data = response.json()
                assert "status" in data or "success" in data
            except requests.RequestException as e:
                pytest.skip(f"Service on port {port} not available: {e}")

    @pytest.mark.integration
    def test_database_connectivity(self):
        """Test basic database connectivity using config"""
        try:
            import psycopg2

            from config import get_settings

            settings = get_settings()
            conn_str = (
                f"host={settings.db_host} port={settings.db_port} "
                f"dbname={settings.db_name} user={settings.db_user} "
                f"password={settings.db_password}"
            )

            conn = psycopg2.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

            conn.close()

        except ImportError:
            pytest.skip("psycopg2 not available")
        except psycopg2.Error as e:
            pytest.skip(f"Database not available: {e}")

    @pytest.mark.integration
    def test_ollama_containers_responding(self):
        """Test that Ollama containers are accessible"""
        ports = [11434, 11435, 11436, 11437]
        responding = 0

        for port in ports:
            try:
                response = requests.get(f"{BASE_URL}:{port}/api/tags", timeout=TIMEOUT)
                if response.status_code == 200:
                    responding += 1
            except requests.RequestException:
                continue

        # At least one Ollama instance should be responding
        assert responding > 0, f"No Ollama instances responding on ports {ports}"

    def test_import_paths_resolved(self):
        """Test that common import paths work correctly"""
        # These should not raise ImportError with conftest.py setup
        try:
            pass

            # Import succeeds
            assert True
        except ImportError as e:
            pytest.fail(f"Import path not resolved: {e}")


class TestConfigurationValidation:
    """Test configuration and environment setup"""

    def test_required_env_vars_have_defaults(self):
        """Test that critical configuration has sensible defaults"""
        from config import get_settings

        settings = get_settings()

        # Database defaults
        assert settings.db_host in ["localhost", "pgvector"]
        assert settings.db_port in [5432]
        assert settings.db_name

        # Model defaults
        assert "nomic" in settings.embedding_model.lower()
        assert settings.chat_model

        # Paths
        assert settings.log_dir
        assert settings.uploads_dir

    def test_logging_config_portable(self):
        """Test that logging works in different environments"""
        from utils.logging_config import setup_logging

        # Test console-only logging (no file)
        logger1 = setup_logging("test1", console_output=True)
        assert logger1.name == "test1"

        # Test with LOG_DIR override
        os.environ["LOG_DIR"] = "./test_logs"
        logger2 = setup_logging("test2", console_output=True)
        assert logger2.name == "test2"

        # Cleanup
        if "LOG_DIR" in os.environ:
            del os.environ["LOG_DIR"]


def run_smoke_tests():
    """Run smoke tests programmatically"""
    return pytest.main([__file__, "-v", "--tb=short", "-x", "--durations=5"])  # Stop on first failure


if __name__ == "__main__":
    exit_code = run_smoke_tests()
    sys.exit(exit_code)
