"""
Reasoning Engine Module

Advanced reasoning capabilities for the Technical Service Assistant including:
- Chain-of-thought reasoning
- Knowledge synthesis and cross-document analysis
- Advanced context management with conversation memory
- Enhanced model orchestration with consensus capabilities
- Multi-step reasoning coordination
- Intelligent model orchestration
"""

__version__ = "0.4.0"

# Chain-of-thought reasoning
from .chain_of_thought import ChainOfThoughtReasoner, is_complex_reasoning_query

# Main orchestrator
from .orchestrator import ReasoningOrchestrator

# Core reasoning types and utilities
from .reasoning_types import (
    ChainOfThoughtRequest,
    ComplexityLevel,
    ReasoningQuery,
    ReasoningResponse,
    ReasoningStep,
    ReasoningType,
    classify_reasoning_type,
    estimate_complexity,
)

# Knowledge synthesis capabilities

# Advanced context management

# Enhanced model orchestration


__all__ = [
    # Types and enums
    "ReasoningType",
    "ComplexityLevel",
    "ReasoningStep",
    "ReasoningQuery",
    "ReasoningResponse",
    "ChainOfThoughtRequest",
    # Core functions
    "classify_reasoning_type",
    "estimate_complexity",
    "is_complex_reasoning_query",
    # Main components
    "ChainOfThoughtReasoner",
    "KnowledgeSynthesizer",
    "ReasoningOrchestrator",
    "AdvancedContextManager",
    "EnhancedModelOrchestrator",
    # Knowledge synthesis types
    "KnowledgeCluster",
    "CrossReferencePattern",
    "SynthesisResult",
    # Context management types
    "ConversationTurn",
    "ContextChunk",
    "ContextWindow",
    # Model orchestration types
    "ModelPerformanceMetrics",
    "ModelCapability",
    "ConsensusRequest",
    "ConsensusResult",
]

from .chain_of_thought import ChainOfThoughtReasoner, create_reasoning_engine, is_complex_reasoning_query
from .orchestrator import ReasoningOrchestrator, create_reasoning_orchestrator
from .reasoning_types import (
    ChainOfThoughtRequest,
    ComplexityLevel,
    ReasoningQuery,
    ReasoningResponse,
    ReasoningStep,
    ReasoningType,
    classify_reasoning_type,
    estimate_complexity,
)

__all__ = [
    "ReasoningType",
    "ComplexityLevel",
    "ReasoningStep",
    "ReasoningQuery",
    "ReasoningResponse",
    "ChainOfThoughtRequest",
    "ChainOfThoughtReasoner",
    "ReasoningOrchestrator",
    "classify_reasoning_type",
    "estimate_complexity",
    "create_reasoning_engine",
    "create_reasoning_orchestrator",
    "is_complex_reasoning_query",
]

# Version info
__version__ = "1.0.0"
__author__ = "Technical Service Assistant Team"
__description__ = "Advanced reasoning engine with chain-of-thought and knowledge synthesis"
