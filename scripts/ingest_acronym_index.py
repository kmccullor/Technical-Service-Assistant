#!/usr/bin/env python3
"""
Ingest Acronym Index into Vector Database
Script to add the acronym index to the vector database for cross-referencing during searches.
"""

import os
import sys
import json
import hashlib
import requests
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config import get_settings
from pdf_processor.pdf_utils import get_db_connection, get_embedding

def ingest_acronym_index():
    """Ingest the acronym index markdown file into the vector database."""
    
    settings = get_settings()
    acronym_file = os.path.join(project_root, "ACRONYM_INDEX.md")
    
    if not os.path.exists(acronym_file):
        print(f"❌ Acronym index file not found: {acronym_file}")
        return False
    
    print(f"📚 Processing acronym index: {acronym_file}")
    
    # Read the file content
    with open(acronym_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if not content.strip():
        print("❌ Acronym index file is empty")
        return False
    
    # Create chunks for better searchability
    chunks = create_acronym_chunks(content)
    print(f"📝 Created {len(chunks)} searchable chunks from acronym index")
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        with conn.cursor() as cursor:
            # Check if document already exists
            cursor.execute(
                "SELECT id FROM documents WHERE source = %s",
                ("ACRONYM_INDEX.md",)
            )
            existing_doc = cursor.fetchone()
            
            if existing_doc:
                doc_id = existing_doc[0]
                print(f"🔄 Updating existing acronym index (doc_id: {doc_id})")
                # Delete existing chunks
                cursor.execute("DELETE FROM document_chunks WHERE document_id = %s", (doc_id,))
            else:
                # Insert new document
                cursor.execute("""
                    INSERT INTO documents (title, source, document_type, created_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (
                    "Technical Service Assistant - Acronym Index & References",
                    "ACRONYM_INDEX.md",
                    "reference_manual",
                    datetime.now()
                ))
                result = cursor.fetchone()
                if not result:
                    print("❌ Failed to create document entry")
                    return False
                doc_id = result[0]
                print(f"✅ Created new document entry (doc_id: {doc_id})")
            
            # Insert chunks
            chunk_count = 0
            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding = get_embedding(chunk['content'])
                if not embedding:
                    print(f"⚠️ Failed to generate embedding for chunk {i+1}")
                    continue
                
                content_hash = hashlib.md5(chunk['content'].encode()).hexdigest()
                
                cursor.execute("""
                    INSERT INTO document_chunks (
                        document_id, chunk_index, page_number, section_title,
                        chunk_type, content, content_hash, content_length,
                        embedding, language, metadata, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    doc_id,
                    i,
                    1,  # All on "page 1" since it's a markdown file
                    chunk['section_title'],
                    chunk['chunk_type'],
                    chunk['content'],
                    content_hash,
                    len(chunk['content']),
                    embedding,
                    'en',
                    chunk['metadata'],
                    datetime.now()
                ))
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

def create_acronym_chunks(content):
    """Create searchable chunks from the acronym index content."""
    chunks = []
    
    # Split by main sections
    sections = content.split('## ')
    
    for i, section in enumerate(sections):
        if not section.strip():
            continue
            
        # First section won't have the ## prefix
        if i == 0:
            section_title = "Introduction"
            section_content = section
        else:
            lines = section.split('\n', 1)
            section_title = lines[0].replace('*', '').strip()
            section_content = lines[1] if len(lines) > 1 else ""
        
        if not section_content.strip():
            continue
        
        # Further split large sections by individual acronyms
        if section_title not in ["Introduction", "Usage Guidelines", "Updates & Maintenance"]:
            # Split by ### entries (individual acronyms)
            acronym_entries = section_content.split('### ')
            
            for j, entry in enumerate(acronym_entries):
                if not entry.strip():
                    continue
                
                if j == 0:
                    # First part might be section introduction
                    if entry.strip():
                        chunks.append({
                            'content': f"## {section_title}\n\n{entry.strip()}",
                            'section_title': section_title,
                            'chunk_type': 'text',
                            'metadata': {
                                'section': section_title,
                                'chunk_type': 'section_intro',
                                'document_type': 'acronym_index'
                            }
                        })
                else:
                    # Individual acronym entry
                    lines = entry.split('\n', 1)
                    acronym_name = lines[0].strip()
                    acronym_content = lines[1] if len(lines) > 1 else ""
                    
                    full_content = f"### {acronym_name}\n{acronym_content}"
                    
                    chunks.append({
                        'content': full_content.strip(),
                        'section_title': f"{section_title} - {acronym_name}",
                        'chunk_type': 'text',
                        'metadata': {
                            'section': section_title,
                            'acronym': acronym_name.split(' - ')[0] if ' - ' in acronym_name else acronym_name,
                            'chunk_type': 'acronym_definition',
                            'document_type': 'acronym_index'
                        }
                    })
        else:
            # Keep full section for guidelines and metadata
            chunks.append({
                'content': f"## {section_title}\n\n{section_content.strip()}",
                'section_title': section_title,
                'chunk_type': 'text',
                'metadata': {
                    'section': section_title,
                    'chunk_type': 'guidance',
                    'document_type': 'acronym_index'
                }
            })
    
    return chunks

if __name__ == "__main__":
    print("🚀 Starting acronym index ingestion...")
    success = ingest_acronym_index()
    
    if success:
        print("✅ Acronym index successfully added to vector database!")
        print("🔍 The acronym definitions are now available for cross-referencing during searches.")
    else:
        print("❌ Failed to ingest acronym index")
        sys.exit(1)