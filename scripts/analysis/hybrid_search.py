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
        db_host = "localhost" if settings.db_host == "pgvector" else settings.db_host
        return psycopg2.connect(
            host=db_host,
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
                # Get model ID
                cursor.execute("SELECT id FROM models WHERE name = %s;", (self.embedding_model,))
                model_result = cursor.fetchone()
                if not model_result:
                    raise ValueError(f"Model {self.embedding_model} not found in database")

                model_id = model_result["id"]

                # Get all documents with embeddings
                cursor.execute(
                    """
                    SELECT
                        c.id,
                        c.text,
                        c.metadata,
                        d.name as document_name,
                        e.embedding
                    from document_chunks c
                    JOIN embeddings e ON c.id = e.chunk_id
                    JOIN documents d ON c.document_id = d.id
                    WHERE e.model_id = %s
                    ORDER BY c.id
                """,
                    (model_id,),
                )

                rows = cursor.fetchall()

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

        # Get BM25 scores
        bm25_scores = self.bm25.get_scores(query)

        # Get vector similarity scores
        vector_scores = self._get_vector_scores(query)

        if len(vector_scores) != len(bm25_scores):
            logger.warning(f"Mismatch in score lengths: vector={len(vector_scores)}, bm25={len(bm25_scores)}")
            min_len = min(len(vector_scores), len(bm25_scores))
            vector_scores = vector_scores[:min_len]
            bm25_scores = bm25_scores[:min_len]

        # Normalize scores
        vector_scores_norm = self._normalize_scores(vector_scores)
        bm25_scores_norm = self._normalize_scores(bm25_scores)

        # Combine scores
        combined_results = []
        for i, (vec_score, bm25_score) in enumerate(zip(vector_scores_norm, bm25_scores_norm)):
            if i >= len(self.document_metadata):
                break

            combined_score = alpha * vec_score + (1 - alpha) * bm25_score

            result = {
                "text": self.document_texts[i],
                "document_name": self.document_metadata[i]["document_name"],
                "metadata": self.document_metadata[i]["metadata"],
                "vector_score": vec_score,
                "bm25_score": bm25_score,
                "combined_score": combined_score,
                "chunk_id": self.document_metadata[i]["id"],
            }
            combined_results.append(result)

        # Sort by combined score and return top-k
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)

        search_time = time.time() - start_time
        logger.debug(f"Hybrid search completed in {search_time:.3f}s - Vector weight: {alpha}")

        return combined_results[:top_k]

    def _get_vector_scores(self, query: str) -> List[float]:
        """Get vector similarity scores for query."""
        try:
            import ollama

            # Initialize Ollama client
            base_url = (
                settings.ollama_url.rsplit("/api", 1)[0] if "/api" in settings.ollama_url else settings.ollama_url
            )
            ollama_url = base_url.replace("ollama:", "localhost:").replace("ollama-server-1:", "localhost:")
            ollama_client = ollama.Client(host=ollama_url)

            # Generate query embedding
            query_embedding = ollama_client.embeddings(model=self.embedding_model.split(":")[0], prompt=query)[
                "embedding"
            ]

            # Calculate cosine similarity with all document embeddings
            scores = []
            for metadata in self.document_metadata:
                doc_embedding = metadata["embedding"]
                if doc_embedding:
                    # Convert to lists if they're not already
                    if isinstance(query_embedding, str):
                        query_embedding = json.loads(query_embedding)
                    if isinstance(doc_embedding, str):
                        doc_embedding = json.loads(doc_embedding)

                    # Cosine similarity
                    dot_product = sum(a * b for a, b in zip(query_embedding, doc_embedding))
                    norm_a = math.sqrt(sum(a * a for a in query_embedding))
                    norm_b = math.sqrt(sum(b * b for b in doc_embedding))

                    similarity = dot_product / (norm_a * norm_b) if norm_a * norm_b > 0 else 0
                    scores.append(similarity)
                else:
                    scores.append(0.0)

            return scores

        except Exception as e:
            logger.error(f"Vector scoring failed: {e}")
            # Fallback to zero scores
            return [0.0] * len(self.document_metadata)

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Normalize scores to 0-1 range."""
        if not scores:
            return scores

        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [0.5] * len(scores)  # All scores are the same

        return [(score - min_score) / (max_score - min_score) for score in scores]

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
    print("🔍 Testing Hybrid Search Implementation")
    print("=" * 50)

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
        print(f"\nQuery: {query}")
        print("-" * 30)

        # Compare all methods
        comparison = hybrid_search.compare_methods(query, top_k=3)

        print("🎯 Vector Only (Top 3):")
        for i, result in enumerate(comparison["vector_only"][:3], 1):
            print(f"  {i}. {result['text'][:60]}... (score: {result['vector_score']:.3f})")

        print("\n🔤 BM25 Only (Top 3):")
        for i, result in enumerate(comparison["bm25_only"][:3], 1):
            print(f"  {i}. {result['text'][:60]}... (score: {result['bm25_score']:.3f})")

        print("\n🚀 Hybrid (Top 3):")
        for i, result in enumerate(comparison["hybrid"][:3], 1):
            print(f"  {i}. {result['text'][:60]}... (combined: {result['combined_score']:.3f})")

    print(f"\n💾 Hybrid search system ready for integration!")


if __name__ == "__main__":
    main()
