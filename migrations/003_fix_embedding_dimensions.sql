-- Fix embedding dimensions for nomic-embed-text model (768 dimensions)
-- This migration updates the embeddings table to support variable dimensions

-- Drop the existing embeddings table and recreate with correct dimensions
DROP TABLE IF EXISTS embeddings CASCADE;

CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER REFERENCES chunks(id),
    model_id INTEGER REFERENCES models(id),
    embedding VECTOR(768), -- Updated to match nomic-embed-text output
    UNIQUE(chunk_id, model_id)
);

-- Create index for vector similarity search
CREATE INDEX embeddings_embedding_idx ON embeddings USING ivfflat (embedding vector_cosine_ops);

-- Insert the nomic-embed-text model if it doesn't exist
INSERT INTO models (name, provider, dimension_size) 
VALUES ('nomic-embed-text:v1.5', 'ollama', 768)
ON CONFLICT (name) DO UPDATE SET dimension_size = 768;