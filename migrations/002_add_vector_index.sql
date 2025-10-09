-- Migration 002: Add alternative HNSW index (optional) for embeddings
-- Provides faster recall trade-offs vs IVFFlat for some workloads.
-- Safe to run multiple times (IF NOT EXISTS guards not yet available for index method, so conditional pattern used).

DO $$
BEGIN
    -- Only create if it does not already exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = 'idx_embeddings_hnsw' AND n.nspname = 'public'
    ) THEN
        CREATE INDEX idx_embeddings_hnsw ON embeddings USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);
    END IF;
END $$;

-- Recommendation: Tune runtime parameter `SET hnsw.ef_search = <value>;` per session for latency/accuracy balance.
