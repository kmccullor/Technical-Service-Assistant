#!/usr/bin/env python3
"""
Update TSVector for Acronym Index
Updates the full-text search vectors for better searchability.
"""

import psycopg2
import os

def update_tsvector():
    """Update the tsvector for the acronym index document."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', 5432),
            database=os.getenv('DB_NAME', 'vector_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )

        with conn.cursor() as cursor:
            # Update content_tsvector for acronym index chunks
            cursor.execute("""
                UPDATE document_chunks
                SET content_tsvector = to_tsvector('english', content)
                WHERE document_id IN (
                    SELECT id FROM documents WHERE file_name = 'ACRONYM_INDEX.md'
                )
            """)

            rows_updated = cursor.rowcount
            print(f"✅ Updated tsvector for {rows_updated} acronym index chunks")

            conn.commit()

            # Test query to see if we can find GUI
            cursor.execute("""
                SELECT content
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.file_name = 'ACRONYM_INDEX.md'
                AND content_tsvector @@ to_tsquery('english', 'GUI | Graphical')
                LIMIT 3
            """)

            results = cursor.fetchall()
            print(f"🔍 Found {len(results)} chunks matching 'GUI | Graphical'")
            for i, result in enumerate(results):
                print(f"  Result {i+1}: {result[0][:100]}...")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🚀 Updating TSVector for acronym index...")
    update_tsvector()
    print("✅ TSVector update complete!")