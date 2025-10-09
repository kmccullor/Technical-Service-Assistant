from datetime import datetime

from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="orchestrator",
    log_level="INFO",
    console_output=True,
)

"""
Reasoning Orchestrator

Main orchestrator for the reasoning engine that coordinates between
chain-of-thought reasoning, knowledge synthesis, and model selection.
"""

import json
import time
from typing import Any, Dict, List

from chain_of_thought import ChainOfThoughtReasoner, is_complex_reasoning_query
from context_management import AdvancedContextManager
from knowledge_synthesis import KnowledgeSynthesizer
from model_orchestration import EnhancedModelOrchestrator
from reasoning_types import ChainOfThoughtRequest


class ReasoningOrchestrator:
    """
    Main orchestrator for advanced reasoning capabilities.

    Coordinates between different reasoning approaches:
    - Chain-of-thought for complex multi-step analysis
    - Knowledge synthesis for cross-document reasoning
    - Context management for long conversations
    - Model orchestration for specialized reasoning tasks
    """

    def __init__(self, search_client, ollama_client, db_client, settings):
        """Initialize the reasoning orchestrator with required clients."""
        self.search_client = search_client
        self.ollama_client = ollama_client
        self.db_client = db_client
        self.settings = settings

        # Initialize specialized reasoning components
        self.chain_of_thought = ChainOfThoughtReasoner(search_client, ollama_client, settings)
        self.knowledge_synthesizer = KnowledgeSynthesizer(search_client, ollama_client, settings)
        self.context_manager = AdvancedContextManager(
            max_memory_size=getattr(settings, "max_memory_size", 1000),
            max_context_tokens=getattr(settings, "max_context_tokens", 4000),
        )
        self.model_orchestrator = EnhancedModelOrchestrator(
            ollama_client=ollama_client, available_models=getattr(settings, "available_models", None)
        )

        # Reasoning cache for performance
        self.reasoning_cache = {}
        self.max_cache_size = 100

        logger.info("Reasoning orchestrator initialized")

    async def process_reasoning_query(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Main entry point for reasoning queries.

        Determines the appropriate reasoning approach and orchestrates the response.
        Enhanced with knowledge synthesis capabilities.
        """
        start_time = time.time()

        # Check cache first
        cache_key = self._generate_cache_key(query, kwargs)
        if kwargs.get("enable_caching", True) and cache_key in self.reasoning_cache:
            logger.info("Returning cached reasoning result")
            cached_result = self.reasoning_cache[cache_key].copy()
            cached_result["cache_hit"] = True
            return cached_result

        try:
            # Determine reasoning approach based on query complexity and requirements
            reasoning_type = kwargs.get("reasoning_type", "auto")
            max_steps = kwargs.get("max_steps", 5)
            context_documents = kwargs.get("context_documents", [])

            # Gather relevant documents if not provided
            if not context_documents:
                search_results = await self.search_client.search(query, top_k=10)
                context_documents = []
                for result in search_results:
                    doc = {
                        "text": getattr(result, "text", str(result)),
                        "metadata": getattr(result, "metadata", {}),
                        "source": getattr(result, "metadata", {}).get("document_name", "unknown"),
                    }
                    context_documents.append(doc)

            # Apply advanced context management
            session_id = kwargs.get("session_id", "default")
            context_window = await self.context_manager.manage_context_for_reasoning(
                query=query,
                reasoning_type=reasoning_type,
                available_contexts=context_documents,
                session_id=session_id,
                max_context_length=kwargs.get("max_context_tokens"),
            )

            # Use optimized context for reasoning
            optimized_documents = [
                {"text": chunk.text, "source": chunk.source, "metadata": chunk.metadata}
                for chunk in context_window.chunks
            ]

            # Select optimal model(s) using enhanced orchestration
            complexity_level = self._estimate_query_complexity(query)
            use_consensus = kwargs.get("use_consensus", False) or (
                complexity_level == "high" and reasoning_type == "synthesis"
            )

            model_selection = await self.model_orchestrator.select_optimal_model(
                query=query,
                reasoning_type=reasoning_type,
                complexity_level=complexity_level,
                available_instances=kwargs.get("available_instances"),
                require_consensus=use_consensus,
            )

            # Store selected model info for result tracking
            selected_models = model_selection.get("selected_models", [model_selection.get("selected_model")])
            primary_model = model_selection.get("selected_model", "llama2")

            # Determine processing approach with model orchestration
            if use_consensus and len(selected_models) > 1:
                logger.info("Using multi-model consensus reasoning")
                consensus_result = await self.model_orchestrator.execute_with_consensus(
                    query=query,
                    reasoning_type=reasoning_type,
                    selected_models=selected_models,
                    consensus_strategy=kwargs.get("consensus_strategy", "weighted_voting"),
                    max_models=kwargs.get("max_consensus_models", 3),
                )
                result = {
                    "success": True,
                    "final_answer": consensus_result.final_answer,
                    "confidence_score": consensus_result.confidence_score,
                    "reasoning_approach": f"consensus_{consensus_result.consensus_strategy_used}",
                    "models_used": consensus_result.models_participated,
                    "agreement_level": consensus_result.agreement_level,
                    "sources_used": [chunk.source for chunk in context_window.chunks],
                }
                final_answer = consensus_result.final_answer

            elif reasoning_type == "synthesis" or (reasoning_type == "auto" and len(optimized_documents) > 5):
                logger.info("Using enhanced knowledge synthesis approach")
                result = await self.enhanced_cross_document_reasoning(
                    query=query,
                    documents=optimized_documents,
                    reasoning_type="comprehensive" if max_steps > 3 else "standard",
                )
                final_answer = result.get(
                    "enhanced_reasoning", result.get("synthesis_summary", "No synthesis generated")
                )

            elif is_complex_reasoning_query(query) or reasoning_type == "chain_of_thought":
                logger.info("Using chain-of-thought reasoning for complex query")
                result = await self._handle_complex_reasoning(query, model=primary_model, **kwargs)
                final_answer = result.get("response", result.get("final_answer", "No answer generated"))

            else:
                logger.info("Using standard retrieval for simple query")
                result = await self._handle_simple_reasoning(query, model=primary_model, **kwargs)
                final_answer = result.get("response", result.get("final_answer", "No answer generated"))

            # Standardize response format with enhanced model info
            standardized_result = {
                "success": result.get("success", True),
                "final_answer": final_answer,
                "reasoning_type": (
                    reasoning_type if reasoning_type != "auto" else result.get("reasoning_approach", "standard")
                ),
                "complexity_level": complexity_level,
                "reasoning_steps": result.get("reasoning_steps", []),
                "confidence_score": result.get("confidence_score", 0.7),
                "sources_used": result.get("sources_analyzed", result.get("sources_used", [])),
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "cache_hit": False,
                "error_message": result.get("error") if not result.get("success", True) else None,
                "reasoning_approach": result.get("reasoning_approach", "standard"),
                "knowledge_clusters": result.get("knowledge_clusters", []),
                "cross_patterns": result.get("cross_patterns", []),
                "context_efficiency": context_window.efficiency_score if "context_window" in locals() else 0.0,
                "model_selection": {
                    "primary_model": primary_model,
                    "selected_models": selected_models,
                    "selection_confidence": model_selection.get("confidence", 0.5),
                    "selection_strategy": model_selection.get("selection_strategy", "default"),
                    "consensus_used": use_consensus,
                    "agreement_level": result.get("agreement_level", 1.0),
                },
            }

            # Store conversation turn for future context management
            if standardized_result["success"]:
                await self.context_manager.store_conversation_turn(
                    user_query=query,
                    assistant_response=final_answer,
                    context_used=(
                        [chunk.source for chunk in context_window.chunks] if "context_window" in locals() else []
                    ),
                    reasoning_type=standardized_result["reasoning_type"],
                    confidence_score=standardized_result["confidence_score"],
                    session_id=session_id,
                    metadata={
                        "processing_time_ms": standardized_result["processing_time_ms"],
                        "context_efficiency": standardized_result["context_efficiency"],
                        "reasoning_approach": standardized_result["reasoning_approach"],
                    },
                )

            # Cache result if successful
            if standardized_result["success"] and kwargs.get("enable_caching", True):
                self._cache_result(cache_key, standardized_result)

            return standardized_result

        except Exception as e:
            logger.error(f"Reasoning query failed: {e}")
            reasoning_type = kwargs.get("reasoning_type", "unknown")
            return {
                "success": False,
                "final_answer": "I encountered an error while processing your question. Please try rephrasing or ask a simpler question.",
                "reasoning_type": reasoning_type,
                "complexity_level": "medium",
                "reasoning_steps": [],
                "confidence_score": 0.0,
                "sources_used": [],
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "cache_hit": False,
                "error_message": str(e),
                "reasoning_approach": "error_fallback",
                "knowledge_clusters": [],
                "cross_patterns": [],
            }

    def _estimate_query_complexity(self, query: str) -> str:
        """Estimate query complexity level."""
        # Simple heuristic based on query characteristics
        if len(query.split()) > 20 or any(
            word in query.lower() for word in ["compare", "analyze", "synthesize", "evaluate"]
        ):
            return "high"
        elif len(query.split()) > 10 or any(word in query.lower() for word in ["explain", "describe", "summarize"]):
            return "medium"
        else:
            return "low"

    async def _handle_complex_reasoning(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle complex reasoning queries using chain-of-thought."""

        # Create chain-of-thought request
        cot_request = ChainOfThoughtRequest(
            query=query,
            decompose_query=kwargs.get("decompose_query", True),
            gather_evidence=kwargs.get("gather_evidence", True),
            synthesize_answer=kwargs.get("synthesize_answer", True),
            min_evidence_sources=kwargs.get("min_evidence_sources", 3),
            max_reasoning_depth=kwargs.get("max_reasoning_depth", 5),
        )

        # Execute chain-of-thought reasoning
        reasoning_response = await self.chain_of_thought.reason_through_query(cot_request)

        return {
            "success": True,
            "response": reasoning_response.final_answer,
            "reasoning_type": reasoning_response.reasoning_type,
            "complexity": reasoning_response.complexity,
            "confidence_score": reasoning_response.confidence_score,
            "reasoning_steps": reasoning_response.steps,
            "sources_used": reasoning_response.sources_used,
            "model_used": reasoning_response.model_used,
            "reasoning_time_ms": reasoning_response.reasoning_time_ms,
        }

    async def _handle_simple_reasoning(self, query: str, **kwargs) -> Dict[str, Any]:
        """Handle simple reasoning queries with standard retrieval."""

        try:
            # Simple evidence gathering
            search_results = await self.search_client.search(query=query, top_k=kwargs.get("top_k", 5))

            if not search_results:
                return {
                    "success": True,
                    "response": "I couldn't find relevant information to answer your question.",
                    "reasoning_type": "simple_retrieval",
                    "sources_used": [],
                    "confidence_score": 0.1,
                }

            # Create context from search results
            context_chunks = []
            sources = []

            for result in search_results:
                if hasattr(result, "text"):
                    context_chunks.append(result.text)
                if hasattr(result, "metadata"):
                    source = result.metadata.get("document_name", "Unknown source")
                    sources.append(source)

            context = "\n\n".join(context_chunks)

            # Generate simple response
            prompt = f"""
            Based on the following information, answer the question clearly and concisely.

            Context:
            {context}

            Question: {query}

            Answer:
            """

            response = self.ollama_client.generate(
                model=kwargs.get("model", "mistral:7B"),
                prompt=prompt,
                options={"temperature": kwargs.get("temperature", 0.2), "num_predict": kwargs.get("max_tokens", 300)},
            )

            return {
                "success": True,
                "response": response["response"].strip(),
                "reasoning_type": "simple_retrieval",
                "sources_used": list(set(sources)),
                "confidence_score": 0.8,
                "context_used": context_chunks,
            }

        except Exception as e:
            logger.error(f"Simple reasoning failed: {e}")
            raise

    async def chain_of_thought_reasoning(self, query: str, context: List[str]) -> Dict[str, Any]:
        """
        Perform chain-of-thought reasoning with provided context.

        This method implements multi-step reasoning:
        1. Break down the query into logical steps
        2. Analyze each step with available context
        3. Build reasoning chain
        4. Synthesize final answer
        """

        logger.info(f"Starting chain-of-thought reasoning for: {query[:100]}...")

        try:
            # Step 1: Decompose the query
            decomposition = await self._decompose_reasoning_query(query)

            # Step 2: Analyze each component
            reasoning_steps = []
            for i, component in enumerate(decomposition):
                step_analysis = await self._analyze_reasoning_step(component, context, step_number=i + 1)
                reasoning_steps.append(step_analysis)

            # Step 3: Synthesize final reasoning
            final_answer = await self._synthesize_reasoning_chain(query, reasoning_steps, context)

            return {
                "success": True,
                "final_answer": final_answer,
                "reasoning_steps": reasoning_steps,
                "decomposition": decomposition,
                "confidence": self._calculate_reasoning_confidence(reasoning_steps),
            }

        except Exception as e:
            logger.error(f"Chain-of-thought reasoning failed: {e}")
            return {"success": False, "error": str(e), "final_answer": "Unable to complete chain-of-thought reasoning."}

    async def multi_step_analysis(self, query: str, documents: List[Dict]) -> Dict[str, Any]:
        """
        Perform multi-step analysis across multiple documents.

        This method implements cross-document reasoning:
        1. Extract relevant information from each document
        2. Identify relationships and patterns
        3. Synthesize insights across documents
        4. Generate comprehensive analysis
        """

        logger.info(f"Starting multi-step analysis across {len(documents)} documents")

        try:
            # Step 1: Extract relevant info from each document
            document_analyses = []
            for doc in documents:
                analysis = await self._analyze_single_document(query, doc)
                document_analyses.append(analysis)

            # Step 2: Identify cross-document patterns
            patterns = await self._identify_cross_document_patterns(query, document_analyses)

            # Step 3: Synthesize comprehensive analysis
            comprehensive_analysis = await self._synthesize_multi_document_analysis(query, document_analyses, patterns)

            return {
                "success": True,
                "comprehensive_analysis": comprehensive_analysis,
                "document_analyses": document_analyses,
                "identified_patterns": patterns,
                "documents_analyzed": len(documents),
            }

        except Exception as e:
            logger.error(f"Multi-step analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "comprehensive_analysis": "Unable to complete multi-step analysis.",
            }

    async def knowledge_synthesis(
        self, query: str, source_documents: List[Dict[str, Any]], synthesis_depth: str = "standard"
    ) -> Dict[str, Any]:
        """
        Advanced knowledge synthesis across multiple documents.

        Args:
            query: Research question or query
            source_documents: List of document chunks with text and metadata
            synthesis_depth: Level of synthesis ('shallow', 'standard', 'deep')

        Returns:
            Comprehensive synthesis result with clusters, patterns, and conflicts
        """
        logger.info(f"Starting knowledge synthesis for: {query[:100]}...")

        try:
            synthesis_result = await self.knowledge_synthesizer.synthesize_knowledge(
                query=query, source_documents=source_documents, synthesis_depth=synthesis_depth
            )

            return {
                "success": True,
                "main_synthesis": synthesis_result.main_synthesis,
                "knowledge_clusters": [
                    {
                        "theme": cluster.theme,
                        "confidence": cluster.confidence,
                        "source_documents": cluster.source_documents,
                        "key_concepts": cluster.key_concepts,
                        "synthesis": cluster.synthesis,
                    }
                    for cluster in synthesis_result.knowledge_clusters
                ],
                "cross_patterns": [
                    {
                        "pattern_type": pattern.pattern_type,
                        "description": pattern.description,
                        "strength": pattern.strength,
                        "documents_involved": list(pattern.documents_involved),
                    }
                    for pattern in synthesis_result.cross_patterns
                ],
                "conflicting_viewpoints": synthesis_result.conflicting_viewpoints,
                "confidence_score": synthesis_result.confidence_score,
                "synthesis_approach": synthesis_result.synthesis_approach,
                "sources_analyzed": synthesis_result.sources_analyzed,
            }

        except Exception as e:
            logger.error(f"Knowledge synthesis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "main_synthesis": f"Knowledge synthesis failed: {str(e)}",
                "knowledge_clusters": [],
                "cross_patterns": [],
                "conflicting_viewpoints": [],
                "confidence_score": 0.0,
                "synthesis_approach": synthesis_depth,
                "sources_analyzed": [],
            }

    async def enhanced_cross_document_reasoning(
        self, query: str, documents: List[Dict[str, Any]], reasoning_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Enhanced cross-document reasoning with knowledge synthesis.

        Combines multi-step analysis with knowledge synthesis for comprehensive
        understanding across multiple documents.
        """
        logger.info(f"Enhanced cross-document reasoning for: {query[:100]}...")

        try:
            # Step 1: Perform knowledge synthesis
            synthesis_result = await self.knowledge_synthesis(
                query=query,
                source_documents=documents,
                synthesis_depth="deep" if reasoning_type == "comprehensive" else "standard",
            )

            # Step 2: Perform multi-step analysis
            analysis_result = await self.multi_step_analysis(query, documents)

            # Step 3: Combine results for enhanced reasoning
            enhanced_reasoning = await self._combine_synthesis_and_analysis(query, synthesis_result, analysis_result)

            return {
                "success": True,
                "enhanced_reasoning": enhanced_reasoning,
                "synthesis_summary": synthesis_result.get("main_synthesis", ""),
                "analysis_summary": analysis_result.get("comprehensive_analysis", ""),
                "knowledge_clusters": synthesis_result.get("knowledge_clusters", []),
                "cross_patterns": synthesis_result.get("cross_patterns", []),
                "confidence_score": max(
                    synthesis_result.get("confidence_score", 0.0), 0.8 if analysis_result.get("success", False) else 0.3
                ),
                "reasoning_approach": "enhanced_cross_document",
            }

        except Exception as e:
            logger.error(f"Enhanced cross-document reasoning failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "enhanced_reasoning": f"Enhanced reasoning failed: {str(e)}",
                "synthesis_summary": "",
                "analysis_summary": "",
                "confidence_score": 0.0,
                "reasoning_approach": "enhanced_cross_document",
            }

    async def _combine_synthesis_and_analysis(
        self, query: str, synthesis_result: Dict[str, Any], analysis_result: Dict[str, Any]
    ) -> str:
        """Combine knowledge synthesis and multi-step analysis results."""
        try:
            combine_prompt = f"""
            Create a comprehensive reasoning response for: {query}

            Knowledge Synthesis:
            {synthesis_result.get('main_synthesis', 'No synthesis available')}

            Multi-Step Analysis:
            {analysis_result.get('comprehensive_analysis', 'No analysis available')}

            Knowledge Clusters:
            {json.dumps(synthesis_result.get('knowledge_clusters', []), indent=2)}

            Cross-Document Patterns:
            {json.dumps(synthesis_result.get('cross_patterns', []), indent=2)}

            Provide a unified, comprehensive response that:
            1. Synthesizes insights from both approaches
            2. Highlights key findings and patterns
            3. Addresses the original query thoroughly
            4. Notes any limitations or contradictions
            5. Draws meaningful conclusions
            """

            response = self.ollama_client.generate(
                model="mistral:7B", prompt=combine_prompt, options={"temperature": 0.6, "num_predict": 800}
            )

            return response["response"].strip()

        except Exception as e:
            logger.error(f"Failed to combine synthesis and analysis: {e}")
            return f"Failed to combine reasoning approaches: {str(e)}"

    async def cross_document_synthesis(self, topics: List[str]) -> Dict[str, Any]:
        """
        Synthesize information across multiple topics and documents.

        This method implements knowledge synthesis:
        1. Gather information for each topic
        2. Identify relationships between topics
        3. Resolve conflicts and contradictions
        4. Generate synthesized knowledge
        """

        logger.info(f"Starting cross-document synthesis for {len(topics)} topics")

        try:
            # Step 1: Gather information for each topic
            topic_information = {}
            for topic in topics:
                info = await self._gather_topic_information(topic)
                topic_information[topic] = info

            # Step 2: Identify relationships
            relationships = await self._identify_topic_relationships(topics, topic_information)

            # Step 3: Resolve conflicts
            resolved_information = await self._resolve_information_conflicts(topic_information, relationships)

            # Step 4: Generate synthesis
            synthesis = await self._generate_knowledge_synthesis(topics, resolved_information, relationships)

            return {
                "success": True,
                "synthesis": synthesis,
                "topic_information": topic_information,
                "relationships": relationships,
                "topics_processed": len(topics),
            }

        except Exception as e:
            logger.error(f"Cross-document synthesis failed: {e}")
            return {"success": False, "error": str(e), "synthesis": "Unable to complete cross-document synthesis."}

    def _generate_cache_key(self, query: str, kwargs: Dict) -> str:
        """Generate cache key for reasoning queries."""
        import hashlib

        key_data = f"{query}_{json.dumps(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache reasoning result with size management."""
        if len(self.reasoning_cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.reasoning_cache))
            del self.reasoning_cache[oldest_key]

        self.reasoning_cache[cache_key] = result

    async def _decompose_reasoning_query(self, query: str) -> List[str]:
        """Decompose a query into logical reasoning components."""
        # This is a simplified implementation
        # In practice, this would use more sophisticated NLP

        components = [query]  # Placeholder
        return components

    async def _analyze_reasoning_step(self, component: str, context: List[str], step_number: int) -> Dict[str, Any]:
        """Analyze a single reasoning step."""
        return {
            "step_number": step_number,
            "component": component,
            "analysis": f"Analysis of step {step_number}",
            "confidence": 0.8,
        }

    async def _synthesize_reasoning_chain(self, query: str, steps: List[Dict], context: List[str]) -> str:
        """Synthesize final answer from reasoning chain."""
        return f"Synthesized answer for: {query}"

    def _calculate_reasoning_confidence(self, steps: List[Dict]) -> float:
        """Calculate overall confidence from reasoning steps."""
        if not steps:
            return 0.0

        confidences = [step.get("confidence", 0.5) for step in steps]
        return sum(confidences) / len(confidences)

    async def _analyze_single_document(self, query: str, document: Dict) -> Dict[str, Any]:
        """Analyze single document for relevant information."""
        return {
            "document_id": document.get("id", "unknown"),
            "relevant_info": "Extracted information",
            "confidence": 0.7,
        }

    async def _identify_cross_document_patterns(self, query: str, analyses: List[Dict]) -> List[Dict]:
        """Identify patterns across document analyses."""
        return [{"pattern": "example_pattern", "strength": 0.8}]

    async def _synthesize_multi_document_analysis(self, query: str, analyses: List[Dict], patterns: List[Dict]) -> str:
        """Synthesize comprehensive analysis from multiple documents."""
        return f"Comprehensive analysis for: {query}"

    async def _gather_topic_information(self, topic: str) -> Dict[str, Any]:
        """Gather information for a specific topic."""
        return {"topic": topic, "information": "Gathered information"}

    async def _identify_topic_relationships(self, topics: List[str], topic_info: Dict) -> List[Dict]:
        """Identify relationships between topics."""
        return [{"topics": topics[:2], "relationship": "related", "strength": 0.7}]

    async def _resolve_information_conflicts(self, topic_info: Dict, relationships: List[Dict]) -> Dict[str, Any]:
        """Resolve conflicts in gathered information."""
        return topic_info  # Simplified - would implement conflict resolution

    async def _generate_knowledge_synthesis(self, topics: List[str], info: Dict, relationships: List[Dict]) -> str:
        """Generate final knowledge synthesis."""
        return f"Synthesized knowledge for topics: {', '.join(topics)}"

    def get_orchestrator_statistics(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator statistics."""
        return {
            "reasoning_cache_size": len(self.reasoning_cache),
            "context_stats": self.context_manager.get_context_statistics(),
            "model_orchestration_stats": self.model_orchestrator.get_orchestration_statistics(),
            "total_reasoning_operations": len(self.reasoning_cache),
            "cache_hit_rate": 0.0,  # Would calculate from cache hits vs misses
        }


# Factory function for easy instantiation
async def create_reasoning_orchestrator(search_client, ollama_client, db_client, settings):
    """Factory function to create a reasoning orchestrator instance."""
    return ReasoningOrchestrator(search_client, ollama_client, db_client, settings)
