import os
import shutil
import time
from datetime import datetime
from importlib import metadata

import psycopg2
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption

try:
    # Docling >= 2.6 moves PdfPipelineOptions under datamodel.pipeline_options
    from docling.datamodel.pipeline_options import PdfPipelineOptions
except (ImportError, AttributeError):
    # Fall back for older docling releases
    from docling.pipeline.standard_pdf_pipeline import PdfPipelineOptions

from prometheus_client import Counter, Gauge, Histogram, start_http_server

import config
from utils.logging_config import setup_logging

# Suppress PyTorch warnings for CPU-only usage
try:
    pass
except ImportError:
    pass

# Import acronym extraction functionality
try:
    from . import acronym_extractor
except ImportError:
    import acronym_extractor

settings = config.get_settings()
UPLOADS_DIR = settings.uploads_dir
ARCHIVE_DIR = settings.archive_dir

# Prometheus metrics
DOCS_PROCESSED = Counter("docling_documents_processed_total", "Total documents successfully processed")
DOCS_FAILED = Counter("docling_documents_failed_total", "Total documents that failed processing")
CHUNKS_CREATED = Counter("docling_chunks_created_total", "Total chunks created from documents")
LAST_SUCCESS_TS = Gauge("docling_last_success_timestamp", "Unix timestamp of last successful document processing")
PROCESS_DURATION = Histogram("docling_processing_duration_seconds", "Per-document processing duration (seconds)")
PROCESS_CYCLE_DURATION = Histogram("docling_cycle_duration_seconds", "Duration of a processing cycle in seconds")
ACTIVE_FILES = Gauge("docling_active_files_in_cycle", "Number of files discovered in current cycle")

logger = setup_logging(
    program_name="docling_processor",
    log_level=getattr(settings, "log_level", "INFO"),
    log_file=f'/app/logs/docling_processor_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True,
)

EXPECTED_DOCLING_VERSION = "2.60.0"

try:
    installed_docling_version = metadata.version("docling")
except metadata.PackageNotFoundError:
    installed_docling_version = "unknown"

if installed_docling_version != EXPECTED_DOCLING_VERSION:
    logger.warning(
        "Docling version mismatch detected: expected %s but found %s. "
        "Re-evaluate OCR toggles and pipeline configuration before processing documents.",
        EXPECTED_DOCLING_VERSION,
        installed_docling_version,
    )
else:
    logger.info("Docling %s loaded; OCR pipeline configuration verified.", installed_docling_version)

MIN_TEXT_CHAR_THRESHOLD = int(os.environ.get("DOCLING_MIN_TEXT_THRESHOLD", "200"))


def _analyze_pdf_content(file_path: str, filename: str) -> dict:
    """Quickly inspect a PDF to decide whether OCR is likely required."""
    try:
        import fitz  # PyMuPDF
    except Exception as import_err:
        logger.debug(f"PyMuPDF unavailable for {filename}: {import_err}")
        return {"ok": False, "reason": "pymupdf_unavailable"}

    analysis_start = time.time()
    doc = None
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        total_chars = 0
        text_pages = 0
        image_heavy_pages = 0

        for page in doc:
            text = page.get_text("text") or ""
            char_count = len(text.strip())
            if char_count > 0:
                text_pages += 1
            total_chars += char_count
            if char_count < 50 and page.get_images(full=True):
                image_heavy_pages += 1

        avg_chars_per_page = (total_chars / page_count) if page_count else 0
        needs_ocr = total_chars < MIN_TEXT_CHAR_THRESHOLD or (
            avg_chars_per_page < 60 and image_heavy_pages >= max(1, page_count // 3)
        )

        analysis = {
            "ok": True,
            "page_count": page_count,
            "total_chars": total_chars,
            "avg_chars_per_page": round(avg_chars_per_page, 2),
            "text_pages": text_pages,
            "image_heavy_pages": image_heavy_pages,
            "needs_ocr": needs_ocr,
            "duration": round(time.time() - analysis_start, 3),
        }
        logger.info(
            "Pre-analysis for %s: pages=%s, text_chars=%s, avg_chars=%.2f, text_pages=%s, image_pages=%s -> %s",
            filename,
            page_count,
            total_chars,
            avg_chars_per_page,
            text_pages,
            image_heavy_pages,
            "OCR" if needs_ocr else "native text",
        )
        return analysis
    except Exception as analysis_err:
        logger.warning(f"Failed to pre-analyze {filename} before Docling conversion: {analysis_err}")
        return {"ok": False, "reason": "analysis_failed"}
    finally:
        if doc is not None:
            doc.close()


def _build_converter(use_ocr: bool) -> DocumentConverter:
    """Construct a Docling converter with explicit OCR preference."""
    pdf_option = PdfFormatOption(pipeline_options=PdfPipelineOptions(do_ocr=use_ocr))
    return DocumentConverter(format_options={InputFormat.PDF: pdf_option})


try:
    PDF_CONVERTER_NO_OCR = _build_converter(use_ocr=False)
    PDF_CONVERTER_WITH_OCR = _build_converter(use_ocr=True)
except Exception as converter_err:
    logger.warning(f"Failed to initialize optimized Docling converters: {converter_err}")
    # Fallback to default behavior if optimized converters fail
    PDF_CONVERTER_NO_OCR = DocumentConverter()
    PDF_CONVERTER_WITH_OCR = PDF_CONVERTER_NO_OCR


def _extract_primary_text(doc) -> str:
    """Build a textual payload from Docling document content for classification."""
    if not doc:
        return ""
    # Prefer doc.text when populated
    doc_text = getattr(doc, "text", None)
    if isinstance(doc_text, str) and doc_text.strip():
        return doc_text

    parts = []

    # Aggregate textual blocks
    for item in getattr(doc, "texts", []) or []:
        item_text = getattr(item, "text", None)
        if isinstance(item_text, str) and item_text.strip():
            parts.append(item_text.strip())

    # Append table renderings so classifiers see structured content
    for table in getattr(doc, "tables", []) or []:
        table_text = ""
        if hasattr(table, "export_to_markdown"):
            try:
                table_text = table.export_to_markdown(doc=doc)
            except Exception:
                table_text = ""
        if not table_text:
            data = getattr(table, "data", None)
            rows = []
            if data and hasattr(data, "grid"):
                for row in getattr(data, "grid", []):
                    cells = []
                    for cell in row:
                        try:
                            cell_text = cell._get_text(doc=doc)
                        except Exception:
                            cell_text = ""
                        if cell_text:
                            cells.append(cell_text.strip())
                    if cells:
                        rows.append(" | ".join(cells))
            table_text = "\n".join(rows)
        if isinstance(table_text, str) and table_text.strip():
            parts.append(table_text.strip())

    # Include picture captions when available
    for picture in getattr(doc, "pictures", []) or []:
        caption = getattr(picture, "caption", None)
        if isinstance(caption, str) and caption.strip():
            parts.append(caption.strip())
        elif hasattr(caption, "text"):
            caption_text = getattr(caption, "text", "")
            if isinstance(caption_text, str) and caption_text.strip():
                parts.append(caption_text.strip())

    return "\n\n".join(parts)


def _document_needs_ocr(doc) -> bool:
    """Determine whether OCR is required based on extracted content."""
    if not doc:
        return True
    texts = getattr(doc, "texts", []) or []
    if texts:
        text_chars = sum(len(getattr(item, "text", "") or "") for item in texts)
        if text_chars >= MIN_TEXT_CHAR_THRESHOLD:
            return False
    pictures = getattr(doc, "pictures", []) or []
    tables = getattr(doc, "tables", []) or []
    has_visual_only_content = bool(pictures or tables)
    # Retry with OCR when textual content is minimal and visuals dominate
    return has_visual_only_content or not texts


def _convert_document(file_path: str, filename: str):
    """Convert a document using the fastest viable Docling pipeline."""
    analysis = _analyze_pdf_content(file_path, filename)

    conversion_plan = []
    if analysis.get("ok"):
        if analysis["needs_ocr"]:
            conversion_plan.append(("analysis-ocr", PDF_CONVERTER_WITH_OCR))
            conversion_plan.append(("fallback-no-ocr", PDF_CONVERTER_NO_OCR))
        else:
            conversion_plan.append(("analysis-no-ocr", PDF_CONVERTER_NO_OCR))
            conversion_plan.append(("fallback-ocr", PDF_CONVERTER_WITH_OCR))
    else:
        conversion_plan = [
            ("default-no-ocr", PDF_CONVERTER_NO_OCR),
            ("default-ocr", PDF_CONVERTER_WITH_OCR),
        ]
        if analysis.get("reason"):
            logger.debug(f"Pre-analysis unavailable for {filename}: {analysis['reason']}")

    last_error = None
    for label, converter in conversion_plan:
        try:
            logger.info(f"Docling conversion step '{label}' starting for {filename}")
            result = converter.convert(file_path)
            doc = result.document
            if converter is PDF_CONVERTER_NO_OCR and _document_needs_ocr(doc):
                logger.info(f"Post-conversion check indicates OCR still needed for {filename}; retrying with OCR")
                continue
            return result, doc
        except Exception as err:
            logger.error(f"Docling conversion step '{label}' failed for {filename}: {err}")
            last_error = err
    if last_error:
        raise last_error
    raise RuntimeError(f"Docling conversion exhausted without success for {filename}")


def _archive_file(src: str, dest: str) -> None:
    """Move a file into archive, handling cross-device issues gracefully.

    Attempts shutil.move; on failure falls back to copy+remove.
    """
    if not os.path.exists(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        shutil.move(src, dest)
    except Exception:
        # Fallback strategy
        shutil.copy2(src, dest)
        os.remove(src)


def get_db_connection():
    return psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )


def process_pending_files():
    cycle_start = time.time()
    logger.info("Starting Docling processing cycle")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
    try:
        files = [f for f in os.listdir(UPLOADS_DIR) if not f.startswith(".")]
        ACTIVE_FILES.set(len(files))
        logger.info(f"Found {len(files)} files to process: {files}")
        if not files:
            cur.close()
            conn.close()
            PROCESS_CYCLE_DURATION.observe(time.time() - cycle_start)
            return
    except Exception as e:
        logger.error(f"Failed to scan uploads directory: {e}")
        cur.close()
        conn.close()
        return
    for file_index, filename in enumerate(files, 1):
        file_path = os.path.join(UPLOADS_DIR, filename)
        # Skip directories (they may be auxiliary folders like images, archive etc.)
        if os.path.isdir(file_path):
            logger.debug(f"Skipping directory entry: {filename}")
            continue
        logger.info(f"Processing file {file_index}: {filename}")
        doc_start = time.time()
        try:
            result, doc = _convert_document(file_path, filename)
            # DoclingDocument does not have 'chunks', so we check for content
            if not doc or (
                not getattr(doc, "texts", None)
                and not getattr(doc, "tables", None)
                and not getattr(doc, "pictures", None)
            ):
                logger.warning(f"No content extracted from {filename}, archiving")
                archive_target = os.path.join(ARCHIVE_DIR, filename)
                try:
                    _archive_file(file_path, archive_target)
                except Exception as arch_err:
                    logger.error(f"Failed to archive empty-content file {filename}: {arch_err}")
                continue

            # Remove existing document before import
            from pdf_processor.pdf_utils import (
                classify_document_with_ai,
                detect_confidentiality,
                insert_document_chunks_with_categorization,
                insert_document_with_categorization,
                insert_ingestion_metrics,
                remove_existing_document,
            )

            try:
                removed_doc_id = remove_existing_document(conn, filename)
                if removed_doc_id:
                    logger.info(f"Removed existing version of '{filename}' (previous ID: {removed_doc_id})")
            except Exception as e:
                logger.error(f"Failed to remove existing document '{filename}': {e}")

            # Use Docling's metadata for classification, fallback to AI classification if needed
            doc_text = _extract_primary_text(doc)
            privacy_level = detect_confidentiality(doc_text)
            classification = classify_document_with_ai(doc_text, filename)

            # Insert document record
            document_id = insert_document_with_categorization(conn, filename, privacy_level, classification)

            # Build generalized chunks from Docling document structure
            chunks = []
            try:
                # Textual items
                texts = getattr(doc, "texts", []) or []
                for idx, item in enumerate(texts):
                    item_text = getattr(item, "text", "") or ""
                    if not item_text.strip():
                        continue
                    # Determine a page number from provenance if available
                    page_no = None
                    prov = getattr(item, "prov", []) or []
                    if prov:
                        try:
                            page_no = getattr(prov[0], "page_no", None)
                        except Exception:
                            page_no = None
                    chunks.append(
                        {
                            "text": item_text,
                            "metadata": {
                                "label": getattr(item, "label", "text"),
                            },
                            "page_number": page_no or (idx + 1),
                            "chunk_type": str(getattr(item, "label", "text")).lower(),
                        }
                    )

                # Tables
                tables = getattr(doc, "tables", []) or []
                for t_idx, table in enumerate(tables):
                    try:
                        # Export table as markdown for embedding context
                        md = ""
                        if hasattr(table, "export_to_markdown"):
                            try:
                                md = table.export_to_markdown(doc=doc)
                            except Exception:
                                md = ""
                        if not md:
                            # Fallback simple concatenation of cell text if available
                            data = getattr(table, "data", None)
                            rows_text = []
                            if data and hasattr(data, "grid"):
                                for row in getattr(data, "grid", []):
                                    row_cells = []
                                    for cell in row:
                                        cell_text = getattr(cell, "_get_text", lambda **_: "")(doc=doc)
                                        if cell_text:
                                            row_cells.append(cell_text.strip())
                                    if row_cells:
                                        rows_text.append(" | ".join(row_cells))
                            md = "\n".join(rows_text)
                        if md.strip():
                            page_no = None
                            prov = getattr(table, "prov", []) or []
                            if prov:
                                try:
                                    page_no = getattr(prov[0], "page_no", None)
                                except Exception:
                                    page_no = None
                            chunks.append(
                                {
                                    "text": md,
                                    "metadata": {"label": "table"},
                                    "page_number": page_no or (len(chunks) + 1),
                                    "chunk_type": "table",
                                }
                            )
                    except Exception as table_err:
                        logger.debug(f"Failed to process table {t_idx} in {filename}: {table_err}")

                # Pictures / Figures (capture caption text if any)
                pictures = getattr(doc, "pictures", []) or []
                for p_idx, pic in enumerate(pictures):
                    try:
                        caption = ""
                        if hasattr(pic, "caption_text"):
                            try:
                                caption = pic.caption_text(doc) or ""
                            except Exception:
                                caption = ""
                        # If no caption, skip to avoid low-signal embeddings
                        if caption and caption.strip():
                            page_no = None
                            prov = getattr(pic, "prov", []) or []
                            if prov:
                                try:
                                    page_no = getattr(prov[0], "page_no", None)
                                except Exception:
                                    page_no = None
                            chunks.append(
                                {
                                    "text": caption.strip(),
                                    "metadata": {"label": "picture"},
                                    "page_number": page_no or (len(chunks) + 1),
                                    "chunk_type": "picture",
                                }
                            )
                    except Exception as pic_err:
                        logger.debug(f"Failed to process picture {p_idx} in {filename}: {pic_err}")
            except Exception as build_err:
                logger.error(f"Failed building chunks for {filename}: {build_err}")
                chunks = []

            # Insert chunks and embeddings
            metrics = insert_document_chunks_with_categorization(
                conn, chunks, document_id, privacy_level, classification, settings.embedding_model
            )
            # Metrics updates
            DOCS_PROCESSED.inc()
            CHUNKS_CREATED.inc(sum(1 for _ in chunks))
            LAST_SUCCESS_TS.set(time.time())

            # Extract acronyms from document text for ACRONYM_INDEX.md updates
            try:
                full_text = ""
                # Combine all text chunks for acronym extraction
                for chunk in chunks:
                    if chunk.get("text"):
                        full_text += chunk["text"] + " "

                if full_text.strip():
                    extractor = acronym_extractor.AcronymExtractor()
                    new_acronyms = extractor.extract_from_text(full_text, filename)

                    if new_acronyms:
                        logger.info(f"Extracted {len(new_acronyms)} acronyms from {filename}")

                        # Load existing acronyms
                        acronym_file_path = os.path.join(UPLOADS_DIR, "ACRONYM_INDEX.md")
                        existing_acronyms = acronym_extractor.load_existing_acronyms(acronym_file_path)

                        # Merge with new acronyms
                        merged_acronyms = extractor.merge_acronyms(existing_acronyms, new_acronyms)

                        # Save updated acronyms if we have new ones
                        if len(merged_acronyms) > len(existing_acronyms):
                            source_docs = {filename}
                            acronym_extractor.save_acronyms_to_file(merged_acronyms, acronym_file_path, source_docs)
                            logger.info(f"Updated ACRONYM_INDEX.md with {len(merged_acronyms)} total acronyms")

            except Exception as acronym_err:
                logger.warning(f"Acronym extraction failed for {filename}: {acronym_err}")

            # Store ingestion metrics
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None
            page_count = len(chunks) // 10 if chunks else None
            processing_start_time = datetime.now()
            processing_end_time = datetime.now()
            insert_ingestion_metrics(
                conn,
                document_id,
                filename,
                file_size,
                page_count,
                processing_start_time,
                processing_end_time,
                metrics,
                settings.embedding_model,
            )

            duration = time.time() - doc_start
            PROCESS_DURATION.observe(duration)
            logger.info(f"Successfully processed and inserted {filename} in {duration:.2f}s")
            try:
                _archive_file(file_path, os.path.join(ARCHIVE_DIR, filename))
            except Exception as arch_move_err:
                logger.error(f"Archiving move failed for {filename}: {arch_move_err}")
        except Exception as e:
            logger.error(f"Processing failed for {filename}: {e}")
            DOCS_FAILED.inc()
            try:
                _archive_file(file_path, os.path.join(ARCHIVE_DIR, filename))
            except Exception as archive_error:
                logger.error(f"Failed to archive {filename}: {archive_error}")
            continue
    try:
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error closing database connection: {e}")
    PROCESS_CYCLE_DURATION.observe(time.time() - cycle_start)
    logger.info("Docling processing cycle complete")


def main():
    logger.info("Docling Processor starting up (metrics exporter on 0.0.0.0:9110)")
    try:
        start_http_server(9110)
    except Exception as e:
        logger.error(f"Failed starting metrics HTTP server: {e}")

    # Safety check: ensure no conflicting processors are running
    try:
        import subprocess

        result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and "pdf_processor" in result.stdout:
            logger.error("CONFLICT DETECTED: pdf_processor container is running. Stopping to prevent conflicts.")
            logger.error("Please stop pdf_processor before running docling_processor: docker stop pdf_processor")
            return 1
    except Exception as safety_err:
        logger.warning(f"Could not check for conflicting processors: {safety_err}")

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
            time.sleep(10)
    logger.info("Docling Processor shutting down")


if __name__ == "__main__":
    main()
