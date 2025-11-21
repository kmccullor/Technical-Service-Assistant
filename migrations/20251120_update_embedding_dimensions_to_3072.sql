-- Migration: Align embedding dimensions with llama3.2:3b output (3072 dimensions)
-- Updates existing vector columns, indexes, and helper functions to use vector(3072)

BEGIN;

-- Drop indexes that depend on old dimensions
DROP INDEX IF EXISTS document_chunks_embedding_hnsw_idx;
DROP INDEX IF EXISTS embeddings_embedding_idx;
DROP INDEX IF EXISTS idx_embeddings_vector;

-- Reset and widen chunk embedding column
ALTER TABLE IF EXISTS document_chunks
DROP COLUMN IF EXISTS embedding;
ALTER TABLE IF EXISTS document_chunks
ADD COLUMN embedding vector(3072);

-- Reset and widen generic embeddings table column
ALTER TABLE IF EXISTS embeddings
DROP COLUMN IF EXISTS embedding;
ALTER TABLE IF EXISTS embeddings
ADD COLUMN embedding vector(3072);

-- Index creation omitted because pgvector index types currently cap dimensions at 2000.
-- Downstream services may temporarily rely on brute-force scans until a lower-dim model or ANN proxy is deployed.

-- Refresh similarity helper functions to match 3072-dim vectors
CREATE OR REPLACE FUNCTION match_document_chunks (
  query_embedding vector(3072),
  match_threshold float,
  match_count int,
  privacy_filter text DEFAULT 'public'
)
RETURNS TABLE (
  id bigint,
  document_id bigint,
  page_number integer,
  chunk_type text,
  content text,
  privacy_level text,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    document_chunks.id,
    document_chunks.document_id,
    document_chunks.page_number,
    document_chunks.chunk_type,
    document_chunks.content,
    document_chunks.privacy_level,
    1 - (document_chunks.embedding <=> query_embedding) AS similarity
  FROM document_chunks
  WHERE 1 - (document_chunks.embedding <=> query_embedding) > match_threshold
    AND (privacy_filter = 'all' OR document_chunks.privacy_level = privacy_filter)
  ORDER BY similarity DESC
  LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION match_document_chunks_categorized (
  query_embedding vector(3072),
  match_threshold float,
  match_count int,
  privacy_filter text DEFAULT 'public',
  document_type_filter text DEFAULT 'all',
  product_filter text DEFAULT 'all'
)
RETURNS TABLE (
  id bigint,
  document_id bigint,
  page_number integer,
  chunk_type text,
  content text,
  privacy_level text,
  document_type text,
  product_name text,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    document_chunks.id,
    document_chunks.document_id,
    document_chunks.page_number,
    document_chunks.chunk_type,
    document_chunks.content,
    document_chunks.privacy_level,
    document_chunks.document_type,
    document_chunks.product_name,
    1 - (document_chunks.embedding <=> query_embedding) AS similarity
  FROM document_chunks
  WHERE 1 - (document_chunks.embedding <=> query_embedding) > match_threshold
    AND (privacy_filter = 'all' OR document_chunks.privacy_level = privacy_filter)
    AND (document_type_filter = 'all' OR document_chunks.document_type = document_type_filter)
    AND (product_filter = 'all' OR document_chunks.product_name = product_filter)
  ORDER BY similarity DESC
  LIMIT match_count;
$$;

-- Update model catalog entry for llama3.2:3b (idempotent)
INSERT INTO models (name, provider, dimension_size)
VALUES ('llama3.2:3b', 'ollama', 3072)
ON CONFLICT (name) DO UPDATE SET dimension_size = EXCLUDED.dimension_size;

COMMIT;
