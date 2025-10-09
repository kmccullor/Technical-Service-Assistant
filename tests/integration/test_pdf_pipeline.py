"""Integration tests for PDF processing pipeline."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPDFProcessingPipeline:
    """Test the complete PDF processing workflow."""
    
    @pytest.mark.integration
    def test_pdf_upload_and_processing(self, temp_upload_dir, sample_pdf_content):
        """Test complete PDF upload and processing workflow."""
        # Create a test PDF file
        test_pdf = temp_upload_dir / "test_document.pdf"
        test_pdf.write_bytes(sample_pdf_content)
        
        # Import your PDF processing functions
        # from pdf_processor.utils import process_pdf_file
        
        # Mock external dependencies
        with patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                "embedding": [0.1] * 1280
            }
            
            # Test the processing pipeline
            # result = process_pdf_file(str(test_pdf))
            
            # Assertions will depend on your actual implementation
            # assert result is not None
            # assert len(result) > 0
        
        # Clean up
        test_pdf.unlink()
    
    @pytest.mark.integration
    def test_embedding_generation(self):
        """Test embedding generation for text chunks."""
        test_text = "This is a test document about artificial intelligence."
        
        # Mock Ollama API response
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "embedding": [0.1] * 1280,
                "model": "nomic-embed-text:v1.5"
            }
            
            # Test embedding generation
            # from pdf_processor.utils import generate_embedding
            # embedding = generate_embedding(test_text)
            
            # assert embedding is not None
            # assert len(embedding) == 1280
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_database_storage(self, mock_database):
        """Test storing processed chunks in database."""
        mock_conn, mock_cursor = mock_database
        
        # Test data
        test_chunk = {
            "content": "Test content",
            "metadata": {"document_name": "test.pdf", "page_number": 1},
            "embedding": [0.1] * 1280
        }
        
        # Mock database operations
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)  # Mock inserted ID
        
        # Test database storage
        # This will depend on your actual database functions
        # from pdf_processor.utils import store_chunk
        # chunk_id = store_chunk(mock_conn, test_chunk)
        
        # assert chunk_id == 1
        # mock_cursor.execute.assert_called_once()
    
    @pytest.mark.integration
    def test_search_functionality(self, mock_search_results):
        """Test the search functionality end-to-end."""
        test_query = "artificial intelligence"
        
        # Mock database search
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock search results
            mock_cursor.fetchall.return_value = [
                ("Test content", {"document_name": "test.pdf"}, 0.95)
            ]
            
            # Test search function
            # from reranker.app import search_documents
            # results = search_documents(test_query)
            
            # assert results is not None
            # assert len(results) > 0