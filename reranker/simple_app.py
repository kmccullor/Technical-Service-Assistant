"""
Minimal Technical Service Assistant API
Just the basic chat endpoints to get the frontend working.
"""

from typing import List, Optional
import uvicorn
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Header
from pydantic import BaseModel, Field


class RAGChatRequest(BaseModel):
    """RAG-enhanced chat request following Pydantic AI patterns."""
    query: str = Field(..., description="User question or prompt")
    use_context: bool = Field(True, description="Whether to retrieve document context")
    max_context_chunks: int = Field(10, description="Number of context chunks to retrieve")
    model: str = Field("mistral:7b", description="Ollama model to use for generation")
    privacy_filter: str = Field("public", description="Privacy filter: 'public', 'private', or 'all'")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Generation temperature")
    max_tokens: int = Field(512, ge=64, le=2048, description="Maximum tokens to generate")


class RAGChatResponse(BaseModel):
    """RAG-enhanced chat response with context metadata."""
    response: str = Field(..., description="Generated response text")
    context_used: List[str] = Field(default_factory=list, description="Retrieved context chunks")
    model: str = Field(..., description="Model used for generation")
    context_retrieved: bool = Field(..., description="Whether context was retrieved and used")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in RAG response (0-1)")
    search_method: str = Field("rag", description="Search method used: 'rag', 'web', or 'hybrid'")
    fusion_metadata: Optional[dict] = Field(
        default=None, description="Metadata about fusion when search_method='fusion'"
    )
    source_metadata: Optional[List[dict]] = Field(
        default=None, description="Metadata for source documents with download links"
    )
    event_id: Optional[int] = Field(default=None, description="Analytics event id for feedback linkage")
    tokens_input: Optional[int] = Field(default=None, description="Number of input tokens processed")
    tokens_output: Optional[int] = Field(default=None, description="Number of output tokens generated")
    tokens_total: Optional[int] = Field(default=None, description="Total tokens (input + output)")
    tokens_per_second: Optional[float] = Field(default=None, description="Token generation rate (tokens/second)")
    response_time_ms: Optional[int] = Field(default=None, description="Total response time in milliseconds")


app = FastAPI(
    title="Technical Service Assistant API",
    description="API for RAG system with basic chat endpoints",
    version="1.0.0",
)


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "pgvector"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "vector_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


@app.post("/api/chat", response_model=RAGChatResponse)
def chat_endpoint(request: RAGChatRequest):
    """Chat endpoint that returns a simple response."""
    return RAGChatResponse(
        response=f"I received your query: '{request.query}'. This is a placeholder response.",
        model=request.model,
        context_retrieved=False,
        confidence_score=0.5,
        search_method="placeholder"
    )


# RAG Chat endpoint that matches frontend expectations
class RAGChatRequestV2(BaseModel):
    query: str = Field(..., description="User question or prompt")
    use_web_fallback: bool = Field(True, description="Whether to use web fallback")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Generation temperature")
    max_tokens: int = Field(512, ge=64, le=2048, description="Maximum tokens to generate")
    confidence_threshold: float = Field(0.3, ge=0.0, le=1.0, description="Confidence threshold")


class RAGChatResponseV2(BaseModel):
    response: str = Field(..., description="Generated response text")
    context_used: List[str] = Field(default_factory=list, description="Retrieved context chunks")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in RAG response (0-1)")
    search_method: str = Field("rag", description="Search method used: 'rag', 'web', or 'hybrid'")
    source_metadata: Optional[List[dict]] = Field(default=None, description="Metadata for source documents")


@app.post("/api/rag-chat")
def rag_chat_endpoint(request: RAGChatRequestV2):
    """RAG chat endpoint that matches frontend expectations with streaming response."""
    from fastapi.responses import StreamingResponse
    import json
    import asyncio

    async def generate():
        # Send sources first
        sources_data = {
            "context_used": ["This is placeholder context chunk 1", "This is placeholder context chunk 2"],
            "confidence_score": 0.7,
            "search_method": "rag",
            "source_metadata": [
                {
                    "title": "Placeholder Document 1",
                    "file_name": "placeholder1.pdf",
                    "document_type": "manual",
                    "product_name": "Technical Service Assistant",
                    "page_number": 1,
                    "section_title": "Introduction"
                },
                {
                    "title": "Placeholder Document 2",
                    "file_name": "placeholder2.pdf",
                    "document_type": "guide",
                    "product_name": "Technical Service Assistant",
                    "page_number": 5,
                    "section_title": "Getting Started"
                }
            ]
        }

        # Send sources
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources_data['context_used'], 'confidence': sources_data['confidence_score'], 'method': sources_data['search_method']})}\n\n"

        # Stream the response text in chunks
        response_text = f"I received your query: '{request.query}'. This is a placeholder RAG response with temperature {request.temperature} and max tokens {request.max_tokens}."

        # Split response into chunks for streaming
        chunk_size = 20
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'token': chunk})}\n\n"
            await asyncio.sleep(0.01)  # Small delay to simulate streaming

        # Send completion
        yield f"data: {json.dumps({'type': 'done', 'messageId': 'temp-id'})}\n\n"

    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/api/conversations")
def get_conversations(limit: int = 30):
    """Get list of conversations (stub implementation)."""
    return {"conversations": [], "total": 0, "limit": limit}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/test")
def test_endpoint():
    """Test endpoint."""
    return {"message": "test ok"}


# Basic auth endpoints for login functionality
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: dict


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


@app.post("/api/auth/login", response_model=TokenResponse)
def login_endpoint(request: LoginRequest):
    """Basic login endpoint that accepts any credentials for testing."""
    # For now, accept any login and return a mock token
    # In production, this would validate against the database

    # Parse email to create dynamic user info
    email_parts = request.email.split('@')
    username = email_parts[0] if email_parts else "user"
    name_parts = username.replace('.', ' ').replace('_', ' ').split()
    first_name = name_parts[0].capitalize() if name_parts else "User"
    last_name = name_parts[1].capitalize() if len(name_parts) > 1 else "Test"

    # Assign role based on email
    if request.email in ["kevin.mccullor@xylem.com", "admin@employee.com"] or "admin" in request.email.lower():
        role_id = 1
        role_name = "admin"
    else:
        role_id = 2
        role_name = "employee"

    user_data = {
        "id": hash(request.email) % 10000,  # Simple ID based on email
        "email": request.email,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": f"{first_name} {last_name}",
        "role_id": role_id,
        "role_name": role_name,
        "status": "active",
        "verified": True,
        "last_login": None,
        "is_active": True,
        "is_locked": False,
        "password_change_required": False,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }

    return TokenResponse(
        access_token="mock_access_token_" + request.email,
        refresh_token="mock_refresh_token_" + request.email,
        expires_in=3600,  # 1 hour
        user=user_data
    )


@app.get("/api/auth/health")
def auth_health():
    """Auth health check endpoint."""
    return {"status": "healthy", "service": "auth"}


@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current user profile (mock implementation)."""
    # In a real implementation, this would get the user from the session/token
    # For mock, parse email from Authorization header
    email = "admin@employee.com"  # default
    if authorization and authorization.startswith("Bearer mock_access_token_"):
        token = authorization.replace("Bearer mock_access_token_", "")
        if "@" in token:
            email = token

    # Create user data based on email
    email_parts = email.split('@')
    username = email_parts[0] if email_parts else "user"
    name_parts = username.replace('.', ' ').replace('_', ' ').split()
    first_name = name_parts[0].capitalize() if name_parts else "User"
    last_name = name_parts[1].capitalize() if len(name_parts) > 1 else "Test"

    # Assign role based on email
    if email in ["kevin.mccullor@xylem.com", "admin@employee.com"] or "admin" in email.lower():
        role_id = 1
        role_name = "admin"
    else:
        role_id = 2
        role_name = "employee"

    return UserResponse(
        id=hash(email) % 10000,
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
        updated_at="2024-01-01T00:00:00Z"
    )


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

        return UserListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[UserListItem(**dict(user)) for user in users]
        )
    except Exception as e:
        # Fallback to mock data if database connection fails
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
                "permissions": ["read", "write", "delete", "admin"],
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8008)