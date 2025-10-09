from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

class KnowledgeCorrection(BaseModel):
    id: Optional[int] = None
    question: str = Field(..., description="The user question being corrected.")
    original_answer: str = Field(..., description="The original answer given by the system.")
    corrected_answer: str = Field(..., description="The corrected answer provided by the user.")
    metadata: Optional[Any] = Field(default_factory=dict, description="Optional metadata about the correction.")
    user_id: Optional[str] = Field(None, description="ID of the user who submitted the correction.")
    created_at: Optional[datetime] = None

# DB access helpers (psycopg2 or asyncpg, depending on project)
import psycopg2.extras

def insert_correction(conn, correction: KnowledgeCorrection) -> int:
    """Insert a new correction and return its ID."""
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
                correction.user_id
            )
        )
        return cur.fetchone()[0]

def get_correction_for_question(conn, question: str) -> Optional[KnowledgeCorrection]:
    """Return the most recent correction for a question, if any."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, question, original_answer, corrected_answer, metadata, user_id, created_at
            FROM knowledge_corrections
            WHERE question = %s
            ORDER BY created_at DESC
            LIMIT 1;
            """,
            (question,)
        )
        row = cur.fetchone()
        if row:
            return KnowledgeCorrection(
                id=row[0], question=row[1], original_answer=row[2],
                corrected_answer=row[3], metadata=row[4], user_id=row[5], created_at=row[6]
            )
        return None
