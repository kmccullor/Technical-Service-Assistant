"""
Chain-of-Thought Reasoning Implementation

Implements multi-step reasoning with query decomposition, evidence gathering,
and step-by-step analysis for the Technical Service Assistant.
"""

import logging
import re
import time
from typing import Any, Dict, List

from reasoning_types import (
    ChainOfThoughtRequest,
    ComplexityLevel,
    ReasoningResponse,
    ReasoningStep,
    ReasoningType,
    classify_reasoning_type,
    estimate_complexity,
)

from config import get_model_num_ctx

logger = logging.getLogger(__name__)


class ChainOfThoughtReasoner:
    """Chain-of-thought reasoning engine for complex multi-step analysis."""

    def __init__(self, search_client, ollama_client, settings):
        """Initialize the reasoning engine with required clients."""
        self.search_client = search_client
        self.ollama_client = ollama_client
        self.settings = settings

    async def reason_through_query(self, request: ChainOfThoughtRequest) -> ReasoningResponse:
        """
        Main reasoning pipeline: decompose → gather evidence → analyze → synthesize.
        """
        start_time = time.time()

        # Step 1: Classify reasoning type and complexity
        reasoning_type = classify_reasoning_type(request.query)
        complexity = estimate_complexity(request.query)

        logger.info(f"Starting reasoning: type={reasoning_type}, complexity={complexity}")

        # Step 2: Decompose complex query into sub-questions
        sub_queries = []
        if request.decompose_query and complexity in [ComplexityLevel.COMPLEX, ComplexityLevel.EXPERT]:
            sub_queries = await self._decompose_query(request.query, reasoning_type)
        else:
            sub_queries = [request.query]

        # Step 3: Gather evidence for each sub-query
        evidence_steps = []
        for i, sub_query in enumerate(sub_queries):
            evidence = await self._gather_evidence(sub_query, min_sources=request.min_evidence_sources)

            step = ReasoningStep(
                step_number=i + 1,
                description=f"Evidence for: {sub_query}",
                evidence=evidence["chunks"],
                reasoning=f"Gathered {len(evidence['chunks'])} relevant sources",
                confidence=evidence["confidence"],
                sources=evidence["sources"],
            )
            evidence_steps.append(step)

        # Step 4: Perform step-by-step reasoning
        reasoning_steps = await self._perform_reasoning_steps(
            request.query, evidence_steps, reasoning_type, max_depth=request.max_reasoning_depth
        )

        # Step 5: Synthesize final answer
        final_answer = await self._synthesize_final_answer(request.query, reasoning_steps, reasoning_type)

        # Calculate metrics
        reasoning_time = int((time.time() - start_time) * 1000)
        all_sources = list(set(sum([step.sources for step in reasoning_steps], [])))
        avg_confidence = sum(step.confidence for step in reasoning_steps) / len(reasoning_steps)

        return ReasoningResponse(
            original_query=request.query,
            reasoning_type=reasoning_type,
            complexity=complexity,
            steps=[
                {
                    "step_number": step.step_number,
                    "description": step.description,
                    "evidence": step.evidence,
                    "reasoning": step.reasoning,
                    "confidence": step.confidence,
                    "sources": step.sources,
                }
                for step in reasoning_steps
            ],
            final_answer=final_answer,
            confidence_score=avg_confidence,
            sources_used=all_sources,
            reasoning_time_ms=reasoning_time,
            model_used="reasoning-orchestrator",
            instance_used="primary",
        )

    async def _decompose_query(self, query: str, reasoning_type: ReasoningType) -> List[str]:
        """Decompose complex query into manageable sub-questions."""

        decomposition_prompt = f"""
        Break down this complex question into 3-5 simpler sub-questions that need to be answered to fully address the main question.

        Question: {query}
        Reasoning Type: {reasoning_type}

        Provide only the sub-questions, one per line, numbered:
        1. [sub-question]
        2. [sub-question]
        etc.
        """

        try:
            model_name = "mistral:7B"  # Good for analytical tasks
            options = {"temperature": 0.3, "num_predict": 200}
            num_ctx = get_model_num_ctx(model_name)
            if num_ctx:
                options["num_ctx"] = num_ctx

            response = await self.ollama_client.generate(
                model=model_name,  # Good for analytical tasks
                prompt=decomposition_prompt,
                options=options,
            )

            # Parse numbered sub-questions
            lines = response["response"].strip().split("\n")
            sub_queries = []

            for line in lines:
                line = line.strip()
                if re.match(r"^\d+\.", line):
                    sub_question = re.sub(r"^\d+\.\s*", "", line)
                    if sub_question:
                        sub_queries.append(sub_question)

            logger.info(f"Decomposed query into {len(sub_queries)} sub-questions")
            return sub_queries[:5]  # Limit to 5 sub-questions

        except Exception as e:
            logger.error(f"Query decomposition failed: {e}")
            return [query]  # Fallback to original query

    async def _gather_evidence(self, query: str, min_sources: int = 3) -> Dict[str, Any]:
        """Gather relevant evidence from the knowledge base."""

        try:
            # Use the search client to get relevant chunks
            search_results = await self.search_client.search(
                query=query, top_k=min_sources * 2  # Get more than needed for filtering
            )

            if not search_results:
                return {"chunks": ["No relevant information found in knowledge base"], "sources": [], "confidence": 0.1}

            # Filter and rank evidence
            evidence_chunks = []
            sources = []
            confidence_scores = []

            for result in search_results[:min_sources]:
                if hasattr(result, "text") and hasattr(result, "metadata"):
                    evidence_chunks.append(result.text)
                    source = result.metadata.get("document_name", "Unknown source")
                    sources.append(source)
                    confidence_scores.append(getattr(result, "similarity", 0.5))

            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5

            return {"chunks": evidence_chunks, "sources": sources, "confidence": avg_confidence}

        except Exception as e:
            logger.error(f"Evidence gathering failed: {e}")
            return {"chunks": ["Evidence gathering failed due to search error"], "sources": [], "confidence": 0.1}

    async def _perform_reasoning_steps(
        self,
        original_query: str,
        evidence_steps: List[ReasoningStep],
        reasoning_type: ReasoningType,
        max_depth: int = 5,
    ) -> List[ReasoningStep]:
        """Perform step-by-step reasoning analysis."""

        reasoning_steps = []

        for i, evidence_step in enumerate(evidence_steps):
            # Create reasoning prompt based on type
            reasoning_prompt = self._create_reasoning_prompt(
                original_query, evidence_step.evidence, reasoning_type, step_number=i + 1
            )

            try:
                # Select appropriate model for reasoning type
                model = self._select_reasoning_model(reasoning_type)

                options = {"temperature": 0.2, "num_predict": 300}
                num_ctx = get_model_num_ctx(model)
                if num_ctx:
                    options["num_ctx"] = num_ctx

                response = await self.ollama_client.generate(model=model, prompt=reasoning_prompt, options=options)

                reasoning_text = response["response"].strip()

                # Create reasoning step
                step = ReasoningStep(
                    step_number=len(reasoning_steps) + 1,
                    description=f"Reasoning step {len(reasoning_steps) + 1}: {evidence_step.description}",
                    evidence=evidence_step.evidence,
                    reasoning=reasoning_text,
                    confidence=evidence_step.confidence * 0.9,  # Slight confidence reduction for reasoning
                    sources=evidence_step.sources,
                )

                reasoning_steps.append(step)

            except Exception as e:
                logger.error(f"Reasoning step {i+1} failed: {e}")
                # Add fallback step
                step = ReasoningStep(
                    step_number=len(reasoning_steps) + 1,
                    description=f"Reasoning step {len(reasoning_steps) + 1}: Analysis failed",
                    evidence=evidence_step.evidence,
                    reasoning="Unable to complete reasoning analysis due to error",
                    confidence=0.2,
                    sources=evidence_step.sources,
                )
                reasoning_steps.append(step)

        return reasoning_steps

    def _create_reasoning_prompt(
        self, query: str, evidence: List[str], reasoning_type: ReasoningType, step_number: int
    ) -> str:
        """Create reasoning prompt based on reasoning type."""

        evidence_text = "\n".join([f"Evidence {i+1}: {chunk}" for i, chunk in enumerate(evidence)])

        base_prompt = f"""
        Original Question: {query}

        Evidence Available:
        {evidence_text}

        Reasoning Task: {reasoning_type.value.title()} Analysis - Step {step_number}
        """

        if reasoning_type == ReasoningType.ANALYTICAL:
            return (
                base_prompt
                + """
            Analyze the evidence systematically. Break down the key components and examine how they relate to the question. Identify patterns, relationships, and important details.

            Provide your analysis:
            """
            )

        elif reasoning_type == ReasoningType.COMPARATIVE:
            return (
                base_prompt
                + """
            Compare and contrast the different elements in the evidence. Identify similarities, differences, advantages, and disadvantages. Draw comparisons that help answer the question.

            Provide your comparative analysis:
            """
            )

        elif reasoning_type == ReasoningType.CAUSAL:
            return (
                base_prompt
                + """
            Identify cause-and-effect relationships in the evidence. Explain what leads to what, why things happen, and what the consequences are. Trace causal chains.

            Provide your causal analysis:
            """
            )

        elif reasoning_type == ReasoningType.PROCEDURAL:
            return (
                base_prompt
                + """
            Extract and organize procedural information. Identify steps, sequences, methods, and processes. Create a logical flow of actions or procedures.

            Provide your procedural analysis:
            """
            )

        else:  # Default analytical approach
            return (
                base_prompt
                + """
            Analyze the evidence logically and systematically. Draw reasonable conclusions based on the available information. Explain your reasoning clearly.

            Provide your analysis:
            """
            )

    def _select_reasoning_model(self, reasoning_type: ReasoningType) -> str:
        """Select the most appropriate model for the reasoning type."""

        if reasoning_type in [ReasoningType.ANALYTICAL, ReasoningType.INFERENTIAL]:
            return "DeepSeek-R1:8B"  # Best for analytical reasoning
        elif reasoning_type == ReasoningType.PROCEDURAL:
            return "mistral:7B"  # Good for step-by-step instructions
        elif reasoning_type == ReasoningType.COMPARATIVE:
            return "athene-v2:72b"  # Good for nuanced comparisons
        else:
            return "mistral:7B"  # Default reliable choice

    async def _synthesize_final_answer(
        self, original_query: str, reasoning_steps: List[ReasoningStep], reasoning_type: ReasoningType
    ) -> str:
        """Synthesize final answer from reasoning steps."""

        # Combine all reasoning from steps
        all_reasoning = "\n\n".join([f"Step {step.step_number}: {step.reasoning}" for step in reasoning_steps])

        synthesis_prompt = f"""
        Original Question: {original_query}

        Reasoning Analysis:
        {all_reasoning}

        Based on the step-by-step reasoning above, provide a clear, comprehensive final answer to the original question. Synthesize the insights from all reasoning steps into a coherent response.

        Final Answer:
        """

        try:
            model_name = "mistral:7B"  # Good for synthesis
            options = {"temperature": 0.1, "num_predict": 400}
            num_ctx = get_model_num_ctx(model_name)
            if num_ctx:
                options["num_ctx"] = num_ctx

            response = await self.ollama_client.generate(
                model=model_name,
                prompt=synthesis_prompt,
                options=options,
            )

            return response["response"].strip()

        except Exception as e:
            logger.error(f"Final synthesis failed: {e}")
            return "Unable to synthesize final answer due to processing error."


# Utility functions for integration
async def create_reasoning_engine(search_client, ollama_client, settings):
    """Factory function to create a reasoning engine instance."""
    return ChainOfThoughtReasoner(search_client, ollama_client, settings)


def is_complex_reasoning_query(query: str) -> bool:
    """Determine if a query requires complex reasoning."""
    complexity = estimate_complexity(query)
    reasoning_type = classify_reasoning_type(query)

    # Require complex reasoning for certain types and complexity levels
    complex_types = [ReasoningType.ANALYTICAL, ReasoningType.SYNTHESIS, ReasoningType.EVALUATIVE]
    complex_levels = [ComplexityLevel.COMPLEX, ComplexityLevel.EXPERT]

    return reasoning_type in complex_types or complexity in complex_levels
