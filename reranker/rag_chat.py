"""
RAG-Enhanced Chat Endpoint

Combines vector retrieval with LLM generation for document-aware responses.
Follows Pydantic AI best practices from https://ai.pydantic.dev/
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import httpx
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from httpx import Response
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from config import get_model_num_ctx

# Advanced multi-layer caching for embeddings and inference
from reranker.advanced_cache import get_advanced_cache

# Optional intelligent router import (kept local to avoid circular issues at startup)
from reranker.intelligent_router import ModelSelectionRequest, QuestionType, intelligent_router

# Advanced load balancing for Ollama instances
from reranker.load_balancer import RequestType, get_load_balancer

# Query optimization for improved retrieval
from reranker.query_optimizer import optimize_query

# Query-Response caching for 15-20% latency reduction
from reranker.query_response_cache import cache_rag_response, get_query_response_cache
from scripts.analysis.hybrid_search import HybridSearch
from utils.redis_cache import track_instance_usage, track_model_usage, track_question_type

from .reranker_config import get_settings

# Setup basic logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


settings = get_settings()
CHAT_GENERATION_TIMEOUT = getattr(settings, "generation_timeout_seconds", 300)


class RAGChatRequest(BaseModel):
    """Request model for RAG chat."""

    query: str = Field(..., description="User query")
    use_context: bool = Field(True, description="Whether to use document context")
    max_context_chunks: int = Field(5, description="Maximum number of context chunks to retrieve")
    model: str = Field("rni-mistral", description="LLM model to use; set to 'rni-mistral' or 'auto' for smart routing")
    temperature: float = Field(0.2, description="Generation temperature")
    max_tokens: int = Field(500, description="Maximum tokens to generate")
    stream: bool = Field(True, description="Whether to stream the response")


class RAGChatResponse(BaseModel):
    """Response model for RAG chat."""

    response: str = Field(..., description="Generated response")
    context_used: List[str] = Field(default_factory=list, description="Context chunks used")
    context_metadata: List[Dict[str, Any]] = Field(
        default_factory=list, description="Context metadata with document info"
    )
    web_sources: List[Dict[str, Any]] = Field(default_factory=list, description="Web sources used for citations")
    model: str = Field(..., description="Model used for generation")
    context_retrieved: bool = Field(..., description="Whether context was retrieved")
    confidence: float = Field(0.5, description="Confidence score in the response (0.0-1.0)")
    fallback_used: bool = Field(False, description="Whether fallback strategy was used")


class BatchRAGChatRequest(BaseModel):
    """Request model for batch RAG chat."""

    queries: List[str] = Field(..., description="List of user queries to process")
    max_concurrent: int = Field(4, description="Maximum concurrent requests", ge=1, le=8)
    max_context_chunks: int = Field(5, description="Maximum number of context chunks per query")
    model: str = Field("rni-mistral", description="LLM model to use")
    temperature: float = Field(0.2, description="Generation temperature")
    max_tokens: int = Field(500, description="Maximum tokens per response")


class BatchRAGChatResponse(BaseModel):
    """Response model for batch RAG chat."""

    responses: List[RAGChatResponse] = Field(..., description="List of responses, one per query")
    total_queries: int = Field(..., description="Total number of queries processed")
    successful_responses: int = Field(..., description="Number of successful responses")
    processing_time_seconds: float = Field(..., description="Total processing time")


class RAGChatService:
    """Service for RAG-enhanced chat functionality."""

    def __init__(self, ollama_urls: Optional[List[str]] = None, reranker_url: Optional[str] = None):
        """Initialize the RAG chat service."""
        settings = get_settings()

        if ollama_urls:
            self.ollama_urls = ollama_urls
        else:
            instances_str = os.getenv("OLLAMA_INSTANCES")
            if instances_str:
                self.ollama_urls = [url.strip() for url in instances_str.split(",")]
            else:
                # Fallback to all 8 instances for load balancing
                self.ollama_urls = [
                    "http://ollama-server-1:11434",
                    "http://ollama-server-2:11434",
                    "http://ollama-server-3:11434",
                    "http://ollama-server-4:11434",
                    "http://ollama-server-5:11434",
                    "http://ollama-server-6:11434",
                    "http://ollama-server-7:11434",
                    "http://ollama-server-8:11434",
                ]
        logger.info(f"Using all {len(self.ollama_urls)} Ollama instances for load balancing")

        # Initialize load balancer for intelligent instance routing
        self.load_balancer = get_load_balancer(self.ollama_urls)

        # Initialize advanced caching (embeddings, inference, chunks)
        self.advanced_cache = get_advanced_cache()

        self.reranker_url = (
            reranker_url if reranker_url is not None else os.getenv("RERANKER_URL", "http://reranker:8008")
        )
        # Hybrid search instance (lazy)
        self._hybrid_search_instance: Optional[HybridSearch] = None

        # Load model configurations
        self.chat_model = settings.chat_model
        self.coding_model = settings.coding_model
        self.reasoning_model = settings.reasoning_model
        self.vision_model = settings.vision_model
        self.embedding_model = settings.embedding_model
        self.default_num_ctx = settings.default_model_num_ctx

        logger.info(f"Initialized RAGChatService with {len(self.ollama_urls)} Ollama instances: {self.ollama_urls}")
        logger.info(
            f"Models: chat={self.chat_model}, coding={self.coding_model}, reasoning={self.reasoning_model}, vision={self.vision_model}"
        )

        # Database connection for vector search
        self.db_host = settings.db_host
        self.db_name = settings.db_name
        self.db_user = settings.db_user
        self.db_password = settings.db_password
        self.db_port = settings.db_port

    def select_model(self, query: str) -> str:
        """Select appropriate model based on query content."""
        query_lower = query.lower()

        # Coding-related queries
        coding_keywords = [
            "code",
            "programming",
            "python",
            "javascript",
            "function",
            "class",
            "script",
            "debug",
            "error",
            "compile",
            "syntax",
        ]
        if any(keyword in query_lower for keyword in coding_keywords):
            return self.coding_model

        # Reasoning/complex queries
        reasoning_keywords = ["reason", "explain", "why", "analyze", "compare", "evaluate", "logic", "step", "process"]
        if any(keyword in query_lower for keyword in reasoning_keywords) or len(query) > 200:
            return self.reasoning_model

        # Vision-related (though text-only for now)
        vision_keywords = ["image", "diagram", "visual", "chart", "graph", "picture"]
        if any(keyword in query_lower for keyword in vision_keywords):
            return self.vision_model

        # Default to chat model
        return self.chat_model

    async def _determine_model_and_instance(self, query: str) -> Tuple[str, Optional[str], QuestionType, str, int]:
        """Use the intelligent router when available; fallback to local heuristics."""
        try:
            router_request = ModelSelectionRequest(query=query)
            router_response = await intelligent_router.route_request(router_request)
            logger.info(
                "Router selected %s on %s for %s questions (context: %d tokens)",
                router_response.selected_model,
                router_response.selected_instance,
                router_response.question_type.value,
                router_response.context_length,
            )
            return (
                router_response.selected_model,
                router_response.instance_url,
                router_response.question_type,
                router_response.complexity,
                router_response.context_length,
            )
        except Exception as exc:
            logger.warning(f"Router selection failed; falling back to heuristics: {exc}")
            question_type = intelligent_router.classify_question(query)
            complexity = intelligent_router.assess_complexity(query)
            # Default context length for fallback
            return self.select_model(query), None, question_type, complexity, 4096

    async def retrieve_context(self, query: str, max_chunks: int = 5) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Retrieve relevant context chunks using hierarchical search: RAG first, then web search."""
        logger.info(f"Starting context retrieval for query: {query[:50]}...")
        try:
            # Optimize query for better retrieval (removes stop words, etc.)
            optimization = optimize_query(query)
            optimized_query = optimization.get("reduced", query)
            keywords = optimization.get("keywords", [])
            expansions = optimization.get("expansions", [])

            logger.debug(
                f"Query optimization: original='{query[:40]}' optimized='{optimized_query[:40]}' keywords={keywords} expansions={expansions}"
            )

            # Step 1: Try hybrid search with query expansion for improved accuracy
            all_chunks = []
            all_metadata = []

            # Search with original optimized query
            try:
                rag_chunks, rag_metadata = await self._hybrid_search(optimized_query, max_chunks)
                all_chunks.extend(rag_chunks)
                all_metadata.extend(rag_metadata)
            except Exception as e:
                logger.warning(f"Hybrid search failed for optimized query: {e}")

            # Search with expansions if available
            if expansions:
                for expansion in expansions[:3]:  # Limit to 3 expansions to avoid too many searches
                    try:
                        exp_chunks, exp_metadata = await self._hybrid_search(expansion, max_chunks // 2)
                        all_chunks.extend(exp_chunks)
                        all_metadata.extend(exp_metadata)
                    except Exception as e:
                        logger.warning(f"Hybrid search failed for expansion '{expansion}': {e}")

            # Deduplicate and limit results
            if all_chunks:
                # Simple deduplication by content hash
                seen = set()
                unique_chunks = []
                unique_metadata = []
                for chunk, meta in zip(all_chunks, all_metadata):
                    chunk_hash = hash(chunk[:200])  # Hash first 200 chars
                    if chunk_hash not in seen:
                        seen.add(chunk_hash)
                        unique_chunks.append(chunk)
                        unique_metadata.append(meta)

                rag_chunks = unique_chunks[:max_chunks]
                rag_metadata = unique_metadata[:max_chunks]

            if rag_chunks:
                logger.info(f"Hybrid retrieved {len(rag_chunks)} context chunks for query: {query[:50]}...")
                return rag_chunks, rag_metadata

            # Fallback: vector DB search using embeddings
            query_embedding = await self._get_query_embedding(optimized_query)
            rag_chunks, rag_metadata = await self._vector_search(query_embedding, max_chunks)

            if rag_chunks:
                logger.info(f"Vector DB retrieved {len(rag_chunks)} RAG context chunks for query: {query[:50]}...")
                return rag_chunks, rag_metadata

            # Step 2: If no RAG results, try web search
            logger.info(f"No RAG results found, trying web search for query: {query[:50]}...")
            web_results = await self._web_search(optimized_query, max_chunks)

            if web_results:
                # Convert web results to context chunks
                context_chunks = [
                    f"Web Result: {result['title']}\n{result['content']}\nSource: {result['url']}"
                    for result in web_results
                ]
                # Create metadata for web results
                web_metadata = [
                    {
                        "content": result["content"],
                        "file_name": result["title"],
                        "document_type": "web",
                        "distance": 1.0 - result["score"],  # Convert score to distance-like metric
                    }
                    for result in web_results
                ]
                logger.info(f"Retrieved {len(context_chunks)} web search context chunks")
                return context_chunks, web_metadata

            # Step 3: If still no results, return empty
            logger.info(f"No context found for query: {query[:50]}...")
            return [], []

        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            return [], []

    async def _get_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for the query using Ollama with load balancing and caching."""
        # Check advanced embedding cache first
        cached_embedding = self.advanced_cache.get_embedding(query)
        if cached_embedding:
            logger.info(f"Embedding cache HIT for query: {query[:50]}...")
            return cached_embedding

        # Get next healthy embedding instance
        selected_url = await self.load_balancer.get_next_instance(RequestType.EMBEDDING)
        logger.info(f"Getting embedding for query: {query[:50]}... from Ollama instance: {selected_url}")

        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{selected_url}/api/embeddings",
                    json={
                        "model": self.embedding_model,
                        "prompt": query,
                    },
                    timeout=30.0,
                )
                response_time = (time.time() - start_time) * 1000  # Convert to ms

                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get("embedding", [])
                    # Cache the embedding for future use
                    self.advanced_cache.cache_embedding(query, embedding)
                    # Record successful embedding request
                    self.load_balancer.record_request(selected_url, response_time, success=True)
                    return embedding
                else:
                    self.load_balancer.record_request(
                        selected_url, response_time, success=False, error=f"HTTP {response.status_code}"
                    )
                    raise HTTPException(status_code=response.status_code, detail="Embedding generation failed")
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.load_balancer.record_request(selected_url, response_time, success=False, error=str(e))
            logger.error(f"Embedding generation failed: {e}")
            raise

    def _calculate_response_confidence(self, response: str, context_chunks: List[str], query: str, model: str) -> float:
        """Calculate confidence score for the response."""
        confidence = 0.5  # Base confidence

        # Context quality boost
        if context_chunks:
            # More context chunks = higher confidence
            context_boost = min(0.2, len(context_chunks) * 0.05)
            confidence += context_boost

            # Check if response contains context terms
            context_text = " ".join(context_chunks).lower()
            response_lower = response.lower()
            query_lower = query.lower()

            # Count matching terms between query/response and context
            query_terms = set(query_lower.split())
            response_terms = set(response_lower.split())
            context_terms = set(context_text.split())

            query_context_overlap = len(query_terms & context_terms)
            response_context_overlap = len(response_terms & context_terms)

            if query_context_overlap > 0:
                confidence += 0.1
            if response_context_overlap > 0:
                confidence += 0.1
        else:
            # No context = lower confidence
            confidence -= 0.2

        # Model quality adjustment
        model_lower = model.lower()
        if "llama3.2:3b" in model_lower:
            confidence -= 0.1  # Smaller model
        elif "mistral:7b" in model_lower or "codellama:7b" in model_lower:
            confidence += 0.05  # Good balance

        # Response length heuristic (too short = low confidence)
        if len(response.split()) < 10:
            confidence -= 0.1
        elif len(response.split()) > 50:
            confidence += 0.05  # Detailed responses

        # Check for uncertainty indicators
        uncertainty_terms = ["i'm not sure", "uncertain", "maybe", "possibly", "i think", "perhaps"]
        if any(term in response.lower() for term in uncertainty_terms):
            confidence -= 0.15

        return max(0.0, min(1.0, confidence))

    async def _vector_search(
        self, query_embedding: List[float], max_chunks: int
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Perform vector similarity search in the database."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
                port=self.db_port,
            )
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Convert embedding to PostgreSQL vector format
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

            cursor.execute(
                """
                SELECT
                    dc.content,
                    dc.embedding <=> %s::vector as distance,
                    d.file_name,
                    d.document_type
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                 WHERE dc.embedding IS NOT NULL
                 AND d.processing_status = 'processed'
                 AND d.privacy_level = 'public'
                ORDER BY dc.embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding_str, embedding_str, max_chunks),
            )

            results = cursor.fetchall()
            cursor.close()
            conn.close()

            # Extract content and metadata from results
            context_chunks = [row["content"] for row in results]
            context_metadata = [
                {
                    "content": row["content"],
                    "file_name": row["file_name"],
                    "document_type": row["document_type"],
                    "distance": row["distance"],
                }
                for row in results
            ]
            return context_chunks, context_metadata

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return [], []

    async def _hybrid_search(self, query: str, max_chunks: int) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Perform hybrid search (vector + BM25) using the HybridSearch module.

        This method uses a threadpool to avoid blocking the event loop because the
        HybridSearch implementation is synchronous and interacts with the DB.
        """
        try:
            # Initialize lazy hybrid search instance
            if not self._hybrid_search_instance:
                # Use default vector weight; can be overridden via env var
                alpha = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.7"))
                self._hybrid_search_instance = HybridSearch(embedding_model=self.embedding_model, alpha=alpha)

            # Run search in threadpool to avoid blocking
            results = await asyncio.to_thread(self._hybrid_search_instance.search, query, max_chunks)

            # Map results to context_chunks and metadata
            context_chunks = [r.get("text") for r in results]
            context_metadata = [
                {
                    "content": r.get("text"),
                    "file_name": r.get("document_name"),
                    "document_type": r.get("metadata", {}).get("type", "document"),
                    "distance": 1.0 - float(r.get("combined_score", 0.0)),
                }
                for r in results
            ]
            return context_chunks, context_metadata

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return [], []

    async def _web_search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Perform web search with priority for sensus-training.com."""
        from cache import get_cached_web_results, store_web_results

        # Check cache first
        cached_results = get_cached_web_results(query)
        if cached_results:
            logger.info(f"Using cached web results for query: {query[:50]}...")
            return [
                {"title": r.title, "content": r.content, "url": r.url, "score": r.score}
                for r in cached_results[:max_results]
            ]

        results = []

        # First, try sensus-training.com
        sensus_results = await self._search_sensus_training(query)
        results.extend(sensus_results)

        # If we don't have enough results, search broadly
        if len(results) < max_results:
            broad_results = await self._search_broad_web(query, max_results - len(results))
            results.extend(broad_results)

        # Cache the results
        if results:
            store_web_results(
                query,
                [{"title": r["title"], "url": r["url"], "content": r["content"], "score": r["score"]} for r in results],
            )

        return results[:max_results]

    async def web_search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Public wrapper for web search to expose in tools."""

        return await self._web_search(query, max_results)

    async def _search_sensus_training(self, query: str) -> List[Dict[str, Any]]:
        """Search sensus-training.com for relevant content using SearXNG."""
        try:
            searxng_url = os.getenv("SEARXNG_BASE_URL", "http://localhost:8888/")
            search_url = f"{searxng_url.rstrip('/')}/search"

            params = {
                "q": f"site:sensus-training.com {query}",
                "format": "json",
                "categories": "general",
                "engines": "duckduckgo,google",
                "safesearch": "0",
                "time_range": "",
                "lang": "en",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(search_url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for result in data.get("results", [])[:3]:  # Limit to 3
                        results.append(
                            {
                                "title": result.get("title", ""),
                                "url": result.get("url", ""),
                                "content": result.get("content", ""),
                                "score": 0.8,  # Default score
                            }
                        )

                    logger.info(f"SearXNG search returned {len(results)} results from sensus-training.com")
                    return results
                else:
                    logger.warning(f"SearXNG API error: {response.status_code}")
                    return []

        except Exception as e:
            logger.warning(f"Sensus-training.com search failed: {e}")
            return []

    async def _search_broad_web(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Perform broad web search using SearXNG."""
        try:
            searxng_url = os.getenv("SEARXNG_BASE_URL", "http://localhost:8888/")
            search_url = f"{searxng_url.rstrip('/')}/search"

            params = {
                "q": query,
                "format": "json",
                "categories": "general",
                "engines": "duckduckgo,google,startpage",
                "safesearch": "0",
                "time_range": "",
                "lang": "en",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(search_url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    for result in data.get("results", [])[:max_results]:
                        results.append(
                            {
                                "title": result.get("title", ""),
                                "url": result.get("url", ""),
                                "content": result.get("content", ""),
                                "score": 0.7,  # Default score
                            }
                        )

                    logger.info(f"SearXNG broad search returned {len(results)} results")
                    return results
                else:
                    logger.warning(f"SearXNG API error: {response.status_code}")
                    return []

        except Exception as e:
            logger.warning(f"Broad web search failed: {e}")
            return []

    def build_rag_prompt(self, query: str, context_chunks: List[str], complexity: str = "moderate") -> Dict[str, str]:
        """Build prompt with retrieved context, returning system and user prompts separately."""
        rni_definition = "The RNI is a Sensus Regional Network Interface - a comprehensive platform for utility AMI (Advanced Metering Infrastructure) systems."

        # Adjust prompt based on question complexity
        if complexity == "simple":
            response_guidelines = """RESPONSE GUIDELINES:
- Provide direct, concise answers without verbose analysis
- Answer immediately without "Thinking:" prefix
- Be clear and to the point
- Cite sources only if using external information"""
        elif complexity == "complex":
            response_guidelines = """RESPONSE GUIDELINES:
- Use step-by-step reasoning for complex questions
- Show analysis process briefly, then provide clear answer
- Break down technical concepts when needed
- Always cite sources used"""
        else:  # moderate
            response_guidelines = """RESPONSE GUIDELINES:
- Provide clear, accurate answers
- Use brief reasoning for technical questions
- Prioritize clarity over verbosity
- Cite sources when using external information"""

        system_prompt = f"""You are a helpful AI assistant specialized in RNI systems and Sensus products. {rni_definition}

{response_guidelines}"""

        if not context_chunks:
            user_prompt = f"Question: {query}\n\nProvide your response in the following format:\nThinking: [step-by-step reasoning]\nAnswer: [clear answer]\nSources: [list sources or 'None']"
            return {"system": system_prompt, "user": user_prompt}

        # Check if context contains web search results
        has_web_results = any("Web Result:" in chunk or "Source:" in chunk for chunk in context_chunks)

        if has_web_results:
            context_text = "\n\n".join(f"Web Source {i+1}: {chunk}" for i, chunk in enumerate(context_chunks))
            user_prompt = f"""Web Search Results:
{context_text}

Question: {query}

Provide your response in the following format:
Thinking: [step-by-step reasoning analyzing the sources]
Answer: [clear answer based on sources]
Sources: [list all sources cited]"""
        else:
            context_text = "\n\n".join(f"Context {i+1}: {chunk}" for i, chunk in enumerate(context_chunks))
            user_prompt = f"""Context from RNI 4.16 documentation:
{context_text}

Question: {query}

Provide your response in the following format:
Thinking: [step-by-step reasoning analyzing the context]
Answer: [clear answer based on documentation]
Sources: [list documentation sources]"""

        return {"system": system_prompt, "user": user_prompt}

    async def generate_response(
        self,
        prompt_dict: Dict[str, str],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        preferred_instance: Optional[str] = None,
    ) -> Union[str, Response]:
        """Generate response using Ollama chat API with system and user prompts and load balancing."""
        system_prompt = prompt_dict.get("system", "")
        user_prompt = prompt_dict.get("user", "")

        # Get healthy instances for fallback chain
        healthy_instances = await self.load_balancer.get_healthy_instances(RequestType.INFERENCE)

        # Try instances in order: preferred > load-balanced > fallback chain
        instances_to_try = []
        if preferred_instance:
            instances_to_try.append(preferred_instance)

        # Get load-balanced instance
        lb_instance = await self.load_balancer.get_next_instance(RequestType.INFERENCE)
        if lb_instance not in instances_to_try:
            instances_to_try.append(lb_instance)

        # Add remaining healthy instances
        for inst in healthy_instances:
            if inst not in instances_to_try:
                instances_to_try.append(inst)

        for attempt, selected_url in enumerate(instances_to_try):
            logger.debug(
                f"Attempting Ollama instance {selected_url} for model {model} (attempt {attempt + 1}/{len(instances_to_try)})"
            )
            track_instance_usage(selected_url)

            start_time = time.time()
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{selected_url}/api/chat",
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            "stream": stream,
                            "options": self._build_generation_options(model, temperature, max_tokens),
                        },
                        timeout=float(CHAT_GENERATION_TIMEOUT),
                    )
                    response_time = (time.time() - start_time) * 1000  # Convert to ms

                    if response.status_code == 200:
                        self.load_balancer.record_request(selected_url, response_time, success=True)
                        if stream:
                            return response
                        data = response.json()
                        message = data.get("message", {})
                        return message.get("content", "No response generated")

                    logger.warning(
                        "Generation failure status=%s on %s; trying next instance.",
                        response.status_code,
                        selected_url,
                    )
                    self.load_balancer.record_request(
                        selected_url, response_time, success=False, error=f"HTTP {response.status_code}"
                    )

            except (httpx.ReadTimeout, httpx.TimeoutException) as e:
                response_time = (time.time() - start_time) * 1000
                logger.warning("Timeout on %s; retrying with next instance", selected_url)
                self.load_balancer.record_request(selected_url, response_time, success=False, error=str(e))
            except Exception as exc:
                response_time = (time.time() - start_time) * 1000
                logger.error("Generation error on %s: %s", selected_url, exc)
                self.load_balancer.record_request(selected_url, response_time, success=False, error=str(exc))
                preferred_instance = None
                continue

        raise HTTPException(status_code=408, detail="Generation timeout")

    def _build_generation_options(self, model: str, temperature: float, max_tokens: int) -> Dict[str, Any]:
        options: Dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
        num_ctx = get_model_num_ctx(model)
        if num_ctx:
            options["num_ctx"] = num_ctx
        return options

    async def chat(self, request: RAGChatRequest) -> Union[RAGChatResponse, Response]:
        """Process RAG-enhanced chat request with hierarchical search."""
        logger.info(
            f"Processing chat request: query='{request.query[:50]}...', use_context={request.use_context}, stream={request.stream}"
        )
        context_chunks = []
        context_metadata = []
        web_sources = []
        cache_hit = False

        # Check cache first for non-streaming requests (streaming uses cache for context only)
        if request.use_context and not request.stream:
            cache = get_query_response_cache()
            cached_response = cache.get(request.query)
            if cached_response:
                logger.info(f"Cache HIT for query: {request.query[:50]}...")
                cache_hit = True
                return RAGChatResponse(
                    response=cached_response.get("response", ""),
                    context_used=cached_response.get("context_used", []),
                    context_metadata=cached_response.get("context_metadata", []),
                    web_sources=cached_response.get("web_sources", []),
                    model=cached_response.get("model", "cached"),
                    context_retrieved=cached_response.get("context_retrieved", False),
                    confidence=cached_response.get("confidence", 0.8),
                    fallback_used=False,
                )

        model_value = (request.model or "").lower()
        preferred_instance: Optional[str] = None
        question_type: Optional[QuestionType] = None
        complexity: str = "moderate"
        context_length: int = 4096

        if model_value in {"", "rni-mistral", "auto"}:
            (
                selected_model,
                preferred_instance,
                question_type,
                complexity,
                context_length,
            ) = await self._determine_model_and_instance(request.query)
        else:
            selected_model = request.model
            question_type = intelligent_router.classify_question(request.query)
            complexity = intelligent_router.assess_complexity(request.query)
            # Get context length from model profile or default
            model_profile = intelligent_router.model_profiles.get(selected_model)
            context_length = model_profile.context_length if model_profile else 4096

        # Calculate dynamic max chunks based on model context length
        # Estimate ~1000 tokens per chunk, reserve ~2000 tokens for system prompt and response
        estimated_tokens_per_chunk = 1000
        reserved_tokens = 2000
        max_chunks_based_on_context = max(1, (context_length - reserved_tokens) // estimated_tokens_per_chunk)
        effective_max_chunks = min(request.max_context_chunks, max_chunks_based_on_context)

        logger.info(
            f"Model {selected_model} has {context_length} token context, allowing max {effective_max_chunks} chunks"
        )

        if request.use_context:
            context_chunks, context_metadata = await self.retrieve_context(request.query, effective_max_chunks)
            logger.info(f"Retrieved {len(context_chunks)} chunks and {len(context_metadata)} metadata items")

            # Extract web sources for citations
            for chunk in context_chunks:
                if "Web Result:" in chunk and "Source:" in chunk:
                    lines = chunk.split("\n")
                    title = lines[0].replace("Web Result: ", "") if lines else "Web Source"
                    url = ""
                    for line in lines:
                        if line.startswith("Source: "):
                            url = line.replace("Source: ", "")
                            break
                    web_sources.append({"title": title, "url": url, "score": 0.8})

            logger.info(f"Retrieved {len(context_chunks)} context chunks ({len(web_sources)} from web) for query")

        prompt_dict = self.build_rag_prompt(request.query, context_chunks, complexity)

        logger.info(
            "Selected model %s for query: %s (question_type=%s, preferred_instance=%s, context_length=%d)",
            selected_model,
            request.query[:50] + ("..." if len(request.query) > 50 else ""),
            question_type.value if question_type else "unknown",
            preferred_instance,
            context_length,
        )

        track_model_usage(selected_model)
        if question_type:
            track_question_type(question_type.value)

        if request.stream:
            # For streaming, context was retrieved with default limits, but log what it should have been
            estimated_tokens_per_chunk = 1000
            reserved_tokens = 2000
            optimal_max_chunks = max(1, (context_length - reserved_tokens) // estimated_tokens_per_chunk)
            if len(context_chunks) > optimal_max_chunks:
                logger.warning(
                    f"Streaming request retrieved {len(context_chunks)} chunks but model {selected_model} "
                    f"({context_length} tokens) should only use {optimal_max_chunks} chunks"
                )
            # For streaming, return the response object
            return cast(
                Response,
                await self.generate_response(
                    prompt_dict,
                    selected_model,
                    request.temperature,
                    request.max_tokens,
                    True,
                    preferred_instance,
                ),
            )  # type: ignore
        else:
            # For non-streaming, return the response text
            response_text = cast(
                str,
                await self.generate_response(
                    prompt_dict,
                    selected_model,
                    request.temperature,
                    request.max_tokens,
                    False,
                    preferred_instance,
                ),
            )  # type: ignore

            # Calculate confidence score
            confidence = self._calculate_response_confidence(
                response_text, context_chunks, request.query, selected_model
            )
            fallback_used = False

            # Fallback strategy for low confidence
            if confidence < 0.4:
                logger.info(f"Low confidence ({confidence:.2f}) detected, attempting fallback strategy")
                fallback_used = True

                # Try different model from fallback options
                if fallback_options:
                    fallback_model = fallback_options[0].get("model", "mistral:7b")
                    fallback_url = fallback_options[0].get("url", preferred_instance)

                    try:
                        logger.info(f"Trying fallback model: {fallback_model} on {fallback_url}")
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            fallback_response = await client.post(
                                f"{fallback_url}/api/generate",
                                json={
                                    "model": fallback_model,
                                    "prompt": prompt,
                                    "stream": False,
                                    "options": {"temperature": request.temperature, "num_predict": request.max_tokens},
                                },
                            )

                            if fallback_response.status_code == 200:
                                fallback_data = fallback_response.json()
                                fallback_response_text = fallback_data.get("response", "").strip()

                                if fallback_response_text:
                                    # Recalculate confidence for fallback response
                                    fallback_confidence = self._calculate_response_confidence(
                                        fallback_response_text, context_chunks, request.query, fallback_model
                                    )

                                    # Use fallback if it's better
                                    if fallback_confidence > confidence:
                                        logger.info(
                                            f"Fallback improved confidence: {confidence:.2f} → {fallback_confidence:.2f}"
                                        )
                                        response_text = fallback_response_text
                                        selected_model = fallback_model
                                        confidence = fallback_confidence
                                    else:
                                        logger.info(
                                            f"Fallback did not improve confidence: {confidence:.2f} → {fallback_confidence:.2f}"
                                        )
                    except Exception as e:
                        logger.warning(f"Fallback attempt failed: {e}")

            rag_response = RAGChatResponse(
                response=response_text,
                context_used=context_chunks,
                context_metadata=context_metadata,
                web_sources=web_sources,
                model=selected_model,
                context_retrieved=len(context_chunks) > 0,
                confidence=confidence,
                fallback_used=fallback_used,
            )

            # Cache response for future queries (unless from cache already)
            if not cache_hit and request.use_context:
                try:
                    cache_rag_response(
                        request.query,
                        {
                            "response": response_text,
                            "context_used": context_chunks,
                            "context_metadata": context_metadata,
                            "web_sources": web_sources,
                            "model": selected_model,
                            "context_retrieved": len(context_chunks) > 0,
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache response: {e}")

            return rag_response

    async def batch_chat(self, request: BatchRAGChatRequest) -> BatchRAGChatResponse:
        """Process multiple queries concurrently."""
        import asyncio

        start_time = time.time()
        semaphore = asyncio.Semaphore(request.max_concurrent)

        async def process_single_query(query: str) -> RAGChatResponse:
            async with semaphore:
                single_request = RAGChatRequest(
                    query=query,
                    use_context=True,
                    max_context_chunks=request.max_context_chunks,
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stream=False,  # Batch doesn't support streaming
                )
                return await self.chat(single_request)

        # Process all queries concurrently with semaphore limiting
        tasks = [process_single_query(query) for query in request.queries]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed_responses = []
        successful_count = 0

        for i, result in enumerate(responses):
            if isinstance(result, Exception):
                logger.error(f"Batch query {i} failed: {result}")
                # Return error response
                processed_responses.append(
                    RAGChatResponse(
                        response=f"Error processing query: {str(result)}",
                        model="error",
                        confidence=0.0,
                        fallback_used=False,
                    )
                )
            else:
                processed_responses.append(result)
                if result.confidence > 0.0:  # Consider non-error responses as successful
                    successful_count += 1

        processing_time = time.time() - start_time

        return BatchRAGChatResponse(
            responses=processed_responses,
            total_queries=len(request.queries),
            successful_responses=successful_count,
            processing_time_seconds=processing_time,
        )


# Global service instance
rag_service = RAGChatService()


def add_rag_endpoints(app: FastAPI):
    """Add RAG chat endpoints to existing FastAPI app."""

    @app.post("/api/rag-chat")
    async def rag_chat(request: RAGChatRequest):
        """RAG-enhanced chat endpoint combining retrieval and generation."""
        if request.stream:
            # For streaming, return StreamingResponse
            response = cast(Response, await rag_service.chat(request))

            async def generate():
                async for line in response.aiter_lines():  # type: ignore
                    if line.strip():
                        yield f"data: {line}\n\n"

            return StreamingResponse(content=generate(), media_type="text/event-stream")
        else:
            # For non-streaming, return JSON
            return await rag_service.chat(request)

    @app.get("/api/rag-health")
    async def rag_health():
        """Health check for RAG service components."""
        try:
            # Test Ollama instances
            ollama_ok = False
            reranker_ok = False
            for url in rag_service.ollama_urls:
                try:
                    async with httpx.AsyncClient() as client:
                        ollama_resp = await client.get(f"{url}/api/tags", timeout=5.0)
                        if ollama_resp.status_code == 200:
                            ollama_ok = True
                            break
                except:
                    continue

            # Test reranker (self)
            reranker_ok = False
            try:
                async with httpx.AsyncClient() as client:
                    reranker_resp = await client.get("http://reranker:8008/health", timeout=5.0)
                    reranker_ok = reranker_resp.status_code == 200
            except:
                pass

            return {
                "status": "healthy" if (ollama_ok and reranker_ok) else "degraded",
                "ollama": "ok" if ollama_ok else "error",
                "reranker": "ok" if reranker_ok else "error",
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}
