"""
Reasoning Types and Classifications

Defines the types of reasoning tasks and their characteristics for the
Technical Service Assistant reasoning engine.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReasoningType(str, Enum):
    """Types of reasoning supported by the engine."""

    ANALYTICAL = "analytical"  # Step-by-step analysis with evidence
    COMPARATIVE = "comparative"  # Comparing multiple concepts/solutions
    CAUSAL = "causal"  # Cause-and-effect relationships
    INFERENTIAL = "inferential"  # Drawing conclusions from premises
    PROCEDURAL = "procedural"  # Step-by-step instructions/processes
    SYNTHESIS = "synthesis"  # Combining multiple information sources
    EVALUATIVE = "evaluative"  # Assessment and judgment tasks


class ComplexityLevel(str, Enum):
    """Complexity levels for reasoning tasks."""

    SIMPLE = "simple"  # Single-step, direct answers
    MEDIUM = "medium"  # Multi-step but straightforward
    COMPLEX = "complex"  # Requires deep analysis and synthesis
    EXPERT = "expert"  # Domain expertise and advanced reasoning


@dataclass
class ReasoningStep:
    """Individual step in a reasoning chain."""

    step_number: int
    description: str
    evidence: List[str]
    reasoning: str
    confidence: float
    sources: List[str]


class ReasoningQuery(BaseModel):
    """Input query for reasoning engine."""

    query: str = Field(..., description="Original user question")
    reasoning_type: Optional[ReasoningType] = Field(None, description="Specified reasoning type")
    complexity: Optional[ComplexityLevel] = Field(None, description="Expected complexity level")
    max_steps: int = Field(5, description="Maximum reasoning steps")
    require_sources: bool = Field(True, description="Require source attribution")
    context_window: int = Field(32768, description="Maximum context tokens")


class ReasoningResponse(BaseModel):
    """Output from reasoning engine."""

    model_config = ConfigDict(protected_namespaces=())

    original_query: str
    reasoning_type: ReasoningType
    complexity: ComplexityLevel
    steps: List[Dict[str, Any]]  # ReasoningStep data
    final_answer: str
    confidence_score: float
    sources_used: List[str]
    reasoning_time_ms: int
    model_used: str
    instance_used: str


class ChainOfThoughtRequest(BaseModel):
    """Request for chain-of-thought reasoning."""

    query: str
    decompose_query: bool = Field(True, description="Break down complex queries")
    gather_evidence: bool = Field(True, description="Collect supporting evidence")
    synthesize_answer: bool = Field(True, description="Generate final synthesis")
    min_evidence_sources: int = Field(3, description="Minimum evidence sources")
    max_reasoning_depth: int = Field(5, description="Maximum reasoning chain depth")


def classify_reasoning_type(query: str) -> ReasoningType:
    """Classify the type of reasoning required for a query."""
    query_lower = query.lower()

    # Analytical reasoning keywords
    if any(term in query_lower for term in ["analyze", "examine", "investigate", "study", "breakdown"]):
        return ReasoningType.ANALYTICAL

    # Comparative reasoning keywords
    elif any(term in query_lower for term in ["compare", "contrast", "difference", "versus", "vs", "better"]):
        return ReasoningType.COMPARATIVE

    # Causal reasoning keywords
    elif any(term in query_lower for term in ["why", "because", "cause", "effect", "reason", "result"]):
        return ReasoningType.CAUSAL

    # Procedural reasoning keywords
    elif any(term in query_lower for term in ["how to", "steps", "process", "procedure", "method", "guide"]):
        return ReasoningType.PROCEDURAL

    # Synthesis reasoning keywords
    elif any(term in query_lower for term in ["combine", "integrate", "synthesize", "merge", "overall"]):
        return ReasoningType.SYNTHESIS

    # Evaluative reasoning keywords
    elif any(term in query_lower for term in ["evaluate", "assess", "judge", "rate", "review", "best"]):
        return ReasoningType.EVALUATIVE

    # Default to inferential for other types
    else:
        return ReasoningType.INFERENTIAL


def estimate_complexity(query: str, context_length: int = 0) -> ComplexityLevel:
    """Estimate the complexity level of a reasoning task."""
    query_lower = query.lower()

    # Simple indicators
    simple_indicators = ["what is", "define", "list", "show me", "find"]
    if any(indicator in query_lower for indicator in simple_indicators):
        return ComplexityLevel.SIMPLE

    # Complex indicators
    complex_indicators = ["comprehensive", "detailed analysis", "in-depth", "thoroughly", "multiple factors"]
    if any(indicator in query_lower for indicator in complex_indicators):
        return ComplexityLevel.COMPLEX

    # Expert indicators
    expert_indicators = ["research", "academic", "peer review", "methodology", "framework"]
    if any(indicator in query_lower for indicator in expert_indicators):
        return ComplexityLevel.EXPERT

    # Base on context length and query complexity
    word_count = len(query.split())
    if word_count > 20 or context_length > 2000:
        return ComplexityLevel.COMPLEX
    elif word_count > 10 or context_length > 500:
        return ComplexityLevel.MEDIUM
    else:
        return ComplexityLevel.SIMPLE
