#!/usr/bin/env python3
"""
Comprehensive Embedding and Retrieval Test Suite

This script generates test questions for each document, tests retrieval accuracy,
and provides detailed scoring and analysis.
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple
import textwrap

import psycopg2
import requests

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from config import get_settings

settings = get_settings()


class RetrievalTestSuite:
    def __init__(self):
        self.db_conn = self.get_db_connection()
        # Use configured URLs
        ollama_host = settings.ollama_url.rsplit("/api", 1)[0] if "/api" in settings.ollama_url else settings.ollama_url
        self.ollama_url = ollama_host.replace("ollama-server-1", "localhost").replace(":11434", ":11434")
        self.embedding_model = settings.embedding_model
        self.generation_model = "mistral:7B"
        self.results = {"test_timestamp": datetime.now().isoformat(), "documents": {}, "overall_metrics": {}}

    def get_db_connection(self):
        db_host = "localhost" if settings.db_host == "pgvector" else settings.db_host
        return psycopg2.connect(
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            host=db_host,
            port=settings.db_port,
        )

    def get_documents(self) -> List[Dict[str, Any]]:
        """Retrieve all processed documents from the database."""
        with self.db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, d.name, COUNT(c.id) as chunk_count
                from pdf_documents d
                LEFT JOIN chunks c ON d.id = c.document_id
                WHERE d.name != 'Unknown Document'
                GROUP BY d.id, d.name
                ORDER BY d.name
            """
            )
            return [{"id": row[0], "name": row[1], "chunk_count": row[2]} for row in cur.fetchall()]

    def get_sample_content(self, document_id: int, limit: int = 10) -> List[str]:
        """Get sample content from a document for question generation."""
        with self.db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT text from document_chunks
                WHERE document_id = %s
                ORDER BY chunk_index
                LIMIT %s
            """,
                (document_id, limit),
            )
            return [row[0] for row in cur.fetchall()]

    def generate_questions_for_document(self, document_name: str, content_samples: List[str]) -> List[Dict[str, str]]:
        """Generate test questions based on document content."""
        # Combine content samples for context
        context = "\n".join(content_samples[:5])  # Use first 5 chunks for context

        prompt = textwrap.dedent(
            f"""
            Based on the following content from "{document_name}", generate exactly 20 diverse
            test questions that can be answered using the document content. Include a mix of:
            - Factual questions (what, when, where)
            - Procedural questions (how to)
            - Conceptual questions (why, explain)
            - Technical questions specific to the content

            Content:
            {context[:2000]}...

            Generate exactly 20 questions, one per line, starting each with "Q: ":
            """
        )

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.generation_model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            response.raise_for_status()

            response_text = response.json().get("response", "")

            # Extract questions from response
            questions = []
            lines = response_text.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("Q: "):
                    question = line[3:].strip()
                    if question and len(question) > 10:  # Filter out very short questions
                        questions.append(
                            {"question": question, "document": document_name, "expected_source": document_name}
                        )

            # If we don't have enough questions, add some generic ones
            while len(questions) < 20:
                generic_questions = [
                    f"What are the main features described in {document_name}?",
                    f"What are the system requirements mentioned in {document_name}?",
                    f"How do you configure the system according to {document_name}?",
                    f"What security considerations are outlined in {document_name}?",
                    f"What are the installation steps described in {document_name}?",
                    f"What troubleshooting steps are provided in {document_name}?",
                    f"What are the key components mentioned in {document_name}?",
                    f"How do you maintain the system according to {document_name}?",
                    f"What are the performance considerations in {document_name}?",
                    f"What are the compatibility requirements in {document_name}?",
                ]

                for generic_q in generic_questions:
                    if len(questions) >= 20:
                        break
                    questions.append(
                        {"question": generic_q, "document": document_name, "expected_source": document_name}
                    )

            return questions[:20]  # Ensure exactly 20 questions

        except Exception as e:
            print(f"Error generating questions for {document_name}: {e}")
            return []

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings", json={"model": self.embedding_model, "prompt": text}, timeout=30
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return None

    def search_similar_chunks(self, question_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Find similar chunks using vector similarity search."""
        with self.db_conn.cursor() as cur:
            cur.execute("SELECT id FROM models WHERE name = %s;", (self.embedding_model,))
            model_result = cur.fetchone()
            if not model_result:
                return []

            model_id = model_result[0]

            cur.execute(
                """
                SELECT c.text, d.name as document_name,
                       1 - (e.embedding <-> %s::vector) AS similarity_score
                from document_chunks c
                JOIN embeddings e ON c.id = e.chunk_id
                JOIN documents d ON c.document_id = d.id
                WHERE e.model_id = %s
                ORDER BY e.embedding <-> %s::vector
                LIMIT %s
            """,
                (json.dumps(question_embedding), model_id, json.dumps(question_embedding), top_k),
            )

            return [
                {"text": row[0], "document_name": row[1], "similarity_score": float(row[2])} for row in cur.fetchall()
            ]

    def test_question(self, question_data: Dict[str, str]) -> Dict[str, Any]:
        """Test a single question and return detailed results."""
        question = question_data["question"]
        expected_document = question_data["expected_source"]

        # Generate embedding for the question
        start_time = time.time()
        question_embedding = self.get_embedding(question)
        embedding_time = time.time() - start_time

        if not question_embedding:
            return {
                "question": question,
                "expected_document": expected_document,
                "status": "failed",
                "error": "Failed to generate embedding",
            }

        # Search for similar chunks
        search_start = time.time()
        results = self.search_similar_chunks(question_embedding, top_k=10)
        search_time = time.time() - search_start

        # Analyze results
        correct_document_results = [r for r in results if r["document_name"] == expected_document]

        # Calculate metrics
        recall_at_1 = 1 if results and results[0]["document_name"] == expected_document else 0
        recall_at_3 = 1 if any(r["document_name"] == expected_document for r in results[:3]) else 0
        recall_at_5 = 1 if any(r["document_name"] == expected_document for r in results[:5]) else 0
        recall_at_10 = 1 if any(r["document_name"] == expected_document for r in results[:10]) else 0

        # Average similarity score for correct document
        avg_similarity = (
            sum(r["similarity_score"] for r in correct_document_results) / len(correct_document_results)
            if correct_document_results
            else 0
        )

        return {
            "question": question,
            "expected_document": expected_document,
            "status": "success",
            "metrics": {
                "recall_at_1": recall_at_1,
                "recall_at_3": recall_at_3,
                "recall_at_5": recall_at_5,
                "recall_at_10": recall_at_10,
                "avg_similarity_score": avg_similarity,
                "embedding_time": embedding_time,
                "search_time": search_time,
                "total_time": embedding_time + search_time,
            },
            "top_results": results[:5],
            "correct_document_count": len(correct_document_results),
        }

    def run_comprehensive_test(self):
        """Run the complete test suite."""
        print("🚀 Starting Comprehensive Embedding and Retrieval Test Suite")
        print("=" * 80)

        # Get all documents
        documents = self.get_documents()
        print(f"📚 Found {len(documents)} documents to test:")
        for doc in documents:
            print(f"  • {doc['name']} ({doc['chunk_count']} chunks)")

        print(f"\n🧪 Generating test questions and running retrieval tests...")

        all_test_results = []

        # Process each document
        for doc in documents:
            print(f"\n📖 Processing: {doc['name']}")

            # Get sample content for question generation
            content_samples = self.get_sample_content(doc["id"], limit=10)

            if not content_samples:
                print(f"  ⚠️  No content found for {doc['name']}, skipping...")
                continue

            # Generate questions
            print(f"  🤔 Generating 20 test questions...")
            questions = self.generate_questions_for_document(doc["name"], content_samples)

            if not questions:
                print(f"  ❌ Failed to generate questions for {doc['name']}")
                continue

            print(f"  ✅ Generated {len(questions)} questions")

            # Test each question
            document_results = []
            print(f"  🔍 Testing retrieval for each question...")

            for i, question_data in enumerate(questions, 1):
                print(f"    Testing question {i}/20...", end=" ")
                result = self.test_question(question_data)
                document_results.append(result)

                if result["status"] == "success":
                    metrics = result["metrics"]
                    print(
                        "R@1: {r1}, R@5: {r5}, Sim: {sim:.3f}".format(
                            r1=metrics['recall_at_1'],
                            r5=metrics['recall_at_5'],
                            sim=metrics['avg_similarity_score'],
                        )
                    )
                else:
                    print(f"❌ {result.get('error', 'Unknown error')}")

            # Calculate document-level metrics
            successful_tests = [r for r in document_results if r["status"] == "success"]
            if successful_tests:
                doc_metrics = {
                    "total_questions": len(questions),
                    "successful_tests": len(successful_tests),
                    "recall_at_1": (
                        sum(r["metrics"]["recall_at_1"] for r in successful_tests)
                        / len(successful_tests)
                    ),
                    "recall_at_3": (
                        sum(r["metrics"]["recall_at_3"] for r in successful_tests)
                        / len(successful_tests)
                    ),
                    "recall_at_5": (
                        sum(r["metrics"]["recall_at_5"] for r in successful_tests)
                        / len(successful_tests)
                    ),
                    "recall_at_10": (
                        sum(r["metrics"]["recall_at_10"] for r in successful_tests)
                        / len(successful_tests)
                    ),
                    "avg_similarity": (
                        sum(r["metrics"]["avg_similarity_score"] for r in successful_tests)
                        / len(successful_tests)
                    ),
                    "avg_embedding_time": sum(r["metrics"]["embedding_time"] for r in successful_tests)
                    / len(successful_tests),
                    "avg_search_time": sum(r["metrics"]["search_time"] for r in successful_tests)
                    / len(successful_tests),
                    "avg_total_time": sum(r["metrics"]["total_time"] for r in successful_tests) / len(successful_tests),
                }

                print(f"  📊 Document Metrics:")
                print(f"    • Recall@1: {doc_metrics['recall_at_1']:.3f}")
                print(f"    • Recall@5: {doc_metrics['recall_at_5']:.3f}")
                print(f"    • Recall@10: {doc_metrics['recall_at_10']:.3f}")
                print(f"    • Avg Similarity: {doc_metrics['avg_similarity']:.3f}")
                print(f"    • Avg Total Time: {doc_metrics['avg_total_time']:.3f}s")

            # Store results
            self.results["documents"][doc["name"]] = {
                "metadata": doc,
                "questions": questions,
                "test_results": document_results,
                "metrics": doc_metrics if successful_tests else {},
            }

            all_test_results.extend(successful_tests)

        # Calculate overall metrics
        if all_test_results:
            overall_metrics = {
                "total_documents": len(documents),
                "total_questions": len(all_test_results),
                "overall_recall_at_1": sum(r["metrics"]["recall_at_1"] for r in all_test_results)
                / len(all_test_results),
                "overall_recall_at_3": sum(r["metrics"]["recall_at_3"] for r in all_test_results)
                / len(all_test_results),
                "overall_recall_at_5": sum(r["metrics"]["recall_at_5"] for r in all_test_results)
                / len(all_test_results),
                "overall_recall_at_10": sum(r["metrics"]["recall_at_10"] for r in all_test_results)
                / len(all_test_results),
                "overall_avg_similarity": sum(r["metrics"]["avg_similarity_score"] for r in all_test_results)
                / len(all_test_results),
                "overall_avg_embedding_time": sum(r["metrics"]["embedding_time"] for r in all_test_results)
                / len(all_test_results),
                "overall_avg_search_time": sum(r["metrics"]["search_time"] for r in all_test_results)
                / len(all_test_results),
                "overall_avg_total_time": sum(r["metrics"]["total_time"] for r in all_test_results)
                / len(all_test_results),
            }

            self.results["overall_metrics"] = overall_metrics

            # Print overall results
            print(f"\n🎯 OVERALL TEST RESULTS")
            print("=" * 80)
            print(f"📚 Documents Tested: {overall_metrics['total_documents']}")
            print(f"❓ Total Questions: {overall_metrics['total_questions']}")
            print(f"🎯 Overall Recall@1: {overall_metrics['overall_recall_at_1']:.3f}")
            print(f"🎯 Overall Recall@5: {overall_metrics['overall_recall_at_5']:.3f}")
            print(f"🎯 Overall Recall@10: {overall_metrics['overall_recall_at_10']:.3f}")
            print(f"📊 Average Similarity Score: {overall_metrics['overall_avg_similarity']:.3f}")
            print(f"⚡ Average Embedding Time: {overall_metrics['overall_avg_embedding_time']:.3f}s")
            print(f"🔍 Average Search Time: {overall_metrics['overall_avg_search_time']:.3f}s")
            print(f"⏱️  Average Total Time: {overall_metrics['overall_avg_total_time']:.3f}s")

        return self.results

    def save_results(self, filename: str = "retrieval_test_results.json"):
        """Save test results to JSON file."""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n💾 Results saved to {filename}")

    def generate_markdown_report(self, filename: str = "RETRIEVAL_TEST_REPORT.md"):
        """Generate a comprehensive markdown report."""
        if not self.results.get("overall_metrics"):
            print("No test results available for report generation.")
            return

        overall = self.results["overall_metrics"]

        def grade(score: float, thresholds: List[Tuple[float, str]]) -> str:
            for threshold, label in thresholds:
                if score > threshold:
                    return label
            return "❌ Poor"

        recall1_grade = grade(
            overall['overall_recall_at_1'],
            [(0.8, '🏆 Excellent'), (0.6, '🥈 Good'), (0.4, '🥉 Fair')],
        )
        recall5_grade = grade(
            overall['overall_recall_at_5'],
            [(0.9, '🏆 Excellent'), (0.8, '🥈 Good'), (0.6, '🥉 Fair')],
        )
        recall10_grade = grade(
            overall['overall_recall_at_10'],
            [(0.95, '🏆 Excellent'), (0.9, '🥈 Good'), (0.8, '🥉 Fair')],
        )
        similarity_grade = grade(
            overall['overall_avg_similarity'],
            [(0.8, '🏆 Excellent'), (0.6, '🥈 Good'), (0.4, '🥉 Fair')],
        )

        report_lines = [
            "# 🔍 Technical Service Assistant - Retrieval Test Report",
            "",
            f"**Test Date:** {self.results['test_timestamp']}",
            f"**Total Documents:** {overall['total_documents']}",
            f"**Total Questions Tested:** {overall['total_questions']}",
            "",
            "## 📊 Overall Performance Metrics",
            "",
            "| Metric | Score | Grade |",
            "|--------|-------|-------|",
            f"| **Recall@1** | {overall['overall_recall_at_1']:.3f} | {recall1_grade} |",
            f"| **Recall@5** | {overall['overall_recall_at_5']:.3f} | {recall5_grade} |",
            f"| **Recall@10** | {overall['overall_recall_at_10']:.3f} | {recall10_grade} |",
            f"| **Avg Similarity** | {overall['overall_avg_similarity']:.3f} | {similarity_grade} |",
            "",
            "## ⚡ Performance Metrics",
            "",
            f"- **Average Embedding Time:** {overall['overall_avg_embedding_time']:.3f}s",
            f"- **Average Search Time:** {overall['overall_avg_search_time']:.3f}s",
            f"- **Average Total Time:** {overall['overall_avg_total_time']:.3f}s",
            "",
            "## 📚 Document-Level Results",
            "",
        ]

        for doc_name, doc_data in self.results["documents"].items():
            if not doc_data.get("metrics"):
                continue

            metrics = doc_data["metrics"]
            metadata = doc_data["metadata"]

            report_lines.extend([
                f"### 📖 {doc_name}",
                "",
                f"**Chunks:** {metadata['chunk_count']} | **Questions:** {metrics['total_questions']} | "
                f"**Successful Tests:** {metrics['successful_tests']}",
                "",
                "| Metric | Score |",
                "|--------|-------|",
                f"| Recall@1 | {metrics['recall_at_1']:.3f} |",
                f"| Recall@5 | {metrics['recall_at_5']:.3f} |",
                f"| Recall@10 | {metrics['recall_at_10']:.3f} |",
                f"| Avg Similarity | {metrics['avg_similarity']:.3f} |",
                f"| Avg Response Time | {metrics['avg_total_time']:.3f}s |",
                "",
                "#### Sample Questions Tested:",
            ])

            for i, question in enumerate(doc_data["questions"][:5], 1):
                report_lines.append(f"{i}. {question['question']}")

            report_lines.append("")

        strengths = []
        if overall['overall_recall_at_1'] > 0.8:
            strengths.append("High precision with Recall@1 > 0.8")
        else:
            strengths.append("Decent recall performance")
        if overall['overall_avg_similarity'] > 0.7:
            strengths.append("Excellent semantic similarity scores")
        else:
            strengths.append("Good semantic matching")
        if overall['overall_avg_total_time'] < 1.0:
            strengths.append("Fast response times < 1s")
        else:
            strengths.append("Reasonable response times")

        improvements = []
        if overall['overall_recall_at_1'] < 0.7:
            improvements.append("Consider improving chunking strategy for better Recall@1")
        if overall['overall_avg_similarity'] < 0.6:
            improvements.append("Optimize embedding model or add reranking for better similarity scores")
        if overall['overall_avg_search_time'] > 0.5:
            improvements.append("Consider indexing optimizations for faster search")

        report_lines.extend([
            "## 🎯 Key Findings",
            "",
            "### ✅ Strengths",
        ])
        report_lines.extend(f"- {item}" for item in strengths)
        report_lines.append("")

        if improvements:
            report_lines.append("### 🔄 Areas for Improvement")
            report_lines.extend(f"- {item}" for item in improvements)
            report_lines.append("")

        retrieval_rating = (
            "Excellent" if overall['overall_recall_at_5'] > 0.9
            else "Good" if overall['overall_recall_at_5'] > 0.8
            else "Needs improvement"
        )
        performance_rating = (
            "Excellent" if overall['overall_avg_total_time'] < 0.5
            else "Good" if overall['overall_avg_total_time'] < 1.0
            else "Consider optimization"
        )
        embedding_rating = (
            "well" if overall['overall_avg_similarity'] > 0.6 else "adequately"
        )

        report_lines.extend([
            "## 🛠️ Recommendations",
            "",
            f"1. **Embedding Quality**: Current nomic-embed-text model performing {embedding_rating}",
            f"2. **Retrieval Performance**: {retrieval_rating} recall rates",
            f"3. **Performance**: {performance_rating} response times",
            "",
            "---",
            "*Report generated by Technical Service Assistant Test Suite*",
            "",
        ])

        report = "\n".join(report_lines)

        with open(filename, "w") as f:
            f.write(report)

        print(f"📝 Markdown report saved to {filename}")


if __name__ == "__main__":
    test_suite = RetrievalTestSuite()

    try:
        print("Starting comprehensive retrieval test suite...")
        results = test_suite.run_comprehensive_test()

        # Save results
        test_suite.save_results()
        test_suite.generate_markdown_report()

        print("\n✅ Test suite completed successfully!")

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        test_suite.db_conn.close()
