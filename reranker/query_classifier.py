"""
Query Classification System for Hybrid Search

This module analyzes incoming queries and classifies them into different categories
to optimize search strategy selection and confidence thresholds.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Query classification categories."""

    TECHNICAL_DOCS = "technical_docs"  # System requirements, installation, configuration
    GENERAL_KNOWLEDGE = "general_knowledge"  # Wikipedia-style factual information
    CURRENT_EVENTS = "current_events"  # Recent news, latest developments
    CODE_EXAMPLES = "code_examples"  # Programming help, code snippets
    HOW_TO = "how_to"  # Procedural instructions
    COMPARISON = "comparison"  # "Best X vs Y", "Compare A and B"
    TROUBLESHOOTING = "troubleshooting"  # Error fixing, debugging help
    UNKNOWN = "unknown"  # Unclear or mixed intent


@dataclass
class QueryClassification:
    """Results of query classification analysis."""

    query_type: QueryType
    confidence: float
    suggested_confidence_threshold: float
    prefer_web_search: bool
    reasoning: str
    keywords_matched: List[str]


class QueryClassifier:
    """
    Intelligent query classification system that analyzes user queries
    to determine optimal search strategy.
    """

    def __init__(self):
        self.technical_keywords = {
            "installation",
            "setup",
            "configure",
            "requirements",
            "install",
            "system",
            "server",
            "database",
            "network",
            "security",
            "authentication",
            "rni",
            "sql",
            "windows",
            "active directory",
            "prerequisites",
            "configuration",
            "documentation",
            "manual",
            "guide",
        }

        self.current_events_keywords = {
            "latest",
            "recent",
            "new",
            "updated",
            "current",
            "2024",
            "2025",
            "released",
            "announced",
            "breaking",
            "trending",
            "now",
        }

        self.code_keywords = {
            "code",
            "programming",
            "function",
            "class",
            "method",
            "api",
            "python",
            "javascript",
            "java",
            "framework",
            "library",
            "example",
            "snippet",
            "syntax",
            "algorithm",
            "implementation",
        }

        self.how_to_patterns = [
            r"^how\s+to\s+",
            r"^how\s+do\s+i\s+",
            r"^how\s+can\s+i\s+",
            r"step\s+by\s+step",
            r"tutorial",
            r"walkthrough",
        ]

        self.comparison_patterns = [
            r"\b(best|top|compare|vs|versus|difference|better)\b",
            r"\b(pros\s+and\s+cons|advantages|disadvantages)\b",
            r"\b(which\s+is\s+better|what.*best)\b",
        ]

        self.troubleshooting_patterns = [
            r"\b(error|problem|issue|fix|solve|troubleshoot)\b",
            r"\b(not\s+working|broken|failed|failing)\b",
            r"\b(debug|diagnose|resolve)\b",
        ]

    def classify_query(self, query: str) -> QueryClassification:
        """
        Analyze a query and return classification with search strategy recommendations.

        Args:
            query: User's search query

        Returns:
            QueryClassification with type, confidence, and recommendations
        """
        query_lower = query.lower().strip()

        # Check for technical documentation queries
        tech_matches = self._find_keyword_matches(query_lower, self.technical_keywords)
        if tech_matches:
            return QueryClassification(
                query_type=QueryType.TECHNICAL_DOCS,
                confidence=0.8,
                suggested_confidence_threshold=0.2,  # Favor RAG for technical docs
                prefer_web_search=False,
                reasoning=f"Technical documentation query detected. Keywords: {', '.join(tech_matches)}",
                keywords_matched=tech_matches,
            )

        # Check for current events
        current_matches = self._find_keyword_matches(query_lower, self.current_events_keywords)
        if current_matches or self._contains_recent_date(query_lower):
            return QueryClassification(
                query_type=QueryType.CURRENT_EVENTS,
                confidence=0.9,
                suggested_confidence_threshold=0.8,  # Favor web search for current events
                prefer_web_search=True,
                reasoning=f"Current events query detected. Keywords: {', '.join(current_matches)}",
                keywords_matched=current_matches,
            )

        # Check for code examples
        code_matches = self._find_keyword_matches(query_lower, self.code_keywords)
        if code_matches:
            # Code queries can benefit from both RAG and web search
            return QueryClassification(
                query_type=QueryType.CODE_EXAMPLES,
                confidence=0.7,
                suggested_confidence_threshold=0.4,  # Moderate threshold for code
                prefer_web_search=False,
                reasoning=f"Code/programming query detected. Keywords: {', '.join(code_matches)}",
                keywords_matched=code_matches,
            )

        # Check for how-to queries
        if self._matches_patterns(query_lower, self.how_to_patterns):
            return QueryClassification(
                query_type=QueryType.HOW_TO,
                confidence=0.8,
                suggested_confidence_threshold=0.3,  # Slight preference for RAG
                prefer_web_search=False,
                reasoning="How-to/tutorial query detected",
                keywords_matched=[],
            )

        # Check for comparison queries
        if self._matches_patterns(query_lower, self.comparison_patterns):
            return QueryClassification(
                query_type=QueryType.COMPARISON,
                confidence=0.7,
                suggested_confidence_threshold=0.5,  # Balanced approach
                prefer_web_search=True,
                reasoning="Comparison query detected - benefits from diverse web sources",
                keywords_matched=[],
            )

        # Check for troubleshooting
        if self._matches_patterns(query_lower, self.troubleshooting_patterns):
            return QueryClassification(
                query_type=QueryType.TROUBLESHOOTING,
                confidence=0.6,
                suggested_confidence_threshold=0.3,  # Try RAG first for known issues
                prefer_web_search=False,
                reasoning="Troubleshooting query detected",
                keywords_matched=[],
            )

        # General knowledge (default case)
        return QueryClassification(
            query_type=QueryType.GENERAL_KNOWLEDGE,
            confidence=0.5,
            suggested_confidence_threshold=0.4,  # Moderate threshold
            prefer_web_search=True,
            reasoning="General knowledge query - web search recommended for broader coverage",
            keywords_matched=[],
        )

    def get_optimized_search_params(self, query: str, base_confidence_threshold: float = 0.3) -> Dict:
        """
        Get optimized search parameters based on query classification.

        Args:
            query: User's search query
            base_confidence_threshold: Default confidence threshold

        Returns:
            Dictionary with optimized search parameters
        """
        classification = self.classify_query(query)

        # Adjust confidence threshold based on classification
        if classification.query_type == QueryType.CURRENT_EVENTS:
            confidence_threshold = max(base_confidence_threshold, 0.7)  # Force web search
        elif classification.query_type == QueryType.TECHNICAL_DOCS:
            confidence_threshold = min(base_confidence_threshold, 0.2)  # Force RAG
        else:
            confidence_threshold = classification.suggested_confidence_threshold

        # Determine max context chunks based on query type
        if classification.query_type in [QueryType.TECHNICAL_DOCS, QueryType.HOW_TO]:
            max_context_chunks = 8  # More context for detailed queries
        elif classification.query_type == QueryType.CURRENT_EVENTS:
            max_context_chunks = 3  # Less context, faster web search
        else:
            max_context_chunks = 5  # Default

        return {
            "confidence_threshold": confidence_threshold,
            "enable_web_search": True,  # Always enable for hybrid approach
            "max_context_chunks": max_context_chunks,
            "classification": classification,
            "search_strategy": self._get_search_strategy(classification),
        }

    def _find_keyword_matches(self, query: str, keywords: set) -> List[str]:
        """Find which keywords from a set appear in the query."""
        words = set(re.findall(r"\b\w+\b", query))
        return list(words.intersection(keywords))

    def _matches_patterns(self, query: str, patterns: List[str]) -> bool:
        """Check if query matches any of the given regex patterns."""
        return any(re.search(pattern, query, re.IGNORECASE) for pattern in patterns)

    def _contains_recent_date(self, query: str) -> bool:
        """Check if query contains recent dates or time references."""
        current_year = datetime.now().year
        recent_years = [str(year) for year in range(current_year - 1, current_year + 2)]

        for year in recent_years:
            if year in query:
                return True

        recent_terms = ["today", "yesterday", "this week", "this month", "this year"]
        return any(term in query for term in recent_terms)

    def _get_search_strategy(self, classification: QueryClassification) -> str:
        """Get recommended search strategy description."""
        if classification.query_type == QueryType.CURRENT_EVENTS:
            return "web_first"
        elif classification.query_type == QueryType.TECHNICAL_DOCS:
            return "rag_first"
        elif classification.query_type == QueryType.COMPARISON:
            return "balanced_hybrid"
        else:
            return "adaptive_hybrid"


# Global classifier instance
query_classifier = QueryClassifier()


def classify_and_optimize_query(query: str, base_confidence_threshold: float = 0.3) -> Dict:
    """
    Convenience function to classify query and get optimized search parameters.

    Args:
        query: User's search query
        base_confidence_threshold: Default confidence threshold

    Returns:
        Dictionary with classification and optimized parameters
    """
    return query_classifier.get_optimized_search_params(query, base_confidence_threshold)
