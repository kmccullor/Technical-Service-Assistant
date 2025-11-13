"""
Minimal Technical Service Assistant API
Just the basic chat endpoints to get the frontend working.
"""

import hashlib
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, cast

import jwt
import uvicorn

# Add /app to Python path for imports
sys.path.insert(0, "/app")
import asyncio
import json
import logging

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response, StreamingResponse
from prometheus_client.exposition import CONTENT_TYPE_LATEST, generate_latest
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

print("Starting app.py execution")

# Import auth endpoints
from config import get_settings
from reranker.cache import get_db_connection
from reranker.question_decomposer import QuestionDecomposer
from reranker.rag_chat import (
    BatchRAGChatRequest,
    BatchRAGChatResponse,
    RAGChatResponse,
    RAGChatService,
    add_rag_endpoints,
)
from reranker.rethink_reranker import rethink_pipeline
from utils.redis_cache import (
    cache_decomposed_response,
    cache_sub_request_result,
    get_decomposed_response,
    get_sub_request_result,
)

try:
    from pydantic_agent import (
        ChatAgentDeps,
        initialize_pydantic_agent,
        is_pydantic_agent_enabled,
        run_pydantic_agent_chat,
    )

    _HAS_PYDANTIC_AGENT = True
except Exception:  # pragma: no cover - fallback when dependency missing
    ChatAgentDeps = None

    def initialize_pydantic_agent(*_: Any, **__: Any) -> None:
        return None

    def is_pydantic_agent_enabled() -> bool:
        return False

    async def run_pydantic_agent_chat(*_: Any, **__: Any) -> RAGChatResponse:
        raise RuntimeError("Pydantic AI agent is not available")

    _HAS_PYDANTIC_AGENT = False

ENABLE_A2A_AGENT = os.getenv("ENABLE_A2A_AGENT", "false").lower() in {"1", "true", "yes"}

from reranker.rbac_endpoints import rbac_router

# TIER 2: Authentication & Security imports
try:
    from reranker.auth_endpoints import router as auth_router

    # from reranker.auth_middleware import JWTAuthMiddleware, verify_jwt_token  # Temporarily disabled
    _HAS_TIER2_AUTH = True
except ImportError as e:
    logger.warning(f"Tier 2 authentication modules not available: {e}")
    _HAS_TIER2_AUTH = False

app = FastAPI(
    title="Technical Service Assistant API",
    description="API for RAG system with basic chat endpoints",
    version="1.0.0",
)


async def _token_stream_chunks(text: str) -> AsyncIterator[str]:
    """Yield response text in configurable word chunks to avoid long-running SSE streams."""
    words = text.split()
    chunk_size = max(1, STREAM_CHUNK_WORDS)
    delay = STREAM_DELAY_SECONDS
    for start in range(0, len(words), chunk_size):
        chunk = " ".join(words[start : start + chunk_size]) + " "
        yield chunk
        if delay > 0:
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(0)


# Test question endpoint
@app.get("/api/admin/question-stats-test")
def test_question_stats():
    return {"message": "Question stats endpoint works"}


# Initialize RAG service
rag_service = RAGChatService()
app_settings = get_settings()
STREAM_CHUNK_WORDS = max(1, getattr(app_settings, "chat_stream_chunk_words", 40))
STREAM_DELAY_SECONDS = max(0.0, getattr(app_settings, "chat_stream_delay_seconds", 0.0))

a2a_service = None
if ENABLE_A2A_AGENT:
    if not _HAS_PYDANTIC_AGENT:
        logger.warning("ENABLE_A2A_AGENT is set but the Pydantic AI agent is disabled; skipping A2A server init")
    else:
        try:
            from pydantic_agent_a2a import create_a2a_service

            a2a_service = create_a2a_service(rag_service)
            if a2a_service.app:
                app.mount("/a2a", a2a_service.app)
                logger.info("Mounted Agent2Agent endpoint at /a2a")
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to initialize Agent2Agent endpoint: %s", exc)
            a2a_service = None

# Include RAG endpoints
add_rag_endpoints(app)

# Include auth endpoints
app.include_router(rbac_router)

# Include Tier 2 authentication endpoints if available
if _HAS_TIER2_AUTH:
    app.include_router(auth_router)
    # app.add_middleware(JWTAuthMiddleware)  # Temporarily disabled for testing
    logger.info("Tier 2 authentication enabled (middleware disabled)")
else:
    logger.warning("Tier 2 authentication disabled - modules not available")


@app.on_event("startup")
async def bootstrap_agents() -> None:
    if _HAS_PYDANTIC_AGENT:
        initialize_pydantic_agent(rag_service)
    if a2a_service is not None:
        await a2a_service.startup()


@app.on_event("shutdown")
async def shutdown_agents() -> None:
    if a2a_service is not None:
        await a2a_service.shutdown()


# Add intelligent routing endpoints
print("Importing intelligent_router...")
from reranker.intelligent_router import add_intelligent_routing_endpoints

print("Calling add_intelligent_routing_endpoints...")
add_intelligent_routing_endpoints(app)
print("Intelligent routing endpoints added.")


class ChatRequest(BaseModel):
    conversationId: Optional[int] = None
    message: str
    displayMessage: Optional[str] = None


class ConversationSummary(BaseModel):
    id: int
    title: str
    createdAt: str
    updatedAt: Optional[str] = None


class MessageInfo(BaseModel):
    id: int
    role: str
    content: str
    citations: Optional[List[dict]] = None
    createdAt: str


class ConversationDetail(BaseModel):
    id: int
    title: str
    createdAt: str
    updatedAt: Optional[str] = None
    messages: List[MessageInfo]


class ConversationListResponse(BaseModel):
    conversations: List[ConversationSummary]
    total: int
    hasMore: bool


class UserResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    role_id: int
    role_name: Optional[str]
    status: str
    verified: bool
    last_login: Optional[str]
    is_active: bool
    is_locked: bool
    password_change_required: bool
    created_at: str
    updated_at: str


def _deterministic_user_id(email: str) -> int:
    normalized = email.strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    # Use first 7 hex characters to stay within safe integer range.
    return int(digest[:7], 16)


def _normalize_question(question: str) -> str:
    """Normalize question text for consistent hashing and grouping."""
    # Convert to lowercase
    normalized = question.lower().strip()
    # Remove extra whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    # Remove punctuation except essential ones
    normalized = re.sub(r"[^\w\s\?\!\.]", "", normalized)
    return normalized


def _hash_question(question: str) -> str:
    """Generate SHA-256 hash of normalized question."""
    normalized = _normalize_question(question)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _categorize_question(question: str) -> str:
    """Auto-categorize question based on content."""
    q_lower = question.lower()

    if any(word in q_lower for word in ["how to", "how do", "setup", "install", "configure"]):
        return "technical_setup"
    elif any(word in q_lower for word in ["what is", "explain", "definition", "meaning"]):
        return "explanatory"
    elif any(word in q_lower for word in ["error", "problem", "issue", "fail", "broken"]):
        return "troubleshooting"
    elif any(word in q_lower for word in ["user", "role", "permission", "admin", "access"]):
        return "user_management"
    elif any(word in q_lower for word in ["report", "dashboard", "analytics", "statistics"]):
        return "reporting"
    else:
        return "general"


def _track_question_usage(
    question_text: str,
    user_id: int,
    conversation_id: int,
    response_time_ms: int,
    quality_score: float,
    search_method: str,
    citations_count: int,
    context_length: int,
):
    """Track question usage in database."""
    try:
        question_hash = _hash_question(question_text)
        category = _categorize_question(question_text)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert or get question pattern
        cursor.execute(
            """
            INSERT INTO question_patterns (question_hash, canonical_question, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (question_hash) DO UPDATE SET
                canonical_question = EXCLUDED.canonical_question,
                category = EXCLUDED.category
            RETURNING id
        """,
            [question_hash, question_text[:500], category],
        )

        pattern_result = cursor.fetchone()
        pattern_id = pattern_result[0] if pattern_result else None

        if pattern_id:
            # Insert usage record
            cursor.execute(
                """
                INSERT INTO question_usage (
                    question_pattern_id, user_id, conversation_id, question_text,
                    response_time_ms, response_quality_score, context_length,
                    search_method, citations_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                [
                    pattern_id,
                    user_id,
                    conversation_id,
                    question_text,
                    response_time_ms,
                    quality_score,
                    context_length,
                    search_method,
                    citations_count,
                ],
            )

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"Failed to track question usage: {e}")


def _serialize_timestamp(value: Optional[Any], default: Optional[str] = None) -> Optional[str]:
    """Convert datetime-like objects to ISO strings."""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).isoformat()
        except Exception:
            return default
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _user_from_authorization(authorization: Optional[str]) -> UserResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "")

    # Try to decode JWT
    jwt_secret = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        email = payload.get("email")
        if user_id and email:
            # Look up user from database
            try:
                conn = get_db_connection()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("SELECT * FROM users WHERE id = %s", [user_id])
                user_row = cursor.fetchone()
                cursor.close()
                conn.close()

                if user_row:
                    created_at_value = user_row.get("created_at")
                    updated_at_value = user_row.get("updated_at")
                    return UserResponse(
                        id=user_row["id"],
                        email=user_row["email"],
                        first_name=user_row.get("first_name"),
                        last_name=user_row.get("last_name"),
                        full_name=f"{user_row.get('first_name', 'User')} {user_row.get('last_name', 'Test')}",
                        role_id=user_row.get("role_id", 2),
                        role_name="admin" if user_row.get("role_id") == 1 else "employee",
                        status=user_row.get("status", "active"),
                        verified=user_row.get("verified", True),
                        last_login=_serialize_timestamp(user_row.get("last_login")),
                        is_active=True,
                        is_locked=False,
                        password_change_required=user_row.get("password_change_required", False),
                        created_at=_serialize_timestamp(created_at_value, "2024-01-01T00:00:00Z"),
                        updated_at=_serialize_timestamp(updated_at_value, "2024-01-01T00:00:00Z"),
                    )
            except Exception as e:
                logger.error(f"Error looking up user {user_id}: {e}")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.DecodeError:
        pass  # Fall back to old logic

    # Fallback for mock tokens or old logic
    email = "admin@employee.com"
    if authorization and authorization.startswith("Bearer mock_access_token_"):
        token = authorization.replace("Bearer mock_access_token_", "")
        if "@" in token:
            email = token

    # Hardcoded mapping for known users
    known_users = {
        "jim.hitchcock@xylem.com": 8,
        "admin@example.com": 1,
        "jason.kelly@xylem.com": 13,
        "brad.lee@xylem.com": 12,
        "karen.zeher@xylem.com": 11,
        "brian.ekelman@xylem.com": 21,
        "joseph.davis@xylem.com": 37,
        "katie.king@xylem.com": 39,
        "charlie.burtyk@xylem.com": 20,
        "terrence.blacknell@xylem.com": 19,
    }

    print(f"DEBUG: Email extracted: {email}")
    if email in known_users:
        print(f"DEBUG: Using hardcoded user ID: {known_users[email]}")
        user_id = known_users[email]
        # Mock response for known users
        is_admin = email in ["jim.hitchcock@xylem.com", "admin@example.com"]
        return UserResponse(
            id=user_id,
            email=email,
            first_name="Test",
            last_name="User",
            full_name="Test User",
            role_id=1 if is_admin else 2,
            role_name="admin" if is_admin else "employee",
            status="active",
            verified=True,
            last_login=None,
            is_active=True,
            is_locked=False,
            password_change_required=False,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

    # Look up user from database, create if doesn't exist
    try:
        # Extract name parts for user creation
        email_parts = email.split("@")
        username = email_parts[0] if email_parts else "user"
        name_parts = username.replace(".", " ").replace("_", " ").split()
        first_name = name_parts[0].capitalize() if name_parts else "User"
        last_name = name_parts[1].capitalize() if len(name_parts) > 1 else "Test"

        logger.info(f"Looking up user with email: {email}")
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s", [email])
        user_row = cursor.fetchone()
        logger.info(f"User lookup result: {user_row is not None}")

        if not user_row:
            # User doesn't exist, create them
            user_id = _deterministic_user_id(email)
            role_id = (
                1 if email in ["kevin.mccullor@xylem.com", "admin@employee.com"] or "admin" in email.lower() else 2
            )

            logger.info(
                f"Creating new user: id={user_id}, email={email}, first_name={first_name}, last_name={last_name}, role_id={role_id}"
            )
            cursor.execute(
                """
                INSERT INTO users (id, email, name, first_name, last_name, role_id, status, verified, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'active', true, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    role_id = EXCLUDED.role_id,
                    updated_at = NOW()
                RETURNING *
            """,
                [user_id, email, f"{first_name} {last_name}", first_name, last_name, role_id],
            )
            user_row = cursor.fetchone()
            conn.commit()
            logger.info(f"User creation result: {user_row}")

        cursor.close()
        conn.close()

        if user_row:
            return UserResponse(
                id=user_row["id"],
                email=user_row["email"],
                first_name=user_row.get("first_name"),
                last_name=user_row.get("last_name"),
                full_name=user_row.get(
                    "name", f"{user_row.get('first_name', 'User')} {user_row.get('last_name', 'Test')}"
                ),
                role_id=user_row.get("role_id", 2),
                role_name="admin" if user_row.get("role_id") == 1 else "employee",
                status=user_row.get("status", "active"),
                verified=user_row.get("verified", True),
                last_login=user_row.get("last_login"),
                is_active=True,
                is_locked=False,
                password_change_required=user_row.get("password_change_required", False),
                created_at=user_row["created_at"].isoformat() if user_row["created_at"] else "2024-01-01T00:00:00Z",
                updated_at=user_row["updated_at"].isoformat() if user_row["updated_at"] else "2024-01-01T00:00:00Z",
            )
    except Exception as e:
        logger.error(f"Error looking up/creating user {email}: {e}")

    # Fallback to mock user (should not reach here after database lookup/creation)
    email_parts = email.split("@")
    username = email_parts[0] if email_parts else "user"
    name_parts = username.replace(".", " ").replace("_", " ").split()
    first_name = name_parts[0].capitalize() if name_parts else "User"
    last_name = name_parts[1].capitalize() if len(name_parts) > 1 else "Test"

    if email in ["kevin.mccullor@xylem.com", "admin@employee.com"] or "admin" in email.lower():
        role_id = 1
        role_name = "admin"
    else:
        role_id = 2
        role_name = "employee"

    user_id = 7 if email == "kevin.mccullor@xylem.com" else _deterministic_user_id(email)

    return UserResponse(
        id=user_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name} {last_name}",
        role_id=role_id,
        role_name=role_name,
        status="active",
        verified=True,
        last_login=None,
        is_active=True,
        is_locked=False,
        password_change_required=False,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, authorization: Optional[str] = Header(None)):
    """Streaming chat endpoint with RAG integration."""
    # Basic auth check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = _user_from_authorization(authorization)
    print(f"User ID: {user.id}, email: {user.email}, type: {type(user.id)}")

    conversation_id = request.conversationId
    is_new_conversation = False

    title_source = (request.displayMessage or request.message or "").strip()
    if not title_source:
        title_source = "New conversation"
    conversation_title = title_source if len(title_source) <= 50 else f"{title_source[:50]}..."

    if conversation_id is None:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                "INSERT INTO conversations (title, user_id) VALUES (%s, %s) RETURNING id",
                [conversation_title, user.id],
            )
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=500, detail="Failed to create conversation")
            conversation_id = result["id"]
            conn.commit()
            is_new_conversation = True
        finally:
            cursor.close()
            conn.close()
    else:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                "SELECT id FROM conversations WHERE id = %s AND user_id = %s",
                [conversation_id, user.id],
            )
            existing = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()
        if not existing:
            raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation_id is None:
        raise HTTPException(status_code=500, detail="Conversation setup failed")

    # Get conversation context length for tracking
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as message_count FROM messages WHERE conversation_id = %s", [conversation_id])
        context_result = cursor.fetchone()
        context_length = context_result[0] if context_result else 0
    finally:
        cursor.close()
        conn.close()

    async def generate():
        try:
            start_time = time.time()

            if is_new_conversation:
                yield f"data: {json.dumps({'type': 'conversation_id', 'conversationId': conversation_id})}\n\n"

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
                    [conversation_id, "user", request.message],
                )
                cursor.execute(
                    "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                    [conversation_id],
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()

            from rag_chat import RAGChatRequest

            rag_response: RAGChatResponse
            use_pydantic_agent = _HAS_PYDANTIC_AGENT and is_pydantic_agent_enabled() and ChatAgentDeps is not None

            if use_pydantic_agent:
                try:
                    agent_deps = ChatAgentDeps(
                        user_email=user.email,
                        conversation_id=conversation_id,
                        rag_service=rag_service,
                        context_messages=context_length,
                    )
                    rag_response = await run_pydantic_agent_chat(request.message, agent_deps)
                except Exception as exc:  # pragma: no cover - defensive fallback
                    logger.exception("Pydantic AI agent execution failed, falling back to legacy path: %s", exc)
                    use_pydantic_agent = False

            if not use_pydantic_agent:
                # Feature-flagged decomposition + rerank pipeline
                enable_decomp = os.getenv("ENABLE_QUESTION_DECOMPOSITION", "false").lower() in {
                    "1",
                    "true",
                    "yes",
                }

                if enable_decomp:
                    # Decompose and check short-term cache
                    decomposer = QuestionDecomposer()
                    decomposition = decomposer.decompose_question(request.message, user.id)

                    # Cache decomposition metadata so rethink pipeline can read it
                    try:
                        cache_decomposed_response(decomposition.query_hash, user.id, decomposition.to_dict())
                    except Exception:
                        logger.debug("Failed to cache decomposition metadata (continuing)")

                    # If a synthesized final response already exists in cache, return it
                    cached_final = get_decomposed_response(decomposition.query_hash, user.id)
                    if cached_final and isinstance(cached_final, dict) and cached_final.get("synthesized"):
                        # Use cached synthesized text as the response
                        resp_text = cached_final.get("synthesized", {}).get("synthesized_text") or cached_final.get(
                            "response"
                        )
                        rag_response = RAGChatResponse(
                            response=resp_text or "",
                            context_used=[],
                            context_metadata=[],
                            web_sources=[],
                            model="cached",
                            context_retrieved=False,
                        )
                    else:
                        # Process each sub-request (use cache when available)
                        sub_results = []
                        for sr in decomposition.sub_requests:
                            # Try to reuse cached sub-response
                            cached_sub = get_sub_request_result(sr.id)
                            if cached_sub:
                                sub_results.append(cached_sub)
                                continue

                            # Not cached: generate via rag_service using selected model
                            model_to_use = decomposer.select_model_for_complexity(sr.complexity)
                            rag_req = RAGChatRequest(
                                query=sr.sub_query,
                                use_context=True,
                                max_context_chunks=5,
                                model=model_to_use,
                                temperature=0.2,
                                max_tokens=300,
                            )
                            try:
                                sub_resp = cast(RAGChatResponse, await rag_service.chat(rag_req))
                                sub_data = {
                                    "id": sr.id,
                                    "sub_query": sr.sub_query,
                                    "response": sub_resp.response,
                                    "model": sub_resp.model,
                                    "time_ms": 0,
                                    "confidence": 1.0,
                                }
                                cache_sub_request_result(sr.id, sub_data)
                                sub_results.append(sub_data)
                            except Exception as exc:  # pragma: no cover - tolerate generation errors per-sub
                                logger.exception("Sub-request generation failed: %s", exc)
                                sub_results.append(
                                    {
                                        "id": sr.id,
                                        "sub_query": sr.sub_query,
                                        "response": "",
                                        "model": model_to_use,
                                        "time_ms": 0,
                                        "confidence": 0.0,
                                    }
                                )

                        # At this point, ensure sub-results are cached; aggregate and rerank
                        final_result = rethink_pipeline(decomposition.query_hash, user.id, request.message)

                        # Cache final synthesized result (ttl default)
                        try:
                            cache_decomposed_response(decomposition.query_hash, user.id, final_result)
                        except Exception:
                            logger.debug("Failed to cache final synthesized result (continuing)")

                        synthesized = final_result.get("synthesized", {})
                        resp_text = synthesized.get("synthesized_text") if isinstance(synthesized, dict) else ""

                        # Fallback: if rethink_pipeline returned an error or no synthesized text,
                        # synthesize directly from sub_results we just computed.
                        if (not resp_text) and sub_results:
                            try:
                                # Prefer cached/reranked ordering if available in final_result
                                if final_result.get("reranked_components"):
                                    [r.get("model") or "" for r in final_result.get("reranked_components", [])]
                                else:
                                    [r.get("model") or "" for r in sub_results]
                                joined = "\n\n".join([r.get("response") for r in sub_results if r.get("response")])
                                resp_text = joined
                                # create a minimal final_result-like structure for caching
                                final_result = {
                                    "decomposition": decomposition.to_dict(),
                                    "reranked_components": sub_results,
                                    "synthesized": {"synthesized_text": resp_text, "components": sub_results},
                                    "final_relevance": 0.0,
                                }
                                try:
                                    cache_decomposed_response(decomposition.query_hash, user.id, final_result)
                                except Exception:
                                    pass
                            except Exception:
                                resp_text = resp_text or ""

                        rag_response = RAGChatResponse(
                            response=resp_text or "",
                            context_used=[],
                            context_metadata=[],
                            web_sources=[],
                            model=",".join({r.get("model") or "" for r in final_result.get("reranked_components", [])})
                            if final_result.get("reranked_components")
                            else "",
                            context_retrieved=True,
                        )
                else:
                    rag_request = RAGChatRequest(
                        query=request.message,
                        use_context=True,
                        max_context_chunks=5,
                        model="rni-mistral",
                        temperature=0.2,
                        max_tokens=500,
                    )
                    rag_response = cast(RAGChatResponse, await rag_service.chat(rag_request))

            # Calculate response time
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)

            sources_data = []
            search_method = "rag"
            citations_count = 0

            if rag_response.web_sources:
                search_method = "web"
                for source in rag_response.web_sources[:3]:
                    content_value = source.get("content", "") or ""
                    content = content_value[:200] + "..." if len(content_value) > 200 else content_value
                    sources_data.append(
                        {
                            "title": source.get("title", "Web Source"),
                            "content": content,
                            "source": source.get("url", ""),
                            "score": source.get("score", 0.8),
                        }
                    )
                citations_count = len(rag_response.web_sources)
            elif rag_response.context_metadata:
                search_method = "rag"
                for index, metadata in enumerate(rag_response.context_metadata[:3]):
                    content = (
                        metadata.get("content", "")[:200] + "..."
                        if len(metadata.get("content", "")) > 200
                        else metadata.get("content", "")
                    )
                    sources_data.append(
                        {
                            "title": metadata.get("file_name", f"RAG Context {index + 1}"),
                            "content": content,
                            "source": metadata.get("document_type", "unknown"),
                            "score": 1.0 - metadata.get("distance", 0.0),  # Convert distance to score
                        }
                    )
                citations_count = len(rag_response.context_metadata)

            # Calculate quality score based on citations and response length
            quality_score = min(1.0, (citations_count * 0.1) + (len(rag_response.response) / 1000.0))

            # Track question usage
            _track_question_usage(
                question_text=request.message,
                user_id=user.id,
                conversation_id=conversation_id,
                response_time_ms=response_time_ms,
                quality_score=quality_score,
                search_method=search_method,
                citations_count=citations_count,
                context_length=context_length,
            )

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO messages (conversation_id, role, content, citations) VALUES (%s, %s, %s, %s)",
                    [conversation_id, "assistant", rag_response.response, json.dumps(sources_data)],
                )
                cursor.execute(
                    "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                    [conversation_id],
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()

            response_text = rag_response.response
            async for chunk in _token_stream_chunks(response_text):
                yield f"data: {json.dumps({'type': 'token', 'token': chunk})}\n\n"

            search_method = "web" if rag_response.web_sources else "rag"
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources_data, 'method': search_method})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as exc:
            logger.error(f"Chat endpoint error: {exc}")
            error_msg = "I encountered an error processing your request. Please try again."
            yield f"data: {json.dumps({'type': 'token', 'token': error_msg})}\n\n"
            yield f"data: {json.dumps({'type': 'sources', 'sources': [], 'method': 'error'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/api/batch-chat", response_model=BatchRAGChatResponse)
async def batch_chat(request: BatchRAGChatRequest, authorization: Optional[str] = Header(None)):
    """Process multiple queries concurrently for batch processing."""
    user = _user_from_authorization(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    logger.info(f"Batch chat request: {len(request.queries)} queries, max_concurrent={request.max_concurrent}")

    try:
        result = await rag_service.batch_chat(request)
        logger.info(
            f"Batch chat completed: {result.successful_responses}/{result.total_queries} successful in {result.processing_time_seconds:.2f}s"
        )
        return result
    except Exception as e:
        logger.error(f"Batch chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")


# Conversation management endpoints
MAX_CONVERSATIONS_PER_USER = 30
RECENT_CONVERSATION_INTERVAL = "30 days"


@app.get("/api/conversations", response_model=ConversationListResponse)
def list_conversations(
    limit: int = MAX_CONVERSATIONS_PER_USER, offset: int = 0, authorization: Optional[str] = Header(None)
):
    """List conversations for the authenticated user."""
    # Basic auth check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = _user_from_authorization(authorization)
    try:
        requested_limit = int(limit)
    except (TypeError, ValueError):
        requested_limit = MAX_CONVERSATIONS_PER_USER
    try:
        requested_offset = int(offset)
    except (TypeError, ValueError):
        requested_offset = 0

    effective_limit = max(1, min(requested_limit, MAX_CONVERSATIONS_PER_USER))
    effective_offset = max(0, requested_offset)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            count_query = """
                WITH conversation_activity AS (
                    SELECT
                        c.id,
                        COALESCE(MAX(m.created_at), c.updated_at, c.created_at) AS last_activity
                    FROM conversations c
                    LEFT JOIN messages m ON c.id = m.conversation_id
                    WHERE c.user_id = %s
                    GROUP BY c.id, c.updated_at, c.created_at
                )
                SELECT COUNT(*) AS total
                FROM conversation_activity
                WHERE last_activity >= NOW() - INTERVAL %s
            """
            cursor.execute(count_query, [user.id, RECENT_CONVERSATION_INTERVAL])
            count_result = cursor.fetchone()
            total = int(count_result["total"]) if count_result and count_result.get("total") is not None else 0

            conversations_query = """
                WITH conversation_activity AS (
                    SELECT
                        c.id,
                        c.title,
                        c.created_at,
                        c.updated_at,
                        COALESCE(MAX(m.created_at), c.updated_at, c.created_at) AS last_activity
                    FROM conversations c
                    LEFT JOIN messages m ON c.id = m.conversation_id
                    WHERE c.user_id = %s
                    GROUP BY c.id, c.title, c.created_at, c.updated_at
                )
                SELECT
                    id,
                    title,
                    created_at,
                    updated_at,
                    last_activity
                FROM conversation_activity
                WHERE last_activity >= NOW() - INTERVAL %s
                ORDER BY last_activity DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(
                conversations_query,
                [user.id, RECENT_CONVERSATION_INTERVAL, effective_limit, effective_offset],
            )
            conversations_data = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        conversations = []
        for conv in conversations_data:
            created_at_value = conv.get("created_at")
            last_message_value = conv.get("last_activity") or conv.get("updated_at")
            created_at_str = (
                created_at_value.isoformat() if hasattr(created_at_value, "isoformat") else created_at_value
            )
            updated_at_str = (
                last_message_value.isoformat() if hasattr(last_message_value, "isoformat") else last_message_value
            )
            conversations.append(
                ConversationSummary(
                    id=conv["id"],
                    title=conv["title"],
                    createdAt=created_at_str,
                    updatedAt=updated_at_str,
                )
            )

        has_more = (effective_offset + len(conversations)) < total

        return ConversationListResponse(conversations=conversations, total=total, hasMore=has_more)

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        # Fallback to empty list
        return ConversationListResponse(conversations=[], total=0, hasMore=False)


@app.post("/api/conversations")
def create_conversation(title: str = "New Conversation", authorization: Optional[str] = Header(None)):
    """Create a new conversation."""
    # Basic auth check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = _user_from_authorization(authorization)
    title_text = title.strip() if isinstance(title, str) else ""
    if not title_text:
        title_text = "New Conversation"

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Insert new conversation
        insert_query = """
            INSERT INTO conversations (title, user_id)
            VALUES (%s, %s)
            RETURNING id, title, created_at, updated_at
        """
        try:
            cursor.execute(insert_query, [title_text, user.id])
            result = cursor.fetchone()
            conn.commit()
        finally:
            cursor.close()
            conn.close()

        if result:
            created_at_value = result.get("created_at")
            updated_at_value = result.get("updated_at")
            return ConversationSummary(
                id=result["id"],
                title=result["title"],
                createdAt=created_at_value.isoformat() if hasattr(created_at_value, "isoformat") else created_at_value,
                updatedAt=updated_at_value.isoformat() if hasattr(updated_at_value, "isoformat") else updated_at_value,
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to create conversation")

    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to create conversation")


@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, authorization: Optional[str] = Header(None)):
    """Get conversation details and messages."""
    # Basic auth check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = _user_from_authorization(authorization)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            conv_query = """
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE id = %s AND user_id = %s
            """
            cursor.execute(conv_query, [conversation_id, user.id])
            conv_result = cursor.fetchone()

            if not conv_result:
                raise HTTPException(status_code=404, detail="Conversation not found")

            messages_query = """
                SELECT id, role, content, citations, created_at
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at ASC
            """
            cursor.execute(messages_query, [conversation_id])
            messages_data = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        messages = []
        for msg in messages_data:
            created_at_value = msg.get("created_at")
            messages.append(
                MessageInfo(
                    id=msg["id"],
                    role=msg["role"],
                    content=msg["content"],
                    citations=msg["citations"],
                    createdAt=created_at_value.isoformat()
                    if hasattr(created_at_value, "isoformat")
                    else created_at_value,
                )
            )

        # Calculate updated_at as the latest message time
        timestamps = [msg.get("created_at") for msg in messages_data if hasattr(msg.get("created_at"), "isoformat")]
        updated_at_value = conv_result.get("updated_at")
        if updated_at_value is not None and hasattr(updated_at_value, "isoformat"):
            timestamps.append(updated_at_value)
        latest_timestamp = max(timestamps) if timestamps else updated_at_value

        return ConversationDetail(
            id=conv_result["id"],
            title=conv_result["title"],
            createdAt=conv_result["created_at"].isoformat()
            if hasattr(conv_result["created_at"], "isoformat")
            else conv_result["created_at"],
            updatedAt=latest_timestamp.isoformat() if hasattr(latest_timestamp, "isoformat") else latest_timestamp,
            messages=messages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation")


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, authorization: Optional[str] = Header(None)):
    """Delete a conversation and all its messages."""
    # Basic auth check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = _user_from_authorization(authorization)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Clean up dependent analytics data before removing the conversation itself
            delete_usage_query = "DELETE FROM question_usage WHERE conversation_id = %s"
            cursor.execute(delete_usage_query, [conversation_id])

            delete_query = "DELETE FROM conversations WHERE id = %s AND user_id = %s"
            cursor.execute(delete_query, [conversation_id, user.id])

            if cursor.rowcount == 0:
                conn.rollback()
                raise HTTPException(status_code=404, detail="Conversation not found")

            conn.commit()
        finally:
            cursor.close()
            conn.close()

        return Response(status_code=204)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


@app.get("/health")
async def auth_health():
    """Auth health check endpoint with database connectivity check."""
    try:
        # Check database connectivity
        from reranker.cache import get_db_connection

        conn = get_db_connection()
        conn.close()

        return {
            "status": "healthy",
            "service": "auth",
            "database": "connected",
            "message": "Auth service and database are healthy",
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "auth",
            "database": "disconnected",
            "error": str(e),
            "message": "Auth service is running but database is unavailable",
        }


print("Defining /api/ollama-health endpoint")


@app.get("/api/ollama-health")
async def ollama_health():
    """Check health status of all Ollama instances with graceful error handling."""
    try:
        # Import here to avoid circular imports
        from intelligent_router import intelligent_router

        await intelligent_router.refresh_health_status_force()

        status_summary = []
        for instance in intelligent_router.instances:
            status_summary.append(
                {
                    "name": instance.name,
                    "url": instance.url,
                    "healthy": instance.healthy,
                    "response_time": f"{instance.response_time:.2f}s" if instance.response_time > 0 else "unknown",
                    "load_score": f"{instance.load_score:.2f}" if instance.load_score > 0 else "unknown",
                    "last_check": instance.last_check,
                }
            )

        healthy_count = sum(1 for i in intelligent_router.instances if i.healthy)

        # Determine overall status with graceful degradation
        if healthy_count == len(intelligent_router.instances):
            overall_status = "healthy"
            message = "All Ollama instances are healthy"
        elif healthy_count > 0:
            overall_status = "degraded"
            message = f"{healthy_count}/{len(intelligent_router.instances)} instances are healthy"
        else:
            overall_status = "unhealthy"
            message = "No Ollama instances are available"

        return {
            "status": overall_status,
            "message": message,
            "healthy_instances": healthy_count,
            "total_instances": len(intelligent_router.instances),
            "instances": status_summary,
        }
    except Exception as e:
        # Graceful degradation - return status indicating health check failure
        return {
            "status": "unknown",
            "message": "Unable to check Ollama health",
            "error": str(e),
            "healthy_instances": 0,
            "total_instances": 0,
            "instances": [],
        }


@app.get("/api/cache-stats")
async def cache_stats(authorization: Optional[str] = Header(None)):
    """Get query-response cache statistics for monitoring."""
    # Optional: require auth for monitoring endpoint
    # if not authorization or not authorization.startswith("Bearer "):
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    from reranker.query_response_cache import get_cache_stats

    try:
        stats = get_cache_stats()
        return {
            "success": True,
            "cache": stats,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/api/load-balancer-stats")
async def load_balancer_stats(authorization: Optional[str] = Header(None)):
    """Get Ollama load balancer metrics for each instance."""
    from reranker.load_balancer import get_load_balancer

    try:
        lb = get_load_balancer()
        metrics = lb.get_metrics_summary()

        # Calculate overall statistics
        total_requests = sum(int(v["total_requests"]) for v in metrics.values())
        total_successful = sum(int(v["successful_requests"]) for v in metrics.values())
        total_failed = sum(int(v["failed_requests"]) for v in metrics.values())

        healthy_count = sum(1 for v in metrics.values() if v["healthy"])

        return {
            "success": True,
            "instances": metrics,
            "overall": {
                "total_requests": total_requests,
                "successful_requests": total_successful,
                "failed_requests": total_failed,
                "overall_success_rate": f"{(total_successful / max(total_requests, 1)) * 100:.1f}%",
                "healthy_instances": healthy_count,
                "total_instances": len(metrics),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/api/advanced-cache-stats")
async def advanced_cache_stats(authorization: Optional[str] = Header(None)):
    """Get advanced multi-layer cache statistics (embeddings, inference, chunks)."""
    from reranker.advanced_cache import get_advanced_cache

    try:
        cache = get_advanced_cache()
        stats = cache.get_stats()

        return {
            "success": True,
            "cache": stats,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


async def optimization_stats(authorization: Optional[str] = Header(None)):
    """Get query optimization cache statistics for monitoring."""
    from reranker.query_optimizer import get_optimization_stats

    try:
        stats = get_optimization_stats()
        return {
            "success": True,
            "optimization": stats,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current user profile (mock implementation)."""
    return _user_from_authorization(authorization)


# Admin endpoints for user and role management
class UserListItem(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role_id: int
    role_name: str
    status: str
    verified: bool
    created_at: str
    updated_at: str


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    permissions: List[str]
    system: bool
    user_count: int


class UserListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[UserListItem]


@app.get("/api/admin/users", response_model=UserListResponse)
def list_users(limit: int = 50, offset: int = 0, search: Optional[str] = None):
    """List users with pagination and search."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build query with search
        where_conditions = []
        params = []

        if search:
            where_conditions.append("(u.email ILIKE %s OR u.first_name ILIKE %s OR u.last_name ILIKE %s)")
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total
            FROM users u
            WHERE {where_clause}
        """
        cursor.execute(count_query, params)
        count_result = cursor.fetchone()
        total = count_result["total"] if count_result else 0

        # Get users with role info
        users_query = f"""
            SELECT
                u.id,
                u.email,
                u.first_name,
                u.last_name,
                u.role_id,
                r.name as role_name,
                u.status,
                u.verified,
                u.created_at,
                u.updated_at
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE {where_clause}
            ORDER BY u.created_at DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(users_query, params + [limit, offset])
        users = cursor.fetchall()

        cursor.close()
        conn.close()

        # Convert datetime objects to ISO format strings for Pydantic
        processed_users = []
        for user in users:
            user_dict = dict(user)
            if "created_at" in user_dict and user_dict["created_at"]:
                user_dict["created_at"] = user_dict["created_at"].isoformat()
            if "updated_at" in user_dict and user_dict["updated_at"]:
                user_dict["updated_at"] = user_dict["updated_at"].isoformat()
            processed_users.append(user_dict)

        try:
            items = [UserListItem(**user) for user in processed_users]
            return UserListResponse(total=total, limit=limit, offset=offset, items=items)
        except Exception as e:
            print(f"Pydantic validation error: {e}")
            raise
    except Exception as e:
        # Fallback to mock data if database connection fails
        print(f"Database error in list_users: {e}")
        mock_users = [
            {
                "id": 1,
                "email": "admin@employee.com",
                "first_name": "Admin",
                "last_name": "User",
                "role_id": 1,
                "role_name": "admin",
                "status": "active",
                "verified": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": 2,
                "email": "user@employee.com",
                "first_name": "Regular",
                "last_name": "User",
                "role_id": 2,
                "role_name": "employee",
                "status": "active",
                "verified": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
        ]

        if search:
            mock_users = [
                u
                for u in mock_users
                if search.lower() in u["email"].lower()
                or search.lower() in u["first_name"].lower()
                or search.lower() in u["last_name"].lower()
            ]

        total = len(mock_users)
        items = mock_users[offset : offset + limit]

        return UserListResponse(total=total, limit=limit, offset=offset, items=[UserListItem(**user) for user in items])


@app.get("/api/admin/roles", response_model=List[RoleResponse])
def list_roles():
    """List all roles with permissions."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get roles with permissions and user counts
        roles_query = """
            SELECT
                r.id,
                r.name,
                r.description,
                r.is_system as system,
                COUNT(DISTINCT ur.user_id) as user_count,
                array_agg(DISTINCT p.name) FILTER (WHERE p.name IS NOT NULL) as permissions
            FROM roles r
            LEFT JOIN user_roles ur ON r.id = ur.role_id
            LEFT JOIN role_permissions rp ON r.id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.id
            GROUP BY r.id, r.name, r.description, r.is_system
            ORDER BY r.name
        """
        cursor.execute(roles_query)
        roles = cursor.fetchall()

        cursor.close()
        conn.close()

        return [RoleResponse(**dict(role)) for role in roles]
    except Exception:
        # Fallback to mock data
        mock_roles = [
            {
                "id": 1,
                "name": "admin",
                "description": "Administrator with full access",
                "permissions": ["read", "write", "admin"],
                "system": True,
                "user_count": 1,
            },
            {
                "id": 2,
                "name": "employee",
                "description": "Standard employee access",
                "permissions": ["read", "write"],
                "system": True,
                "user_count": 1,
            },
        ]
        return [RoleResponse(**role) for role in mock_roles]


@app.patch("/api/admin/users/{user_id}")
def update_user(user_id: int, updates: dict):
    """Update user status or role (mock implementation)."""
    # In a real implementation, this would update the database
    return {"message": f"User {user_id} updated", "updates": updates}


@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int):
    """Delete user (mock implementation)."""
    # In a real implementation, this would delete from database
    return {"message": f"User {user_id} deleted"}


# Data dictionary endpoints
class RNIVersion(BaseModel):
    id: int
    version_number: str
    version_name: str
    description: str
    release_date: str
    is_active: bool


class DatabaseInstance(BaseModel):
    id: int
    rni_version_id: int
    database_name: str
    database_type: str
    server_name: str
    port: int
    description: str
    is_active: bool


@app.get("/api/data-dictionary/rni-versions")
def get_rni_versions():
    """Get RNI versions (mock implementation)."""
    mock_versions = [
        {
            "id": 1,
            "version_number": "1.0.0",
            "version_name": "Initial Release",
            "description": "First version of the system",
            "release_date": "2024-01-01",
            "is_active": True,
        }
    ]
    return mock_versions


@app.post("/api/data-dictionary/rni-versions")
def create_rni_version(version: dict):
    """Create new RNI version (mock implementation)."""
    return {"message": "RNI version created", "version": version}


@app.get("/api/data-dictionary/database-instances")
def get_database_instances():
    """Get database instances (mock implementation)."""
    mock_instances = [
        {
            "id": 1,
            "rni_version_id": 1,
            "database_name": "vector_db",
            "database_type": "postgresql",
            "server_name": "pgvector",
            "port": 5432,
            "description": "Main vector database",
            "is_active": True,
        }
    ]
    return mock_instances


@app.get("/api/data-dictionary/database-schemas")
def get_database_schemas():
    """Get database schemas (mock implementation)."""
    return {"schemas": ["public"], "message": "Mock database schemas"}


@app.post("/api/data-dictionary/extract-schema")
def extract_schema(request: dict):
    """Extract schema from database (mock implementation)."""
    return {"message": "Schema extraction completed", "schema": {}}


@app.get("/api/data-dictionary/query-assistance")
def get_query_assistance():
    """Get query assistance (mock implementation)."""
    return {"assistance": "Mock query assistance"}


# Document management endpoints
class DocumentInfo(BaseModel):
    id: int
    file_name: str
    title: Optional[str]
    document_type: Optional[str]
    product_name: Optional[str]
    product_version: Optional[str]
    privacy_level: str
    file_size: Optional[int]
    chunk_count: int
    processed_at: Optional[str]
    created_at: str


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total_count: int
    offset: int
    limit: int
    has_more: bool


class DocumentListRequest(BaseModel):
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    search_term: Optional[str] = None
    document_type: Optional[str] = None
    product_name: Optional[str] = None
    privacy_level: Optional[str] = None
    sort_by: str = Field("created_at", description="Sort field: created_at, file_name, chunk_count, processed_at")
    sort_order: str = Field("desc", description="Sort order: asc or desc")


@app.post("/api/documents/list", response_model=DocumentListResponse)
def list_documents(request: DocumentListRequest):
    """List documents in the knowledge base."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build query with filters
        where_conditions = ["d.processing_status = 'processed'"]
        params = []

        if request.document_type:
            where_conditions.append("d.document_type = %s")
            params.append(request.document_type)

        if request.product_name:
            where_conditions.append("d.product_name = %s")
            params.append(request.product_name)

        if request.privacy_level:
            where_conditions.append("d.privacy_level = %s")
            params.append(request.privacy_level)

        if request.search_term:
            where_conditions.append("(d.file_name ILIKE %s OR d.title ILIKE %s)")
            search_pattern = f"%{request.search_term}%"
            params.extend([search_pattern, search_pattern])

        where_clause = " AND ".join(where_conditions)

        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total
            FROM documents d
            WHERE {where_clause}
        """
        cursor.execute(count_query, params)
        count_result = cursor.fetchone()
        total_count = count_result["total"] if count_result else 0

        # Validate sort parameters
        valid_sort_fields = {"created_at", "file_name", "chunk_count", "processed_at"}
        sort_field = request.sort_by if request.sort_by in valid_sort_fields else "created_at"
        sort_order = "ASC" if request.sort_order.lower() == "asc" else "DESC"

        # Get documents with chunk counts
        documents_query = f"""
            SELECT
                d.id,
                d.file_name,
                d.title,
                d.document_type,
                d.product_name,
                d.product_version,
                d.privacy_level,
                d.file_size,
                d.processed_at,
                d.created_at,
                COALESCE(chunk_counts.chunk_count, 0) as chunk_count
            FROM documents d
            LEFT JOIN (
                SELECT document_id, COUNT(*) as chunk_count
                FROM document_chunks
                GROUP BY document_id
            ) chunk_counts ON d.id = chunk_counts.document_id
            WHERE {where_clause}
            ORDER BY d.{sort_field} {sort_order}
            LIMIT %s OFFSET %s
        """

        query_params = params + [request.limit, request.offset]
        cursor.execute(documents_query, query_params)

        documents = []
        for row in cursor.fetchall():
            documents.append(
                DocumentInfo(
                    id=row["id"],
                    file_name=row["file_name"],
                    title=row["title"],
                    document_type=row["document_type"],
                    product_name=row["product_name"],
                    product_version=row["product_version"],
                    privacy_level=row["privacy_level"] or "public",
                    file_size=row["file_size"],
                    chunk_count=row["chunk_count"],
                    processed_at=row["processed_at"].isoformat() if row["processed_at"] else None,
                    created_at=row["created_at"].isoformat(),
                )
            )

        cursor.close()
        conn.close()

        has_more = (request.offset + len(documents)) < total_count

        return DocumentListResponse(
            documents=documents, total_count=total_count, offset=request.offset, limit=request.limit, has_more=has_more
        )
    except Exception:
        # Fallback to mock data if database connection fails
        mock_documents = [
            {
                "id": 1,
                "file_name": "technical_manual.pdf",
                "title": "Technical Service Manual",
                "document_type": "manual",
                "product_name": "Technical Service Assistant",
                "product_version": "1.0.0",
                "privacy_level": "public",
                "file_size": 2048576,
                "chunk_count": 45,
                "processed_at": "2024-01-01T12:00:00Z",
                "created_at": "2024-01-01T10:00:00Z",
            },
            {
                "id": 2,
                "file_name": "user_guide.pdf",
                "title": "User Guide",
                "document_type": "guide",
                "product_name": "Technical Service Assistant",
                "product_version": "1.0.0",
                "privacy_level": "public",
                "file_size": 1536000,
                "chunk_count": 32,
                "processed_at": "2024-01-01T13:00:00Z",
                "created_at": "2024-01-01T11:00:00Z",
            },
            {
                "id": 3,
                "file_name": "api_reference.pdf",
                "title": "API Reference Documentation",
                "document_type": "reference",
                "product_name": "Technical Service Assistant",
                "product_version": "1.0.0",
                "privacy_level": "private",
                "file_size": 1024000,
                "chunk_count": 28,
                "processed_at": "2024-01-01T14:00:00Z",
                "created_at": "2024-01-01T12:00:00Z",
            },
        ]

        # Apply same filtering logic as above
        if request.search_term:
            search_lower = request.search_term.lower()
            mock_documents = [
                d
                for d in mock_documents
                if search_lower in d["file_name"].lower() or (d["title"] and search_lower in d["title"].lower())
            ]

        if request.document_type:
            mock_documents = [d for d in mock_documents if d["document_type"] == request.document_type]

        if request.product_name:
            mock_documents = [d for d in mock_documents if d["product_name"] == request.product_name]

        if request.privacy_level:
            mock_documents = [d for d in mock_documents if d["privacy_level"] == request.privacy_level]

        reverse = request.sort_order.lower() == "desc"
        if request.sort_by == "file_name":
            mock_documents.sort(key=lambda x: x["file_name"], reverse=reverse)
        elif request.sort_by == "chunk_count":
            mock_documents.sort(key=lambda x: x["chunk_count"], reverse=reverse)
        elif request.sort_by == "processed_at":
            mock_documents.sort(key=lambda x: x["processed_at"] or "", reverse=reverse)
        else:
            mock_documents.sort(key=lambda x: x["created_at"], reverse=reverse)

        total_count = len(mock_documents)
        start_idx = request.offset
        end_idx = start_idx + request.limit
        paginated_documents = mock_documents[start_idx:end_idx]
        has_more = end_idx < total_count

        return DocumentListResponse(
            documents=[DocumentInfo(**doc) for doc in paginated_documents],
            total_count=total_count,
            offset=request.offset,
            limit=request.limit,
            has_more=has_more,
        )


@app.get("/api/documents", response_model=DocumentListResponse)
def get_documents(limit: int = 20, offset: int = 0):
    """Get documents (GET version for backward compatibility)."""
    request = DocumentListRequest(limit=limit, offset=offset, sort_by="created_at", sort_order="desc")
    return list_documents(request)


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Test endpoint
@app.get("/api/test")
def test_endpoint():
    return {"message": "test endpoint works"}


# Question analytics endpoints
print("Loading question analytics endpoints")


class QuestionStatsResponse(BaseModel):
    total_questions: int
    unique_questions: int
    avg_response_time: float
    avg_quality_score: float
    top_categories: List[Dict[str, Any]]
    recent_questions: List[Dict[str, Any]]


class QuestionDetailResponse(BaseModel):
    question_hash: str
    canonical_question: str
    category: str
    usage_count: int
    avg_response_time: float
    avg_quality_score: float
    positive_feedback: int
    negative_feedback: int
    last_used: str
    unique_users: int
    recent_usage: List[Dict[str, Any]]


@app.get("/api/admin/question-stats", response_model=QuestionStatsResponse)
def get_question_stats(limit: int = 10, authorization: Optional[str] = Header(None)):
    """Get overall question statistics."""
    # Basic admin check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = _user_from_authorization(authorization)
    if user.role_name != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Overall stats
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_questions,
                COUNT(DISTINCT question_pattern_id) as unique_questions,
                AVG(response_time_ms) as avg_response_time,
                AVG(response_quality_score) as avg_quality_score
            FROM question_usage
        """
        )
        overall_stats = cursor.fetchone()

        # Top categories
        cursor.execute(
            """
            SELECT
                qp.category,
                COUNT(*) as usage_count,
                AVG(qu.response_time_ms) as avg_response_time
            FROM question_patterns qp
            JOIN question_usage qu ON qp.id = qu.question_pattern_id
            GROUP BY qp.category
            ORDER BY usage_count DESC
            LIMIT %s
        """,
            [limit],
        )
        top_categories = cursor.fetchall()

        # Recent questions
        cursor.execute(
            """
            SELECT
                qp.canonical_question,
                qp.category,
                qu.created_at,
                qu.response_time_ms,
                qu.response_quality_score
            FROM question_usage qu
            JOIN question_patterns qp ON qu.question_pattern_id = qp.id
            ORDER BY qu.created_at DESC
            LIMIT %s
        """,
            [limit],
        )
        recent_questions = cursor.fetchall()

        cursor.close()
        conn.close()

        return QuestionStatsResponse(
            total_questions=overall_stats["total_questions"] or 0,
            unique_questions=overall_stats["unique_questions"] or 0,
            avg_response_time=overall_stats["avg_response_time"] or 0.0,
            avg_quality_score=overall_stats["avg_quality_score"] or 0.0,
            top_categories=[dict(cat) for cat in top_categories],
            recent_questions=[dict(q) for q in recent_questions],
        )

    except Exception as e:
        logger.error(f"Error getting question stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve question statistics")


@app.get("/api/admin/question-stats/{question_hash}", response_model=QuestionDetailResponse)
def get_question_detail(question_hash: str, limit: int = 10, authorization: Optional[str] = Header(None)):
    """Get detailed statistics for a specific question pattern."""
    # Basic admin check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = _user_from_authorization(authorization)
    if user.role_name != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Question pattern details
        cursor.execute(
            """
            SELECT * FROM question_statistics WHERE question_hash = %s
        """,
            [question_hash],
        )
        pattern_stats = cursor.fetchone()

        if not pattern_stats:
            raise HTTPException(status_code=404, detail="Question pattern not found")

        # Recent usage
        cursor.execute(
            """
            SELECT
                qu.question_text,
                qu.response_time_ms,
                qu.response_quality_score,
                qu.user_feedback,
                qu.search_method,
                qu.created_at,
                u.email as user_email
            FROM question_usage qu
            JOIN question_patterns qp ON qu.question_pattern_id = qp.id
            LEFT JOIN users u ON qu.user_id = u.id
            WHERE qp.question_hash = %s
            ORDER BY qu.created_at DESC
            LIMIT %s
        """,
            [question_hash, limit],
        )
        recent_usage = cursor.fetchall()

        cursor.close()
        conn.close()

        return QuestionDetailResponse(
            question_hash=pattern_stats["question_hash"],
            canonical_question=pattern_stats["canonical_question"],
            category=pattern_stats["category"],
            usage_count=pattern_stats["usage_count"],
            avg_response_time=pattern_stats["avg_response_time"],
            avg_quality_score=pattern_stats["avg_quality_score"],
            positive_feedback=pattern_stats["positive_feedback"],
            negative_feedback=pattern_stats["negative_feedback"],
            last_used=pattern_stats["last_used"].isoformat() if pattern_stats["last_used"] else None,
            unique_users=pattern_stats["unique_users"],
            recent_usage=[dict(usage) for usage in recent_usage],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting question detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve question details")


@app.post("/api/feedback")
def submit_feedback(
    message_id: int, rating: str, comment: Optional[str] = None, authorization: Optional[str] = Header(None)
):
    """Submit user feedback for a question response."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = _user_from_authorization(authorization)

    if rating not in ["positive", "negative", "neutral"]:
        raise HTTPException(status_code=400, detail="Invalid rating")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Update the message with feedback
        cursor.execute(
            """
            UPDATE messages
            SET citations = jsonb_set(citations, '{feedback}', %s)
            WHERE id = %s AND conversation_id IN (
                SELECT id FROM conversations WHERE user_id = %s
            )
        """,
            [json.dumps({"rating": rating, "comment": comment, "user_id": user.id}), message_id, user.id],
        )

        if cursor.rowcount == 0:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Message not found or access denied")

        # Also update question_usage if this message is part of tracked questions
        cursor.execute(
            """
            UPDATE question_usage
            SET user_feedback = %s
            WHERE conversation_id = (SELECT conversation_id FROM messages WHERE id = %s)
            AND question_text = (SELECT content FROM messages WHERE id = %s AND role = 'user')
        """,
            [rating, message_id, message_id],
        )

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Feedback submitted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8008)
