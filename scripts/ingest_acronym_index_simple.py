#!/usr/bin/env python3
"""
Simple Acronym Index Ingestion Script
Direct database insertion without complex logging setup.
"""

import hashlib
import json
import os
import sys
from datetime import datetime

import psycopg2
import requests


def get_database_connection():
    """Get database connection using environment variables."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", 5432),
            database=os.getenv("DB_NAME", "vector_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None


def get_ollama_embedding(text: str, model: str = "nomic-embed-text:v1.5") -> list:
    """Get embedding from Ollama API."""
    ollama_urls = [
        "http://localhost:11434",
        "http://localhost:11435",
        "http://localhost:11436",
        "http://localhost:11437",
    ]

    for url in ollama_urls:
        try:
            response = requests.post(f"{url}/api/embed", json={"model": model, "input": text}, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("embeddings", [data.get("embedding", [])])[0]
        except Exception as e:
            print(f"⚠️ Ollama instance {url} failed: {e}")
            continue

    print(f"❌ All Ollama instances failed for embedding generation")
    return []


def create_acronym_chunks(content):
    """Create searchable chunks from the acronym index content."""
    chunks = []

    # Split by main sections
    sections = content.split("## ")

    for i, section in enumerate(sections):
        if not section.strip():
            continue

        # First section won't have the ## prefix
        if i == 0:
            section_title = "Introduction"
            section_content = section
        else:
            lines = section.split("\n", 1)
            section_title = lines[0].replace("*", "").strip()
            section_content = lines[1] if len(lines) > 1 else ""

        if not section_content.strip():
            continue

        # Further split large sections by individual acronyms
        if section_title not in ["Introduction", "Usage Guidelines", "Updates & Maintenance"] and "**" in section_title:
            # Split by ### entries (individual acronyms)
            acronym_entries = section_content.split("### ")

            for j, entry in enumerate(acronym_entries):
                if not entry.strip():
                    continue

                if j == 0:
                    # First part might be section introduction
                    if entry.strip():
                        chunks.append(
                            {
                                "content": f"## {section_title}\n\n{entry.strip()}",
                                "section_title": section_title,
                                "chunk_type": "text",
                                "metadata": {
                                    "section": section_title,
                                    "chunk_type": "section_intro",
                                    "document_type": "acronym_index",
                                },
                            }
                        )
                else:
                    # Individual acronym entry
                    lines = entry.split("\n", 1)
                    acronym_name = lines[0].strip()
                    acronym_content = lines[1] if len(lines) > 1 else ""

                    full_content = f"### {acronym_name}\n{acronym_content}"

                    chunks.append(
                        {
                            "content": full_content.strip(),
                            "section_title": f"{section_title} - {acronym_name}",
                            "chunk_type": "text",
                            "metadata": {
                                "section": section_title,
                                "acronym": acronym_name.split(" - ")[0] if " - " in acronym_name else acronym_name,
                                "chunk_type": "acronym_definition",
                                "document_type": "acronym_index",
                            },
                        }
                    )
        else:
            # Keep full section for guidelines and metadata
            chunks.append(
                {
                    "content": f"## {section_title}\n\n{section_content.strip()}",
                    "section_title": section_title,
                    "chunk_type": "text",
                    "metadata": {"section": section_title, "chunk_type": "guidance", "document_type": "acronym_index"},
                }
            )

    return chunks


def main():
    """Main ingestion function."""
    print("🚀 Starting acronym index ingestion...")

    # Find the acronym index file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    acronym_file = os.path.join(project_root, "ACRONYM_INDEX.md")

    if not os.path.exists(acronym_file):
        print(f"❌ Acronym index file not found: {acronym_file}")
        return False

    print(f"📚 Processing acronym index: {acronym_file}")

    # Read the file content
    with open(acronym_file, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        print("❌ Acronym index file is empty")
        return False

    # Create chunks for better searchability
    chunks = create_acronym_chunks(content)
    print(f"📝 Created {len(chunks)} searchable chunks from acronym index")

    # Connect to database
    conn = get_database_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False

    try:
        with conn.cursor() as cursor:
            # Check if document already exists
            cursor.execute("SELECT id FROM documents WHERE file_name = %s", ("ACRONYM_INDEX.md",))
            existing_doc = cursor.fetchone()

            if existing_doc:
                doc_id = existing_doc[0]
                print(f"🔄 Updating existing acronym index (doc_id: {doc_id})")
                # Delete existing chunks
                cursor.execute("DELETE FROM document_chunks WHERE document_id = %s", (doc_id,))
            else:
                # Insert new document
                cursor.execute(
                    """
                    INSERT INTO documents (title, file_name, file_hash, document_type, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        "Technical Service Assistant - Acronym Index & References",
                        "ACRONYM_INDEX.md",
                        hashlib.md5("ACRONYM_INDEX.md".encode()).hexdigest(),
                        "reference_manual",
                        datetime.now(),
                    ),
                )
                result = cursor.fetchone()
                if not result:
                    print("❌ Failed to create document entry")
                    return False
                doc_id = result[0]
                print(f"✅ Created new document entry (doc_id: {doc_id})")

            # Insert chunks
            chunk_count = 0
            for i, chunk in enumerate(chunks):
                print(f"📄 Processing chunk {i+1}/{len(chunks)}: {chunk['section_title']}")

                # Generate embedding
                embedding = get_ollama_embedding(chunk["content"])
                if not embedding:
                    print(f"⚠️ Failed to generate embedding for chunk {i+1}, skipping...")
                    continue

                content_hash = hashlib.md5(chunk["content"].encode()).hexdigest()

                cursor.execute(
                    """
                    INSERT INTO document_chunks (
                        document_id, chunk_index, page_number,
                        chunk_type, content, content_hash, content_length,
                        embedding, metadata, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        doc_id,
                        i,
                        1,  # All on "page 1" since it's a markdown file
                        chunk["chunk_type"],
                        chunk["content"],
                        content_hash,
                        len(chunk["content"]),
                        embedding,
                        json.dumps(chunk["metadata"]),
                        datetime.now(),
                    ),
                )
                chunk_count += 1

            conn.commit()
            print(f"✅ Successfully ingested {chunk_count} chunks from acronym index")
            return True

    except Exception as e:
        print(f"❌ Error ingesting acronym index: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = main()

    if success:
        print("✅ Acronym index successfully added to vector database!")
        print("🔍 The acronym definitions are now available for cross-referencing during searches.")
    else:
        print("❌ Failed to ingest acronym index")
        sys.exit(1)
