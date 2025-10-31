-- Migration: add privacy_level and optional classification metadata to document_chunks & pdf_documents
-- Date: 2025-09-21
-- Idempotent guards to avoid errors if rerun.

DO $$
BEGIN
    -- Add privacy_level to document_chunks if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='document_chunks' AND column_name='privacy_level'
    ) THEN
        ALTER TABLE document_chunks ADD COLUMN privacy_level text DEFAULT 'public';
        CREATE INDEX IF NOT EXISTS idx_document_chunks_privacy_level ON document_chunks(privacy_level);
    END IF;

    -- Add privacy_level to pdf_documents for future aggregation
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='pdf_documents' AND column_name='privacy_level'
    ) THEN
        ALTER TABLE pdf_documents ADD COLUMN privacy_level text DEFAULT 'public';
        CREATE INDEX IF NOT EXISTS idx_pdf_documents_privacy_level ON pdf_documents(privacy_level);
    END IF;

    -- Add document_type & product_name classification metadata if not present
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='document_chunks' AND column_name='document_type'
    ) THEN
        ALTER TABLE document_chunks ADD COLUMN document_type text;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='document_chunks' AND column_name='product_name'
    ) THEN
        ALTER TABLE document_chunks ADD COLUMN product_name text;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='document_chunks' AND column_name='ai_classification'
    ) THEN
        ALTER TABLE document_chunks ADD COLUMN ai_classification jsonb;
    END IF;
END $$;

-- Backfill NULL privacy_level values to 'public'
UPDATE document_chunks SET privacy_level='public' WHERE privacy_level IS NULL;
UPDATE pdf_documents SET privacy_level='public' WHERE privacy_level IS NULL;

-- Verification query (optional)
-- SELECT privacy_level, count(*) FROM document_chunks GROUP BY 1;
