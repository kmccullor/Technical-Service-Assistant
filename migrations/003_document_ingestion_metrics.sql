-- Document Ingestion Metrics Table
-- Stores per-document processing metrics for monitoring and analysis

CREATE TABLE IF NOT EXISTS document_ingestion_metrics (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    
    -- Processing timestamps
    processing_start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    processing_end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    processing_duration_seconds NUMERIC(10,3) NOT NULL,
    
    -- Input metrics
    total_input_chunks INTEGER NOT NULL DEFAULT 0,
    file_size_bytes BIGINT,
    page_count INTEGER,
    
    -- Chunk type distribution
    text_chunks INTEGER NOT NULL DEFAULT 0,
    table_chunks INTEGER NOT NULL DEFAULT 0,
    image_chunks INTEGER NOT NULL DEFAULT 0,
    ocr_chunks INTEGER NOT NULL DEFAULT 0,
    
    -- Processing results
    inserted_chunks INTEGER NOT NULL DEFAULT 0,
    failed_chunks INTEGER NOT NULL DEFAULT 0,
    skipped_duplicates INTEGER NOT NULL DEFAULT 0,
    failed_embeddings INTEGER NOT NULL DEFAULT 0,
    
    -- Performance metrics
    embedding_time_seconds NUMERIC(10,3),
    avg_embedding_time_ms NUMERIC(10,3),
    
    -- Quality metrics  
    ocr_yield_ratio NUMERIC(5,4), -- ocr_chunks / image_chunks
    success_rate NUMERIC(5,4), -- inserted_chunks / total_input_chunks
    
    -- Metadata
    embedding_model TEXT,
    processor_version TEXT DEFAULT 'option_b',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_document_id ON document_ingestion_metrics(document_id);
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_file_name ON document_ingestion_metrics(file_name);
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_created_at ON document_ingestion_metrics(created_at);
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_processing_start ON document_ingestion_metrics(processing_start_time);

-- Comments for documentation
COMMENT ON TABLE document_ingestion_metrics IS 'Stores detailed metrics for each document processing session';
COMMENT ON COLUMN document_ingestion_metrics.ocr_yield_ratio IS 'Percentage of images that produced OCR text (ocr_chunks / image_chunks)';
COMMENT ON COLUMN document_ingestion_metrics.success_rate IS 'Percentage of input chunks successfully inserted (inserted_chunks / total_input_chunks)';
COMMENT ON COLUMN document_ingestion_metrics.avg_embedding_time_ms IS 'Average time in milliseconds to generate embeddings per chunk';