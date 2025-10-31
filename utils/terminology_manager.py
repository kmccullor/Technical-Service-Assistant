#!/usr/bin/env python3
"""
Terminology Management System for Acronyms and Synonyms.

This module manages the extraction, storage, and retrieval of acronyms and synonyms
during document ingestion, and provides them for use in chat prompts and query expansion.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from config import get_settings
from utils.logging_config import setup_logging

logger = setup_logging(program_name="terminology_manager")


@dataclass
class AcronymEntry:
    """Represents an acronym entry in the database."""

    acronym: str
    definition: str
    confidence_score: float = 0.5
    source_documents: List[str] = None
    usage_count: int = 1
    is_verified: bool = False

    def __post_init__(self):
        if self.source_documents is None:
            self.source_documents = []


@dataclass
class SynonymEntry:
    """Represents a synonym entry in the database."""

    term: str
    synonym: str
    term_type: str = "general"
    confidence_score: float = 0.5
    source_documents: List[str] = None
    context_usage: Optional[str] = None
    usage_count: int = 1
    is_verified: bool = False

    def __post_init__(self):
        if self.source_documents is None:
            self.source_documents = []


@dataclass
class TermRelationship:
    """Represents a term relationship entry."""

    primary_term: str
    related_term: str
    relationship_type: str  # 'synonym', 'acronym', 'abbreviation', 'alias'
    confidence_score: float = 0.5
    source_documents: List[str] = None
    context_examples: List[str] = None
    usage_count: int = 1

    def __post_init__(self):
        if self.source_documents is None:
            self.source_documents = []
        if self.context_examples is None:
            self.context_examples = []


class TerminologyManager:
    """Manages acronyms and synonyms extraction, storage, and retrieval."""

    def __init__(self):
        self.settings = get_settings()
        self.db_conn = None

    def _get_db_connection(self):
        """Get database connection."""
        if self.db_conn is None:
            import psycopg2

            self.db_conn = psycopg2.connect(
                host=self.settings.db_host,
                database=self.settings.db_name,
                user=self.settings.db_user,
                password=self.settings.db_password,
                port=self.settings.db_port,
            )
        return self.db_conn

    def extract_and_store_terminology(self, text: str, document_name: str) -> Dict[str, int]:
        """
        Extract acronyms and synonyms from text and store them in the database.

        Args:
            text: Document text to analyze
            document_name: Name of the source document

        Returns:
            Dictionary with counts of extracted items
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()

            # Extract acronyms
            acronyms = self._extract_acronyms(text)
            stored_acronyms = 0

            for acronym, definition in acronyms.items():
                try:
                    # Check if acronym already exists
                    cur.execute("SELECT id, source_documents, usage_count FROM acronyms WHERE acronym = %s", (acronym,))
                    existing = cur.fetchone()

                    if existing:
                        # Update existing entry
                        existing_id, existing_docs, usage_count = existing
                        new_docs = list(set(existing_docs + [document_name]))
                        cur.execute(
                            """
                            UPDATE acronyms
                            SET source_documents = %s, usage_count = %s, last_updated_at = now()
                            WHERE id = %s
                            """,
                            (new_docs, usage_count + 1, existing_id),
                        )
                    else:
                        # Insert new acronym
                        cur.execute(
                            """
                            INSERT INTO acronyms (acronym, definition, source_documents, confidence_score)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (acronym, definition, [document_name], 0.7),  # Higher confidence for extracted
                        )
                        stored_acronyms += 1

                except Exception as e:
                    logger.warning(f"Failed to store acronym {acronym}: {e}")

            # Extract synonyms and term relationships
            synonyms, relationships = self._extract_synonyms_and_relationships(text)
            stored_synonyms = 0
            stored_relationships = 0

            for synonym_entry in synonyms:
                try:
                    synonym_entry.source_documents = [document_name]
                    cur.execute(
                        """
                        INSERT INTO synonyms (term, synonym, term_type, source_documents, confidence_score, context_usage)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (term, synonym, term_type) DO UPDATE SET
                            usage_count = synonyms.usage_count + 1,
                            source_documents = array_cat(synonyms.source_documents, EXCLUDED.source_documents),
                            last_updated_at = now()
                        """,
                        (
                            synonym_entry.term,
                            synonym_entry.synonym,
                            synonym_entry.term_type,
                            synonym_entry.source_documents,
                            synonym_entry.confidence_score,
                            synonym_entry.context_usage,
                        ),
                    )
                    stored_synonyms += 1

                except Exception as e:
                    logger.warning(f"Failed to store synonym {synonym_entry.term}->{synonym_entry.synonym}: {e}")

            for rel in relationships:
                try:
                    rel.source_documents = [document_name]
                    cur.execute(
                        """
                        INSERT INTO term_relationships (primary_term, related_term, relationship_type, source_documents, confidence_score)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (primary_term, related_term, relationship_type) DO UPDATE SET
                            usage_count = term_relationships.usage_count + 1,
                            source_documents = array_cat(term_relationships.source_documents, EXCLUDED.source_documents),
                            last_updated_at = now()
                        """,
                        (
                            rel.primary_term,
                            rel.related_term,
                            rel.relationship_type,
                            rel.source_documents,
                            rel.confidence_score,
                        ),
                    )
                    stored_relationships += 1

                except Exception as e:
                    logger.warning(f"Failed to store relationship {rel.primary_term}->{rel.related_term}: {e}")

            conn.commit()
            cur.close()

            logger.info(
                f"Extracted and stored terminology from {document_name}: "
                f"{stored_acronyms} acronyms, {stored_synonyms} synonyms, {stored_relationships} relationships"
            )

            return {"acronyms": stored_acronyms, "synonyms": stored_synonyms, "relationships": stored_relationships}

        except Exception as e:
            logger.error(f"Failed to extract and store terminology: {e}")
            return {"acronyms": 0, "synonyms": 0, "relationships": 0}

    def _extract_acronyms(self, text: str) -> Dict[str, str]:
        """Extract acronyms from text using the existing AcronymExtractor."""
        try:
            from docling_processor.acronym_extractor import AcronymExtractor

            extractor = AcronymExtractor()
            return extractor.extract_from_text(text)
        except Exception as e:
            logger.warning(f"Failed to extract acronyms: {e}")
            return {}

    def _extract_synonyms_and_relationships(self, text: str) -> Tuple[List[SynonymEntry], List[TermRelationship]]:
        """Extract synonyms and term relationships from text."""
        synonyms = []
        relationships = []

        # Pattern for synonyms: "term (also known as synonym)" or "term, synonym"
        synonym_patterns = [
            re.compile(
                r"\b([A-Za-z][a-zA-Z\s]{2,20})\s*\((?:also known as|aka|also called)\s*([A-Za-z][a-zA-Z\s]{2,20})\)",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b([A-Za-z][a-zA-Z\s]{2,20})\s*(?:,|or)\s*([A-Za-z][a-zA-Z\s]{2,20})\s*(?:is|are|refers to)",
                re.IGNORECASE,
            ),
        ]

        for pattern in synonym_patterns:
            for match in pattern.finditer(text):
                term1, term2 = match.groups()
                term1 = term1.strip()
                term2 = term2.strip()

                if len(term1) > 2 and len(term2) > 2:
                    # Create synonym entries (bidirectional)
                    synonyms.append(
                        SynonymEntry(
                            term=term1.lower(),
                            synonym=term2.lower(),
                            term_type="general",
                            confidence_score=0.6,
                            context_usage=f"Found in pattern: {match.group()}",
                        )
                    )
                    synonyms.append(
                        SynonymEntry(
                            term=term2.lower(),
                            synonym=term1.lower(),
                            term_type="general",
                            confidence_score=0.6,
                            context_usage=f"Found in pattern: {match.group()}",
                        )
                    )

                    # Create term relationships
                    relationships.append(
                        TermRelationship(
                            primary_term=term1.lower(),
                            related_term=term2.lower(),
                            relationship_type="synonym",
                            confidence_score=0.6,
                            context_examples=[match.group()],
                        )
                    )

        # Extract product synonyms based on common patterns
        product_synonyms = self._extract_product_synonyms(text)
        synonyms.extend(product_synonyms)

        return synonyms, relationships

    def _extract_product_synonyms(self, text: str) -> List[SynonymEntry]:
        """Extract product-specific synonyms."""
        synonyms = []

        # Common product synonym patterns
        product_patterns = {
            "rni": ["regional network interface", "rni system", "network interface"],
            "ami": ["advanced metering infrastructure", "smart metering", "metering system"],
            "flexnet": ["flexnet system", "flexnet platform", "sensus flexnet"],
            "esm": ["enterprise service management", "esm system", "service management"],
        }

        text_lower = text.lower()

        for product, product_synonyms in product_patterns.items():
            if product in text_lower:
                for synonym in product_synonyms:
                    if synonym in text_lower:
                        synonyms.append(
                            SynonymEntry(
                                term=product,
                                synonym=synonym,
                                term_type="product",
                                confidence_score=0.8,
                                context_usage=f"Product synonym found in context",
                            )
                        )

        return synonyms

    def get_relevant_acronyms_for_query(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Get relevant acronyms for a query to include in chat prompts.

        Args:
            query: User query
            max_results: Maximum number of acronyms to return

        Returns:
            List of acronym dictionaries with definition and confidence
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()

            cur.execute(
                "SELECT acronym, definition, confidence_score FROM get_relevant_acronyms(%s, %s)", (query, max_results)
            )

            results = []
            for row in cur.fetchall():
                results.append({"acronym": row[0], "definition": row[1], "confidence": row[2]})

            cur.close()
            return results

        except Exception as e:
            logger.warning(f"Failed to get relevant acronyms: {e}")
            return []

    def get_relevant_synonyms_for_term(
        self, term: str, term_type: Optional[str] = None, max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get relevant synonyms for a term.

        Args:
            term: Term to find synonyms for
            term_type: Optional type filter ('product', 'technical', etc.)
            max_results: Maximum number of synonyms to return

        Returns:
            List of synonym dictionaries
        """
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()

            cur.execute(
                "SELECT term, synonym, term_type, confidence_score FROM get_relevant_synonyms(%s, %s, %s)",
                (term, term_type, max_results),
            )

            results = []
            for row in cur.fetchall():
                results.append({"term": row[0], "synonym": row[1], "type": row[2], "confidence": row[3]})

            cur.close()
            return results

        except Exception as e:
            logger.warning(f"Failed to get relevant synonyms: {e}")
            return []

    def get_term_context_for_prompt(self, terms: List[str]) -> Dict[str, Any]:
        """
        Get terminology context for inclusion in chat prompts.

        Args:
            terms: List of terms to get context for

        Returns:
            Dictionary with acronyms and synonyms organized for prompt inclusion
        """
        context = {"acronyms": [], "synonyms": [], "key_terms": []}

        # Get acronyms for all terms
        all_acronyms = set()
        for term in terms:
            acronyms = self.get_relevant_acronyms_for_query(term, max_results=3)
            for acronym in acronyms:
                if acronym["acronym"] not in all_acronyms:
                    all_acronyms.add(acronym["acronym"])
                    context["acronyms"].append(acronym)

        # Get synonyms for key terms
        for term in terms[:3]:  # Limit to first 3 terms to avoid prompt bloat
            synonyms = self.get_relevant_synonyms_for_term(term, max_results=3)
            context["synonyms"].extend(synonyms)

        # Add key terms themselves
        context["key_terms"] = terms[:5]  # Limit to 5 key terms

        return context

    def build_enhanced_system_prompt(self, base_prompt: str, query_terms: List[str]) -> str:
        """
        Build an enhanced system prompt that includes relevant terminology.

        Args:
            base_prompt: Original system prompt
            query_terms: Key terms from the user query

        Returns:
            Enhanced prompt with terminology context
        """
        term_context = self.get_term_context_for_prompt(query_terms)

        enhancements = []

        if term_context["acronyms"]:
            acronym_text = "Key acronyms and their meanings:\n"
            for acronym in term_context["acronyms"][:3]:  # Limit to avoid prompt bloat
                acronym_text += f"- {acronym['acronym']}: {acronym['definition']}\n"
            enhancements.append(acronym_text)

        if term_context["synonyms"]:
            synonym_text = "Related terms and synonyms:\n"
            # Group by term type
            by_type = defaultdict(list)
            for syn in term_context["synonyms"][:5]:
                by_type[syn["type"]].append(f"{syn['term']} ↔ {syn['synonym']}")

            for term_type, synonyms in by_type.items():
                synonym_text += f"- {term_type.title()}: {', '.join(synonyms)}\n"
            enhancements.append(synonym_text)

        if enhancements:
            enhanced_prompt = base_prompt + "\n\n" + "\n".join(enhancements)
            return enhanced_prompt

        return base_prompt

    def close(self):
        """Close database connection."""
        if self.db_conn:
            self.db_conn.close()
            self.db_conn = None


# Global instance for easy access
terminology_manager = TerminologyManager()


def extract_and_store_terminology(text: str, document_name: str) -> Dict[str, int]:
    """Convenience function for terminology extraction."""
    return terminology_manager.extract_and_store_terminology(text, document_name)


def get_terminology_context_for_prompt(terms: List[str]) -> Dict[str, Any]:
    """Convenience function for getting terminology context."""
    return terminology_manager.get_term_context_for_prompt(terms)


def enhance_system_prompt_with_terminology(base_prompt: str, query_terms: List[str]) -> str:
    """Convenience function for enhancing prompts with terminology."""
    return terminology_manager.build_enhanced_system_prompt(base_prompt, query_terms)
