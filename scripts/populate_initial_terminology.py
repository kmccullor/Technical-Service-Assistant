#!/usr/bin/env python3
"""
Script to populate initial terminology data (acronyms and synonyms) into the database.

This script extracts terminology from existing documents and populates the new
terminology tables for enhanced chat prompts.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import get_settings
from utils.logging_config import setup_logging
from utils.terminology_manager import TerminologyManager

logger = setup_logging(program_name="populate_terminology")


def populate_initial_terminology():
    """Extract terminology from existing documents in the uploads directory."""
    settings = get_settings()
    terminology_manager = TerminologyManager()

    uploads_dir = settings.uploads_dir

    if not os.path.exists(uploads_dir):
        logger.error(f"Uploads directory does not exist: {uploads_dir}")
        return

    # Get list of PDF files
    pdf_files = [f for f in os.listdir(uploads_dir) if f.lower().endswith(".pdf")]

    if not pdf_files:
        logger.warning("No PDF files found in uploads directory")
        return

    logger.info(f"Found {len(pdf_files)} PDF files to process for terminology extraction")

    total_stats = {"acronyms": 0, "synonyms": 0, "relationships": 0}

    for pdf_filename in pdf_files:
        pdf_path = os.path.join(uploads_dir, pdf_filename)
        logger.info(f"Processing {pdf_filename} for terminology...")

        try:
            # Extract text
            from pdf_processor.pdf_utils_enhanced import extract_text

            text = extract_text(pdf_path)

            if not text or len(text.strip()) < 100:
                logger.warning(f"Insufficient text extracted from {pdf_filename}, skipping")
                continue

            # Extract and store terminology
            stats = terminology_manager.extract_and_store_terminology(text, pdf_filename)
            logger.info(f"Extracted from {pdf_filename}: {stats}")

            for key in total_stats:
                total_stats[key] += stats.get(key, 0)

        except Exception as e:
            logger.error(f"Failed to process {pdf_filename}: {e}")

    logger.info(f"Terminology population completed. Total: {total_stats}")

    # Add some manual high-confidence entries
    add_manual_terminology(terminology_manager)

    terminology_manager.close()


def add_manual_terminology(manager: TerminologyManager):
    """Add manually curated high-confidence terminology entries."""
    logger.info("Adding manual terminology entries...")

    manual_acronyms = [
        ("RNI", "Regional Network Interface", ["RNI System Administration Guide.pdf", "RNI Installation Guide.pdf"]),
        ("AMI", "Advanced Metering Infrastructure", ["AMI Overview.pdf"]),
        ("API", "Application Programming Interface", ["API Reference Guide.pdf"]),
        ("HSM", "Hardware Security Module", ["HSM Installation Guide.pdf"]),
        ("LDAP", "Lightweight Directory Access Protocol", ["Active Directory Integration Guide.pdf"]),
        ("DNS", "Domain Name System", ["Network Configuration Guide.pdf"]),
        ("HTTP", "Hypertext Transfer Protocol", ["Web Services Guide.pdf"]),
        ("SQL", "Structured Query Language", ["Database Administration Guide.pdf"]),
    ]

    manual_synonyms = [
        ("RNI", "regional network interface", "product"),
        ("RNI", "rni system", "product"),
        ("AMI", "advanced metering infrastructure", "product"),
        ("AMI", "smart metering", "product"),
        ("troubleshoot", "diagnose", "technical"),
        ("troubleshoot", "debug", "technical"),
        ("configure", "setup", "technical"),
        ("configure", "initialize", "technical"),
        ("install", "deploy", "technical"),
        ("install", "implement", "technical"),
    ]

    try:
        conn = manager._get_db_connection()
        cur = conn.cursor()

        # Add manual acronyms
        for acronym, definition, sources in manual_acronyms:
            cur.execute(
                """
                INSERT INTO acronyms (acronym, definition, source_documents, confidence_score, is_verified)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (acronym) DO UPDATE SET
                    definition = EXCLUDED.definition,
                    source_documents = array_cat(acronyms.source_documents, EXCLUDED.source_documents),
                    confidence_score = GREATEST(acronyms.confidence_score, EXCLUDED.confidence_score),
                    is_verified = true,
                    last_updated_at = now()
                """,
                (acronym, definition, sources, 0.9, True),
            )

        # Add manual synonyms
        for term, synonym, term_type in manual_synonyms:
            cur.execute(
                """
                INSERT INTO synonyms (term, synonym, term_type, confidence_score, is_verified)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (term, synonym, term_type) DO UPDATE SET
                    confidence_score = GREATEST(synonyms.confidence_score, EXCLUDED.confidence_score),
                    is_verified = true,
                    last_updated_at = now()
                """,
                (term, synonym, term_type, 0.8, True),
            )

        conn.commit()
        cur.close()

        logger.info(f"Added {len(manual_acronyms)} manual acronyms and {len(manual_synonyms)} manual synonyms")

    except Exception as e:
        logger.error(f"Failed to add manual terminology: {e}")


if __name__ == "__main__":
    populate_initial_terminology()
