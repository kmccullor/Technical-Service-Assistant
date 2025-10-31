#!/usr/bin/env python3
"""
Comprehensive RAG Document Validation Suite
Generates 20+ targeted questions per document and validates RAG responses with detailed confidence analysis.
"""

import json
import os
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass
class TestResult:
    document: str
    question: str
    expected_keywords: List[str]
    response_time: float
    confidence: Optional[float]
    answer: str
    sources_found: int
    keywords_matched: int
    success: bool
    reasoning: str


class ComprehensiveRAGTester:
    def __init__(self, api_url: str = "http://localhost:3015/api/chat"):
        self.api_url = api_url
        self.results = []

    def generate_document_questions(self) -> Dict[str, List[Dict]]:
        """Generate 20+ targeted questions for each document type"""

        question_templates = {
            "Installation Guide": [
                "What are the system requirements for installing {}?",
                "What are the prerequisites for {} installation?",
                "How do you prepare the system for {} installation?",
                "What ports need to be configured for {}?",
                "What are the minimum hardware requirements for {}?",
                "How do you verify the {} installation was successful?",
                "What services need to be started after {} installation?",
                "How do you troubleshoot {} installation issues?",
                "What are the post-installation configuration steps for {}?",
                "How do you uninstall or remove {}?",
                "What firewall rules are needed for {}?",
                "How do you upgrade from a previous version of {}?",
                "What database setup is required for {}?",
                "How do you configure network settings for {}?",
                "What are the security considerations during {} installation?",
                "How do you backup the system before installing {}?",
                "What logs should you check during {} installation?",
                "How do you configure SSL/TLS for {}?",
                "What are the typical installation errors for {}?",
                "How do you perform a silent installation of {}?",
                "What environment variables need to be set for {}?",
                "How do you validate the {} installation configuration?",
            ],
            "User Guide": [
                "How do you access the {} interface?",
                "What are the main features of {}?",
                "How do you configure {} settings?",
                "What are the navigation options in {}?",
                "How do you create new items in {}?",
                "How do you edit existing configurations in {}?",
                "What are the security features of {}?",
                "How do you manage user permissions in {}?",
                "What reports are available in {}?",
                "How do you export data from {}?",
                "How do you import data into {}?",
                "What are the keyboard shortcuts for {}?",
                "How do you customize the {} dashboard?",
                "What are the troubleshooting steps for {}?",
                "How do you backup {} configurations?",
                "How do you restore {} settings?",
                "What are the performance optimization tips for {}?",
                "How do you monitor {} system health?",
                "What alerts and notifications does {} provide?",
                "How do you schedule tasks in {}?",
                "What are the integration capabilities of {}?",
                "How do you manage {} workflows?",
            ],
            "Reference Manual": [
                "What are the technical specifications of {}?",
                "What APIs are available in {}?",
                "What are the configuration parameters for {}?",
                "What data formats does {} support?",
                "What are the {} protocol specifications?",
                "What error codes can {} generate?",
                "What are the {} performance metrics?",
                "What are the {} memory requirements?",
                "What network protocols does {} use?",
                "What are the {} file formats?",
                "What security protocols does {} implement?",
                "What are the {} logging mechanisms?",
                "What backup procedures are recommended for {}?",
                "What are the {} scalability limits?",
                "What third-party integrations does {} support?",
                "What are the {} compliance requirements?",
                "What monitoring tools work with {}?",
                "What are the {} disaster recovery procedures?",
                "What performance tuning options exist for {}?",
                "What are the {} upgrade procedures?",
                "What debugging tools are available for {}?",
                "What are the {} best practices?",
            ],
            "Release Notes": [
                "What are the new features in {}?",
                "What bugs were fixed in {}?",
                "What are the known issues in {}?",
                "What security updates are included in {}?",
                "What are the breaking changes in {}?",
                "What performance improvements are in {}?",
                "What deprecated features are removed in {}?",
                "What are the upgrade instructions for {}?",
                "What compatibility changes exist in {}?",
                "What new APIs were added in {}?",
                "What configuration changes are required for {}?",
                "What are the rollback procedures for {}?",
                "What testing was performed for {}?",
                "What documentation updates accompany {}?",
                "What third-party updates are included in {}?",
                "What are the system requirement changes in {}?",
                "What new integrations are available in {}?",
                "What licensing changes occurred in {}?",
                "What migration steps are needed for {}?",
                "What validation steps are recommended for {}?",
                "What monitoring changes exist in {}?",
                "What support changes accompany {}?",
            ],
            "Integration Guide": [
                "How do you integrate {} with other systems?",
                "What are the {} API endpoints?",
                "How do you authenticate with {} services?",
                "What data formats does {} exchange?",
                "How do you configure {} connectors?",
                "What are the {} message formats?",
                "How do you handle {} error responses?",
                "What are the {} rate limiting rules?",
                "How do you test {} integrations?",
                "What are the {} security requirements for integration?",
                "How do you monitor {} integration health?",
                "What are the {} timeout configurations?",
                "How do you handle {} failover scenarios?",
                "What are the {} data mapping requirements?",
                "How do you configure {} webhooks?",
                "What are the {} batch processing capabilities?",
                "How do you implement {} real-time updates?",
                "What are the {} versioning strategies?",
                "How do you manage {} credentials securely?",
                "What are the {} troubleshooting procedures?",
                "How do you optimize {} performance?",
                "What are the {} compliance considerations?",
            ],
        }

        # Get actual documents from archive
        archive_path = "/home/kmccullor/Projects/Technical-Service-Assistant/uploads/archive"
        if os.path.exists(archive_path):
            documents = [f for f in os.listdir(archive_path) if f.endswith(".pdf")]
        else:
            # Fallback to known documents
            documents = [
                "RNI 4.14 Installation Guide.pdf",
                "RNI 4.15 Device Manager Electric User Guide.pdf",
                "RNI 4.16 System Security User Guide.pdf",
                "RNI 4.14.1 Release Notes.pdf",
            ]

        generated_questions = {}

        for doc in documents:
            doc_questions = []
            doc_name = doc.replace(".pdf", "")

            # Determine document type and generate appropriate questions
            if "Installation Guide" in doc:
                template_set = question_templates["Installation Guide"]
                keywords = ["install", "setup", "configure", "requirement", "prerequisite"]
            elif "User Guide" in doc:
                template_set = question_templates["User Guide"]
                keywords = ["interface", "feature", "configure", "navigate", "manage"]
            elif "Reference Manual" in doc or "Specs" in doc:
                template_set = question_templates["Reference Manual"]
                keywords = ["specification", "API", "protocol", "format", "parameter"]
            elif "Release Notes" in doc:
                template_set = question_templates["Release Notes"]
                keywords = ["feature", "fix", "update", "change", "improve"]
            elif "Integration Guide" in doc:
                template_set = question_templates["Integration Guide"]
                keywords = ["integrate", "API", "connect", "authenticate", "configure"]
            else:
                template_set = question_templates["User Guide"]  # Default
                keywords = ["feature", "configure", "use", "manage", "setup"]

            # Generate questions for this document
            for i, template in enumerate(template_set):
                if i < 22:  # Limit to 22 questions per document
                    question = template.format(doc_name)
                    doc_questions.append(
                        {
                            "question": question,
                            "expected_keywords": keywords + [doc_name.split()[0], doc_name.split()[1]]
                            if len(doc_name.split()) > 1
                            else keywords,
                            "document_type": template_set,
                        }
                    )

            generated_questions[doc] = doc_questions

        return generated_questions

    def test_document_questions(self, document: str, questions: List[Dict]) -> List[TestResult]:
        """Test all questions for a specific document"""
        results = []

        print(f"\n🔍 Testing {len(questions)} questions for: {document}")
        print("=" * 80)

        for i, q_data in enumerate(questions, 1):
            question = q_data["question"]
            expected_keywords = q_data["expected_keywords"]

            print(f"\n📋 Question {i}/{len(questions)}: {question}")

            start_time = time.time()

            try:
                # Query the RAG Chat endpoint
                payload = {"messages": [{"role": "user", "content": question}]}

                response = requests.post(
                    self.api_url, json=payload, timeout=45, headers={"Content-Type": "application/json"}
                )

                response_time = time.time() - start_time

                if response.status_code == 200:
                    # Parse streaming response
                    answer, confidence, sources_count = self.parse_streaming_response(response.text)

                    # Calculate keyword matching
                    keywords_matched = sum(1 for kw in expected_keywords if kw.lower() in answer.lower())

                    # Determine success criteria
                    success = (
                        confidence
                        and confidence >= 0.95
                        and keywords_matched >= len(expected_keywords) // 2  # 95%+ confidence
                        and len(answer) > 50  # At least half keywords  # Substantial answer
                    )

                    reasoning = self.generate_reasoning(
                        confidence, keywords_matched, len(expected_keywords), sources_count, len(answer)
                    )

                    result = TestResult(
                        document=document,
                        question=question,
                        expected_keywords=expected_keywords,
                        response_time=response_time,
                        confidence=confidence,
                        answer=answer[:200] + "..." if len(answer) > 200 else answer,
                        sources_found=sources_count,
                        keywords_matched=keywords_matched,
                        success=success,
                        reasoning=reasoning,
                    )

                    # Display results immediately
                    self.display_result(result)

                else:
                    result = TestResult(
                        document=document,
                        question=question,
                        expected_keywords=expected_keywords,
                        response_time=response_time,
                        confidence=None,
                        answer="",
                        sources_found=0,
                        keywords_matched=0,
                        success=False,
                        reasoning=f"API Error: {response.status_code}",
                    )
                    print(f"❌ API Error: {response.status_code}")

            except Exception as e:
                result = TestResult(
                    document=document,
                    question=question,
                    expected_keywords=expected_keywords,
                    response_time=time.time() - start_time,
                    confidence=None,
                    answer="",
                    sources_found=0,
                    keywords_matched=0,
                    success=False,
                    reasoning=f"Exception: {str(e)}",
                )
                print(f"❌ Exception: {str(e)}")

            results.append(result)

            # Small delay between requests
            time.sleep(1)

        return results

    def parse_streaming_response(self, response_text: str) -> Tuple[str, Optional[float], int]:
        """Parse streaming SSE response to extract answer, confidence, and sources"""
        answer_tokens = []
        confidence = None
        sources_count = 0

        try:
            lines = response_text.strip().split("\n")
            for line in lines:
                if line.startswith("data: "):
                    json_str = line[6:]
                    try:
                        parsed = json.loads(json_str)

                        if parsed.get("type") == "token":
                            answer_tokens.append(parsed.get("token", ""))
                        elif parsed.get("type") == "sources":
                            confidence = parsed.get("confidence")
                            sources_count = len(parsed.get("sources", []))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        answer = "".join(answer_tokens)
        return answer, confidence, sources_count

    def generate_reasoning(
        self,
        confidence: Optional[float],
        keywords_matched: int,
        total_keywords: int,
        sources_count: int,
        answer_length: int,
    ) -> str:
        """Generate detailed reasoning for the test result"""
        reasoning_parts = []

        if confidence:
            conf_pct = confidence * 100
            if conf_pct >= 95:
                reasoning_parts.append(f"🎯 Excellent confidence: {conf_pct:.1f}%")
            elif conf_pct >= 85:
                reasoning_parts.append(f"✅ Good confidence: {conf_pct:.1f}%")
            elif conf_pct >= 70:
                reasoning_parts.append(f"⚠️ Moderate confidence: {conf_pct:.1f}%")
            else:
                reasoning_parts.append(f"❌ Low confidence: {conf_pct:.1f}%")
        else:
            reasoning_parts.append("❌ No confidence score")

        keyword_ratio = keywords_matched / total_keywords if total_keywords > 0 else 0
        if keyword_ratio >= 0.7:
            reasoning_parts.append(f"🔍 Strong keyword match: {keywords_matched}/{total_keywords}")
        elif keyword_ratio >= 0.5:
            reasoning_parts.append(f"✅ Good keyword match: {keywords_matched}/{total_keywords}")
        else:
            reasoning_parts.append(f"⚠️ Weak keyword match: {keywords_matched}/{total_keywords}")

        if sources_count >= 3:
            reasoning_parts.append(f"📚 Multiple sources: {sources_count}")
        elif sources_count >= 1:
            reasoning_parts.append(f"📄 Source found: {sources_count}")
        else:
            reasoning_parts.append("❌ No sources")

        if answer_length >= 100:
            reasoning_parts.append(f"📝 Comprehensive answer: {answer_length} chars")
        elif answer_length >= 50:
            reasoning_parts.append(f"📝 Adequate answer: {answer_length} chars")
        else:
            reasoning_parts.append(f"⚠️ Brief answer: {answer_length} chars")

        return " | ".join(reasoning_parts)

    def display_result(self, result: TestResult):
        """Display individual test result with detailed formatting"""
        status = "✅ SUCCESS" if result.success else "❌ FAILED"
        conf_display = f"{result.confidence*100:.1f}%" if result.confidence else "N/A"

        print(
            f"   {status} | Confidence: {conf_display} | Sources: {result.sources_found} | Keywords: {result.keywords_matched}"
        )
        print(f"   💭 Reasoning: {result.reasoning}")
        if result.answer:
            print(f"   📝 Answer: {result.answer}")
        print()

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test suite across all documents"""
        print("🚀 Starting Comprehensive RAG Document Validation")
        print("=" * 80)

        # Generate questions for all documents
        all_questions = self.generate_document_questions()

        print(f"📊 Generated questions for {len(all_questions)} documents")
        total_questions = sum(len(questions) for questions in all_questions.values())
        print(f"📋 Total questions to test: {total_questions}")

        start_time = time.time()
        all_results = []

        # Test each document
        for document, questions in all_questions.items():
            doc_results = self.test_document_questions(document, questions)
            all_results.extend(doc_results)

            # Document summary
            doc_success = sum(1 for r in doc_results if r.success)
            doc_avg_conf = statistics.mean([r.confidence for r in doc_results if r.confidence]) if doc_results else 0
            print(
                f"\n📊 {document} Summary: {doc_success}/{len(doc_results)} passed, Avg Confidence: {doc_avg_conf*100:.1f}%"
            )

        total_time = time.time() - start_time

        # Generate comprehensive summary
        summary = self.generate_summary(all_results, total_time)

        # Save results
        self.save_results(all_results, summary)

        return summary

    def generate_summary(self, results: List[TestResult], total_time: float) -> Dict[str, Any]:
        """Generate comprehensive test summary"""
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.success)
        failed_tests = total_tests - successful_tests

        confidences = [r.confidence for r in results if r.confidence]
        avg_confidence = statistics.mean(confidences) if confidences else 0
        high_conf_tests = sum(1 for c in confidences if c >= 0.95)

        response_times = [r.response_time for r in results]
        avg_response_time = statistics.mean(response_times) if response_times else 0

        # Document-level analysis
        doc_analysis = {}
        for result in results:
            if result.document not in doc_analysis:
                doc_analysis[result.document] = {"total": 0, "passed": 0, "confidences": []}

            doc_analysis[result.document]["total"] += 1
            if result.success:
                doc_analysis[result.document]["passed"] += 1
            if result.confidence:
                doc_analysis[result.document]["confidences"].append(result.confidence)

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": successful_tests / total_tests if total_tests > 0 else 0,
            "average_confidence": avg_confidence,
            "high_confidence_tests": high_conf_tests,
            "high_confidence_rate": high_conf_tests / len(confidences) if confidences else 0,
            "average_response_time": avg_response_time,
            "total_time": total_time,
            "documents_tested": len(doc_analysis),
            "document_analysis": {
                doc: {
                    "success_rate": data["passed"] / data["total"],
                    "avg_confidence": statistics.mean(data["confidences"]) if data["confidences"] else 0,
                    "total_questions": data["total"],
                    "passed_questions": data["passed"],
                }
                for doc, data in doc_analysis.items()
            },
        }

        return summary

    def save_results(self, results: List[TestResult], summary: Dict[str, Any]):
        """Save detailed results and summary to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save detailed results
        results_file = f"comprehensive_rag_results_{timestamp}.json"
        detailed_results = {
            "summary": summary,
            "detailed_results": [
                {
                    "document": r.document,
                    "question": r.question,
                    "expected_keywords": r.expected_keywords,
                    "response_time": r.response_time,
                    "confidence": r.confidence,
                    "answer": r.answer,
                    "sources_found": r.sources_found,
                    "keywords_matched": r.keywords_matched,
                    "success": r.success,
                    "reasoning": r.reasoning,
                }
                for r in results
            ],
        }

        with open(results_file, "w") as f:
            json.dump(detailed_results, f, indent=2)

        print(f"\n💾 Detailed results saved to: {results_file}")

        # Display final summary
        self.display_final_summary(summary)

    def display_final_summary(self, summary: Dict[str, Any]):
        """Display comprehensive final summary"""
        print("\n" + "=" * 100)
        print("🎯 COMPREHENSIVE RAG VALIDATION SUMMARY")
        print("=" * 100)

        print(f"📊 Overall Results:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   Successful: {summary['successful_tests']} ({summary['success_rate']*100:.1f}%)")
        print(f"   Failed: {summary['failed_tests']}")

        print(f"\n🎯 Confidence Analysis:")
        print(f"   Average Confidence: {summary['average_confidence']*100:.1f}%")
        print(
            f"   High Confidence (≥95%): {summary['high_confidence_tests']} ({summary['high_confidence_rate']*100:.1f}%)"
        )

        print(f"\n⚡ Performance:")
        print(f"   Average Response Time: {summary['average_response_time']:.2f}s")
        print(f"   Total Test Time: {summary['total_time']:.1f}s")

        print(f"\n📚 Document Analysis ({summary['documents_tested']} documents):")
        for doc, analysis in summary["document_analysis"].items():
            status = "✅" if analysis["success_rate"] >= 0.9 else "⚠️" if analysis["success_rate"] >= 0.7 else "❌"
            print(f"   {status} {doc}")
            print(
                f"      Success: {analysis['passed_questions']}/{analysis['total_questions']} ({analysis['success_rate']*100:.1f}%)"
            )
            print(f"      Avg Confidence: {analysis['avg_confidence']*100:.1f}%")


if __name__ == "__main__":
    tester = ComprehensiveRAGTester()
    summary = tester.run_comprehensive_test()
