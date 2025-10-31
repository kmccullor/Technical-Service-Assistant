-- Migration 003: Add privacy level classification to documents and chunks
-- This enables marking content as public or private based on confidentiality keywords

-- Add privacy_level column to pdf_documents table
ALTER TABLE pdf_documents
ADD COLUMN IF NOT EXISTS privacy_level text DEFAULT 'public' CHECK (privacy_level IN ('public', 'private'));

-- Add privacy_level column to document_chunks table
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS privacy_level text DEFAULT 'public' CHECK (privacy_level IN ('public', 'private'));

-- Create index for efficient privacy filtering
CREATE INDEX IF NOT EXISTS idx_document_chunks_privacy_level ON document_chunks(privacy_level);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_privacy_level ON pdf_documents(privacy_level);

-- Update the match_document_chunks function to support privacy filtering
CREATE OR REPLACE FUNCTION match_document_chunks (
  query_embedding vector(768),
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

-- Create function to get privacy statistics
CREATE OR REPLACE FUNCTION get_privacy_statistics()
RETURNS TABLE (
  privacy_level text,
  document_count bigint,
  chunk_count bigint
)
LANGUAGE sql STABLE
AS $$
  SELECT
    d.privacy_level,
    COUNT(DISTINCT d.id) as document_count,
    COUNT(c.id) as chunk_count
  FROM pdf_documents d
  LEFT JOIN document_chunks c ON d.id = c.document_id
  GROUP BY d.privacy_level
  ORDER BY d.privacy_level;
$$;

-- Add comments for documentation
COMMENT ON COLUMN pdf_documents.privacy_level IS 'Classification of document privacy: public (default) or private (confidential)';
COMMENT ON COLUMN document_chunks.privacy_level IS 'Inherited privacy level from parent document';
COMMENT ON FUNCTION match_document_chunks IS 'Enhanced search function with privacy filtering support';
COMMENT ON FUNCTION get_privacy_statistics IS 'Returns count of documents and chunks by privacy level';
