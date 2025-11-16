from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='simple_domain_analyzer',
    log_level='INFO',
    log_file=f'/app/logs/simple_domain_analyzer_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

#!/usr/bin/env python3
"""
Simple Domain Corpus Analyzer for RNI Documents

Analyzes the RNI document corpus to extract domain-specific patterns
without external dependencies for quick analysis.
"""

import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor

from config import get_settings

settings = get_settings()

@dataclass
class DomainAnalysis:
    """Results of domain corpus analysis."""

    total_documents: int
    total_chunks: int
    technical_terms: Dict[str, int]
    domain_patterns: Dict[str, List[str]]
    document_types: Dict[str, int]
    acronym_expansions: Dict[str, str]
    vocabulary_stats: Dict[str, Any]

class SimpleDomainAnalyzer:
    """Simple analyzer for RNI document corpus."""

    def __init__(self):
        """Initialize the analyzer."""

        # RNI-specific patterns
        self.rni_patterns = {
            "version_numbers": r"(?:RNI\s+)?(\d+\.\d+(?:\.\d+)?)",
            "installation_terms": r"\b(?:install|installation|setup|configure|configuration)\b",
            "security_terms": r"\b(?:security|authentication|authorization|certificate|encryption)\b",
            "integration_terms": r"\b(?:integration|connector|interface|API|LDAP|Active\s+Directory)\b",
            "troubleshooting_terms": r"\b(?:troubleshoot|error|issue|problem|fix|resolve)\b",
            "technical_acronyms": r"\b[A-Z]{2,6}\b",
            "file_paths": r"[A-Za-z]:\\\\[^\\s]+|/[^\\s]+",
            "ip_addresses": r"\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b",
        }

        # Document type patterns
        self.doc_type_patterns = {
            "installation_guide": r"installation.*guide",
            "integration_guide": r"integration.*guide",
            "release_notes": r"release.*notes",
            "configuration_guide": r"configuration.*guide",
            "troubleshooting_guide": r"troubleshooting.*guide",
            "user_manual": r"user.*manual",
            "admin_guide": r"admin.*guide",
        }

        # Common stop words
        self.stop_words = {
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "this",
            "that",
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

    def analyze_corpus(self) -> DomainAnalysis:
        """Perform comprehensive domain analysis of the RNI corpus."""
        logger.info("Starting domain corpus analysis...")

        # Get all document chunks from database
        chunks = self._get_all_chunks()

        if not chunks:
            logger.error("No document chunks found in database")
            return self._empty_analysis()

        logger.info(f"Analyzing {len(chunks)} document chunks...")

        # Perform various analyses
        technical_terms = self._extract_technical_terms(chunks)
        domain_patterns = self._analyze_domain_patterns(chunks)
        document_types = self._classify_document_types(chunks)
        acronym_expansions = self._extract_acronym_expansions(chunks)
        vocabulary_stats = self._calculate_vocabulary_stats(chunks)

        # Count unique documents
        unique_docs = len(set(chunk["document_name"] for chunk in chunks))

        analysis = DomainAnalysis(
            total_documents=unique_docs,
            total_chunks=len(chunks),
            technical_terms=technical_terms,
            domain_patterns=domain_patterns,
            document_types=document_types,
            acronym_expansions=acronym_expansions,
            vocabulary_stats=vocabulary_stats,
        )

        logger.info("Domain corpus analysis completed")
        return analysis

    def _get_all_chunks(self) -> List[Dict]:
        """Retrieve all document chunks from the database."""
        try:
            conn = psycopg2.connect(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
            )

            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        c.text as content,
                        c.metadata,
                        d.name as document_name
                    from document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    ORDER BY d.name, c.id
                """
                )

                chunks = []
                for row in cursor.fetchall():
                    chunks.append(
                        {
                            "content": row["content"],
                            "metadata": row["metadata"] or {},
                            "document_name": row["document_name"],
                        }
                    )

                return chunks

        except Exception as e:
            logger.error(f"Error retrieving chunks from database: {e}")
            return []
        finally:
            if "conn" in locals():
                conn.close()

    def _extract_technical_terms(self, chunks: List[Dict]) -> Dict[str, int]:
        """Extract and count technical terms across the corpus."""
        technical_terms = Counter()

        for chunk in chunks:
            content = chunk["content"].lower()

            # Extract terms matching technical patterns
            for pattern_name, pattern in self.rni_patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = " ".join(match)
                    if match and len(match.strip()) > 1:
                        technical_terms[match.strip()] += 1

            # Extract capitalized terms (likely technical terms)
            capitalized_terms = re.findall(r"\\b[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*\\b", chunk["content"])
            for term in capitalized_terms:
                if len(term) > 3 and term.lower() not in self.stop_words:
                    technical_terms[term] += 1

        # Return top 100 most common technical terms
        return dict(technical_terms.most_common(100))

    def _analyze_domain_patterns(self, chunks: List[Dict]) -> Dict[str, List[str]]:
        """Analyze domain-specific patterns in the corpus."""
        patterns_found = defaultdict(list)

        for chunk in chunks:
            content = chunk["content"]

            for pattern_name, pattern in self.rni_patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = " ".join(match)
                    if match and match not in patterns_found[pattern_name]:
                        patterns_found[pattern_name].append(match)

        # Limit to top 20 examples per pattern
        return {k: v[:20] for k, v in patterns_found.items()}

    def _classify_document_types(self, chunks: List[Dict]) -> Dict[str, int]:
        """Classify documents by type based on their names."""
        doc_types = Counter()

        for chunk in chunks:
            doc_name = chunk["document_name"].lower()

            classified = False
            for doc_type, pattern in self.doc_type_patterns.items():
                if re.search(pattern, doc_name, re.IGNORECASE):
                    doc_types[doc_type] += 1
                    classified = True
                    break

            if not classified:
                doc_types["other"] += 1

        return dict(doc_types)

    def _extract_acronym_expansions(self, chunks: List[Dict]) -> Dict[str, str]:
        """Extract acronym expansions from the corpus."""
        acronym_expansions = {}

        # Pattern to find acronym definitions: "Full Name (ACRONYM)"
        pattern = r"([A-Z][a-z\\s]+)\\s*\\(([A-Z]{2,6})\\)"

        for chunk in chunks:
            content = chunk["content"]
            matches = re.findall(pattern, content)

            for full_name, acronym in matches:
                full_name = full_name.strip()
                if len(full_name) > 5 and acronym not in acronym_expansions:
                    acronym_expansions[acronym] = full_name

        return acronym_expansions

    def _calculate_vocabulary_stats(self, chunks: List[Dict]) -> Dict[str, Any]:
        """Calculate vocabulary statistics for the corpus."""
        all_words = []

        for chunk in chunks:
            content = chunk["content"]
            # Simple word tokenization
            words = re.findall(r"\\b[a-zA-Z]+\\b", content.lower())
            words = [w for w in words if w not in self.stop_words and len(w) > 2]
            all_words.extend(words)

        unique_words = set(all_words)
        word_freq = Counter(all_words)

        return {
            "total_words": len(all_words),
            "unique_words": len(unique_words),
            "vocabulary_richness": len(unique_words) / len(all_words) if all_words else 0,
            "most_common_word": word_freq.most_common(1)[0] if word_freq else ("none", 0),
            "top_10_words": word_freq.most_common(10),
        }

    def _empty_analysis(self) -> DomainAnalysis:
        """Return empty analysis for error cases."""
        return DomainAnalysis(
            total_documents=0,
            total_chunks=0,
            technical_terms={},
            domain_patterns={},
            document_types={},
            acronym_expansions={},
            vocabulary_stats={},
        )

    def save_analysis(self, analysis: DomainAnalysis, filename: str = "domain_analysis.json"):
        """Save analysis results to JSON file."""
        # Convert to serializable format
        analysis_dict = {
            "total_documents": analysis.total_documents,
            "total_chunks": analysis.total_chunks,
            "technical_terms": analysis.technical_terms,
            "domain_patterns": analysis.domain_patterns,
            "document_types": analysis.document_types,
            "acronym_expansions": analysis.acronym_expansions,
            "vocabulary_stats": analysis.vocabulary_stats,
        }

        with open(filename, "w") as f:
            json.dump(analysis_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Domain analysis saved to {filename}")

    def generate_report(self, analysis: DomainAnalysis) -> str:
        """Generate a human-readable analysis report."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        report = [
            "# RNI Domain Corpus Analysis Report",
            f"**Analysis Date:** {timestamp}",
            "",
            "## 📊 Corpus Overview",
            f"- **Total Documents:** {analysis.total_documents}",
            f"- **Total Chunks:** {analysis.total_chunks}",
            f"- **Unique Words:** {analysis.vocabulary_stats.get('unique_words', 0):,}",
            f"- **Total Words:** {analysis.vocabulary_stats.get('total_words', 0):,}",
            f"- **Vocabulary Richness:** {analysis.vocabulary_stats.get('vocabulary_richness', 0):.3f}",
            "",
            "## 🏷️ Document Types",
        ]

        for doc_type, count in sorted(analysis.document_types.items(), key=lambda x: x[1], reverse=True):
            report.append(f"- **{doc_type.replace('_', ' ').title()}:** {count} chunks")

        report.extend(
            [
                "",
                "## 🔧 Top Technical Terms",
            ]
        )

        for term, count in list(analysis.technical_terms.items())[:20]:
            report.append(f"- **{term}:** {count} occurrences")

        report.extend(
            [
                "",
                "## 🔤 Acronym Expansions",
            ]
        )

        for acronym, expansion in list(analysis.acronym_expansions.items())[:15]:
            report.append(f"- **{acronym}:** {expansion}")

        report.extend(
            [
                "",
                "## 🎯 Domain Patterns Found",
            ]
        )

        for pattern_name, examples in analysis.domain_patterns.items():
            if examples:
                report.append(f"### {pattern_name.replace('_', ' ').title()}")
                for example in examples[:10]:
                    report.append(f"- {example}")
                report.append("")

        return "\\n".join(report)

def main():
    """Run domain corpus analysis."""
    logger.info("🔍 RNI Domain Corpus Analyzer")
    logger.info("=" * 50)

    analyzer = SimpleDomainAnalyzer()

    logger.info("📊 Analyzing RNI document corpus...")
    analysis = analyzer.analyze_corpus()

    if analysis.total_documents == 0:
        logger.info("❌ No documents found in corpus. Please ensure PDFs are processed.")
        return

    logger.info(f"✅ Analysis complete!")
    logger.info(f"📁 Analyzed {analysis.total_documents} documents ({analysis.total_chunks} chunks)")
    logger.info(f"🔤 Found {len(analysis.technical_terms)} technical terms")
    logger.info(f"🏷️ Identified {len(analysis.acronym_expansions)} acronym expansions")

    # Save results
    analyzer.save_analysis(analysis, "logs/domain_analysis.json")

    # Generate and save report
    report = analyzer.generate_report(analysis)
    with open("logs/domain_analysis_report.md", "w") as f:
        f.write(report)

    logger.info(f"💾 Results saved to:")
    logger.info(f"  - logs/domain_analysis.json")
    logger.info(f"  - logs/domain_analysis_report.md")

    # Display key findings
    logger.info(f"\\n🎯 Key Findings:")
    if analysis.technical_terms:
        top_term = list(analysis.technical_terms.items())[0]
        logger.info(f"  Most common technical term: {top_term[0]} ({top_term[1]} occurrences)")

    if analysis.document_types:
        top_doc_type = max(analysis.document_types.items(), key=lambda x: x[1])
        logger.info(f"  Most frequent document type: {top_doc_type[0]} ({top_doc_type[1]} chunks)")

    vocab_richness = analysis.vocabulary_stats.get("vocabulary_richness", 0)
    logger.info(f"  Vocabulary richness: {vocab_richness:.3f}")

    logger.info(f"\\n🚀 Ready for Phase 1 embedding fine-tuning!")

if __name__ == "__main__":
    main()
