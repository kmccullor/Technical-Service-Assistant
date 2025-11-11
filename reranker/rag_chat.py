"""
RAG-Enhanced Chat Endpoint

Combines vector retrieval with LLM generation for document-aware responses.
Follows Pydantic AI best practices from https://ai.pydantic.dev/
"""

import logging
import os
import random
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import httpx
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from httpx import Response
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from config import get_model_num_ctx, get_settings
from utils.redis_cache import track_instance_usage, track_model_usage, track_question_type

# Optional intelligent router import (kept local to avoid circular issues at startup)
from reranker.intelligent_router import ModelSelectionRequest, QuestionType, intelligent_router

# Setup basic logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)


class RAGChatRequest(BaseModel):
    """Request model for RAG chat."""

    query: str = Field(..., description="User query")
    use_context: bool = Field(True, description="Whether to use document context")
    max_context_chunks: int = Field(5, description="Maximum number of context chunks to retrieve")
    model: str = Field("rni-mistral", description="LLM model to use; set to 'rni-mistral' or 'auto' for smart routing")
    temperature: float = Field(0.2, description="Generation temperature")
    max_tokens: int = Field(500, description="Maximum tokens to generate")
    stream: bool = Field(False, description="Whether to stream the response")


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
        self.reranker_url = (
            reranker_url if reranker_url is not None else os.getenv("RERANKER_URL", "http://reranker:8008")
        )

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

    async def _determine_model_and_instance(self, query: str) -> Tuple[str, Optional[str], QuestionType]:
        """Use the intelligent router when available; fallback to local heuristics."""
        try:
            router_request = ModelSelectionRequest(query=query)
            router_response = await intelligent_router.route_request(router_request)
            logger.info(
                "Router selected %s on %s for %s questions",
                router_response.selected_model,
                router_response.selected_instance,
                router_response.question_type.value,
            )
            return (
                router_response.selected_model,
                router_response.instance_url,
                router_response.question_type,
            )
        except Exception as exc:
            logger.warning(f"Router selection failed; falling back to heuristics: {exc}")
            question_type = intelligent_router.classify_question(query)
            return self.select_model(query), None, question_type

    async def retrieve_context(self, query: str, max_chunks: int = 5) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Retrieve relevant context chunks using hierarchical search: RAG first, then web search."""
        logger.info(f"Starting context retrieval for query: {query[:50]}...")
        try:
            # Step 1: Try RAG knowledge base first
            query_embedding = await self._get_query_embedding(query)
            rag_chunks, rag_metadata = await self._vector_search(query_embedding, max_chunks)

            if rag_chunks:
                logger.info(f"Retrieved {len(rag_chunks)} RAG context chunks for query: {query[:50]}...")
                return rag_chunks, rag_metadata

            # Step 2: If no RAG results, try web search
            logger.info(f"No RAG results found, trying web search for query: {query[:50]}...")
            web_results = await self._web_search(query, max_chunks)

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
        """Generate embedding for the query using Ollama."""
        # Use the first available Ollama instance for embeddings
        selected_url = self.ollama_urls[0]
        logger.info(f"Getting embedding for query: {query[:50]}... from Ollama instance: {selected_url}")

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
                if response.status_code == 200:
                    data = response.json()
                    return data.get("embedding", [])
                else:
                    raise HTTPException(status_code=response.status_code, detail="Embedding generation failed")
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

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

    def build_rag_prompt(self, query: str, context_chunks: List[str]) -> Dict[str, str]:
        """Build prompt with retrieved context, returning system and user prompts separately."""
        rni_definition = "The RNI is a Sensus Regional Network Interface - a comprehensive platform for utility AMI (Advanced Metering Infrastructure) systems."

        system_prompt = f"""You are a helpful AI assistant specialized in RNI systems and Sensus products. {rni_definition}

REASONING PROCESS:
1. Analyze the question and identify key requirements
2. Consider available context and knowledge
3. Think step-by-step through the solution
4. Provide clear, actionable answers
5. Cite sources when using external information

Always structure your response with:
- Thinking: Show your step-by-step reasoning process
- Answer: Provide the clear answer
- Sources: List all sources used (if any)

Always show your reasoning process and explain your conclusions."""

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
        """Generate response using Ollama chat API with system and user prompts."""
        # Select an Ollama instance (router hint wins, otherwise random)
        selected_url = preferred_instance or random.choice(self.ollama_urls)
        logger.debug(
            f"Available instances: {self.ollama_urls}, Selected Ollama instance: {selected_url} for model {model}"
        )
        track_instance_usage(selected_url)

        system_prompt = prompt_dict.get("system", "")
        user_prompt = prompt_dict.get("user", "")

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
                    timeout=120.0,
                )
                if response.status_code == 200:
                    if stream:
                        # For streaming, return the response object for streaming
                        return response
                    else:
                        data = response.json()
                        message = data.get("message", {})
                        return message.get("content", "No response generated")
                else:
                    raise HTTPException(status_code=response.status_code, detail="Generation failed")
        except httpx.TimeoutException:
            raise HTTPException(status_code=408, detail="Generation timeout")
        except Exception as e:
            logger.error(f"Generation error: {e}")
            raise HTTPException(status_code=500, detail="Generation service error")

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

        if request.use_context:
            context_chunks, context_metadata = await self.retrieve_context(request.query, request.max_context_chunks)
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

        prompt_dict = self.build_rag_prompt(request.query, context_chunks)

        model_value = (request.model or "").lower()
        preferred_instance: Optional[str] = None
        question_type: Optional[QuestionType] = None

        if model_value in {"", "rni-mistral", "auto"}:
            selected_model, preferred_instance, question_type = await self._determine_model_and_instance(request.query)
        else:
            selected_model = request.model
            question_type = intelligent_router.classify_question(request.query)

        logger.info(
            "Selected model %s for query: %s (question_type=%s, preferred_instance=%s)",
            selected_model,
            request.query[:50] + ("..." if len(request.query) > 50 else ""),
            question_type.value if question_type else "unknown",
            preferred_instance,
        )

        track_model_usage(selected_model)
        if question_type:
            track_question_type(question_type.value)

        if request.stream:
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
            return RAGChatResponse(
                response=response_text,
                context_used=context_chunks,
                context_metadata=context_metadata,
                web_sources=web_sources,
                model=selected_model,
                context_retrieved=len(context_chunks) > 0,
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
