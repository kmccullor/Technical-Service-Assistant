import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class KnowledgeCorrection(BaseModel):
    id: Optional[int] = None
    question: str = Field(..., description="The user question being corrected.")
    original_answer: str = Field(..., description="The original answer given by the system.")
    corrected_answer: str = Field(..., description="The corrected answer provided by the user.")
    metadata: Optional[Any] = Field(default_factory=dict, description="Optional metadata about the correction.")
    user_id: Optional[str] = Field(None, description="ID of the user who submitted the correction.")
    created_at: Optional[datetime] = None


# DB access helpers (psycopg2 or asyncpg, depending on project)
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


def _has_corrections_table(conn) -> bool:
    """Return True if the knowledge_corrections table exists."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.knowledge_corrections')")
            result = cur.fetchone()
            return bool(result and result[0])
    except psycopg2.Error as exc:
        logger.error("Failed to check knowledge_corrections table existence: %s", exc)
        return False


def insert_correction(conn, correction: KnowledgeCorrection) -> int:
    """Insert a new correction and return its ID."""
    if not _has_corrections_table(conn):
        logger.debug("knowledge_corrections table absent; insert skipped")
        return -1
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO knowledge_corrections (question, original_answer, corrected_answer, metadata, user_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    correction.question,
                    correction.original_answer,
                    correction.corrected_answer,
                    psycopg2.extras.Json(correction.metadata) if correction.metadata is not None else None,
                    correction.user_id,
                ),
            )
            return cur.fetchone()[0]
    except psycopg2.errors.UndefinedTable:
        conn.rollback()
        logger.warning("knowledge_corrections table missing; skipping insert")
        return -1
    except psycopg2.Error as exc:
        conn.rollback()
        logger.error("Failed to insert knowledge correction: %s", exc)
        return -1


def get_correction_for_question(conn, question: str) -> Optional[KnowledgeCorrection]:
    """Return the most recent correction for a question, if any."""
    if not _has_corrections_table(conn):
        logger.debug("knowledge_corrections table absent; lookup skipped")
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, question, original_answer, corrected_answer, metadata, user_id, created_at
                FROM knowledge_corrections
                WHERE question = %s
                ORDER BY created_at DESC
                LIMIT 1;
                """,
                (question,),
            )
            row = cur.fetchone()
            if row:
                return KnowledgeCorrection(
                    id=row[0],
                    question=row[1],
                    original_answer=row[2],
                    corrected_answer=row[3],
                    metadata=row[4],
                    user_id=row[5],
                    created_at=row[6],
                )
            return None
    except psycopg2.errors.UndefinedTable:
        conn.rollback()
        logger.debug("knowledge_corrections table missing; skipping lookup")
        return None
    except psycopg2.Error as exc:
        conn.rollback()
        logger.error("Failed to load knowledge correction: %s", exc)
        return None
