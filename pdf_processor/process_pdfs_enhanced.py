import os
import shutil
import sys
import time
from datetime import datetime

import psutil  # For memory monitoring

sys.path.append("/app")
from config import get_settings
from pdf_processor.pdf_utils_enhanced import (
    calculate_file_hash,
    chunk_text_semantic,
    classify_document_with_ai,
    detect_confidentiality,
    extract_document_metadata,
    extract_text,
    get_db_connection,
    insert_document_chunks_comprehensive,
    insert_document_comprehensive,
    remove_existing_document,
)
from utils.logging_config import setup_logging

settings = get_settings()
UPLOADS_DIR = settings.uploads_dir
ARCHIVE_DIR = settings.archive_dir

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="pdf_processor_enhanced",
    log_level=getattr(settings, "log_level", "INFO"),
    log_file=f'/app/logs/pdf_processor_enhanced_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True,
)


def log_system_resources():
    """Log current system resource usage for monitoring."""
    try:
        import psutil

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        logger.info(
            f"System Resources - Memory: {memory.percent}% used ({memory.used // 1024 // 1024}MB/{memory.total // 1024 // 1024}MB), Disk: {disk.percent}% used"
        )
    except ImportError:
        logger.debug("psutil not available for system monitoring")
    except Exception as e:
        logger.warning(f"Failed to get system resources: {e}")


def process_pending_files():
    """Process pending PDF files with comprehensive metadata extraction and pgvector schema."""
    logger.info("=" * 60)
    logger.info("Starting enhanced PDF processing cycle with pgvector schema")
    log_system_resources()

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        logger.debug("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return

    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
        logger.info(f"Created archive directory: {ARCHIVE_DIR}")

    try:
        pdf_files = [f for f in os.listdir(UPLOADS_DIR) if f.lower().endswith(".pdf")]
        logger.info(f"Found {len(pdf_files)} PDF files to process: {pdf_files}")

        if not pdf_files:
            logger.debug("No new PDF files to process")
            cur.close()
            conn.close()
            return

    except Exception as e:
        logger.error(f"Failed to scan uploads directory: {e}")
        cur.close()
        conn.close()
        return

    # Process each PDF file with enhanced metadata extraction
    total_files = len(pdf_files)
    for file_index, pdf_filename in enumerate(pdf_files, 1):
        pdf_path = os.path.join(UPLOADS_DIR, pdf_filename)
        file_start_time = time.time()

        logger.info(f"Processing file {file_index}/{total_files}: {pdf_filename}")
        log_system_resources()

        try:
            # Calculate file hash for deduplication
            file_hash = calculate_file_hash(pdf_path)
            logger.debug(f"File hash: {file_hash[:16]}... for {pdf_filename}")

            # Check if document already exists
            try:
                removed_doc_id = remove_existing_document(conn, file_hash, pdf_filename)
                if removed_doc_id:
                    logger.info(f"Removed existing version of '{pdf_filename}' (previous ID: {removed_doc_id})")
                else:
                    logger.debug(f"No existing version found for '{pdf_filename}' - proceeding with fresh import")
            except Exception as e:
                logger.error(f"Failed to check/remove existing document '{pdf_filename}': {e}")
                # Continue with processing - this might be a new document
                logger.warning(f"Continuing with import despite deduplication error")

            # Extract text with timing
            logger.debug(f"Starting text extraction from: {pdf_filename}")
            text = extract_text(pdf_path)

            # Extract and store terminology (acronyms, synonyms)
            logger.info(f"Extracting terminology from: {pdf_filename}")
            try:
                from utils.terminology_manager import extract_and_store_terminology

                terminology_counts = extract_and_store_terminology(text, pdf_filename)
                logger.info(f"Terminology extraction completed: {terminology_counts}")
            except Exception as term_error:
                logger.warning(f"Terminology extraction failed for {pdf_filename}: {term_error}")
                terminology_counts = {"acronyms": 0, "synonyms": 0, "relationships": 0}

            if not text:
                logger.warning(f"No text extracted from {pdf_filename}, archiving")
                shutil.move(pdf_path, os.path.join(ARCHIVE_DIR, pdf_filename))
                continue

            logger.info(f"Extracted {len(text)} characters from {pdf_filename}")

            # Extract comprehensive document metadata
            logger.info(f"Extracting document metadata for: {pdf_filename}")
            try:
                extracted_metadata = extract_document_metadata(text, pdf_filename)
                logger.info(f"Metadata extraction completed - Title: {extracted_metadata.get('title', 'None')[:50]}...")
                logger.debug(f"Full metadata: {extracted_metadata}")
            except Exception as e:
                logger.error(f"Metadata extraction failed for {pdf_filename}: {e}")
                extracted_metadata = {}

            # AI Classification for document categorization
            logger.info(f"Starting AI classification for: {pdf_filename}")
            try:
                ai_classification = classify_document_with_ai(text, pdf_filename)
                logger.info(f"AI classification completed for {pdf_filename}")
                logger.info(f"  Type: {ai_classification.get('document_type', 'unknown')}")
                logger.info(
                    f"  Product: {ai_classification.get('product_name', 'unknown')} v{ai_classification.get('product_version', 'unknown')}"
                )
                logger.info(f"  Confidence: {ai_classification.get('confidence', 0.0):.2f}")
            except Exception as e:
                logger.error(f"AI classification failed for {pdf_filename}: {e}")
                # Continue with fallback classification
                ai_classification = {
                    "document_type": "unknown",
                    "product_name": "unknown",
                    "product_version": "unknown",
                    "document_category": "documentation",
                    "confidence": 0.0,
                    "metadata": {"classification_method": "fallback_due_to_error"},
                }

            # Detect privacy level
            logger.info(f"Detecting privacy level for: {pdf_filename}")
            try:
                privacy_level = detect_confidentiality(text)
                logger.info(f"Privacy level detected for {pdf_filename}: {privacy_level}")
            except Exception as e:
                logger.error(f"Privacy detection failed for {pdf_filename}: {e}")
                privacy_level = "public"  # Default to public for safety

        except Exception as e:
            logger.error(f"Text extraction or metadata processing failed for {pdf_filename}: {e}")
            try:
                shutil.move(pdf_path, os.path.join(ARCHIVE_DIR, pdf_filename))
                logger.info(f"Archived failed file: {pdf_filename}")
            except Exception as archive_error:
                logger.error(f"Failed to archive {pdf_filename}: {archive_error}")
            continue

        try:
            # Enhanced semantic chunking
            logger.debug(f"Starting semantic chunking for: {pdf_filename}")
            chunks = chunk_text_semantic(text, document_name=pdf_filename, max_chunk_size=1000)
            logger.info(f"Generated {len(chunks)} semantic chunks from {pdf_filename}")

            if not chunks:
                logger.warning(f"No chunks generated from {pdf_filename}, archiving")
                shutil.move(pdf_path, os.path.join(ARCHIVE_DIR, pdf_filename))
                continue

            # Insert comprehensive document with full metadata
            logger.info(f"Inserting comprehensive document record: {pdf_filename}")
            document_id = insert_document_comprehensive(
                conn, pdf_path, privacy_level, ai_classification, extracted_metadata
            )
            logger.info(f"Document inserted with ID: {document_id}")

            # Process chunks with enhanced schema
            logger.info(f"Processing {len(chunks)} semantic chunks for {pdf_filename}")
            try:
                insert_document_chunks_comprehensive(conn, chunks, document_id)
                successful_chunks = len(chunks)
                failed_chunks = 0
                logger.info(f"Successfully processed all {successful_chunks} chunks for {pdf_filename}")

                # Verify embedding coverage
                cur.execute(
                    """
                    SELECT COUNT(*) as total_chunks,
                           COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as embedded_chunks
                    FROM document_chunks WHERE document_id = %s;
                """,
                    (document_id,),
                )
                result = cur.fetchone()
                if result:
                    total, embedded = result
                    coverage = (embedded / total * 100) if total > 0 else 0
                    logger.info(f"Embedding coverage: {embedded}/{total} chunks ({coverage:.1f}%)")

                    if coverage < 100:
                        logger.warning(f"Incomplete embedding coverage for {pdf_filename}")

            except Exception as e:
                logger.error(f"Failed to process chunks for {pdf_filename}: {e}")
                successful_chunks = 0
                failed_chunks = len(chunks)
                # Update document status to failed
                try:
                    cur.execute(
                        """
                        UPDATE documents
                        SET processing_status = 'failed'
                        WHERE id = %s;
                    """,
                        (document_id,),
                    )
                    conn.commit()
                except Exception as status_error:
                    logger.error(f"Failed to update document status: {status_error}")

        except Exception as e:
            logger.error(f"Chunking or database processing failed for {pdf_filename}: {e}")
            try:
                shutil.move(pdf_path, os.path.join(ARCHIVE_DIR, pdf_filename))
                logger.info(f"Archived failed file: {pdf_filename}")
            except Exception as archive_error:
                logger.error(f"Failed to archive {pdf_filename}: {archive_error}")
            continue

        # Archive the processed PDF
        try:
            archive_path = os.path.join(ARCHIVE_DIR, pdf_filename)
            shutil.move(pdf_path, archive_path)
            logger.info(f"Archived {pdf_filename} to {archive_path}")
        except Exception as e:
            logger.error(f"Failed to archive {pdf_filename}: {e}")

        # Log completion statistics
        file_time = time.time() - file_start_time
        success_rate = (successful_chunks / len(chunks)) * 100 if chunks else 0

        logger.info(f"File processing complete: {pdf_filename}")
        logger.info(
            f"Results: {successful_chunks}/{len(chunks)} chunks successful ({success_rate:.1f}%), Time: {file_time:.2f}s"
        )
        logger.info(f"Document metadata fields populated: {len([k for k, v in extracted_metadata.items() if v])}")

        if failed_chunks > 0:
            logger.warning(f"Some chunks failed for {pdf_filename}: {failed_chunks} failures")

    # Final cleanup and database statistics
    try:
        # Get comprehensive database statistics
        logger.info("Gathering database statistics...")

        cur.execute(
            """
            SELECT
                COUNT(*) as total_documents,
                COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_docs,
                COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_docs,
                COUNT(CASE WHEN privacy_level = 'private' THEN 1 END) as private_docs
            FROM documents;
        """
        )
        doc_stats = cur.fetchone()

        cur.execute(
            """
            SELECT
                COUNT(*) as total_chunks,
                COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as embedded_chunks,
                AVG(content_length) as avg_chunk_length
            FROM document_chunks;
        """
        )
        chunk_stats = cur.fetchone()

        if doc_stats and chunk_stats:
            total_docs, completed_docs, failed_docs, private_docs = doc_stats
            total_chunks, embedded_chunks, avg_length = chunk_stats

            logger.info("=== DATABASE STATISTICS ===")
            logger.info(
                f"Documents: {total_docs} total, {completed_docs} completed, {failed_docs} failed, {private_docs} private"
            )
            logger.info(
                f"Chunks: {total_chunks} total, {embedded_chunks} with embeddings ({(embedded_chunks/total_chunks*100) if total_chunks > 0 else 0:.1f}%)"
            )
            logger.info(f"Average chunk length: {avg_length:.0f} characters" if avg_length else "N/A")

        cur.close()
        conn.close()
        logger.debug("Database connection closed")
    except Exception as e:
        logger.error(f"Error gathering statistics or closing database connection: {e}")

    logger.info(f"Enhanced processing cycle complete: processed {total_files} files")
    log_system_resources()


def main():
    """Main processing loop with enhanced logging and error handling."""
    logger.info("Enhanced PDF Processor starting up with pgvector schema")
    logger.info(f"Configuration - Upload dir: {UPLOADS_DIR}, Archive dir: {ARCHIVE_DIR}")
    logger.info(f"Features: Semantic chunking, comprehensive metadata extraction, pgvector optimized schema")

    cycle_count = 0

    while True:
        try:
            cycle_count += 1
            logger.info(f"Starting enhanced processing cycle #{cycle_count}")

            process_pending_files()

            sleep_duration = getattr(settings, "poll_interval_seconds", 60)
            logger.info(f"Cycle #{cycle_count} complete. Sleeping for {sleep_duration} seconds...")
            time.sleep(sleep_duration)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            logger.info("Continuing after error...")
            time.sleep(10)  # Brief pause before retrying

    logger.info("Enhanced PDF Processor shutting down")


if __name__ == "__main__":
    main()
