-- Cleanup legacy objects no longer used after canonical schema adoption
-- Safe to run multiple times (IF EXISTS guards)

DO $$
BEGIN
    -- Drop legacy pdf_documents table (superseded by documents)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='pdf_documents') THEN
        DROP TABLE pdf_documents CASCADE;
    END IF;

    -- Drop match_document_chunks SQL function (replaced by direct vector index queries)
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='match_document_chunks') THEN
        DROP FUNCTION match_document_chunks(vector, float, int);
    END IF;

    -- Optionally drop deprecated summary/search objects if not referenced
    IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_name='document_summary') THEN
        DROP VIEW document_summary;
    ELSIF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='document_summary') THEN
        DROP TABLE document_summary;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_name='searchable_chunks') THEN
        DROP VIEW searchable_chunks;
    ELSIF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='searchable_chunks') THEN
        DROP TABLE searchable_chunks;
    END IF;
END $$;

-- Verification (commented)
-- SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY 1;
