-- Migration: Add new chunk columns (section_title, language, tokens) and new conversation tables
-- Date: 2025-10-07
-- This migration captures manual production fixes applied during chat pipeline restoration.

BEGIN;

-- Idempotent guards for new columns on document_chunks
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS section_title text;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS language text DEFAULT 'en';
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS tokens integer;

-- New conversation tables for Next.js chat history
CREATE TABLE IF NOT EXISTS conversations (
  id bigserial PRIMARY KEY,
  title text NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
  id bigserial PRIMARY KEY,
  conversation_id bigint NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role text NOT NULL,
  content text NOT NULL,
  citations jsonb,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);

COMMIT;
