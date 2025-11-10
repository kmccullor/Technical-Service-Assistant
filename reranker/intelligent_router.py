import os

from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="intelligent_router",
    log_level="INFO",
    console_output=True,
)

"""
Dynamic Ollama Instance Router

Intelligently selects the best available Ollama instance and model based on:
- Question type analysis (technical, creative, factual, code, math)
- Instance health and availability
- Model capabilities and load balancing

Follows Pydantic AI patterns from https://ai.pydantic.dev/
"""

import asyncio
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple

import httpx
from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Question categories for model selection."""

    TECHNICAL = "technical"  # Documentation, troubleshooting, system config
    CODE = "code"  # Programming, scripts, syntax
    CREATIVE = "creative"  # Stories, creative writing, brainstorming
    FACTUAL = "factual"  # Direct Q&A, definitions, explanations
    MATH = "math"  # Calculations, formulas, numerical
    CHAT = "chat"  # Casual conversation, greetings


class ModelCapability(BaseModel):
    """Model capability profile."""

    name: str
    strengths: List[QuestionType]
    context_length: int = 4096
    speed_tier: int = Field(1, ge=1, le=3, description="1=fast, 2=medium, 3=slow")
    quality_tier: int = Field(1, ge=1, le=3, description="1=basic, 2=good, 3=excellent")


@dataclass
class OllamaInstance:
    """Ollama instance configuration."""

    host: str
    port: int
    name: str
    healthy: bool = True
    last_check: float = 0
    response_time: float = 0
    load_score: float = 0  # Lower is better

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class ModelSelectionRequest(BaseModel):
    """Request for intelligent model selection."""

    query: str = Field(..., description="User question/prompt")
    prefer_speed: bool = Field(False, description="Prioritize speed over quality")
    require_context: bool = Field(False, description="Needs large context window")
    exclude_models: List[str] = Field(default_factory=list, description="Models to avoid")


class ModelSelectionResponse(BaseModel):
    """Response with selected model and instance."""

    selected_model: str
    selected_instance: str
    instance_url: str
    question_type: QuestionType
    reasoning: str
    fallback_options: List[Dict[str, str]] = Field(default_factory=list)


class IntelligentRouter:
    """Dynamic Ollama router with model intelligence."""

    def __init__(self):
        # Use OLLAMA_INSTANCES environment variable if available, otherwise fallback to defaults
        instances_str = os.getenv("OLLAMA_INSTANCES")
        if instances_str:
            # Parse comma-separated URLs like "http://host1:port1,http://host2:port2"
            instance_urls = [url.strip() for url in instances_str.split(",")]
            self.instances = []
            for i, url in enumerate(instance_urls):
                # Extract host and port from URL
                if url.startswith("http://"):
                    url = url[7:]  # Remove http://
                if ":" in url:
                    host, port_str = url.rsplit(":", 1)
                    try:
                        port = int(port_str)
                    except ValueError:
                        port = 11434  # fallback
                else:
                    host = url
                    port = 11434

                # Determine role based on index
                if i == 0:
                    role = "primary"
                elif i == 1:
                    role = "secondary"
                elif i == 2:
                    role = "tertiary"
                elif i == 3:
                    role = "quaternary"
                else:
                    role = "additional"

                self.instances.append(OllamaInstance(host, port, role))
        else:
            # Fallback to hardcoded defaults
            self.instances = [
                OllamaInstance("ollama-server-1", 11434, "primary"),
                OllamaInstance("ollama-server-2", 11434, "secondary"),
                OllamaInstance("ollama-server-3", 11434, "tertiary"),
                OllamaInstance("ollama-server-4", 11434, "quaternary"),
                OllamaInstance("ollama-server-5", 11434, "additional"),
                OllamaInstance("ollama-server-6", 11434, "additional"),
                OllamaInstance("ollama-server-7", 11434, "additional"),
                OllamaInstance("ollama-server-8", 11434, "additional"),
            ]

        # Health check caching
        self.last_health_check = 0
        self.health_check_cache_duration = 30  # seconds

        # Model capability definitions - Updated for specialized instances
        chat_model = os.getenv("CHAT_MODEL", "mistral:7b")
        coding_model = os.getenv("CODING_MODEL", "codellama:7b")
        reasoning_model = os.getenv("REASONING_MODEL", "llama3.2:3b")
        vision_model = os.getenv("VISION_MODEL", "llava:7b")

        self.model_profiles = {
            chat_model: ModelCapability(
                name=chat_model,
                strengths=[QuestionType.TECHNICAL, QuestionType.FACTUAL, QuestionType.CHAT],
                context_length=8192,
                speed_tier=2,
                quality_tier=3,
            ),
            coding_model: ModelCapability(
                name=coding_model,
                strengths=[QuestionType.CODE, QuestionType.TECHNICAL],
                context_length=4096,
                speed_tier=1,
                quality_tier=2,
            ),
            reasoning_model: ModelCapability(
                name=reasoning_model,
                strengths=[QuestionType.MATH, QuestionType.FACTUAL, QuestionType.TECHNICAL],
                context_length=4096,
                speed_tier=1,
                quality_tier=2,
            ),
            vision_model: ModelCapability(
                name=vision_model,
                strengths=[QuestionType.TECHNICAL, QuestionType.FACTUAL],  # Vision models can handle visual Q&A
                context_length=4096,
                speed_tier=2,
                quality_tier=2,
            ),
            "llama3.2:1b": ModelCapability(
                name="llama3.2:1b",
                strengths=[QuestionType.FACTUAL, QuestionType.CHAT],
                context_length=2048,
                speed_tier=1,
                quality_tier=1,
            ),
            "gemma2:2b": ModelCapability(
                name="gemma2:2b",
                strengths=[QuestionType.CODE, QuestionType.FACTUAL],
                context_length=4096,
                speed_tier=1,
                quality_tier=2,
            ),
            "phi3:mini": ModelCapability(
                name="phi3:mini",
                strengths=[QuestionType.CODE, QuestionType.TECHNICAL],
                context_length=4096,
                speed_tier=1,
                quality_tier=2,
            ),
            "nomic-embed-text:v1.5": ModelCapability(
                name="nomic-embed-text:v1.5",
                strengths=[],  # Embedding model, not for generation
                context_length=2048,
                speed_tier=1,
                quality_tier=1,
            ),
            "nomic-embed-text:latest": ModelCapability(
                name="nomic-embed-text:latest",
                strengths=[],  # Embedding model, not for generation
                context_length=2048,
                speed_tier=1,
                quality_tier=1,
            ),
        }

        def _unique_models(models):
            seen = []
            for m in models:
                if m and m not in seen:
                    seen.append(m)
            return seen

        general_models = _unique_models([chat_model, "mistral:7b", "mistral:latest", "llama3.1:8b"])
        code_models = _unique_models([coding_model, "mistral:7b", "gemma2:2b", "phi3:mini"])
        reasoning_models = _unique_models([reasoning_model, "llama3.1:8b", "llama3.2:3b", "mistral:latest"])
        embedding_models = _unique_models([os.getenv("EMBEDDING_MODEL", "nomic-embed-text:v1.5"), "nomic-embed-text:v1.5", "nomic-embed-text:latest"])

        # Instance specialization mapping
        self.instance_specializations = {
            1: {  # General Chat & Document QA (11434)
                "primary_models": general_models,
                "strengths": [QuestionType.CHAT, QuestionType.FACTUAL, QuestionType.TECHNICAL],
                "description": "General chat and document QA",
            },
            2: {  # Code & Technical Analysis (11435)
                "primary_models": code_models,
                "strengths": [QuestionType.CODE, QuestionType.TECHNICAL],
                "description": "Code and technical analysis",
            },
            3: {  # Advanced Reasoning & Math (11436)
                "primary_models": reasoning_models,
                "strengths": [QuestionType.MATH, QuestionType.TECHNICAL],
                "description": "Advanced reasoning and math",
            },
            4: {  # Embeddings & Search Optimization (11437)
                "primary_models": embedding_models,
                "strengths": [],  # Embedding-focused
                "description": "Embeddings and search optimization",
            },
        }

        self.health_check_interval = 30  # seconds

    def classify_question(self, query: str) -> QuestionType:
        """Analyze question to determine type."""
        query_lower = query.lower()

        # Technical/documentation patterns
        if any(
            term in query_lower
            for term in [
                "install",
                "config",
                "setup",
                "error",
                "troubleshoot",
                "rni",
                "active directory",
                "database",
                "server",
                "network",
                "security",
                "documentation",
                "manual",
                "guide",
                "prerequisite",
            ]
        ):
            return QuestionType.TECHNICAL

        # Code patterns
        if any(
            term in query_lower
            for term in [
                "code",
                "script",
                "function",
                "class",
                "variable",
                "syntax",
                "programming",
                "python",
                "javascript",
                "sql",
                "api",
                "debug",
                "algorithm",
                "implementation",
            ]
        ) or re.search(r"def |class |import |function|console\.log|SELECT|UPDATE", query):
            return QuestionType.CODE

        # Math patterns
        if any(
            term in query_lower
            for term in [
                "calculate",
                "formula",
                "equation",
                "math",
                "number",
                "percentage",
                "sum",
                "average",
                "statistics",
            ]
        ) or re.search(r"\d+[\+\-\*/]\d+|what is \d+", query_lower):
            return QuestionType.MATH

        # Creative patterns
        if any(
            term in query_lower
            for term in [
                "story",
                "creative",
                "write",
                "poem",
                "idea",
                "brainstorm",
                "imagine",
                "fiction",
                "character",
                "plot",
            ]
        ):
            return QuestionType.CREATIVE

        # Chat/greeting patterns
        if (
            any(term in query_lower for term in ["hello", "hi", "hey", "thanks", "thank you", "how are you"])
            or len(query.split()) < 4
        ):
            return QuestionType.CHAT

        # Default to factual
        return QuestionType.FACTUAL

    async def check_instance_health(self, instance: OllamaInstance) -> bool:
        """Check if an Ollama instance is healthy."""
        try:
            start_time = time.time()
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{instance.url}/api/tags", timeout=5.0)

            response_time = time.time() - start_time
            instance.response_time = response_time
            instance.last_check = time.time()

            if response.status_code == 200:
                # Update load score based on response time
                instance.load_score = response_time
                instance.healthy = True
                return True
            else:
                instance.healthy = False
                return False

        except Exception as e:
            logger.warning(f"Health check failed for {instance.name}: {e}")
            instance.healthy = False
            instance.last_check = time.time()
            return False

    async def get_available_models(self, instance: OllamaInstance) -> List[str]:
        """Get list of available models on an instance."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{instance.url}/api/tags", timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                models = [model.get("name", "").split(":")[0] for model in data.get("models", [])]
                return [m for m in models if m]  # Filter out empty names
            return []
        except Exception as e:
            logger.error(f"Failed to get models from {instance.name}: {e}")
            return []

    async def refresh_health_status(self):
        """Refresh health status for all instances with caching."""
        current_time = time.time()

        # Check if we need to refresh (cache duration expired)
        if current_time - self.last_health_check < self.health_check_cache_duration:
            logger.debug(f"Using cached health status (age: {current_time - self.last_health_check:.1f}s)")
            return

        # Perform fresh health checks
        self.last_health_check = current_time
        tasks = [self.check_instance_health(instance) for instance in self.instances]
        await asyncio.gather(*tasks, return_exceptions=True)

        healthy_count = sum(1 for i in self.instances if i.healthy)
        logger.info(f"Health check complete: {healthy_count}/{len(self.instances)} instances healthy")

    async def refresh_health_status_force(self):
        """Force refresh health status for all instances (ignore cache)."""
        self.last_health_check = 0  # Reset cache
        await self.refresh_health_status()

    def select_best_model_for_instance(
        self,
        question_type: QuestionType,
        instance_num: int,
        prefer_speed: bool,
        require_context: bool,
        exclude_models: List[str],
    ) -> Tuple[str, str]:
        """Select best model for question type on specific instance."""
        # Get available models for this instance
        instance_spec = self.instance_specializations.get(instance_num, {})
        available_models = instance_spec.get("primary_models", [])

        # Filter candidates from available models on this instance
        candidates = []
        for model_name in available_models:
            if model_name in exclude_models:
                continue
            if "embed" in model_name.lower():  # Skip embedding models
                continue

            profile = self.model_profiles.get(model_name)
            if not profile:
                continue

            if require_context and profile.context_length < 8192:
                continue

            # Score based on suitability
            score = 0
            if question_type in profile.strengths:
                score += 3
            if prefer_speed:
                score += 4 - profile.speed_tier  # Higher score for faster models
            else:
                score += profile.quality_tier  # Higher score for better quality

            candidates.append((model_name, score, profile))

        if not candidates:
            # Fallback to any available model on the instance
            fallback_models = [m for m in available_models if "embed" not in m.lower()]
            if fallback_models:
                return fallback_models[0], f"Fallback model on instance {instance_num}"
            return "mistral:7b", "Global fallback model"

        # Select highest scoring model
        best_model, _, profile = max(candidates, key=lambda x: x[1])

        reasoning = f"Selected {best_model} on instance {instance_num} for {question_type.value}"
        if question_type in profile.strengths:
            reasoning += " (specialized)"
        if prefer_speed and profile.speed_tier == 1:
            reasoning += " (fast)"
        if profile.quality_tier == 3:
            reasoning += " (high quality)"

        return best_model, reasoning

    def select_best_model(
        self, question_type: QuestionType, prefer_speed: bool, require_context: bool, exclude_models: List[str]
    ) -> Tuple[str, str]:
        """Select best model for question type (legacy method for compatibility)."""
        # Use instance 1 (general) as default for backward compatibility
        return self.select_best_model_for_instance(question_type, 1, prefer_speed, require_context, exclude_models)

    def select_specialized_instance(self, question_type: QuestionType) -> OllamaInstance:
        """Select best specialized instance for question type."""
        # Find instances specialized for this question type
        specialized_instances = []
        for i, instance in enumerate(self.instances, 1):
            if not instance.healthy:
                continue

            spec = self.instance_specializations.get(i, {})
            if question_type in spec.get("strengths", []):
                specialized_instances.append((instance, i))

        if specialized_instances:
            # Select the least loaded specialized instance
            best_instance, instance_num = min(specialized_instances, key=lambda x: x[0].load_score)
            spec_desc = self.instance_specializations[instance_num]["description"]
            logger.info(f"Selected specialized instance {instance_num} ({spec_desc}) for {question_type.value}")
            return best_instance

        # Fallback to general instance selection
        return self.select_best_instance()

    def select_best_instance(self) -> OllamaInstance:
        """Select best available instance based on health and load."""
        healthy_instances = [i for i in self.instances if i.healthy]

        if not healthy_instances:
            logger.warning("No healthy instances available, using primary")
            return self.instances[0]  # Fallback to primary

        # Select instance with lowest load score
        best_instance = min(healthy_instances, key=lambda i: i.load_score)
        return best_instance

    async def route_request(self, request: ModelSelectionRequest) -> ModelSelectionResponse:
        """Main routing logic with specialized instance selection."""
        # Classify the question
        question_type = self.classify_question(request.query)

        # Refresh health if needed
        current_time = time.time()
        if any(current_time - i.last_check > self.health_check_interval for i in self.instances):
            await self.refresh_health_status()

        # Select specialized instance for this question type
        selected_instance = self.select_specialized_instance(question_type)

        # Get instance number for model selection
        instance_num = next((i for i, inst in enumerate(self.instances, 1) if inst == selected_instance), 1)

        # Select best model for the specialized instance
        selected_model, reasoning = self.select_best_model_for_instance(
            question_type, instance_num, request.prefer_speed, request.require_context, request.exclude_models
        )

        # Build fallback options
        fallback_options = []
        for instance in self.instances:
            if instance != selected_instance and instance.healthy:
                fallback_options.append(
                    {"instance": instance.name, "url": instance.url, "load_score": f"{instance.load_score:.2f}s"}
                )

        return ModelSelectionResponse(
            selected_model=selected_model,
            selected_instance=selected_instance.name,
            instance_url=selected_instance.url,
            question_type=question_type,
            reasoning=reasoning,
            fallback_options=fallback_options[:2],  # Limit to top 2 fallbacks
        )


# Global router instance
intelligent_router = IntelligentRouter()


def add_intelligent_routing_endpoints(app):
    """Add intelligent routing endpoints to FastAPI app."""
    print("Adding intelligent routing endpoints...")

    async def intelligent_route(request: ModelSelectionRequest):
        """Get optimal model and instance selection for a query."""
        return await intelligent_router.route_request(request)

    async def ollama_health():
        """Check health status of all Ollama instances."""
        await intelligent_router.refresh_health_status()

        status_summary = []
        for instance in intelligent_router.instances:
            status_summary.append(
                {
                    "name": instance.name,
                    "url": instance.url,
                    "healthy": instance.healthy,
                    "response_time": f"{instance.response_time:.2f}s" if instance.response_time > 0 else "unknown",
                    "load_score": f"{instance.load_score:.2f}" if instance.load_score > 0 else "unknown",
                    "last_check": instance.last_check,
                }
            )

        healthy_count = sum(1 for i in intelligent_router.instances if i.healthy)

        return {
            "status": "healthy" if healthy_count > 0 else "degraded",
            "healthy_instances": healthy_count,
            "total_instances": len(intelligent_router.instances),
            "instances": status_summary,
        }

    app.add_api_route(
        "/api/intelligent-route", intelligent_route, methods=["POST"], response_model=ModelSelectionResponse
    )
    app.add_api_route("/api/ollama-health", ollama_health, methods=["GET"])
