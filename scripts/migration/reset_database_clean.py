#!/usr/bin/env python3
"""
Clean Database Reset Script
===========================

Drops all tables and recreates with unified Python worker schema.
Then re-processes all PDFs from uploads/ directory.

This eliminates N8N legacy confusion and ensures clean foreign key integrity.
"""

import os
import sys
from pathlib import Path

import psycopg2

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import get_settings

settings = get_settings()


def get_db_connection():
    return psycopg2.connect(
        host="localhost" if settings.db_host == "pgvector" else settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


def drop_all_tables():
    """Drop all existing tables"""
    conn = get_db_connection()
    cur = conn.cursor()

    print("🗑️  Dropping all existing tables...")

    # Drop all tables (order matters for foreign keys)
    tables_to_drop = [
        "chat_messages",
        "chat_sessions",
        "embeddings",
        "chunks",
        "models",
        "chunks_backup",
        "embeddings_backup",
        "models_backup",
        "document_chunks",
        "pdf_documents",
    ]

    for table in tables_to_drop:
        try:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
            print(f"   ✅ Dropped {table}")
        except Exception as e:
            print(f"   ⚠️  {table}: {e}")

    # Drop functions
    try:
        cur.execute("DROP FUNCTION IF EXISTS match_document_chunks CASCADE;")
        print("   ✅ Dropped match_document_chunks function")
    except Exception as e:
        print(f"   ⚠️  Function: {e}")

    conn.commit()
    cur.close()
    conn.close()

    print("✅ All tables dropped")


def recreate_schema():
    """Recreate schema using init.sql"""
    print("🔄 Recreating schema from init.sql...")

    # Read init.sql
    init_sql_path = Path(__file__).parent / "init.sql"
    with open(init_sql_path, "r") as f:
        init_sql = f.read()

    conn = get_db_connection()
    cur = conn.cursor()

    # Execute init.sql
    cur.execute(init_sql)
    conn.commit()

    # Verify tables created
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """
    )

    tables = [row[0] for row in cur.fetchall()]
    print(f"✅ Schema recreated with tables: {', '.join(tables)}")

    cur.close()
    conn.close()


def update_code_to_use_document_chunks():
    """Update all code files to use document_chunks instead of chunks"""
    print("🔧 Updating code to use document_chunks schema...")

    # List of files that need updating
    files_to_update = [
        "reranker/app.py",
        "pdf_processor/utils.py",
        "scripts/verify_ingestion.py",
        "scripts/eval_suite.py",
        "bin/ask_questions.py",
        "bin/monitor_uploads.py",
        "bin/process_all_pdfs.py",
    ]

    # Mapping of old queries to new queries
    query_mappings = {
        # Basic table references
        "from document_chunks": "FROM document_chunks",
        "INTO chunks": "INTO document_chunks",
        "UPDATE chunks": "UPDATE document_chunks",
        "DELETE from document_chunks": "DELETE FROM document_chunks",
        # Column mappings for document_chunks schema
        "chunks.text": "document_chunks.content",
        "c.text": "c.content",
        "chunk_index": "page_number",
        "chunks.metadata": "document_chunks.chunk_type",
        # Embedding joins (now integrated)
        """from document_chunks c
        INNER JOIN embeddings e ON c.id = e.chunk_id""": "FROM document_chunks c",
        """from document_chunks c
                INNER JOIN embeddings e ON c.id = e.chunk_id""": "FROM document_chunks c",
        # Vector similarity with integrated embeddings
        "e.embedding": "c.embedding",
        "embeddings.embedding": "document_chunks.embedding",
    }

    updated_files = []
    for file_path in files_to_update:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    content = f.read()

                original_content = content
                for old_pattern, new_pattern in query_mappings.items():
                    content = content.replace(old_pattern, new_pattern)

                if content != original_content:
                    with open(file_path, "w") as f:
                        f.write(content)
                    updated_files.append(file_path)

            except Exception as e:
                print(f"   ⚠️  Failed to update {file_path}: {e}")

    if updated_files:
        print(f"✅ Updated {len(updated_files)} files:")
        for file_path in updated_files:
            print(f"   - {file_path}")
    else:
        print("ℹ️  No files needed updating")


def trigger_pdf_reprocessing():
    """Trigger re-processing of all PDFs"""
    print("📄 Triggering PDF re-processing...")

    uploads_dir = Path("uploads")
    pdf_files = list(uploads_dir.glob("*.pdf"))

    print(f"Found {len(pdf_files)} PDFs to process:")
    for pdf in pdf_files:
        print(f"   - {pdf.name}")

    if pdf_files:
        print("🚀 PDF processor will automatically detect and process these files")
        print(f"   Monitor logs: docker logs -f pdf_processor")
    else:
        print("⚠️  No PDF files found in uploads/")


def verify_clean_schema():
    """Verify the new schema is working"""
    print("🔍 Verifying clean schema...")

    conn = get_db_connection()
    cur = conn.cursor()

    # Check tables exist
    cur.execute("SELECT COUNT(*) FROM pdf_documents;")
    result = cur.fetchone()
    pdf_docs_count = result[0] if result else 0

    cur.execute("SELECT COUNT(*) FROM document_chunks;")
    result = cur.fetchone()
    chunks_count = result[0] if result else 0

    # Test the function
    try:
        cur.execute("SELECT match_document_chunks(ARRAY[0.1,0.2,0.3]::vector(3), 0.5, 1);")
        function_works = True
    except Exception:
        function_works = False

    print(f"✅ Schema verification:")
    print(f"   - pdf_documents: {pdf_docs_count} records")
    print(f"   - document_chunks: {chunks_count} records")
    print(f"   - match_document_chunks function: {'✅' if function_works else '❌'}")

    cur.close()
    conn.close()

    return pdf_docs_count >= 0 and function_works


def main():
    """Main reset process"""
    print("🎯 Clean Database Reset")
    print("=" * 50)
    print("This will drop all tables and recreate with unified schema")
    print()

    # Confirm destructive operation
    response = input("🚨 This will DELETE ALL DATA. Continue? (y/N): ")
    if response.lower() != "y":
        print("❌ Operation cancelled")
        return 1

    try:
        # Step 1: Drop all tables
        drop_all_tables()
        print()

        # Step 2: Recreate schema
        recreate_schema()
        print()

        # Step 3: Update code
        update_code_to_use_document_chunks()
        print()

        # Step 4: Verify schema
        if verify_clean_schema():
            print()
            print("🎉 Database reset complete!")
            print()

            # Step 5: Trigger reprocessing
            trigger_pdf_reprocessing()

            print()
            print("🚀 Next steps:")
            print("   1. Wait for PDF processor to re-process files")
            print("   2. Monitor: docker logs -f pdf_processor")
            print("   3. Test: python test_connectivity.py")

        else:
            print("❌ Schema verification failed!")
            return 1

    except Exception as e:
        print(f"❌ Reset failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
