from datetime import datetime

from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="enhanced_retrieval",
    log_level="INFO",
    console_output=True,
)

#!/usr/bin/env python3
"""
Enhanced Retrieval Pipeline with Reranker Integration

This module implements a two-stage retrieval system:
1. Vector similarity search (cast wide net)
2. Reranking for precision enhancement

Expected improvements: 15-20% better Recall@1 performance
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import ollama
import psycopg2
import requests
from psycopg2.extras import RealDictCursor

from config import get_settings

settings = get_settings()

# Import the load balancer for optimal container utilization
try:
    from ollama_load_balancer import OllamaLoadBalancer

    LOAD_BALANCER_AVAILABLE = True
except ImportError:
    LOAD_BALANCER_AVAILABLE = False
    logger.warning("Load balancer not available, falling back to single container")


@dataclass
class RetrievalResult:
    """Container for retrieval results with quality metrics."""

    documents: List[Dict[str, Any]]
    scores: List[float]
    metrics: Dict[str, Any]
    query: str
    total_time: float


@dataclass
class QualityMetrics:
    """Quality assessment metrics for retrieval results."""

    vector_search_time: float
    rerank_time: float
    total_time: float
    candidate_diversity: float
    rerank_confidence: float
    semantic_coverage: float


class EnhancedRetrieval:
    """Enhanced retrieval pipeline with reranker integration and quality monitoring."""

    def __init__(
        self,
        reranker_url: str = "http://localhost:8008",
        ollama_url: Optional[str] = None,
        enable_reranking: bool = True,
    ):
        """
        Initialize enhanced retrieval system.

        Args:
            reranker_url: URL for reranker service
            ollama_url: URL for Ollama embedding service
            enable_reranking: Whether to use reranker (fallback to vector-only if False)
        """
        self.reranker_url = reranker_url
        # Fix Ollama URL for localhost access
        if ollama_url:
            self.ollama_url = ollama_url
        else:
            base_url = (
                settings.ollama_url.rsplit("/api", 1)[0] if "/api" in settings.ollama_url else settings.ollama_url
            )
            # Replace docker hostnames with localhost
            self.ollama_url = base_url.replace("ollama:", "localhost:").replace("ollama-server-1:", "localhost:")

        self.enable_reranking = enable_reranking
        self.embedding_model = settings.embedding_model

        # Initialize Ollama client and load balancer
        self.ollama_client = ollama.Client(host=self.ollama_url)

        # Initialize load balancer for optimal container utilization
        if LOAD_BALANCER_AVAILABLE:
            self.load_balancer = OllamaLoadBalancer(
                containers=["11434", "11435", "11436", "11437"], strategy="response_time"
            )
            logger.info("Load balancer initialized for parallel processing")
        else:
            self.load_balancer = None
            logger.info("Using single container mode")

        logger.info(f"Enhanced retrieval initialized - Reranking: {enable_reranking}")

    def _get_db_connection(self):
        """Get database connection."""
        # Use localhost when running outside containers
        db_host = "localhost" if settings.db_host == "pgvector" else settings.db_host

        return psycopg2.connect(
            host=db_host,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            port=settings.db_port,
        )

    def search(self, query: str, top_k: int = 10, candidate_pool: Optional[int] = None) -> RetrievalResult:
        """
        Enhanced search with optional reranking.

        Args:
            query: Search query
            top_k: Number of final results to return
            candidate_pool: Number of candidates for reranking (default: settings.retrieval_candidates)

        Returns:
            RetrievalResult with documents, scores, and quality metrics
        """
        start_time = time.time()
        candidate_pool = candidate_pool or settings.retrieval_candidates

        try:
            # Stage 1: Vector similarity search (cast wide net)
            candidates, vector_time = self._vector_search(query, limit=candidate_pool)

            if not candidates:
                return RetrievalResult(
                    documents=[],
                    scores=[],
                    metrics={"error": "No candidates found"},
                    query=query,
                    total_time=time.time() - start_time,
                )

            # Stage 2: Reranking (if enabled and available)
            if self.enable_reranking and len(candidates) > 1:
                final_results, rerank_time = self._rerank_candidates(query, candidates, top_k)
            else:
                # Fallback: Use vector results directly
                final_results = candidates[:top_k]
                rerank_time = 0
                logger.info("Using vector-only results (reranking disabled or insufficient candidates)")

            total_time = time.time() - start_time

            # Calculate quality metrics
            metrics = self._calculate_quality_metrics(
                query, candidates, final_results, vector_time, rerank_time, total_time
            )

            # Extract documents and scores
            documents = [result["document"] for result in final_results]
            scores = [result.get("score", 0.0) for result in final_results]

            return RetrievalResult(
                documents=documents, scores=scores, metrics=metrics, query=query, total_time=total_time
            )

        except Exception as e:
            logger.error(f"Enhanced search failed for query '{query}': {e}")
            return self._fallback_search(query, top_k, start_time)

    def _vector_search(self, query: str, limit: int) -> Tuple[List[Dict], float]:
        """Perform vector similarity search."""
        vector_start = time.time()

        try:
            # Use load balancer for optimal embedding generation if available
            if self.load_balancer:
                query_embedding = self.load_balancer.get_embedding(query, self.embedding_model.split(":")[0])
                if query_embedding and "embedding" in query_embedding:
                    query_embedding = query_embedding["embedding"]
                else:
                    raise Exception("Load balancer embedding failed")
            else:
                # Fallback to single container
                query_embedding = self.ollama_client.embeddings(model=self.embedding_model.split(":")[0], prompt=query)[
                    "embedding"
                ]

            # Get fresh database connection for each search
            conn = self._get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # First get the model ID
                    cursor.execute("SELECT id FROM models WHERE name = %s;", (self.embedding_model,))
                    model_result = cursor.fetchone()
                    if not model_result:
                        logger.error(f"Model {self.embedding_model} not found in database")
                        return [], 0

                    model_id = model_result["id"]

                    cursor.execute(
                        """
                        SELECT
                            c.text as content,
                            c.metadata,
                            d.name as document_name,
                            e.embedding <-> %s::vector as distance,
                            1 - (e.embedding <-> %s::vector) as similarity_score
                        from document_chunks c
                        JOIN embeddings e ON c.id = e.chunk_id
                        JOIN documents d ON c.document_id = d.id
                        WHERE e.model_id = %s
                        ORDER BY e.embedding <-> %s::vector
                        LIMIT %s
                        """,
                        (query_embedding, query_embedding, model_id, query_embedding, limit),
                    )

                    results = []
                    for row in cursor.fetchall():
                        results.append(
                            {
                                "document": {
                                    "content": row["content"],
                                    "metadata": row["metadata"],
                                    "document_name": row["document_name"],
                                    "distance": float(row["distance"]),
                                },
                                "vector_score": float(row["similarity_score"]),
                            }
                        )

                    vector_time = time.time() - vector_start
                    logger.debug(f"Vector search found {len(results)} candidates in {vector_time:.3f}s")

                    return results, vector_time
            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise

    def _rerank_candidates(self, query: str, candidates: List[Dict], top_k: int) -> Tuple[List[Dict], float]:
        """Apply reranking to candidate results."""
        rerank_start = time.time()

        try:
            # Prepare passages for reranking
            passages = [candidate["document"]["content"] for candidate in candidates]

            # Call reranker service
            rerank_request = {"query": query, "passages": passages, "top_k": min(top_k, len(passages))}

            response = requests.post(
                f"{self.reranker_url}/rerank", json=rerank_request, timeout=30  # 30 second timeout
            )
            response.raise_for_status()

            rerank_result = response.json()
            rerank_time = time.time() - rerank_start

            # Map reranked results back to original candidates
            reranked_passages = rerank_result["reranked"]
            rerank_scores = rerank_result["scores"]

            final_results = []
            for i, passage in enumerate(reranked_passages):
                # Find original candidate
                for candidate in candidates:
                    if candidate["document"]["content"] == passage:
                        result = candidate.copy()
                        result["rerank_score"] = rerank_scores[i]
                        result["score"] = rerank_scores[i]  # Use rerank score as primary
                        final_results.append(result)
                        break

            logger.debug(f"Reranking completed in {rerank_time:.3f}s, returned {len(final_results)} results")
            return final_results, rerank_time

        except Exception as e:
            logger.warning(f"Reranking failed, falling back to vector results: {e}")
            # Fallback to vector results
            return candidates[:top_k], 0

    def _calculate_quality_metrics(
        self,
        query: str,
        candidates: List[Dict],
        final_results: List[Dict],
        vector_time: float,
        rerank_time: float,
        total_time: float,
    ) -> Dict[str, Any]:
        """Calculate quality metrics for the retrieval results."""

        # Candidate diversity (based on document names)
        candidate_docs = set(c["document"]["document_name"] for c in candidates)
        candidate_diversity = len(candidate_docs) / len(candidates) if candidates else 0

        # Rerank confidence (average rerank score)
        rerank_scores = [r.get("rerank_score", 0) for r in final_results if "rerank_score" in r]
        rerank_confidence = sum(rerank_scores) / len(rerank_scores) if rerank_scores else 0

        # Semantic coverage (basic heuristic based on query length vs result content)
        query_terms = set(query.lower().split())
        coverage_scores = []
        for result in final_results:
            content_terms = set(result["document"]["content"].lower().split())
            overlap = len(query_terms & content_terms)
            coverage = overlap / len(query_terms) if query_terms else 0
            coverage_scores.append(coverage)

        semantic_coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0

        return {
            "vector_search_time": vector_time,
            "rerank_time": rerank_time,
            "total_time": total_time,
            "candidate_count": len(candidates),
            "final_count": len(final_results),
            "candidate_diversity": candidate_diversity,
            "rerank_confidence": rerank_confidence,
            "semantic_coverage": semantic_coverage,
            "used_reranking": rerank_time > 0,
        }

    def _fallback_search(self, query: str, top_k: int, start_time: float) -> RetrievalResult:
        """Fallback search when main pipeline fails."""
        try:
            logger.info("Attempting fallback vector search")
            candidates, vector_time = self._vector_search(query, limit=top_k)
            documents = [c["document"] for c in candidates]
            scores = [c["vector_score"] for c in candidates]

            return RetrievalResult(
                documents=documents,
                scores=scores,
                metrics={
                    "fallback_used": True,
                    "vector_search_time": vector_time,
                    "total_time": time.time() - start_time,
                },
                query=query,
                total_time=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"Fallback search also failed: {e}")
            return RetrievalResult(
                documents=[],
                scores=[],
                metrics={"error": str(e), "total_time": time.time() - start_time},
                query=query,
                total_time=time.time() - start_time,
            )

    def health_check(self) -> Dict[str, Any]:
        """Check health of all retrieval components."""
        health = {"enhanced_retrieval": "ok", "timestamp": time.time()}

        # Check database
        try:
            conn = self._get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                health["database"] = "ok"
            finally:
                conn.close()
        except Exception as e:
            health["database"] = f"error: {e}"
            health["enhanced_retrieval"] = "degraded"

        # Check Ollama
        try:
            self.ollama_client.list()
            health["ollama"] = "ok"
        except Exception as e:
            health["ollama"] = f"error: {e}"
            health["enhanced_retrieval"] = "degraded"

        # Check reranker (if enabled)
        if self.enable_reranking:
            try:
                response = requests.get(f"{self.reranker_url}/health", timeout=5)
                response.raise_for_status()
                health["reranker"] = "ok"
            except Exception as e:
                health["reranker"] = f"error: {e}"
                health["enhanced_retrieval"] = "degraded"
        else:
            health["reranker"] = "disabled"

        return health


def main():
    """Test the enhanced retrieval system."""
    import json

    # Initialize enhanced retrieval
    retrieval = EnhancedRetrieval(enable_reranking=True)

    # Test queries
    test_queries = [
        "What is the RNI 4.16 release date?",
        "How do you configure the security system?",
        "What are the installation requirements?",
    ]

    print("🔍 Testing Enhanced Retrieval Pipeline")
    print("=" * 50)

    for query in test_queries:
        print(f"\nQuery: {query}")
        result = retrieval.search(query, top_k=5)

        print(f"Results: {len(result.documents)}")
        print(f"Total time: {result.total_time:.3f}s")
        print(f"Metrics: {json.dumps(result.metrics, indent=2)}")

        if result.documents:
            print(f"Top result: {result.documents[0]['content'][:100]}...")

    # Health check
    print(f"\n🏥 Health Check:")
    health = retrieval.health_check()
    print(json.dumps(health, indent=2))


if __name__ == "__main__":
    main()
