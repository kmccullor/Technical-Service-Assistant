"""
Query Optimization Module

Implements query preprocessing techniques to improve accuracy and reduce latency:
- Stop word removal
- Query normalization
- Frequency caching
- Query expansion hints

Expected improvements: 3-5% latency reduction, 5% accuracy improvement
"""

import logging
import re
from functools import lru_cache
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Common stop words for technical queries (broader than traditional NLP)
# We keep technical terms even if they appear frequently
TECHNICAL_STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "can",
    "must",
    "shall",
    "what",
    "which",
    "who",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "neither",
    "either",
    "any",
    "some",
    "no",
    "not",
    "more",
    "most",
    "very",
    "just",
    "only",
    "than",
    "as",
    "if",
    "while",
    "until",
    "because",
    "that",
    "this",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
}

# Technical terms to preserve (never remove)
PRESERVE_TERMS = {
    "rni",
    "ollama",
    "llm",
    "api",
    "rest",
    "json",
    "sql",
    "db",
    "cpu",
    "gpu",
    "error",
    "warning",
    "debug",
    "info",
    "log",
    "cache",
    "memory",
    "network",
    "configuration",
    "setup",
    "deploy",
    "production",
    "development",
    "test",
    "performance",
    "latency",
    "throughput",
    "reliability",
    "availability",
    "security",
    "encryption",
    "authentication",
    "authorization",
    "permission",
    "model",
    "training",
    "inference",
    "vector",
    "embedding",
    "search",
    "retrieval",
    "generation",
    "ranking",
    "scoring",
    "confidence",
}


def normalize_query(query: str) -> str:
    """
    Normalize query text for consistent processing.

    - Convert to lowercase
    - Remove extra whitespace
    - Remove punctuation except hyphens in compound words
    """
    # Convert to lowercase
    normalized = query.lower().strip()

    # Remove common punctuation that doesn't affect meaning
    normalized = re.sub(r"[?,;:!\"()]", "", normalized)

    # Preserve hyphens in compound words but remove trailing/leading
    normalized = re.sub(r"\s+-+\s*", " ", normalized)
    normalized = re.sub(r"-+", "-", normalized)

    # Replace multiple spaces with single
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized


def remove_stop_words(query: str) -> str:
    """
    Remove common stop words while preserving technical terms.

    Returns query with stop words removed but structure preserved.
    """
    words = query.split()
    filtered = []

    for word in words:
        # Keep if it's a technical term or not a stop word
        if word in PRESERVE_TERMS or word not in TECHNICAL_STOP_WORDS:
            filtered.append(word)

    return " ".join(filtered) if filtered else query


def extract_keywords(query: str) -> List[str]:
    """
    Extract important keywords from query.

    Returns list of significant terms for retrieval ranking.
    """
    normalized = normalize_query(query)
    words = normalized.split()

    keywords = []
    for word in words:
        # Include non-stop words and technical terms
        if word not in TECHNICAL_STOP_WORDS or word in PRESERVE_TERMS:
            # Remove hyphens for searching
            word_clean = word.replace("-", "")
            if len(word_clean) > 2:  # Skip very short words
                keywords.append(word_clean)

    return keywords


def extract_entities(query: str) -> List[str]:
    """
    Extract potential entities from query (dates, numbers, etc.).

    Returns list of extracted entities for enhanced search.
    """
    entities = []

    # Extract dates (simple patterns)
    date_patterns = [
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",  # MM/DD/YYYY
        r"\b\d{4}-\d{2}-\d{2}\b",  # YYYY-MM-DD
        r"\b\d{1,2}-\d{1,2}-\d{2,4}\b",  # MM-DD-YYYY
    ]
    for pattern in date_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        entities.extend(matches)

    # Extract version numbers
    version_pattern = r"\bv?\d+\.\d+(?:\.\d+)*\b"
    versions = re.findall(version_pattern, query, re.IGNORECASE)
    entities.extend(versions)

    # Extract IP addresses
    ip_pattern = r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
    ips = re.findall(ip_pattern, query)
    entities.extend(ips)

    # Extract error codes (common patterns)
    error_pattern = r"\b(?:error|err|code)\s*\d+\b"
    errors = re.findall(error_pattern, query, re.IGNORECASE)
    entities.extend(errors)

    return list(set(entities))  # deduplicate


def suggest_expansions(query: str) -> List[str]:
    """
    Suggest query expansions for better retrieval.

    Uses heuristics to identify related search terms.
    """
    normalized = normalize_query(query)
    expansions = []

    # If query mentions error/problem, also search for solution/fix
    if any(word in normalized for word in ["error", "problem", "issue", "bug"]):
        expansions.append("solution")
        expansions.append("fix")

    # If query mentions model/training, also search for inference/deployment
    if any(word in normalized for word in ["train", "model", "learning"]):
        expansions.append("inference")
        expansions.append("deployment")

    # If query mentions performance, also search for optimization
    if any(word in normalized for word in ["slow", "performance", "speed"]):
        expansions.append("optimization")
        expansions.append("tuning")

    # If query mentions configuration/setup, also search for guide/tutorial
    if any(word in normalized for word in ["configure", "setup", "install"]):
        expansions.append("guide")
        expansions.append("tutorial")

    # Acronym expansions
    ACRONYM_EXPANSIONS = {
        "rni": "regional network interface",
        "ami": "advanced metering infrastructure",
        "api": "application programming interface",
        "llm": "large language model",
        "rag": "retrieval augmented generation",
        "scada": "supervisory control and data acquisition",
        "mdm": "meter data management",
        "ems": "energy management system",
        "esm": "energy services module",
        "da": "distribution automation",
        "der": "distributed energy resources",
        "han": "home area network",
        "fdir": "fault detection isolation and restoration",
        "dr": "demand response",
        "vvo": "volt var optimization",
        "soe": "sequence of events",
        "tmr": "trip matrix recorder",
        "hmi": "human machine interface",
        "plc": "programmable logic controller",
        "pki": "public key infrastructure",
        "rbac": "role based access control",
        "jwt": "json web token",
        "oauth": "open authorization",
        "ssl": "secure sockets layer",
        "tls": "transport layer security",
        "dhcp": "dynamic host configuration protocol",
        "dns": "domain name system",
        "nat": "network address translation",
        "vpn": "virtual private network",
        "lan": "local area network",
        "wan": "wide area network",
        "tcp": "transmission control protocol",
        "udp": "user datagram protocol",
        "http": "hypertext transfer protocol",
        "https": "hypertext transfer protocol secure",
        "ip": "internet protocol",
        "sql": "structured query language",
        "nosql": "not only sql",
        "rdbms": "relational database management system",
        "orm": "object relational mapping",
        "etl": "extract transform load",
        "olap": "online analytical processing",
        "oltp": "online transaction processing",
        "crud": "create read update delete",
        "rest": "representational state transfer",
        "json": "javascript object notation",
        "xml": "extensible markup language",
        "yaml": "yaml ain't markup language",
        "toml": "tom's obvious minimal language",
        "html": "hypertext markup language",
        "css": "cascading style sheets",
        "js": "javascript",
        "ajax": "asynchronous javascript and xml",
        "dom": "document object model",
        "spa": "single page application",
        "pwa": "progressive web application",
        "ocr": "optical character recognition",
        "nlp": "natural language processing",
        "ml": "machine learning",
        "dl": "deep learning",
        "ai": "artificial intelligence",
        "rl": "reinforcement learning",
        "cnn": "convolutional neural network",
        "rnn": "recurrent neural network",
        "lstm": "long short term memory",
        "bert": "bidirectional encoder representations from transformers",
        "gpt": "generative pre trained transformer",
        "gan": "generative adversarial network",
        "ci": "continuous integration",
        "cd": "continuous deployment",
        "tdd": "test driven development",
        "bdd": "behavior driven development",
        "devops": "development operations",
        "iac": "infrastructure as code",
        "iacs": "infrastructure as code",
        "cap": "consistency availability partition tolerance",
        "acid": "atomicity consistency isolation durability",
        "base": "basically available soft state eventually consistent",
        "docker": "container platform",
        "kubernetes": "container orchestration system",
        "aws": "amazon web services",
        "gcp": "google cloud platform",
        "azure": "microsoft azure",
        "iaas": "infrastructure as a service",
        "paas": "platform as a service",
        "saas": "software as a service",
        "pdf": "portable document format",
        "csv": "comma separated values",
        "ldap": "lightweight directory access protocol",
        "hsm": "hardware security module",
        "gis": "geographic information system",
        "iec": "international electrotechnical commission",
        "iot": "internet of things",
        "mvc": "model view controller",
    }

    # Expand acronyms in query
    for acronym, expansion in ACRONYM_EXPANSIONS.items():
        if acronym in normalized:
            expansions.append(expansion)

    # Domain-specific expansions for RNI-related queries
    if "rni" in normalized or "regional network" in normalized:
        expansions.extend(
            [
                "regional network interface",
                "rni configuration",
                "rni installation",
                "rni security",
                "rni deployment",
            ]
        )

    # Deduplicate and keep order
    seen = set()
    deduped = []
    for term in expansions:
        if term not in seen:
            deduped.append(term)
            seen.add(term)

    return deduped

    return expansions


class QueryOptimizer:
    """
    Comprehensive query optimization for improved retrieval and reduced latency.

    - Normalizes queries for consistency
    - Removes stop words intelligently
    - Extracts keywords for ranking
    - Suggests related search terms
    """

    def __init__(self):
        """Initialize query optimizer."""
        self.cache_hits = 0
        self.cache_misses = 0

    @lru_cache(maxsize=1000)
    def optimize(self, query: str) -> Dict[str, Any]:
        """
        Fully optimize a query.

        Returns dict with:
        - original: Original query
        - normalized: Normalized query
        - keywords: Extracted keywords
        - reduced: Query with stop words removed
        - expansions: Suggested expansion terms
        """
        return {
            "original": query,
            "normalized": normalize_query(query),
            "keywords": extract_keywords(query),
            "reduced": remove_stop_words(normalize_query(query)),
            "expansions": suggest_expansions(query),
            "entities": extract_entities(query),
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get optimization cache statistics."""
        cache_info = self.optimize.cache_info()
        return {
            "cache_hits": cache_info.hits,
            "cache_misses": cache_info.misses,
            "cache_size": cache_info.currsize,
            "cache_max": cache_info.maxsize,
            "hit_rate": (
                cache_info.hits / (cache_info.hits + cache_info.misses)
                if (cache_info.hits + cache_info.misses) > 0
                else 0
            ),
        }

    def clear_cache(self) -> None:
        """Clear the optimization cache."""
        self.optimize.cache_clear()
        logger.info("Query optimization cache cleared")


# Global optimizer instance
_optimizer: QueryOptimizer = QueryOptimizer()


def get_query_optimizer() -> QueryOptimizer:
    """Get or create global query optimizer."""
    return _optimizer


def optimize_query(query: str) -> Dict[str, Any]:
    """Optimize a query using the global optimizer."""
    optimizer = get_query_optimizer()
    return optimizer.optimize(query)


def get_optimization_stats() -> Dict[str, Any]:
    """Get query optimization cache statistics."""
    optimizer = get_query_optimizer()
    return optimizer.get_cache_stats()
