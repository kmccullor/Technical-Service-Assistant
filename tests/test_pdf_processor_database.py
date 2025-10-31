"""Ring 2 bootstrap: Database utility function tests.

These tests validate database-related functions in pdf_utils.py including
get_db_connection, remove_existing_document, insert_document_with_categorization,
and related database operations. They mock psycopg2 connections and test error
handling. They are NOT yet part of enforced coverage gating.

Run standalone (without coverage gate) via:
    pytest tests/test_pdf_processor_database.py --no-cov
"""

from datetime import datetime
from unittest.mock import Mock, patch

import psycopg2
import pytest

from pdf_processor.pdf_utils import (
    get_db_connection,
    insert_document_chunks_with_categorization,
    insert_document_with_categorization,
    insert_ingestion_metrics,
    remove_existing_document,
)


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.psycopg2.connect")
def test_get_db_connection_success(mock_connect):
    """Test successful database connection."""
    mock_conn = Mock()
    mock_connect.return_value = mock_conn

    result = get_db_connection()

    assert result == mock_conn
    mock_connect.assert_called_once()


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.psycopg2.connect")
def test_get_db_connection_error(mock_connect):
    """Test database connection error handling."""
    mock_connect.side_effect = psycopg2.OperationalError("Connection failed")

    with pytest.raises(psycopg2.OperationalError):
        get_db_connection()


# --- remove_existing_document tests ---


@pytest.mark.unit
def test_remove_existing_document_found():
    """Test removing existing document successfully."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    # Mock document exists
    mock_cursor.fetchone.side_effect = [(123,), (5,)]  # document_id, chunk_count
    mock_cursor.rowcount = 1  # Successful deletion

    result = remove_existing_document(mock_conn, "test_doc.pdf")

    assert result == 123
    assert mock_cursor.execute.call_count == 3  # SELECT id, SELECT count, DELETE

    # Check SQL calls
    calls = mock_cursor.execute.call_args_list
    assert "SELECT id FROM documents WHERE file_name" in calls[0][0][0]
    assert "SELECT COUNT(*) FROM document_chunks WHERE document_id" in calls[1][0][0]
    assert "DELETE FROM documents WHERE id" in calls[2][0][0]


@pytest.mark.unit
def test_remove_existing_document_not_found():
    """Test removing document that doesn't exist."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    # Mock document doesn't exist
    mock_cursor.fetchone.return_value = None

    result = remove_existing_document(mock_conn, "missing_doc.pdf")

    assert result is None
    assert mock_cursor.execute.call_count == 1  # Only SELECT id query


@pytest.mark.unit
def test_remove_existing_document_database_error():
    """Test error handling during document removal."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    mock_cursor.execute.side_effect = psycopg2.DatabaseError("Database error")

    with pytest.raises(psycopg2.DatabaseError):
        remove_existing_document(mock_conn, "error_doc.pdf")


# --- insert_document_with_categorization tests ---


@pytest.mark.unit
def test_insert_document_with_categorization_new_document():
    """Test inserting new document with categorization."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    # Mock document doesn't exist, then return new ID
    mock_cursor.fetchone.side_effect = [None, (456,)]

    classification = {
        "document_type": "user_guide",
        "product_name": "RNI",
        "product_version": "4.16",
        "document_category": "documentation",
        "confidence": 0.95,
        "metadata": {"key": "value"},
    }

    result = insert_document_with_categorization(mock_conn, "new_doc.pdf", "private", classification)

    assert result == 456
    mock_conn.commit.assert_called_once()

    # Check INSERT was called
    insert_call = mock_cursor.execute.call_args_list[1]  # Second call after SELECT
    assert "INSERT INTO documents" in insert_call[0][0]


@pytest.mark.unit
def test_insert_document_with_categorization_existing_document():
    """Test updating existing document with categorization."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    # Mock document exists
    mock_cursor.fetchone.return_value = (789,)

    classification = {
        "document_type": "installation_guide",
        "product_name": "FlexNet",
        "product_version": "5.0",
        "confidence": 0.8,
        "metadata": {},
    }

    result = insert_document_with_categorization(mock_conn, "existing_doc.pdf", "public", classification)

    assert result == 789
    mock_conn.commit.assert_called_once()

    # Check UPDATE was called
    update_call = mock_cursor.execute.call_args_list[1]
    assert "UPDATE documents SET" in update_call[0][0]


@pytest.mark.unit
def test_insert_document_with_categorization_error():
    """Test error handling during document insertion."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    mock_cursor.execute.side_effect = Exception("Insert failed")

    classification = {
        "document_type": "unknown",
        "product_name": "unknown",
        "product_version": "unknown",
        "confidence": 0.0,
        "metadata": {},
    }

    with pytest.raises(Exception) as exc_info:
        insert_document_with_categorization(mock_conn, "error_doc.pdf", "public", classification)

    assert "Insert failed" in str(exc_info.value)
    mock_conn.rollback.assert_called_once()


# --- insert_document_chunks_with_categorization tests ---


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.get_embedding")
def test_insert_document_chunks_with_categorization_success(mock_get_embedding):
    """Test successful chunk insertion with categorization."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    # Mock embedding generation
    mock_get_embedding.return_value = [0.1, 0.2, 0.3]

    chunks = [
        {"text": "First chunk content", "page_number": 1, "chunk_type": "text", "metadata": {"type": "text"}},
        {"text": "Second chunk content", "page_number": 2, "chunk_type": "text", "metadata": {"type": "text"}},
    ]

    classification = {"document_type": "user_guide", "product_name": "RNI"}

    result = insert_document_chunks_with_categorization(mock_conn, chunks, 123, "private", classification, "test_model")

    assert result["document_id"] == 123
    assert result["total_input_chunks"] == 2
    assert result["inserted_chunks"] == 2
    assert result["failed_embeddings"] == 0
    assert result["skipped_duplicates"] == 0

    mock_conn.commit.assert_called_once()
    mock_cursor.executemany.assert_called_once()


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.get_embedding")
def test_insert_document_chunks_empty_chunks(mock_get_embedding):
    """Test chunk insertion with empty chunk list."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    result = insert_document_chunks_with_categorization(mock_conn, [], 123, "public", {}, "test_model")

    assert result["inserted_chunks"] == 0
    assert result["total_input_chunks"] == 0
    mock_cursor.executemany.assert_not_called()


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.get_embedding")
def test_insert_document_chunks_embedding_failures(mock_get_embedding):
    """Test chunk insertion with embedding generation failures."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    # Mock embedding to fail for first chunk, succeed for second
    mock_get_embedding.side_effect = [Exception("Embedding failed"), [0.1, 0.2]]

    chunks = [
        {"text": "First chunk", "page_number": 1, "chunk_type": "text"},
        {"text": "Second chunk", "page_number": 2, "chunk_type": "text"},
    ]

    result = insert_document_chunks_with_categorization(mock_conn, chunks, 123, "public", {}, "test_model")

    assert result["inserted_chunks"] == 1  # Only one succeeded
    assert result["failed_embeddings"] == 1


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.get_embedding")
def test_insert_document_chunks_duplicate_detection(mock_get_embedding):
    """Test duplicate chunk detection and skipping."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    mock_get_embedding.return_value = [0.1, 0.2, 0.3]

    # Same text content - should detect duplicate
    chunks = [
        {"text": "Duplicate content", "page_number": 1, "chunk_type": "text"},
        {"text": "Duplicate content", "page_number": 2, "chunk_type": "text"},
    ]

    result = insert_document_chunks_with_categorization(mock_conn, chunks, 123, "public", {}, "test_model")

    assert result["inserted_chunks"] == 1  # Only first instance
    assert result["skipped_duplicates"] == 1


# --- insert_ingestion_metrics tests ---


@pytest.mark.unit
def test_insert_ingestion_metrics_success():
    """Test successful ingestion metrics insertion."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    start_time = datetime(2025, 1, 1, 10, 0, 0)
    end_time = datetime(2025, 1, 1, 10, 0, 30)  # 30 seconds later

    metrics = {
        "total_input_chunks": 10,
        "inserted_chunks": 8,
        "failed_embeddings": 1,
        "skipped_duplicates": 1,
        "by_type": {"text": 6, "table": 2},
        "elapsed_seconds": 25.5,
    }

    insert_ingestion_metrics(mock_conn, 123, "test.pdf", 1024, 5, start_time, end_time, metrics, "test_model")

    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

    # Check SQL call
    sql_call = mock_cursor.execute.call_args[0][0]
    assert "INSERT INTO document_ingestion_metrics" in sql_call


@pytest.mark.unit
def test_insert_ingestion_metrics_error():
    """Test error handling during metrics insertion."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    mock_cursor.execute.side_effect = Exception("Metrics insert failed")

    start_time = datetime.now()
    end_time = datetime.now()

    # Should not raise exception, just log error
    insert_ingestion_metrics(mock_conn, 123, "test.pdf", 1024, 5, start_time, end_time, {}, "test_model")

    mock_conn.rollback.assert_called_once()


@pytest.mark.unit
def test_insert_ingestion_metrics_calculations():
    """Test metrics calculations and derived values."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    start_time = datetime(2025, 1, 1, 10, 0, 0)
    end_time = datetime(2025, 1, 1, 10, 1, 0)  # 60 seconds later

    metrics = {
        "total_input_chunks": 20,
        "inserted_chunks": 18,
        "by_type": {"text": 10, "table": 5, "image": 3, "image_ocr": 2},
        "elapsed_seconds": 45.0,
    }

    insert_ingestion_metrics(mock_conn, 123, "test.pdf", 2048, 10, start_time, end_time, metrics, "embedding_model")

    # Extract the parameters passed to execute
    call_args = mock_cursor.execute.call_args[0][1]

    # Check calculated values
    duration = call_args[4]  # processing_duration_seconds
    assert duration == 60.0

    success_rate = call_args[19]  # success_rate
    assert success_rate == 18 / 20  # inserted/total

    ocr_yield_ratio = call_args[18]  # ocr_yield_ratio
    assert ocr_yield_ratio == 2 / 3  # ocr_chunks/image_chunks
