#!/usr/bin/env python3
"""
Database Schema Consolidation Script
====================================

Migrates from N8N legacy schema (chunks + embeddings) to unified Python worker schema (document_chunks).
This script consolidates the dual table structure and removes confusion.

Legacy N8N Schema:
- chunks(id, document_id, chunk_index, text, metadata)
- embeddings(id, chunk_id, model_id, embedding)

Target Python Worker Schema:
- document_chunks(id, document_id, page_number, chunk_type, content, embedding, created_at)

"""

import os
import sys

import psycopg2

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import get_settings

settings = get_settings()


def get_db_connection():
    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


def migrate_data():
    """Migrate data from document_chunks+embeddings to document_chunks"""
    conn = get_db_connection()
    cur = conn.cursor()

    print("🔄 Starting schema consolidation migration...")

    # Step 1: Check current state
    cur.execute("SELECT COUNT(*) from document_chunks;")
    result = cur.fetchone()
    chunks_count = result[0] if result else 0

    cur.execute("SELECT COUNT(*) FROM embeddings;")
    result = cur.fetchone()
    embeddings_count = result[0] if result else 0

    cur.execute("SELECT COUNT(*) FROM document_chunks;")
    result = cur.fetchone()
    document_chunks_count = result[0] if result else 0

    print(f"📊 Current state:")
    print(f"   - chunks: {chunks_count} records")
    print(f"   - embeddings: {embeddings_count} records")
    print(f"   - document_chunks: {document_chunks_count} records")

    if document_chunks_count > 0:
        print("⚠️  document_chunks already has data. Skipping migration.")
        return False

    # Step 2: Migrate data with JOIN
    print("🚀 Migrating chunks + embeddings → document_chunks...")

    # First, get the default model_id (most common)
    cur.execute(
        """
        SELECT model_id, COUNT(*) as count
        FROM embeddings
        GROUP BY model_id
        ORDER BY count DESC
        LIMIT 1;
    """
    )
    default_model = cur.fetchone()
    if not default_model:
        print("❌ No embeddings found. Cannot proceed.")
        return False

    default_model_id = default_model[0]
    print(f"   Using default model_id: {default_model_id}")

    # Migrate data using JOIN between chunks and embeddings
    migration_query = """
        INSERT INTO document_chunks (
            document_id,
            page_number,
            chunk_type,
            content,
            embedding,
            created_at
        )
        SELECT
            c.document_id,
            COALESCE((c.metadata->>'page_number')::integer, c.chunk_index) as page_number,
            COALESCE(c.metadata->>'chunk_type', 'text') as chunk_type,
            c.text as content,
            e.embedding,
            NOW() as created_at
        from document_chunks c
        INNER JOIN embeddings e ON c.id = e.chunk_id
        WHERE e.model_id = %s
        ORDER BY c.document_id, c.chunk_index;
    """

    cur.execute(migration_query, (default_model_id,))
    migrated_count = cur.rowcount

    print(f"✅ Migrated {migrated_count} records to document_chunks")

    # Step 3: Verify migration
    cur.execute("SELECT COUNT(*) FROM document_chunks;")
    result = cur.fetchone()
    final_count = result[0] if result else 0

    print(f"📊 Final document_chunks count: {final_count}")

    conn.commit()
    cur.close()
    conn.close()

    return True


def backup_legacy_tables():
    """Create backup tables before dropping"""
    conn = get_db_connection()
    cur = conn.cursor()

    print("💾 Creating backup tables...")

    # Backup chunks
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks_backup AS
        SELECT * from document_chunks;
    """
    )

    # Backup embeddings
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings_backup AS
        SELECT * FROM embeddings;
    """
    )

    # Backup models
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS models_backup AS
        SELECT * FROM models;
    """
    )

    conn.commit()
    cur.close()
    conn.close()

    print("✅ Backup tables created (chunks_backup, embeddings_backup, models_backup)")


def drop_legacy_tables():
    """Drop the old N8N schema tables"""
    conn = get_db_connection()
    cur = conn.cursor()

    print("🗑️  Dropping legacy N8N tables...")

    # Drop in correct order (foreign key dependencies)
    cur.execute("DROP TABLE IF EXISTS embeddings CASCADE;")
    cur.execute("DROP TABLE IF EXISTS chunks CASCADE;")
    cur.execute("DROP TABLE IF EXISTS models CASCADE;")

    print("✅ Legacy tables dropped")

    conn.commit()
    cur.close()
    conn.close()


def verify_migration():
    """Verify the migration was successful"""
    conn = get_db_connection()
    cur = conn.cursor()

    print("🔍 Verifying migration...")

    # Check document_chunks has data
    cur.execute("SELECT COUNT(*) FROM document_chunks;")
    result = cur.fetchone()
    count = result[0] if result else 0

    # Check we have embeddings
    cur.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL;")
    result = cur.fetchone()
    embedding_count = result[0] if result else 0

    # Check some sample data
    cur.execute(
        """
        SELECT document_id, chunk_type, LENGTH(content), vector_dims(embedding)
        FROM document_chunks
        LIMIT 3;
    """
    )
    samples = cur.fetchall()

    print(f"✅ Verification Results:")
    print(f"   - Total records: {count}")
    print(f"   - Records with embeddings: {embedding_count}")
    print(f"   - Sample data:")
    for doc_id, chunk_type, content_len, embed_dims in samples:
        print(f"     * Doc {doc_id}: {chunk_type}, {content_len} chars, {embed_dims}D embedding")

    cur.close()
    conn.close()

    return count > 0 and embedding_count > 0


def main():
    """Main consolidation process"""
    print("🎯 Database Schema Consolidation")
    print("=" * 50)
    print("Migrating from N8N legacy schema to Python worker schema")
    print()

    try:
        # Step 1: Backup existing data
        backup_legacy_tables()
        print()

        # Step 2: Migrate data
        if migrate_data():
            print()

            # Step 3: Verify migration
            if verify_migration():
                print()
                print("🎉 Migration completed successfully!")
                print()

                # Ask for confirmation before dropping
                response = input("🚨 Drop legacy tables? (y/N): ")
                if response.lower() == "y":
                    drop_legacy_tables()
                    print("✅ Schema consolidation complete!")
                else:
                    print("⏸️  Legacy tables preserved. Run again to complete.")
            else:
                print("❌ Migration verification failed!")
                return 1
        else:
            print("⏸️  Migration skipped or failed.")
            return 1

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
