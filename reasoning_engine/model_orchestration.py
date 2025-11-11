"""
Enhanced Model Orchestration

Sophisticated model orchestration capabilities including reasoning-aware model selection,
multi-model consensus building, specialized model routing, and performance optimization.
"""

import logging
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import get_model_num_ctx

logger = logging.getLogger(__name__)


@dataclass
class ModelPerformanceMetrics:
    """Performance metrics for a specific model."""

    model_name: str
    instance_url: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    avg_confidence_score: float = 0.0
    reasoning_type_performance: Dict[str, float] = field(default_factory=dict)
    last_update: float = field(default_factory=time.time)
    health_score: float = 1.0


@dataclass
class ModelCapability:
    """Represents capabilities of a model for different reasoning types."""

    model_name: str
    reasoning_strengths: List[str]
    complexity_levels: List[str]
    max_context_tokens: int
    specializations: List[str]
    performance_tier: str  # 'high', 'medium', 'low'
    availability_score: float = 1.0


@dataclass
class ConsensusRequest:
    """Request for multi-model consensus."""

    query: str
    reasoning_type: str
    models_to_use: List[str]
    consensus_strategy: str
    min_agreement_threshold: float
    max_models: int


@dataclass
class ConsensusResult:
    """Result from multi-model consensus."""

    final_answer: str
    confidence_score: float
    agreement_level: float
    model_responses: Dict[str, Dict[str, Any]]
    consensus_strategy_used: str
    models_participated: List[str]
    processing_time_ms: int


class EnhancedModelOrchestrator:
    """
    Advanced model orchestration system for reasoning operations.

    Features:
    - Reasoning-aware model selection
    - Multi-model consensus building
    - Performance-based routing optimization
    - Specialized model routing for different reasoning types
    - Dynamic load balancing across model instances
    - Intelligent fallback strategies
    - Performance monitoring and adaptation
    """

    def __init__(self, ollama_client, available_models: Optional[List[str]] = None):
        """Initialize enhanced model orchestrator."""
        self.ollama_client = ollama_client

        # Model capabilities and performance tracking
        self.model_metrics: Dict[str, ModelPerformanceMetrics] = {}
        self.model_capabilities: Dict[str, ModelCapability] = {}

        # Performance history for optimization
        self.performance_history: deque = deque(maxlen=1000)
        self.consensus_history: List[ConsensusResult] = []

        # Routing configuration
        self.routing_strategy = "performance_based"
        self.enable_consensus = True
        self.consensus_threshold = 0.7

        # Initialize model capabilities
        self._initialize_model_capabilities(available_models or ["llama2", "mistral:7b", "codellama", "llama2:13b"])

        logger.info("Enhanced model orchestrator initialized")

    async def select_optimal_model(
        self,
        query: str,
        reasoning_type: str,
        complexity_level: str = "medium",
        available_instances: Optional[List[str]] = None,
        require_consensus: bool = False,
    ) -> Dict[str, Any]:
        """
        Select optimal model(s) for a reasoning task.

        Args:
            query: The user query or reasoning task
            reasoning_type: Type of reasoning required
            complexity_level: Complexity level of the task
            available_instances: Available model instances
            require_consensus: Whether to use multi-model consensus

        Returns:
            Model selection result with recommendations
        """
        logger.info(f"Selecting optimal model for {reasoning_type} reasoning (complexity: {complexity_level})")

        try:
            if require_consensus:
                return await self._select_consensus_models(
                    query=query,
                    reasoning_type=reasoning_type,
                    complexity_level=complexity_level,
                    available_instances=available_instances,
                )
            else:
                return await self._select_single_model(
                    query=query,
                    reasoning_type=reasoning_type,
                    complexity_level=complexity_level,
                    available_instances=available_instances,
                )

        except Exception as e:
            logger.error(f"Model selection failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "selected_model": "llama2",  # Fallback
                "instance_url": None,
                "selection_strategy": "fallback",
                "confidence": 0.3,
            }

    async def execute_with_consensus(
        self,
        query: str,
        reasoning_type: str,
        selected_models: List[str],
        consensus_strategy: str = "weighted_voting",
        max_models: int = 3,
    ) -> ConsensusResult:
        """
        Execute reasoning with multi-model consensus.

        Args:
            query: The reasoning query
            reasoning_type: Type of reasoning
            selected_models: Models to use for consensus
            consensus_strategy: Strategy for reaching consensus
            max_models: Maximum number of models to use

        Returns:
            Consensus result with final answer and agreement metrics
        """
        logger.info(f"Executing consensus reasoning with {len(selected_models[:max_models])} models")

        start_time = time.time()
        model_responses = {}

        try:
            # Execute reasoning with each selected model
            tasks = []
            for model in selected_models[:max_models]:
                task = self._execute_single_model_reasoning(query, reasoning_type, model)
                tasks.append((model, task))

            # Gather responses
            for model, task in tasks:
                try:
                    response = await task
                    model_responses[model] = response
                except Exception as e:
                    logger.error(f"Model {model} failed: {e}")
                    model_responses[model] = {"success": False, "error": str(e), "answer": "", "confidence": 0.0}

            # Apply consensus strategy
            consensus_result = await self._apply_consensus_strategy(
                query=query, model_responses=model_responses, strategy=consensus_strategy
            )

            processing_time = int((time.time() - start_time) * 1000)

            result = ConsensusResult(
                final_answer=consensus_result["final_answer"],
                confidence_score=consensus_result["confidence_score"],
                agreement_level=consensus_result["agreement_level"],
                model_responses=model_responses,
                consensus_strategy_used=consensus_strategy,
                models_participated=list(model_responses.keys()),
                processing_time_ms=processing_time,
            )

            # Update performance metrics
            await self._update_consensus_metrics(result, reasoning_type)

            self.consensus_history.append(result)
            return result

        except Exception as e:
            logger.error(f"Consensus execution failed: {e}")
            return ConsensusResult(
                final_answer=f"Consensus failed: {str(e)}",
                confidence_score=0.0,
                agreement_level=0.0,
                model_responses=model_responses,
                consensus_strategy_used=consensus_strategy,
                models_participated=list(model_responses.keys()),
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

    async def optimize_model_routing(self, reasoning_type: str, performance_window: int = 100) -> Dict[str, Any]:
        """
        Optimize model routing based on recent performance.

        Args:
            reasoning_type: Type of reasoning to optimize for
            performance_window: Number of recent requests to analyze

        Returns:
            Optimization results and recommendations
        """
        logger.info(f"Optimizing model routing for {reasoning_type} reasoning")

        try:
            # Analyze recent performance
            recent_performance = list(self.performance_history)[-performance_window:]

            # Calculate performance metrics by model
            model_performance = defaultdict(list)
            for record in recent_performance:
                if record.get("reasoning_type") == reasoning_type:
                    model = record.get("model_used")
                    if model:
                        model_performance[model].append(record)

            # Generate optimization recommendations
            recommendations = {}
            for model, records in model_performance.items():
                if len(records) >= 5:  # Minimum sample size
                    avg_response_time = statistics.mean(r.get("response_time_ms", 0) for r in records)
                    avg_confidence = statistics.mean(r.get("confidence_score", 0) for r in records)
                    success_rate = sum(1 for r in records if r.get("success", False)) / len(records)

                    performance_score = (
                        success_rate * 0.5 + (avg_confidence / 1.0) * 0.3 + (1000 / max(avg_response_time, 100)) * 0.2
                    )

                    recommendations[model] = {
                        "performance_score": performance_score,
                        "avg_response_time": avg_response_time,
                        "avg_confidence": avg_confidence,
                        "success_rate": success_rate,
                        "sample_size": len(records),
                        "recommendation": self._generate_model_recommendation(performance_score),
                    }

            # Update model capabilities based on performance
            await self._update_model_capabilities(recommendations, reasoning_type)

            return {
                "success": True,
                "reasoning_type": reasoning_type,
                "models_analyzed": len(recommendations),
                "recommendations": recommendations,
                "optimization_strategy": "performance_based",
                "best_performing_model": (
                    max(recommendations.keys(), key=lambda k: recommendations[k]["performance_score"])
                    if recommendations
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Model routing optimization failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "reasoning_type": reasoning_type,
                "models_analyzed": 0,
                "recommendations": {},
            }

    async def _select_single_model(
        self, query: str, reasoning_type: str, complexity_level: str, available_instances: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Select single best model for the task."""

        # Score models based on capabilities and performance
        model_scores = {}

        for model_name, capability in self.model_capabilities.items():
            score = 0.0

            # Reasoning type compatibility
            if reasoning_type in capability.reasoning_strengths:
                score += 0.4
            elif any(strength in reasoning_type for strength in capability.reasoning_strengths):
                score += 0.2

            # Complexity level compatibility
            if complexity_level in capability.complexity_levels:
                score += 0.3

            # Performance metrics
            metrics = self.model_metrics.get(model_name)
            if metrics:
                success_rate = metrics.successful_requests / max(metrics.total_requests, 1)
                score += success_rate * 0.2

                # Response time factor (inverse relationship)
                time_factor = min(1.0, 1000 / max(metrics.avg_response_time, 100))
                score += time_factor * 0.1

            model_scores[model_name] = score

        # Select best model
        if model_scores:
            best_model = max(model_scores.keys(), key=lambda k: model_scores[k])
            best_score = model_scores[best_model]
        else:
            best_model = "llama2"  # Fallback
            best_score = 0.5

        return {
            "success": True,
            "selected_model": best_model,
            "instance_url": self._get_model_instance_url(best_model, available_instances),
            "selection_strategy": "capability_performance_based",
            "confidence": best_score,
            "model_scores": model_scores,
            "reasoning_type": reasoning_type,
            "complexity_level": complexity_level,
        }

    async def _select_consensus_models(
        self, query: str, reasoning_type: str, complexity_level: str, available_instances: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Select models for consensus reasoning."""

        # Get top models for this reasoning type
        suitable_models = []

        for model_name, capability in self.model_capabilities.items():
            if reasoning_type in capability.reasoning_strengths and complexity_level in capability.complexity_levels:
                metrics = self.model_metrics.get(model_name)
                performance_score = 0.7  # Default

                if metrics:
                    success_rate = metrics.successful_requests / max(metrics.total_requests, 1)
                    confidence_score = metrics.avg_confidence_score
                    performance_score = (success_rate + confidence_score) / 2

                suitable_models.append((model_name, performance_score))

        # Sort by performance and select top models
        suitable_models.sort(key=lambda x: x[1], reverse=True)
        selected_models = [model for model, _ in suitable_models[:3]]

        if not selected_models:
            selected_models = ["llama2", "mistral:7b"]  # Fallback

        return {
            "success": True,
            "selected_models": selected_models,
            "consensus_strategy": "weighted_voting",
            "selection_strategy": "multi_model_consensus",
            "confidence": 0.8,
            "reasoning_type": reasoning_type,
            "complexity_level": complexity_level,
        }

    async def _execute_single_model_reasoning(self, query: str, reasoning_type: str, model: str) -> Dict[str, Any]:
        """Execute reasoning with a single model."""

        start_time = time.time()

        try:
            # Prepare prompt based on reasoning type
            prompt = self._prepare_reasoning_prompt(query, reasoning_type)

            # Execute model call
            options = {
                "temperature": 0.3 if reasoning_type in ["analytical", "factual"] else 0.7,
                "num_predict": 500,
            }
            num_ctx = get_model_num_ctx(model)
            if num_ctx:
                options["num_ctx"] = num_ctx

            response = await self.ollama_client.generate(
                model=model,
                prompt=prompt,
                options=options,
            )

            answer = response.get("response", "").strip()

            # Estimate confidence (simplified)
            confidence = self._estimate_response_confidence(answer, reasoning_type)

            processing_time = int((time.time() - start_time) * 1000)

            # Update model metrics
            await self._update_model_metrics(model, True, processing_time, confidence, reasoning_type)

            return {
                "success": True,
                "answer": answer,
                "confidence": confidence,
                "model": model,
                "reasoning_type": reasoning_type,
                "processing_time_ms": processing_time,
            }

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            await self._update_model_metrics(model, False, processing_time, 0.0, reasoning_type)

            logger.error(f"Model {model} reasoning failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "answer": "",
                "confidence": 0.0,
                "model": model,
                "reasoning_type": reasoning_type,
                "processing_time_ms": processing_time,
            }

    async def _apply_consensus_strategy(
        self, query: str, model_responses: Dict[str, Dict[str, Any]], strategy: str
    ) -> Dict[str, Any]:
        """Apply consensus strategy to model responses."""

        successful_responses = {
            model: resp
            for model, resp in model_responses.items()
            if resp.get("success", False) and resp.get("answer", "").strip()
        }

        if not successful_responses:
            return {
                "final_answer": "No successful responses from models",
                "confidence_score": 0.0,
                "agreement_level": 0.0,
            }

        if strategy == "weighted_voting":
            return await self._weighted_voting_consensus(successful_responses)
        elif strategy == "highest_confidence":
            return await self._highest_confidence_consensus(successful_responses)
        elif strategy == "majority_similarity":
            return await self._majority_similarity_consensus(successful_responses)
        else:
            # Default to weighted voting
            return await self._weighted_voting_consensus(successful_responses)

    async def _weighted_voting_consensus(self, responses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Apply weighted voting consensus."""

        # Weight responses by confidence and model performance

        # For now, use the highest confidence response as final answer
        # In a more sophisticated implementation, we would analyze semantic similarity
        best_response = max(responses.values(), key=lambda r: r.get("confidence", 0))

        # Calculate agreement level based on confidence distribution
        confidences = [r.get("confidence", 0) for r in responses.values()]
        agreement_level = 1.0 - (statistics.stdev(confidences) if len(confidences) > 1 else 0.0)

        return {
            "final_answer": best_response.get("answer", ""),
            "confidence_score": best_response.get("confidence", 0),
            "agreement_level": max(0.0, min(1.0, agreement_level)),
        }

    async def _highest_confidence_consensus(self, responses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Select response with highest confidence."""

        best_response = max(responses.values(), key=lambda r: r.get("confidence", 0))

        # Agreement level based on how much higher the best confidence is
        confidences = [r.get("confidence", 0) for r in responses.values()]
        max_conf = max(confidences)
        avg_conf = statistics.mean(confidences)
        agreement_level = min(1.0, max_conf / max(avg_conf, 0.1))

        return {
            "final_answer": best_response.get("answer", ""),
            "confidence_score": best_response.get("confidence", 0),
            "agreement_level": agreement_level,
        }

    async def _majority_similarity_consensus(self, responses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Find consensus based on response similarity."""

        # Simplified: use response lengths as similarity proxy
        # In practice, would use semantic similarity
        response_items = list(responses.items())

        if len(response_items) == 1:
            resp = response_items[0][1]
            return {
                "final_answer": resp.get("answer", ""),
                "confidence_score": resp.get("confidence", 0),
                "agreement_level": 1.0,
            }

        # For now, return the median-length response
        sorted_responses = sorted(response_items, key=lambda x: len(x[1].get("answer", "")))
        median_resp = sorted_responses[len(sorted_responses) // 2][1]

        return {
            "final_answer": median_resp.get("answer", ""),
            "confidence_score": median_resp.get("confidence", 0),
            "agreement_level": 0.7,  # Placeholder
        }

    def _initialize_model_capabilities(self, available_models: List[str]):
        """Initialize model capabilities based on known model strengths."""

        model_configs = {
            "llama2": ModelCapability(
                model_name="llama2",
                reasoning_strengths=["general", "conversational", "synthesis"],
                complexity_levels=["low", "medium"],
                max_context_tokens=4096,
                specializations=["general_purpose"],
                performance_tier="medium",
            ),
            "mistral:7b": ModelCapability(
                model_name="mistral:7b",
                reasoning_strengths=["analytical", "technical", "factual"],
                complexity_levels=["medium", "high"],
                max_context_tokens=8192,
                specializations=["technical_analysis"],
                performance_tier="high",
            ),
            "codellama": ModelCapability(
                model_name="codellama",
                reasoning_strengths=["code", "logical", "step_by_step"],
                complexity_levels=["medium", "high"],
                max_context_tokens=4096,
                specializations=["code_analysis", "logical_reasoning"],
                performance_tier="high",
            ),
            "llama2:13b": ModelCapability(
                model_name="llama2:13b",
                reasoning_strengths=["synthesis", "comprehensive", "complex"],
                complexity_levels=["high"],
                max_context_tokens=4096,
                specializations=["complex_reasoning"],
                performance_tier="high",
            ),
        }

        for model in available_models:
            if model in model_configs:
                self.model_capabilities[model] = model_configs[model]
            else:
                # Default capability for unknown models
                self.model_capabilities[model] = ModelCapability(
                    model_name=model,
                    reasoning_strengths=["general"],
                    complexity_levels=["low", "medium"],
                    max_context_tokens=2048,
                    specializations=["general_purpose"],
                    performance_tier="medium",
                )

            # Initialize metrics
            self.model_metrics[model] = ModelPerformanceMetrics(
                model_name=model,
                instance_url="",
            )

    async def _update_model_metrics(
        self, model: str, success: bool, response_time: int, confidence: float, reasoning_type: str
    ):
        """Update performance metrics for a model."""

        if model not in self.model_metrics:
            self.model_metrics[model] = ModelPerformanceMetrics(model_name=model, instance_url="")

        metrics = self.model_metrics[model]
        metrics.total_requests += 1

        if success:
            metrics.successful_requests += 1

            # Update running averages
            total_successful = metrics.successful_requests
            metrics.avg_response_time = (
                metrics.avg_response_time * (total_successful - 1) + response_time
            ) / total_successful
            metrics.avg_confidence_score = (
                metrics.avg_confidence_score * (total_successful - 1) + confidence
            ) / total_successful

            # Update reasoning type performance
            if reasoning_type not in metrics.reasoning_type_performance:
                metrics.reasoning_type_performance[reasoning_type] = confidence
            else:
                current = metrics.reasoning_type_performance[reasoning_type]
                metrics.reasoning_type_performance[reasoning_type] = current * 0.8 + confidence * 0.2
        else:
            metrics.failed_requests += 1

        # Update health score
        success_rate = metrics.successful_requests / metrics.total_requests
        metrics.health_score = success_rate
        metrics.last_update = time.time()

        # Record performance history
        self.performance_history.append(
            {
                "timestamp": time.time(),
                "model_used": model,
                "success": success,
                "response_time_ms": response_time,
                "confidence_score": confidence,
                "reasoning_type": reasoning_type,
            }
        )

    async def _update_consensus_metrics(self, result: ConsensusResult, reasoning_type: str):
        """Update metrics for consensus results."""

        # Record consensus performance
        consensus_record = {
            "timestamp": time.time(),
            "reasoning_type": reasoning_type,
            "models_used": result.models_participated,
            "agreement_level": result.agreement_level,
            "confidence_score": result.confidence_score,
            "processing_time_ms": result.processing_time_ms,
            "strategy": result.consensus_strategy_used,
        }

        self.performance_history.append(consensus_record)

    async def _update_model_capabilities(self, recommendations: Dict[str, Dict], reasoning_type: str):
        """Update model capabilities based on performance recommendations."""

        for model, rec in recommendations.items():
            if model in self.model_capabilities:
                capability = self.model_capabilities[model]

                # Adjust performance tier based on performance score
                score = rec["performance_score"]
                if score > 0.8:
                    capability.performance_tier = "high"
                elif score > 0.6:
                    capability.performance_tier = "medium"
                else:
                    capability.performance_tier = "low"

                # Update availability score
                capability.availability_score = rec["success_rate"]

    def _prepare_reasoning_prompt(self, query: str, reasoning_type: str) -> str:
        """Prepare reasoning-specific prompt."""

        prompts = {
            "analytical": f"Analyze the following question step by step and provide a detailed analytical response:\n\n{query}",
            "synthesis": f"Synthesize information and provide a comprehensive response to:\n\n{query}",
            "factual": f"Provide a factual, accurate answer to:\n\n{query}",
            "creative": f"Think creatively and provide an innovative response to:\n\n{query}",
            "logical": f"Use logical reasoning to answer:\n\n{query}",
            "code": f"Analyze this code-related question and provide a technical response:\n\n{query}",
        }

        return prompts.get(reasoning_type, f"Answer the following question:\n\n{query}")

    def _estimate_response_confidence(self, answer: str, reasoning_type: str) -> float:
        """Estimate confidence in model response."""

        if not answer or len(answer.strip()) < 10:
            return 0.1

        # Simple heuristics for confidence estimation
        confidence = 0.5  # Base confidence

        # Length factor
        if len(answer) > 100:
            confidence += 0.2

        # Certainty indicators
        certain_phrases = ["definitely", "certainly", "clearly", "obviously", "precisely"]
        uncertain_phrases = ["maybe", "perhaps", "possibly", "might", "could be"]

        certain_count = sum(1 for phrase in certain_phrases if phrase in answer.lower())
        uncertain_count = sum(1 for phrase in uncertain_phrases if phrase in answer.lower())

        confidence += certain_count * 0.1 - uncertain_count * 0.1

        # Reasoning type adjustments
        if reasoning_type in ["factual", "analytical"] and "because" in answer.lower():
            confidence += 0.1

        return max(0.0, min(1.0, confidence))

    def _generate_model_recommendation(self, performance_score: float) -> str:
        """Generate recommendation based on performance score."""

        if performance_score > 0.8:
            return "Excellent performance - prioritize for this reasoning type"
        elif performance_score > 0.6:
            return "Good performance - suitable for regular use"
        elif performance_score > 0.4:
            return "Average performance - use as backup option"
        else:
            return "Poor performance - consider alternative models"

    def _get_model_instance_url(self, model: str, available_instances: Optional[List[str]]) -> Optional[str]:
        """Get instance URL for model deployment."""

        # Simplified - would implement actual instance selection logic
        if available_instances:
            return available_instances[0]
        return None

    def get_orchestration_statistics(self) -> Dict[str, Any]:
        """Get model orchestration statistics."""

        total_requests = sum(m.total_requests for m in self.model_metrics.values())
        successful_requests = sum(m.successful_requests for m in self.model_metrics.values())

        return {
            "total_models": len(self.model_capabilities),
            "total_requests": total_requests,
            "overall_success_rate": successful_requests / max(total_requests, 1),
            "consensus_operations": len(self.consensus_history),
            "avg_consensus_agreement": (
                statistics.mean(c.agreement_level for c in self.consensus_history) if self.consensus_history else 0.0
            ),
            "model_performance": {
                model: {
                    "requests": metrics.total_requests,
                    "success_rate": metrics.successful_requests / max(metrics.total_requests, 1),
                    "avg_confidence": metrics.avg_confidence_score,
                    "health_score": metrics.health_score,
                }
                for model, metrics in self.model_metrics.items()
            },
        }
