# Python Coding Instructions for Technical Service Assistant

## Overview
This document provides comprehensive coding guidelines for Python development within the Technical Service Assistant project. Follow these patterns for consistency with the existing codebase and to maintain the project's architectural principles.

## Core Configuration Pattern

### ALWAYS Use Centralized Configuration
```python
# ✅ CORRECT - Always import from config.py
from config import get_settings

settings = get_settings()

# Use settings attributes directly
connection = psycopg2.connect(
    host=settings.db_host,
    port=settings.db_port,
    database=settings.db_name,
    user=settings.db_user,
    password=settings.db_password
)
```

```python
# ❌ INCORRECT - Never read os.environ directly
import os
db_host = os.getenv("DB_HOST", "localhost")  # Don't do this
```

### Configuration Access Patterns
```python
# Single instance pattern - import once at module level
from config import get_settings
settings = get_settings()  # Cached via @lru_cache

# Access typed settings attributes
model_name = settings.embedding_model
log_level = settings.log_level
is_enabled = settings.enable_table_extraction
```

## API Development with Pydantic

### Request/Response Models
```python
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class QuestionType(str, Enum):
    """Question classification for intelligent routing."""
    TECHNICAL = "technical"
    CODE = "code"
    CREATIVE = "creative"
    FACTUAL = "factual"
    MATH = "math"
    CHAT = "chat"

class ModelSelectionRequest(BaseModel):
    """Request model for intelligent routing endpoint."""
    query: str = Field(..., description="User query to analyze for optimal model selection")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens for generation")
    temperature: Optional[float] = Field(None, description="Temperature for generation")

class ModelSelectionResponse(BaseModel):
    """Response model with selected model and routing details."""
    selected_model: str = Field(..., description="Chosen model for the query type")
    question_type: QuestionType = Field(..., description="Classified question category")
    instance_url: str = Field(..., description="Selected Ollama instance URL")
    reasoning: str = Field(..., description="Explanation of model selection")
    load_score: float = Field(..., description="Instance load score at selection time")
```

### FastAPI Endpoint Patterns
```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)

@app.post("/api/intelligent-route", response_model=ModelSelectionResponse)
async def intelligent_route(request: ModelSelectionRequest):
    """Analyze query and select optimal model + instance."""
    try:
        # Question classification
        question_type = classify_question(request.query)

        # Model selection logic
        selected_model = select_model_for_question(question_type)

        # Instance health checking
        healthy_instances = await get_healthy_instances()
        if not healthy_instances:
            raise HTTPException(status_code=503, detail="No healthy Ollama instances available")

        # Load balancing
        selected_instance = select_best_instance(healthy_instances)

        return ModelSelectionResponse(
            selected_model=selected_model,
            question_type=question_type,
            instance_url=selected_instance.url,
            reasoning=f"Selected {selected_model} for {question_type} query",
            load_score=selected_instance.load_score
        )

    except ValidationError as e:
        logger.error(f"Request validation failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Intelligent routing failed: {e}")
        raise HTTPException(status_code=500, detail="Routing service unavailable")
```

## Database Operations

### Connection Management
```python
import psycopg2
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

def get_db_connection():
    """Create database connection using centralized settings."""
    try:
        connection = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            cursor_factory=psycopg2.extras.RealDictCursor  # For dict-like rows
        )
        return connection
    except psycopg2.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise

def execute_query(query: str, params: tuple = None) -> List[Dict]:
    """Execute query with proper connection handling."""
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:  # SELECT query
                return cursor.fetchall()
            connection.commit()  # INSERT/UPDATE/DELETE
            return []
    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        logger.error(f"Query execution failed: {e}")
        raise
    finally:
        if connection:
            connection.close()
```

### Vector Search Patterns
```python
def vector_search(query_text: str, top_k: int = 10) -> List[Dict]:
    """Perform vector similarity search with proper embedding."""
    # Get embedding for query
    query_embedding = get_embedding(query_text)

    # Vector similarity query with metadata
    query = """
        SELECT
            content,
            metadata,
            document_name,
            1 - (embedding <=> %s::vector) AS similarity_score
        FROM document_chunks
        WHERE 1 - (embedding <=> %s::vector) > 0.3
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    return execute_query(query, (query_embedding, query_embedding, query_embedding, top_k))
```

## Logging Standards

### Logger Setup
```python
import logging
from config import get_settings

settings = get_settings()

# Configure logging at module level
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)  # Use module name
```

### Logging Patterns
```python
# Information logging
logger.info(f"Processing PDF: {pdf_path}")
logger.info(f"Generated {len(chunks)} chunks for document {document_name}")

# Error handling with context
try:
    result = risky_operation()
    logger.info(f"Operation completed successfully: {result}")
except SpecificException as e:
    logger.error(f"Specific operation failed for {context}: {e}")
    raise
except Exception as e:
    logger.exception(f"Unexpected error in {operation_name}")  # Includes traceback
    raise

# Debug information (only when log_level=DEBUG)
logger.debug(f"Processing chunk {i+1}/{total_chunks}")
logger.debug(f"Embedding dimensions: {len(embedding)}")
```

## PDF Processing Patterns

### Text Extraction
```python
def extract_text(pdf_path: str) -> str:
    """Extract plain text from PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError(f"PyMuPDF (fitz) is required for extract_text: {e}")

    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text
```

### Chunking Strategy
```python
def chunk_text(text: str, document_name: str = "", start_index: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    """Chunk text using sentence-based approach with overlap."""
    try:
        import nltk
        from nltk.tokenize import sent_tokenize
    except ImportError:
        raise RuntimeError("NLTK is required for sentence tokenization")

    sentences = sent_tokenize(text)
    chunks = []
    current_index = start_index

    # Strategy: sent_overlap (previous sentence + current for context)
    for i, sentence in enumerate(sentences):
        # Include previous sentence for context (overlap strategy)
        content = sentences[i-1] + " " + sentence if i > 0 else sentence

        chunk = {
            "content": content.strip(),
            "metadata": {
                "document_name": document_name,
                "paragraph_index": current_index,
                "sentence_index": i,
                "chunk_strategy": settings.chunk_strategy
            }
        }
        chunks.append(chunk)
        current_index += 1

    return chunks, current_index
```

## HTTP Client Patterns

### Ollama API Calls
```python
import requests
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

def get_embedding(text: str, model: str = None, ollama_url: str = None) -> List[float]:
    """Get text embedding from Ollama with fallback logic."""
    model = model or settings.embedding_model
    base_url = ollama_url or settings.ollama_url

    # Support multiple instance URLs for load balancing
    urls_to_try = [
        base_url,
        "http://ollama-server-2:11435/api/embeddings",
        "http://ollama-server-3:11436/api/embeddings",
        "http://ollama-server-4:11437/api/embeddings"
    ]

    payload = {
        "model": model,
        "prompt": text
    }

    for url in urls_to_try:
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding")
            if not embedding:
                raise ValueError(f"No embedding in response from {url}")

            logger.debug(f"Successfully got embedding from {url}")
            return embedding

        except requests.exceptions.RequestException as e:
            logger.warning(f"Embedding request failed for {url}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error with {url}: {e}")
            continue

    raise RuntimeError(f"All Ollama instances failed for model {model}")
```

### Health Check Patterns
```python
async def check_ollama_health(instance_url: str) -> Dict[str, Any]:
    """Check health of specific Ollama instance."""
    try:
        # Quick health check endpoint
        health_url = f"{instance_url}/api/tags"

        response = requests.get(health_url, timeout=5)
        response.raise_for_status()

        models = response.json().get("models", [])

        return {
            "url": instance_url,
            "healthy": True,
            "model_count": len(models),
            "response_time": response.elapsed.total_seconds(),
            "available_models": [model["name"] for model in models]
        }

    except Exception as e:
        logger.warning(f"Health check failed for {instance_url}: {e}")
        return {
            "url": instance_url,
            "healthy": False,
            "error": str(e)
        }
```

## Error Handling Standards

### Exception Patterns
```python
class PDFProcessingError(Exception):
    """Custom exception for PDF processing failures."""
    pass

class EmbeddingServiceError(Exception):
    """Custom exception for embedding service failures."""
    pass

def process_pdf_with_error_handling(pdf_path: str) -> Dict[str, Any]:
    """Process PDF with comprehensive error handling."""
    try:
        # Validation
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if not pdf_path.lower().endswith('.pdf'):
            raise ValueError(f"File is not a PDF: {pdf_path}")

        # Processing
        text = extract_text(pdf_path)
        if not text.strip():
            raise PDFProcessingError(f"No text extracted from {pdf_path}")

        chunks, _ = chunk_text(text, document_name=os.path.basename(pdf_path))

        return {
            "status": "success",
            "pdf_path": pdf_path,
            "chunk_count": len(chunks),
            "chunks": chunks
        }

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Validation error for {pdf_path}: {e}")
        return {"status": "validation_error", "error": str(e)}

    except PDFProcessingError as e:
        logger.error(f"PDF processing error for {pdf_path}: {e}")
        return {"status": "processing_error", "error": str(e)}

    except Exception as e:
        logger.exception(f"Unexpected error processing {pdf_path}")
        return {"status": "unexpected_error", "error": str(e)}
```

## Type Annotations

### Function Signatures
```python
from typing import List, Dict, Tuple, Optional, Any, Union
from pathlib import Path

def chunk_tables(
    tables: List[Any],
    document_name: str = "",
    start_index: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """Chunk table data with proper type annotations."""
    pass

def get_ollama_instances() -> List[Dict[str, Union[str, int, bool]]]:
    """Return list of Ollama instance configurations."""
    pass

Optional[str]  # For nullable strings
List[Dict[str, Any]]  # For complex nested structures
Union[str, int]  # For multiple possible types
```

## File Organization

### Module Structure
```python
# Standard library imports
import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# Third-party imports
import requests
import psycopg2
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException

# Local imports
sys.path.append('/app')  # For Docker container compatibility
from config import get_settings

# Module-level configuration
settings = get_settings()
logger = logging.getLogger(__name__)
```

### Directory Conventions
- `pdf_processor/utils.py` - Core extraction/chunking/embedding logic (single source of truth)
- `reranker/app.py` - FastAPI service with search, chat, RAG, and intelligent routing
- `config.py` - Centralized configuration (all services import from here)
- `scripts/` - Operational scripts (evaluation, verification, etc.)
- `bin/` - Development tools and utilities
- `migrations/` - Database schema evolution

## Testing Patterns

### Unit Test Structure
```python
import pytest
from unittest.mock import Mock, patch
from pdf_processor.utils import extract_text, chunk_text

def test_extract_text_success():
    """Test successful text extraction."""
    # Arrange
    pdf_path = "test.pdf"
    expected_text = "Sample text content"

    # Act
    with patch('fitz.open') as mock_fitz:
        mock_doc = Mock()
        mock_page = Mock()
        mock_page.get_text.return_value = expected_text
        mock_doc.__iter__.return_value = [mock_page]
        mock_fitz.return_value = mock_doc

        result = extract_text(pdf_path)

    # Assert
    assert result == expected_text
    mock_fitz.assert_called_once_with(pdf_path)

def test_chunk_text_with_overlap():
    """Test chunking strategy with sentence overlap."""
    # Arrange
    text = "First sentence. Second sentence. Third sentence."
    document_name = "test.pdf"

    # Act
    chunks, final_index = chunk_text(text, document_name)

    # Assert
    assert len(chunks) == 3
    assert chunks[0]["content"] == "First sentence."
    assert chunks[1]["content"] == "First sentence. Second sentence."  # Overlap
    assert all("document_name" in chunk["metadata"] for chunk in chunks)
```

## Performance Considerations

### Memory Management
```python
# Process large files in chunks to avoid memory issues
def process_large_pdf(pdf_path: str, chunk_size: int = 1000):
    """Process large PDF files in memory-efficient chunks."""
    text = extract_text(pdf_path)

    # Process text in smaller chunks to avoid memory overflow
    sentences = sent_tokenize(text)

    for i in range(0, len(sentences), chunk_size):
        batch = sentences[i:i + chunk_size]
        batch_text = " ".join(batch)
        yield chunk_text(batch_text, os.path.basename(pdf_path), i)
```

### Connection Pooling
```python
# For high-throughput applications, consider connection pooling
from psycopg2 import pool

connection_pool = None

def get_connection_pool():
    """Initialize connection pool if needed."""
    global connection_pool
    if connection_pool is None:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password
        )
    return connection_pool
```

## Documentation Standards

### Docstring Format
```python
def intelligent_route_selection(query: str, instances: List[Dict]) -> Dict[str, Any]:
    """Select optimal Ollama instance and model for given query.

    Analyzes query type and instance health to route requests to the most
    appropriate model and available instance for optimal performance.

    Args:
        query: User query text to analyze for model selection
        instances: List of available Ollama instance configurations

    Returns:
        Dictionary containing selected model, instance URL, reasoning,
        and load balancing metrics

    Raises:
        ValueError: If no healthy instances are available
        RuntimeError: If model selection logic fails

    Example:
        >>> instances = [{"url": "http://ollama:11434", "healthy": True}]
        >>> result = intelligent_route_selection("Write Python code", instances)
        >>> result["selected_model"]
        'codellama'
    """
```

## Summary

These Python coding instructions ensure consistency with the Technical Service Assistant's architectural patterns:

- **Configuration**: Always use `config.py` settings, never read `os.environ` directly
- **API Design**: Use Pydantic models for request/response validation
- **Database**: Proper connection handling with error management
- **Logging**: Structured logging with appropriate levels and context
- **Error Handling**: Comprehensive exception management with custom types
- **Type Safety**: Full type annotations for better code quality
- **Testing**: Unit tests with mocking for external dependencies
- **Performance**: Memory-efficient processing for large files
- **Documentation**: Clear docstrings with examples and error conditions

Follow these patterns to maintain code quality and consistency across the project.
