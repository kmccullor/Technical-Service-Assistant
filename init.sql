-- Canonical schema initialization (2025-09-21)
-- Enables pgvector and defines core tables: documents, document_chunks, search_events, web_search_cache, chat sessions/messages.
-- Legacy objects removed: pdf_documents, match_document_chunks function.

CREATE EXTENSION IF NOT EXISTS vector;

-- Documents metadata
CREATE TABLE IF NOT EXISTS documents (
  id bigserial PRIMARY KEY,
  file_name text NOT NULL,
  file_hash text NOT NULL,
  file_size bigint,
  mime_type text,
  title text,
  document_type text,
  product_name text,
  product_version text,
  privacy_level text DEFAULT 'public',
  processing_status text DEFAULT 'pending',
  processed_at timestamptz,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS documents_file_hash_idx ON documents(file_hash);
CREATE INDEX IF NOT EXISTS documents_privacy_level_idx ON documents(privacy_level);

-- Document chunks with hybrid search fields
CREATE TABLE IF NOT EXISTS document_chunks (
  id bigserial PRIMARY KEY,
  document_id bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  page_number integer,
  -- Added in Oct 2025 to preserve structural context (header/section extraction)
  section_title text,
  chunk_type text DEFAULT 'text',
  content text NOT NULL,
  content_hash text NOT NULL,
  content_length integer,
  embedding vector(768),
  -- Added in Oct 2025 for language-aware retrieval / filtering
  language text DEFAULT 'en',
  -- Approximate token count (for budgeting / context window management)
  tokens integer,
  -- Added in Oct 2025 for product-level filtering in retrieval
  product_name text,
  metadata jsonb DEFAULT '{}'::jsonb,
  content_tsvector tsvector,
  created_at timestamptz DEFAULT now(),
  UNIQUE(document_id, chunk_index),
  UNIQUE(document_id, content_hash)
);
CREATE INDEX IF NOT EXISTS document_chunks_document_id_idx ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS document_chunks_page_number_idx ON document_chunks(page_number);
CREATE INDEX IF NOT EXISTS document_chunks_chunk_type_idx ON document_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS document_chunks_content_hash_idx ON document_chunks(content_hash);
-- HNSW vector index (cosine) for semantic similarity
CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx ON document_chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
-- Full text search index
CREATE INDEX IF NOT EXISTS document_chunks_content_tsvector_gin_idx ON document_chunks USING gin(content_tsvector);

-- Embedding models tracking table
CREATE TABLE IF NOT EXISTS models (
  id bigserial PRIMARY KEY,
  name text NOT NULL UNIQUE,
  provider text,
  dimension_size integer,
  created_at timestamptz DEFAULT now()
);

-- Insert default embedding model
INSERT INTO models (name, provider, dimension_size)
VALUES ('nomic-embed-text:v1.5', 'ollama', 768)
ON CONFLICT (name) DO UPDATE SET dimension_size = 768;

-- Privacy level for chunks (inherits from documents, can be overridden)
CREATE INDEX IF NOT EXISTS document_chunks_metadata_gin_idx ON document_chunks USING gin(metadata);

-- Search analytics
CREATE TABLE IF NOT EXISTS search_events (
  id serial PRIMARY KEY,
  created_at timestamptz DEFAULT now() NOT NULL,
  query text NOT NULL,
  search_method text NOT NULL,
  confidence_score double precision,
  rag_confidence double precision,
  classification_type text,
  strategy text,
  response_time_ms integer,
  context_chunk_count integer,
  web_result_count integer,
  fused_count integer,
  model_used text,
  error text
);
CREATE INDEX IF NOT EXISTS idx_search_events_created_at ON search_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_events_method ON search_events(search_method);
CREATE INDEX IF NOT EXISTS idx_search_events_classification ON search_events(classification_type);

-- Web search cache
CREATE TABLE IF NOT EXISTS web_search_cache (
  id serial PRIMARY KEY,
  query_hash text NOT NULL UNIQUE,
  normalized_query text NOT NULL,
  results_json jsonb NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  expires_at timestamptz NOT NULL,
  hit_count integer NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_web_search_cache_normalized_query ON web_search_cache(normalized_query);
CREATE INDEX IF NOT EXISTS idx_web_search_cache_expires_at ON web_search_cache(expires_at);

-- Chat memory (session + messages)
-- Legacy chat tables (deprecated). Kept for backward compatibility with older services.
CREATE TABLE IF NOT EXISTS chat_sessions (
  id bigserial PRIMARY KEY,
  user_id text,
  created_at timestamptz DEFAULT now(),
  last_active_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  sender text NOT NULL,
  content text NOT NULL,
  message_type text DEFAULT 'text',
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);

-- New unified conversation tables used by Next.js app (preferred going forward)
CREATE TABLE IF NOT EXISTS conversations (
  id bigserial PRIMARY KEY,
  title text NOT NULL,
  user_id bigint,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now(),
  last_reviewed_at timestamptz
);

CREATE INDEX IF NOT EXISTS conversations_user_id_idx ON conversations(user_id);

CREATE TABLE IF NOT EXISTS messages (
  id bigserial PRIMARY KEY,
  conversation_id bigint NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role text NOT NULL,
  content text NOT NULL,
  citations jsonb,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);

-- Triggers (optional) to maintain updated_at / content length & tsvector
CREATE OR REPLACE FUNCTION update_documents_timestamp() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION update_documents_timestamp();

CREATE OR REPLACE FUNCTION calculate_content_length() RETURNS trigger AS $$
BEGIN
  NEW.content_length = char_length(NEW.content);
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS calculate_chunk_content_length ON document_chunks;
CREATE TRIGGER calculate_chunk_content_length BEFORE INSERT OR UPDATE OF content ON document_chunks
  FOR EACH ROW EXECUTE FUNCTION calculate_content_length();

CREATE OR REPLACE FUNCTION update_content_tsvector() RETURNS trigger AS $$
BEGIN
  NEW.content_tsvector := to_tsvector('english', coalesce(NEW.content,''));
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_chunk_tsvector ON document_chunks;
CREATE TRIGGER update_chunk_tsvector BEFORE INSERT OR UPDATE OF content ON document_chunks
  FOR EACH ROW EXECUTE FUNCTION update_content_tsvector();

-- Document ingestion metrics (added Oct 7 2025)
-- Stores per-document processing performance and quality metrics for monitoring & optimization
CREATE TABLE IF NOT EXISTS document_ingestion_metrics (
  id bigserial PRIMARY KEY,
  document_id bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  file_name text NOT NULL,
  processing_start_time timestamptz NOT NULL,
  processing_end_time timestamptz NOT NULL,
  processing_duration_seconds double precision NOT NULL,
  total_input_chunks integer NOT NULL DEFAULT 0,
  file_size_bytes bigint,
  page_count integer,
  text_chunks integer NOT NULL DEFAULT 0,
  table_chunks integer NOT NULL DEFAULT 0,
  image_chunks integer NOT NULL DEFAULT 0,
  ocr_chunks integer NOT NULL DEFAULT 0,
  inserted_chunks integer NOT NULL DEFAULT 0,
  failed_chunks integer NOT NULL DEFAULT 0,
  skipped_duplicates integer NOT NULL DEFAULT 0,
  failed_embeddings integer NOT NULL DEFAULT 0,
  embedding_time_seconds double precision,
  avg_embedding_time_ms double precision,
  ocr_yield_ratio double precision,
  success_rate double precision,
  embedding_model text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_document_id ON document_ingestion_metrics(document_id);
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_file_name ON document_ingestion_metrics(file_name);
CREATE INDEX IF NOT EXISTS idx_document_ingestion_metrics_start_time ON document_ingestion_metrics(processing_start_time);

-- User management tables for admin functionality
CREATE TABLE IF NOT EXISTS roles (
    id bigserial PRIMARY KEY,
    name text NOT NULL UNIQUE,
    description text,
    is_system boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS permissions (
    id bigserial PRIMARY KEY,
    name text NOT NULL UNIQUE,
    description text,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id bigserial PRIMARY KEY,
    role_id bigint NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id bigint NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    UNIQUE(role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS users (
    id bigserial PRIMARY KEY,
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    first_name text,
    last_name text,
    role_id bigint REFERENCES roles(id),
    status text DEFAULT 'active',
    verified boolean DEFAULT false,
    last_login timestamptz,
    password_change_required boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_roles (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id bigint NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    UNIQUE(user_id, role_id)
);

-- Insert default roles
INSERT INTO roles (name, description, is_system) VALUES
    ('admin', 'Administrator with full access', true),
    ('employee', 'Standard employee access', true)
ON CONFLICT (name) DO NOTHING;

-- Insert default permissions
INSERT INTO permissions (name, description) VALUES
    ('read', 'Read access'),
    ('write', 'Write access'),
    ('delete', 'Delete access'),
    ('admin', 'Administrative access')
ON CONFLICT (name) DO NOTHING;

-- Assign permissions to roles
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE (r.name = 'admin' AND p.name IN ('read', 'write', 'delete', 'admin'))
   OR (r.name = 'employee' AND p.name IN ('read', 'write'))
ON CONFLICT DO NOTHING;

-- Insert default admin user (password: admin123)
INSERT INTO users (email, password_hash, first_name, last_name, role_id, verified, status)
SELECT 'admin@employee.com',
       '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6fM9q7XH2e', -- bcrypt hash for 'admin123'
       'Admin',
       'User',
       r.id,
       true,
       'active'
FROM roles r
WHERE r.name = 'admin'
ON CONFLICT (email) DO NOTHING;

-- Insert default employee user (password: employee123)
INSERT INTO users (email, password_hash, first_name, last_name, role_id, verified, status)
SELECT 'user@employee.com',
       '$2b$12$dummy.hash.for.employee', -- placeholder hash
       'Regular',
       'User',
       r.id,
       true,
       'active'
FROM roles r
WHERE r.name = 'employee'
ON CONFLICT (email) DO NOTHING;

-- End canonical schema
