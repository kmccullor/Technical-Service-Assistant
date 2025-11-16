from __future__ import annotations

from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='question_decomposer',
    log_level='INFO',
    log_file=f'/app/logs/question_decomposer_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

"""Question decomposition and complexity classification for intelligent routing.

This module analyzes user queries to:
1. Classify complexity (SIMPLE, MODERATE, COMPLEX)
2. Decompose into logical sub-requests
3. Select appropriate models based on complexity
4. Generate deterministic cache keys for short-term memory

Used by chat endpoints to optimize response quality and performance.
"""

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field

from config import get_settings

class ComplexityLevel(str, Enum):
    """Query complexity classification for model routing."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"

@dataclass
class SubRequest:
    """Represents a sub-question extracted from decomposition."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_query: str = ""
    sub_query: str = ""
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    required_context: list[str] = field(default_factory=list)
    topic: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict:
        """Serialize to dictionary for caching."""
        return {
            "id": self.id,
            "original_query": self.original_query,
            "sub_query": self.sub_query,
            "complexity": self.complexity.value,
            "required_context": self.required_context,
            "topic": self.topic,
            "confidence": self.confidence,
        }

class DecompositionResult(BaseModel):
    """Result of question decomposition."""

    query_hash: str = Field(..., description="Deterministic hash of normalized query")
    original_query: str = Field(..., description="Original user query")
    complexity: ComplexityLevel = Field(..., description="Overall query complexity")
    sub_requests: list[SubRequest] = Field(default_factory=list, description="Decomposed sub-requests")
    total_sub_requests: int = Field(default=0, description="Number of sub-requests")
    needs_decomposition: bool = Field(default=False, description="Whether query needs decomposition")
    decomposition_confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in decomposition quality"
    )

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def to_dict(self) -> dict:
        """Serialize to dictionary for caching."""
        return {
            "query_hash": self.query_hash,
            "original_query": self.original_query,
            "complexity": self.complexity.value,
            "sub_requests": [sr.to_dict() for sr in self.sub_requests],
            "total_sub_requests": self.total_sub_requests,
            "needs_decomposition": self.needs_decomposition,
            "decomposition_confidence": self.decomposition_confidence,
        }

class QuestionDecomposer:
    """Decomposes questions into sub-requests and classifies complexity."""

    # Keyword patterns for complexity classification
    SIMPLE_KEYWORDS = {
        "what is",
        "how do",
        "explain",
        "tell me",
        "describe",
        "define",
        "list",
        "where is",
        "who is",
        "when is",
    }

    MODERATE_KEYWORDS = {
        "compare",
        "analyze",
        "summarize",
        "discuss",
        "contrast",
        "evaluate",
        "assess",
        "examine",
        "review",
    }

    COMPLEX_KEYWORDS = {
        "design",
        "implement",
        "troubleshoot",
        "optimize",
        "recommend",
        "suggest",
        "predict",
        "forecast",
        "architect",
        "evaluate tradeoffs",
    }

    # Decomposition trigger keywords (indicate multi-part questions)
    DECOMPOSITION_TRIGGERS = {
        " and ",
        " or ",
        "also ",
        "furthermore",
        "in addition",
        "moreover",
        "then ",
        "next ",
        "additionally",
        "?",  # Multiple question marks
        "both",
    }

    def __init__(self, settings=None):
        """Initialize decomposer with settings."""
        self.settings = settings or get_settings()
        self.min_tokens_for_decomposition = 15
        self.max_sub_requests = 5
        self.confidence_thresholds = {
            ComplexityLevel.SIMPLE: 0.7,
            ComplexityLevel.MODERATE: 0.6,
            ComplexityLevel.COMPLEX: 0.5,
        }

    def decompose_question(self, query: str, user_id: int = 0) -> DecompositionResult:
        """Decompose question into logical sub-requests.

        Args:
            query: User's original query
            user_id: User ID for cache key generation

        Returns:
            DecompositionResult with decomposition metadata and sub-requests
        """
        # Normalize query
        normalized = self._normalize_query(query)
        query_hash = self._generate_cache_key(query, user_id)

        # Classify complexity
        complexity = self.classify_complexity(query)

        # Decompose if beneficial
        sub_requests: list[SubRequest] = []
        needs_decomposition = False

        if len(normalized.split()) >= self.min_tokens_for_decomposition:
            sub_requests, needs_decomposition = self._extract_sub_requests(query, complexity)

        # Ensure sub-requests don't exceed limit
        if len(sub_requests) > self.max_sub_requests:
            # Merge least confident sub-requests
            sub_requests = self._merge_sub_requests(sub_requests, self.max_sub_requests)
            needs_decomposition = True

        # Calculate decomposition confidence
        decomposition_confidence = self._calculate_confidence(query, sub_requests, complexity)

        result = DecompositionResult(
            query_hash=query_hash,
            original_query=query,
            complexity=complexity,
            sub_requests=sub_requests,
            total_sub_requests=len(sub_requests),
            needs_decomposition=needs_decomposition,
            decomposition_confidence=decomposition_confidence,
        )

        logger.debug(
            f"Decomposed query: complexity={complexity}, sub_requests={len(sub_requests)}, confidence={decomposition_confidence:.2f}"
        )

        return result

    def classify_complexity(self, query: str) -> ComplexityLevel:
        """Classify query complexity level.

        Considers:
        - Token count
        - Keyword patterns
        - Structure (questions, conditions)
        - Context requirements

        Args:
            query: User query to classify

        Returns:
            ComplexityLevel (SIMPLE, MODERATE, or COMPLEX)
        """
        normalized = self._normalize_query(query).lower()

        # Token count analysis
        token_count = len(normalized.split())
        if token_count < 10:
            ComplexityLevel.SIMPLE
        elif token_count < 30:
            ComplexityLevel.MODERATE
        else:
            ComplexityLevel.COMPLEX

        # Keyword pattern matching (increases complexity)
        complexity_score = 0

        if any(kw in normalized for kw in self.SIMPLE_KEYWORDS):
            complexity_score += 1

        if any(kw in normalized for kw in self.MODERATE_KEYWORDS):
            complexity_score += 2

        if any(kw in normalized for kw in self.COMPLEX_KEYWORDS):
            complexity_score += 3

        # Count question marks (multiple = more complex)
        question_count = normalized.count("?")
        complexity_score += question_count

        # Count conditionals
        conditional_keywords = ["if ", "when ", "given ", "assuming ", "in case "]
        conditional_count = sum(1 for kw in conditional_keywords if kw in normalized)
        complexity_score += conditional_count

        # Determine final complexity
        if complexity_score >= 4:
            return ComplexityLevel.COMPLEX
        elif complexity_score >= 2:
            return ComplexityLevel.MODERATE
        else:
            return ComplexityLevel.SIMPLE

    def select_model_for_complexity(self, complexity: ComplexityLevel) -> str:
        """Select appropriate model size based on complexity.

        Args:
            complexity: ComplexityLevel classification

        Returns:
            Model name (small/medium/large)
        """
        model_map = {
            ComplexityLevel.SIMPLE: self.settings.reasoning_model,  # 3b (fastest)
            ComplexityLevel.MODERATE: self.settings.chat_model,  # 7b (balanced)
            ComplexityLevel.COMPLEX: self.settings.coding_model,  # 7b or larger
        }
        return model_map.get(complexity, self.settings.chat_model)

    def generate_cache_key(self, query: str, user_id: int) -> str:
        """Generate deterministic cache key for decomposed request.

        Same query → same key (across sessions)

        Args:
            query: User query
            user_id: User ID for scoping

        Returns:
            Cache key string
        """
        return self._generate_cache_key(query, user_id)

    # Private helper methods

    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent analysis.

        Args:
            query: Raw query text

        Returns:
            Normalized query
        """
        # Remove extra whitespace
        normalized = " ".join(query.split())
        # Remove trailing punctuation for processing
        normalized = normalized.rstrip("?!.")
        return normalized

    def _generate_cache_key(self, query: str, user_id: int) -> str:
        """Generate deterministic cache key.

        Args:
            query: User query
            user_id: User ID

        Returns:
            Cache key
        """
        # Normalize for consistent hashing
        normalized = self._normalize_query(query).lower()
        # Hash normalized query
        query_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"tsa:chat:decomposed:{query_hash}:{user_id}"

    def _extract_sub_requests(self, query: str, complexity: ComplexityLevel) -> tuple[list[SubRequest], bool]:
        """Extract sub-requests from query.

        Args:
            query: Original query
            complexity: Query complexity level

        Returns:
            Tuple of (sub_requests, needs_decomposition)
        """
        # Check if decomposition is beneficial
        if complexity == ComplexityLevel.SIMPLE:
            return [], False

        sub_requests: list[SubRequest] = []

        # Split on common decomposition triggers
        sentences = re.split(r"[?.!]", query)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) > 1:
            # Multi-sentence query - decompose
            for i, sentence in enumerate(sentences):
                sub_req = SubRequest(
                    original_query=query,
                    sub_query=sentence,
                    complexity=self.classify_complexity(sentence),
                    topic=self._extract_topic(sentence),
                    confidence=0.8,
                )
                sub_requests.append(sub_req)
            return sub_requests, True

        # Check for "and" or "or" connectives within single sentence
        if " and " in query.lower() or " or " in query.lower():
            # Split by connectives
            parts = re.split(r"\s+and\s+|\s+or\s+", query, flags=re.IGNORECASE)
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) > 1:
                for part in parts:
                    sub_req = SubRequest(
                        original_query=query,
                        sub_query=part,
                        complexity=self.classify_complexity(part),
                        topic=self._extract_topic(part),
                        confidence=0.7,
                    )
                    sub_requests.append(sub_req)
                return sub_requests, True

        # Single focused question - return as-is
        return [], False

    def _extract_topic(self, text: str) -> str:
        """Extract primary topic from text.

        Args:
            text: Text to analyze

        Returns:
            Topic string
        """
        # Simple heuristic: first noun or noun phrase
        words = text.split()
        return " ".join(words[:3]) if words else "general"

    def _merge_sub_requests(self, sub_requests: list[SubRequest], target_count: int) -> list[SubRequest]:
        """Merge least confident sub-requests to reach target count.

        Args:
            sub_requests: List of sub-requests
            target_count: Target number of sub-requests

        Returns:
            Merged list with target_count or fewer sub-requests
        """
        if len(sub_requests) <= target_count:
            return sub_requests

        # Sort by confidence (ascending) - least confident first
        sorted_reqs = sorted(sub_requests, key=lambda r: r.confidence)

        # Merge least confident pairs until we reach target
        merged = []
        i = 0
        while i < len(sorted_reqs) and len(merged) < target_count:
            if i + 1 < len(sorted_reqs) and len(sorted_reqs) - i > target_count - len(merged):
                # Merge two sub-requests
                merged_query = f"{sorted_reqs[i].sub_query} and {sorted_reqs[i+1].sub_query}"
                merged_req = SubRequest(
                    original_query=sorted_reqs[i].original_query,
                    sub_query=merged_query,
                    complexity=max(sorted_reqs[i].complexity, sorted_reqs[i + 1].complexity),
                    topic=f"{sorted_reqs[i].topic} + {sorted_reqs[i+1].topic}",
                    confidence=min(sorted_reqs[i].confidence, sorted_reqs[i + 1].confidence),
                )
                merged.append(merged_req)
                i += 2
            else:
                merged.append(sorted_reqs[i])
                i += 1

        return merged

    def _calculate_confidence(self, query: str, sub_requests: list[SubRequest], complexity: ComplexityLevel) -> float:
        """Calculate decomposition confidence score.

        Args:
            query: Original query
            sub_requests: Extracted sub-requests
            complexity: Classified complexity

        Returns:
            Confidence score 0.0-1.0
        """
        if not sub_requests:
            return 1.0  # Single-request = high confidence

        # Base confidence on sub-request confidences
        avg_confidence = sum(sr.confidence for sr in sub_requests) / len(sub_requests)

        # Adjust for query characteristics
        query_len = len(query.split())
        if query_len < 20:
            avg_confidence *= 0.9  # Lower confidence for short queries
        elif query_len > 100:
            avg_confidence *= 0.85  # Slightly lower for very long queries

        return min(1.0, max(0.5, avg_confidence))  # Clamp to [0.5, 1.0]

def classify_and_decompose(query: str, user_id: int = 0) -> DecompositionResult:
    """Convenience function to decompose a question.

    Args:
        query: User query
        user_id: User ID for caching

    Returns:
        DecompositionResult
    """
    decomposer = QuestionDecomposer()
    return decomposer.decompose_question(query, user_id)

def select_model_for_query(query: str) -> str:
    """Convenience function to select model for a query.

    Args:
        query: User query

    Returns:
        Model name
    """
    decomposer = QuestionDecomposer()
    complexity = decomposer.classify_complexity(query)
    return decomposer.select_model_for_complexity(complexity)
