"""
Minimal Technical Service Assistant API
Just the basic chat endpoints to get the frontend working.
"""

from typing import List, Optional
import uvicorn
import os
import sys
import psycopg2
import hashlib

# Add /app to Python path for imports
sys.path.insert(0, '/app')
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
import json
import asyncio
import logging
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Import auth endpoints
from rbac_endpoints import router as auth_router
from cache import get_db_connection
from rag_chat import RAGChatService, add_rag_endpoints
# from admin_endpoints import router as admin_router  # Temporarily commented out due to import issues

app = FastAPI(
    title="Technical Service Assistant API",
    description="API for RAG system with basic chat endpoints",
    version="1.0.0",
)

# Initialize RAG service
rag_service = RAGChatService()

# Include RAG endpoints
add_rag_endpoints(app)

# Include auth endpoints
app.include_router(auth_router)
# app.include_router(admin_router)  # Temporarily commented out due to import issues


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
    # Use first 8 hex characters to stay within 32-bit signed int range.
    return int(digest[:8], 16)


def _user_from_authorization(authorization: Optional[str]) -> UserResponse:
    email = "admin@employee.com"
    if authorization and authorization.startswith("Bearer mock_access_token_"):
        token = authorization.replace("Bearer mock_access_token_", "")
        if "@" in token:
            email = token

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

    user_id = _deterministic_user_id(email)

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

    async def generate():
        try:
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

            rag_request = RAGChatRequest(
                query=request.message,
                use_context=True,
                max_context_chunks=5,
                model="mistral:7b",
                temperature=0.2,
                max_tokens=500,
            )

            rag_response = await rag_service.chat(rag_request)

            sources_data = []
            if rag_response.web_sources:
                for source in rag_response.web_sources[:3]:
                    content_value = source.get("content", "") or ""
                    snippet = (
                        content_value[:200] + "..."
                        if len(content_value) > 200
                        else content_value
                    )
                    sources_data.append(
                        {
                            "title": source.get("title", "Web Source"),
                            "snippet": snippet,
                            "url": source.get("url", ""),
                            "score": source.get("score", 0.8),
                        }
                    )
            elif rag_response.context_used:
                for index, chunk in enumerate(rag_response.context_used[:3]):
                    snippet = chunk[:200] + "..." if len(chunk) > 200 else chunk
                    sources_data.append(
                        {
                            "title": f"RAG Context {index + 1}",
                            "snippet": snippet,
                            "score": 0.8 - (index * 0.1),
                        }
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
            for word in response_text.split():
                yield f"data: {json.dumps({'type': 'token', 'token': word + ' '})}\n\n"
                await asyncio.sleep(0.05)

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

# Conversation management endpoints
@app.get("/api/conversations", response_model=ConversationListResponse)
def list_conversations(limit: int = 20, offset: int = 0, authorization: Optional[str] = Header(None)):
    """List conversations for the authenticated user."""
    # Basic auth check
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = _user_from_authorization(authorization)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute(
                "SELECT COUNT(*) as total FROM conversations WHERE user_id = %s",
                [user.id],
            )
            count_result = cursor.fetchone()
            raw_total = count_result["total"] if count_result else 0
            try:
                total = int(raw_total)
            except (TypeError, ValueError):
                total = 0

            conversations_query = """
                SELECT
                    c.id,
                    c.title,
                    c.created_at,
                    c.updated_at,
                    COALESCE(MAX(m.created_at), c.updated_at, c.created_at) AS last_message_at,
                    COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = %s
                GROUP BY c.id, c.title, c.created_at, c.updated_at
                ORDER BY COALESCE(MAX(m.created_at), c.updated_at, c.created_at) DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(conversations_query, [user.id, limit, offset])
            conversations_data = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        conversations = []
        for conv in conversations_data:
            created_at_value = conv.get("created_at")
            last_message_value = conv.get("last_message_at") or conv.get("updated_at")
            created_at_str = (
                created_at_value.isoformat()
                if hasattr(created_at_value, "isoformat")
                else created_at_value
            )
            updated_at_str = (
                last_message_value.isoformat()
                if hasattr(last_message_value, "isoformat")
                else last_message_value
            )
            conversations.append(ConversationSummary(
                id=conv["id"],
                title=conv["title"],
                createdAt=created_at_str,
                updatedAt=updated_at_str,
            ))

        has_more = (offset + len(conversations)) < total

        return ConversationListResponse(
            conversations=conversations,
            total=total,
            hasMore=has_more
        )

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        # Fallback to empty list
        return ConversationListResponse(
            conversations=[],
            total=0,
            hasMore=False
        )


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
            messages.append(MessageInfo(
                id=msg["id"],
                role=msg["role"],
                content=msg["content"],
                citations=msg["citations"],
                createdAt=created_at_value.isoformat() if hasattr(created_at_value, "isoformat") else created_at_value,
            ))

        # Calculate updated_at as the latest message time
        timestamps = [
            msg.get("created_at") for msg in messages_data if hasattr(msg.get("created_at"), "isoformat")
        ]
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
            messages=messages
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
            delete_query = "DELETE FROM conversations WHERE id = %s AND user_id = %s"
            cursor.execute(delete_query, [conversation_id, user.id])

            if cursor.rowcount == 0:
                conn.rollback()
                raise HTTPException(status_code=404, detail="Conversation not found")

            conn.commit()
        finally:
            cursor.close()
            conn.close()

        return {"message": f"Conversation {conversation_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


@app.get("/health")
def health():
    """General health check endpoint."""
    return {"status": "healthy", "service": "reranker"}

@app.get("/api/auth/health")
def auth_health():
    """Auth health check endpoint."""
    return {"status": "healthy", "service": "auth"}


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
            if 'created_at' in user_dict and user_dict['created_at']:
                user_dict['created_at'] = user_dict['created_at'].isoformat()
            if 'updated_at' in user_dict and user_dict['updated_at']:
                user_dict['updated_at'] = user_dict['updated_at'].isoformat()
            processed_users.append(user_dict)

        try:
            items = [UserListItem(**user) for user in processed_users]
            return UserListResponse(
                total=total,
                limit=limit,
                offset=offset,
                items=items
            )
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
                "updated_at": "2024-01-01T00:00:00Z"
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
                "updated_at": "2024-01-01T00:00:00Z"
            }
        ]

        if search:
            mock_users = [u for u in mock_users if search.lower() in u["email"].lower() or search.lower() in u["first_name"].lower() or search.lower() in u["last_name"].lower()]

        total = len(mock_users)
        items = mock_users[offset:offset + limit]

        return UserListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[UserListItem(**user) for user in items]
        )


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
    except Exception as e:
        # Fallback to mock data
        mock_roles = [
            {
                "id": 1,
                "name": "admin",
                "description": "Administrator with full access",
                "permissions": ["read", "write", "admin"],
                "system": True,
                "user_count": 1
            },
            {
                "id": 2,
                "name": "employee",
                "description": "Standard employee access",
                "permissions": ["read", "write"],
                "system": True,
                "user_count": 1
            }
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
            "is_active": True
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
            "is_active": True
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
            documents.append(DocumentInfo(
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
            ))

        cursor.close()
        conn.close()

        has_more = (request.offset + len(documents)) < total_count

        return DocumentListResponse(
            documents=documents,
            total_count=total_count,
            offset=request.offset,
            limit=request.limit,
            has_more=has_more
        )
    except Exception as e:
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
                "created_at": "2024-01-01T10:00:00Z"
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
                "created_at": "2024-01-01T11:00:00Z"
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
                "created_at": "2024-01-01T12:00:00Z"
            }
        ]

        # Apply same filtering logic as above
        if request.search_term:
            search_lower = request.search_term.lower()
            mock_documents = [d for d in mock_documents if
                             search_lower in d["file_name"].lower() or
                             (d["title"] and search_lower in d["title"].lower())]

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
            has_more=has_more
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8008)
