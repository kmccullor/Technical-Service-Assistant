#!/usr/bin/env python3
"""
Archive Reprocessing Script

This script moves archived PDF documents back to the uploads directory
for reprocessing with the new privacy classification system.
"""

import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Add app path for imports
sys.path.append("/app")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup basic logging without the containerized logging system
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'archive_reprocessor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
    ],
)
logger = logging.getLogger("archive_reprocessor")

# Try to import settings, fall back to manual config if needed
try:
    from config import get_settings

    settings = get_settings()
    UPLOADS_DIR = settings.uploads_dir
    ARCHIVE_DIR = settings.archive_dir
except ImportError:
    logger.warning("Could not import settings, using default paths")
    # Default paths for local execution
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    UPLOADS_DIR = os.path.join(project_root, "uploads")
    ARCHIVE_DIR = os.path.join(project_root, "uploads", "archive")


def get_archived_documents():
    """Get list of all PDF documents in the archive directory."""
    try:
        archive_path = Path(ARCHIVE_DIR)
        if not archive_path.exists():
            logger.warning(f"Archive directory does not exist: {ARCHIVE_DIR}")
            return []

        pdf_files = [f for f in archive_path.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]

        logger.info(f"Found {len(pdf_files)} PDF files in archive directory")
        return pdf_files

    except Exception as e:
        logger.error(f"Error scanning archive directory: {e}")
        return []


def get_db_config():
    """Get database configuration, trying multiple methods."""
    try:
        from config import get_settings

        settings = get_settings()
        return {
            "dbname": settings.db_name,
            "user": settings.db_user,
            "password": settings.db_password,
            "host": settings.db_host,
            "port": settings.db_port,
        }
    except (ImportError, AttributeError, Exception):  # broad fallback with logging
        logger.warning("Falling back to environment variable database configuration")
        return {
            "dbname": os.environ.get("DB_NAME", "vector_db"),
            "user": os.environ.get("DB_USER", "postgres"),
            "password": os.environ.get("DB_PASSWORD", "postgres"),
            "host": os.environ.get("DB_HOST", "localhost"),  # localhost for Docker port mapping
            "port": os.environ.get("DB_PORT", "5432"),
        }


def backup_current_database():
    """Create a backup of current database state before reprocessing."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        db_cfg = get_db_config()
        conn = psycopg2.connect(
            dbname=db_cfg["dbname"],
            user=db_cfg["user"],
            password=db_cfg["password"],
            host=db_cfg["host"],
            port=db_cfg["port"],
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get current document and chunk counts
        cursor.execute("SELECT COUNT(*) AS count FROM pdf_documents")
        row = cursor.fetchone()
        doc_count = row["count"] if row and "count" in row else 0

        cursor.execute("SELECT COUNT(*) AS count FROM document_chunks")
        row = cursor.fetchone()
        chunk_count = row["count"] if row and "count" in row else 0

        # Get privacy level distribution
        cursor.execute(
            """
            SELECT privacy_level, COUNT(*) AS count
            FROM pdf_documents
            GROUP BY privacy_level
            """
        )
        privacy_dist_rows = cursor.fetchall() or []
        privacy_dist = {r["privacy_level"]: r["count"] for r in privacy_dist_rows if r.get("privacy_level") is not None}

        cursor.close()
        conn.close()

        logger.info("Database state before reprocessing:")
        logger.info(f"  - Documents: {doc_count}")
        logger.info(f"  - Chunks: {chunk_count}")
        logger.info(f"  - Privacy distribution: {privacy_dist}")

        return {
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "privacy_distribution": privacy_dist,
        }

    except Exception as e:
        logger.error(f"Failed to backup database state: {e}")
        return None


def move_files_for_reprocessing(pdf_files, batch_size=5, delay_between_batches=30):
    """
    Move archived PDF files back to uploads directory for reprocessing.

    Args:
        pdf_files: List of PDF file paths to reprocess
        batch_size: Number of files to process in each batch
        delay_between_batches: Seconds to wait between batches
    """
    uploads_path = Path(UPLOADS_DIR)

    if not uploads_path.exists():
        logger.error(f"Uploads directory does not exist: {UPLOADS_DIR}")
        return False

    total_files = len(pdf_files)
    processed = 0
    failed = 0

    logger.info(f"Starting reprocessing of {total_files} files in batches of {batch_size}")

    # Process files in batches to avoid overwhelming the processor
    for i in range(0, total_files, batch_size):
        batch = pdf_files[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_files + batch_size - 1) // batch_size

        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)")

        for pdf_file in batch:
            try:
                # Generate unique filename to avoid conflicts
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                original_name = pdf_file.stem
                new_name = f"{original_name}_reprocess_{timestamp}.pdf"
                destination = uploads_path / new_name

                # Copy file to uploads directory (keep original in archive)
                shutil.copy2(pdf_file, destination)

                logger.info(f"Queued for reprocessing: {pdf_file.name} -> {new_name}")
                processed += 1

                # Small delay between individual files
                time.sleep(1)

            except Exception as e:
                logger.error(f"Failed to queue {pdf_file.name} for reprocessing: {e}")
                failed += 1

        # Wait between batches to allow processor to handle current batch
        if i + batch_size < total_files:
            logger.info(f"Waiting {delay_between_batches} seconds before next batch...")
            time.sleep(delay_between_batches)

    logger.info(f"Reprocessing queue complete:")
    logger.info(f"  - Successfully queued: {processed}")
    logger.info(f"  - Failed to queue: {failed}")
    logger.info(f"  - Success rate: {(processed/total_files*100):.1f}%")

    return failed == 0


def monitor_processing_progress(expected_count, max_wait_minutes=60):
    """
    Monitor the PDF processor's progress on reprocessing documents.

    Args:
        expected_count: Number of documents expected to be processed
        max_wait_minutes: Maximum time to wait for processing completion
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60

        logger.info(f"Monitoring processing progress for up to {max_wait_minutes} minutes...")

        while time.time() - start_time < max_wait_seconds:
            try:
                db_cfg = get_db_config()
                conn = psycopg2.connect(
                    dbname=db_cfg["dbname"],
                    user=db_cfg["user"],
                    password=db_cfg["password"],
                    host=db_cfg["host"],
                    port=db_cfg["port"],
                )

                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Check uploads directory for remaining files
                uploads_path = Path(UPLOADS_DIR)
                remaining_files = len([f for f in uploads_path.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"])

                # Get current database stats
                cursor.execute("SELECT COUNT(*) AS count FROM pdf_documents WHERE file_name LIKE '%_reprocess_%'")
                row = cursor.fetchone()
                processed_docs = row["count"] if row and "count" in row else 0

                cursor.execute(
                    """
                    SELECT privacy_level, COUNT(*) AS count
                    FROM pdf_documents
                    WHERE file_name LIKE '%_reprocess_%'
                    GROUP BY privacy_level
                    """
                )
                privacy_rows = cursor.fetchall() or []
                privacy_stats = {
                    r["privacy_level"]: r["count"] for r in privacy_rows if r.get("privacy_level") is not None
                }

                cursor.close()
                conn.close()

                logger.info(f"Progress update:")
                logger.info(f"  - Files remaining in uploads: {remaining_files}")
                logger.info(f"  - Documents processed: {processed_docs}/{expected_count}")
                logger.info(f"  - Privacy classification: {privacy_stats}")

                if remaining_files == 0 and processed_docs >= expected_count:
                    logger.info("✅ All documents have been reprocessed!")
                    return True

                # Wait before next check
                time.sleep(30)

            except Exception as e:
                logger.warning(f"Error checking progress: {e}")
                time.sleep(10)

        logger.warning(f"Monitoring timeout reached after {max_wait_minutes} minutes")
        return False

    except Exception as e:
        logger.error(f"Failed to monitor processing: {e}")
        return False


def generate_reprocessing_report():
    """Generate a report on the reprocessing results."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        db_cfg = get_db_config()
        conn = psycopg2.connect(
            dbname=db_cfg["dbname"],
            user=db_cfg["user"],
            password=db_cfg["password"],
            host=db_cfg["host"],
            port=db_cfg["port"],
        )

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get reprocessed documents stats
        cursor.execute(
            """
            SELECT
                privacy_level,
                COUNT(*) as document_count,
                AVG(LENGTH(file_name)) as avg_filename_length
            FROM pdf_documents
            WHERE file_name LIKE '%_reprocess_%'
            GROUP BY privacy_level
        """
        )
        reprocessed_stats = cursor.fetchall()

        # Get chunk stats for reprocessed documents
        cursor.execute(
            """
            SELECT
                c.privacy_level,
                COUNT(*) as chunk_count,
                AVG(LENGTH(c.content)) as avg_chunk_size
            FROM document_chunks c
            JOIN pdf_documents d ON c.document_id = d.id
            WHERE d.file_name LIKE '%_reprocess_%'
            GROUP BY c.privacy_level
        """
        )
        chunk_stats = cursor.fetchall()

        # Get total stats
        cursor.execute("SELECT COUNT(*) AS count FROM pdf_documents")
        row = cursor.fetchone()
        total_docs = row["count"] if row and "count" in row else 0

        cursor.execute("SELECT COUNT(*) AS count FROM document_chunks")
        row = cursor.fetchone()
        total_chunks = row["count"] if row and "count" in row else 0

        cursor.close()
        conn.close()

        # Generate report
        logger.info("=" * 60)
        logger.info("REPROCESSING REPORT")
        logger.info("=" * 60)

        logger.info(f"Total documents in system: {total_docs}")
        logger.info(f"Total chunks in system: {total_chunks}")

        logger.info("\nReprocessed Documents by Privacy Level:")
        for stat in reprocessed_stats:
            logger.info(f"  - {stat['privacy_level'].upper()}: {stat['document_count']} documents")

        logger.info("\nReprocessed Chunks by Privacy Level:")
        for stat in chunk_stats:
            avg_size = stat["avg_chunk_size"]
            logger.info(
                "  - %s: %s chunks (avg size: %.0f chars)",
                stat["privacy_level"].upper(),
                stat["chunk_count"],
                avg_size,
            )

        # Privacy distribution analysis
        private_docs = sum(stat["document_count"] for stat in reprocessed_stats if stat["privacy_level"] == "private")
        public_docs = sum(stat["document_count"] for stat in reprocessed_stats if stat["privacy_level"] == "public")
        total_reprocessed = private_docs + public_docs

        if total_reprocessed > 0:
            private_percentage = (private_docs / total_reprocessed) * 100
            public_percentage = (public_docs / total_reprocessed) * 100

            logger.info(f"\nPrivacy Classification Results:")
            logger.info(f"  - Private/Confidential: {private_docs} ({private_percentage:.1f}%)")
            logger.info(f"  - Public: {public_docs} ({public_percentage:.1f}%)")

        logger.info("=" * 60)

        return {
            "reprocessed_stats": reprocessed_stats,
            "chunk_stats": chunk_stats,
            "total_documents": total_docs,
            "total_chunks": total_chunks,
        }

    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        return None


def main():
    """Main function to orchestrate the reprocessing."""
    logger.info("Starting archive reprocessing with privacy classification")
    logger.info("=" * 60)

    try:
        # Step 1: Get archived documents
        pdf_files = get_archived_documents()
        if not pdf_files:
            logger.warning("No PDF files found in archive. Nothing to reprocess.")
            return True

        # Step 2: Backup current database state
        logger.info("Creating database state backup...")
        backup_info = backup_current_database()

        # Step 3: Ask for user confirmation
        print(f"\n📋 Found {len(pdf_files)} PDF documents to reprocess")
        print("🔄 This will:")
        print("   - Copy archived PDFs back to uploads directory")
        print("   - Trigger automatic reprocessing with privacy classification")
        print("   - Generate new privacy-classified database entries")

        if backup_info:
            print(f"\n📊 Current database state:")
            print(f"   - Documents: {backup_info['document_count']}")
            print(f"   - Chunks: {backup_info['chunk_count']}")
            print(f"   - Privacy distribution: {backup_info['privacy_distribution']}")

        response = input("\n❓ Proceed with reprocessing? (y/N): ")
        if not response.lower().startswith("y"):
            logger.info("Reprocessing cancelled by user")
            return True

        # Step 4: Move files for reprocessing
        logger.info("Moving files to uploads directory for reprocessing...")
        success = move_files_for_reprocessing(pdf_files)

        if not success:
            logger.error("Failed to queue all files for reprocessing")
            return False

        # Step 5: Monitor processing (optional)
        response = input("\n❓ Monitor processing progress? (y/N): ")
        if response.lower().startswith("y"):
            monitor_processing_progress(len(pdf_files))

        # Step 6: Generate final report
        logger.info("Generating reprocessing report...")
        generate_reprocessing_report()

        logger.info("Archive reprocessing completed successfully! 🎉")
        return True

    except KeyboardInterrupt:
        logger.info("Reprocessing interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Reprocessing failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
