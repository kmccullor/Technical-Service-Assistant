"""
Test configuration for Technical Service Assistant
Handles path setup and common fixtures for pytest runs
"""
import builtins
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock as _AsyncMock
from unittest.mock import patch as _patch

# Add project root to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Add specific module directories
sys.path.insert(0, str(project_root / "pdf_processor"))
sys.path.insert(0, str(project_root / "reranker"))
sys.path.insert(0, str(project_root / "utils"))
sys.path.insert(0, str(project_root / "bin"))
sys.path.insert(0, str(project_root / "scripts"))

# Set environment variables for testing
os.environ.setdefault("LOG_DIR", str(project_root / "logs"))
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "vector_db")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "postgres")
os.environ.setdefault("EMBEDDING_MODEL", "nomic-embed-text:v1.5")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

if not hasattr(builtins, "patch"):
    builtins.patch = _patch
if not hasattr(builtins, "AsyncMock"):
    builtins.AsyncMock = _AsyncMock

# Mock setup for testing without external dependencies
import pytest


@pytest.fixture(scope="session")
def mock_logging():
    """Mock logging setup to prevent file permission issues in tests"""

    def mock_setup_logging(*args, **kwargs):
        import logging

        return logging.getLogger("test")

    # Monkey patch the logging setup
    import utils.logging_config

    utils.logging_config.setup_logging = mock_setup_logging
    return mock_setup_logging


@pytest.fixture(scope="session")
def test_logs_dir():
    """Ensure logs directory exists for testing"""
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


# Auto-use fixtures
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest with project-specific settings"""
    # Ensure logs directory exists
    (project_root / "logs").mkdir(exist_ok=True)

    # Set up mock for database connections during collection
    try:
        pass

        # Don't actually mock here, just ensure import works
    except ImportError:
        pass


def pytest_collection_modifyitems(config, items):
    """Modify test items during collection"""
    # Add markers for slow tests
    for item in items:
        if "database" in item.nodeid or "integration" in item.nodeid:
            item.add_marker(pytest.mark.slow)
        if "connectivity" in item.nodeid:
            item.add_marker(pytest.mark.integration)
