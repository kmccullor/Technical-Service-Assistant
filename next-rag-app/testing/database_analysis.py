#!/usr/bin/env python3
"""
Comprehensive Database Analysis Script for RAG System Testing
Analyzes all documents, chunks, and metadata in the PGVector database
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor


class DatabaseAnalyzer:
    def __init__(self):
        """Initialize database connection"""
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "vector_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
        )
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)

    def analyze_documents(self) -> Dict[str, Any]:
        """Analyze documents table structure and content"""
        print("📊 Analyzing documents...")

        # Get document statistics
        self.cursor.execute(
            """
            SELECT
                COUNT(*) as total_documents,
                COUNT(DISTINCT document_type) as unique_types,
                COUNT(DISTINCT document_category) as unique_categories,
                COUNT(DISTINCT product_family) as unique_products,
                AVG(file_size) as avg_file_size,
                MAX(file_size) as max_file_size,
                MIN(file_size) as min_file_size
            FROM documents
        """
        )

        stats = dict(self.cursor.fetchone())

        # Get document types distribution
        self.cursor.execute(
            """
            SELECT document_type, document_category, COUNT(*) as count
            FROM documents
            GROUP BY document_type, document_category
            ORDER BY count DESC
        """
        )

        type_distribution = []
        for row in self.cursor.fetchall():
            type_distribution.append(dict(row))

        # Get document titles and metadata
        self.cursor.execute(
            """
            SELECT id, title, file_name, document_type, document_category,
                   product_name, product_version, doc_number, metadata
            FROM documents
            ORDER BY id
        """
        )

        documents = []
        for row in self.cursor.fetchall():
            doc = dict(row)
            documents.append(doc)

        return {"statistics": stats, "type_distribution": type_distribution, "documents": documents}

    def analyze_chunks(self) -> Dict[str, Any]:
        """Analyze document chunks and their properties"""
        print("📊 Analyzing document chunks...")

        # Get chunk statistics
        self.cursor.execute(
            """
            SELECT
                COUNT(*) as total_chunks,
                AVG(content_length) as avg_content_length,
                MAX(content_length) as max_content_length,
                MIN(content_length) as min_content_length,
                AVG(tokens) as avg_tokens,
                COUNT(DISTINCT chunk_type) as unique_chunk_types,
                COUNT(DISTINCT language) as unique_languages
            FROM document_chunks
        """
        )

        chunk_stats = dict(self.cursor.fetchone())

        # Get chunk type distribution
        self.cursor.execute(
            """
            SELECT chunk_type, COUNT(*) as count
            FROM document_chunks
            GROUP BY chunk_type
            ORDER BY count DESC
        """
        )

        chunk_types = []
        for row in self.cursor.fetchall():
            chunk_types.append(dict(row))

        # Get chunks per document
        self.cursor.execute(
            """
            SELECT
                d.title, d.document_type, d.file_name,
                COUNT(dc.id) as chunk_count,
                AVG(dc.content_length) as avg_chunk_length,
                AVG(dc.tokens) as avg_tokens
            FROM documents d
            LEFT JOIN document_chunks dc ON d.id = dc.document_id
            GROUP BY d.id, d.title, d.document_type, d.file_name
            ORDER BY chunk_count DESC
        """
        )

        chunks_per_doc = []
        for row in self.cursor.fetchall():
            chunks_per_doc.append(dict(row))

        return {"statistics": chunk_stats, "chunk_types": chunk_types, "chunks_per_document": chunks_per_doc}

    def analyze_embeddings(self) -> Dict[str, Any]:
        """Analyze embedding vectors and their properties"""
        print("📊 Analyzing embeddings...")

        # Check embedding dimensions and nulls
        self.cursor.execute(
            """
            SELECT
                COUNT(*) as total_embeddings,
                COUNT(embedding) as non_null_embeddings
            FROM document_chunks
            WHERE embedding IS NOT NULL
        """
        )

        result = self.cursor.fetchone()
        embedding_info = dict(result) if result else {}

        # Get embedding dimension separately using vector function
        try:
            self.cursor.execute(
                """
                SELECT vector_dims(embedding) as embedding_dimension
                FROM document_chunks
                WHERE embedding IS NOT NULL
                LIMIT 1
            """
            )

            dim_result = self.cursor.fetchone()
            if dim_result:
                embedding_info["embedding_dimension"] = dim_result["embedding_dimension"]
            else:
                embedding_info["embedding_dimension"] = None
        except Exception as e:
            print(f"Could not get embedding dimension: {e}")
            embedding_info["embedding_dimension"] = None

        # Get embedding model distribution
        self.cursor.execute(
            """
            SELECT
                metadata->>'embedding_model' as embedding_model,
                COUNT(*) as count
            FROM document_chunks
            WHERE metadata->>'embedding_model' IS NOT NULL
            GROUP BY metadata->>'embedding_model'
        """
        )

        models = []
        for row in self.cursor.fetchall():
            models.append(dict(row))

        return {"embedding_info": embedding_info, "models_used": models}

    def generate_test_questions(self, documents: List[Dict]) -> List[Dict[str, Any]]:
        """Generate comprehensive test questions based on document content"""
        print("🤔 Generating test questions...")

        questions = []

        # Question templates by document type
        question_templates = {
            "user_guide": [
                "How do I configure {product_name}?",
                "What are the installation requirements for {product_name}?",
                "What troubleshooting steps are available for {product_name}?",
                "How do I update {product_name}?",
                "What are the security settings for {product_name}?",
            ],
            "installation_guide": [
                "What are the system requirements for installation?",
                "How do I install {product_name}?",
                "What are the pre-installation steps?",
                "How do I verify the installation was successful?",
                "What are common installation issues?",
            ],
            "integration_guide": [
                "How do I integrate {product_name} with other systems?",
                "What APIs are available for integration?",
                "What are the authentication requirements?",
                "How do I configure {product_name} for integration?",
                "What are the integration best practices?",
            ],
            "reference_manual": [
                "What are the technical specifications of {product_name}?",
                "What are all the available commands?",
                "How do I configure advanced settings?",
                "What are the API endpoints?",
                "What are the configuration parameters?",
            ],
            "release_notes": [
                "What's new in version {product_version}?",
                "What bugs were fixed in {product_version}?",
                "What are the breaking changes?",
                "What features were added?",
                "What are the upgrade instructions?",
            ],
        }

        # Generic questions that apply to all documents
        generic_questions = [
            "What is RNI?",
            "What are the main features?",
            "How do I get started?",
            "What are the system requirements?",
            "Where can I find documentation?",
            "What versions are available?",
            "How do I troubleshoot issues?",
            "What support options are available?",
            "How do I contact support?",
            "What are the licensing requirements?",
        ]

        # Add generic questions
        for question in generic_questions:
            questions.append(
                {
                    "question": question,
                    "type": "generic",
                    "expected_topics": ["general", "overview"],
                    "difficulty": "basic",
                }
            )

        # Add document-specific questions
        for doc in documents:
            doc_type = doc.get("document_type", "").lower()
            product_name = doc.get("product_name", "the product")
            product_version = doc.get("product_version", "latest")
            title = doc.get("title", "")

            if doc_type in question_templates:
                for template in question_templates[doc_type]:
                    question = template.format(product_name=product_name, product_version=product_version)
                    questions.append(
                        {
                            "question": question,
                            "type": doc_type,
                            "document_id": doc["id"],
                            "document_title": title,
                            "expected_topics": [doc_type, product_name.lower()],
                            "difficulty": "intermediate",
                        }
                    )

        # Add complex/edge case questions
        complex_questions = [
            {
                "question": "How do I migrate from version 4.14 to 4.16?",
                "type": "complex",
                "expected_topics": ["migration", "upgrade", "version"],
                "difficulty": "advanced",
            },
            {
                "question": "What are the differences between RNI versions?",
                "type": "comparison",
                "expected_topics": ["version", "comparison", "features"],
                "difficulty": "advanced",
            },
            {
                "question": "How do I integrate RNI with Active Directory?",
                "type": "integration",
                "expected_topics": ["integration", "active directory", "authentication"],
                "difficulty": "advanced",
            },
            {
                "question": "What network ports does RNI use?",
                "type": "technical",
                "expected_topics": ["network", "ports", "configuration"],
                "difficulty": "intermediate",
            },
            {
                "question": "How do I backup RNI configuration?",
                "type": "maintenance",
                "expected_topics": ["backup", "configuration", "maintenance"],
                "difficulty": "intermediate",
            },
        ]

        questions.extend(complex_questions)

        return questions

    def save_analysis_report(self, analysis: Dict[str, Any]) -> str:
        """Save comprehensive analysis report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"/home/kmccullor/Projects/Technical-Service-Assistant/next-rag-app/testing/database_analysis_report_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(analysis, f, indent=2, default=str)

        return report_file

    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run complete database analysis"""
        print("🔍 Starting comprehensive database analysis...")

        analysis = {
            "timestamp": datetime.now().isoformat(),
            "database_info": {},
            "documents": {},
            "chunks": {},
            "embeddings": {},
            "test_questions": [],
        }

        try:
            # Analyze documents
            analysis["documents"] = self.analyze_documents()

            # Analyze chunks
            analysis["chunks"] = self.analyze_chunks()

            # Analyze embeddings
            analysis["embeddings"] = self.analyze_embeddings()

            # Generate test questions
            analysis["test_questions"] = self.generate_test_questions(analysis["documents"]["documents"])

            # Add summary
            analysis["summary"] = {
                "total_documents": analysis["documents"]["statistics"]["total_documents"],
                "total_chunks": analysis["chunks"]["statistics"]["total_chunks"],
                "total_test_questions": len(analysis["test_questions"]),
                "document_types": len(analysis["documents"]["type_distribution"]),
                "chunk_types": len(analysis["chunks"]["chunk_types"]),
                "embedding_dimension": analysis["embeddings"]["embedding_info"].get("embedding_dimension", "N/A"),
            }

            print("✅ Database analysis completed successfully!")
            return analysis

        except Exception as e:
            print(f"❌ Error during analysis: {e}")
            raise
        finally:
            self.cursor.close()
            self.conn.close()


def main():
    """Main execution function"""
    analyzer = DatabaseAnalyzer()
    analysis = analyzer.run_comprehensive_analysis()

    # Save report
    report_file = analyzer.save_analysis_report(analysis)
    print(f"📊 Analysis report saved to: {report_file}")

    # Print summary
    summary = analysis["summary"]
    print("\n📋 ANALYSIS SUMMARY:")
    print(f"  📚 Total Documents: {summary['total_documents']}")
    print(f"  🧩 Total Chunks: {summary['total_chunks']}")
    print(f"  ❓ Test Questions Generated: {summary['total_test_questions']}")
    print(f"  📖 Document Types: {summary['document_types']}")
    print(f"  🔤 Chunk Types: {summary['chunk_types']}")
    print(f"  🔢 Embedding Dimension: {summary['embedding_dimension']}")

    return analysis


if __name__ == "__main__":
    main()
