"""Pytest configuration and fixtures for the Technical Service Assistant test suite."""

import os
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
import httpx
from fastapi.testclient import TestClient

# Import your main application components
from config import get_settings


def pytest_configure(config: pytest.Config) -> None:
    """Relax default addopts when PYTEST_RELAX_DEFAULTS is enabled."""
    relax_flag = os.getenv("PYTEST_RELAX_DEFAULTS", "").lower()
    if relax_flag not in {"1", "true", "yes", "on"}:
        return

    # Allow full test selection instead of the focused keyword filter.
    if getattr(config.option, "keyword", None):
        config.option.keyword = ""

    # Disable coverage enforcement and reports for sandboxed runs.
    for attr in ("cov", "cov_source", "cov_report"):
        if hasattr(config.option, attr):
            setattr(config.option, attr, [])
    if hasattr(config.option, "no_cov"):
        config.option.no_cov = True
    if hasattr(config.option, "cov_fail_under"):
        config.option.cov_fail_under = 0


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():  # backward compatibility placeholder
    """Return current settings object (no overrides)."""
    return get_settings()


@pytest.fixture
def temp_upload_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test file uploads."""
    with tempfile.TemporaryDirectory() as temp_dir:
        upload_path = Path(temp_dir) / "uploads"
        upload_path.mkdir(exist_ok=True)
        yield upload_path


@pytest.fixture
def mock_database():
    """Mock database connection for testing."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


@pytest.fixture
def mock_ollama_response():
    """Mock Ollama API response for testing."""
    return {
        "embedding": [0.1, 0.2, 0.3, 0.4, 0.5] * 256,  # 1280-dimensional embedding
        "model": "nomic-embed-text:v1.5"
    }


@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create an async HTTP client for testing."""
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def test_client() -> TestClient:
    from reranker.app import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_pdf_content() -> bytes:
    """Generate sample PDF content for testing."""
    # This is a minimal PDF content for testing
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Hello, World!) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
300
%%EOF"""


@pytest.fixture
def sample_document_chunks():
    """Generate sample document chunks for testing."""
    return [
        {
            "id": 1,
            "content": "This is the first chunk of content about artificial intelligence.",
            "metadata": {
                "document_name": "ai_paper.pdf",
                "page_number": 1,
                "chunk_index": 0,
                "chunk_type": "text"
            },
            "embedding": [0.1] * 1280
        },
        {
            "id": 2,
            "content": "This is the second chunk discussing machine learning algorithms.",
            "metadata": {
                "document_name": "ai_paper.pdf",
                "page_number": 1,
                "chunk_index": 1,
                "chunk_type": "text"
            },
            "embedding": [0.2] * 1280
        }
    ]


@pytest.fixture
def mock_search_results():
    """Mock search results for testing."""
    return {
        "chunks": [
            {
                "content": "Relevant content about the search query.",
                "metadata": {"document_name": "test.pdf", "page_number": 1},
                "similarity_score": 0.95
            }
        ],
        "total_results": 1,
        "search_time_ms": 50
    }


# Async fixtures for testing async functions
@pytest.fixture
async def mock_async_database():
    """Mock async database connection for testing."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    return mock_pool


# Performance testing fixtures
@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()


# Markers for different test types
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.slow = pytest.mark.slow
