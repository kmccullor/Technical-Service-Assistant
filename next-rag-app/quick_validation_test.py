#!/usr/bin/env python3
"""
Quick RAG Validation Test - Test 5 questions per document for key documents
"""

import json
import time
from datetime import datetime

import requests


def test_quick_validation():
    api_url = "http://localhost:3015/api/chat"

    # Key documents and targeted questions
    test_cases = {
        "RNI 4.14 Installation Guide.pdf": [
            "What are the system requirements for installing RNI 4.14?",
            "What ports need to be configured for RNI 4.14?",
            "How do you verify the RNI 4.14 installation was successful?",
            "What are the prerequisites for RNI 4.14 installation?",
            "How do you troubleshoot RNI 4.14 installation issues?",
        ],
        "RNI 4.15 Device Manager Electric User Guide.pdf": [
            "How do you access the Device Manager Electric interface?",
            "What are the main features of Device Manager Electric?",
            "How do you add a new electric device in Device Manager?",
            "How do you configure Device Manager Electric settings?",
            "What reports are available in Device Manager Electric?",
        ],
        "RNI 4.14 Hardware Security Module Installation Guide.pdf": [
            "What is the purpose of the Hardware Security Module in RNI 4.14?",
            "How do you install the Hardware Security Module?",
            "What are the security requirements for the Hardware Security Module?",
            "How do you configure the Hardware Security Module?",
            "What troubleshooting steps exist for the Hardware Security Module?",
        ],
        "RNI 4.16.1 Release Notes.pdf": [
            "What are the new features in RNI 4.16.1?",
            "What bugs were fixed in RNI 4.16.1?",
            "What are the known issues in RNI 4.16.1?",
            "What are the upgrade instructions for RNI 4.16.1?",
            "What security updates are included in RNI 4.16.1?",
        ],
    }

    print("🚀 Quick RAG Validation with Reranking Enabled")
    print("=" * 60)

    all_results = []

    for document, questions in test_cases.items():
        print(f"\n📚 Testing: {document}")
        print("-" * 60)

        doc_results = []

        for i, question in enumerate(questions, 1):
            print(f"\n❓ Q{i}: {question}")

            start_time = time.time()

            try:
                payload = {"messages": [{"role": "user", "content": question}]}
                response = requests.post(api_url, json=payload, timeout=30)
                response_time = time.time() - start_time

                if response.status_code == 200:
                    # Parse streaming response
                    answer_tokens = []
                    confidence = None
                    sources_count = 0

                    lines = response.text.strip().split("\n")
                    for line in lines:
                        if line.startswith("data: "):
                            try:
                                parsed = json.loads(line[6:])
                                if parsed.get("type") == "token":
                                    answer_tokens.append(parsed.get("token", ""))
                                elif parsed.get("type") == "sources":
                                    confidence = parsed.get("confidence")
                                    sources_count = len(parsed.get("sources", []))
                            except (ValueError, KeyError, TypeError):
                                # Skip malformed responses
                                continue

                    answer = "".join(answer_tokens)
                    conf_pct = confidence * 100 if confidence else 0

                    # Determine success
                    success = conf_pct >= 95 and len(answer) > 30 and sources_count > 0
                    status = "✅ SUCCESS" if success else "⚠️ PARTIAL" if conf_pct >= 85 else "❌ FAILED"

                    print(f"   {status}")
                    print(f"   🎯 Confidence: {conf_pct:.1f}%")
                    print(f"   📚 Sources: {sources_count}")
                    print(f"   ⏱️ Time: {response_time:.2f}s")
                    print(f"   📝 Answer: {answer[:150]}{'...' if len(answer) > 150 else ''}")

                    doc_results.append(
                        {
                            "question": question,
                            "confidence": conf_pct,
                            "sources": sources_count,
                            "answer_length": len(answer),
                            "success": success,
                            "response_time": response_time,
                        }
                    )

                else:
                    print(f"   ❌ API Error: {response.status_code}")
                    doc_results.append(
                        {
                            "question": question,
                            "confidence": 0,
                            "sources": 0,
                            "success": False,
                            "response_time": response_time,
                        }
                    )

            except Exception as e:
                print(f"   ❌ Exception: {str(e)}")
                doc_results.append(
                    {"question": question, "confidence": 0, "sources": 0, "success": False, "response_time": 0}
                )

            time.sleep(2)  # Brief pause between requests

        # Document summary
        doc_success = sum(1 for r in doc_results if r["success"])
        doc_avg_conf = sum(r["confidence"] for r in doc_results) / len(doc_results) if doc_results else 0
        doc_avg_time = sum(r["response_time"] for r in doc_results) / len(doc_results) if doc_results else 0

        print(f"\n📊 {document} Results:")
        print(f"   Success Rate: {doc_success}/{len(questions)} ({doc_success/len(questions)*100:.1f}%)")
        print(f"   Avg Confidence: {doc_avg_conf:.1f}%")
        print(f"   Avg Response Time: {doc_avg_time:.2f}s")

        all_results.extend(doc_results)

    # Overall summary
    total_success = sum(1 for r in all_results if r["success"])
    total_tests = len(all_results)
    overall_conf = sum(r["confidence"] for r in all_results) / len(all_results) if all_results else 0
    high_conf_count = sum(1 for r in all_results if r["confidence"] >= 95)

    print(f"\n🎯 OVERALL SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {total_tests}")
    print(f"Successful: {total_success} ({total_success/total_tests*100:.1f}%)")
    print(f"Average Confidence: {overall_conf:.1f}%")
    print(f"High Confidence (≥95%): {high_conf_count} ({high_conf_count/total_tests*100:.1f}%)")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"quick_validation_{timestamp}.json"

    with open(results_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_tests": total_tests,
                    "successful_tests": total_success,
                    "success_rate": total_success / total_tests,
                    "average_confidence": overall_conf,
                    "high_confidence_tests": high_conf_count,
                },
                "results": all_results,
            },
            f,
            indent=2,
        )

    print(f"\n💾 Results saved to: {results_file}")

    return overall_conf >= 90  # Return True if average confidence >= 90%


if __name__ == "__main__":
    success = test_quick_validation()
