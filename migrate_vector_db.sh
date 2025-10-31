#!/bin/bash
# Migration script to rebuild vector database with proper pgvector schema
# Technical Service Assistant - Vector Database Migration

set -e

echo "Starting vector database migration..."

# Backup existing data
echo "Step 1: Backing up existing data..."
docker exec pgvector pg_dump -U postgres -d vector_db --data-only \
    --table=pdf_documents --table=document_chunks \
    --table=chat_sessions --table=chat_messages > backup/vector_db_data_backup.sql

echo "Data backed up to backup/vector_db_data_backup.sql"

# Drop and recreate database
echo "Step 2: Dropping existing vector_db database..."
docker exec pgvector psql -U postgres -c "DROP DATABASE IF EXISTS vector_db;"

echo "Step 3: Creating new vector_db database..."
docker exec pgvector psql -U postgres -c "CREATE DATABASE vector_db;"

# Apply new schema
echo "Step 4: Applying new pgvector-compliant schema..."
docker exec -i pgvector psql -U postgres -d vector_db < vector_database_schema.sql

echo "Step 5: Verifying new schema..."
docker exec pgvector psql -U postgres -d vector_db -c "\dt"

echo "Step 6: Checking vector extension..."
docker exec pgvector psql -U postgres -d vector_db -c "\dx"

echo "Step 7: Verifying indexes..."
docker exec pgvector psql -U postgres -d vector_db -c "
SELECT
    indexname,
    tablename,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND indexname LIKE '%embedding%'
ORDER BY tablename, indexname;"

echo ""
echo "Vector database migration completed successfully!"
echo ""
echo "New schema includes:"
echo "- documents: Comprehensive document metadata with proper classifications"
echo "- document_chunks: Text chunks with 768-dim vector embeddings"
echo "- entities: Extracted entities (devices, protocols, platforms)"
echo "- document_entities: Many-to-many entity relationships"
echo "- keywords: Searchable keywords and tags"
echo "- search_sessions: Search performance tracking"
echo "- Optimized vector indexes: HNSW for fast similarity search"
echo "- Full-text search: tsvector indexes for keyword matching"
echo "- Metadata indexes: JSONB GIN indexes for flexible queries"
echo ""
echo "Next steps:"
echo "1. Update PDF processor to use new schema"
echo "2. Migrate existing documents with enhanced metadata extraction"
echo "3. Test vector search performance with new indexes"
