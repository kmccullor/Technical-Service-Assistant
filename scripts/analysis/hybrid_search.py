from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="hybrid_search",
    log_level="INFO",
    console_output=True,
)

#!/usr/bin/env python3
"""
Hybrid Search Implementation

Combines vector similarity search with BM25 keyword matching for improved
retrieval accuracy, especially for technical terms and exact matches.
"""

import json
import math
import re
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from config import get_settings

settings = get_settings()


class BM25Scorer:
    """BM25 scoring implementation for keyword matching."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 scorer.

        Args:
            k1: Controls non-linear term frequency normalization (default: 1.5)
            b: Controls how much effect document length has on relevance (default: 0.75)
        """
        self.k1 = k1
        self.b = b
        self.corpus = []
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.avgdl = 0

    def fit(self, corpus: List[str]) -> None:
        """
        Fit BM25 on a corpus of documents.

        Args:
            corpus: List of document texts
        """
        self.corpus = corpus
        self.doc_len = [len(self._tokenize(doc)) for doc in corpus]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0

        # Calculate document frequencies
        df = defaultdict(int)
        for doc in corpus:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                df[token] += 1

        # Calculate IDF values
        self.idf = {}
        for token, freq in df.items():
            self.idf[token] = math.log((len(corpus) - freq + 0.5) / (freq + 0.5))

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization - split on whitespace and punctuation."""
        # Convert to lowercase and split on whitespace/punctuation
        tokens = re.findall(r"\b\w+\b", text.lower())
        return tokens

    def get_scores(self, query: str) -> List[float]:
        """
        Get BM25 scores for query against all documents.

        Args:
            query: Query string

        Returns:
            List of BM25 scores for each document
        """
        query_tokens = self._tokenize(query)
        scores = []

        for i, doc in enumerate(self.corpus):
            doc_tokens = self._tokenize(doc)
            token_counts = Counter(doc_tokens)
            score = 0

            for token in query_tokens:
                if token in token_counts and token in self.idf:
                    tf = token_counts[token]
                    idf = self.idf[token]

                    # BM25 formula
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                    score += idf * (numerator / denominator)

            scores.append(score)

        return scores


class HybridSearch:
    """Hybrid search combining vector similarity and BM25 keyword matching."""

    def __init__(self, embedding_model: Optional[str] = None, alpha: float = 0.7):
        """
        Initialize hybrid search.

        Args:
            embedding_model: Name of embedding model to use
            alpha: Weight for vector similarity (1-alpha for BM25). Default 0.7 favors vector similarity.
        """
        self.embedding_model = embedding_model or settings.embedding_model
        self.alpha = alpha  # Vector weight
        self.bm25 = BM25Scorer()
        self.corpus_indexed = False
        self.document_texts = []
        self.document_metadata = []

        logger.info(f"Hybrid search initialized - Vector weight: {alpha}, BM25 weight: {1-alpha}")

    def _get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            host=settings.db_host,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            port=settings.db_port,
        )

    def build_index(self) -> None:
        """Build the hybrid search index from database."""
        logger.info("Building hybrid search index...")
        start_time = time.time()

        conn = self._get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get all documents with embeddings from document_chunks table
                # (embeddings are stored directly in the document_chunks table, not in a separate table)
                cursor.execute(
                    """
                    SELECT
                        c.id,
                        c.content as text,
                        c.metadata,
                        d.file_name as document_name,
                        c.embedding
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE c.embedding IS NOT NULL
                    ORDER BY c.id
                """
                )

                rows = cursor.fetchall()

                if not rows:
                    logger.warning("No documents with embeddings found in database")
                    self.corpus_indexed = False
                    return

                # Extract texts and metadata
                self.document_texts = [row["text"] for row in rows]
                self.document_metadata = [
                    {
                        "id": row["id"],
                        "document_name": row["document_name"],
                        "metadata": row["metadata"],
                        "embedding": row["embedding"],
                    }
                    for row in rows
                ]

                # Build BM25 index
                self.bm25.fit(self.document_texts)
                self.corpus_indexed = True

                build_time = time.time() - start_time
                logger.info(f"Index built successfully: {len(self.document_texts)} documents in {build_time:.2f}s")

        finally:
            conn.close()

    def search(self, query: str, top_k: int = 10, vector_weight: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector similarity and BM25.

        Args:
            query: Search query
            top_k: Number of results to return
            vector_weight: Override default alpha weight for this query

        Returns:
            List of search results with combined scores
        """
        if not self.corpus_indexed:
            self.build_index()

        alpha = vector_weight if vector_weight is not None else self.alpha
        start_time = time.time()

        # Get top results from vector and BM25 search
        vector_results = self._get_top_vector_results(query, top_k * 2)
        bm25_results = self._get_top_bm25_results(query, top_k * 2)

        # Combine candidates
        candidate_map = {}
        for result in vector_results + bm25_results:
            chunk_id = result["chunk_id"]
            if chunk_id not in candidate_map:
                candidate_map[chunk_id] = result
            else:
                # Merge scores if both have them
                existing = candidate_map[chunk_id]
                if "vector_score" in result and "vector_score" not in existing:
                    existing["vector_score"] = result["vector_score"]
                if "bm25_score" in result and "bm25_score" not in existing:
                    existing["bm25_score"] = result["bm25_score"]

        # Calculate combined scores
        combined_results = []
        for chunk_id, result in candidate_map.items():
            vec_score = result.get("vector_score", 0.0)
            bm25_score = result.get("bm25_score", 0.0)

            # Normalize scores within the candidate set
            all_vec_scores = [r.get("vector_score", 0.0) for r in candidate_map.values()]
            all_bm25_scores = [r.get("bm25_score", 0.0) for r in candidate_map.values()]

            vec_score_norm = self._normalize_score(vec_score, all_vec_scores)
            bm25_score_norm = self._normalize_score(bm25_score, all_bm25_scores)

            combined_score = alpha * vec_score_norm + (1 - alpha) * bm25_score_norm

            result["vector_score"] = vec_score_norm
            result["bm25_score"] = bm25_score_norm
            result["combined_score"] = combined_score
            combined_results.append(result)

        # Sort by combined score
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)

        search_time = time.time() - start_time
        logger.debug(f"Hybrid search completed in {search_time:.3f}s - Vector weight: {alpha}")

        return combined_results[:top_k]

    def _get_top_vector_results(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Get top vector similarity results from PostgreSQL."""
        try:
            import ollama

            # Try primary Ollama instance first
            try:
                ollama_client = ollama.Client(host="http://ollama-server-1:11434")
                logger.debug("Connected to ollama-server-1 (Docker container)")
            except Exception:
                # Fallback to config URL
                base_url = settings.ollama_url
                if "/api" in base_url:
                    base_url = base_url.rsplit("/api", 1)[0]
                ollama_client = ollama.Client(host=base_url)
                logger.debug(f"Connected to {base_url} (config fallback)")

            # Generate query embedding
            query_embedding = ollama_client.embeddings(model=self.embedding_model, prompt=query)["embedding"]

            conn = psycopg2.connect(
                host=settings.db_host,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                port=settings.db_port,
            )
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Convert embedding to PostgreSQL vector format
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

            cursor.execute(
                """
                SELECT
                    dc.id,
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
                (embedding_str, embedding_str, top_k),
            )

            results = cursor.fetchall()
            cursor.close()
            conn.close()

            # Convert to result format
            vector_results = []
            for row in results:
                vector_results.append({
                    "chunk_id": row["id"],
                    "text": row["content"],
                    "document_name": row["file_name"],
                    "metadata": {"type": row["document_type"]},
                    "vector_score": 1.0 - row["distance"],  # Convert distance to similarity
                })

            logger.debug(f"Got {len(vector_results)} vector results")
            return vector_results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def _get_top_bm25_results(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Get top BM25 results."""
        try:
            bm25_scores = self.bm25.get_scores(query)

            # Get top scoring documents
            scored_docs = [(i, score) for i, score in enumerate(bm25_scores)]
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            bm25_results = []
            for chunk_id, score in scored_docs[:top_k]:
                if chunk_id < len(self.document_metadata):
                    bm25_results.append({
                        "chunk_id": chunk_id,
                        "text": self.document_texts[chunk_id],
                        "document_name": self.document_metadata[chunk_id]["document_name"],
                        "metadata": self.document_metadata[chunk_id]["metadata"],
                        "bm25_score": score,
                    })

            logger.debug(f"Got {len(bm25_results)} BM25 results")
            return bm25_results

        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize scores to 0-1 range."""
        if not scores:
            return scores

        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [0.5] * len(scores)  # All scores are the same

        return [(score - min_score) / (max_score - min_score) for score in scores]

    def _normalize_score(self, score: float, all_scores: List[float]) -> float:
        """Normalize a single score within a list of scores."""
        if not all_scores:
            return 0.5

        min_score = min(all_scores)
        max_score = max(all_scores)

        if max_score == min_score:
            return 0.5

        return (score - min_score) / (max_score - min_score)

    def compare_methods(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Compare vector-only, BM25-only, and hybrid search results.

        Args:
            query: Search query
            top_k: Number of results to compare

        Returns:
            Comparison results
        """
        if not self.corpus_indexed:
            self.build_index()

        # Vector-only results (alpha = 1.0)
        vector_results = self.search(query, top_k, vector_weight=1.0)

        # BM25-only results (alpha = 0.0)
        bm25_results = self.search(query, top_k, vector_weight=0.0)

        # Hybrid results (default alpha)
        hybrid_results = self.search(query, top_k)

        return {
            "query": query,
            "vector_only": vector_results,
            "bm25_only": bm25_results,
            "hybrid": hybrid_results,
            "alpha": self.alpha,
        }


def main():
    """Test hybrid search implementation."""
    logger.info("🔍 Testing Hybrid Search Implementation")
    logger.info("=" * 50)

    # Initialize hybrid search
    hybrid_search = HybridSearch(alpha=0.7)  # 70% vector, 30% BM25

    # Test queries
    test_queries = [
        "RNI 4.16 release date",
        "security configuration requirements",
        "Active Directory integration setup",
        "installation prerequisites",
        "reporting features available",
    ]

    for query in test_queries:
        logger.info(f"\nQuery: {query}")
        logger.info("-" * 30)

        # Compare all methods
        comparison = hybrid_search.compare_methods(query, top_k=3)

        logger.info("🎯 Vector Only (Top 3):")
        for i, result in enumerate(comparison["vector_only"][:3], 1):
            logger.info(f"  {i}. {result['text'][:60]}... (score: {result['vector_score']:.3f})")

        logger.info("\n🔤 BM25 Only (Top 3):")
        for i, result in enumerate(comparison["bm25_only"][:3], 1):
            logger.info(f"  {i}. {result['text'][:60]}... (score: {result['bm25_score']:.3f})")

        logger.info("\n🚀 Hybrid (Top 3):")
        for i, result in enumerate(comparison["hybrid"][:3], 1):
            logger.info(f"  {i}. {result['text'][:60]}... (combined: {result['combined_score']:.3f})")

    logger.info(f"\n💾 Hybrid search system ready for integration!")


if __name__ == "__main__":
    main()
