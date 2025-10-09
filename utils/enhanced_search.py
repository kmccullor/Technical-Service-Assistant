"""
Enhanced Hybrid Search Pipeline with Advanced Query Optimization.
Leverages specialized model routing and adaptive confidence thresholds.
"""

import re
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class QueryComplexity(str, Enum):
    """Query complexity levels for adaptive threshold adjustment."""
    SIMPLE = "simple"        # Basic factual questions
    MODERATE = "moderate"    # Multi-part or analytical questions  
    COMPLEX = "complex"      # Technical/reasoning questions requiring deep analysis
    CREATIVE = "creative"    # Open-ended creative tasks

class SearchStrategy(str, Enum):
    """Search strategy options based on query analysis."""
    RAG_ONLY = "rag_only"           # High confidence in document coverage
    WEB_PREFERRED = "web_preferred"  # Query likely needs current info
    HYBRID_BALANCED = "hybrid_balanced"  # Balanced approach
    FUSION = "fusion"                # Combine multiple approaches

@dataclass
class QueryAnalysis:
    """Comprehensive query analysis results."""
    complexity: QueryComplexity
    question_type: str  # From existing QuestionType enum
    domain_keywords: List[str]
    temporal_indicators: List[str]
    certainty_requirements: float  # 0-1 scale
    optimal_model: str
    optimal_instance: str
    confidence_threshold: float
    search_strategy: SearchStrategy
    rerank_priority: float  # Higher = more aggressive reranking

class EnhancedHybridSearch:
    """Enhanced hybrid search with adaptive optimization."""
    
    def __init__(self):
        # Domain-specific keyword mappings
        self.domain_keywords = {
            'technical': ['configure', 'setup', 'install', 'deploy', 'network', 'server', 'system'],
            'programming': ['code', 'function', 'algorithm', 'programming', 'debug', 'syntax'],
            'mathematical': ['calculate', 'solve', 'equation', 'formula', 'proof', 'derivative'],
            'current_events': ['latest', 'recent', 'current', 'news', 'today', '2025', 'now'],
            'creative': ['write', 'create', 'design', 'imagine', 'brainstorm', 'generate']
        }
        
        # Temporal indicators suggesting need for current information
        self.temporal_indicators = [
            'latest', 'recent', 'current', 'now', 'today', 'this year', '2025',
            'newest', 'updated', 'breaking', 'trending', 'just released'
        ]
        
        # Confidence adjustment factors per question type
        self.type_confidence_factors = {
            'code': {'base': 0.7, 'doc_bonus': 0.2, 'uncertainty_penalty': 0.4},
            'technical': {'base': 0.6, 'doc_bonus': 0.25, 'uncertainty_penalty': 0.3},  
            'math': {'base': 0.8, 'doc_bonus': 0.15, 'uncertainty_penalty': 0.5},
            'factual': {'base': 0.5, 'doc_bonus': 0.3, 'uncertainty_penalty': 0.2},
            'creative': {'base': 0.4, 'doc_bonus': 0.1, 'uncertainty_penalty': 0.1},
            'chat': {'base': 0.6, 'doc_bonus': 0.2, 'uncertainty_penalty': 0.2}
        }
    
    def analyze_query(self, query: str, base_threshold: float = 0.5) -> QueryAnalysis:
        """Perform comprehensive query analysis for optimization."""
        query_lower = query.lower()
        
        # Determine complexity
        complexity = self._assess_complexity(query)
        
        # Classify question type (reuse existing logic)
        question_type = self._classify_question_type(query)
        
        # Extract domain keywords
        domain_keywords = self._extract_domain_keywords(query_lower)
        
        # Find temporal indicators
        temporal_indicators = [indicator for indicator in self.temporal_indicators 
                             if indicator in query_lower]
        
        # Assess certainty requirements
        certainty_requirements = self._assess_certainty_requirements(query_lower)
        
        # Select optimal model and instance using existing specialization
        optimal_model, instance_index = self._select_specialized_model(question_type)
        optimal_instance = f"ollama-server-{instance_index + 1}"
        
        # Calculate adaptive confidence threshold
        confidence_threshold = self._calculate_adaptive_threshold(
            complexity, question_type, temporal_indicators, base_threshold
        )
        
        # Determine search strategy
        search_strategy = self._determine_search_strategy(
            complexity, temporal_indicators, domain_keywords
        )
        
        # Calculate reranking priority
        rerank_priority = self._calculate_rerank_priority(complexity, question_type)
        
        return QueryAnalysis(
            complexity=complexity,
            question_type=question_type,
            domain_keywords=domain_keywords,
            temporal_indicators=temporal_indicators,
            certainty_requirements=certainty_requirements,
            optimal_model=optimal_model,
            optimal_instance=optimal_instance,
            confidence_threshold=confidence_threshold,
            search_strategy=search_strategy,
            rerank_priority=rerank_priority
        )
    
    def _assess_complexity(self, query: str) -> QueryComplexity:
        """Assess query complexity based on linguistic features."""
        # Count question words, technical terms, conjunctions
        complexity_indicators = {
            'multi_part': len(re.findall(r'\band\b|\bor\b|\bbut\b', query.lower())),
            'question_words': len(re.findall(r'\bwho\b|\bwhat\b|\bwhen\b|\bwhere\b|\bwhy\b|\bhow\b', query.lower())),
            'technical_terms': len([word for word in query.split() if len(word) > 8]),
            'word_count': len(query.split()),
            'nested_concepts': query.count('(') + query.count('[')
        }
        
        complexity_score = (
            complexity_indicators['multi_part'] * 2 +
            complexity_indicators['question_words'] * 1.5 +
            complexity_indicators['technical_terms'] * 0.5 +
            min(complexity_indicators['word_count'] / 20, 2) +
            complexity_indicators['nested_concepts'] * 1.5
        )
        
        # Creative indicators
        creative_words = ['write', 'create', 'design', 'imagine', 'brainstorm']
        if any(word in query.lower() for word in creative_words):
            return QueryComplexity.CREATIVE
        
        if complexity_score >= 4:
            return QueryComplexity.COMPLEX
        elif complexity_score >= 2:
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.SIMPLE
    
    def _classify_question_type(self, query: str) -> str:
        """Classify question type (reuses existing classification logic)."""
        query_lower = query.lower()
        
        # Technical/system configuration keywords
        if any(term in query_lower for term in [
            'install', 'config', 'setup', 'active directory', 'server', 'network', 'deployment'
        ]):
            return 'technical'
        
        # Programming/code keywords
        if any(term in query_lower for term in [
            'code', 'function', 'algorithm', 'programming', 'python', 'javascript'
        ]):
            return 'code'
        
        # Math/calculation keywords
        if any(term in query_lower for term in [
            'calculate', 'solve', 'derivative', 'integral', 'equation', 'math'
        ]):
            return 'math'
        
        # Creative keywords
        if any(term in query_lower for term in [
            'write', 'create', 'design', 'story', 'poem'
        ]):
            return 'creative'
        
        # Chat/conversational
        if any(term in query_lower for term in [
            'hello', 'hi', 'how are you', 'good morning'
        ]):
            return 'chat'
        
        return 'factual'  # Default
    
    def _extract_domain_keywords(self, query_lower: str) -> List[str]:
        """Extract domain-specific keywords from query."""
        found_keywords = []
        for domain, keywords in self.domain_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    found_keywords.append(f"{domain}:{keyword}")
        return found_keywords
    
    def _assess_certainty_requirements(self, query_lower: str) -> float:
        """Assess how certain the answer needs to be (0-1 scale)."""
        # High certainty indicators
        high_certainty_words = ['exactly', 'precisely', 'accurate', 'correct', 'definitive']
        low_certainty_words = ['approximately', 'roughly', 'about', 'maybe', 'suggest']
        
        high_count = sum(1 for word in high_certainty_words if word in query_lower)
        low_count = sum(1 for word in low_certainty_words if word in query_lower)
        
        base_certainty = 0.6  # Default moderate certainty
        certainty_adjustment = (high_count * 0.2) - (low_count * 0.1)
        
        return max(0.1, min(1.0, base_certainty + certainty_adjustment))
    
    def _select_specialized_model(self, question_type: str) -> Tuple[str, int]:
        """Select specialized model using existing routing logic."""
        if question_type == 'code':
            return "phi3:mini", 1  # Instance 2
        elif question_type == 'technical':
            return "mistral:7b", 1  # Instance 2
        elif question_type == 'math':
            return "llama3.2:3b", 2  # Instance 3
        elif question_type == 'creative':
            return "llama3.1:8b", 2  # Instance 3
        elif question_type == 'factual':
            return "mistral:7b", 0  # Instance 1
        else:  # chat
            return "llama3.1:8b", 0  # Instance 1
    
    def _calculate_adaptive_threshold(self, complexity: QueryComplexity, 
                                    question_type: str, temporal_indicators: List[str], 
                                    base_threshold: float) -> float:
        """Calculate adaptive confidence threshold based on query analysis."""
        # Start with base threshold
        threshold = base_threshold
        
        # Complexity adjustments
        complexity_adjustments = {
            QueryComplexity.SIMPLE: -0.1,     # Lower threshold for simple questions
            QueryComplexity.MODERATE: 0.0,    # No adjustment
            QueryComplexity.COMPLEX: 0.15,    # Higher threshold for complex questions
            QueryComplexity.CREATIVE: -0.05   # Slightly lower for creative tasks
        }
        threshold += complexity_adjustments.get(complexity, 0.0)
        
        # Question type adjustments
        type_adjustments = {
            'code': 0.1,        # Higher threshold for code (needs accuracy)
            'technical': 0.05,  # Slightly higher for technical
            'math': 0.15,       # Highest for math (precision critical)
            'factual': 0.0,     # No adjustment
            'creative': -0.1,   # Lower threshold (more subjective)
            'chat': -0.05       # Slightly lower for conversational
        }
        threshold += type_adjustments.get(question_type, 0.0)
        
        # Temporal adjustment - if query asks for current info, lower threshold to allow web search
        if temporal_indicators:
            threshold -= 0.2  # Significant reduction to encourage web search
        
        # Ensure threshold stays within valid range
        return max(0.1, min(0.9, threshold))
    
    def _determine_search_strategy(self, complexity: QueryComplexity, 
                                 temporal_indicators: List[str], 
                                 domain_keywords: List[str]) -> SearchStrategy:
        """Determine optimal search strategy."""
        # Temporal queries prefer web search
        if temporal_indicators:
            return SearchStrategy.WEB_PREFERRED
        
        # Complex queries benefit from fusion
        if complexity == QueryComplexity.COMPLEX:
            return SearchStrategy.FUSION
        
        # Technical/programming queries likely have good doc coverage
        tech_domains = ['technical', 'programming']
        if any(domain.startswith(tech) for domain in domain_keywords for tech in tech_domains):
            return SearchStrategy.RAG_ONLY
        
        # Default balanced approach
        return SearchStrategy.HYBRID_BALANCED
    
    def _calculate_rerank_priority(self, complexity: QueryComplexity, question_type: str) -> float:
        """Calculate reranking priority (0-1 scale)."""
        base_priority = 0.5
        
        # Complex queries benefit more from reranking
        complexity_bonus = {
            QueryComplexity.SIMPLE: -0.1,
            QueryComplexity.MODERATE: 0.0,
            QueryComplexity.COMPLEX: 0.2,
            QueryComplexity.CREATIVE: 0.1
        }
        base_priority += complexity_bonus.get(complexity, 0.0)
        
        # Technical and code queries benefit significantly from reranking
        type_bonus = {
            'code': 0.3,
            'technical': 0.2,
            'math': 0.25,
            'factual': 0.1,
            'creative': 0.0,
            'chat': -0.1
        }
        base_priority += type_bonus.get(question_type, 0.0)
        
        return max(0.0, min(1.0, base_priority))

    def calculate_enhanced_confidence(self, query: str, context_chunks: List[str], 
                                    response: str, query_analysis: QueryAnalysis) -> float:
        """Enhanced confidence calculation using query analysis."""
        if not context_chunks:
            return 0.0
        
        question_type = query_analysis.question_type
        factors = self.type_confidence_factors.get(question_type, 
                                                  self.type_confidence_factors['factual'])
        
        # Base confidence adjusted by question type
        chunk_factor = min(len(context_chunks) / 8.0, factors['base'])
        
        # Enhanced uncertainty detection
        uncertain_phrases = [
            "i don't know", "not sure", "cannot", "unable", "no information",
            "unclear", "apologize", "does not contain", "not available",
            "insufficient", "limited information", "may not be accurate"
        ]
        
        response_lower = response.lower()
        uncertainty_count = sum(1 for phrase in uncertain_phrases if phrase in response_lower)
        uncertainty_penalty = uncertainty_count * factors['uncertainty_penalty']
        
        # Content quality assessment
        response_length = len(response)
        quality_indicators = {
            'detailed': response_length > 500,
            'structured': response.count('\n') > 2 or response.count('•') > 1,
            'specific': len(re.findall(r'\b\d+\b', response)) > 0,  # Contains numbers
            'authoritative': any(word in response_lower for word in 
                               ['according to', 'research shows', 'studies indicate'])
        }
        
        quality_bonus = sum(0.05 for indicator, present in quality_indicators.items() if present)
        
        # Semantic relevance (enhanced)
        query_terms = set(query.lower().split())
        context_text = " ".join(context_chunks).lower()
        
        # Calculate different types of relevance
        exact_matches = len([term for term in query_terms if term in context_text])
        partial_matches = len([term for term in query_terms 
                             if any(term in chunk_word for chunk_word in context_text.split())])
        
        relevance_score = (exact_matches * 0.3 + partial_matches * 0.1) / max(len(query_terms), 1)
        relevance_bonus = relevance_score * factors['doc_bonus']
        
        # Domain expertise bonus
        domain_expertise_bonus = 0.0
        if query_analysis.domain_keywords:
            # If we found domain-specific keywords, boost confidence if context seems relevant
            domain_terms_in_context = sum(1 for keyword in query_analysis.domain_keywords 
                                        if keyword.split(':')[1] in context_text)
            if domain_terms_in_context > 0:
                domain_expertise_bonus = 0.1
        
        # Certainty requirement adjustment
        certainty_adjustment = (query_analysis.certainty_requirements - 0.5) * 0.1
        
        # Calculate final confidence
        confidence = (chunk_factor + quality_bonus + relevance_bonus + 
                     domain_expertise_bonus + certainty_adjustment - uncertainty_penalty)
        
        return max(0.0, min(1.0, confidence))

# Global instance
enhanced_search = EnhancedHybridSearch()