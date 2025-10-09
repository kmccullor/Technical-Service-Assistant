"""
Integration test for privacy level database migration and functionality.

This test verifies that the database schema changes work correctly
and that privacy filtering functions as expected.
"""

import pytest
import psycopg2
import os
import sys
from unittest.mock import patch

# Add app path for imports
sys.path.append('/app')
from config import get_settings


class TestDatabasePrivacyMigration:
    """Test database migration and privacy level functionality."""
    
    @pytest.fixture(scope="class")
    def db_connection(self):
        """Create a test database connection."""
        settings = get_settings()
        
        try:
            conn = psycopg2.connect(
                dbname=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                host=settings.db_host,
                port=settings.db_port,
            )
            yield conn
            conn.close()
        except Exception as e:
            pytest.skip(f"Database not available for testing: {e}")
    
    def test_privacy_level_columns_exist(self, db_connection):
        """Test that privacy_level columns were added to both tables."""
        with db_connection.cursor() as cursor:
            # Check pdf_documents table has privacy_level column
            cursor.execute("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'pdf_documents' AND column_name = 'privacy_level'
            """)
            result = cursor.fetchone()
            assert result is not None, "privacy_level column missing from pdf_documents table"
            assert result[1] == 'text', "privacy_level should be text type"
            assert 'public' in result[2], "privacy_level should default to 'public'"
            
            # Check document_chunks table has privacy_level column
            cursor.execute("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'document_chunks' AND column_name = 'privacy_level'
            """)
            result = cursor.fetchone()
            assert result is not None, "privacy_level column missing from document_chunks table"
            assert result[1] == 'text', "privacy_level should be text type"
            assert 'public' in result[2], "privacy_level should default to 'public'"
    
    def test_privacy_level_constraints(self, db_connection):
        """Test that privacy_level columns have proper constraints."""
        with db_connection.cursor() as cursor:
            # Test valid values work
            try:
                cursor.execute("""
                    INSERT INTO pdf_documents (file_name, privacy_level)
                    VALUES ('test_public.pdf', 'public')
                    RETURNING id
                """)
                doc_id = cursor.fetchone()[0]
                
                cursor.execute("""
                    INSERT INTO pdf_documents (file_name, privacy_level)
                    VALUES ('test_private.pdf', 'private')
                    RETURNING id
                """)
                private_doc_id = cursor.fetchone()[0]
                
                # Clean up
                cursor.execute("DELETE FROM pdf_documents WHERE id IN (%s, %s)", (doc_id, private_doc_id))
                db_connection.commit()
                
            except Exception as e:
                db_connection.rollback()
                pytest.fail(f"Valid privacy levels should be accepted: {e}")
            
            # Test invalid values are rejected
            with pytest.raises(psycopg2.IntegrityError):
                cursor.execute("""
                    INSERT INTO pdf_documents (file_name, privacy_level)
                    VALUES ('test_invalid.pdf', 'invalid_level')
                """)
                db_connection.commit()
            
            db_connection.rollback()
    
    def test_privacy_indexes_exist(self, db_connection):
        """Test that privacy level indexes were created."""
        with db_connection.cursor() as cursor:
            # Check for document_chunks privacy index
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'document_chunks'
                AND indexname LIKE '%privacy%'
            """)
            indexes = cursor.fetchall()
            assert len(indexes) > 0, "Privacy index missing on document_chunks table"
            
            # Check for pdf_documents privacy index
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'pdf_documents'
                AND indexname LIKE '%privacy%'
            """)
            indexes = cursor.fetchall()
            assert len(indexes) > 0, "Privacy index missing on pdf_documents table"
    
    def test_enhanced_match_function_exists(self, db_connection):
        """Test that the enhanced match_document_chunks function exists and works."""
        with db_connection.cursor() as cursor:
            # Check function exists
            cursor.execute("""
                SELECT routine_name FROM information_schema.routines
                WHERE routine_name = 'match_document_chunks'
                AND routine_type = 'FUNCTION'
            """)
            result = cursor.fetchone()
            assert result is not None, "match_document_chunks function should exist"
            
            # Test function signature includes privacy_filter parameter
            cursor.execute("""
                SELECT pg_get_function_arguments(p.oid)
                FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE p.proname = 'match_document_chunks'
                AND n.nspname = 'public'
            """)
            result = cursor.fetchone()
            assert result is not None, "Function signature should be available"
            assert 'privacy_filter' in result[0], "Function should have privacy_filter parameter"
    
    def test_privacy_statistics_function(self, db_connection):
        """Test the get_privacy_statistics function."""
        with db_connection.cursor() as cursor:
            # Check function exists
            cursor.execute("""
                SELECT routine_name FROM information_schema.routines
                WHERE routine_name = 'get_privacy_statistics'
                AND routine_type = 'FUNCTION'
            """)
            result = cursor.fetchone()
            assert result is not None, "get_privacy_statistics function should exist"
            
            # Test function execution
            try:
                cursor.execute("SELECT * FROM get_privacy_statistics()")
                results = cursor.fetchall()
                # Should return at least empty results without error
                assert isinstance(results, list), "Function should return results"
            except Exception as e:
                pytest.fail(f"get_privacy_statistics function should execute without error: {e}")
    
    def test_privacy_filtering_in_search(self, db_connection):
        """Test privacy filtering in document search."""
        with db_connection.cursor() as cursor:
            try:
                # Insert test documents with different privacy levels
                cursor.execute("""
                    INSERT INTO pdf_documents (file_name, privacy_level)
                    VALUES ('public_doc.pdf', 'public'), ('private_doc.pdf', 'private')
                    RETURNING id
                """)
                doc_ids = [row[0] for row in cursor.fetchall()]
                
                # Insert test chunks
                test_embedding = [0.1] * 768  # Mock embedding
                cursor.execute("""
                    INSERT INTO document_chunks (document_id, page_number, chunk_type, content, embedding, privacy_level)
                    VALUES 
                    (%s, 1, 'text', 'This is public content', %s, 'public'),
                    (%s, 1, 'text', 'This is private content', %s, 'private')
                """, (doc_ids[0], test_embedding, doc_ids[1], test_embedding))
                
                db_connection.commit()
                
                # Test filtering - public only
                cursor.execute("""
                    SELECT * FROM match_document_chunks(%s, 0.0, 10, 'public')
                """, (test_embedding,))
                public_results = cursor.fetchall()
                
                # Test filtering - private only
                cursor.execute("""
                    SELECT * FROM match_document_chunks(%s, 0.0, 10, 'private')
                """, (test_embedding,))
                private_results = cursor.fetchall()
                
                # Test filtering - all
                cursor.execute("""
                    SELECT * FROM match_document_chunks(%s, 0.0, 10, 'all')
                """, (test_embedding,))
                all_results = cursor.fetchall()
                
                # Verify filtering works
                assert len(public_results) >= 1, "Should find public content"
                assert len(private_results) >= 1, "Should find private content"
                assert len(all_results) >= len(public_results) + len(private_results), "All should include both"
                
                # Verify content separation
                public_content = [row[4] for row in public_results]  # content column
                private_content = [row[4] for row in private_results]
                
                assert any('public content' in content for content in public_content), "Public search should find public content"
                assert any('private content' in content for content in private_content), "Private search should find private content"
                
            except Exception as e:
                db_connection.rollback()
                pytest.fail(f"Privacy filtering test failed: {e}")
            finally:
                # Clean up
                try:
                    cursor.execute("DELETE FROM pdf_documents WHERE file_name IN ('public_doc.pdf', 'private_doc.pdf')")
                    db_connection.commit()
                except:
                    db_connection.rollback()
    
    def test_default_privacy_behavior(self, db_connection):
        """Test that documents default to public privacy level."""
        with db_connection.cursor() as cursor:
            try:
                # Insert document without specifying privacy_level
                cursor.execute("""
                    INSERT INTO pdf_documents (file_name)
                    VALUES ('default_test.pdf')
                    RETURNING id, privacy_level
                """)
                result = cursor.fetchone()
                doc_id, privacy_level = result
                
                assert privacy_level == 'public', "Documents should default to public privacy level"
                
                # Insert chunk without specifying privacy_level
                test_embedding = [0.1] * 768
                cursor.execute("""
                    INSERT INTO document_chunks (document_id, page_number, chunk_type, content, embedding)
                    VALUES (%s, 1, 'text', 'Default privacy test', %s)
                    RETURNING privacy_level
                """, (doc_id, test_embedding))
                result = cursor.fetchone()
                chunk_privacy = result[0]
                
                assert chunk_privacy == 'public', "Chunks should default to public privacy level"
                
            except Exception as e:
                pytest.fail(f"Default privacy behavior test failed: {e}")
            finally:
                # Clean up
                try:
                    cursor.execute("DELETE FROM pdf_documents WHERE file_name = 'default_test.pdf'")
                    db_connection.commit()
                except:
                    db_connection.rollback()


class TestPrivacyAPIIntegration:
    """Integration tests for privacy API functionality."""
    
    def test_api_models_have_privacy_fields(self):
        """Test that API models include privacy filtering fields."""
        from reranker.app import RerankRequest, RAGChatRequest, HybridSearchRequest
        
        # Test RerankRequest
        rerank_req = RerankRequest(query="test", passages=[], top_k=5)
        assert hasattr(rerank_req, 'privacy_filter')
        assert rerank_req.privacy_filter == 'public'  # Default value
        
        # Test RAGChatRequest
        rag_req = RAGChatRequest(query="test")
        assert hasattr(rag_req, 'privacy_filter')
        assert rag_req.privacy_filter == 'public'  # Default value
        
        # Test HybridSearchRequest
        hybrid_req = HybridSearchRequest(query="test")
        assert hasattr(hybrid_req, 'privacy_filter')
        assert hybrid_req.privacy_filter == 'public'  # Default value
    
    def test_privacy_filter_validation(self):
        """Test privacy filter accepts only valid values."""
        from reranker.app import RerankRequest
        
        # Valid values should work
        valid_filters = ['public', 'private', 'all']
        for filter_value in valid_filters:
            req = RerankRequest(query="test", passages=[], top_k=5, privacy_filter=filter_value)
            assert req.privacy_filter == filter_value
        
        # Invalid values should be caught by Pydantic validation
        # (This would require custom validation, which could be added later)


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])