from __future__ import annotations

from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='cache',
    log_level='INFO',
    log_file=f'/app/logs/cache_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

"""Web search caching utilities.

Provides simple Postgres-backed caching for SearXNG web search results.
Avoids repeated outbound queries for identical (normalized) queries within TTL.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import psycopg2
from pydantic import BaseModel

from config import get_settings

# Initialize logger

settings = get_settings()

def get_db_connection():
    """Get database connection using centralized config."""
    return psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )

class CachedWebResult(BaseModel):
    title: str
    url: str
    content: str
    score: float

def _normalize_query(q: str) -> str:
    return " ".join(q.lower().strip().split())

def _hash_query(norm: str) -> str:
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()

def get_cached_web_results(query: str) -> Optional[List[CachedWebResult]]:
    if not settings.web_cache_enabled:
        return None
    norm = _normalize_query(query)
    qh = _hash_query(norm)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT results_json, expires_at, hit_count FROM web_search_cache
                   WHERE query_hash=%s LIMIT 1""",
            (qh,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return None
        results_json, expires_at, hit_count = row
        if expires_at < datetime.now(timezone.utc):
            # Expired - purge
            cur.execute("DELETE FROM web_search_cache WHERE query_hash=%s", (qh,))
            conn.commit()
            cur.close()
            conn.close()
            return None
        # Increment hit count (non-critical if fails)
        try:
            cur.execute("UPDATE web_search_cache SET hit_count=hit_count+1 WHERE query_hash=%s", (qh,))
            conn.commit()
        except Exception:
            conn.rollback()
        cur.close()
        conn.close()
        if isinstance(results_json, str):
            try:
                results_json = json.loads(results_json)
            except json.JSONDecodeError:
                return None
        return [CachedWebResult(**r) for r in results_json]
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None

def store_web_results(query: str, results: List[dict]):
    if not settings.web_cache_enabled:
        return
    norm = _normalize_query(query)
    qh = _hash_query(norm)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.web_cache_ttl_seconds)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO web_search_cache (query_hash, normalized_query, results_json, expires_at)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (query_hash) DO UPDATE SET
                     results_json=EXCLUDED.results_json,
                     expires_at=EXCLUDED.expires_at
               """,
            (qh, norm, json.dumps(results), expires_at),
        )
        conn.commit()
        # Optional pruning if above max rows
        if settings.web_cache_max_rows > 0:
            cur.execute("SELECT COUNT(*) FROM web_search_cache")
            count = cur.fetchone()[0]
            if count > settings.web_cache_max_rows:
                # delete oldest extra
                cur.execute(
                    "DELETE FROM web_search_cache WHERE id IN (SELECT id FROM web_search_cache ORDER BY created_at ASC LIMIT %s)",
                    (count - settings.web_cache_max_rows,),
                )
                conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Cache store failed: {e}")
