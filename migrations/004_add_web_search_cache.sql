-- Migration 004: Web Search Cache

CREATE TABLE IF NOT EXISTS web_search_cache (
    id SERIAL PRIMARY KEY,
    query_hash TEXT NOT NULL UNIQUE,
    normalized_query TEXT NOT NULL,
    results_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_web_search_cache_expires_at ON web_search_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_web_search_cache_normalized_query ON web_search_cache(normalized_query);
