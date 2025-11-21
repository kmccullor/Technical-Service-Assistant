# PostgreSQL Instructions for Technical Service Assistant

## Overview
This document provides comprehensive PostgreSQL guidelines for the Technical Service Assistant project, covering database setup, vector operations, schema management, performance optimization, and operational procedures specific to the pgvector-enabled database architecture.

## Database Architecture

### Core Components
- **Primary Database**: PostgreSQL 15+ with pgvector extension
- **Vector Storage**: Document embeddings with 768-dimensional vectors (nomic-embed-text default)
- **Schema Evolution**: Migration-based schema management in `migrations/` directory
- **Connection Pattern**: Direct psycopg2 connections with centralized configuration

### Container Configuration
```yaml
# docker-compose.yml
pgvector:
  image: ankane/pgvector:latest
  container_name: pgvector
  environment:
    POSTGRES_PASSWORD: postgres
    POSTGRES_DB: vector_db
  ports:
    - "5432:5432"
  volumes:
    - pgvector_data:/var/lib/postgresql/data
    - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
  command: ["postgres", "-c", "shared_preload_libraries=vector.so"]
```

## Schema Management

### Primary Tables Structure

#### Modern Schema (migrations/001_add_extended_embedding_schema.sql)
```sql
-- Documents table - PDF metadata
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,          -- Original filename
    checksum TEXT,                      -- File integrity verification
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Models table - Embedding model tracking
CREATE TABLE IF NOT EXISTS models (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,          -- e.g., 'nomic-embed-text:v1.5'
    dim INT,                           -- Vector dimensions (768, 1536, etc.)
    provider TEXT,                     -- 'ollama', 'openai', etc.
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Chunks table - Text segments with metadata
CREATE TABLE IF NOT EXISTS chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index BIGINT NOT NULL,       -- Sequential chunk number
    text TEXT NOT NULL,                -- Actual text content
    metadata JSONB,                    -- Flexible metadata storage
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, chunk_index)
);

-- Embeddings table - Vector storage per model
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id BIGINT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    model_id BIGINT NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    embedding vector(3072),            -- Adjust dimensions per model
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY(chunk_id, model_id)
);
```

#### Legacy Schema (init.sql) - For Compatibility
```sql
-- Simplified schema for backward compatibility
CREATE TABLE IF NOT EXISTS document_chunks (
    id bigserial PRIMARY KEY,
    document_id bigint NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
    page_number integer NOT NULL,
    chunk_type text NOT NULL,          -- 'text', 'table', 'image'
    content text,                      -- Content or file path
    embedding vector(3072),            -- Single embedding column
    created_at timestamp with time zone DEFAULT now()
);
```

### Essential Indexes

#### Vector Similarity Indexes
```sql
-- IVFFlat index (default) - Good for most workloads
CREATE INDEX IF NOT EXISTS idx_embeddings_vector
ON embeddings USING ivfflat (embedding vector_l2_ops)
WITH (lists = 100);

-- HNSW index (optional) - Better recall for some queries
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw
ON embeddings USING hnsw (embedding vector_l2_ops)
WITH (m = 16, ef_construction = 64);

-- Legacy compatibility index
CREATE INDEX ON document_chunks
USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
```

#### Performance Indexes
```sql
-- Chunk retrieval optimization
CREATE INDEX IF NOT EXISTS idx_chunks_document
ON chunks(document_id, chunk_index);

-- Metadata search optimization
CREATE INDEX IF NOT EXISTS idx_chunks_metadata_gin
ON chunks USING GIN((metadata));

-- Chat session indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
ON chat_messages(session_id);
```

## Vector Operations Patterns

### Vector Similarity Search
```sql
-- Standard similarity search with distance threshold
SELECT
    c.text,
    c.metadata,
    d.name as document_name,
    1 - (e.embedding <=> %s::vector) AS similarity_score
from document_chunks c
JOIN embeddings e ON c.id = e.chunk_id
JOIN documents d ON c.document_id = d.id
JOIN models m ON e.model_id = m.id
WHERE m.name = %s                                    -- Specific model
  AND 1 - (e.embedding <=> %s::vector) > 0.3        -- Similarity threshold
ORDER BY e.embedding <=> %s::vector                 -- Distance sorting
LIMIT %s;
```

### Hybrid Search (Vector + Keyword)
```sql
-- Combined vector similarity and text search
WITH vector_results AS (
    SELECT c.id, c.text,
           1 - (e.embedding <=> %s::vector) as similarity_score
    from document_chunks c
    JOIN embeddings e ON c.id = e.chunk_id
    WHERE 1 - (e.embedding <=> %s::vector) > 0.3
    ORDER BY e.embedding <=> %s::vector
    LIMIT 50
),
text_results AS (
    SELECT c.id, c.text,
           ts_rank(to_tsvector('english', c.text), plainto_tsquery('english', %s)) as text_score
    from document_chunks c
    WHERE to_tsvector('english', c.text) @@ plainto_tsquery('english', %s)
    ORDER BY text_score DESC
    LIMIT 20
)
SELECT DISTINCT
    COALESCE(v.text, t.text) as text,
    COALESCE(v.similarity_score, 0) * 0.7 + COALESCE(t.text_score, 0) * 0.3 as combined_score
FROM vector_results v
FULL OUTER JOIN text_results t ON v.id = t.id
ORDER BY combined_score DESC
LIMIT %s;
```

### Metadata-Enhanced Search
```sql
-- Search with JSON metadata filtering
SELECT c.text, c.metadata, d.name
from document_chunks c
JOIN embeddings e ON c.id = e.chunk_id
JOIN documents d ON c.document_id = d.id
WHERE e.embedding IS NOT NULL
  AND c.metadata->>'document_type' = 'technical'     -- JSON path filtering
  AND c.metadata->>'section' ILIKE '%installation%'   -- Pattern matching in metadata
ORDER BY e.embedding <=> %s::vector
LIMIT %s;
```

## Connection Management

### Database Connection Pattern
```python
import psycopg2
from psycopg2.extras import RealDictCursor
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

def get_db_connection():
    """Create database connection using centralized settings."""
    try:
        connection = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            cursor_factory=RealDictCursor  # Returns dict-like rows
        )
        return connection
    except psycopg2.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise
```

### Transaction Management
```python
def execute_with_transaction(queries_and_params):
    """Execute multiple queries in a single transaction."""
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            for query, params in queries_and_params:
                cursor.execute(query, params)
            connection.commit()
            logger.info(f"Transaction completed successfully: {len(queries_and_params)} queries")
    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        logger.error(f"Transaction failed: {e}")
        raise
    finally:
        if connection:
            connection.close()
```

### Connection Pool (High-Throughput Applications)
```python
from psycopg2 import pool

class DatabasePool:
    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize_pool(self):
        """Initialize connection pool."""
        if self._pool is None:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password
            )
            logger.info("Database connection pool initialized")

    def get_connection(self):
        """Get connection from pool."""
        if self._pool is None:
            self.initialize_pool()
        return self._pool.getconn()

    def return_connection(self, connection):
        """Return connection to pool."""
        if self._pool:
            self._pool.putconn(connection)

# Usage pattern
db_pool = DatabasePool()

def execute_query_pooled(query: str, params: tuple = None):
    """Execute query using connection pool."""
    connection = None
    try:
        connection = db_pool.get_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return cursor.fetchall()
            connection.commit()
            return []
    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        logger.error(f"Pooled query failed: {e}")
        raise
    finally:
        if connection:
            db_pool.return_connection(connection)
```

## Data Ingestion Patterns

### Document Insertion Workflow
```python
def insert_document_with_chunks(document_name: str, chunks_data: List[Dict], model_name: str = None):
    """Insert document and associated chunks with embeddings."""
    model_name = model_name or settings.embedding_model

    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # 1. Insert or get document
            cursor.execute(
                "INSERT INTO documents (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
                (document_name,)
            )
            result = cursor.fetchone()
            if result:
                document_id = result['id']
            else:
                # Document exists, get ID
                cursor.execute("SELECT id from pdf_documents WHERE name = %s", (document_name,))
                document_id = cursor.fetchone()['id']

            # 2. Insert or get model
            cursor.execute(
                """INSERT INTO models (name, dim) VALUES (%s, %s)
                   ON CONFLICT (name) DO NOTHING RETURNING id""",
                (model_name, 768)  # Adjust dimensions as needed
            )
            result = cursor.fetchone()
            if result:
                model_id = result['id']
            else:
                cursor.execute("SELECT id FROM models WHERE name = %s", (model_name,))
                model_id = cursor.fetchone()['id']

            # 3. Batch insert chunks
            chunk_values = []
            for i, chunk_data in enumerate(chunks_data):
                chunk_values.append((
                    document_id,
                    i,  # chunk_index
                    chunk_data['text'],
                    json.dumps(chunk_data.get('metadata', {}))
                ))

            cursor.executemany(
                """INSERT INTO chunks (document_id, chunk_index, text, metadata)
                   VALUES (%s, %s, %s, %s) ON CONFLICT (document_id, chunk_index) DO NOTHING""",
                chunk_values
            )

            # 4. Get chunk IDs for embedding insertion
            cursor.execute(
                "SELECT id, chunk_index from document_chunks WHERE document_id = %s ORDER BY chunk_index",
                (document_id,)
            )
            chunk_ids = cursor.fetchall()

            # 5. Batch insert embeddings (if provided)
            if 'embedding' in chunks_data[0]:
                embedding_values = []
                for i, chunk_data in enumerate(chunks_data):
                    if 'embedding' in chunk_data:
                        chunk_id = chunk_ids[i]['id']
                        embedding_values.append((chunk_id, model_id, chunk_data['embedding']))

                cursor.executemany(
                    """INSERT INTO embeddings (chunk_id, model_id, embedding)
                       VALUES (%s, %s, %s) ON CONFLICT (chunk_id, model_id) DO NOTHING""",
                    embedding_values
                )

            connection.commit()
            logger.info(f"Inserted document '{document_name}' with {len(chunks_data)} chunks")

    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        logger.error(f"Document insertion failed for '{document_name}': {e}")
        raise
    finally:
        if connection:
            connection.close()
```

### Embedding Update Batch Processing
```python
def update_embeddings_batch(model_name: str, chunk_embeddings: List[Tuple[int, List[float]]]):
    """Batch update embeddings for chunks."""
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Get model ID
            cursor.execute("SELECT id FROM models WHERE name = %s", (model_name,))
            model_result = cursor.fetchone()
            if not model_result:
                raise ValueError(f"Model not found: {model_name}")
            model_id = model_result['id']

            # Batch update embeddings
            update_values = []
            for chunk_id, embedding in chunk_embeddings:
                update_values.append((embedding, chunk_id, model_id))

            cursor.executemany(
                """INSERT INTO embeddings (chunk_id, model_id, embedding)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (chunk_id, model_id)
                   DO UPDATE SET embedding = EXCLUDED.embedding, created_at = now()""",
                [(chunk_id, model_id, embedding) for chunk_id, embedding in chunk_embeddings]
            )

            connection.commit()
            logger.info(f"Updated {len(chunk_embeddings)} embeddings for model {model_name}")

    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        logger.error(f"Embedding batch update failed: {e}")
        raise
    finally:
        if connection:
            connection.close()
```

## Performance Optimization

### Vector Index Tuning
```sql
-- IVFFlat index optimization
-- Adjust 'lists' parameter based on data size:
-- Small datasets (< 1M vectors): lists = sqrt(total_vectors)
-- Large datasets (> 1M vectors): lists = total_vectors / 1000

-- Create optimized index
CREATE INDEX CONCURRENTLY idx_embeddings_vector_optimized
ON embeddings USING ivfflat (embedding vector_l2_ops)
WITH (lists = 500);  -- Adjust based on dataset size

-- HNSW index tuning for better recall
CREATE INDEX CONCURRENTLY idx_embeddings_hnsw_tuned
ON embeddings USING hnsw (embedding vector_l2_ops)
WITH (m = 32, ef_construction = 128);  -- Higher values = better recall, slower build

-- Runtime tuning for HNSW
SET hnsw.ef_search = 100;  -- Higher = better recall, slower queries
```

### Query Performance Configuration
```postgresql
-- Optimize PostgreSQL for vector workloads
-- Add to postgresql.conf or via ALTER SYSTEM

-- Memory settings
shared_buffers = 4GB                    -- 25% of RAM
work_mem = 256MB                        -- Per-query memory
maintenance_work_mem = 2GB              -- For index creation

-- Vector-specific settings
max_parallel_workers_per_gather = 4     -- Parallel query execution
effective_cache_size = 12GB             -- Available OS cache

-- Connection settings
max_connections = 100                   -- Adjust based on load
```

### Query Optimization Patterns
```sql
-- Use EXPLAIN ANALYZE to optimize vector queries
EXPLAIN (ANALYZE, BUFFERS)
SELECT c.text, 1 - (e.embedding <=> %s::vector) AS similarity
from document_chunks c
JOIN embeddings e ON c.id = e.chunk_id
WHERE 1 - (e.embedding <=> %s::vector) > 0.3
ORDER BY e.embedding <=> %s::vector
LIMIT 10;

-- Optimize with covering indexes
CREATE INDEX idx_chunks_text_metadata
ON chunks (id) INCLUDE (text, metadata);  -- Avoid heap lookups

-- Pre-filter large datasets
CREATE INDEX idx_chunks_document_type
ON chunks ((metadata->>'document_type'));
```

## Maintenance Operations

### Database Health Monitoring
```sql
-- Check vector index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE indexname LIKE '%vector%' OR indexname LIKE '%hnsw%';

-- Monitor table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check embedding distribution
SELECT
    m.name as model_name,
    COUNT(*) as embedding_count,
    AVG(array_length(e.embedding::real[], 1)) as avg_dimensions
FROM embeddings e
JOIN models m ON e.model_id = m.id
GROUP BY m.name;
```

### Routine Maintenance Scripts
```sql
-- Vacuum and analyze vector tables
VACUUM ANALYZE embeddings;
VACUUM ANALYZE chunks;
VACUUM ANALYZE documents;

-- Reindex vector indexes (during low-traffic periods)
REINDEX INDEX CONCURRENTLY idx_embeddings_vector;

-- Update table statistics for query planner
ANALYZE embeddings;
ANALYZE chunks;
```

### Backup and Recovery
```bash
# Backup with vector data preservation
pg_dump -h localhost -U postgres -d vector_db \
    --verbose --format=custom \
    --file=vector_db_backup_$(date +%Y%m%d_%H%M%S).dump

# Restore backup
pg_restore -h localhost -U postgres -d vector_db \
    --verbose --clean --if-exists \
    vector_db_backup_20250918_120000.dump

# Selective backup (data only, no indexes)
pg_dump -h localhost -U postgres -d vector_db \
    --data-only --table=embeddings --table=chunks \
    --file=embeddings_data_$(date +%Y%m%d).sql
```

## Migration Management

### Migration Execution Pattern
```python
def execute_migration(migration_file: str):
    """Execute database migration safely."""
    migration_path = f"migrations/{migration_file}"

    if not os.path.exists(migration_path):
        raise FileNotFoundError(f"Migration file not found: {migration_path}")

    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Check if migration already applied
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations
                   (filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())"""
            )

            cursor.execute("SELECT 1 FROM schema_migrations WHERE filename = %s", (migration_file,))
            if cursor.fetchone():
                logger.info(f"Migration {migration_file} already applied, skipping")
                return

            # Read and execute migration
            with open(migration_path, 'r') as f:
                migration_sql = f.read()

            cursor.execute(migration_sql)

            # Record migration
            cursor.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (migration_file,)
            )

            connection.commit()
            logger.info(f"Migration {migration_file} applied successfully")

    except psycopg2.Error as e:
        if connection:
            connection.rollback()
        logger.error(f"Migration {migration_file} failed: {e}")
        raise
    finally:
        if connection:
            connection.close()

# Apply all pending migrations
def apply_all_migrations():
    """Apply all pending migrations in order."""
    migration_files = sorted([f for f in os.listdir("migrations") if f.endswith('.sql')])

    for migration_file in migration_files:
        execute_migration(migration_file)
```

## Error Handling and Debugging

### Common Issues and Solutions

#### Vector Dimension Mismatches
```python
def validate_embedding_dimensions(embedding: List[float], expected_dim: int = 768):
    """Validate embedding dimensions before database insertion."""
    if len(embedding) != expected_dim:
        raise ValueError(f"Embedding dimension mismatch: got {len(embedding)}, expected {expected_dim}")

    # Check for NaN or infinite values
    if any(not math.isfinite(x) for x in embedding):
        raise ValueError("Embedding contains NaN or infinite values")
```

#### Connection Recovery
```python
def execute_with_retry(query: str, params: tuple = None, max_retries: int = 3):
    """Execute query with connection retry logic."""
    for attempt in range(max_retries):
        try:
            connection = get_db_connection()
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description:
                    result = cursor.fetchall()
                else:
                    connection.commit()
                    result = []
            connection.close()
            return result

        except psycopg2.OperationalError as e:
            logger.warning(f"Database connection failed (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
        except psycopg2.Error as e:
            logger.error(f"Database query failed: {e}")
            raise
```

#### Vector Search Debugging
```sql
-- Debug vector search performance
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT c.text, 1 - (e.embedding <=> %s::vector) AS similarity
from document_chunks c
JOIN embeddings e ON c.id = e.chunk_id
WHERE 1 - (e.embedding <=> %s::vector) > 0.3
ORDER BY e.embedding <=> %s::vector
LIMIT 10;

-- Check for missing embeddings
SELECT
    COUNT(c.id) as total_chunks,
    COUNT(e.chunk_id) as chunks_with_embeddings,
    COUNT(c.id) - COUNT(e.chunk_id) as missing_embeddings
from document_chunks c
LEFT JOIN embeddings e ON c.id = e.chunk_id;
```

## Security Considerations

### Connection Security
```python
# Use environment variables for sensitive data
# Never hardcode credentials in application code

# SSL connection (production)
def get_secure_db_connection():
    """Create SSL-secured database connection."""
    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        sslmode='require',  # Enforce SSL
        sslcert='client-cert.pem',
        sslkey='client-key.pem',
        sslrootcert='ca-cert.pem'
    )
```

### Query Parameterization
```python
# ✅ CORRECT - Always use parameterized queries
cursor.execute(
    "SELECT * from document_chunks WHERE document_id = %s AND text ILIKE %s",
    (document_id, f"%{search_term}%")
)

# ❌ INCORRECT - SQL injection vulnerability
cursor.execute(f"SELECT * from document_chunks WHERE text LIKE '%{user_input}%'")
```

## Summary

These PostgreSQL instructions provide comprehensive coverage of database operations for the Technical Service Assistant:

- **Architecture**: Modern multi-table schema with proper normalization
- **Vector Operations**: Optimized similarity search with multiple index strategies
- **Connection Management**: Robust connection handling with pooling for high-throughput
- **Performance**: Index tuning and query optimization for vector workloads
- **Maintenance**: Health monitoring, backup procedures, and migration management
- **Security**: Parameterized queries and secure connection patterns

Follow these patterns to maintain database performance, reliability, and security in your AI PDF vector search system.
