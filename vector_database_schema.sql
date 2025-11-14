-- Technical Service Assistant Vector Database Schema
-- Following pgvector best practices and comprehensive metadata structure
-- Based on ChatGPT analysis recommendations

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ==========================================
-- DOCUMENTS TABLE - Core document metadata
-- ==========================================
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,

    -- Basic identification
    file_name TEXT NOT NULL,
    original_path TEXT,
    file_hash TEXT UNIQUE NOT NULL, -- Prevent duplicates
    file_size BIGINT,
    mime_type TEXT,

    -- Document metadata
    title TEXT,
    version TEXT,
    doc_number TEXT, -- e.g., ARN-10003-01
    ga_date DATE,
    publisher TEXT,
    copyright_year INTEGER,

    -- Product information
    product_family TEXT[], -- e.g., ['RNI', 'FlexNet']
    product_name TEXT,
    product_version TEXT,

    -- Classification
    document_type TEXT, -- user_guide, release_notes, technical_specification, etc.
    document_category TEXT,
    service_lines TEXT[], -- ['Electric', 'Gas', 'Water', 'Common']
    audiences TEXT[], -- ['RNI administrators', 'Utility operations', etc.]

    -- Privacy and security
    privacy_level TEXT DEFAULT 'public',
    security_classification TEXT,

    -- AI classification metadata
    classification_confidence FLOAT,
    classification_method TEXT, -- 'ai', 'rule_based', 'manual'

    -- Processing status
    processing_status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    processed_at TIMESTAMP WITH TIME ZONE,

    -- Rich metadata (JSONB for flexible schema)
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==========================================
-- DOCUMENT_CHUNKS TABLE - Text chunks with embeddings
-- ==========================================
CREATE TABLE document_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Chunk identification
    chunk_index INTEGER NOT NULL, -- Order within document
    page_number INTEGER,
    section_title TEXT,
    chunk_type TEXT DEFAULT 'text', -- text, table, image, code, header, footer

    -- Content
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL, -- For deduplication
    content_length INTEGER,

    -- Vector embedding
    embedding vector(3072), -- llama3.2:3b dimensions

    -- Chunk-level metadata
    language TEXT DEFAULT 'en',
    tokens INTEGER,
    metadata JSONB DEFAULT '{}',

    -- Search optimization
    content_tsvector tsvector, -- Full-text search

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique chunks per document
    UNIQUE(document_id, chunk_index),
    UNIQUE(document_id, content_hash)
);

-- ==========================================
-- ENTITIES TABLE - Extracted entities
-- ==========================================
CREATE TABLE entities (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL, -- device, protocol, platform, tool, person, organization
    category TEXT, -- e.g., 'electric_meter', 'communication_protocol'
    description TEXT,
    aliases TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(name, entity_type)
);

-- ==========================================
-- DOCUMENT_ENTITIES - Many-to-many relationship
-- ==========================================
CREATE TABLE document_entities (
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relevance_score FLOAT, -- How relevant this entity is to the document
    first_mention_chunk_id BIGINT REFERENCES document_chunks(id),
    mention_count INTEGER DEFAULT 1,

    PRIMARY KEY(document_id, entity_id)
);

-- ==========================================
-- KEYWORDS TABLE - Searchable keywords/tags
-- ==========================================
CREATE TABLE keywords (
    id BIGSERIAL PRIMARY KEY,
    keyword TEXT NOT NULL UNIQUE,
    category TEXT, -- technical, product, feature, etc.
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==========================================
-- DOCUMENT_KEYWORDS - Many-to-many relationship
-- ==========================================
CREATE TABLE document_keywords (
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 1.0,

    PRIMARY KEY(document_id, keyword_id)
);

-- ==========================================
-- SEARCH_SESSIONS - Track search performance
-- ==========================================
CREATE TABLE search_sessions (
    id BIGSERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    query_embedding vector(768),
    search_type TEXT, -- vector, hybrid, keyword
    result_count INTEGER,
    max_distance FLOAT,
    execution_time_ms INTEGER,
    user_feedback TEXT, -- good, bad, irrelevant
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==========================================
-- VECTOR INDEXES - pgvector optimized indexes
-- ==========================================

-- Primary vector similarity index (HNSW for better performance)
CREATE INDEX document_chunks_embedding_hnsw_idx
ON document_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- IVF index for large datasets (alternative)
-- CREATE INDEX document_chunks_embedding_ivf_idx
-- ON document_chunks USING ivfflat (embedding vector_cosine_ops)
-- WITH (lists = 100);

-- ==========================================
-- ADDITIONAL INDEXES - Query optimization
-- ==========================================

-- Document lookups
CREATE INDEX documents_file_hash_idx ON documents(file_hash);
CREATE INDEX documents_product_family_idx ON documents USING GIN(product_family);
CREATE INDEX documents_service_lines_idx ON documents USING GIN(service_lines);
CREATE INDEX documents_audiences_idx ON documents USING GIN(audiences);
CREATE INDEX documents_document_type_idx ON documents(document_type);
CREATE INDEX documents_privacy_level_idx ON documents(privacy_level);
CREATE INDEX documents_processed_at_idx ON documents(processed_at);

-- Chunk lookups
CREATE INDEX document_chunks_document_id_idx ON document_chunks(document_id);
CREATE INDEX document_chunks_page_number_idx ON document_chunks(page_number);
CREATE INDEX document_chunks_chunk_type_idx ON document_chunks(chunk_type);
CREATE INDEX document_chunks_content_hash_idx ON document_chunks(content_hash);

-- Full-text search index
CREATE INDEX document_chunks_content_tsvector_idx ON document_chunks USING GIN(content_tsvector);

-- Entity and keyword indexes
CREATE INDEX entities_entity_type_idx ON entities(entity_type);
CREATE INDEX entities_name_trgm_idx ON entities USING GIN(name gin_trgm_ops);
CREATE INDEX keywords_keyword_trgm_idx ON keywords USING GIN(keyword gin_trgm_ops);

-- Metadata indexes (JSONB GIN)
CREATE INDEX documents_metadata_gin_idx ON documents USING GIN(metadata);
CREATE INDEX document_chunks_metadata_gin_idx ON document_chunks USING GIN(metadata);

-- ==========================================
-- TRIGGERS - Automatic maintenance
-- ==========================================

-- Update tsvector on content change
CREATE OR REPLACE FUNCTION update_content_tsvector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_tsvector := to_tsvector('english', NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_chunk_tsvector
    BEFORE INSERT OR UPDATE OF content ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION update_content_tsvector();

-- Update document timestamps
CREATE OR REPLACE FUNCTION update_documents_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_documents_timestamp();

-- ==========================================
-- UTILITY FUNCTIONS - Helper functions
-- ==========================================

-- Function to calculate content length
CREATE OR REPLACE FUNCTION calculate_content_length()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_length := LENGTH(NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calculate_chunk_content_length
    BEFORE INSERT OR UPDATE OF content ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION calculate_content_length();

-- ==========================================
-- SAMPLE DATA POPULATION
-- ==========================================

-- Insert common entity types
INSERT INTO entities (name, entity_type, category, description) VALUES
('RNI', 'product', 'software_platform', 'Regional Network Interface platform'),
('FlexNet', 'product', 'communication_system', 'FlexNet communication system'),
('MultiSpeak', 'protocol', 'communication_protocol', 'Utility communication protocol'),
('CMEP', 'protocol', 'communication_protocol', 'Critical meters enhancement protocol'),
('Aclara I-210+c', 'device', 'electric_meter', 'Aclara electric meter model'),
('Stratus IQ+', 'device', 'electric_meter', 'Advanced electric meter'),
('PostgreSQL', 'platform', 'database', 'Relational database system'),
('Docker', 'platform', 'containerization', 'Container platform');

-- Insert common keywords
INSERT INTO keywords (keyword, category, weight) VALUES
('API', 'technical', 1.5),
('authentication', 'security', 1.8),
('configuration', 'technical', 1.2),
('installation', 'process', 1.4),
('release notes', 'documentation', 1.0),
('user guide', 'documentation', 1.0),
('technical specification', 'documentation', 1.3),
('troubleshooting', 'support', 1.6);

-- ==========================================
-- VIEWS - Convenient access patterns
-- ==========================================

-- Document summary view
CREATE VIEW document_summary AS
SELECT
    d.id,
    d.file_name,
    d.title,
    d.document_type,
    d.product_name,
    d.product_version,
    d.privacy_level,
    d.classification_confidence,
    COUNT(dc.id) as chunk_count,
    COUNT(CASE WHEN dc.embedding IS NOT NULL THEN 1 END) as embedded_chunks,
    d.processed_at,
    d.processing_status
FROM documents d
LEFT JOIN document_chunks dc ON d.id = dc.document_id
GROUP BY d.id;

-- Search-ready chunks view
CREATE VIEW searchable_chunks AS
SELECT
    dc.id,
    dc.document_id,
    d.file_name,
    d.title,
    d.document_type,
    d.product_name,
    dc.chunk_index,
    dc.page_number,
    dc.section_title,
    dc.content,
    dc.embedding,
    dc.content_tsvector,
    d.privacy_level,
    d.classification_confidence
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
WHERE dc.embedding IS NOT NULL
AND d.processing_status = 'completed';

-- ==========================================
-- COMMENTS - Documentation
-- ==========================================

COMMENT ON TABLE documents IS 'Core documents table with comprehensive metadata following pgvector best practices';
COMMENT ON TABLE document_chunks IS 'Text chunks with vector embeddings for semantic search';
COMMENT ON TABLE entities IS 'Extracted entities (devices, protocols, platforms, etc.)';
COMMENT ON TABLE document_entities IS 'Many-to-many relationship between documents and entities';
COMMENT ON TABLE keywords IS 'Searchable keywords and tags for classification';
COMMENT ON TABLE search_sessions IS 'Search performance tracking and analytics';

COMMENT ON COLUMN documents.file_hash IS 'SHA-256 hash to prevent duplicate uploads';
COMMENT ON COLUMN documents.metadata IS 'Flexible JSONB field for additional document attributes';
COMMENT ON COLUMN document_chunks.embedding IS '768-dimensional vector embedding for semantic search';
COMMENT ON COLUMN document_chunks.content_tsvector IS 'Full-text search vector for keyword matching';
