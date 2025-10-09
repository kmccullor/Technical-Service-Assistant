"""
Advanced Context Management

Sophisticated context management capabilities including conversation memory,
context window optimization, dynamic context selection, and contextual relevance scoring.
"""

import hashlib
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Represents a single turn in a conversation."""

    turn_id: str
    timestamp: float
    user_query: str
    assistant_response: str
    context_used: List[str]
    reasoning_type: str
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextChunk:
    """Represents a chunk of context with relevance scoring."""

    chunk_id: str
    text: str
    source: str
    relevance_score: float
    recency_score: float
    frequency_score: float
    combined_score: float
    last_accessed: float
    access_count: int
    token_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextWindow:
    """Represents the current context window with optimization metrics."""

    total_tokens: int
    max_tokens: int
    chunks: List[ContextChunk]
    conversation_history: List[ConversationTurn]
    optimization_strategy: str
    efficiency_score: float
    last_optimization: float


class AdvancedContextManager:
    """
    Advanced context management system for reasoning operations.

    Features:
    - Conversation memory with intelligent summarization
    - Dynamic context window optimization
    - Contextual relevance scoring with multiple factors
    - Adaptive context selection based on reasoning type
    - Memory consolidation and pruning
    - Cross-conversation knowledge retention
    """

    def __init__(self, max_memory_size: int = 1000, max_context_tokens: int = 4000):
        """Initialize advanced context manager."""
        self.max_memory_size = max_memory_size
        self.max_context_tokens = max_context_tokens

        # Conversation memory
        self.conversation_history: deque = deque(maxlen=max_memory_size)
        self.conversation_sessions: Dict[str, List[ConversationTurn]] = defaultdict(list)

        # Context management
        self.context_cache: Dict[str, ContextChunk] = {}
        self.context_frequency: Dict[str, int] = defaultdict(int)
        self.context_recency: Dict[str, float] = {}

        # Optimization settings
        self.relevance_weight = 0.4
        self.recency_weight = 0.3
        self.frequency_weight = 0.3
        self.decay_factor = 0.95

        # Performance tracking
        self.optimization_history: List[Dict[str, Any]] = []

        logger.info("Advanced context manager initialized")

    async def manage_context_for_reasoning(
        self,
        query: str,
        reasoning_type: str,
        available_contexts: List[Dict[str, Any]],
        session_id: str = "default",
        max_context_length: Optional[int] = None,
    ) -> ContextWindow:
        """
        Manage context for a reasoning operation.

        Args:
            query: Current user query
            reasoning_type: Type of reasoning being performed
            available_contexts: Available context chunks
            session_id: Conversation session identifier
            max_context_length: Override default context length

        Returns:
            Optimized context window for the reasoning operation
        """
        logger.info(f"Managing context for {reasoning_type} reasoning: {query[:100]}...")

        start_time = time.time()
        max_tokens = max_context_length or self.max_context_tokens

        try:
            # Step 1: Score and rank available contexts
            scored_contexts = await self._score_context_relevance(
                query=query, contexts=available_contexts, reasoning_type=reasoning_type, session_id=session_id
            )

            # Step 2: Retrieve relevant conversation history
            relevant_history = await self._get_relevant_conversation_history(
                query=query, session_id=session_id, max_turns=5
            )

            # Step 3: Optimize context window
            optimized_window = await self._optimize_context_window(
                query=query,
                scored_contexts=scored_contexts,
                conversation_history=relevant_history,
                max_tokens=max_tokens,
                reasoning_type=reasoning_type,
            )

            # Step 4: Update context usage statistics
            await self._update_context_usage(optimized_window.chunks, query)

            # Step 5: Calculate efficiency metrics
            efficiency_score = self._calculate_context_efficiency(optimized_window)
            optimized_window.efficiency_score = efficiency_score
            optimized_window.last_optimization = time.time()

            # Record optimization metrics
            optimization_time = time.time() - start_time
            self.optimization_history.append(
                {
                    "timestamp": time.time(),
                    "query": query[:100],
                    "reasoning_type": reasoning_type,
                    "contexts_available": len(available_contexts),
                    "contexts_selected": len(optimized_window.chunks),
                    "total_tokens": optimized_window.total_tokens,
                    "efficiency_score": efficiency_score,
                    "optimization_time_ms": int(optimization_time * 1000),
                }
            )

            logger.info(
                f"Context optimized: {len(optimized_window.chunks)} chunks, "
                f"{optimized_window.total_tokens} tokens, efficiency: {efficiency_score:.3f}"
            )

            return optimized_window

        except Exception as e:
            logger.error(f"Context management failed: {e}")
            # Return minimal context window on failure
            return ContextWindow(
                total_tokens=0,
                max_tokens=max_tokens,
                chunks=[],
                conversation_history=[],
                optimization_strategy="fallback",
                efficiency_score=0.0,
                last_optimization=time.time(),
            )

    async def store_conversation_turn(
        self,
        user_query: str,
        assistant_response: str,
        context_used: List[str],
        reasoning_type: str,
        confidence_score: float,
        session_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store a conversation turn for future context management."""

        turn_id = self._generate_turn_id(user_query, assistant_response)

        turn = ConversationTurn(
            turn_id=turn_id,
            timestamp=time.time(),
            user_query=user_query,
            assistant_response=assistant_response,
            context_used=context_used,
            reasoning_type=reasoning_type,
            confidence_score=confidence_score,
            metadata=metadata or {},
        )

        # Store in conversation history
        self.conversation_history.append(turn)
        self.conversation_sessions[session_id].append(turn)

        # Update context usage tracking
        for context in context_used:
            self.context_frequency[context] += 1
            self.context_recency[context] = time.time()

        logger.info(f"Stored conversation turn: {turn_id}")
        return turn_id

    async def get_conversation_summary(
        self, session_id: str, max_turns: int = 10, include_reasoning_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get a summary of the conversation for context."""

        session_turns = self.conversation_sessions.get(session_id, [])
        if not session_turns:
            return {
                "summary": "No conversation history",
                "total_turns": 0,
                "reasoning_types_used": [],
                "avg_confidence": 0.0,
                "key_topics": [],
            }

        # Filter by reasoning types if specified
        if include_reasoning_types:
            session_turns = [turn for turn in session_turns if turn.reasoning_type in include_reasoning_types]

        recent_turns = session_turns[-max_turns:]

        # Calculate statistics
        total_turns = len(recent_turns)
        reasoning_types = list(set(turn.reasoning_type for turn in recent_turns))
        avg_confidence = sum(turn.confidence_score for turn in recent_turns) / total_turns if total_turns > 0 else 0.0

        # Extract key topics (simplified - could use NLP)
        key_topics = await self._extract_conversation_topics(recent_turns)

        # Generate summary
        summary = await self._generate_conversation_summary(recent_turns)

        return {
            "summary": summary,
            "total_turns": total_turns,
            "reasoning_types_used": reasoning_types,
            "avg_confidence": avg_confidence,
            "key_topics": key_topics,
            "recent_queries": [turn.user_query for turn in recent_turns[-3:]],
        }

    async def _score_context_relevance(
        self, query: str, contexts: List[Dict[str, Any]], reasoning_type: str, session_id: str
    ) -> List[ContextChunk]:
        """Score context chunks for relevance to the current query."""

        scored_chunks = []
        current_time = time.time()

        for i, context in enumerate(contexts):
            chunk_id = f"{context.get('source', 'unknown')}_{i}"
            text = context.get("text", "")
            source = context.get("source", "unknown")

            # Calculate relevance score (simplified - could use embeddings)
            relevance_score = await self._calculate_semantic_relevance(query, text, reasoning_type)

            # Calculate recency score
            last_access = self.context_recency.get(chunk_id, 0)
            recency_score = self._calculate_recency_score(last_access, current_time)

            # Calculate frequency score
            access_count = self.context_frequency.get(chunk_id, 0)
            frequency_score = self._calculate_frequency_score(access_count)

            # Combined score
            combined_score = (
                self.relevance_weight * relevance_score
                + self.recency_weight * recency_score
                + self.frequency_weight * frequency_score
            )

            # Estimate token count (rough approximation)
            token_count = len(text.split()) * 1.3  # Rough token estimation

            chunk = ContextChunk(
                chunk_id=chunk_id,
                text=text,
                source=source,
                relevance_score=relevance_score,
                recency_score=recency_score,
                frequency_score=frequency_score,
                combined_score=combined_score,
                last_accessed=last_access,
                access_count=access_count,
                token_count=int(token_count),
                metadata=context.get("metadata", {}),
            )

            scored_chunks.append(chunk)

        # Sort by combined score
        scored_chunks.sort(key=lambda x: x.combined_score, reverse=True)
        return scored_chunks

    async def _get_relevant_conversation_history(
        self, query: str, session_id: str, max_turns: int
    ) -> List[ConversationTurn]:
        """Get relevant conversation history for context."""

        session_turns = self.conversation_sessions.get(session_id, [])
        if not session_turns:
            return []

        # Get recent turns and score them for relevance
        recent_turns = session_turns[-max_turns * 2 :]  # Get more to filter from

        scored_turns = []
        for turn in recent_turns:
            # Simple relevance scoring based on query similarity
            relevance = await self._calculate_conversation_relevance(query, turn)
            scored_turns.append((turn, relevance))

        # Sort by relevance and return top turns
        scored_turns.sort(key=lambda x: x[1], reverse=True)
        return [turn for turn, _ in scored_turns[:max_turns]]

    async def _optimize_context_window(
        self,
        query: str,
        scored_contexts: List[ContextChunk],
        conversation_history: List[ConversationTurn],
        max_tokens: int,
        reasoning_type: str,
    ) -> ContextWindow:
        """Optimize the context window for maximum efficiency."""

        selected_chunks = []
        total_tokens = 0

        # Reserve tokens for conversation history
        history_tokens = (
            sum(len(turn.user_query.split()) + len(turn.assistant_response.split()) for turn in conversation_history)
            * 1.3
        )  # Rough token estimation

        available_tokens = max_tokens - int(history_tokens)

        # Strategy selection based on reasoning type
        if reasoning_type in ["synthesis", "comprehensive"]:
            strategy = "diversity_focused"
        elif reasoning_type in ["chain_of_thought", "analytical"]:
            strategy = "depth_focused"
        else:
            strategy = "balanced"

        # Apply selection strategy
        if strategy == "diversity_focused":
            selected_chunks = await self._select_diverse_contexts(scored_contexts, available_tokens)
        elif strategy == "depth_focused":
            selected_chunks = await self._select_depth_focused_contexts(scored_contexts, available_tokens)
        else:
            selected_chunks = await self._select_balanced_contexts(scored_contexts, available_tokens)

        total_tokens = sum(chunk.token_count for chunk in selected_chunks) + int(history_tokens)

        return ContextWindow(
            total_tokens=total_tokens,
            max_tokens=max_tokens,
            chunks=selected_chunks,
            conversation_history=conversation_history,
            optimization_strategy=strategy,
            efficiency_score=0.0,  # Will be calculated later
            last_optimization=time.time(),
        )

    async def _select_diverse_contexts(
        self, scored_contexts: List[ContextChunk], available_tokens: int
    ) -> List[ContextChunk]:
        """Select contexts for maximum diversity."""
        selected = []
        used_sources = set()
        total_tokens = 0

        for chunk in scored_contexts:
            if total_tokens + chunk.token_count > available_tokens:
                break

            # Prefer diverse sources
            if chunk.source not in used_sources or len(used_sources) < 3:
                selected.append(chunk)
                used_sources.add(chunk.source)
                total_tokens += chunk.token_count

        return selected

    async def _select_depth_focused_contexts(
        self, scored_contexts: List[ContextChunk], available_tokens: int
    ) -> List[ContextChunk]:
        """Select contexts for maximum depth on top-scoring sources."""
        selected = []
        total_tokens = 0

        # Group by source and select top-scoring sources
        source_groups = defaultdict(list)
        for chunk in scored_contexts:
            source_groups[chunk.source].append(chunk)

        # Sort sources by their best chunk score
        sorted_sources = sorted(
            source_groups.keys(), key=lambda s: max(chunk.combined_score for chunk in source_groups[s]), reverse=True
        )

        # Select chunks from top sources
        for source in sorted_sources[:3]:  # Focus on top 3 sources
            for chunk in sorted(source_groups[source], key=lambda x: x.combined_score, reverse=True):
                if total_tokens + chunk.token_count > available_tokens:
                    break
                selected.append(chunk)
                total_tokens += chunk.token_count

        return selected

    async def _select_balanced_contexts(
        self, scored_contexts: List[ContextChunk], available_tokens: int
    ) -> List[ContextChunk]:
        """Select contexts with balanced approach."""
        selected = []
        total_tokens = 0

        # Simple greedy selection by combined score
        for chunk in scored_contexts:
            if total_tokens + chunk.token_count > available_tokens:
                break
            selected.append(chunk)
            total_tokens += chunk.token_count

        return selected

    async def _update_context_usage(self, chunks: List[ContextChunk], query: str):
        """Update context usage statistics."""
        current_time = time.time()

        for chunk in chunks:
            self.context_frequency[chunk.chunk_id] += 1
            self.context_recency[chunk.chunk_id] = current_time
            chunk.last_accessed = current_time
            chunk.access_count += 1

    def _calculate_context_efficiency(self, context_window: ContextWindow) -> float:
        """Calculate efficiency score for the context window."""
        if not context_window.chunks:
            return 0.0

        # Factors: token utilization, relevance, diversity
        token_utilization = context_window.total_tokens / context_window.max_tokens
        avg_relevance = sum(chunk.relevance_score for chunk in context_window.chunks) / len(context_window.chunks)
        source_diversity = len(set(chunk.source for chunk in context_window.chunks)) / len(context_window.chunks)

        efficiency = token_utilization * 0.3 + avg_relevance * 0.5 + source_diversity * 0.2
        return min(1.0, max(0.0, efficiency))

    async def _calculate_semantic_relevance(self, query: str, text: str, reasoning_type: str) -> float:
        """Calculate semantic relevance score (simplified implementation)."""
        # Simplified keyword-based relevance
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())

        if not query_words:
            return 0.0

        overlap = len(query_words.intersection(text_words))
        relevance = overlap / len(query_words)

        # Boost for reasoning-specific terms
        reasoning_terms = {
            "analysis": ["analyze", "analysis", "examine", "study"],
            "synthesis": ["synthesize", "combine", "integrate", "merge"],
            "comparison": ["compare", "contrast", "versus", "difference"],
        }

        for term_type, terms in reasoning_terms.items():
            if any(term in query.lower() for term in terms):
                if any(term in text.lower() for term in terms):
                    relevance *= 1.2

        return min(1.0, relevance)

    def _calculate_recency_score(self, last_access: float, current_time: float) -> float:
        """Calculate recency score with exponential decay."""
        if last_access == 0:
            return 0.0

        time_diff = current_time - last_access
        # Decay over time (half-life of 1 hour = 3600 seconds)
        decay = 0.5 ** (time_diff / 3600)
        return decay

    def _calculate_frequency_score(self, access_count: int) -> float:
        """Calculate frequency score with logarithmic scaling."""
        if access_count == 0:
            return 0.0

        # Logarithmic scaling to prevent frequency dominance
        import math

        return min(1.0, math.log(access_count + 1) / math.log(10))

    async def _calculate_conversation_relevance(self, query: str, turn: ConversationTurn) -> float:
        """Calculate relevance of a conversation turn to current query."""
        # Simple keyword overlap for now
        query_words = set(query.lower().split())
        turn_words = set((turn.user_query + " " + turn.assistant_response).lower().split())

        if not query_words:
            return 0.0

        overlap = len(query_words.intersection(turn_words))
        relevance = overlap / len(query_words)

        # Boost recent turns
        time_factor = max(0.1, 1.0 - (time.time() - turn.timestamp) / 3600)  # Decay over 1 hour

        return relevance * time_factor

    async def _extract_conversation_topics(self, turns: List[ConversationTurn]) -> List[str]:
        """Extract key topics from conversation turns."""
        # Simplified topic extraction
        all_text = " ".join(turn.user_query + " " + turn.assistant_response for turn in turns)
        words = all_text.lower().split()

        # Simple frequency-based topic extraction
        word_freq = defaultdict(int)
        for word in words:
            if len(word) > 4:  # Focus on meaningful words
                word_freq[word] += 1

        # Return top words as topics
        topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, freq in topics[:5] if freq > 1]

    async def _generate_conversation_summary(self, turns: List[ConversationTurn]) -> str:
        """Generate a summary of conversation turns."""
        if not turns:
            return "No conversation history available."

        # Simple template-based summary
        reasoning_types = list(set(turn.reasoning_type for turn in turns))
        avg_confidence = sum(turn.confidence_score for turn in turns) / len(turns)

        summary = f"Conversation includes {len(turns)} turns with {', '.join(reasoning_types)} reasoning. "
        summary += f"Average confidence: {avg_confidence:.2f}. "

        if turns:
            last_query = turns[-1].user_query[:100]
            summary += f"Last query: {last_query}..."

        return summary

    def _generate_turn_id(self, user_query: str, assistant_response: str) -> str:
        """Generate unique ID for conversation turn."""
        content = f"{user_query}_{assistant_response}_{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def get_context_statistics(self) -> Dict[str, Any]:
        """Get context management statistics."""
        return {
            "total_conversations": len(self.conversation_sessions),
            "total_turns": len(self.conversation_history),
            "context_cache_size": len(self.context_cache),
            "avg_optimization_time": (
                sum(opt["optimization_time_ms"] for opt in self.optimization_history) / len(self.optimization_history)
                if self.optimization_history
                else 0
            ),
            "avg_efficiency_score": (
                sum(opt["efficiency_score"] for opt in self.optimization_history) / len(self.optimization_history)
                if self.optimization_history
                else 0
            ),
            "optimization_count": len(self.optimization_history),
        }
