#!/usr/bin/env python3
"""
Verification script for AI categorization database schema and functionality.
"""

import os
import sys

sys.path.append("/home/kmccullor/Projects/Technical-Service-Assistant")

# Set environment variables to avoid app directory issues
os.environ["UPLOADS_DIR"] = "/home/kmccullor/Projects/Technical-Service-Assistant/uploads"
os.environ["ARCHIVE_DIR"] = "/home/kmccullor/Projects/Technical-Service-Assistant/uploads/archive"

import psycopg2

from config import get_settings


def verify_ai_categorization_schema():
    """Verify that the AI categorization database schema is properly applied."""
    print("Verifying AI Categorization Database Schema")
    print("=" * 60)

    try:
        # Get database connection
        get_settings()
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),  # Use localhost instead of docker service name
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "vector_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
        )

        with conn.cursor() as cur:
            # Check pdf_documents table schema
            print("1. Checking pdf_documents table schema...")
            cur.execute(
                """
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'pdf_documents'
                AND column_name IN ('document_type', 'product_name', 'product_version',
                                  'document_category', 'classification_confidence', 'ai_metadata')
                ORDER BY column_name;
            """
            )

            pdf_docs_columns = cur.fetchall()
            print(f"   Found {len(pdf_docs_columns)} AI categorization columns:")
            for col_name, data_type, default_val in pdf_docs_columns:
                print(f"     - {col_name}: {data_type} (default: {default_val})")

            # Check document_chunks table schema
            print("\n2. Checking document_chunks table schema...")
            cur.execute(
                """
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'document_chunks'
                AND column_name IN ('document_type', 'product_name')
                ORDER BY column_name;
            """
            )

            chunks_columns = cur.fetchall()
            print(f"   Found {len(chunks_columns)} AI categorization columns:")
            for col_name, data_type, default_val in chunks_columns:
                print(f"     - {col_name}: {data_type} (default: {default_val})")

            # Check for new functions
            print("\n3. Checking for AI categorization functions...")
            cur.execute(
                """
                SELECT routine_name, routine_type
                FROM information_schema.routines
                WHERE routine_name LIKE '%categorized%'
                OR routine_name LIKE '%categorization%'
                ORDER BY routine_name;
            """
            )

            functions = cur.fetchall()
            print(f"   Found {len(functions)} categorization functions:")
            for func_name, func_type in functions:
                print(f"     - {func_name} ({func_type})")

            # Check indexes
            print("\n4. Checking for AI categorization indexes...")
            cur.execute(
                """
                SELECT indexname, tablename
                FROM pg_indexes
                WHERE indexname LIKE '%document_type%'
                OR indexname LIKE '%product_name%'
                OR indexname LIKE '%ai_metadata%'
                ORDER BY tablename, indexname;
            """
            )

            indexes = cur.fetchall()
            print(f"   Found {len(indexes)} categorization indexes:")
            for idx_name, table_name in indexes:
                print(f"     - {idx_name} on {table_name}")

            # Sample data check
            print("\n5. Checking for existing categorized documents...")
            cur.execute(
                """
                SELECT COUNT(*) as total_docs,
                       COUNT(CASE WHEN document_type != 'unknown' THEN 1 END) as categorized_docs,
                       COUNT(CASE WHEN product_name != 'unknown' THEN 1 END) as with_product,
                       COUNT(CASE WHEN classification_confidence > 0 THEN 1 END) as with_confidence
                FROM pdf_documents;
            """
            )

            stats = cur.fetchone()
            if stats:
                total, categorized, with_product, with_confidence = stats
                print(f"   Total documents: {total}")
                print(f"   Categorized documents: {categorized}")
                print(f"   Documents with product info: {with_product}")
                print(f"   Documents with AI confidence: {with_confidence}")
            else:
                categorized = 0
                print("   No document statistics available")

            # Show sample categorized documents
            if categorized > 0:
                print("\n6. Sample categorized documents:")
                cur.execute(
                    """
                    SELECT file_name, document_type, product_name, product_version,
                           classification_confidence
                    FROM pdf_documents
                    WHERE document_type != 'unknown' OR product_name != 'unknown'
                    ORDER BY classification_confidence DESC
                    LIMIT 5;
                """
                )

                samples = cur.fetchall()
                for sample in samples:
                    file_name, doc_type, product, version, confidence = sample
                    print(f"     - {file_name}")
                    print(f"       Type: {doc_type}, Product: {product} v{version}")
                    print(f"       Confidence: {confidence:.2f}")
                    print()

            # Test the categorization search function
            print("7. Testing categorization search function...")
            try:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM match_document_chunks_categorized(
                        array[0.1, 0.2, 0.3]::float[], -- dummy embedding
                        5,                             -- match_count
                        'public',                      -- privacy_level
                        null,                          -- document_type
                        null                           -- product_name
                    );
                """
                )
                result = cur.fetchone()
                print(f"   Categorization search function working: {result[0] if result else 'No results'}")
            except Exception as e:
                print(f"   Categorization search function error: {e}")

        conn.close()
        print("\n" + "=" * 60)
        print("AI Categorization Schema Verification: COMPLETE")
        return True

    except Exception as e:
        print(f"Schema verification failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify_ai_categorization_schema()
    sys.exit(0 if success else 1)
