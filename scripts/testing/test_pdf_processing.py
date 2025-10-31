#!/usr/bin/env python3
"""
Simple PDF Processing Test Script
=================================

Test script to diagnose PDF processing issues with the unified schema.
"""

import os
import sys

sys.path.append("/app")

from config import get_settings
from pdf_processor.utils import chunk_text, extract_text, get_db_connection, get_embedding, insert_chunk_and_embedding


def test_processing():
    """Test the complete processing pipeline with debugging."""

    print("🔧 Testing PDF Processing Pipeline")
    print("=" * 50)

    # Test 1: Database connection
    print("1. Testing database connection...")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM pdf_documents;")
        result = cur.fetchone()
        print(f"   ✅ Database connected. pdf_documents count: {result[0]}")
        cur.close()
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        return

    # Test 2: Check for PDF files
    print("\n2. Checking for PDF files...")
    settings = get_settings()
    uploads_dir = settings.uploads_dir
    pdf_files = [f for f in os.listdir(uploads_dir) if f.lower().endswith(".pdf")]
    print(f"   Found {len(pdf_files)} PDF files: {pdf_files}")

    if not pdf_files:
        print("   No PDFs to test with.")
        return

    # Test 3: Process first PDF
    pdf_file = pdf_files[0]
    pdf_path = os.path.join(uploads_dir, pdf_file)
    print(f"\n3. Testing processing of: {pdf_file}")

    try:
        # Extract text
        print("   Extracting text...")
        text = extract_text(pdf_path)
        print(f"   ✅ Extracted {len(text)} characters")

        # Chunk text
        print("   Chunking text...")
        chunks = chunk_text(text, pdf_file)
        print(f"   ✅ Created {len(chunks)} chunks")

        if chunks:
            # Test single chunk processing
            test_chunk = chunks[0]
            print(f"\n4. Testing embedding generation for first chunk...")
            print(f"   Chunk text preview: {test_chunk['text'][:100]}...")

            try:
                embedding = get_embedding(test_chunk["text"])
                print(f"   ✅ Generated embedding with {len(embedding)} dimensions")

                # Test database insertion
                print("\n5. Testing database insertion...")
                conn = get_db_connection()
                try:
                    insert_chunk_and_embedding(conn, test_chunk, embedding, "nomic-embed-text:v1.5")
                    conn.commit()
                    print("   ✅ Successfully inserted chunk to database")

                    # Verify insertion
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM pdf_documents;")
                    docs = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM document_chunks;")
                    chunks_count = cur.fetchone()[0]
                    print(f"   📊 Database now has: {docs} documents, {chunks_count} chunks")
                    cur.close()

                except Exception as e:
                    print(f"   ❌ Database insertion failed: {e}")
                    conn.rollback()
                finally:
                    conn.close()

            except Exception as e:
                print(f"   ❌ Embedding generation failed: {e}")

    except Exception as e:
        print(f"   ❌ PDF processing failed: {e}")

    print("\n✅ Test completed!")


if __name__ == "__main__":
    test_processing()
