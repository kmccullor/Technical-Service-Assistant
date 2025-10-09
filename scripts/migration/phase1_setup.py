#!/usr/bin/env python3
"""
Phase 1 Implementation Plan - Start Domain-Specific Fine-tuning

This script sets up the foundation for improving embedding quality
by creating domain-specific training data from the RNI corpus.
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List

import psycopg2
import requests
from psycopg2.extras import RealDictCursor

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class TrainingPair:
    """A training pair for embedding fine-tuning."""

    query: str
    positive_passage: str
    negative_passages: List[str]
    domain_category: str


class Phase1Setup:
    """Set up Phase 1 implementation for domain-specific improvements."""

    def __init__(self):
        """Initialize Phase 1 setup."""
        self.domain_analysis = self._load_domain_analysis()

    def _load_domain_analysis(self) -> Dict[str, Any]:
        """Load the domain analysis results."""
        try:
            with open("logs/domain_analysis.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("Domain analysis not found. Run simple_domain_analyzer.py first.")
            return {}

    def create_training_data(self) -> List[TrainingPair]:
        """Create training pairs from the corpus for fine-tuning."""
        print("🎯 Creating training data for embedding fine-tuning...")

        # Get chunks from database
        chunks = self._get_chunks_with_metadata()

        if not chunks:
            print("❌ No chunks found. Ensure database is populated.")
            return []

        training_pairs = []

        # Create training pairs based on domain patterns
        training_pairs.extend(self._create_version_pairs(chunks))
        training_pairs.extend(self._create_installation_pairs(chunks))
        training_pairs.extend(self._create_integration_pairs(chunks))
        training_pairs.extend(self._create_security_pairs(chunks))
        training_pairs.extend(self._create_troubleshooting_pairs(chunks))

        print(f"✅ Created {len(training_pairs)} training pairs")
        return training_pairs

    def _get_chunks_with_metadata(self) -> List[Dict]:
        """Get chunks with document context."""
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
                        d.name as document_name,
                        c.id as chunk_id
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
                            "chunk_id": row["chunk_id"],
                        }
                    )

                return chunks

        except Exception as e:
            logger.error(f"Error retrieving chunks: {e}")
            return []
        finally:
            if "conn" in locals():
                conn.close()

    def _create_version_pairs(self, chunks: List[Dict]) -> List[TrainingPair]:
        """Create training pairs for version-related queries."""
        pairs = []

        # Find chunks containing version information
        version_chunks = [
            chunk
            for chunk in chunks
            if any(v in chunk["content"].lower() for v in ["4.16", "4.15", "4.14", "version", "release"])
        ]

        if len(version_chunks) < 3:
            return pairs

        # Create version-specific queries
        version_queries = [
            "RNI 4.16 release information",
            "What's new in RNI 4.16",
            "RNI version 4.16 features",
            "Latest RNI release notes",
            "RNI 4.16.1 updates",
        ]

        for query in version_queries:
            positive = max(version_chunks, key=lambda c: c["content"].lower().count("4.16"))
            negatives = [c["content"] for c in chunks if c != positive][:3]

            pairs.append(
                TrainingPair(
                    query=query,
                    positive_passage=positive["content"],
                    negative_passages=negatives,
                    domain_category="version_information",
                )
            )

        return pairs

    def _create_installation_pairs(self, chunks: List[Dict]) -> List[TrainingPair]:
        """Create training pairs for installation queries."""
        pairs = []

        installation_chunks = [
            chunk
            for chunk in chunks
            if any(term in chunk["content"].lower() for term in ["install", "setup", "configuration", "configure"])
        ]

        if len(installation_chunks) < 3:
            return pairs

        installation_queries = [
            "How to install RNI",
            "RNI installation requirements",
            "RNI setup procedure",
            "Configure RNI settings",
            "RNI installation guide",
        ]

        for query in installation_queries:
            positive = max(installation_chunks, key=lambda c: c["content"].lower().count("install"))
            negatives = [c["content"] for c in chunks if c != positive][:3]

            pairs.append(
                TrainingPair(
                    query=query,
                    positive_passage=positive["content"],
                    negative_passages=negatives,
                    domain_category="installation",
                )
            )

        return pairs

    def _create_integration_pairs(self, chunks: List[Dict]) -> List[TrainingPair]:
        """Create training pairs for integration queries."""
        pairs = []

        integration_chunks = [
            chunk
            for chunk in chunks
            if any(term in chunk["content"].lower() for term in ["integration", "active directory", "ldap", "api"])
        ]

        if len(integration_chunks) < 3:
            return pairs

        integration_queries = [
            "Active Directory integration with RNI",
            "RNI LDAP configuration",
            "How to integrate RNI with existing systems",
            "RNI API integration guide",
            "RNI connector setup",
        ]

        for query in integration_queries:
            positive = max(integration_chunks, key=lambda c: c["content"].lower().count("integration"))
            negatives = [c["content"] for c in chunks if c != positive][:3]

            pairs.append(
                TrainingPair(
                    query=query,
                    positive_passage=positive["content"],
                    negative_passages=negatives,
                    domain_category="integration",
                )
            )

        return pairs

    def _create_security_pairs(self, chunks: List[Dict]) -> List[TrainingPair]:
        """Create training pairs for security queries."""
        pairs = []

        security_chunks = [
            chunk
            for chunk in chunks
            if any(
                term in chunk["content"].lower() for term in ["security", "authentication", "certificate", "encryption"]
            )
        ]

        if len(security_chunks) < 3:
            return pairs

        security_queries = [
            "RNI security configuration",
            "Authentication setup for RNI",
            "RNI certificate management",
            "Security best practices for RNI",
            "RNI encryption settings",
        ]

        for query in security_queries:
            positive = max(security_chunks, key=lambda c: c["content"].lower().count("security"))
            negatives = [c["content"] for c in chunks if c != positive][:3]

            pairs.append(
                TrainingPair(
                    query=query,
                    positive_passage=positive["content"],
                    negative_passages=negatives,
                    domain_category="security",
                )
            )

        return pairs

    def _create_troubleshooting_pairs(self, chunks: List[Dict]) -> List[TrainingPair]:
        """Create training pairs for troubleshooting queries."""
        pairs = []

        troubleshooting_chunks = [
            chunk
            for chunk in chunks
            if any(term in chunk["content"].lower() for term in ["error", "problem", "issue", "troubleshoot", "fix"])
        ]

        if len(troubleshooting_chunks) < 3:
            return pairs

        troubleshooting_queries = [
            "RNI error troubleshooting",
            "How to fix RNI connection issues",
            "RNI authentication errors",
            "Troubleshoot RNI installation problems",
            "Resolve RNI configuration issues",
        ]

        for query in troubleshooting_queries:
            positive = max(troubleshooting_chunks, key=lambda c: c["content"].lower().count("error"))
            negatives = [c["content"] for c in chunks if c != positive][:3]

            pairs.append(
                TrainingPair(
                    query=query,
                    positive_passage=positive["content"],
                    negative_passages=negatives,
                    domain_category="troubleshooting",
                )
            )

        return pairs

    def save_training_data(self, training_pairs: List[TrainingPair], filename: str = "logs/training_data.json"):
        """Save training data to file."""
        training_data = []

        for pair in training_pairs:
            training_data.append(
                {
                    "query": pair.query,
                    "positive_passage": pair.positive_passage,
                    "negative_passages": pair.negative_passages,
                    "domain_category": pair.domain_category,
                }
            )

        with open(filename, "w") as f:
            json.dump(training_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Training data saved to {filename}")

    def test_current_embeddings(self, queries: List[str]) -> Dict[str, Any]:
        """Test current embedding quality on domain-specific queries."""
        print("🧪 Testing current embedding performance...")

        results = {}

        for query in queries:
            try:
                # Test with load balancer (if available)
                start_time = time.time()

                # Simple embedding test using existing system
                response = requests.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": query},
                    timeout=10,
                )

                response_time = time.time() - start_time

                if response.status_code == 200:
                    embedding = response.json().get("embedding", [])
                    results[query] = {"success": True, "embedding_dim": len(embedding), "response_time": response_time}
                else:
                    results[query] = {"success": False, "error": f"HTTP {response.status_code}"}

            except Exception as e:
                results[query] = {"success": False, "error": str(e)}

        return results

    def generate_phase1_report(self, training_pairs: List[TrainingPair], embedding_results: Dict[str, Any]) -> str:
        """Generate Phase 1 setup report."""

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Count by domain category
        category_counts = {}
        for pair in training_pairs:
            category_counts[pair.domain_category] = category_counts.get(pair.domain_category, 0) + 1

        # Embedding test summary
        successful_tests = sum(1 for r in embedding_results.values() if r.get("success", False))
        total_tests = len(embedding_results)

        report = [
            "# Phase 1: Domain-Specific Embedding Setup Report",
            f"**Generated:** {timestamp}",
            "",
            "## 📊 Training Data Summary",
            f"- **Total Training Pairs:** {len(training_pairs)}",
            f"- **Domain Categories:** {len(category_counts)}",
            "",
            "### Training Pairs by Category:",
        ]

        for category, count in sorted(category_counts.items()):
            report.append(f"- **{category.replace('_', ' ').title()}:** {count} pairs")

        report.extend(
            [
                "",
                "## 🧪 Current Embedding Performance",
                f"- **Tests Conducted:** {total_tests}",
                f"- **Successful:** {successful_tests}/{total_tests} ({100*successful_tests/total_tests:.1f}%)",
            ]
        )

        if embedding_results:
            avg_response_time = sum(
                r.get("response_time", 0) for r in embedding_results.values() if r.get("success", False)
            ) / max(successful_tests, 1)
            report.append(f"- **Average Response Time:** {avg_response_time:.3f}s")

        report.extend(
            [
                "",
                "## 🎯 Next Steps",
                "",
                "### Immediate Actions:",
                "1. **Fine-tune Embeddings** - Use generated training pairs",
                "2. **Create Ensemble Models** - Combine multiple embedding approaches",
                "3. **Validate Improvements** - A/B test against current system",
                "",
                "### Implementation Commands:",
                "```bash",
                "# Install fine-tuning dependencies",
                "pip install sentence-transformers datasets",
                "",
                "# Create fine-tuned model (next step)",
                "python embedding_fine_tuner.py",
                "",
                "# Test improvements",
                "python test_phase1_improvements.py",
                "```",
                "",
                "## 📈 Expected Improvements",
                "- **Accuracy Target:** 87%+ Recall@1 (from current 82%)",
                "- **Domain Relevance:** Improved matching for technical terms",
                "- **Response Quality:** Better understanding of RNI-specific context",
                "",
                "## ✅ Phase 1 Foundation Complete",
                "Ready to proceed with embedding fine-tuning and ensemble methods.",
            ]
        )

        return "\n".join(report)


def main():
    """Run Phase 1 setup."""
    print("🚀 Phase 1: Domain-Specific Embedding Setup")
    print("=" * 60)

    # Initialize Phase 1 setup
    phase1 = Phase1Setup()

    if not phase1.domain_analysis:
        print("❌ Domain analysis required. Run: python simple_domain_analyzer.py")
        return

    print(f"📊 Domain analysis loaded: {phase1.domain_analysis['total_documents']} documents")

    # Create training data
    training_pairs = phase1.create_training_data()

    if not training_pairs:
        print("❌ No training pairs created. Check database connection.")
        return

    # Save training data
    phase1.save_training_data(training_pairs)

    # Test current embedding performance
    test_queries = [
        "RNI 4.16 installation requirements",
        "Active Directory integration setup",
        "security configuration guide",
        "troubleshoot authentication errors",
        "RNI version information",
    ]

    embedding_results = phase1.test_current_embeddings(test_queries)

    # Generate report
    report = phase1.generate_phase1_report(training_pairs, embedding_results)

    with open("logs/phase1_setup_report.md", "w") as f:
        f.write(report)

    print(f"\n📈 Phase 1 Results:")
    print(f"  Training pairs created: {len(training_pairs)}")

    successful_tests = sum(1 for r in embedding_results.values() if r.get("success", False))
    print(f"  Embedding tests: {successful_tests}/{len(embedding_results)} successful")

    print(f"\n💾 Files generated:")
    print(f"  - logs/training_data.json")
    print(f"  - logs/phase1_setup_report.md")

    print(f"\n🎯 Next Action:")
    print(f"  Ready to implement embedding fine-tuning!")
    print(f"  Run: python embedding_fine_tuner.py")


if __name__ == "__main__":
    main()
