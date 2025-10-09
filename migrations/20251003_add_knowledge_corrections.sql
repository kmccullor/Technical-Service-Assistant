-- Migration: Add knowledge_corrections table for answer corrections
CREATE TABLE IF NOT EXISTS knowledge_corrections (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    original_answer TEXT NOT NULL,
    corrected_answer TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    user_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_knowledge_corrections_question ON knowledge_corrections USING GIN (to_tsvector('english', question));
