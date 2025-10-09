-- Migration: Add document_ingestion_metrics table
-- Date: 2025-10-07
-- Purpose: Store per-document ingestion performance and quality metrics

CREATE TABLE IF NOT EXISTS document_ingestion_metrics (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    processing_start_time TIMESTAMPTZ NOT NULL,
    processing_end_time TIMESTAMPTZ NOT NULL,
    processing_duration_seconds DOUBLE PRECISION NOT NULL,
    total_input_chunks INTEGER NOT NULL DEFAULT 0,
    file_size_bytes BIGINT,
    page_count INTEGER,
    text_chunks INTEGER NOT NULL DEFAULT 0,
    table_chunks INTEGER NOT NULL DEFAULT 0,
    image_chunks INTEGER NOT NULL DEFAULT 0,
    ocr_chunks INTEGER NOT NULL DEFAULT 0,
    inserted_chunks INTEGER NOT NULL DEFAULT 0,
    failed_chunks INTEGER NOT NULL DEFAULT 0,
    skipped_duplicates INTEGER NOT NULL DEFAULT 0,
    failed_embeddings INTEGER NOT NULL DEFAULT 0,
    embedding_time_seconds DOUBLE PRECISION,
    avg_embedding_time_ms DOUBLE PRECISION,
    ocr_yield_ratio DOUBLE PRECISION,
    success_rate DOUBLE PRECISION,
    embedding_model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_document_id ON document_ingestion_metrics(document_id);
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_file_name ON document_ingestion_metrics(file_name);
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_start_time ON document_ingestion_metrics(processing_start_time);
