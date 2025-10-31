import os
import shutil
import sys
import time
from datetime import datetime

import psutil  # For memory monitoring

sys.path.append("/app")
from config import get_settings
from pdf_processor.pdf_utils import (
    chunk_images,
    chunk_tables,
    chunk_text,
    classify_document_with_ai,
    detect_confidentiality,
    extract_images,
    extract_tables,
    extract_text,
    get_db_connection,
    insert_document_chunks_with_categorization,
    insert_document_with_categorization,
    insert_ingestion_metrics,
    perform_image_ocr,
    remove_existing_document,
)
from utils.logging_config import setup_logging

settings = get_settings()
UPLOADS_DIR = settings.uploads_dir
ARCHIVE_DIR = settings.archive_dir

# Memory optimization settings
MAX_FILE_SIZE_MB = getattr(settings, "max_pdf_file_size_mb", 50)
MEMORY_CHECK_INTERVAL = getattr(settings, "memory_check_interval", 5)  # Check every N files

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="pdf_processor",
    log_level=getattr(settings, "log_level", "INFO"),
    log_file=f'/app/logs/pdf_processor_{datetime.now().strftime("%Y%m%d")}.log',
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
    """Process pending PDF files with comprehensive logging and error handling."""
    logger.info("=" * 60)
    logger.info("Starting PDF processing cycle")
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
        conn.close()
        return

        # Process each PDF file
    total_files = len(pdf_files)
    for file_index, pdf_filename in enumerate(pdf_files, 1):
        pdf_path = os.path.join(UPLOADS_DIR, pdf_filename)
        file_start_time = time.time()

        logger.info(f"Processing file {file_index}/{total_files}: {pdf_filename}")
        log_system_resources()

        # Memory optimization: force garbage collection between files
        import gc

        gc.collect()

        # Periodic memory monitoring
        if file_index % MEMORY_CHECK_INTERVAL == 0:
            log_system_resources()

        try:
            # Memory check before processing
            file_size = os.path.getsize(pdf_path) / 1024 / 1024  # Size in MB
            if file_size > MAX_FILE_SIZE_MB:
                logger.warning(f"Skipping large file {pdf_filename} ({file_size:.1f}MB) to prevent memory issues")
                shutil.move(pdf_path, os.path.join(ARCHIVE_DIR, pdf_filename))
                continue

            # Extract text with timing
            logger.debug(f"Starting text extraction from: {pdf_filename}")
            text = extract_text(pdf_path)

            # Memory optimization: clear large text variables when not needed
            if len(text) > 1000000:  # 1MB of text
                logger.info(f"Large text extracted ({len(text)} chars), monitoring memory usage")

            # Derive a basic page count heuristic from chunking phase later, but attempt quick estimate:
            # Large PDF handling: we will conditionally skip expensive extraction steps when page count exceeds threshold

            if not text:
                logger.warning(f"No text extracted from {pdf_filename}, archiving")
                shutil.move(pdf_path, os.path.join(ARCHIVE_DIR, pdf_filename))
                continue

            # AI Classification for document categorization
            logger.info(f"Starting AI classification for: {pdf_filename}")
            try:
                ai_classification = classify_document_with_ai(text, pdf_filename)
                logger.info(f"AI classification completed for {pdf_filename}: {ai_classification}")
            except Exception as e:
                logger.error(f"AI classification failed for {pdf_filename}: {e}")
                # Continue with unknown classification
                ai_classification = {
                    "document_type": "unknown",
                    "product_name": "unknown",
                    "product_version": "unknown",
                    "document_category": "documentation",
                    "confidence": 0.0,
                    "metadata": {},
                }

            # Detect privacy level
            logger.info(f"Detecting privacy level for: {pdf_filename}")
            try:
                privacy_level = detect_confidentiality(text)
                logger.info(f"Privacy level detected for {pdf_filename}: {privacy_level}")
            except Exception as e:
                logger.error(f"Privacy detection failed for {pdf_filename}: {e}")
                privacy_level = "unknown"

        except Exception as e:
            logger.error(f"Text extraction failed for {pdf_filename}: {e}")
            try:
                shutil.move(pdf_path, os.path.join(ARCHIVE_DIR, pdf_filename))
                logger.info(f"Archived failed file: {pdf_filename}")
            except Exception as archive_error:
                logger.error(f"Failed to archive {pdf_filename}: {archive_error}")
            continue

        # Remove existing document version before importing new one
        try:
            logger.debug(f"Checking for existing document to remove: {pdf_filename}")
            removed_doc_id = remove_existing_document(conn, pdf_filename)
            if removed_doc_id:
                logger.info(f"Removed existing version of '{pdf_filename}' (previous ID: {removed_doc_id})")
            else:
                logger.debug(f"No existing version found for '{pdf_filename}' - proceeding with fresh import")
        except Exception as e:
            logger.error(f"Failed to remove existing document '{pdf_filename}': {e}")
            # Continue with processing - this might be a new document
            logger.warning(f"Continuing with import despite removal error")

        try:
            # Chunk the text with timing
            logger.debug(f"Starting text chunking for: {pdf_filename}")
            text_chunks, next_index = chunk_text(text, document_name=pdf_filename)
            logger.info(f"Generated {len(text_chunks)} text chunks from {pdf_filename}")

            # Heuristic page estimation: sentences/paragraph based chunking increments a pseudo page number; use next_index
            estimated_pages = max(next_index, 0)
            large_doc = False
            if estimated_pages >= settings.large_doc_page_threshold:
                large_doc = True
                logger.warning(
                    f"Detected large document (estimated pages={estimated_pages} >= threshold={settings.large_doc_page_threshold}) - applying large-doc extraction policy"
                )

            # Table extraction (best-effort, non-fatal)
            table_chunks = []
            if large_doc and settings.skip_tables_for_large_docs:
                logger.info(f"Skipping table extraction for large document {pdf_filename} (pages~{estimated_pages})")
            else:
                try:
                    logger.debug(f"Attempting table extraction for: {pdf_filename}")
                    tables = extract_tables(pdf_path)
                    if tables:
                        table_chunks, next_index = chunk_tables(
                            tables, document_name=pdf_filename, start_index=next_index
                        )
                        # Annotate chunk_type
                        for tc in table_chunks:
                            tc["chunk_type"] = "table"
                        logger.info(f"Extracted {len(table_chunks)} table chunks from {pdf_filename}")
                    else:
                        logger.debug(f"No tables detected in {pdf_filename}")
                except Exception as te:
                    logger.warning(f"Table extraction skipped for {pdf_filename}: {te}")

            # Image extraction (best-effort, non-fatal)
            image_chunks = []
            ocr_chunks = []
            if large_doc and settings.skip_images_for_large_docs:
                logger.info(f"Skipping image extraction for large document {pdf_filename} (pages~{estimated_pages})")
            else:
                try:
                    logger.debug(f"Attempting image extraction for: {pdf_filename}")
                    images_dir = os.path.join(UPLOADS_DIR, "_images_tmp")
                    image_paths = extract_images(pdf_path, images_dir)
                    if image_paths:
                        image_chunks, next_index = chunk_images(
                            image_paths, document_name=pdf_filename, start_index=next_index
                        )
                        for ic in image_chunks:
                            ic["chunk_type"] = "image"
                        logger.info(f"Extracted {len(image_chunks)} image chunks from {pdf_filename}")
                        # OCR (optional)
                        if settings.enable_ocr and not (large_doc and settings.skip_ocr_for_large_docs):
                            try:
                                ocr_chunks = perform_image_ocr(image_paths)
                                logger.info(f"OCR produced {len(ocr_chunks)} chunks for {pdf_filename}")
                            except Exception as ocr_err:
                                logger.warning(f"OCR failed for {pdf_filename}: {ocr_err}")
                        elif large_doc and settings.skip_ocr_for_large_docs:
                            logger.info(f"Skipping OCR for large document {pdf_filename} (pages~{estimated_pages})")
                    else:
                        logger.debug(f"No images detected in {pdf_filename}")
                except Exception as ie:
                    logger.warning(f"Image extraction skipped for {pdf_filename}: {ie}")

            # Merge all chunk types
            chunks = text_chunks + table_chunks + image_chunks + ocr_chunks
            logger.info(
                f"Total merged chunks for {pdf_filename}: {len(chunks)} "
                f"(text={len(text_chunks)}, tables={len(table_chunks)}, images={len(image_chunks)}, ocr={len(ocr_chunks)})"
            )

            if not chunks:
                logger.warning(f"No chunks generated from {pdf_filename}, archiving")
                shutil.move(pdf_path, os.path.join(ARCHIVE_DIR, pdf_filename))
                continue

            # Insert document with AI categorization
            logger.info(f"Inserting document with AI categorization: {pdf_filename}")
            # Enrich classification metadata with large-doc flags (non-destructive merge expectation in insert helper)
            if "metadata" not in ai_classification or not isinstance(ai_classification["metadata"], dict):
                ai_classification["metadata"] = {}
            if large_doc:
                ai_classification["metadata"]["large_doc"] = True
                ai_classification["metadata"]["estimated_pages"] = estimated_pages
                ai_classification["metadata"]["large_doc_extraction_policy"] = {
                    "tables_skipped": settings.skip_tables_for_large_docs,
                    "images_skipped": settings.skip_images_for_large_docs,
                    "ocr_skipped": settings.skip_ocr_for_large_docs,
                    "threshold": settings.large_doc_page_threshold,
                }

            document_id = insert_document_with_categorization(conn, pdf_filename, privacy_level, ai_classification)
            logger.info(f"Document inserted with ID: {document_id}")

            # Process chunks with categorization
            logger.info(f"Processing {len(chunks)} chunks for {pdf_filename}")
            chunks_start_time = datetime.now()
            try:
                metrics = insert_document_chunks_with_categorization(
                    conn, chunks, document_id, privacy_level, ai_classification, settings.embedding_model
                )
                chunks_end_time = datetime.now()
                successful_chunks = metrics.get("inserted_chunks", 0)
                failed_chunks = metrics.get("failed_embeddings", 0)
                logger.info(
                    f"Ingestion metrics for {pdf_filename}: inserted={metrics.get('inserted_chunks')} "
                    f"total_input={metrics.get('total_input_chunks')} dup_skipped={metrics.get('skipped_duplicates')} "
                    f"failed_embed={metrics.get('failed_embeddings')} by_type={metrics.get('by_type')} "
                    f"elapsed={metrics.get('elapsed_seconds')}s"
                )

                # Store metrics in database
                try:
                    file_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else None
                    page_count = len(chunks) // 10 if chunks else None  # Rough estimate
                    insert_ingestion_metrics(
                        conn,
                        document_id,
                        pdf_filename,
                        file_size,
                        page_count,
                        chunks_start_time,
                        chunks_end_time,
                        metrics,
                        settings.embedding_model,
                    )
                except Exception as metrics_error:
                    logger.error(f"Failed to store metrics for {pdf_filename}: {metrics_error}")
            except Exception as e:
                logger.error(f"Failed to process chunks for {pdf_filename}: {e}")
                successful_chunks = 0
                failed_chunks = len(chunks)

        except Exception as e:
            logger.error(f"Text chunking or AI processing failed for {pdf_filename}: {e}")
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

        if failed_chunks > 0:
            logger.warning(f"Some chunks failed for {pdf_filename}: {failed_chunks} failures")

        # Memory optimization: explicit cleanup after each file
        import gc

        gc.collect()
        log_system_resources()

    # Final cleanup and statistics
    try:
        cur.close()
        conn.close()
        logger.debug("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database connection: {e}")

    logger.info(f"Processing cycle complete: processed {total_files} files")
    log_system_resources()


def main():
    """Main processing loop with enhanced logging and error handling."""
    logger.info("PDF Processor starting up")
    logger.info(f"Configuration - Upload dir: {UPLOADS_DIR}, Archive dir: {ARCHIVE_DIR}")

    cycle_count = 0

    while True:
        try:
            cycle_count += 1
            logger.info(f"Starting processing cycle #{cycle_count}")

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

    logger.info("PDF Processor shutting down")


if __name__ == "__main__":
    main()
