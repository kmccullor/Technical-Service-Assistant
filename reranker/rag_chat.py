from utils.logging_config import setup_logging

# Setup basic logging
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

"""
RAG-Enhanced Chat Endpoint

Combines vector retrieval with LLM generation for document-aware responses.
Follows Pydantic AI best practices from https://ai.pydantic.dev/
"""

from typing import List
import logging

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


# Setup basic logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("reranked", [])
                else:
                    logger.warning(f"Context retrieval failed: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Context retrieval error: {e}")
            return []

    def build_rag_prompt(self, query: str, context_chunks: List[str]) -> str:
        """Build prompt with retrieved context."""
        if not context_chunks:
            return f"You are a helpful AI assistant. Answer the following question clearly and concisely.\n\nQuestion: {query}\n\nAnswer:"

        context_text = "\n\n".join(f"Context {i+1}: {chunk}" for i, chunk in enumerate(context_chunks))

        return f"""You are a helpful AI assistant. Use the provided context from RNI 4.16 documentation to answer the question. If the context doesn't contain relevant information, say so clearly.

Context:
{context_text}

Question: {query}

Answer based on the context above:"""

    async def generate_response(self, prompt: str, model: str, temperature: float, max_tokens: int) -> str:
        """Generate response using Ollama."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": temperature, "num_predict": max_tokens},
                    },
                    timeout=120.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "No response generated")
                else:
                    raise HTTPException(status_code=response.status_code, detail="Generation failed")
        except httpx.TimeoutException:
            raise HTTPException(status_code=408, detail="Generation timeout")
        except Exception as e:
            logger.error(f"Generation error: {e}")
            raise HTTPException(status_code=500, detail="Generation service error")

    async def chat(self, request: RAGChatRequest) -> RAGChatResponse:
        """Process RAG-enhanced chat request."""
        context_chunks = []

        if request.use_context:
            context_chunks = await self.retrieve_context(request.query, request.max_context_chunks)
            logger.info(f"Retrieved {len(context_chunks)} context chunks for query")

        prompt = self.build_rag_prompt(request.query, context_chunks)
        response_text = await self.generate_response(prompt, request.model, request.temperature, request.max_tokens)

        return RAGChatResponse(
            response=response_text,
            context_used=context_chunks,
            model=request.model,
            context_retrieved=len(context_chunks) > 0,
        )


# Global service instance
rag_service = RAGChatService()


def add_rag_endpoints(app: FastAPI):
    """Add RAG chat endpoints to existing FastAPI app."""

    @app.post("/api/rag-chat", response_model=RAGChatResponse)
    async def rag_chat(request: RAGChatRequest):
        """RAG-enhanced chat endpoint combining retrieval and generation."""
        return await rag_service.chat(request)

    @app.get("/api/rag-health")
    async def rag_health():
        """Health check for RAG service components."""
        try:
            # Test Ollama
            async with httpx.AsyncClient() as client:
                ollama_resp = await client.get(f"{rag_service.ollama_url}/api/tags", timeout=5.0)
                ollama_ok = ollama_resp.status_code == 200

                # Test reranker
                reranker_resp = await client.get("http://reranker:8008/health", timeout=5.0)
                reranker_ok = reranker_resp.status_code == 200

            return {
                "status": "healthy" if (ollama_ok and reranker_ok) else "degraded",
                "ollama": "ok" if ollama_ok else "error",
                "reranker": "ok" if reranker_ok else "error",
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}
