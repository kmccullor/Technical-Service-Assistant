#!/usr/bin/env python3
"""
Update the acronyms database table with extracted acronyms from documents.

This script:
1. Extracts acronyms from available documents using the AcronymExtractor
2. Creates/updates ACRONYM_INDEX.md with the extracted acronyms
3. Populates the database acronyms table with the extracted data
"""

import os
import sys
from pathlib import Path
from typing import Dict, Set

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from docling_processor.acronym_extractor import AcronymExtractor, save_acronyms_to_file, load_existing_acronyms
from config import get_settings
import psycopg2
from psycopg2.extras import RealDictCursor


def extract_acronyms_from_documents() -> tuple[Dict[str, str], Set[str]]:
    """
    Extract acronyms from all available documents.

    Returns:
        Tuple of (acronyms_dict, source_documents_set)
    """
    extractor = AcronymExtractor()
    all_acronyms = {}
    source_docs = set()

    # Check for PDF files in uploads and root directory
    pdf_paths = [
        Path("uploads/sample.pdf"),
        Path("sample.pdf"),
    ]

    for pdf_path in pdf_paths:
        if pdf_path.exists():
            print(f"Processing {pdf_path}...")
            try:
                # Extract text from PDF using PyMuPDF
                import fitz

                with fitz.open(str(pdf_path)) as doc:
                    text = ""
                    for page in doc:
                        text += page.get_text()

                if text.strip():
                    # Extract acronyms from the text
                    acronyms = extractor.extract_from_text(text, pdf_path.name)
                    all_acronyms = extractor.merge_acronyms(all_acronyms, acronyms)
                    source_docs.add(pdf_path.name)
                    print(f"  Extracted {len(acronyms)} acronyms from {pdf_path.name}")

            except Exception as e:
                print(f"  Error processing {pdf_path}: {e}")

    # Also check for any markdown files that might contain acronyms
    md_files = list(Path("docs").rglob("*.md"))
    for md_file in md_files[:10]:  # Limit to first 10 to avoid too much processing
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                text = f.read()

            acronyms = extractor.extract_from_text(text, md_file.name)
            all_acronyms = extractor.merge_acronyms(all_acronyms, acronyms)
            source_docs.add(md_file.name)

        except Exception as e:
            print(f"  Error processing {md_file}: {e}")

    return all_acronyms, source_docs


def update_acronym_index_file(acronyms: Dict[str, str], source_docs: Set[str]):
    """Update the ACRONYM_INDEX.md file with extracted acronyms."""
    save_acronyms_to_file(acronyms, "ACRONYM_INDEX.md", source_docs)
    print(f"Updated ACRONYM_INDEX.md with {len(acronyms)} acronyms")


def populate_database(acronyms: Dict[str, str], source_docs: Set[str]):
    """Populate the acronyms table in the database."""
    settings = get_settings()

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password
        )
        cursor = conn.cursor()

        # First, load existing acronyms to avoid duplicates
        cursor.execute("SELECT acronym, definition FROM acronyms")
        existing_acronyms = {row[0]: row[1] for row in cursor.fetchall()}

        inserted_count = 0
        updated_count = 0

        for acronym, definition in acronyms.items():
            source_docs_array = list(source_docs)

            if acronym in existing_acronyms:
                # Update existing acronym if definition is different/better
                if existing_acronyms[acronym] != definition:
                    cursor.execute("""
                        UPDATE acronyms
                        SET definition = %s,
                            source_documents = array_cat(source_documents, %s),
                            last_updated_at = now(),
                            usage_count = usage_count + 1
                        WHERE acronym = %s
                    """, (definition, source_docs_array, acronym))
                    updated_count += 1
            else:
                # Insert new acronym
                cursor.execute("""
                    INSERT INTO acronyms (acronym, definition, source_documents, confidence_score)
                    VALUES (%s, %s, %s, %s)
                """, (acronym, definition, source_docs_array, 0.8))  # Higher confidence for extracted acronyms
                inserted_count += 1

        conn.commit()
        print(f"Database update complete: {inserted_count} inserted, {updated_count} updated")

    except Exception as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def main():
    """Main function to update acronyms database."""
    print("Starting acronym extraction and database update...")

    # Extract acronyms from documents
    acronyms, source_docs = extract_acronyms_from_documents()

    if not acronyms:
        print("No acronyms found in documents. Adding some default technical acronyms...")

        # Add some default technical acronyms if none found
        acronyms = {
            "API": "Application Programming Interface",
            "HTTP": "Hypertext Transfer Protocol",
            "REST": "Representational State Transfer",
            "JSON": "JavaScript Object Notation",
            "SQL": "Structured Query Language",
            "DB": "Database",
            "UI": "User Interface",
            "UX": "User Experience",
            "AI": "Artificial Intelligence",
            "ML": "Machine Learning",
            "RAG": "Retrieval-Augmented Generation",
            "LLM": "Large Language Model",
            "NLP": "Natural Language Processing",
            "OCR": "Optical Character Recognition",
            "PDF": "Portable Document Format",
        }
        source_docs = {"default_technical_terms"}

    print(f"Found {len(acronyms)} acronyms from {len(source_docs)} sources")

    # Update the ACRONYM_INDEX.md file
    update_acronym_index_file(acronyms, source_docs)

    # Populate the database
    populate_database(acronyms, source_docs)

    print("Acronym update process completed successfully!")


if __name__ == "__main__":
    main()
