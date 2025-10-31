-- Migration: Add tables for managing acronyms and synonyms during document ingestion
-- This enables dynamic terminology management and improved chat prompts

CREATE TABLE IF NOT EXISTS acronyms (
    id SERIAL PRIMARY KEY,
    acronym TEXT NOT NULL UNIQUE,
    definition TEXT NOT NULL,
    confidence_score FLOAT DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    source_documents TEXT[], -- Array of document names where this acronym was found
    first_seen_at TIMESTAMPTZ DEFAULT now(),
    last_updated_at TIMESTAMPTZ DEFAULT now(),
    usage_count INTEGER DEFAULT 1,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS synonyms (
    id SERIAL PRIMARY KEY,
    term TEXT NOT NULL,
    synonym TEXT NOT NULL,
    term_type TEXT DEFAULT 'general', -- 'product', 'technical', 'general', etc.
    confidence_score FLOAT DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    source_documents TEXT[],
    context_usage TEXT, -- How this synonym is typically used
    first_seen_at TIMESTAMPTZ DEFAULT now(),
    last_updated_at TIMESTAMPTZ DEFAULT now(),
    usage_count INTEGER DEFAULT 1,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(term, synonym, term_type)
);

CREATE TABLE IF NOT EXISTS term_relationships (
    id SERIAL PRIMARY KEY,
    primary_term TEXT NOT NULL,
    related_term TEXT NOT NULL,
    relationship_type TEXT NOT NULL, -- 'synonym', 'acronym', 'abbreviation', 'alias'
    confidence_score FLOAT DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    source_documents TEXT[],
    context_examples TEXT[], -- Array of example usages
    first_seen_at TIMESTAMPTZ DEFAULT now(),
    last_updated_at TIMESTAMPTZ DEFAULT now(),
    usage_count INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(primary_term, related_term, relationship_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_acronyms_acronym ON acronyms(acronym);
CREATE INDEX IF NOT EXISTS idx_acronyms_confidence ON acronyms(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_synonyms_term ON synonyms(term);
CREATE INDEX IF NOT EXISTS idx_synonyms_synonym ON synonyms(synonym);
CREATE INDEX IF NOT EXISTS idx_synonyms_type ON synonyms(term_type);
CREATE INDEX IF NOT EXISTS idx_term_relationships_primary ON term_relationships(primary_term);
CREATE INDEX IF NOT EXISTS idx_term_relationships_related ON term_relationships(related_term);
CREATE INDEX IF NOT EXISTS idx_term_relationships_type ON term_relationships(relationship_type);

-- Full text search indexes
CREATE INDEX IF NOT EXISTS idx_acronyms_definition_fts ON acronyms USING gin(to_tsvector('english', definition));
CREATE INDEX IF NOT EXISTS idx_synonyms_context_fts ON synonyms USING gin(to_tsvector('english', context_usage));

-- Functions for updating timestamps
CREATE OR REPLACE FUNCTION update_acronym_timestamp() RETURNS trigger AS $$
BEGIN
    NEW.last_updated_at = now();
    RETURN NEW;
END;$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_synonym_timestamp() RETURNS trigger AS $$
BEGIN
    NEW.last_updated_at = now();
    RETURN NEW;
END;$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_term_relationship_timestamp() RETURNS trigger AS $$
BEGIN
    NEW.last_updated_at = now();
    RETURN NEW;
END;$$ LANGUAGE plpgsql;

-- Triggers for auto-updating timestamps
DROP TRIGGER IF EXISTS update_acronym_timestamp_trigger ON acronyms;
CREATE TRIGGER update_acronym_timestamp_trigger
    BEFORE UPDATE ON acronyms
    FOR EACH ROW EXECUTE FUNCTION update_acronym_timestamp();

DROP TRIGGER IF EXISTS update_synonym_timestamp_trigger ON synonyms;
CREATE TRIGGER update_synonym_timestamp_trigger
    BEFORE UPDATE ON synonyms
    FOR EACH ROW EXECUTE FUNCTION update_synonym_timestamp();

DROP TRIGGER IF EXISTS update_term_relationship_timestamp_trigger ON term_relationships;
CREATE TRIGGER update_term_relationship_timestamp_trigger
    BEFORE UPDATE ON term_relationships
    FOR EACH ROW EXECUTE FUNCTION update_term_relationship_timestamp();

-- Function to get relevant acronyms for a query
CREATE OR REPLACE FUNCTION get_relevant_acronyms(query_text TEXT, max_results INTEGER DEFAULT 10)
RETURNS TABLE(acronym TEXT, definition TEXT, confidence_score FLOAT) AS $$
BEGIN
    RETURN QUERY
    SELECT a.acronym, a.definition, a.confidence_score
    FROM acronyms a
    WHERE to_tsvector('english', a.definition) @@ plainto_tsquery('english', query_text)
       OR a.acronym ILIKE '%' || query_text || '%'
    ORDER BY a.confidence_score DESC, a.usage_count DESC
    LIMIT max_results;
END;$$ LANGUAGE plpgsql;

-- Function to get relevant synonyms for a term
CREATE OR REPLACE FUNCTION get_relevant_synonyms(search_term TEXT, term_type_filter TEXT DEFAULT NULL, max_results INTEGER DEFAULT 10)
RETURNS TABLE(term TEXT, synonym TEXT, term_type TEXT, confidence_score FLOAT) AS $$
BEGIN
    RETURN QUERY
    SELECT s.term, s.synonym, s.term_type, s.confidence_score
    FROM synonyms s
    WHERE (s.term ILIKE '%' || search_term || '%' OR s.synonym ILIKE '%' || search_term || '%')
      AND (term_type_filter IS NULL OR s.term_type = term_type_filter)
    ORDER BY s.confidence_score DESC, s.usage_count DESC
    LIMIT max_results;
END;$$ LANGUAGE plpgsql;

-- Function to get term relationships for context
CREATE OR REPLACE FUNCTION get_term_context(primary_term TEXT, relationship_types TEXT[] DEFAULT ARRAY['synonym', 'acronym', 'abbreviation'])
RETURNS TABLE(related_term TEXT, relationship_type TEXT, confidence_score FLOAT, context_examples TEXT[]) AS $$
BEGIN
    RETURN QUERY
    SELECT tr.related_term, tr.relationship_type, tr.confidence_score, tr.context_examples
    FROM term_relationships tr
    WHERE tr.primary_term ILIKE '%' || primary_term || '%'
      AND tr.relationship_type = ANY(relationship_types)
    ORDER BY tr.confidence_score DESC, tr.usage_count DESC;
END;$$ LANGUAGE plpgsql;
