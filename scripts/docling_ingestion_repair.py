#!/usr/bin/env python3
"""Docling ingestion repair & health check utility.

Checks:
 1. Zero-chunk documents (Docling)
 2. Documents missing from DB but present in archive/uploads
 3. Success rate anomalies in document_ingestion_metrics (< threshold)

Repairs:
  - Deletes zero-chunk document rows & restores files from archive
  - Moves missing files back to uploads

Usage:
  python scripts/docling_ingestion_repair.py --db-host pgvector --db-name vector_db --repair
"""
import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Tuple
import psycopg2

DEFAULT_ARCHIVE_SUBDIR = "archive"

@dataclass
class IngestionIssue:
    category: str
    description: str
    details: str

def connect(db_host: str, db_name: str, db_user: str, db_password: str, db_port: int):
    return psycopg2.connect(
        host=db_host,
        dbname=db_name,
        user=db_user,
        password=db_password,
        port=db_port,
    )

def fetch_zero_chunk_docs(conn) -> List[Tuple[int, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.file_name
            FROM documents d
            LEFT JOIN document_chunks c ON d.id = c.document_id
            WHERE d.file_name LIKE '%.%'
            GROUP BY d.id
            HAVING COUNT(c.id) = 0;
            """
        )
        return cur.fetchall()

def fetch_metrics_anomalies(conn, min_success_rate: float) -> List[Tuple[str, float]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT file_name, success_rate
            FROM document_ingestion_metrics
            WHERE success_rate IS NOT NULL AND success_rate < %s
            ORDER BY id DESC
            LIMIT 50;
            """,
            (min_success_rate,),
        )
        return cur.fetchall()

def delete_document(conn, doc_id: int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id=%s;", (doc_id,))

def restore_file(uploads_dir: str, file_name: str):
    archive_path = os.path.join(uploads_dir, DEFAULT_ARCHIVE_SUBDIR, file_name)
    if os.path.exists(archive_path):
        dest_path = os.path.join(uploads_dir, file_name)
        if not os.path.exists(dest_path):
            os.rename(archive_path, dest_path)
            return True, f"Restored {file_name}"
        return False, f"Already present in uploads: {file_name}"
    return False, f"Archive copy not found: {file_name}"

def main():
    parser = argparse.ArgumentParser(description="Docling ingestion health & repair utility")
    parser.add_argument("--db-host", default=os.getenv("DB_HOST", "pgvector"))
    parser.add_argument("--db-port", type=int, default=int(os.getenv("DB_PORT", "5432")))
    parser.add_argument("--db-name", default=os.getenv("DB_NAME", "vector_db"))
    parser.add_argument("--db-user", default=os.getenv("DB_USER", "postgres"))
    parser.add_argument("--db-password", default=os.getenv("DB_PASSWORD", "postgres"))
    parser.add_argument("--uploads-dir", default=os.getenv("UPLOADS_DIR", "uploads"))
    parser.add_argument("--min-success-rate", type=float, default=0.6)
    parser.add_argument("--repair", action="store_true", help="Apply repairs where possible")
    args = parser.parse_args()

    issues: List[IngestionIssue] = []
    try:
        conn = connect(args.db_host, args.db_name, args.db_user, args.db_password, args.db_port)
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}", file=sys.stderr)
        return 2

    try:
        zero_chunk = fetch_zero_chunk_docs(conn)
        if zero_chunk:
            for doc_id, fname in zero_chunk:
                issues.append(
                    IngestionIssue("zero_chunks", f"Document id={doc_id} has 0 chunks", fname)
                )

        anomalies = fetch_metrics_anomalies(conn, args.min_success_rate)
        if anomalies:
            for fname, rate in anomalies:
                msg = f"Success rate {rate:.3f} < {args.min_success_rate}"
                issues.append(IngestionIssue("low_success_rate", msg, fname))

        repairs_applied = []
        if args.repair:
            for doc_id, fname in zero_chunk:
                try:
                    delete_document(conn, doc_id)
                    restored, msg = restore_file(args.uploads_dir, fname)
                    repairs_applied.append(f"Deleted doc_id={doc_id}; {msg}")
                except Exception as e:
                    issues.append(IngestionIssue("repair_error", f"Failed to repair {fname}", str(e)))
            conn.commit()

        if issues:
            print("Docling Ingestion Health Report:")
            for iss in issues:
                print(f" - [{iss.category}] {iss.description} :: {iss.details}")
        else:
            print("Docling Ingestion Health Report: OK (no issues detected)")

        if args.repair and repairs_applied:
            print("Repairs Applied:")
            for r in repairs_applied:
                print(f" - {r}")

        return 0 if (args.repair or not issues) else 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())
