-- Migration: Extended embedding schema (documents/chunks/models/embeddings)
-- Idempotent creation; safe to run multiple times.

BEGIN;

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    checksum TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS models (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    dim INT,
    provider TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index BIGINT NOT NULL,
    text TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, chunk_index)
);

-- Vector dimension intentionally not enforced strictly here; rely on model meta.
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id BIGINT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    model_id BIGINT NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY(chunk_id, model_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_metadata_gin ON chunks USING GIN((metadata));
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

COMMIT;
