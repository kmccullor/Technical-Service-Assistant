# --- RAGChatRequest and RAGChatResponse must be defined before any function/type hint that uses them ---
"""
Minimal Technical Service Assistant API
Just the basic chat endpoints to get the frontend working.
"""

from typing import List, Optional, Tuple
import time
import os
import asyncio
import httpx
import uvicorn
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Import admin endpoints
from admin_endpoints import router as admin_router

# Import local modules
from config import get_settings
from utils.logging_config import setup_logging
from utils.auth_system import AuthManager, get_auth_manager, User
from utils.rbac_models import PermissionLevel
from utils.exceptions import *
from utils.metrics import metrics_collector
from utils.terminology_manager import get_terminology_context

# Database and search
from pdf_processor.pdf_utils import (
    get_db_connection,
    estimate_tokens,
    calculate_tokens_per_second,
    _aggregate_rows_to_dict,
)

# Search and RAG
from reranker.search import (
    search_documents_core,
    RerankRequest,
    build_rag_prompt,
    record_search_event,
)
from reranker.ollama_client import get_ollama_client, OllamaInstance
from reranker.reasoning_engine import get_reasoning_orchestrator
from reranker.web_search import (
    get_cached_web_results,
    store_web_results,
    WebSearchResult,
)
from reranker.intelligent_router import (
    classify_and_optimize_query,
    QueryAnalysis,
    QuestionType,
)
from reranker.enhanced_search import enhanced_search, iterative_research_until_confident
from reranker.performance_monitor import performance_context

# Models and responses
from reranker.models import (
    RAGChatResponse,
    ModelSelectionResponse,
    ModelSelectionRequest,
    ReasoningResponse,
    ReasoningRequest,
    HybridSearchRequest,
    QueryClassification,
    DocumentStatsResponse,
    DocumentListResponse,
    DocumentListRequest,
    DocumentInfo,
    TempDocProcessRequest,
    TempAnalysisResponse,
    TempAnalysisRequest,
)

# Commands and corrections
from reranker.chat_commands import handle_chat_command
from reranker.corrections import get_correction_for_question

# Constants
from reranker.constants import (
    TECHNICAL_SERVICE_SYSTEM_PROMPT,
    OLLAMA_HEALTH,
    CONTENT_TYPE_LATEST,
    MODEL_SELECTION_COUNT,
)

# Prometheus
from prometheus_client import generate_latest

# Setup logging
settings = get_settings()
logger = setup_logging(
    program_name="reranker",
    log_level=getattr(settings, "log_level", "INFO"),
    console_output=True,
)


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



def rag_chat(
    request: RAGChatRequest, instance_url: Optional[str] = None, current_user: Optional[User] = None
):
    """RAG-enhanced chat endpoint combining retrieval and generation."""
    start_time = time.time()
    try:
        # Check for chat commands first - bypass all other processing
        command_response = handle_chat_command(request.query)
        if command_response:
            return command_response

        # Check for a correction before generating a new answer
        conn = get_db_connection()
        correction = get_correction_for_question(conn, request.query)
        conn.close()
        if correction:
            logger.info(f"Correction found for query: {request.query}")
            return RAGChatResponse(
                response=correction.corrected_answer,
                context_used=[],
                model="correction",
                context_retrieved=False,
                confidence_score=1.0,
                search_method="correction",
                tokens_input=0,
                tokens_output=estimate_tokens(correction.corrected_answer),
                tokens_total=estimate_tokens(correction.corrected_answer),
                tokens_per_second=None,
                response_time_ms=0,
            )

        context_chunks = []
        if request.use_context:
            # Use existing search logic to get context
            # Enforce privacy filter: public users limited to public only
            effective_privacy = request.privacy_filter
            if current_user:
                if current_user.role_id not in (1, 2) and effective_privacy in ("all", "private"):
                    effective_privacy = "public"
            else:
                effective_privacy = "public"

            search_req = RerankRequest(
                query=request.query, passages=[], top_k=request.max_context_chunks, privacy_filter=effective_privacy
            )
            search_resp = search_documents_core(search_req, current_user)
            context_chunks = search_resp.reranked
            search_resp.source_metadata
            logger.info(f"Retrieved {len(context_chunks)} context chunks for RAG query")

        # Build prompt with context
        prompt = build_rag_prompt(request.query, context_chunks)

        # Generate response using Ollama with proper instance routing
        try:
            client = get_ollama_client(instance_url)
            response = client.generate(
                model=request.model,
                prompt=prompt,
                options={"temperature": request.temperature, "num_predict": request.max_tokens},
            )
            response_text = response.get("response", "No response generated")
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

        # Calculate token performance metrics
        generation_time = time.time() - start_time
        tokens_input = estimate_tokens(prompt)
        tokens_output = estimate_tokens(response_text)
        tokens_total = tokens_input + tokens_output
        tokens_per_second = calculate_tokens_per_second(tokens_output, generation_time)

        # Calculate confidence score based on context relevance
        confidence_score = calculate_rag_confidence(request.query, context_chunks, response_text)

        resp = RAGChatResponse(
            response=response_text,
            context_used=context_chunks,
            model=request.model,
            context_retrieved=len(context_chunks) > 0,
            confidence_score=confidence_score,
            search_method="rag",
            source_metadata=search_resp.source_metadata,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_total=tokens_total,
            tokens_per_second=tokens_per_second,
            response_time_ms=int(generation_time * 1000),
        )
        resp.event_id = record_search_event(
            query=request.query,
            search_method="rag",
            confidence_score=confidence_score,
            rag_confidence=confidence_score,
            classification_type=None,
            strategy="rag_only",
            response_time_ms=None,
            context_chunk_count=len(context_chunks),
            web_result_count=0,
            fused_count=0,
            model_used=request.model,
        )
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG chat error: {e}")
        raise HTTPException(status_code=500, detail=f"RAG chat failed: {str(e)}")


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


@app.post("/api/auth/login", response_model=TokenResponse)
def login_endpoint(request: LoginRequest):
    """Basic login endpoint that accepts any credentials for testing."""
    # For now, accept any login and return a mock token
    # In production, this would validate against the database
    user_data = {
        "id": 1,
        "email": request.email,
        "first_name": "Test",
        "last_name": "User",
        "full_name": "Test User",
        "role_id": 2,  # employee role
        "role_name": "employee",
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
def get_current_user():
    """Get current user profile (mock implementation)."""
    return UserResponse(
        id=1,
        email="test@example.com",
        first_name="Test",
        last_name="User",
        full_name="Test User",
        role_id=2,
        role_name="employee",
        status="active",
        verified=True,
        last_login=None,
        is_active=True,
        is_locked=False,
        password_change_required=False,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z"
    )


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


@app.get("/health")
def health():
    # basic health only; extended will be separate
    return {"status": "ok"}


# @app.get("/health/details", dependencies=[Depends(require_api_key)])
def health_details():
    details = {"status": "ok"}
    # DB check
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.close()
        details["db"] = "ok"
    except Exception as e:
        details["db"] = f"error: {e}"
        details["status"] = "degraded"
    # Reranker model check
    try:
        _ = get_reranker()
        details["reranker_model"] = settings.rerank_model
    except Exception as e:
        details["reranker_model"] = f"error: {e}"
        details["status"] = "degraded"
    return details


@app.get("/api/test-simple")
async def test_simple():
    """Simple test endpoint."""
    return {"status": "test_ok", "message": "Simple endpoint working"}


# Initialize instances for intelligent routing with specialized models
# Use container names and internal port (11434) for inter-container communication
instances = [
    OllamaInstance("ollama-server-1", 11434, "ollama-server-1-chat-qa"),  # Instance 1: Chat/QA
    OllamaInstance("ollama-server-2", 11434, "ollama-server-2-code-technical"),  # Instance 2: Code/Technical
    OllamaInstance("ollama-server-3", 11434, "ollama-server-3-reasoning-math"),  # Instance 3: Reasoning/Math
    OllamaInstance("ollama-server-4", 11434, "ollama-server-4-embeddings-search"),  # Instance 4: Embeddings/Search
]


def classify_question(query: str) -> QuestionType:
    """Enhanced question classification for optimal model selection."""
    query_lower = query.lower()

    # Technical/system configuration keywords
    if any(
        term in query_lower
        for term in [
            "install",
            "config",
            "setup",
            "rni",
            "active directory",
            "server",
            "network",
            "deployment",
            "troubleshoot",
        ]
    ):
        return QuestionType.TECHNICAL

    # Code/programming keywords
    elif any(
        term in query_lower
        for term in [
            "code",
            "script",
            "function",
            "programming",
            "python",
            "javascript",
            "sql",
            "algorithm",
            "debug",
            "syntax",
        ]
    ):
        return QuestionType.CODE

    # Mathematical/calculation keywords
    elif any(
        term in query_lower
        for term in [
            "calculate",
            "math",
            "equation",
            "formula",
            "solve",
            "statistics",
            "probability",
            "algebra",
            "geometry",
        ]
    ):
        return QuestionType.MATH

    # Creative writing keywords
    elif any(
        term in query_lower
        for term in ["write", "story", "creative", "poem", "essay", "brainstorm", "ideas", "imagine", "describe"]
    ):
        return QuestionType.CREATIVE

    # Casual conversation keywords
    elif any(
        term in query_lower
        for term in ["hello", "hi", "thanks", "how are you", "good morning", "please", "sorry", "goodbye"]
    ):
        return QuestionType.CHAT

    # Default to factual for informational queries
    else:
        return QuestionType.FACTUAL


def select_model_for_question(question_type: QuestionType) -> Tuple[str, int]:
    """Select best model and instance for question type using specialized distribution.

    Returns:
        Tuple[str, int]: (model_name, instance_index) for specialized routing

    Model specialization per instance:
    - Instance 1 (Chat/QA): mistral:7b, llama3.1:8b, nomic-embed-text:v1.5
    - Instance 2 (Code/Technical): gemma2:2b, phi3:mini, mistral:7b
    - Instance 3 (Reasoning/Math): llama3.2:3b, llama3.1:8b
    - Instance 4 (Embeddings/Search): nomic-embed-text:v1.5, llama3.2:1b, gemma2:2b
    """
    if question_type == QuestionType.CODE:
        # Code questions -> Instance 2 (specialized for coding)
        return "phi3:mini", 1  # Index 1 = ollama-server-2

    elif question_type == QuestionType.TECHNICAL:
        # Technical questions -> Instance 2 (technical specialization)
        return "mistral:7b", 1

    elif question_type == QuestionType.MATH:
        # Math/reasoning -> Instance 3 (reasoning specialization)
        return "llama3.2:3b", 2  # Index 2 = ollama-server-3

    elif question_type == QuestionType.CREATIVE:
        # Creative tasks -> Instance 3 (reasoning capabilities)
        return "llama3.1:8b", 2

    elif question_type == QuestionType.FACTUAL:
        # Factual questions -> Instance 1 (general chat/QA)
        return "mistral:7b", 0  # Index 0 = ollama-server-1

    else:  # QuestionType.CHAT
        # General chat -> Instance 1 (chat specialization)
        return "llama3.1:8b", 0


async def select_best_instance(instances: List[OllamaInstance]) -> OllamaInstance:
    """Select the best available Ollama instance based on health and load."""
    import random
    import time

    # Simple health check for each instance
    healthy_instances = []
    for instance in instances:
        try:
            # Quick health check - try to connect to the instance
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{instance.url}/api/tags")
                if response.status_code == 200:
                    instance.healthy = True
                    instance.last_check = time.time()
                    instance.response_time = response.elapsed.total_seconds()
                    healthy_instances.append(instance)
                else:
                    instance.healthy = False
        except Exception:
            instance.healthy = False

    if not healthy_instances:
        # Fallback to primary instance if none are healthy
        logger.warning("No healthy instances found, falling back to primary")
        return instances[0]

    # Simple round-robin selection among healthy instances
    # In a production system, this could be more sophisticated
    return random.choice(healthy_instances)


@app.post("/api/intelligent-route", response_model=ModelSelectionResponse)
async def intelligent_route(request: ModelSelectionRequest):
    """Get optimal model and instance selection for a query using specialized distribution."""
    start_time = time.time()

    try:
        question_type = classify_question(request.query)
        selected_model, instance_index = select_model_for_question(question_type)

        # Get the specialized instance for this question type
        target_instance = instances[instance_index]

        # Health check the target instance
        health_check_start = time.time()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{target_instance.url}/api/tags")
                health_check_time = time.time() - health_check_start

                # Record instance health metrics
                is_healthy = response.status_code == 200
                metrics_collector.record_ollama_health(
                    instance_name=target_instance.name,
                    instance_url=target_instance.url,
                    is_healthy=is_healthy,
                    response_time=health_check_time,
                )

                if not is_healthy:
                    # Fallback to general instance selection if specialized instance is unhealthy
                    logger.warning(f"Specialized instance {target_instance.name} unhealthy, falling back")
                    target_instance = await select_best_instance(instances)
                    selected_model = "mistral:7b"  # Safe fallback model

        except Exception as e:
            logger.warning(f"Health check failed for {target_instance.name}, using fallback: {e}")

            # Record unhealthy status
            metrics_collector.record_ollama_health(
                instance_name=target_instance.name, instance_url=target_instance.url, is_healthy=False
            )

            target_instance = await select_best_instance(instances)
            selected_model = "mistral:7b"

        # Record routing metrics
        routing_duration = time.time() - start_time

        # Record Prometheus metrics
        MODEL_SELECTION_COUNT.labels(model=selected_model, instance=target_instance.name).inc()

        # Record legacy metrics for compatibility
        metrics_collector.record_model_request(
            model_name=selected_model,
            instance=target_instance.name,
            question_type=question_type.value,
            duration=routing_duration,
            status="success",
        )

        return ModelSelectionResponse(
            selected_model=selected_model,
            selected_instance=target_instance.name,
            instance_url=target_instance.url,
            question_type=question_type,
            reasoning=f"Selected {selected_model} on {target_instance.name} for {question_type.value} question",
            fallback_options=[],
        )
    except Exception as e:
        # Record error metrics
        routing_duration = time.time() - start_time
        metrics_collector.record_model_request(
            model_name="unknown", instance="unknown", question_type="unknown", duration=routing_duration, status="error"
        )

        logger.error(f"Routing error: {e}")
        raise HTTPException(status_code=500, detail=f"Routing failed: {str(e)}")


@app.get("/api/ollama-health")
async def ollama_health():
    """Check real-time health status of all Ollama instances."""
    healthy_count = 0
    instance_statuses = []

    for instance in instances:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{instance.url}/api/tags")
                if response.status_code == 200:
                    instance.healthy = True
                    instance.response_time = response.elapsed.total_seconds()
                    healthy_count += 1

                    # Record healthy instance metrics
                    metrics_collector.record_ollama_health(
                        instance_name=instance.name,
                        instance_url=instance.url,
                        is_healthy=True,
                        response_time=instance.response_time,
                    )

                    status = {
                        "name": instance.name,
                        "url": instance.url,
                        "healthy": True,
                        "response_time_ms": round(instance.response_time * 1000, 2),
                        "models_available": len(response.json().get("models", [])),
                    }
                else:
                    instance.healthy = False

                    # Record unhealthy instance
                    metrics_collector.record_ollama_health(
                        instance_name=instance.name, instance_url=instance.url, is_healthy=False
                    )

                    status = {
                        "name": instance.name,
                        "url": instance.url,
                        "healthy": False,
                        "error": f"HTTP {response.status_code}",
                    }
        except Exception as e:
            instance.healthy = False

            # Record failed instance
            metrics_collector.record_ollama_health(
                instance_name=instance.name, instance_url=instance.url, is_healthy=False
            )

            status = {"name": instance.name, "url": instance.url, "healthy": False, "error": str(e)}

        instance_statuses.append(status)

    # Update system resource metrics
    metrics_collector.update_system_metrics()

    overall_status = "healthy" if healthy_count > 0 else "unhealthy"
    if healthy_count < len(instances):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "healthy_instances": healthy_count,
        "total_instances": len(instances),
        "instances": instance_statuses,
    }


@app.get("/metrics")
async def get_metrics():
    """Expose Prometheus metrics."""
    if not metrics_collector.enabled:
        raise HTTPException(status_code=503, detail="Metrics collection not available")

    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        metrics_data = generate_latest(metrics_collector.registry)
        return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate metrics")


@app.post("/api/reasoning", response_model=ReasoningResponse)
async def process_reasoning(request: ReasoningRequest):
    """
    Advanced reasoning endpoint using chain-of-thought analysis.

    This endpoint provides sophisticated reasoning capabilities including:
    - Chain-of-thought decomposition and analysis
    - Multi-step reasoning with evidence gathering
    - Cross-document synthesis and pattern recognition
    - Complexity-aware processing with adaptive approaches
    """
    try:
        orchestrator = await get_reasoning_orchestrator()
        if orchestrator is None:
            return ReasoningResponse(
                query=request.query,
                reasoning_approach="error",
                final_answer="Reasoning engine not available",
                reasoning_type=request.reasoning_type,
                complexity_level="medium",
                reasoning_steps=[],
                confidence_score=0.0,
                sources_used=[],
                processing_time_ms=0,
                cache_hit=False,
                error_message="Reasoning engine initialization failed",
            )

        result = await orchestrator.process_reasoning_query(
            query=request.query,
            reasoning_type=request.reasoning_type,
            context_documents=request.context_documents,
            max_steps=request.max_steps,
            temperature=request.temperature,
            enable_caching=request.enable_caching,
        )

        return ReasoningResponse(
            query=request.query,
            reasoning_approach=result.get("reasoning_approach", "standard"),
            final_answer=result.get("final_answer", "No answer generated"),
            reasoning_type=request.reasoning_type or result.get("reasoning_type"),
            complexity_level=result.get("complexity_level", "medium"),
            reasoning_steps=result.get("reasoning_steps", []),
            confidence_score=result.get("confidence_score", 0.5),
            sources_used=result.get("sources_used", []),
            processing_time_ms=result.get("processing_time_ms", 0),
            cache_hit=result.get("cache_hit", False),
            error_message=result.get("error_message"),
        )

    except Exception as e:
        logger.error(f"Reasoning processing error: {e}")
        return ReasoningResponse(
            query=request.query,
            reasoning_approach="error",
            final_answer=f"Error processing reasoning request: {str(e)}",
            reasoning_type=request.reasoning_type,
            complexity_level="medium",
            reasoning_steps=[],
            confidence_score=0.0,
            sources_used=[],
            processing_time_ms=0,
            cache_hit=False,
            error_message=str(e),
        )


@app.post("/api/fast-test")
async def fast_test_endpoint(request: dict):
    """Fast test endpoint to validate 15-second performance target."""
    start_time = time.time()

    try:
        query = request.get("query", "Test query")

        # Simple fast response without complex reasoning
        response_text = (
            f"Fast response for: {query}. This is a simple test response that should complete within 2 seconds."
        )

        processing_time = int((time.time() - start_time) * 1000)

        return {
            "success": True,
            "query": query,
            "answer": response_text,
            "processing_time_ms": processing_time,
            "mode": "fast_test",
        }

    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        return {"success": False, "error": str(e), "processing_time_ms": processing_time}


@app.get("/api/status")
async def get_system_status():
    """Get system status and performance metrics."""
    return {
        "status": "healthy",
        "services": {"reranker": "running", "reasoning_engine": "initialized", "performance_mode": "optimized"},
        "performance_targets": {
            "max_response_time": "15 seconds",
            "warning_threshold": "10 seconds",
            "target_response_time": "5 seconds",
        },
    }


def calculate_rag_confidence(
    query: str, context_chunks: List[str], response: str, query_analysis: Optional[QueryAnalysis] = None
) -> float:
    """Calculate confidence score for RAG response with optional enhanced analysis."""
    if not context_chunks:
        return 0.0

    # Use enhanced confidence calculation if query analysis is available
    if query_analysis:
        return enhanced_search.calculate_enhanced_confidence(query, context_chunks, response, query_analysis)

    # Fallback to original confidence calculation
    base_confidence = min(len(context_chunks) / 10.0, 0.6)  # More conservative: max 0.6 confidence

    # Stronger penalty for uncertain language
    uncertain_phrases = [
        "i don't know",
        "not sure",
        "cannot",
        "unable",
        "no information",
        "unclear",
        "apologize",
        "does not contain",
    ]
    response_lower = response.lower()
    uncertainty_penalty = sum(0.3 for phrase in uncertain_phrases if phrase in response_lower)

    # Bonus for longer, detailed responses
    length_bonus = min(len(response) / 1000.0, 0.1)  # Up to 0.1 bonus for very detailed responses

    # Check if query terms appear in context
    query_terms = set(query.lower().split())
    context_text = " ".join(context_chunks).lower()
    term_overlap = len([term for term in query_terms if term in context_text]) / max(len(query_terms), 1)
    relevance_bonus = term_overlap * 0.2

    confidence = max(0.0, min(1.0, base_confidence - uncertainty_penalty + length_bonus + relevance_bonus))

    logger.info(
        f"Confidence calculation: base={base_confidence:.2f}, uncertainty_penalty={uncertainty_penalty:.2f}, "
        f"length_bonus={length_bonus:.2f}, relevance_bonus={relevance_bonus:.2f}, final={confidence:.2f}"
    )

    return confidence
    return confidence


async def search_web(query: str, max_results: int = 10) -> List[WebSearchResult]:
    """Search the web using DuckDuckGo Instant Answer API (with caching)."""
    try:
        # Cache lookup
        cached = get_cached_web_results(query)
        if cached:
            logger.info(f"Cache hit for web query: '{query}'")
            return [WebSearchResult(**r.model_dump()) for r in cached][:max_results]

        headers = {
            "User-Agent": "Technical Service Assistant/1.0 (Privacy-focused search)",
        }

        async with httpx.AsyncClient() as client:
            # Use DuckDuckGo Instant Answer API
            try:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    raw_results = []

                    # Process DuckDuckGo Instant Answer results
                    if data.get("AbstractText"):
                        raw_results.append(
                            {
                                "title": data.get("Heading", query),
                                "url": data.get("AbstractURL", ""),
                                "content": data.get("AbstractText", ""),
                                "score": 1.0,
                            }
                        )

                    # Process related topics
                    for i, topic in enumerate(data.get("RelatedTopics", [])[: max_results - len(raw_results)]):
                        if isinstance(topic, dict) and topic.get("Text"):
                            raw_results.append(
                                {
                                    "title": topic.get("Text", "").split(" - ")[0],
                                    "url": topic.get("FirstURL", ""),
                                    "content": topic.get("Text", ""),
                                    "score": 1.0 - (i * 0.1),
                                }
                            )

                    # If no instant answers, try web search fallback with simple Wikipedia/DuckDuckGo
                    if not raw_results:
                        # Create basic web search results from query
                        raw_results.append(
                            {
                                "title": f"Search results for: {query}",
                                "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                                "content": f"Search for '{query}' using DuckDuckGo privacy-focused search.",
                                "score": 0.8,
                            }
                        )

                    if raw_results:
                        store_web_results(query, raw_results)
                    results = [WebSearchResult(**r) for r in raw_results]
                    logger.info(f"DuckDuckGo search returned {len(results)} results (cached)")
                    return results

            except Exception as search_error:
                logger.warning(f"DuckDuckGo search failed: {search_error}")

            # Minimal fallback result
            fallback_results = [
                {
                    "title": f"External search: {query}",
                    "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                    "content": f"For comprehensive results about '{query}', try searching on DuckDuckGo.",
                    "score": 0.5,
                }
            ]

            results = [WebSearchResult(**r) for r in fallback_results]
            logger.info(f"Using fallback search result for: {query}")
            return results

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return []


@app.post("/api/classify-query")
async def classify_query_endpoint(request: dict):
    """Classify a query and return optimization parameters for debugging."""
    query = request.get("query", "")
    base_threshold = request.get("confidence_threshold", 0.3)

    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    try:
        optimization_params = classify_and_optimize_query(query, base_threshold)
        classification = optimization_params["classification"]

        return {
            "query": query,
            "classification": {
                "query_type": classification.query_type.value,
                "confidence": classification.confidence,
                "reasoning": classification.reasoning,
                "keywords_matched": classification.keywords_matched,
                "prefer_web_search": classification.prefer_web_search,
            },
            "optimization": {
                "suggested_confidence_threshold": optimization_params["confidence_threshold"],
                "max_context_chunks": optimization_params["max_context_chunks"],
                "search_strategy": optimization_params["search_strategy"],
            },
            "original_threshold": base_threshold,
        }
    except Exception as e:
        logger.error(f"Query classification error: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@app.get("/api/test-web-search")
async def test_web_search():
    """Test endpoint for web search functionality."""
    try:
        results = await search_web("test query", 2)
        return {
            "status": "success",
            "results_count": len(results),
            "results": [
                {
                    "title": result.title,
                    "url": result.url,
                    "content": result.content[:100] + "..." if len(result.content) > 100 else result.content,
                    "score": result.score,
                }
                for result in results
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/intelligent-hybrid-search", response_model=RAGChatResponse)
async def intelligent_hybrid_search(request: HybridSearchRequest):
    """Enhanced hybrid search with intelligent query classification and optimization."""
    try:
        start_ts = time.time()
        # Classify the query and get optimized parameters
        optimization_params = classify_and_optimize_query(request.query, request.confidence_threshold)

        classification = optimization_params["classification"]
        optimized_threshold = optimization_params["confidence_threshold"]
        optimized_chunks = optimization_params["max_context_chunks"]
        search_strategy = optimization_params["search_strategy"]

        logger.info(
            f"Query classification: {classification.query_type.value}, "
            f"confidence: {classification.confidence:.2f}, "
            f"strategy: {search_strategy}, "
            f"optimized_threshold: {optimized_threshold:.2f}"
        )

        # Create RAG request with optimized parameters
        rag_request = RAGChatRequest(
            query=request.query,
            use_context=True,
            max_context_chunks=optimized_chunks,
            model=request.model,
            privacy_filter=request.privacy_filter,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        # Handle different search strategies
        if search_strategy == "web_first":
            # For current events, try web search first
            if request.enable_web_search:
                logger.info("Strategy: Web search first for current events query")
                web_results = await search_web(request.query)
                if web_results:
                    resp = await _generate_web_response(request, web_results, "intelligent_hybrid", classification)
                    resp.event_id = record_search_event(
                        query=request.query,
                        search_method="intelligent_hybrid_web",
                        confidence_score=resp.confidence_score,
                        rag_confidence=None,
                        classification_type=classification.query_type.value,
                        strategy=search_strategy,
                        response_time_ms=int((time.time() - start_ts) * 1000),
                        context_chunk_count=0,
                        web_result_count=len(web_results),
                        fused_count=0,
                        model_used=request.model,
                    )
                    return resp
            # Fall back to RAG if web search fails
            rag_response = rag_chat(rag_request)
            rag_response.search_method = "intelligent_hybrid"
            rag_response.event_id = record_search_event(
                query=request.query,
                search_method="intelligent_hybrid_rag",
                confidence_score=rag_response.confidence_score,
                rag_confidence=rag_response.confidence_score,
                classification_type=classification.query_type.value,
                strategy=search_strategy,
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=0,
                fused_count=0,
                model_used=request.model,
            )
            return rag_response

        elif search_strategy == "rag_first":
            # For technical docs, try RAG with lower threshold
            rag_response = rag_chat(rag_request)
            if rag_response.confidence_score >= optimized_threshold:
                rag_response.search_method = "intelligent_hybrid"
                rag_response.event_id = record_search_event(
                    query=request.query,
                    search_method="intelligent_hybrid_rag",
                    confidence_score=rag_response.confidence_score,
                    rag_confidence=rag_response.confidence_score,
                    classification_type=classification.query_type.value,
                    strategy=search_strategy,
                    response_time_ms=int((time.time() - start_ts) * 1000),
                    context_chunk_count=len(rag_response.context_used),
                    web_result_count=0,
                    fused_count=0,
                    model_used=request.model,
                )
                return rag_response
            # Fall back to web search only if confidence is very low
            if request.enable_web_search and rag_response.confidence_score < 0.1:
                logger.info(f"RAG confidence {rag_response.confidence_score:.2f} very low, trying web search")
                web_results = await search_web(request.query)
                if web_results:
                    resp = await _generate_web_response(request, web_results, "intelligent_hybrid", classification)
                    resp.event_id = record_search_event(
                        query=request.query,
                        search_method="intelligent_hybrid_web",
                        confidence_score=resp.confidence_score,
                        rag_confidence=rag_response.confidence_score,
                        classification_type=classification.query_type.value,
                        strategy=search_strategy,
                        response_time_ms=int((time.time() - start_ts) * 1000),
                        context_chunk_count=len(rag_response.context_used),
                        web_result_count=len(web_results),
                        fused_count=0,
                        model_used=request.model,
                    )
                    return resp
            return rag_response

        else:
            # Standard hybrid approach with optimized threshold
            rag_response = rag_chat(rag_request)
            if rag_response.confidence_score >= optimized_threshold:
                rag_response.search_method = "intelligent_hybrid"
                rag_response.event_id = record_search_event(
                    query=request.query,
                    search_method="intelligent_hybrid_rag",
                    confidence_score=rag_response.confidence_score,
                    rag_confidence=rag_response.confidence_score,
                    classification_type=classification.query_type.value,
                    strategy=search_strategy,
                    response_time_ms=int((time.time() - start_ts) * 1000),
                    context_chunk_count=len(rag_response.context_used),
                    web_result_count=0,
                    fused_count=0,
                    model_used=request.model,
                )
                return rag_response

            if request.enable_web_search:
                logger.info(
                    f"RAG confidence {rag_response.confidence_score:.2f} below optimized threshold {optimized_threshold:.2f}, trying web search"
                )
                web_results = await search_web(request.query)
                if web_results:
                    resp = await _generate_web_response(request, web_results, "intelligent_hybrid", classification)
                    resp.event_id = record_search_event(
                        query=request.query,
                        search_method="intelligent_hybrid_web",
                        confidence_score=resp.confidence_score,
                        rag_confidence=rag_response.confidence_score,
                        classification_type=classification.query_type.value,
                        strategy=search_strategy,
                        response_time_ms=int((time.time() - start_ts) * 1000),
                        context_chunk_count=len(rag_response.context_used),
                        web_result_count=len(web_results),
                        fused_count=0,
                        model_used=request.model,
                    )
                    return resp

            rag_response.event_id = record_search_event(
                query=request.query,
                search_method="intelligent_hybrid_rag_low_conf",
                confidence_score=rag_response.confidence_score,
                rag_confidence=rag_response.confidence_score,
                classification_type=classification.query_type.value,
                strategy=search_strategy,
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=0,
                fused_count=0,
                model_used=request.model,
            )
            return rag_response

    except Exception as e:
        logger.error(f"Intelligent hybrid search error: {e}")
        raise HTTPException(status_code=500, detail=f"Intelligent hybrid search failed: {str(e)}")


async def _generate_web_response(
    request: HybridSearchRequest,
    web_results: List[WebSearchResult],
    search_method: str,
    classification: QueryClassification,
) -> RAGChatResponse:
    """Generate response from web search results with classification context."""
    web_context = []
    for result in web_results:
        web_context.append(f"Title: {result.title}\nURL: {result.url}\nContent: {result.content}")

    # Customize prompt based on query classification
    if classification.query_type.value == "current_events":
        prompt_prefix = "Based on the latest web search results about current events:"
    elif classification.query_type.value == "comparison":
        prompt_prefix = "Based on the comparative information from web search results:"
    elif classification.query_type.value == "code_examples":
        prompt_prefix = "Based on the programming resources found in web search results:"
    else:
        prompt_prefix = "Based on the web search results provided:"

    web_prompt = f"""{prompt_prefix}

Question: {request.query}

Web Search Results:
{chr(10).join(web_context)}

Please provide a comprehensive answer based on the web search results above. Focus on providing accurate, up-to-date information relevant to the query type: {classification.query_type.value}."""

    try:
        response = ollama_client.generate(
            model=request.model,
            prompt=web_prompt,
            options={"temperature": request.temperature, "num_predict": request.max_tokens},
        )
        web_response_text = response.get("response", "No response generated")
    except Exception as e:
        logger.error(f"Ollama generation error for web search: {e}")
        raise HTTPException(status_code=500, detail=f"Web response generation failed: {str(e)}")

    # Return enhanced response with classification info
    return RAGChatResponse(
        response=web_response_text,
        context_used=web_context,
        model=request.model,
        context_retrieved=True,
        confidence_score=0.8,  # Higher confidence for web-backed responses
        search_method=search_method,
    )


def fuse_rag_and_web_context(
    rag_chunks: List[str], web_results: List[WebSearchResult], max_items: int = 10
) -> Tuple[List[str], dict]:
    """Fuse RAG context chunks with web results, de-duplicating and ranking.

    Returns fused context list and fusion metadata.
    """
    fused = []
    provenance = []
    added = set()

    # Add top RAG chunks first (labelled)
    for i, chunk in enumerate(rag_chunks):
        if len(fused) >= max_items:
            break
        snippet = chunk.strip()
        if snippet and snippet not in added:
            fused.append(f"[DOC {i+1}] {snippet}")
            provenance.append({"source": "rag", "index": i, "chars": len(snippet)})
            added.add(snippet)

    # Add web results after documents
    for j, wr in enumerate(web_results):
        if len(fused) >= max_items:
            break
        snippet = (wr.content or "").strip()
        # Shorten overly long content
        if len(snippet) > 600:
            snippet = snippet[:600].rsplit(".", 1)[0] + "..."
        key = f"{wr.title}|{snippet[:120]}"
        if snippet and key not in added:
            fused.append(f"[WEB {j+1}] Title: {wr.title}\nURL: {wr.url}\n{snippet}")
            provenance.append({"source": "web", "index": j, "title": wr.title[:80], "chars": len(snippet)})
            added.add(key)

    fusion_meta = {
        "rag_count": len(rag_chunks),
        "web_count": len(web_results),
        "fused_count": len(fused),
        "provenance": provenance,
    }
    return fused, fusion_meta


def build_fusion_prompt(query: str, fused_context: List[str]) -> str:
    """Construct a balanced prompt from fused context."""
    header = "You are an assistant that combines internal documentation (DOC) with web knowledge (WEB)."
    instructions = (
        "Synthesize an accurate, concise answer.\n"
        "When referencing: cite [DOC n] or [WEB n] inline.\n"
        "Prefer DOC for system-specific details; use WEB for current or general knowledge.\n"
        "If conflicts arise, note them explicitly."
    )
    context_block = "\n\nFUSED CONTEXT:\n" + "\n---\n".join(fused_context)
    return f"{header}\n{instructions}\n\nQuestion: {query}{context_block}\n\nAnswer:"


@app.get("/api/analytics/summary")
def analytics_summary(last_hours: int = 24):
    """Return aggregate analytics over recent search events."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT search_method, COUNT(*) FROM search_events
            WHERE created_at >= NOW() - INTERVAL '%s hour'
            GROUP BY search_method
            """,
            (last_hours,),
        )
        method_counts = _aggregate_rows_to_dict(cur.fetchall())

        cur.execute(
            """
            SELECT classification_type, COUNT(*) FROM search_events
            WHERE created_at >= NOW() - INTERVAL '%s hour'
            GROUP BY classification_type
            """,
            (last_hours,),
        )
        class_counts = _aggregate_rows_to_dict(cur.fetchall())

        cur.execute(
            """SELECT AVG(response_time_ms) FROM search_events
                   WHERE created_at >= NOW() - INTERVAL '%s hour'""",
            (last_hours,),
        )
        row_latency = cur.fetchone()
        avg_latency = row_latency[0] if row_latency and row_latency[0] is not None else None

        cur.execute(
            """SELECT AVG(confidence_score), AVG(rag_confidence)
                   FROM search_events
                   WHERE created_at >= NOW() - INTERVAL '%s hour'""",
            (last_hours,),
        )
        row = cur.fetchone()
        avg_conf, avg_rag_conf = (row[0], row[1]) if row else (None, None)

        cur.close()
        conn.close()
        return {
            "window_hours": last_hours,
            "search_method_counts": method_counts,
            "classification_counts": class_counts,
            "average_latency_ms": round(avg_latency, 2) if avg_latency else None,
            "average_confidence": round(avg_conf, 3) if avg_conf else None,
            "average_rag_confidence": round(avg_rag_conf, 3) if avg_rag_conf else None,
        }
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        raise HTTPException(status_code=500, detail="Analytics summary failed")


@app.get("/api/analytics/recent")
def analytics_recent(limit: int = 50):
    """Return recent search events (most recent first)."""
    limit = min(max(limit, 1), 500)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT created_at, query, search_method, confidence_score, rag_confidence,
                   classification_type, strategy, response_time_ms, context_chunk_count,
                   web_result_count, fused_count, model_used, error
            FROM search_events
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        keys = [
            "created_at",
            "query",
            "search_method",
            "confidence_score",
            "rag_confidence",
            "classification_type",
            "strategy",
            "response_time_ms",
            "context_chunk_count",
            "web_result_count",
            "fused_count",
            "model_used",
            "error",
        ]
        events = [dict(zip(keys, r)) for r in rows]
        return {"limit": limit, "events": events}
    except Exception as e:
        logger.error(f"Analytics recent error: {e}")
        raise HTTPException(status_code=500, detail="Analytics recent failed")


@app.post("/api/fused-hybrid-search", response_model=RAGChatResponse)
async def fused_hybrid_search(request: HybridSearchRequest):
    """Perform RAG + Web search and fuse results when both have value."""
    try:
        start_ts = time.time()
        # Step 1: Run RAG path
        rag_request = RAGChatRequest(
            query=request.query,
            use_context=True,
            max_context_chunks=request.max_context_chunks,
            model=request.model,
            privacy_filter=request.privacy_filter,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        rag_response = rag_chat(rag_request)

        # Early return if high confidence and no web search wanted
        if (rag_response.confidence_score >= request.confidence_threshold) and not request.enable_web_search:
            rag_response.search_method = "fusion_rag_only"
            rag_response.event_id = record_search_event(
                query=request.query,
                search_method="fusion_rag_only",
                confidence_score=rag_response.confidence_score,
                rag_confidence=rag_response.confidence_score,
                classification_type=None,
                strategy="fusion",
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=0,
                fused_count=0,
                model_used=request.model,
            )
            return rag_response

        # Step 2: Run web search (even if RAG decent) to allow fusion
        web_results: List[WebSearchResult] = []
        if request.enable_web_search:
            web_results = await search_web(request.query)

        # Decide strategy
        if not web_results and rag_response.confidence_score >= request.confidence_threshold:
            rag_response.search_method = "fusion_rag_only"
            rag_response.event_id = record_search_event(
                query=request.query,
                search_method="fusion_rag_only",
                confidence_score=rag_response.confidence_score,
                rag_confidence=rag_response.confidence_score,
                classification_type=None,
                strategy="fusion",
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=0,
                fused_count=0,
                model_used=request.model,
            )
            return rag_response
        if not web_results and rag_response.confidence_score < request.confidence_threshold:
            # No web rescue possible
            rag_response.search_method = "fusion_rag_low_conf"
            rag_response.event_id = record_search_event(
                query=request.query,
                search_method="fusion_rag_low_conf",
                confidence_score=rag_response.confidence_score,
                rag_confidence=rag_response.confidence_score,
                classification_type=None,
                strategy="fusion",
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=0,
                fused_count=0,
                model_used=request.model,
            )
            return rag_response

        # If RAG is very weak but web exists, just return web generation (reuse helper)
        if rag_response.confidence_score < 0.1 and web_results:
            # Simple web response path with synthetic classification
            temp_req = request  # reuse
            classification = QueryClassification(
                query_type=QueryType.GENERAL_KNOWLEDGE,
                confidence=0.5,
                suggested_confidence_threshold=0.4,
                prefer_web_search=True,
                reasoning="Low RAG confidence, using web only in fusion path",
                keywords_matched=[],
            )
            resp = await _generate_web_response(temp_req, web_results, "fusion_web_only", classification)
            resp = await _generate_web_response(temp_req, web_results, "fusion_web_only", classification)
            resp.event_id = record_search_event(
                query=request.query,
                search_method="fusion_web_only",
                confidence_score=resp.confidence_score,
                rag_confidence=rag_response.confidence_score,
                classification_type=classification.query_type.value,
                strategy="fusion",
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=len(web_results),
                fused_count=0,
                model_used=request.model,
            )
            return resp

        # Step 3: Fuse contexts
        fused_context, fusion_meta = fuse_rag_and_web_context(rag_response.context_used, web_results, max_items=10)

        # Step 4: Build fusion prompt
        fusion_prompt = build_fusion_prompt(request.query, fused_context)

        # Step 5: Generate answer
        try:
            gen = ollama_client.generate(
                model=request.model,
                prompt=fusion_prompt,
                options={"temperature": request.temperature, "num_predict": request.max_tokens},
            )
            fused_answer = gen.get("response", "(No answer generated)")
        except Exception as e:
            logger.error(f"Fusion generation error: {e}")
            # Fallback to RAG response if generation fails
            rag_response.search_method = "fusion_fallback_rag"
            return rag_response

        # Heuristic fused confidence: blend signals
        fused_conf = min(0.95, 0.5 * rag_response.confidence_score + 0.4 + 0.05 * (1 if len(web_results) > 0 else 0))

        resp = RAGChatResponse(
            response=fused_answer,
            context_used=fused_context,
            model=request.model,
            context_retrieved=True,
            confidence_score=fused_conf,
            search_method="fusion",
            fusion_metadata=fusion_meta,
        )
        resp.event_id = record_search_event(
            query=request.query,
            search_method="fusion",
            confidence_score=resp.confidence_score,
            rag_confidence=rag_response.confidence_score,
            classification_type=None,
            strategy="fusion",
            response_time_ms=int((time.time() - start_ts) * 1000),
            context_chunk_count=len(rag_response.context_used),
            web_result_count=len(web_results),
            fused_count=fusion_meta.get("fused_count"),
            model_used=request.model,
        )
        return resp
    except Exception as e:
        logger.error(f"Fused hybrid search error: {e}")
        raise HTTPException(status_code=500, detail=f"Fused hybrid search failed: {str(e)}")


@app.post("/api/hybrid-search", response_model=RAGChatResponse)
async def hybrid_search(request: HybridSearchRequest):
    """Enhanced hybrid search with adaptive thresholds and specialized model routing."""
    try:
        start_ts = time.time()

        # Perform advanced query analysis if enabled
        query_analysis = None
        adaptive_threshold = request.confidence_threshold

        if request.enable_adaptive_threshold:
            query_analysis = enhanced_search.analyze_query(request.query, request.confidence_threshold)
            adaptive_threshold = query_analysis.confidence_threshold

            # Use specialized model if not explicitly overridden
            if request.model == "mistral:7b":  # Default model
                request.model = query_analysis.optimal_model

            logger.info(
                f"Query analysis: complexity={query_analysis.complexity.value}, "
                f"type={query_analysis.question_type}, "
                f"adaptive_threshold={adaptive_threshold:.3f}, "
                f"optimal_model={query_analysis.optimal_model}"
            )

        # Check if iterative research is enabled
        if request.enable_iterative_research:
            logger.info(f"Starting iterative research for query: {request.query}")
            rag_response = await iterative_research_until_confident(
                request.query,
                request.target_confidence,
                request.max_research_iterations,
                request.model,
                request.privacy_filter,
            )
        else:
            # Create RAG request with potentially optimized model
            rag_request = RAGChatRequest(
                query=request.query,
                use_context=True,
                max_context_chunks=request.max_context_chunks,
                model=request.model,
                privacy_filter=request.privacy_filter,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            with performance_context("rag_search", {"search_method": "hybrid_rag"}):
                rag_response = rag_chat(rag_request)

        # Enhanced confidence calculation if query analysis available
        if query_analysis:
            # Recalculate confidence with enhanced method
            enhanced_confidence = enhanced_search.calculate_enhanced_confidence(
                request.query, rag_response.context_used, rag_response.response, query_analysis
            )
            original_confidence = rag_response.confidence_score
            rag_response.confidence_score = enhanced_confidence

            logger.info(f"Enhanced confidence: {enhanced_confidence:.3f} " f"(original: {original_confidence:.3f})")

        # Record RAG confidence metrics with analysis context
        metrics_collector.record_rag_confidence(
            confidence=rag_response.confidence_score,
            search_method=f"hybrid_rag_{query_analysis.complexity.value if query_analysis else 'standard'}",
        )

        # Use adaptive threshold for decision making
        if rag_response.confidence_score >= adaptive_threshold:
            rag_response.event_id = record_search_event(
                query=request.query,
                search_method=f"enhanced_hybrid_rag_{query_analysis.complexity.value if query_analysis else 'standard'}",
                confidence_score=rag_response.confidence_score,
                rag_confidence=rag_response.confidence_score,
                classification_type=query_analysis.question_type if query_analysis else None,
                strategy="adaptive_threshold" if request.enable_adaptive_threshold else "threshold",
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=0,
                fused_count=0,
                model_used=request.model,
            )
            return rag_response

        # If confidence is low and web search is enabled, try web search
        if not request.enable_web_search:
            rag_response.event_id = record_search_event(
                query=request.query,
                search_method="hybrid_rag_low_conf_web_disabled",
                confidence_score=rag_response.confidence_score,
                rag_confidence=rag_response.confidence_score,
                classification_type=None,
                strategy="threshold",
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=0,
                fused_count=0,
                model_used=request.model,
            )
            return rag_response  # Return low-confidence RAG result

        logger.info(
            f"RAG confidence {rag_response.confidence_score:.2f} below adaptive threshold {adaptive_threshold:.2f}, trying web search"
        )

        # Perform web search
        web_results = await search_web(request.query)

        if not web_results:
            # No web results, return original RAG response
            rag_response.event_id = record_search_event(
                query=request.query,
                search_method="hybrid_rag_low_conf_no_web_results",
                confidence_score=rag_response.confidence_score,
                rag_confidence=rag_response.confidence_score,
                classification_type=None,
                strategy="threshold",
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=0,
                fused_count=0,
                model_used=request.model,
            )
            return rag_response

        # Combine web results into context
        web_context = []
        for result in web_results:
            web_context.append(f"Title: {result.title}\nURL: {result.url}\nContent: {result.content}")

        # Generate response using web context
        web_prompt = f"""Answer the following question using the provided web search results:

Question: {request.query}

Web Search Results:
{chr(10).join(web_context)}

Please provide a comprehensive answer based on the web search results above:"""

        try:
            response = ollama_client.generate(
                model=request.model,
                prompt=web_prompt,
                options={"temperature": request.temperature, "num_predict": request.max_tokens},
            )
            web_response_text = response.get("response", "No response generated")
        except Exception as e:
            logger.error(f"Ollama generation error for web search: {e}")
            return rag_response  # Fall back to RAG response

        # Return hybrid response with higher confidence since it's web-backed
        resp = RAGChatResponse(
            response=web_response_text,
            context_used=web_context,
            model=request.model,
            context_retrieved=True,
            confidence_score=0.8,  # Higher confidence for web-backed responses
            search_method="hybrid",
        )
        resp.event_id = record_search_event(
            query=request.query,
            search_method="hybrid_web",
            confidence_score=resp.confidence_score,
            rag_confidence=rag_response.confidence_score,
            classification_type=None,
            strategy="threshold",
            response_time_ms=int((time.time() - start_ts) * 1000),
            context_chunk_count=len(rag_response.context_used),
            web_result_count=len(web_results),
            fused_count=0,
            model_used=request.model,
        )
        return resp

    except Exception as e:
        logger.error(f"Hybrid search error: {e}")
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")


@app.post("/api/enhanced-search", response_model=RAGChatResponse)
async def enhanced_search_endpoint(request: HybridSearchRequest):
    """Advanced search with full query optimization and adaptive routing."""
    try:
        start_ts = time.time()

        # Always perform comprehensive query analysis
        query_analysis = enhanced_search.analyze_query(request.query, request.confidence_threshold)

        logger.info(
            f"Enhanced search analysis - Query: '{request.query[:50]}...', "
            f"Complexity: {query_analysis.complexity.value}, "
            f"Type: {query_analysis.question_type}, "
            f"Strategy: {query_analysis.search_strategy.value}, "
            f"Adaptive threshold: {query_analysis.confidence_threshold:.3f}"
        )

        # Route to specialized model based on analysis
        optimized_model = query_analysis.optimal_model

        # Determine chunk count based on complexity
        chunk_count = request.max_context_chunks
        if query_analysis.complexity == "complex":
            chunk_count = min(chunk_count + 3, 10)  # More context for complex queries
        elif query_analysis.complexity == "simple":
            chunk_count = max(chunk_count - 1, 3)  # Less context for simple queries

        # Create optimized RAG request
        rag_request = RAGChatRequest(
            query=request.query,
            use_context=True,
            max_context_chunks=chunk_count,
            model=optimized_model,
            privacy_filter=request.privacy_filter,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        with performance_context(
            "enhanced_rag_search",
            {
                "complexity": query_analysis.complexity.value,
                "question_type": query_analysis.question_type,
                "model": optimized_model,
            },
        ):
            rag_response = rag_chat(rag_request)

        # Always use enhanced confidence calculation
        enhanced_confidence = enhanced_search.calculate_enhanced_confidence(
            request.query, rag_response.context_used, rag_response.response, query_analysis
        )
        original_confidence = rag_response.confidence_score
        rag_response.confidence_score = enhanced_confidence

        logger.info(f"Confidence enhancement: {original_confidence:.3f} → {enhanced_confidence:.3f}")

        # Record comprehensive metrics
        metrics_collector.record_rag_confidence(
            confidence=enhanced_confidence,
            search_method=f"enhanced_{query_analysis.complexity.value}_{query_analysis.question_type}",
        )

        # Apply search strategy
        if query_analysis.search_strategy == "rag_only" or enhanced_confidence >= query_analysis.confidence_threshold:
            # High confidence or RAG-only strategy
            rag_response.event_id = record_search_event(
                query=request.query,
                search_method=f"enhanced_rag_{query_analysis.search_strategy.value}",
                confidence_score=enhanced_confidence,
                rag_confidence=enhanced_confidence,
                classification_type=query_analysis.question_type,
                strategy="enhanced_adaptive",
                response_time_ms=int((time.time() - start_ts) * 1000),
                context_chunk_count=len(rag_response.context_used),
                web_result_count=0,
                fused_count=0,
                model_used=optimized_model,
            )

            # Enhanced response with analysis insights logged
            logger.info(
                f"Enhanced RAG success - Complexity: {query_analysis.complexity.value}, "
                f"Model: {optimized_model}, Strategy: {query_analysis.search_strategy.value}, "
                f"Confidence: {original_confidence:.3f} → {enhanced_confidence:.3f}"
            )

            return rag_response

        # Low confidence - apply strategy
        if query_analysis.search_strategy == "web_preferred" or not request.enable_web_search:
            # Web search or web disabled
            if request.enable_web_search:
                logger.info(f"Low confidence {enhanced_confidence:.3f}, using web search strategy")
                web_results = await search_web(request.query, max_results=8)

                if web_results:
                    # Use existing web response generation
                    temp_request = HybridSearchRequest(
                        query=request.query,
                        confidence_threshold=query_analysis.confidence_threshold,
                        model=optimized_model,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        max_context_chunks=request.max_context_chunks,
                        enable_adaptive_threshold=True,
                        enable_enhanced_reranking=True,
                        enable_web_search=True,
                        privacy_filter=request.privacy_filter,
                        enable_iterative_research=False,
                        target_confidence=0.95,
                        max_research_iterations=25,
                    )

                    # Create classification object for compatibility
                    from query_classifier import QueryClassification, QueryType

                    classification = QueryClassification(
                        query_type=QueryType(query_analysis.question_type),
                        confidence=0.8,
                        reasoning="Enhanced search analysis",
                        suggested_confidence_threshold=query_analysis.confidence_threshold,
                        prefer_web_search=True,
                        keywords_matched=query_analysis.domain_keywords[:3],
                    )

                    web_response = await _generate_web_response(
                        temp_request, web_results, "enhanced_web", classification
                    )

                    # Record enhanced web search event
                    web_response.event_id = record_search_event(
                        query=request.query,
                        search_method=f"enhanced_web_{query_analysis.search_strategy.value}",
                        confidence_score=0.8,  # Web responses get higher confidence
                        rag_confidence=enhanced_confidence,
                        classification_type=query_analysis.question_type,
                        strategy="enhanced_web_fallback",
                        response_time_ms=int((time.time() - start_ts) * 1000),
                        context_chunk_count=len(rag_response.context_used),
                        web_result_count=len(web_results),
                        fused_count=0,
                        model_used=optimized_model,
                    )

                    return web_response

            # Return RAG response with low confidence indicator
            logger.warning(f"Low confidence {enhanced_confidence:.3f}, no web search available")
            # Note: Metadata would be added here in production with extended response model

            return rag_response

    except Exception as e:
        logger.error(f"Enhanced search error: {e}")
        raise HTTPException(status_code=500, detail=f"Enhanced search failed: {str(e)}")


@app.get("/api/documents/stats", response_model=DocumentStatsResponse)
async def get_document_stats():
    """Get knowledge base statistics and overview."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get basic counts
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_documents,
                MAX(processed_at) as last_processed
            FROM documents
            WHERE processing_status = 'processed'
        """
        )
        basic_stats = cursor.fetchone()

        # Get total chunks
        cursor.execute(
            """
            SELECT COUNT(*) as total_chunks
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE d.processing_status = 'processed'
        """
        )
        chunk_stats = cursor.fetchone()

        # Get document type breakdown
        cursor.execute(
            """
            SELECT document_type, COUNT(*) as count
            FROM documents
            WHERE processing_status = 'processed' AND document_type IS NOT NULL
            GROUP BY document_type
            ORDER BY count DESC
        """
        )
        type_breakdown = {row["document_type"]: row["count"] for row in cursor.fetchall()}

        # Get product breakdown
        cursor.execute(
            """
            SELECT product_name, COUNT(*) as count
            FROM documents
            WHERE processing_status = 'processed' AND product_name IS NOT NULL
            GROUP BY product_name
            ORDER BY count DESC
        """
        )
        product_breakdown = {row["product_name"]: row["count"] for row in cursor.fetchall()}

        # Get privacy breakdown
        cursor.execute(
            """
            SELECT privacy_level, COUNT(*) as count
            FROM documents
            WHERE processing_status = 'processed'
            GROUP BY privacy_level
            ORDER BY count DESC
        """
        )
        privacy_breakdown = {row["privacy_level"]: row["count"] for row in cursor.fetchall()}

        cursor.close()
        conn.close()

        total_docs = basic_stats["total_documents"] if basic_stats else 0
        total_chunks = chunk_stats["total_chunks"] if chunk_stats else 0
        avg_chunks = total_chunks / max(total_docs, 1)

        last_processed = None
        if basic_stats and basic_stats["last_processed"]:
            last_processed = basic_stats["last_processed"].isoformat()

        return DocumentStatsResponse(
            total_documents=total_docs,
            total_chunks=total_chunks,
            document_types=type_breakdown,
            product_breakdown=product_breakdown,
            privacy_breakdown=privacy_breakdown,
            avg_chunks_per_document=round(avg_chunks, 1),
            last_processed=last_processed,
        )

    except Exception as e:
        logger.error(f"Error fetching document stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch document statistics")


@app.post("/api/documents/list", response_model=DocumentListResponse)
async def list_documents(request: DocumentListRequest):
    """List documents in the knowledge base with optional filtering and search."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Build base query with filters
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

        # Validate sort parameters
        valid_sort_fields = {"created_at", "file_name", "chunk_count", "processed_at"}
        sort_field = request.sort_by if request.sort_by in valid_sort_fields else "created_at"
        sort_order = "ASC" if request.sort_order.lower() == "asc" else "DESC"

        # Get total count for pagination
        count_query = f"""
            SELECT COUNT(*) as total
            FROM documents d
            WHERE {where_clause}
        """
        cursor.execute(count_query, params)
        count_result = cursor.fetchone()
        total_count = count_result["total"] if count_result else 0

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

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document list")


@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents_get(limit: int = 20, offset: int = 0):
    """Convenience GET wrapper for listing documents (backward compatibility).

    Frontend originally called GET /api/documents without pagination body. This endpoint
    adapts to that usage and delegates to the POST implementation.
    """
    try:
        doc_request = DocumentListRequest(limit=limit, offset=offset)
        return await list_documents(doc_request)  # type: ignore[arg-type]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /api/documents failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve documents")


@app.get("/api/documents/{document_id}")
async def get_document_details(document_id: int):
    """Get detailed information about a specific document."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get document info with chunk details
        cursor.execute(
            """
            SELECT
                d.*,
                COUNT(dc.id) as chunk_count,
                MIN(dc.created_at) as first_chunk_created,
                MAX(dc.created_at) as last_chunk_created,
                AVG(dc.content_length) as avg_chunk_length
            FROM documents d
            LEFT JOIN document_chunks dc ON d.id = dc.document_id
            WHERE d.id = %s AND d.processing_status = 'processed'
            GROUP BY d.id
        """,
            [document_id],
        )

        document = cursor.fetchone()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get chunk breakdown by type
        cursor.execute(
            """
            SELECT chunk_type, COUNT(*) as count
            FROM document_chunks
            WHERE document_id = %s
            GROUP BY chunk_type
            ORDER BY count DESC
        """,
            [document_id],
        )

        chunk_types = {row["chunk_type"]: row["count"] for row in cursor.fetchall()}

        cursor.close()
        conn.close()

        return {
            **dict(document),
            "chunk_types": chunk_types,
            "processed_at": document["processed_at"].isoformat() if document["processed_at"] else None,
            "created_at": document["created_at"].isoformat(),
            "first_chunk_created": document["first_chunk_created"].isoformat()
            if document["first_chunk_created"]
            else None,
            "last_chunk_created": document["last_chunk_created"].isoformat()
            if document["last_chunk_created"]
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document details")


@app.get("/api/documents/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    """Download a document file. Requires download_documents permission."""
    try:
        # Check permissions
        user_permissions = await auth_manager.get_user_permissions(current_user.id)
        if PermissionLevel.DOWNLOAD_DOCUMENTS.value not in user_permissions:
            raise HTTPException(status_code=403, detail="Insufficient permissions to download documents")

        # Get document info
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "SELECT file_name, file_path FROM documents WHERE id = %s AND processing_status = 'processed'",
            [document_id],
        )
        document = cursor.fetchone()
        cursor.close()
        conn.close()

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        file_path = document["file_path"]
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Document file not found")

        # Return file
        return FileResponse(path=file_path, filename=document["file_name"], media_type="application/octet-stream")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to download document")


@app.delete("/api/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    """Delete a document. Requires manage_documents permission (admin only)."""
    try:
        # Check permissions - only admins can delete
        user_permissions = await auth_manager.get_user_permissions(current_user.id)
        if PermissionLevel.MANAGE_DOCUMENTS.value not in user_permissions:
            raise HTTPException(status_code=403, detail="Insufficient permissions to delete documents")

        # Get document info
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            "SELECT file_name, file_path FROM documents WHERE id = %s AND processing_status = 'processed'",
            [document_id],
        )
        document = cursor.fetchone()

        if not document:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")

        file_path = document["file_path"]

        # Delete from database
        cursor.execute("DELETE FROM document_chunks WHERE document_id = %s", [document_id])
        cursor.execute("DELETE FROM documents WHERE id = %s", [document_id])
        conn.commit()

        cursor.close()
        conn.close()

        # Delete file if it exists
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to delete file {file_path}: {e}")

        return {"message": "Document deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")


@app.post("/api/temp-process")
async def process_temp_document(request: TempDocProcessRequest):
    """Process temporarily uploaded document for analysis."""
    try:
        temp_doc = temp_processor.process_file(request.file_path, request.file_name, request.session_id)

        # Generate embeddings for search capability
        success = temp_processor.generate_embeddings(request.session_id)

        return {
            "success": True,
            "session_id": request.session_id,
            "file_name": temp_doc.file_name,
            "content_length": len(temp_doc.content),
            "chunk_count": len(temp_doc.chunks),
            "embeddings_generated": success,
            "message": "Document processed successfully",
        }
    except Exception as e:
        logger.error(f"Failed to process temp document: {e}")
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")


@app.post("/api/temp-analyze", response_model=TempAnalysisResponse)
async def analyze_temp_document(request: TempAnalysisRequest):
    """Analyze temporarily uploaded document using RAG."""
    try:
        # Get session info
        session_info = temp_processor.get_session_info(request.session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")

        # Search temporary document
        search_results = temp_processor.search_temp_documents(
            request.query, request.session_id, request.max_results or 5
        )

        if not search_results:
            return TempAnalysisResponse(
                session_id=request.session_id,
                query=request.query,
                file_name=session_info["file_name"],
                results=[],
                confidence=0.0,
                response="No relevant content found in the uploaded document.",
            )

        # Build context from search results
        context_chunks = [result[0] for result in search_results]
        confidence = max([result[1] for result in search_results])

        # Generate response using Technical Service Assistant prompt
        context_text = "\\n\\n".join(f"Section {i+1}: {chunk}" for i, chunk in enumerate(context_chunks))

        prompt = f"""{TECHNICAL_SERVICE_SYSTEM_PROMPT}

Analyze the following content from the uploaded document: {session_info["file_name"]}

Context from document:
{context_text}

Question: {request.query}

Provide a technical analysis focusing on troubleshooting, configuration, or system issues if applicable:"""

        # Generate response using Ollama
        llm_response = ollama_client.chat(model=settings.chat_model, messages=[{"role": "user", "content": prompt}])

        # Format results for response
        formatted_results = [
            {
                "content": result[0][:500] + "..." if len(result[0]) > 500 else result[0],
                "similarity": result[1],
                "rank": i + 1,
            }
            for i, result in enumerate(search_results)
        ]

        return TempAnalysisResponse(
            session_id=request.session_id,
            query=request.query,
            file_name=session_info["file_name"],
            results=formatted_results,
            confidence=confidence,
            response=llm_response["message"]["content"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Temp analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/temp-session/{session_id}")
async def get_temp_session_info(session_id: str):
    """Get information about a temporary document session."""
    session_info = temp_processor.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    return session_info


@app.delete("/api/temp-session/{session_id}")
async def cleanup_temp_session(session_id: str):
    """Clean up a temporary document session."""
    success = temp_processor.cleanup_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True, "message": "Session cleaned up successfully"}


@app.post("/api/temp-cleanup")
async def cleanup_expired_sessions():
    """Clean up all expired temporary document sessions."""
    try:
        expired_count = temp_processor.cleanup_expired_sessions()
        return {
            "success": True,
            "expired_sessions_cleaned": expired_count,
            "message": f"Cleaned up {expired_count} expired sessions",
        }
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail="Cleanup failed")


@app.post("/api/web-search")
async def web_search_endpoint(request: dict):
    """Lightweight web search endpoint exposing cached DuckDuckGo Instant Answer results.

    Request body:
        {"query": "search terms", "max_results": 5}
    """
    query = request.get("query", "").strip()
    max_results = int(request.get("max_results", 5))
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    try:
        results = await search_web(query, max_results=max_results)
        return {
            "query": query,
            "results_count": len(results),
            "results": [r.model_dump() for r in results],
        }
    except Exception as e:
        logger.error(f"/api/web-search error for '{query}': {e}")
        raise HTTPException(status_code=500, detail="Web search failed")




@app.get("/api/metrics/health")
async def metrics_health():
    """Health check endpoint with basic metrics."""
    try:
        # Check Ollama instances health
        ollama_health = {}
        for i in range(1, 5):
            11433 + i
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"http://ollama-server-{i}:{11434}/api/tags")
                    ollama_health[f"ollama-server-{i}"] = response.status_code == 200
                    OLLAMA_HEALTH.labels(instance=f"ollama-server-{i}").set(1 if response.status_code == 200 else 0)
            except Exception:
                ollama_health[f"ollama-server-{i}"] = False
                OLLAMA_HEALTH.labels(instance=f"ollama-server-{i}").set(0)

        # Check database connectivity
        db_healthy = False
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                db_healthy = True
            conn.close()
        except Exception:
            pass

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {"database": db_healthy, "ollama_instances": ollama_health},
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


cleanup_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    """Application lifespan management replacing deprecated startup event."""
    global cleanup_task

    logger.info("Starting up Technical Service Assistant with performance monitoring")

    if metrics_collector.enabled:
        try:
            metrics_collector.start_metrics_server(port=9091)
        except Exception as e:
            logger.warning(f"Could not start metrics server: {e}")

    metrics_collector.update_system_metrics()

    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("Startup complete - monitoring active")

    try:
        yield
    finally:
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            cleanup_task = None

        logger.info("Shutdown complete - monitoring stopped")


app.router.lifespan_context = app_lifespan


async def periodic_cleanup():
    """Periodically clean up expired temporary document sessions."""
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            expired_count = temp_processor.cleanup_expired_sessions()
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired temporary document sessions")
        except Exception as e:
            logger.error(f"Periodic cleanup error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


# ===== RBAC Authentication & Authorization Endpoints =====
# Auth endpoints now handled by rbac_endpoints.py router


# @app.post("/api/auth/refresh")
# async def refresh_token(current_user: User = Depends(get_current_user)):
#     """Refresh JWT token."""
#     try:
#         result = await auth_system.refresh_token(current_user.email)
#         logger.info(f"Token refreshed for user: {current_user.email}")
#         return result
#     except Exception as e:
#         logger.error(f"Token refresh error: {e}")
#         raise HTTPException(status_code=500, detail="Token refresh failed")


# @app.post("/api/auth/password-reset")
# async def request_password_reset(request: PasswordResetRequest):
#     """Request password reset."""
#     try:
#         success = await auth_system.request_password_reset(request.email)
#         if success:
#             logger.info(f"Password reset requested for: {request.email}")
#             return {"message": "Password reset instructions sent"}
#         else:
#             logger.warning(f"Password reset failed for: {request.email}")
#             raise HTTPException(status_code=404, detail="User not found")
#     except Exception as e:
#         logger.error(f"Password reset error: {e}")
#         raise HTTPException(status_code=500, detail="Password reset failed")


# @app.get("/api/auth/profile", response_model=UserResponse)
# async def get_user_profile(current_user: User = Depends(get_current_user)):
#     """Get current user profile."""
#     return current_user


# @app.get("/api/auth/users")
# @require_permission("users", "read")
# async def list_users(current_user: User = Depends(get_current_user)):
#     """List users (admin only)."""
#     try:
#         users = await auth_system.get_all_users()
#         logger.info(f"User list accessed by: {current_user.email}")
#         return {"users": users}
#     except Exception as e:
#         logger.error(f"List users error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to retrieve users")


# @app.post("/api/auth/users/{user_id}/roles")
# @require_permission("roles", "assign")
# async def assign_user_role(
#     user_id: int,
#     role_assignment: UserRoleAssignment,
#     current_user: User = Depends(get_current_user)
# ):
#     """Assign role to user (admin only)."""
#     try:
#         success = await auth_system.assign_role_to_user(user_id, role_assignment.role_id)
#         if success:
#             logger.info(f"Role {role_assignment.role_id} assigned to user {user_id} by {current_user.email}")
#             return {"message": "Role assigned successfully"}
#         else:
#             raise HTTPException(status_code=404, detail="User or role not found")
#     except Exception as e:
#         logger.error(f"Role assignment error: {e}")
#         raise HTTPException(status_code=500, detail="Role assignment failed")


# @app.get("/api/auth/roles")
# async def list_roles(current_user: User = Depends(get_current_user)):
#     """List all roles."""
#     try:
#         roles = await auth_system.get_all_roles()
#         return {"roles": roles}
#     except Exception as e:
#         logger.error(f"List roles error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to retrieve roles")


# @app.get("/api/auth/permissions")
# @require_permission("system", "monitor")
# async def list_permissions(current_user: User = Depends(get_current_user)):
#     """List all permissions (admin only)."""
#     try:
#         permissions = await auth_system.get_all_permissions()
#         logger.info(f"Permissions list accessed by: {current_user.email}")
#         return {"permissions": permissions}
#     except Exception as e:
#         logger.error(f"List permissions error: {e}")
#         raise HTTPException(status_code=500, detail="Failed to retrieve permissions")


# @app.post("/api/auth/roles/{role_id}/permissions")
# @require_permission("roles", "update")
# async def assign_role_permission(
#     role_id: int,
#     permission_assignment: RolePermissionAssignment,
#     current_user: User = Depends(get_current_user)
# ):
#     """Assign permission to role (admin only)."""
#     try:
#         success = await auth_system.assign_permission_to_role(role_id, permission_assignment.permission_id)
#         if success:
#             logger.info(f"Permission {permission_assignment.permission_id} assigned to role {role_id} by {current_user.email}")
#             return {"message": "Permission assigned successfully"}
#         else:
#             raise HTTPException(status_code=404, detail="Role or permission not found")
#     except Exception as e:
#         logger.error(f"Permission assignment error: {e}")
#         raise HTTPException(status_code=500, detail="Permission assignment failed")


# @app.get("/api/auth/health")
# async def auth_health_check():
#     """Health check for authentication system."""
#     try:
#         # Test database connectivity
#         test_result = await auth_system.health_check()
#         return {
#             "status": "healthy" if test_result else "unhealthy",
#             "timestamp": datetime.utcnow().isoformat(),
#             "database": "connected" if test_result else "disconnected"
#         }
#     except Exception as e:
#         logger.error(f"Auth health check error: {e}")
#         return {
#             "status": "unhealthy",
#             "timestamp": datetime.utcnow().isoformat(),
#             "error": str(e)
#         }

# Include admin router
app.include_router(admin_router)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
