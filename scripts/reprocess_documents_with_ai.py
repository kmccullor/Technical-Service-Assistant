#!/usr/bin/env python3
"""
Script to reprocess existing documents with AI categorization.

This script will:
1. Find all documents without AI categorization (document_type = 'unknown')
2. Re-extract text from archived PDFs
3. Apply AI classification using the optimized system
4. Update database records with new categorization
5. Regenerate chunks with AI metadata if needed

Usage:
    python scripts/reprocess_documents_with_ai.py [--limit N] [--dry-run]
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Add project root to path
sys.path.append("/app")
sys.path.append(str(PROJECT_ROOT))

from config import get_settings
from pdf_processor.pdf_utils import classify_document_with_ai, detect_confidentiality, extract_text, get_db_connection
from utils.logging_config import setup_logging

# Setup logging
logger = setup_logging(
    program_name="reprocess_ai",
    log_level="INFO",
    log_file=f'logs/reprocess_ai_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
    console_output=True,
)

settings = get_settings()


def get_documents_needing_reprocessing(limit=None):
    """Get documents that need AI categorization (have 'unknown' values)."""
    conn = get_db_connection()
    cur = conn.cursor()

    query = """
        SELECT id, file_name, uploaded_at
        FROM pdf_documents
        WHERE document_type = 'unknown' OR document_type IS NULL
        ORDER BY uploaded_at DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    documents = cur.fetchall()

    cur.close()
    conn.close()

    return documents


LEGACY_ARCHIVE_SEGMENT = os.path.join("uploads", "archive")


def find_pdf_file(file_name):
    """Find the PDF file in archive or uploads directory."""
    candidates = [
        Path(settings.archive_dir) / file_name,
        Path(settings.uploads_dir) / file_name,
        Path(settings.uploads_dir) / "archive" / file_name,  # legacy location
        PROJECT_ROOT / "archive" / file_name,
    ]

    for candidate in candidates:
        if candidate.exists():
            if LEGACY_ARCHIVE_SEGMENT in str(candidate):
                logger.warning("Legacy %s path detected for %s. Consider migrating files.", LEGACY_ARCHIVE_SEGMENT, file_name)
            return str(candidate)

    return None


def update_document_categorization(doc_id, file_name, ai_classification, privacy_level):
    """Update document record with AI categorization."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE pdf_documents SET
                document_type = %s,
                product_name = %s,
                product_version = %s,
                document_category = %s,
                classification_confidence = %s,
                privacy_level = %s,
                ai_metadata = %s
            WHERE id = %s
        """,
            (
                ai_classification.get("document_type", "unknown"),
                ai_classification.get("product_name", "unknown"),
                ai_classification.get("product_version", "unknown"),
                ai_classification.get("document_category", "documentation"),
                ai_classification.get("confidence", 0.0),
                privacy_level,
                str(ai_classification.get("metadata", {})),  # Store as text for now
                doc_id,
            ),
        )

        # Update associated chunks with AI categorization
        cur.execute(
            """
            UPDATE document_chunks SET
                document_type = %s,
                product_name = %s,
                privacy_level = %s
            WHERE document_id = %s
        """,
            (
                ai_classification.get("document_type", "unknown"),
                ai_classification.get("product_name", "unknown"),
                privacy_level,
                doc_id,
            ),
        )

        conn.commit()
        logger.info(f"Updated document ID {doc_id} ({file_name}) with AI categorization")
        logger.info(f"  Type: {ai_classification.get('document_type', 'unknown')}")
        product_name = ai_classification.get("product_name", "unknown")
        product_version = ai_classification.get("product_version", "unknown")
        logger.info("  Product: %s v%s", product_name, product_version)
        logger.info(f"  Privacy: {privacy_level}")
        logger.info(f"  Confidence: {ai_classification.get('confidence', 0.0):.2f}")

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update document {doc_id} ({file_name}): {e}")
        raise
    finally:
        cur.close()
        conn.close()


def reprocess_document(doc_id, file_name, dry_run=False):
    """Reprocess a single document with AI categorization."""
    logger.info(f"Processing document ID {doc_id}: {file_name}")

    # Find the PDF file
    pdf_path = find_pdf_file(file_name)
    if not pdf_path:
        logger.error(f"PDF file not found for {file_name}")
        return False

    logger.info(f"Found PDF at: {pdf_path}")

    try:
        # Extract text
        logger.info(f"Extracting text from {file_name}")
        text = extract_text(pdf_path)

        if not text or len(text.strip()) < 100:
            logger.warning(f"Insufficient text extracted from {file_name} ({len(text)} chars)")
            return False

        logger.info(f"Extracted {len(text)} characters from {file_name}")

        # AI Classification
        logger.info(f"Starting AI classification for {file_name}")
        start_time = time.time()

        ai_classification = classify_document_with_ai(text, file_name)

        classification_time = time.time() - start_time
        logger.info(f"AI classification completed in {classification_time:.2f}s")
        logger.info(f"Result: {ai_classification}")

        # Privacy Detection
        logger.info(f"Detecting privacy level for {file_name}")
        privacy_level = detect_confidentiality(text)
        logger.info(f"Privacy level: {privacy_level}")

        if dry_run:
            logger.info(f"DRY RUN: Would update {file_name} with:")
            logger.info(f"  Type: {ai_classification.get('document_type')}")
            logger.info(
                "  Product: %s v%s",
                ai_classification.get("product_name"),
                ai_classification.get("product_version"),
            )
            logger.info(f"  Privacy: {privacy_level}")
            logger.info(f"  Confidence: {ai_classification.get('confidence', 0.0):.2f}")
            return True

        # Update database
        update_document_categorization(doc_id, file_name, ai_classification, privacy_level)

        return True

    except Exception as e:
        logger.error(f"Failed to reprocess {file_name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Reprocess documents with AI categorization")
    parser.add_argument("--limit", type=int, help="Limit number of documents to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")

    args = parser.parse_args()

    logger.info("=== AI Document Reprocessing Started ===")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Limit: {args.limit or 'No limit'}")

    # Get documents needing reprocessing
    documents = get_documents_needing_reprocessing(args.limit)
    logger.info(f"Found {len(documents)} documents needing AI categorization")

    if not documents:
        logger.info("No documents need reprocessing")
        return

    # Process each document
    success_count = 0
    failed_count = 0

    for doc_id, file_name, uploaded_at in documents:
        logger.info(f"\\n--- Processing {success_count + failed_count + 1}/{len(documents)} ---")

        try:
            if reprocess_document(doc_id, file_name, args.dry_run):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Unexpected error processing {file_name}: {e}")
            failed_count += 1

        # Small delay between documents to prevent overwhelming the system
        time.sleep(2)

    # Summary
    logger.info("\\n=== AI Document Reprocessing Complete ===")
    logger.info(f"Total documents: {len(documents)}")
    logger.info(f"Successfully processed: {success_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Success rate: {(success_count/len(documents)*100):.1f}%")


if __name__ == "__main__":
    main()
