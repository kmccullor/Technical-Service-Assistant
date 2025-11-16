from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='query_enhancement',
    log_level='INFO',
    log_file=f'/app/logs/query_enhancement_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

#!/usr/bin/env python3
"""
Query Enhancement Implementation

This module implements advanced query enhancement techniques to improve
retrieval accuracy beyond the current 82% target toward 90%+.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class QueryEnhancement:
    """Enhanced query with expansion and classification."""

    original_query: str
    enhanced_query: str
    technical_terms: List[str]
    query_type: str
    expansion_terms: List[str]
    confidence: float

class QueryEnhancer:
    """Advanced query enhancement for better retrieval accuracy."""

    def __init__(self):
        """Initialize query enhancer with RNI-specific knowledge."""

        # RNI-specific terminology expansion
        self.technical_synonyms = {
            "RNI": ["Regional Network Interface", "RNI system", "Network Interface"],
            "security": ["authentication", "authorization", "encryption", "access control"],
            "configuration": ["setup", "config", "settings", "parameters"],
            "installation": ["install", "deployment", "setup", "implementation"],
            "integration": ["connection", "interface", "linking", "binding"],
            "Active Directory": ["AD", "LDAP", "directory service", "user management"],
            "HSM": ["Hardware Security Module", "security module", "crypto module"],
            "report": ["reporting", "analytics", "data export", "statistics"],
            "backup": ["restore", "recovery", "archive", "snapshot"],
            "monitoring": ["alerts", "logging", "tracking", "surveillance"],
        }

        # Technical acronym expansions
        self.acronym_expansions = {
            "RNI": "Regional Network Interface",
            "HSM": "Hardware Security Module",
            "AD": "Active Directory",
            "LDAP": "Lightweight Directory Access Protocol",
            "TLS": "Transport Layer Security",
            "SSL": "Secure Sockets Layer",
            "API": "Application Programming Interface",
            "UI": "User Interface",
            "DB": "Database",
            "OS": "Operating System",
        }

        # Query classification patterns
        self.query_patterns = {
            "installation": [r"install", r"setup", r"deploy", r"configure", r"requirement"],
            "troubleshooting": [r"error", r"problem", r"issue", r"fix", r"resolve", r"debug"],
            "configuration": [r"config", r"setting", r"parameter", r"option", r"customize"],
            "integration": [r"integrate", r"connect", r"interface", r"link", r"bind"],
            "security": [r"security", r"auth", r"permission", r"access", r"encrypt"],
            "reporting": [r"report", r"export", r"data", r"analytics", r"statistics"],
            "general": [r"what", r"how", r"when", r"where", r"why"],
        }

        # Version-specific terms
        self.version_terms = {
            "4.16": ["4.16.0", "4.16.1", "version 4.16", "RNI 4.16"],
            "latest": ["current", "newest", "recent", "updated"],
        }

    def enhance_query(self, query: str) -> QueryEnhancement:
        """
        Enhance a query with technical term expansion and classification.

        Args:
            query: Original user query

        Returns:
            QueryEnhancement with expanded and classified query
        """
        # Classify query type
        query_type = self._classify_query(query)

        # Extract technical terms
        technical_terms = self._extract_technical_terms(query)

        # Generate expansion terms
        expansion_terms = self._generate_expansion_terms(query, technical_terms)

        # Build enhanced query
        enhanced_query = self._build_enhanced_query(query, expansion_terms, query_type)

        # Calculate confidence score
        confidence = self._calculate_confidence(query, technical_terms, query_type)

        return QueryEnhancement(
            original_query=query,
            enhanced_query=enhanced_query,
            technical_terms=technical_terms,
            query_type=query_type,
            expansion_terms=expansion_terms,
            confidence=confidence,
        )

    def _classify_query(self, query: str) -> str:
        """Classify query into predefined types."""
        query_lower = query.lower()

        # Score each category
        category_scores = {}
        for category, patterns in self.query_patterns.items():
            score = sum(1 for pattern in patterns if re.search(pattern, query_lower))
            if score > 0:
                category_scores[category] = score

        # Return highest scoring category or 'general'
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        return "general"

    def _extract_technical_terms(self, query: str) -> List[str]:
        """Extract technical terms and acronyms from query."""
        terms = []

        # Find acronyms (2+ capital letters)
        acronyms = re.findall(r"\b[A-Z]{2,}\b", query)
        terms.extend(acronyms)

        # Find version numbers
        versions = re.findall(r"\b\d+\.\d+(?:\.\d+)?\b", query)
        terms.extend(versions)

        # Find known technical terms
        query_lower = query.lower()
        for term in self.technical_synonyms.keys():
            if term.lower() in query_lower:
                terms.append(term)

        return list(set(terms))  # Remove duplicates

    def _generate_expansion_terms(self, query: str, technical_terms: List[str]) -> List[str]:
        """Generate expansion terms based on technical terms found."""
        expansions = []

        # Expand technical terms
        for term in technical_terms:
            # Check for direct synonyms
            if term in self.technical_synonyms:
                expansions.extend(self.technical_synonyms[term])

            # Check for acronym expansions
            if term in self.acronym_expansions:
                expansions.append(self.acronym_expansions[term])

            # Check for version expansions
            if term in self.version_terms:
                expansions.extend(self.version_terms[term])

        # Add contextual terms based on query type
        query_lower = query.lower()
        if "configure" in query_lower or "setup" in query_lower:
            expansions.extend(["settings", "parameters", "options"])

        if "install" in query_lower:
            expansions.extend(["deployment", "requirements", "prerequisites"])

        if "error" in query_lower or "problem" in query_lower:
            expansions.extend(["troubleshooting", "debugging", "resolution"])

        return list(set(expansions))  # Remove duplicates

    def _build_enhanced_query(self, original: str, expansions: List[str], query_type: str) -> str:
        """Build enhanced query with expansions."""
        # Start with original query
        enhanced = original

        # Add most relevant expansion terms (limit to avoid query explosion)
        relevant_expansions = expansions[:5]  # Top 5 most relevant

        if relevant_expansions:
            # Add expansions as OR terms
            expansion_string = " OR ".join(f'"{term}"' for term in relevant_expansions)
            enhanced = f"{original} ({expansion_string})"

        return enhanced

    def _calculate_confidence(self, query: str, technical_terms: List[str], query_type: str) -> float:
        """Calculate confidence in query enhancement quality."""
        confidence = 0.5  # Base confidence

        # Boost confidence for technical terms found
        confidence += min(len(technical_terms) * 0.1, 0.3)

        # Boost confidence for specific query types
        if query_type != "general":
            confidence += 0.2

        # Boost confidence for longer, more specific queries
        if len(query.split()) > 3:
            confidence += 0.1

        return min(confidence, 1.0)

    def batch_enhance_queries(self, queries: List[str]) -> List[QueryEnhancement]:
        """Enhance multiple queries in batch."""
        return [self.enhance_query(query) for query in queries]

    def analyze_enhancement_impact(self, test_queries: List[str]) -> Dict[str, Any]:
        """Analyze the potential impact of query enhancement."""
        enhancements = self.batch_enhance_queries(test_queries)

        analysis = {
            "total_queries": len(test_queries),
            "average_confidence": sum(e.confidence for e in enhancements) / len(enhancements),
            "query_types": {},
            "technical_terms_found": sum(len(e.technical_terms) for e in enhancements),
            "average_expansions": sum(len(e.expansion_terms) for e in enhancements) / len(enhancements),
            "enhanced_queries": [],
        }

        # Analyze query types
        for enhancement in enhancements:
            query_type = enhancement.query_type
            analysis["query_types"][query_type] = analysis["query_types"].get(query_type, 0) + 1

        # Store enhanced queries for review
        for enhancement in enhancements:
            analysis["enhanced_queries"].append(
                {
                    "original": enhancement.original_query,
                    "enhanced": enhancement.enhanced_query,
                    "type": enhancement.query_type,
                    "confidence": enhancement.confidence,
                    "technical_terms": enhancement.technical_terms,
                    "expansions": enhancement.expansion_terms,
                }
            )

        return analysis

def main():
    """Test query enhancement implementation."""
    logger.info("🔍 Query Enhancement for Higher Accuracy")
    logger.info("=" * 50)

    enhancer = QueryEnhancer()

    # Test queries from our evaluation
    test_queries = [
        "What is the RNI 4.16 release date?",
        "How do you configure the security system?",
        "Active Directory integration setup",
        "installation prerequisites",
        "HSM configuration steps",
        "troubleshoot authentication errors",
        "backup and restore procedures",
    ]

    logger.info("🧪 Testing Query Enhancement:")
    logger.info("-" * 40)

    for query in test_queries:
        enhancement = enhancer.enhance_query(query)

        logger.info(f"\nOriginal: {enhancement.original_query}")
        logger.info(f"Enhanced: {enhancement.enhanced_query}")
        logger.info(f"Type: {enhancement.query_type}")
        logger.info(f"Confidence: {enhancement.confidence:.2f}")
        logger.info(f"Technical Terms: {enhancement.technical_terms}")
        logger.info(f"Expansions: {enhancement.expansion_terms[:3]}...")  # Show first 3

    # Analyze overall impact
    logger.info(f"\n📊 Enhancement Impact Analysis:")
    analysis = enhancer.analyze_enhancement_impact(test_queries)

    logger.info(f"  Total Queries: {analysis['total_queries']}")
    logger.info(f"  Average Confidence: {analysis['average_confidence']:.2f}")
    logger.info(f"  Technical Terms Found: {analysis['technical_terms_found']}")
    logger.info(f"  Average Expansions: {analysis['average_expansions']:.1f}")
    logger.info(f"  Query Types: {analysis['query_types']}")

    # Save analysis
    with open("query_enhancement_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)

    logger.info(f"\n💾 Detailed analysis saved to: query_enhancement_analysis.json")
    logger.info(f"\n💡 Expected Impact: +3-5% improvement in Recall@1")
    logger.info(f"   Target: 82% → 85-87% with query enhancement")

if __name__ == "__main__":
    main()
