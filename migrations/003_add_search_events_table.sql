-- Migration 003: Add search_events analytics table
-- Tracks usage metrics for hybrid, intelligent, fusion, and RAG searches

CREATE TABLE IF NOT EXISTS search_events (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    query TEXT NOT NULL,
    search_method TEXT NOT NULL,
    confidence_score DOUBLE PRECISION,
    rag_confidence DOUBLE PRECISION,
    classification_type TEXT,
    strategy TEXT,
    response_time_ms INTEGER,
    context_chunk_count INTEGER,
    web_result_count INTEGER,
    fused_count INTEGER,
    model_used TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_search_events_created_at ON search_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_events_method ON search_events(search_method);
CREATE INDEX IF NOT EXISTS idx_search_events_classification ON search_events(classification_type);
