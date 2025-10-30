
# --- RAGChatRequest and RAGChatResponse must be defined before any function/type hint that uses them ---
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class RAGChatRequest(BaseModel):
    """RAG-enhanced chat request following Pydantic AI patterns."""
    query: str = Field(..., description="User question or prompt")
    use_context: bool = Field(True, description="Whether to retrieve document context")
    max_context_chunks: int = Field(10, description="Number of context chunks to retrieve")
    model: str = Field("mistral:7b", description="Ollama model to use for generation")
    privacy_filter: str = Field('public', description="Privacy filter: 'public', 'private', or 'all'")
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
    fusion_metadata: Optional[dict] = Field(default=None, description="Metadata about fusion when search_method='fusion'")
    event_id: Optional[int] = Field(default=None, description="Analytics event id for feedback linkage")
    tokens_input: Optional[int] = Field(default=None, description="Number of input tokens processed")
    tokens_output: Optional[int] = Field(default=None, description="Number of output tokens generated")
    tokens_total: Optional[int] = Field(default=None, description="Total tokens (input + output)")
    tokens_per_second: Optional[float] = Field(default=None, description="Token generation rate (tokens/second)")
    response_time_ms: Optional[int] = Field(default=None, description="Total response time in milliseconds")

# --- End RAGChatRequest/RAGChatResponse early definition ---

import sys
import asyncio
import math
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Tuple
from contextlib import asynccontextmanager

import httpx
import ollama
import psycopg2
import uvicorn
from bs4 import BeautifulSoup
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from FlagEmbedding import FlagReranker
from psycopg2.extras import RealDictCursor

from knowledge_corrections import KnowledgeCorrection, insert_correction, get_correction_for_question

# Import RBAC components
sys.path.append('/app/utils')
# Updated import path for auth system to reflect utils package structure
from utils.auth_system import AuthSystem, UserCreate, UserLogin, UserResponse, PasswordResetRequest
from rbac_models import User, Role, Permission, UserRoleAssignment, RolePermissionAssignment
from rbac_middleware import RBACMiddleware, require_permission, get_current_user

# Document listing API models


# Main FastAPI app instance (must be defined before any usage)
app = FastAPI(
    title="Technical Service Assistant API",
    description="API for RAG system with data dictionary management and RBAC",
    version="1.0.0"
)

# Document listing API models and endpoint

# ...existing code...



# Correction API models and endpoint (must be after main app initialization)
class CorrectionRequest(BaseModel):
    question: str = Field(..., description="The user question being corrected.")
    original_answer: str = Field(..., description="The original answer given by the system.")
    corrected_answer: str = Field(..., description="The corrected answer provided by the user.")
    metadata: Optional[dict] = Field(default_factory=dict, description="Optional metadata about the correction.")
    user_id: Optional[str] = Field(None, description="ID of the user who submitted the correction.")

class CorrectionResponse(BaseModel):
    id: int
    status: str = "ok"

@app.post("/api/submit-correction", response_model=CorrectionResponse)
def submit_correction(req: CorrectionRequest, request: Request):
    """Submit a correction for a previous answer."""
    try:
        conn = get_db_connection()
        correction = KnowledgeCorrection(
            question=req.question,
            original_answer=req.original_answer,
            corrected_answer=req.corrected_answer,
            metadata=req.metadata,
            user_id=req.user_id
        )
        correction_id = insert_correction(conn, correction)
        conn.commit()
        conn.close()
        return CorrectionResponse(id=correction_id)
    except Exception as e:
        logger.error(f"Correction insert failure: {e}")
        raise HTTPException(status_code=500, detail="Failed to record correction")
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST

# Add reasoning engine to path
sys.path.append("/app")
sys.path.append("/app/reasoning_engine")

from cache import get_cached_web_results, store_web_results
from query_classifier import (QueryClassification, QueryType,
                              classify_and_optimize_query)
from temp_document_processor import temp_processor
from data_dictionary_api import router as data_dictionary_router

from config import get_settings
from utils.logging_config import setup_logging
from utils.metrics import metrics_collector, monitor_performance, performance_context
from utils.enhanced_search import enhanced_search, QueryAnalysis
from utils.document_discovery import document_query_handler, DocumentQueryType

# Import RBAC components
sys.path.append("/app")
from rbac_endpoints import rbac_router
from admin_endpoints import router as admin_router
from utils.rbac_middleware import RBACMiddleware, get_current_user

# Technical Service Assistant System Prompt
TECHNICAL_SERVICE_SYSTEM_PROMPT = """
You are a Technical Service Assistant, designed to answer questions about Sensus AMI Technology and Equipment and assist with troubleshooting issues.

You can write Microsoft SQL Server queries for the Sensus FlexNet database, referring to the data dictionary for the specific RNI version in question.

You can write PostgreSQL queries for the Sensus PostgreSQL AMDS, Router, FWDL databases, referring to a database dictionary for the specific database and RNI version in question.

Focus on:
- Sensus AMI (Advanced Metering Infrastructure) technology
- Equipment troubleshooting and technical support
- Database queries for FlexNet, AMDS, Router, and FWDL systems
- RNI (Radio Network Interface) version-specific guidance
- Technical documentation and procedures

Provide accurate, technical responses based on the available documentation and context.
"""

settings = get_settings()


# RAGChatRequest and RAGChatResponse must be defined before use in type hints


# Token counting utilities
def estimate_tokens(text: str) -> int:
    """Estimate token count using simple word/character heuristics."""
    # Rough approximation: ~4 characters per token for English text
    return max(1, len(text) // 4)

def calculate_tokens_per_second(token_count: int, time_seconds: float) -> float:
    """Calculate tokens per second rate."""
    if time_seconds <= 0:
        return 0.0
    return token_count / time_seconds

# Iterative Research Enhancement System
async def iterative_research_until_confident(
    query: str, 
    target_confidence: float = 0.95, 
    max_iterations: int = 25,
    model: str = "mistral:7b",
    privacy_filter: str = "public"
) -> RAGChatResponse:
    """Keep researching and gathering more context until confidence reaches target threshold."""
    
    logger.info(f"Starting iterative research for query: '{query}' with target confidence: {target_confidence}")
    
    iteration = 0
    best_response = None
    best_confidence = 0.0
    all_context_used = []
    research_log = []
    
    while iteration < max_iterations:
        iteration += 1
        logger.info(f"🔍 RESEARCH ITERATION {iteration}/{max_iterations} - Starting enhanced search cycle")
        logger.info(f"Current best confidence: {best_confidence:.3f}, Target: {target_confidence:.3f}")
        
        # Gradually increase context chunks per iteration
        max_chunks = min(3 + (iteration * 2), 10)  # 3, 5, 7, 9, 10+ sources
        
        # Try different search approaches each iteration
        search_approaches = [
            ("document_search", "Focus on technical documentation"),
            ("semantic_expansion", "Expand search with synonyms and related terms"),
            ("multi_angle", "Search from multiple perspectives"),
            ("deep_context", "Gather comprehensive background information"),
            ("expert_knowledge", "Apply domain expertise to the question")
        ]
        
        approach_name, approach_description = search_approaches[min(iteration-1, len(search_approaches)-1)]
        
        logger.info(f"📋 Using search strategy: '{approach_name}' - {approach_description}")
        logger.info(f"🎯 Context chunks for this iteration: {max_chunks}")
        
        # Enhanced search with different strategies
        enhanced_query = await enhance_query_for_iteration(query, iteration, approach_description, research_log)
        logger.info(f"🔄 Enhanced query: '{enhanced_query[:100]}{'...' if len(enhanced_query) > 100 else ''}'")
        
        # Perform search with current approach
        rag_request = RAGChatRequest(
            query=enhanced_query,
            use_context=True,
            max_context_chunks=max_chunks,
            model=model,
            privacy_filter=privacy_filter,
            temperature=0.3,  # Lower temperature for more focused research
            max_tokens=800
        )
        
        # Get response
        response = rag_chat(rag_request)
        
        # Add new context to cumulative context (avoid duplicates)
        new_context = [ctx for ctx in response.context_used if ctx not in all_context_used]
        all_context_used.extend(new_context)
        
        # Recalculate confidence with all accumulated context
        enhanced_confidence = calculate_enhanced_research_confidence(
            query, all_context_used, response.response, iteration, len(new_context)
        )
        
        research_log.append({
            "iteration": iteration,
            "approach": approach_name,
            "enhanced_query": enhanced_query,
            "new_context_count": len(new_context),
            "total_context_count": len(all_context_used),
            "confidence": enhanced_confidence,
            "response_length": len(response.response)
        })
        
        logger.info(f"Iteration {iteration}: confidence={enhanced_confidence:.3f}, "
                   f"new_context={len(new_context)}, total_context={len(all_context_used)}")
        
        # Update best response if this iteration improved confidence
        if enhanced_confidence > best_confidence:
            best_confidence = enhanced_confidence
            best_response = response
            best_response.confidence_score = enhanced_confidence
            best_response.context_used = all_context_used.copy()
            best_response.search_method = f"iterative_research_iter_{iteration}"
            
            # Add research metadata
            if not best_response.fusion_metadata:
                best_response.fusion_metadata = {}
            best_response.fusion_metadata.update({
                "research_iterations": iteration,
                "research_log": research_log,
                "target_confidence": target_confidence,
                "achieved_confidence": enhanced_confidence,
                "total_context_gathered": len(all_context_used)
            })
        
        # Check if we've reached target confidence
        if enhanced_confidence >= target_confidence:
            logger.info(f"✅ Target confidence {target_confidence} achieved in {iteration} iterations "
                       f"(final confidence: {enhanced_confidence:.3f})")
            break
            
        # Early stopping if confidence isn't improving
        if iteration > 2 and enhanced_confidence < best_confidence * 0.98:
            logger.info(f"⚠️ Confidence not improving significantly, stopping early at iteration {iteration}")
            break
    
    # Final response preparation
    if best_response:
        best_response.search_method = f"iterative_research_final_{iteration}_iters"
        logger.info(f"🔍 Research complete: {iteration} iterations, "
                   f"confidence: {best_confidence:.3f}, "
                   f"context_chunks: {len(all_context_used)}")
        return best_response
    
    # Fallback if something went wrong
    logger.warning("Iterative research failed, returning basic response")
    return rag_chat(RAGChatRequest(
        query=query, 
        model=model, 
        privacy_filter=privacy_filter,
        use_context=True,
        max_context_chunks=10,
        temperature=0.7,
        max_tokens=512
    ))

async def enhance_query_for_iteration(original_query: str, iteration: int, approach: str, research_log: list) -> str:
    """Enhance the query for each research iteration with different strategies."""
    
    if iteration == 1:
        return original_query  # First iteration uses original query
    
    # Extract key terms from previous research
    previous_findings = []
    for log_entry in research_log:
        if log_entry.get("new_context_count", 0) > 0:
            previous_findings.append(f"Found {log_entry['new_context_count']} new sources")
    
    enhancement_strategies = {
        2: f"{original_query} technical specifications details documentation",
        3: f"comprehensive information about {original_query} including background context",
        4: f"{original_query} expert knowledge troubleshooting advanced configuration",
        5: f"complete reference material for {original_query} all related topics"
    }
    
    return enhancement_strategies.get(iteration, original_query)

def calculate_enhanced_research_confidence(
    query: str, 
    context_chunks: list, 
    response: str, 
    iteration: int, 
    new_context_count: int
) -> float:
    """Calculate enhanced confidence score for iterative research."""
    
    # Base confidence from standard calculation
    base_confidence = calculate_rag_confidence(query, context_chunks, response)
    
    # Boost confidence based on research depth
    iteration_bonus = min(0.1, iteration * 0.02)  # Up to 10% bonus for multiple iterations
    context_bonus = min(0.1, len(context_chunks) * 0.005)  # Bonus for more context
    new_context_bonus = min(0.05, new_context_count * 0.01)  # Bonus for finding new info
    
    # Response quality indicators
    response_length_bonus = min(0.05, len(response) / 2000 * 0.05)  # Longer responses often more complete
    
    # Calculate enhanced confidence
    enhanced_confidence = min(0.99, base_confidence + iteration_bonus + context_bonus + 
                             new_context_bonus + response_length_bonus)
    
    return enhanced_confidence

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="reranker",
    log_level=getattr(settings, "log_level", "INFO"),
    log_file=f'/app/logs/reranker_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True,
)

# Initialize the Ollama client using configured host (derive host from embeddings URL if possible)
ollama_host = settings.ollama_url.rsplit("/api", 1)[0] if "/api" in settings.ollama_url else settings.ollama_url
ollama_client = ollama.Client(host=ollama_host)

def get_ollama_client(instance_url: Optional[str] = None) -> ollama.Client:
    """Get Ollama client for specific instance or default."""
    if instance_url:
        # Convert internal container URL to external URL if needed
        if "ollama-server-1:11434" in instance_url:
            return ollama.Client(host="http://localhost:11434")
        elif "ollama-server-2:11435" in instance_url:
            return ollama.Client(host="http://localhost:11435")
        elif "ollama-server-3:11436" in instance_url:
            return ollama.Client(host="http://localhost:11436")
        elif "ollama-server-4:11437" in instance_url:
            return ollama.Client(host="http://localhost:11437")
    return ollama_client


# Add RBAC middleware
try:
    app.add_middleware(RBACMiddleware)
    logger.info("RBAC middleware added successfully")
except Exception as e:
    logger.warning(f"Could not add RBAC middleware: {e}")

# Initialize Prometheus metrics
REQUEST_COUNT = Counter('reranker_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('reranker_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
ACTIVE_REQUESTS = Gauge('reranker_active_requests', 'Active requests')
ROUTING_ACCURACY = Gauge('reranker_routing_accuracy', 'Intelligent routing accuracy')
MODEL_SELECTION_COUNT = Counter('reranker_model_selection_total', 'Model selection count', ['model', 'instance'])
OLLAMA_HEALTH = Gauge('reranker_ollama_health', 'Ollama instance health', ['instance'])
SEARCH_OPERATIONS = Counter('reranker_search_operations_total', 'Search operations', ['type', 'status'])
EMBEDDINGS_GENERATED = Counter('reranker_embeddings_generated_total', 'Embeddings generated')
DATABASE_OPERATIONS = Counter('reranker_database_operations_total', 'Database operations', ['operation', 'status'])

# Include data dictionary router
app.include_router(data_dictionary_router)
app.include_router(rbac_router)
app.include_router(admin_router)

# Add metrics collection middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Enhanced middleware to collect comprehensive API request metrics."""
    # Skip metrics collection for the metrics endpoint itself
    if request.url.path == "/metrics":
        return await call_next(request)
    
    start_time = time.time()
    ACTIVE_REQUESTS.inc()
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Record Prometheus metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=str(response.status_code)
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        # Also record legacy metrics for compatibility
        metrics_collector.record_api_request(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration=duration
        )
        
        return response
    except Exception as e:
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status="500"
        ).inc()
        raise
    finally:
        ACTIVE_REQUESTS.dec()

# Lazy-load reranker model to reduce startup latency
_reranker_model: Optional[FlagReranker] = None

# Initialize reasoning engine (lazy-loaded)
_reasoning_orchestrator = None


def get_reranker():
    global _reranker_model
    if _reranker_model is None:
        logger.info(f"Loading reranker model {settings.rerank_model}")
        _reranker_model = FlagReranker(settings.rerank_model, use_fp16=True)
    return _reranker_model


async def get_reasoning_orchestrator():
    """Get or create reasoning orchestrator instance."""
    global _reasoning_orchestrator
    if _reasoning_orchestrator is None:
        try:
            # Import reasoning engine components
            from reasoning_engine.orchestrator import ReasoningOrchestrator

            # Create mock search client for reasoning engine
            class SearchClient:
                async def search(self, query: str, top_k: int = 5):
                    # Use existing search functionality
                    try:
                        query_embedding = ollama_client.embeddings(
                            model=settings.embedding_model.split(":")[0], prompt=query
                        )["embedding"]

                        conn = get_db_connection()
                        cursor = conn.cursor(cursor_factory=RealDictCursor)
                        cursor.execute(
                            """
                            SELECT c.content, c.metadata
                            FROM document_chunks c
                            WHERE c.embedding IS NOT NULL
                            ORDER BY c.embedding <-> %s::vector
                            LIMIT %s
                            """,
                            (query_embedding, top_k),
                        )
                        results = cursor.fetchall()
                        cursor.close()
                        conn.close()

                        # Convert to expected format
                        search_results = []
                        for result in results:

                            class SearchResult:
                                def __init__(self, text, metadata):
                                    self.text = text
                                    self.metadata = metadata

                            search_results.append(SearchResult(result["text"], result["metadata"] or {}))

                        return search_results

                    except Exception as e:
                        logger.error(f"Search failed: {e}")
                        return []

            search_client = SearchClient()

            _reasoning_orchestrator = ReasoningOrchestrator(
                search_client=search_client, ollama_client=ollama_client, db_client=None, settings=settings
            )
            logger.info("Reasoning orchestrator initialized")

        except Exception as e:
            logger.error(f"Failed to initialize reasoning orchestrator: {e}")
            _reasoning_orchestrator = None

    return _reasoning_orchestrator


class RerankRequest(BaseModel):
    query: str
    passages: List[str]
    top_k: int = settings.rerank_top_k
    privacy_filter: str = Field('public', description="Privacy filter: 'public', 'private', or 'all'")


class RerankResponse(BaseModel):
    reranked: List[str]
    scores: List[float]
    confidence_score: float = Field(0.9, ge=0.0, le=1.0, description="Overall reranking confidence (0-1)")
    response_time_ms: Optional[int] = Field(default=None, description="Reranking processing time in milliseconds")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    confidence_score: float = Field(0.8, ge=0.0, le=1.0, description="Confidence in chat response (0-1)")
    model: str = Field(..., description="Model used for generation")
    tokens_input: Optional[int] = Field(default=None, description="Number of input tokens processed")
    tokens_output: Optional[int] = Field(default=None, description="Number of output tokens generated")
    tokens_total: Optional[int] = Field(default=None, description="Total tokens (input + output)")
    tokens_per_second: Optional[float] = Field(default=None, description="Token generation rate (tokens/second)")
    response_time_ms: Optional[int] = Field(default=None, description="Total response time in milliseconds")


class RAGChatRequest(BaseModel):
    """RAG-enhanced chat request following Pydantic AI patterns."""

    query: str = Field(..., description="User question or prompt")
    use_context: bool = Field(True, description="Whether to retrieve document context")
    max_context_chunks: int = Field(10, description="Number of context chunks to retrieve")
    # Default changed from deprecated llama2 to available mistral:7b
    model: str = Field("mistral:7b", description="Ollama model to use for generation")
    privacy_filter: str = Field('public', description="Privacy filter: 'public', 'private', or 'all'")
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
    event_id: Optional[int] = Field(default=None, description="Analytics event id for feedback linkage")
    # Token performance metrics
    tokens_input: Optional[int] = Field(default=None, description="Number of input tokens processed")
    tokens_output: Optional[int] = Field(default=None, description="Number of output tokens generated")
    tokens_total: Optional[int] = Field(default=None, description="Total tokens (input + output)")
    tokens_per_second: Optional[float] = Field(default=None, description="Token generation rate (tokens/second)")
    response_time_ms: Optional[int] = Field(default=None, description="Total response time in milliseconds")


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    event_id: Optional[int] = Field(None, description="Associated search_events id")
    query: str = Field(..., description="Original user query")
    response_excerpt: Optional[str] = Field(
        None, description="Excerpt of model response (server can derive if omitted)"
    )
    search_method: str = Field(..., description="Method used (rag, hybrid, fusion, intelligent_hybrid, etc.)")
    model_used: Optional[str] = Field(None, description="Model that generated the answer")
    rating: str = Field(..., description="'up' or 'down'")
    comment: Optional[str] = Field(None, description="Optional user comment")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    fusion_used: Optional[bool] = Field(None, description="Whether fusion occurred")
    cache_hit: Optional[bool] = Field(None, description="Whether cache was used in retrieval")


class FeedbackResponse(BaseModel):
    id: int
    status: str = "ok"


class FeedbackSummary(BaseModel):
    total: int
    up: int
    down: int
    helpful_rate: float
    by_method: Dict[str, Dict[str, int]]
    last_24h: Dict[str, int]


class DocumentInfo(BaseModel):
    """Document information for knowledge base browsing."""
    
    id: int
    file_name: str
    title: Optional[str] = None
    document_type: Optional[str] = None
    product_name: Optional[str] = None
    product_version: Optional[str] = None
    privacy_level: str = "public"
    file_size: Optional[int] = None
    chunk_count: int = 0
    processed_at: Optional[str] = None
    created_at: str


class DocumentListRequest(BaseModel):
    """Request for listing documents with optional filters."""
    
    limit: int = Field(20, ge=1, le=100, description="Maximum number of documents to return")
    offset: int = Field(0, ge=0, description="Number of documents to skip")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    product_name: Optional[str] = Field(None, description="Filter by product name")
    privacy_level: Optional[str] = Field(None, description="Filter by privacy level (public/private)")
    search_term: Optional[str] = Field(None, description="Search in document titles and names")
    sort_by: str = Field("created_at", description="Sort field: created_at, file_name, chunk_count")
    sort_order: str = Field("desc", description="Sort order: asc or desc")


class DocumentListResponse(BaseModel):
    """Response containing list of documents with metadata."""
    
    documents: List[DocumentInfo]
    total_count: int
    offset: int
    limit: int
    has_more: bool


class DocumentStatsResponse(BaseModel):
    """Knowledge base statistics."""
    
    total_documents: int
    total_chunks: int
    document_types: Dict[str, int]
    product_breakdown: Dict[str, int]
    privacy_breakdown: Dict[str, int]
    avg_chunks_per_document: float
    last_processed: Optional[str] = None


class HybridSearchRequest(BaseModel):
    """Request for hybrid RAG + web search."""

    query: str = Field(..., description="User question")
    confidence_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Confidence threshold for web fallback")
    max_context_chunks: int = Field(10, description="Number of context chunks to retrieve")
    # Default changed from deprecated llama2 to available mistral:7b
    model: str = Field("mistral:7b", description="Ollama model to use for generation")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Generation temperature")
    enable_adaptive_threshold: bool = Field(True, description="Enable adaptive confidence threshold optimization")
    enable_enhanced_reranking: bool = Field(True, description="Enable enhanced reranking based on query analysis")
    max_tokens: int = Field(512, ge=64, le=2048, description="Maximum tokens to generate")
    enable_web_search: bool = Field(True, description="Enable web search fallback")
    privacy_filter: str = Field('public', description="Privacy filter: 'public', 'private', or 'all'")
    # Iterative Research Enhancement
    enable_iterative_research: bool = Field(False, description="Enable iterative research until high confidence")
    target_confidence: float = Field(0.95, ge=0.7, le=0.99, description="Target confidence for iterative research")
    max_research_iterations: int = Field(5, ge=1, le=10, description="Maximum research iterations")


class WebSearchResult(BaseModel):
    """Individual web search result."""

    title: str
    url: str
    content: str
    score: float


class QuestionType(str, Enum):
    """Question categories for model selection."""

    TECHNICAL = "technical"
    CODE = "code"
    CREATIVE = "creative"
    FACTUAL = "factual"
    MATH = "math"
    CHAT = "chat"


class ModelSelectionRequest(BaseModel):
    """Request for intelligent model selection."""

    query: str = Field(..., description="User question/prompt")
    prefer_speed: bool = Field(False, description="Prioritize speed over quality")
    require_context: bool = Field(False, description="Needs large context window")
    exclude_models: List[str] = Field(default_factory=list, description="Models to avoid")


class ModelSelectionResponse(BaseModel):
    """Response with selected model and instance."""

    selected_model: str
    selected_instance: str
    instance_url: str
    question_type: QuestionType
    reasoning: str
    fallback_options: List[dict] = Field(default_factory=list)


# Reasoning Engine Models
class ReasoningRequest(BaseModel):
    """Request for advanced reasoning capabilities."""

    query: str = Field(..., description="Question requiring reasoning")
    reasoning_type: Optional[str] = Field(None, description="Type of reasoning (analytical, comparative, etc.)")
    context_documents: Optional[List[str]] = Field(default_factory=list, description="Context documents for reasoning")
    max_steps: int = Field(5, description="Maximum reasoning steps")
    temperature: float = Field(0.7, description="Temperature for generation")
    enable_caching: bool = Field(True, description="Enable result caching")


class ReasoningResponse(BaseModel):
    """Response from reasoning engine."""

    query: str
    reasoning_approach: str
    final_answer: str
    reasoning_type: Optional[str] = None
    complexity_level: str = "medium"
    reasoning_steps: List[dict] = Field(default_factory=list)
    confidence_score: float
    sources_used: List[str] = Field(default_factory=list)
    processing_time_ms: int
    cache_hit: bool = False
    error_message: Optional[str] = None


class TempDocProcessRequest(BaseModel):
    """Request to process temporarily uploaded document."""
    session_id: str
    file_path: str
    file_name: str


class TempAnalysisRequest(BaseModel):
    """Request to analyze temporarily uploaded document."""
    session_id: str
    query: str
    max_results: Optional[int] = 5


class TempAnalysisResponse(BaseModel):
    """Response from temporary document analysis."""
    session_id: str
    query: str
    file_name: str
    results: List[dict]
    confidence: float
    response: str


@dataclass
class OllamaInstance:
    """Ollama instance configuration."""

    host: str
    port: int
    name: str
    healthy: bool = True
    last_check: float = 0
    response_time: float = 0
    load_score: float = 0

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


def get_db_connection():
    return psycopg2.connect(
        host=settings.db_host,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        port=settings.db_port,
    )


def clamp_confidence(value: Optional[float], default: float = 0.0) -> float:
    """Clamp confidence scores to the valid 0..1 range."""
    if value is None or math.isnan(value):
        return max(0.0, min(1.0, default))
    return max(0.0, min(1.0, float(value)))


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


# -----------------------------
# Analytics / Metrics Recording
# -----------------------------
def record_search_event(
    query: str,
    search_method: str,
    confidence_score: Optional[float] = None,
    rag_confidence: Optional[float] = None,
    classification_type: Optional[str] = None,
    strategy: Optional[str] = None,
    response_time_ms: Optional[int] = None,
    context_chunk_count: Optional[int] = None,
    web_result_count: Optional[int] = None,
    fused_count: Optional[int] = None,
    model_used: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[int]:
    """Persist a search analytics event. Return inserted id or None on failure."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO search_events (
                query, search_method, confidence_score, rag_confidence, classification_type,
                strategy, response_time_ms, context_chunk_count, web_result_count, fused_count,
                model_used, error
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                query,
                search_method,
                confidence_score,
                rag_confidence,
                classification_type,
                strategy,
                response_time_ms,
                context_chunk_count,
                web_result_count,
                fused_count,
                model_used,
                error,
            ),
        )
        row_id = cur.fetchone()
        inserted_id = row_id[0] if row_id else None
        conn.commit()
        cur.close()
        conn.close()
        return inserted_id
    except Exception as e:
        logger.warning(f"Analytics insert failed: {e}")
        return None


# -----------------------------
# Feedback Endpoints
# -----------------------------
@app.post("/api/feedback", response_model=FeedbackResponse)
def submit_feedback(req: FeedbackRequest, request: Request):
    if not settings.enable_feedback:
        raise HTTPException(status_code=403, detail="Feedback disabled")
    rating_map = {"up": 1, "down": -1, "+1": 1, "-1": -1}
    if req.rating.lower() not in rating_map:
        raise HTTPException(status_code=400, detail="Invalid rating. Use 'up' or 'down'.")
    rating_val = rating_map[req.rating.lower()]
    excerpt = (req.response_excerpt or "")[:500]
    comment = (req.comment or "")[:2000]
    user_agent = request.headers.get("user-agent", "")[:300]
    ip_raw = request.client.host if request.client else "0.0.0.0"
    import hashlib

    ip_hash = hashlib.sha256(ip_raw.encode()).hexdigest()[:32]
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO search_feedback (
                    search_event_id, query, response_excerpt, search_method, model_used,
                    rating, comment, confidence_score, fusion_used, cache_hit, user_agent, ip_hash
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                req.event_id,
                req.query,
                excerpt,
                req.search_method,
                req.model_used,
                rating_val,
                comment if comment else None,
                req.confidence_score,
                req.fusion_used,
                req.cache_hit,
                user_agent,
                ip_hash,
            ),
        )
        row = cur.fetchone()
        fid = row[0] if row else -1
        conn.commit()
        cur.close()
        conn.close()
        if fid == -1:
            raise HTTPException(status_code=500, detail="Feedback insert anomaly")
        return FeedbackResponse(id=fid)
    except Exception as e:
        logger.error(f"Feedback insert failure: {e}")
        raise HTTPException(status_code=500, detail="Failed to record feedback")


@app.get("/api/feedback/summary", response_model=FeedbackSummary)
def feedback_summary():
    if not settings.enable_feedback:
        raise HTTPException(status_code=403, detail="Feedback disabled")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*), SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END), SUM(CASE WHEN rating=-1 THEN 1 ELSE 0 END) FROM search_feedback"
        )
        row = cur.fetchone() or (0, 0, 0)
        total = row[0] or 0
        up = row[1] or 0
        down = row[2] or 0
        helpful_rate = (up / total) if total else 0.0
        cur.execute(
            """SELECT search_method,
                              SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) AS up,
                              SUM(CASE WHEN rating=-1 THEN 1 ELSE 0 END) AS down,
                              COUNT(*) AS total
                       FROM search_feedback GROUP BY search_method"""
        )
        by_method_rows = cur.fetchall()
        by_method = {}
        for mrow in by_method_rows:
            by_method[mrow[0]] = {"up": mrow[1] or 0, "down": mrow[2] or 0, "total": mrow[3] or 0}
        cur.execute(
            """SELECT COUNT(*), SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END), SUM(CASE WHEN rating=-1 THEN 1 ELSE 0 END)
                       FROM search_feedback WHERE created_at >= NOW() - INTERVAL '24 hours'"""
        )
        r24 = cur.fetchone() or (0, 0, 0)
        cur.close()
        conn.close()
        last_24h = {"total": r24[0] or 0, "up": r24[1] or 0, "down": r24[2] or 0}
        return FeedbackSummary(
            total=total, up=up, down=down, helpful_rate=round(helpful_rate, 3), by_method=by_method, last_24h=last_24h
        )
    except Exception as e:
        logger.error(f"Feedback summary error: {e}")
        raise HTTPException(status_code=500, detail="Feedback summary failed")


@app.get("/api/feedback/recent")
def feedback_recent(limit: int = 50):
    if not settings.enable_feedback:
        raise HTTPException(status_code=403, detail="Feedback disabled")
    limit = min(max(limit, 1), 200)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, created_at, query, search_method, rating, model_used, confidence_score
                   FROM search_feedback ORDER BY created_at DESC LIMIT %s""",
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        items = []
        for r in rows:
            items.append(
                {
                    "id": r[0],
                    "created_at": r[1],
                    "query": r[2],
                    "search_method": r[3],
                    "rating": r[4],
                    "model_used": r[5],
                    "confidence_score": r[6],
                }
            )
        return {"limit": limit, "items": items}
    except Exception as e:
        logger.error(f"Feedback recent error: {e}")
        raise HTTPException(status_code=500, detail="Feedback recent failed")


def _aggregate_rows_to_dict(rows, key_index=0, value_index=1) -> Dict[str, int]:
    return {r[key_index]: r[value_index] for r in rows if r[key_index] is not None}


@app.post("/rerank", response_model=RerankResponse, dependencies=[Depends(require_api_key)])
def rerank(req: RerankRequest):
    if not req.passages:
        raise HTTPException(status_code=400, detail="No passages provided.")
    pairs = [(req.query, passage) for passage in req.passages]
    model = get_reranker()
    if model is None:  # type: ignore
        logger.error("Reranker model not loaded")
        raise HTTPException(status_code=500, detail="Reranker model unavailable")
    try:
        results = model.compute_score(pairs)
    except Exception as e:
        logger.exception("Reranker scoring failed")
        raise HTTPException(status_code=500, detail=f"Reranker error: {e}")
    scored = sorted(zip(req.passages, results), key=lambda x: x[1], reverse=True)
    reranked, scores = zip(*scored[: req.top_k]) if scored else ([], [])
    return RerankResponse(
        reranked=list(reranked), 
        scores=list(scores),
        confidence_score=clamp_confidence(max(scores) if scores else None, default=0.8),
        response_time_ms=0
    )


def search_documents_core(req: RerankRequest, current_user: Optional[User] = None) -> RerankResponse:
    """Shared implementation for document search."""
    if not req.passages:
        # If no passages provided, retrieve from database with privacy filtering
        try:
            # Predefine effective_filter to avoid unbound warnings
            effective_filter = req.privacy_filter
            if current_user:
                if current_user.role_id not in (1, 2) and effective_filter in ('all', 'private'):
                    effective_filter = 'public'
            else:
                effective_filter = 'public'

            query_embedding = ollama_client.embeddings(model=settings.embedding_model.split(":")[0], prompt=req.query)[
                "embedding"
            ]
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build privacy filter condition using documents table
            privacy_condition = ""
            # Enforce role-based privacy: non-auth users -> public only; employees/admin can request all
            # effective_filter already computed above

            if effective_filter != 'all':
                privacy_condition = "AND d.privacy_level = %s"
            
            cursor.execute(
                f"""
                SELECT c.content
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.embedding IS NOT NULL
                {privacy_condition}
                ORDER BY c.embedding <-> %s::vector
                LIMIT %s
                """,
                (effective_filter, query_embedding, settings.retrieval_candidates) if effective_filter != 'all' 
                else (query_embedding, settings.retrieval_candidates),
            )
            chunks = cursor.fetchall()
            cursor.close()
            conn.close()
            passages = [row["content"] for row in chunks]
        except Exception:
            logger.exception("Database search failed, falling back to direct text search")
            # Fallback: Use simple text search when embedding generation fails
            try:
                conn = get_db_connection()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                query_terms = req.query.lower().replace("'", "''")
                
                # Build privacy filter condition for text search using documents table
                privacy_condition = ""
                if effective_filter != 'all':
                    privacy_condition = "AND d.privacy_level = %s"
                
                cursor.execute(
                    f"""
                    SELECT c.content
                    FROM document_chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE LOWER(c.content) LIKE %s
                    {privacy_condition}
                    ORDER BY c.id DESC
                    LIMIT %s
                    """,
                    (f"%{query_terms}%", effective_filter, settings.retrieval_candidates) if effective_filter != 'all'
                    else (f"%{query_terms}%", settings.retrieval_candidates),
                )
                chunks = cursor.fetchall()
                cursor.close()
                conn.close()
                passages = [row["content"] for row in chunks]
                if not passages:
                    # If no text matches found, return a helpful message
                    passages = [
                        f"I couldn't find specific information about '{req.query}' in the {req.privacy_filter} documents. This may be due to temporary connectivity issues with the embedding service. Please try rephrasing your question or try again later."
                    ]
            except Exception as fallback_error:
                logger.exception("Fallback search also failed")
                raise HTTPException(status_code=500, detail=f"Search error: {fallback_error}")
    else:
        passages = req.passages

    if not passages:
        return RerankResponse(
            reranked=[], 
            scores=[],
            confidence_score=0.0,
            response_time_ms=0
        )

    pairs = [(req.query, passage) for passage in passages]
    model = get_reranker()
    try:
        results = model.compute_score(pairs)
    except Exception as e:
        logger.exception("Reranker scoring failed")
        raise HTTPException(status_code=500, detail=f"Reranker error: {e}")
    scored = sorted(zip(passages, results), key=lambda x: x[1], reverse=True)
    reranked, scores = zip(*scored[: req.top_k]) if scored else ([], [])
    return RerankResponse(
        reranked=list(reranked), 
        scores=list(scores),
        confidence_score=clamp_confidence(max(scores) if scores else None, default=0.8),
        response_time_ms=0  # We'll add proper timing later
    )


@app.post("/search", response_model=RerankResponse, dependencies=[Depends(require_api_key)])
def search_documents(req: RerankRequest, current_user: Optional[User] = Depends(lambda: None)):
    """Simple document search without LLM chat completion with privacy filtering"""
    return search_documents_core(req, current_user)

@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
def chat(req: ChatRequest):
    try:
        # 1. Generate embedding for query
        query_embedding = ollama_client.embeddings(model=settings.embedding_model.split(":")[0], prompt=req.message)[
            "embedding"
        ]
        # 2. Retrieve candidate passages
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT c.content
            FROM document_chunks c
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <-> %s::vector
            LIMIT %s
            """,
            (query_embedding, settings.retrieval_candidates),
        )
        chunks = cursor.fetchall()
        cursor.close()
        conn.close()
        if not chunks:
            return ChatResponse(
                reply="No relevant documents found for your question.",
                confidence_score=0.2,
                model="mistral:7b",
                response_time_ms=0
            )
        passages = [row["content"] for row in chunks]
        rerank_req = RerankRequest(query=req.message, passages=passages, privacy_filter='public')
        rerank_results = rerank(rerank_req)
        context = "\n".join(rerank_results.reranked)
        prompt = (
            f"{TECHNICAL_SERVICE_SYSTEM_PROMPT}\n\n"
            "Using ONLY the following context, answer the question.\n"
            "If information is missing, say you don't know.\n\nContext:\n" + context + "\n\nQuestion: " + req.message
        )
        llm_response = ollama_client.chat(model=settings.chat_model, messages=[{"role": "user", "content": prompt}])
        return ChatResponse(
            reply=llm_response["message"]["content"],
            confidence_score=0.8,
            model=settings.chat_model,
            response_time_ms=0  # We'll add proper timing later
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Chat endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


def build_rag_prompt(query: str, context_chunks: List[str]) -> str:
    """Build prompt with retrieved context for RAG responses using Technical Service Assistant system prompt."""
    if not context_chunks:
        return f"{TECHNICAL_SERVICE_SYSTEM_PROMPT}\\n\\nQuestion: {query}\\n\\nAnswer:"

    context_text = "\\n\\n".join(f"Context {i+1}: {chunk}" for i, chunk in enumerate(context_chunks))

    return f"""{TECHNICAL_SERVICE_SYSTEM_PROMPT}

Use the provided context from technical documentation to answer the question. If the context doesn't contain relevant information, say so clearly.

Context:
{context_text}

Question: {query}

Answer based on the context above:"""


@app.post("/api/smart-chat", response_model=RAGChatResponse)
async def smart_chat(request: RAGChatRequest):
    """Enhanced chat endpoint that handles both document discovery and RAG queries."""
    logger.info(f"SMART CHAT CALLED with query: {request.query[:50]}... model: {request.model}")
    try:
        # First, check if this is a document discovery query
        query_type, params = document_query_handler.analyze_query(request.query)
        
        if query_type:
            logger.info(f"Detected document query: {query_type.value} with params: {params}")
            return await handle_document_query(query_type, params, request)
        
        # Use intelligent routing to select the best model and instance
        routing = await intelligent_route(ModelSelectionRequest(query=request.query, prefer_speed=False, require_context=True))
        logger.info(f"Smart chat received request model: {request.model}")
        logger.info(f"Intelligent routing selected: {routing.selected_model} on {routing.selected_instance}")
        
        # Create new request with selected model if using default
        if request.model == "llama3.1:8b":  # Default model
            # Create new request object with the selected model
            updated_request = request.model_copy(update={"model": routing.selected_model})
            logger.info(f"Updated request model from {request.model} to {updated_request.model}")
            return rag_chat(updated_request, routing.instance_url)
        else:
            # Use original request with specified model
            logger.info(f"Using original model {request.model} with routing to {routing.instance_url}")
            return rag_chat(request, routing.instance_url)
        
    except Exception as e:
        logger.error(f"Smart chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Smart chat failed: {str(e)}")


async def handle_document_query(query_type: DocumentQueryType, params: Dict[str, str], 
                               request: RAGChatRequest) -> RAGChatResponse:
    """Handle document discovery queries with natural language responses."""
    try:
        if query_type == DocumentQueryType.GET_STATS:
            # Get document statistics
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_documents,
                    MAX(processed_at) as last_processed
                FROM documents 
                WHERE processing_status = 'processed'
            """)
            basic_stats = cursor.fetchone()
            
            cursor.execute("SELECT COUNT(*) as total_chunks FROM document_chunks")
            chunk_stats = cursor.fetchone()
            
            cursor.execute("""
                SELECT document_type, COUNT(*) as count 
                FROM documents 
                WHERE processing_status = 'processed' AND document_type IS NOT NULL
                GROUP BY document_type
            """)
            doc_types = {row['document_type']: row['count'] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT product_name, COUNT(*) as count 
                FROM documents 
                WHERE processing_status = 'processed' AND product_name IS NOT NULL
                GROUP BY product_name
            """)
            products = {row['product_name']: row['count'] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT privacy_level, COUNT(*) as count 
                FROM documents 
                WHERE processing_status = 'processed'
                GROUP BY privacy_level
            """)
            privacy = {row['privacy_level']: row['count'] for row in cursor.fetchall()}
            
            cursor.close()
            conn.close()
            
            stats = {
                'total_documents': basic_stats['total_documents'] if basic_stats else 0,
                'total_chunks': chunk_stats['total_chunks'] if chunk_stats else 0,
                'document_types': doc_types,
                'product_breakdown': products,
                'privacy_breakdown': privacy,
                'avg_chunks_per_document': (chunk_stats['total_chunks'] / max(basic_stats['total_documents'], 1)) if (basic_stats and chunk_stats) else 0,
                'last_processed': basic_stats['last_processed'].isoformat() if (basic_stats and basic_stats['last_processed']) else None
            }
            
            results = stats
            
        else:
            # Handle document listing queries
            doc_request = DocumentListRequest(
                limit=int(params.get('limit', 20)),
                offset=0,
                document_type=params.get('document_type'),
                product_name=params.get('product_name'),
                privacy_level=params.get('privacy_level'),
                search_term=params.get('search_term'),
                sort_by=params.get('sort_by', 'created_at'),
                sort_order=params.get('sort_order', 'desc')
            )
            
            # Get documents from database
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = ["d.processing_status = 'processed'"]
            query_params = []
            
            if doc_request.document_type:
                where_conditions.append("d.document_type = %s")
                query_params.append(doc_request.document_type)
                
            if doc_request.product_name:
                where_conditions.append("d.product_name = %s")
                query_params.append(doc_request.product_name)
                
            if doc_request.privacy_level:
                where_conditions.append("d.privacy_level = %s")
                query_params.append(doc_request.privacy_level)
                
            if doc_request.search_term:
                where_conditions.append("(d.file_name ILIKE %s OR d.title ILIKE %s)")
                search_pattern = f"%{doc_request.search_term}%"
                query_params.extend([search_pattern, search_pattern])
            
            where_clause = " AND ".join(where_conditions)
            
            # Get count and documents
            cursor.execute(f"SELECT COUNT(*) as total FROM documents d WHERE {where_clause}", query_params)
            count_result = cursor.fetchone()
            total_count = count_result['total'] if count_result else 0
            
            cursor.execute(f"""
                SELECT d.*, COALESCE(chunk_counts.chunk_count, 0) as chunk_count
                FROM documents d
                LEFT JOIN (
                    SELECT document_id, COUNT(*) as chunk_count 
                    FROM document_chunks 
                    GROUP BY document_id
                ) chunk_counts ON d.id = chunk_counts.document_id
                WHERE {where_clause}
                ORDER BY d.{doc_request.sort_by} {doc_request.sort_order.upper()}
                LIMIT %s
            """, query_params + [doc_request.limit])
            
            docs = []
            for row in cursor.fetchall():
                docs.append({
                    'id': row['id'],
                    'file_name': row['file_name'],
                    'document_type': row['document_type'],
                    'product_name': row['product_name'],
                    'product_version': row['product_version'],
                    'chunk_count': row['chunk_count'],
                    'processed_at': row['processed_at'].isoformat() if row['processed_at'] else None
                })
            
            cursor.close()
            conn.close()
            
            results = {
                'documents': docs,
                'total_count': total_count
            }
        
        # Generate natural language response
        response_prompt = document_query_handler.generate_response_prompt(query_type, params, results)
        
        # Use the appropriate model to generate a natural response
        try:
            ollama_response = ollama_client.generate(
                model=request.model,
                prompt=response_prompt,
                options={"temperature": request.temperature, "num_predict": request.max_tokens}
            )
            response_text = ollama_response.get("response", "I found the document information but couldn't format a response.")
            
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            # Fallback to structured response
            if query_type == DocumentQueryType.GET_STATS:
                response_text = f"I have {results['total_documents']} documents in my knowledge base with {results['total_chunks']} total content chunks."
            else:
                doc_count = len(results.get('documents', []))
                total = results.get('total_count', 0)
                response_text = f"I found {doc_count} documents" + (f" out of {total} total matches" if total > doc_count else "") + "."
        
        return RAGChatResponse(
            response=response_text,
            context_used=[],
            model=request.model,
            context_retrieved=False,
            confidence_score=0.9,  # High confidence for document queries
            search_method="document_discovery"
        )
        
    except Exception as e:
        logger.error(f"Document query error: {e}")
        raise HTTPException(status_code=500, detail=f"Document query failed: {str(e)}")


@app.post("/api/rag-chat", response_model=RAGChatResponse)
def rag_chat(request: RAGChatRequest, instance_url: Optional[str] = None, current_user: Optional[User] = Depends(lambda: None)):
    """RAG-enhanced chat endpoint combining retrieval and generation."""
    start_time = time.time()
    try:
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
                if current_user.role_id not in (1, 2) and effective_privacy in ('all', 'private'):
                    effective_privacy = 'public'
            else:
                effective_privacy = 'public'

            search_req = RerankRequest(query=request.query, passages=[], top_k=request.max_context_chunks, privacy_filter=effective_privacy)
            search_resp = search_documents_core(search_req, current_user)
            context_chunks = search_resp.reranked
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


@app.get("/health")
def health():
    # basic health only; extended will be separate
    return {"status": "ok"}


@app.get("/health/details", dependencies=[Depends(require_api_key)])
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
    OllamaInstance("ollama-server-1", 11434, "ollama-server-1-chat-qa"),          # Instance 1: Chat/QA
    OllamaInstance("ollama-server-2", 11434, "ollama-server-2-code-technical"),   # Instance 2: Code/Technical
    OllamaInstance("ollama-server-3", 11434, "ollama-server-3-reasoning-math"),   # Instance 3: Reasoning/Math
    OllamaInstance("ollama-server-4", 11434, "ollama-server-4-embeddings-search") # Instance 4: Embeddings/Search
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
                    response_time=health_check_time
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
                instance_name=target_instance.name,
                instance_url=target_instance.url,
                is_healthy=False
            )
            
            target_instance = await select_best_instance(instances)
            selected_model = "mistral:7b"

        # Record routing metrics
        routing_duration = time.time() - start_time
        
        # Record Prometheus metrics
        MODEL_SELECTION_COUNT.labels(
            model=selected_model,
            instance=target_instance.name
        ).inc()
        
        # Record legacy metrics for compatibility
        metrics_collector.record_model_request(
            model_name=selected_model,
            instance=target_instance.name,
            question_type=question_type.value,
            duration=routing_duration,
            status="success"
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
            model_name="unknown",
            instance="unknown", 
            question_type="unknown",
            duration=routing_duration,
            status="error"
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
                        response_time=instance.response_time
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
                        instance_name=instance.name,
                        instance_url=instance.url,
                        is_healthy=False
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
                instance_name=instance.name,
                instance_url=instance.url,
                is_healthy=False
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
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
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


def calculate_rag_confidence(query: str, context_chunks: List[str], response: str, 
                           query_analysis: Optional[QueryAnalysis] = None) -> float:
    """Calculate confidence score for RAG response with optional enhanced analysis."""
    if not context_chunks:
        return 0.0
    
    # Use enhanced confidence calculation if query analysis is available
    if query_analysis:
        return enhanced_search.calculate_enhanced_confidence(
            query, context_chunks, response, query_analysis
        )
    
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
                        raw_results.append({
                            "title": data.get("Heading", query),
                            "url": data.get("AbstractURL", ""),
                            "content": data.get("AbstractText", ""),
                            "score": 1.0,
                        })
                    
                    # Process related topics
                    for i, topic in enumerate(data.get("RelatedTopics", [])[:max_results-len(raw_results)]):
                        if isinstance(topic, dict) and topic.get("Text"):
                            raw_results.append({
                                "title": topic.get("Text", "").split(" - ")[0],
                                "url": topic.get("FirstURL", ""),
                                "content": topic.get("Text", ""),
                                "score": 1.0 - (i * 0.1),
                            })
                    
                    # If no instant answers, try web search fallback with simple Wikipedia/DuckDuckGo
                    if not raw_results:
                        # Create basic web search results from query
                        raw_results.append({
                            "title": f"Search results for: {query}",
                            "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                            "content": f"Search for '{query}' using DuckDuckGo privacy-focused search.",
                            "score": 0.8,
                        })
                    
                    if raw_results:
                        store_web_results(query, raw_results)
                    results = [WebSearchResult(**r) for r in raw_results]
                    logger.info(f"DuckDuckGo search returned {len(results)} results (cached)")
                    return results

            except Exception as search_error:
                logger.warning(f"DuckDuckGo search failed: {search_error}")

            # Minimal fallback result
            fallback_results = [{
                "title": f"External search: {query}",
                "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                "content": f"For comprehensive results about '{query}', try searching on DuckDuckGo.",
                "score": 0.5,
            }]
            
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
            
            logger.info(f"Query analysis: complexity={query_analysis.complexity.value}, "
                       f"type={query_analysis.question_type}, "
                       f"adaptive_threshold={adaptive_threshold:.3f}, "
                       f"optimal_model={query_analysis.optimal_model}")
        
        # Check if iterative research is enabled
        if request.enable_iterative_research:
            logger.info(f"Starting iterative research for query: {request.query}")
            rag_response = await iterative_research_until_confident(
                request.query,
                request.target_confidence,
                request.max_research_iterations,
                request.model,
                request.privacy_filter
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
            
            logger.info(f"Enhanced confidence: {enhanced_confidence:.3f} "
                       f"(original: {original_confidence:.3f})")

        # Record RAG confidence metrics with analysis context
        metrics_collector.record_rag_confidence(
            confidence=rag_response.confidence_score, 
            search_method=f"hybrid_rag_{query_analysis.complexity.value if query_analysis else 'standard'}"
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
        
        logger.info(f"Enhanced search analysis - Query: '{request.query[:50]}...', "
                   f"Complexity: {query_analysis.complexity.value}, "
                   f"Type: {query_analysis.question_type}, "
                   f"Strategy: {query_analysis.search_strategy.value}, "
                   f"Adaptive threshold: {query_analysis.confidence_threshold:.3f}")
        
        # Route to specialized model based on analysis
        optimized_model = query_analysis.optimal_model
        
        # Determine chunk count based on complexity
        chunk_count = request.max_context_chunks
        if query_analysis.complexity == "complex":
            chunk_count = min(chunk_count + 3, 10)  # More context for complex queries
        elif query_analysis.complexity == "simple":
            chunk_count = max(chunk_count - 1, 3)   # Less context for simple queries
        
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
        
        with performance_context("enhanced_rag_search", {
            "complexity": query_analysis.complexity.value,
            "question_type": query_analysis.question_type,
            "model": optimized_model
        }):
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
            search_method=f"enhanced_{query_analysis.complexity.value}_{query_analysis.question_type}"
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
            logger.info(f"Enhanced RAG success - Complexity: {query_analysis.complexity.value}, "
                       f"Model: {optimized_model}, Strategy: {query_analysis.search_strategy.value}, "
                       f"Confidence: {original_confidence:.3f} → {enhanced_confidence:.3f}")
            
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
                        max_research_iterations=25
                    )
                    
                    # Create classification object for compatibility
                    from query_classifier import QueryClassification, QueryType
                    classification = QueryClassification(
                        query_type=QueryType(query_analysis.question_type),
                        confidence=0.8,
                        reasoning="Enhanced search analysis",
                        suggested_confidence_threshold=query_analysis.confidence_threshold,
                        prefer_web_search=True,
                        keywords_matched=query_analysis.domain_keywords[:3]
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
        cursor.execute("""
            SELECT 
                COUNT(*) as total_documents,
                MAX(processed_at) as last_processed
            FROM documents 
            WHERE processing_status = 'processed'
        """)
        basic_stats = cursor.fetchone()
        
        # Get total chunks
        cursor.execute("""
            SELECT COUNT(*) as total_chunks 
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id 
            WHERE d.processing_status = 'processed'
        """)
        chunk_stats = cursor.fetchone()
        
        # Get document type breakdown
        cursor.execute("""
            SELECT document_type, COUNT(*) as count 
            FROM documents 
            WHERE processing_status = 'processed' AND document_type IS NOT NULL
            GROUP BY document_type 
            ORDER BY count DESC
        """)
        type_breakdown = {row['document_type']: row['count'] for row in cursor.fetchall()}
        
        # Get product breakdown
        cursor.execute("""
            SELECT product_name, COUNT(*) as count 
            FROM documents 
            WHERE processing_status = 'processed' AND product_name IS NOT NULL
            GROUP BY product_name 
            ORDER BY count DESC
        """)
        product_breakdown = {row['product_name']: row['count'] for row in cursor.fetchall()}
        
        # Get privacy breakdown
        cursor.execute("""
            SELECT privacy_level, COUNT(*) as count 
            FROM documents 
            WHERE processing_status = 'processed'
            GROUP BY privacy_level 
            ORDER BY count DESC
        """)
        privacy_breakdown = {row['privacy_level']: row['count'] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        
        total_docs = basic_stats['total_documents'] if basic_stats else 0
        total_chunks = chunk_stats['total_chunks'] if chunk_stats else 0
        avg_chunks = total_chunks / max(total_docs, 1)
        
        last_processed = None
        if basic_stats and basic_stats['last_processed']:
            last_processed = basic_stats['last_processed'].isoformat()
        
        return DocumentStatsResponse(
            total_documents=total_docs,
            total_chunks=total_chunks,
            document_types=type_breakdown,
            product_breakdown=product_breakdown,
            privacy_breakdown=privacy_breakdown,
            avg_chunks_per_document=round(avg_chunks, 1),
            last_processed=last_processed
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
        total_count = count_result['total'] if count_result else 0
        
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
                id=row['id'],
                file_name=row['file_name'],
                title=row['title'],
                document_type=row['document_type'],
                product_name=row['product_name'],
                product_version=row['product_version'],
                privacy_level=row['privacy_level'] or 'public',
                file_size=row['file_size'],
                chunk_count=row['chunk_count'],
                processed_at=row['processed_at'].isoformat() if row['processed_at'] else None,
                created_at=row['created_at'].isoformat()
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
        cursor.execute("""
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
        """, [document_id])
        
        document = cursor.fetchone()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get chunk breakdown by type
        cursor.execute("""
            SELECT chunk_type, COUNT(*) as count
            FROM document_chunks 
            WHERE document_id = %s
            GROUP BY chunk_type
            ORDER BY count DESC
        """, [document_id])
        
        chunk_types = {row['chunk_type']: row['count'] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        
        return {
            **dict(document),
            "chunk_types": chunk_types,
            "processed_at": document['processed_at'].isoformat() if document['processed_at'] else None,
            "created_at": document['created_at'].isoformat(),
            "first_chunk_created": document['first_chunk_created'].isoformat() if document['first_chunk_created'] else None,
            "last_chunk_created": document['last_chunk_created'].isoformat() if document['last_chunk_created'] else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document details")


@app.post("/api/temp-process")
async def process_temp_document(request: TempDocProcessRequest):
    """Process temporarily uploaded document for analysis."""
    try:
        temp_doc = temp_processor.process_file(
            request.file_path, 
            request.file_name, 
            request.session_id
        )
        
        # Generate embeddings for search capability
        success = temp_processor.generate_embeddings(request.session_id)
        
        return {
            "success": True,
            "session_id": request.session_id,
            "file_name": temp_doc.file_name,
            "content_length": len(temp_doc.content),
            "chunk_count": len(temp_doc.chunks),
            "embeddings_generated": success,
            "message": "Document processed successfully"
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
            request.query, 
            request.session_id, 
            request.max_results or 5
        )
        
        if not search_results:
            return TempAnalysisResponse(
                session_id=request.session_id,
                query=request.query,
                file_name=session_info["file_name"],
                results=[],
                confidence=0.0,
                response="No relevant content found in the uploaded document."
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
        llm_response = ollama_client.chat(
            model=settings.chat_model, 
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Format results for response
        formatted_results = [
            {
                "content": result[0][:500] + "..." if len(result[0]) > 500 else result[0],
                "similarity": result[1],
                "rank": i + 1
            }
            for i, result in enumerate(search_results)
        ]
        
        return TempAnalysisResponse(
            session_id=request.session_id,
            query=request.query,
            file_name=session_info["file_name"],
            results=formatted_results,
            confidence=confidence,
            response=llm_response["message"]["content"]
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
            "message": f"Cleaned up {expired_count} expired sessions"
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


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/metrics/health")
async def metrics_health():
    """Health check endpoint with basic metrics."""
    try:
        # Check Ollama instances health
        ollama_health = {}
        for i in range(1, 5):
            port = 11433 + i
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
            "services": {
                "database": db_healthy,
                "ollama_instances": ollama_health
            }
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


if __name__ == "__main__":
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
