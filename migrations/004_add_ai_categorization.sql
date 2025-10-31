-- Migration 004: Add AI-powered document categorization and product identification
-- This enables intelligent classification of document types and products

-- Add categorization columns to pdf_documents table
ALTER TABLE pdf_documents
ADD COLUMN IF NOT EXISTS document_type text DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS product_name text DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS product_version text DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS document_category text DEFAULT 'documentation',
ADD COLUMN IF NOT EXISTS classification_confidence float DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS ai_metadata jsonb DEFAULT '{}';

-- Create indexes for efficient filtering and searching
CREATE INDEX IF NOT EXISTS idx_pdf_documents_document_type ON pdf_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_product_name ON pdf_documents(product_name);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_product_version ON pdf_documents(product_version);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_document_category ON pdf_documents(document_category);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_ai_metadata ON pdf_documents USING gin(ai_metadata);

-- Add categorization columns to document_chunks table for enhanced search
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS document_type text DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS product_name text DEFAULT 'unknown';

-- Create indexes for chunk-level categorization
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_type ON document_chunks(document_type);
CREATE INDEX IF NOT EXISTS idx_document_chunks_product_name ON document_chunks(product_name);

-- Enhanced search function with categorization filtering
CREATE OR REPLACE FUNCTION match_document_chunks_categorized (
  query_embedding vector(768),
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

-- Function to get categorization statistics
CREATE OR REPLACE FUNCTION get_categorization_statistics()
RETURNS TABLE (
  document_type text,
  product_name text,
  privacy_level text,
  document_count bigint,
  avg_confidence float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    d.document_type,
    d.product_name,
    d.privacy_level,
    COUNT(*) as document_count,
    ROUND(AVG(d.classification_confidence)::numeric, 3) as avg_confidence
  FROM pdf_documents d
  GROUP BY d.document_type, d.product_name, d.privacy_level
  ORDER BY d.product_name, d.document_type, d.privacy_level;
$$;

-- Function to search documents by category and product
CREATE OR REPLACE FUNCTION search_documents_by_category(
  search_document_type text DEFAULT 'all',
  search_product text DEFAULT 'all',
  search_privacy text DEFAULT 'public'
)
RETURNS TABLE (
  id bigint,
  file_name text,
  document_type text,
  product_name text,
  product_version text,
  privacy_level text,
  classification_confidence float,
  created_at timestamp with time zone
)
LANGUAGE sql STABLE
AS $$
  SELECT
    d.id,
    d.file_name,
    d.document_type,
    d.product_name,
    d.product_version,
    d.privacy_level,
    d.classification_confidence,
    d.uploaded_at as created_at
  FROM pdf_documents d
  WHERE (search_document_type = 'all' OR d.document_type = search_document_type)
    AND (search_product = 'all' OR d.product_name = search_product)
    AND (search_privacy = 'all' OR d.privacy_level = search_privacy)
  ORDER BY d.product_name, d.document_type, d.uploaded_at DESC;
$$;

-- Add comments for documentation
COMMENT ON COLUMN pdf_documents.document_type IS 'AI-classified document type (user_guide, installation_guide, reference_manual, etc.)';
COMMENT ON COLUMN pdf_documents.product_name IS 'AI-identified product or system name';
COMMENT ON COLUMN pdf_documents.product_version IS 'Extracted product version number';
COMMENT ON COLUMN pdf_documents.document_category IS 'High-level document category (documentation, specification, guide, etc.)';
COMMENT ON COLUMN pdf_documents.classification_confidence IS 'AI confidence score for classification (0.0-1.0)';
COMMENT ON COLUMN pdf_documents.ai_metadata IS 'Additional AI-extracted metadata in JSON format';
COMMENT ON FUNCTION match_document_chunks_categorized IS 'Enhanced search with privacy and categorization filtering';
COMMENT ON FUNCTION get_categorization_statistics IS 'Returns statistics on document categorization and confidence levels';
COMMENT ON FUNCTION search_documents_by_category IS 'Search documents by type, product, and privacy level';
