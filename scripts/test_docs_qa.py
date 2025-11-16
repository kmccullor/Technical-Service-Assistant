#!/usr/bin/env python3
"""
Test AI Assistant accuracy against documentation Q&A pairs.

Loads Q&A from docs_qa_test.json and tests responses from Ollama models.
Compares answers and calculates confidence scores.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import httpx

from utils.logging_config import configure_root_logging

configure_root_logging()
logger = logging.getLogger(__name__)


class DocsQATester:
    """Test AI responses against documentation Q&A pairs."""

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "reasoning-mistral"):
        self.ollama_url = ollama_url
        self.model = model

    async def load_qa_pairs(self, qa_file: str) -> List[Dict[str, Any]]:
        """Load Q&A pairs from JSON file."""
        with open(qa_file, "r") as f:
            data = json.load(f)

        qa_pairs = []
        for doc in data:
            for qa in doc["qa_pairs"]:
                qa_pairs.append(
                    {
                        "document": doc["document"],
                        "question": qa["question"],
                        "expected_answer": qa["answer"],
                        "confidence_required": qa.get("confidence_required", 100),
                    }
                )

        logger.info(f"Loaded {len(qa_pairs)} Q&A pairs from {len(data)} documents")
        return qa_pairs

    async def test_single_qa(self, qa_pair: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single Q&A pair."""
        question = qa_pair["question"]
        expected = qa_pair["expected_answer"]

        # Get AI response
        response = await self.get_ai_response(question)

        # Compare and score
        confidence = self.calculate_confidence(response, expected)

        return {
            "document": qa_pair["document"],
            "question": question,
            "expected_answer": expected,
            "ai_response": response,
            "confidence": confidence,
            "passed": confidence >= qa_pair["confidence_required"],
        }

    async def get_ai_response(self, question: str) -> str:
        """Get response from Ollama model using chat API with system prompt."""
        system_prompt = """You are an expert technical support specialist for RNI (Regional Network Interface) systems and Sensus products.

Your knowledge includes:

TECHNICAL EXPERTISE:
- RNI 4.16 platform architecture and configuration
- Sensus gas meters (R175, R200, RT200, RT230, R275, RT275, R315, R250 models)
- AMI (Advanced Metering Infrastructure) systems
- SmartPoint 100GM transceiver installation and configuration
- Utility communications protocols (MultiSpeak, CMEP)
- FlexNet communication systems
- PostgreSQL database administration for utility systems

KEY CAPABILITIES:
- Provide step-by-step installation and configuration guidance
- Troubleshoot technical issues with detailed diagnostic steps
- Explain complex technical concepts in clear, practical terms
- Reference specific documentation sections when relevant
- Suggest best practices for system maintenance and optimization

RESPONSE STYLE:
- Be precise and technically accurate
- Use clear, professional language
- Provide actionable solutions
- Include safety considerations when relevant
- Cite specific components, versions, and procedures

Always base your responses on technical documentation and established procedures."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": question},
                        ],
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 500},
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    message = data.get("message", {})
                    return message.get("content", "").strip()
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    return ""

        except Exception as e:
            logger.error(f"Error getting AI response: {e}")
            return ""

    def calculate_confidence(self, response: str, expected: str) -> float:
        """Calculate confidence score by comparing response to expected answer."""
        if not response:
            return 0.0

        # Simple text similarity (can be improved with better metrics)
        response_lower = response.lower()
        expected_lower = expected.lower()

        # Exact match
        if response_lower.strip() == expected_lower.strip():
            return 100.0

        # Contains key phrases
        expected_words = set(expected_lower.split())
        response_words = set(response_lower.split())

        if expected_words and response_words:
            overlap = len(expected_words.intersection(response_words))
            coverage = overlap / len(expected_words)
            return min(100.0, coverage * 100.0)

        return 0.0

    async def run_tests(self, qa_file: str) -> Dict[str, Any]:
        """Run all Q&A tests."""
        qa_pairs = await self.load_qa_pairs(qa_file)

        # Limit to first 5 for testing
        qa_pairs = qa_pairs[:5]

        results = []
        passed = 0
        total = len(qa_pairs)

        for i, qa in enumerate(qa_pairs):
            logger.info(f"Testing Q&A {i+1}/{total}: {qa['document']}")
            result = await self.test_single_qa(qa)
            results.append(result)

            if result["passed"]:
                passed += 1

        overall_confidence = (passed / total) * 100 if total > 0 else 0

        summary = {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "overall_confidence": overall_confidence,
            "results": results,
        }

        logger.info(f"Test complete: {passed}/{total} passed ({overall_confidence:.1f}% confidence)")
        return summary

    def save_results(self, results: Dict[str, Any], output_file: str):
        """Save test results to JSON file."""
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"Results saved to {output_file}")


async def main():
    """Main test runner."""
    tester = DocsQATester()

    qa_file = "archive_qa_test.json"
    results_file = "archive_qa_test_results.json"

    if not Path(qa_file).exists():
        logger.error(f"Q&A file {qa_file} not found")
        return

    results = await tester.run_tests(qa_file)
    tester.save_results(results, results_file)

    # Print summary
    logger.info(f"\nTest Summary:")
    logger.info(f"Total tests: {results['total_tests']}")
    logger.info(f"Passed: {results['passed']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Overall confidence: {results['overall_confidence']:.1f}%")

    if results["overall_confidence"] < 100:
        logger.info("\nFailed tests:")
        for result in results["results"]:
            if not result["passed"]:
                logger.info(f"- {result['document']}: {result['question'][:50]}... (confidence: {result['confidence']:.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
