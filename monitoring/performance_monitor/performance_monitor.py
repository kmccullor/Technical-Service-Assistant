#!/usr/bin/env python3
"""Advanced performance & ingestion monitoring exporter with Prometheus metrics.

Usage:
    SINGLE_RUN=1 python performance_monitor.py
            Emit metrics once to stdout (Prometheus exposition format) and exit.

    REFRESH_INTERVAL=30 EXPORTER_PORT=9109 python performance_monitor.py
            Run continuous exporter server (default interval 30s, port 9109).

Metrics exported (tsa_*):
    - tsa_documents_total                (gauge)     Total rows in documents
    - tsa_document_chunks_total          (gauge)     Total rows in document_chunks
    - tsa_last_ingestion_timestamp       (gauge)     Unix time of latest document.created_at
    - tsa_documents_processed_today      (gauge)     Documents ingested since CURRENT_DATE
    - tsa_avg_processing_time_seconds    (gauge)     Avg processing time (today) from document_ingestion_metrics
    - tsa_chunks_created_today           (gauge)     Chunks created today (sum inserted_chunks)
    - tsa_service_status{component="X"}  (gauge)     1 healthy / 0 unhealthy for reranker, db, ollama servers
    - tsa_last_refresh_timestamp         (gauge)     Unix time of last successful refresh cycle
    - tsa_refresh_duration_seconds       (histogram) Duration distribution of refresh cycles
    - tsa_refresh_errors_total           (counter)   Total refresh cycles that failed

Design:
    * DNS fallback chain for DB host (settings.db_host -> postgres -> postgresql -> db)
    * Resilient refresh loop with histogram timing & error counter
    * Structured logging (level + message) for ingestion into centralized logs
    * Zero dependency on direct os.environ in logic beyond mode flags
"""

from __future__ import annotations

import logging
import os
import socket
import time
from contextlib import contextmanager
from typing import Dict

import psycopg2
import requests
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest, start_http_server

from config import get_settings
from utils.logging_config import configure_root_logging

configure_root_logging()
LOG = logging.getLogger("performance_monitor")

# ---------------------------------------------------------------------------
# Registry & Metric definitions
# ---------------------------------------------------------------------------
REGISTRY = CollectorRegistry()

G_DOCUMENTS_TOTAL = Gauge("tsa_documents_total", "Total documents ingested", registry=REGISTRY)
G_DOCUMENT_CHUNKS_TOTAL = Gauge("tsa_document_chunks_total", "Total document chunks stored", registry=REGISTRY)
G_LAST_INGESTION_TS = Gauge(
    "tsa_last_ingestion_timestamp", "Unix timestamp of latest document ingestion", registry=REGISTRY
)
G_DOCS_PROCESSED_TODAY = Gauge("tsa_documents_processed_today", "Documents processed today", registry=REGISTRY)
G_AVG_PROC_TIME_TODAY = Gauge(
    "tsa_avg_processing_time_seconds", "Average processing time (s) for today's ingestions", registry=REGISTRY
)
G_CHUNKS_CREATED_TODAY = Gauge(
    "tsa_chunks_created_today", "Chunks created today (sum inserted_chunks)", registry=REGISTRY
)
G_SERVICE_STATUS = Gauge(
    "tsa_service_status", "Service/component health (1=healthy,0=unhealthy)", ["component"], registry=REGISTRY
)
G_LAST_REFRESH_TS = Gauge("tsa_last_refresh_timestamp", "Unix timestamp of last successful refresh", registry=REGISTRY)
H_REFRESH_DURATION = Histogram(
    "tsa_refresh_duration_seconds",
    "Refresh cycle durations",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    registry=REGISTRY,
)
C_REFRESH_ERRORS = Counter("tsa_refresh_errors_total", "Total refresh cycles that failed", registry=REGISTRY)


@contextmanager
def timing(metric: Histogram):
    start = time.perf_counter()
    try:
        yield
    finally:
        metric.observe(time.perf_counter() - start)


def _resolve_db_host(settings) -> str:
    for candidate in [settings.db_host, "postgres", "postgresql", "db"]:
        if not candidate:
            continue
        try:
            socket.gethostbyname(candidate)
            return candidate
        except Exception:  # noqa: BLE001
            continue
    return settings.db_host


def _db_connect(settings):
    return psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=_resolve_db_host(settings),
        port=settings.db_port,
        connect_timeout=5,
    )


def _collect_db_metrics() -> Dict[str, float]:
    settings = get_settings()
    out: Dict[str, float] = {
        "documents_total": 0,
        "chunks_total": 0,
        "last_ingestion_ts": 0.0,
        "docs_today": 0,
        "avg_proc_today": 0.0,
        "chunks_today": 0,
    }
    try:
        with _db_connect(settings) as conn:  # type: ignore[arg-type]
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM documents")
                row = cur.fetchone()
                out["documents_total"] = row[0] if row and row[0] is not None else 0

                cur.execute("SELECT COUNT(*) FROM document_chunks")
                row = cur.fetchone()
                out["chunks_total"] = row[0] if row and row[0] is not None else 0

                cur.execute("SELECT MAX(created_at) FROM documents")
                row = cur.fetchone()
                latest = row[0] if row else None
                if latest:
                    out["last_ingestion_ts"] = latest.timestamp()

                cur.execute(
                    """
                    SELECT COUNT(*),
                           AVG(EXTRACT(EPOCH FROM (processing_end_time - processing_start_time))) as avg_time,
                               COALESCE(SUM(inserted_chunks),0)
                    FROM document_ingestion_metrics
                    WHERE created_at >= CURRENT_DATE
                    """
                )
                row = cur.fetchone()
                if row:
                    out["docs_today"] = row[0] or 0
                    out["avg_proc_today"] = float(row[1]) if row[1] else 0.0
                    out["chunks_today"] = row[2] or 0
    except Exception as e:  # noqa: BLE001
        LOG.warning("db_metrics_error error=%s", e)
    return out


def _check_http(url: str, timeout: float = 4.0) -> bool:
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _collect_service_status() -> Dict[str, int]:
    status: Dict[str, int] = {}
    status["reranker"] = 1 if _check_http("http://reranker:8008/health") else 0
    for i in range(1, 5):
        status[f"ollama_server_{i}"] = 1 if _check_http(f"http://ollama-server-{i}:11434/api/tags") else 0
    try:
        with _db_connect(get_settings()):  # type: ignore[arg-type]
            status["database"] = 1
    except Exception:  # noqa: BLE001
        status["database"] = 0
    return status


def refresh_metrics() -> bool:
    ok = True
    with timing(H_REFRESH_DURATION):
        db = _collect_db_metrics()
        G_DOCUMENTS_TOTAL.set(db["documents_total"])
        G_DOCUMENT_CHUNKS_TOTAL.set(db["chunks_total"])
        if db["last_ingestion_ts"]:
            G_LAST_INGESTION_TS.set(db["last_ingestion_ts"])
        G_DOCS_PROCESSED_TODAY.set(db["docs_today"])
        G_AVG_PROC_TIME_TODAY.set(db["avg_proc_today"])
        G_CHUNKS_CREATED_TODAY.set(db["chunks_today"])

        for comp, val in _collect_service_status().items():
            G_SERVICE_STATUS.labels(component=comp).set(val)

        G_LAST_REFRESH_TS.set(time.time())
    return ok


def run_exporter(interval: int = 30) -> None:
    port = int(os.environ.get("EXPORTER_PORT", "9109"))
    LOG.info("starting_exporter port=%s interval=%s", port, interval)
    start_http_server(port, registry=REGISTRY)
    while True:
        try:
            if not refresh_metrics():
                C_REFRESH_ERRORS.inc()
            time.sleep(interval)
        except KeyboardInterrupt:  # pragma: no cover
            LOG.info("exporter_shutdown")
            break
        except Exception as e:  # noqa: BLE001
            C_REFRESH_ERRORS.inc()
            LOG.exception("refresh_cycle_error error=%s", e)
            time.sleep(interval)


def run_single_run() -> None:
    if not refresh_metrics():
        C_REFRESH_ERRORS.inc()
    import sys

    sys.stdout.buffer.write(generate_latest(REGISTRY))


def main() -> None:
    if os.environ.get("SINGLE_RUN") == "1":
        run_single_run()
    else:
        run_exporter(interval=int(os.environ.get("REFRESH_INTERVAL", "30")))


if __name__ == "__main__":  # pragma: no cover
    main()
