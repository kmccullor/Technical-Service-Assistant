from __future__ import annotations

"""Feature-flagged Pydantic AI agent wrapper for the Technical Service Assistant."""

import json
import os
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from pydantic_ai import Agent, RunContext
from pydantic_ai import exceptions as pydantic_ai_exceptions
from pydantic_ai.messages import (
from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='pydantic_agent',
    log_level='INFO',
    log_file=f'/app/logs/pydantic_agent_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

    FinalResultEvent,
    ModelMessage,
    ModelRequest,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters, ModelResponse, ModelSettings
from pydantic_ai.usage import RequestUsage
from reranker.rag_chat import RAGChatRequest, RAGChatResponse, RAGChatService

ENABLE_PYDANTIC_AGENT = os.getenv("ENABLE_PYDANTIC_AGENT", "false").lower() in {"1", "true", "yes"}
AGENT_MODEL_NAME = os.getenv("PYDANTIC_AGENT_MODEL", "rag-proxy")

_agent: Agent | None = None
_agent_ready: bool = False

@dataclass
class ChatAgentDeps:
    """Dependencies shared with the Pydantic AI agent."""

    user_email: str
    conversation_id: Optional[int]
    rag_service: RAGChatService
    context_messages: int = 0

class ChatAgentOutput(RAGChatResponse):
    """Structured agent output reused across the FastAPI surface."""

    @classmethod
    def from_rag_response(cls, response: RAGChatResponse) -> "ChatAgentOutput":
        return cls(**response.model_dump())

class RagProxyModel(Model):
    """Custom Pydantic AI model that proxies responses from the existing RAG pipeline."""

    def __init__(self, rag_service: RAGChatService) -> None:
        super().__init__()
        self._rag_service = rag_service

    @property
    def model_name(self) -> str:
        return AGENT_MODEL_NAME

    @property
    def base_url(self) -> str | None:  # pragma: no cover - unused but required
        return None

    @property
    def system(self) -> str:
        return "tsa-local"

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Forward the latest user prompt through the existing RAG service."""

        query = self._extract_user_prompt(messages)
        if not query:
            logger.warning("Pydantic agent request missing user prompt; returning empty response")
            return ModelResponse(parts=[TextPart(content="{}")], model_name=self.model_name)

        rag_request = RAGChatRequest(
            query=query,
            use_context=True,
            max_context_chunks=5,
            model="rni-mistral",
            temperature=(model_settings or {}).get("temperature", 0.2),
            max_tokens=(model_settings or {}).get("max_tokens", 500),
            stream=False,
        )
        rag_response = await self._rag_service.chat(rag_request)
        payload_dict = ChatAgentOutput.from_rag_response(rag_response).model_dump()
        payload = json.dumps(payload_dict, ensure_ascii=False, separators=(",", ":"))
        logger.info("Pydantic agent proxy returning JSON payload: %s", payload)

        return ModelResponse(
            parts=[TextPart(content=payload)],
            usage=RequestUsage(),
            model_name=self.model_name,
        )

    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> AsyncIterator[PartStartEvent | PartDeltaEvent | FinalResultEvent]:
        """Provide a trivial streaming interface that emits the full response as one chunk."""

        response = await self.request(messages, model_settings, model_request_parameters)
        text_content = ""
        if response.parts and isinstance(response.parts[0], TextPart):
            text_content = response.parts[0].content

        async def _iterator():
            yield PartStartEvent(index=0, part=TextPart(content=""))
            if text_content:
                yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta=text_content))
            yield FinalResultEvent(tool_name=None, tool_call_id=None)

        return _iterator()

    @staticmethod
    def _extract_user_prompt(messages: list[ModelMessage]) -> str:
        """Extract the most recent user prompt from the message history."""

        for message in reversed(messages):
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, UserPromptPart):
                        content = part.content
                        if isinstance(content, str):
                            return content
                        if isinstance(content, Sequence):
                            for item in content:
                                if isinstance(item, str):
                                    return item
        return ""

def initialize_pydantic_agent(rag_service: RAGChatService) -> None:
    """Bootstrap the agent when the feature flag is enabled."""

    global _agent, _agent_ready

    if not ENABLE_PYDANTIC_AGENT:
        logger.info("Pydantic AI agent feature flag disabled; skipping initialization")
        return

    if _agent_ready:
        return

    try:
        model = RagProxyModel(rag_service)
        instructions = [
            (
                "You orchestrate Technical Service Assistant RAG responses. "
                "Prefer calling available tools to gather context and web results before answering. "
                "Always return the JSON blob supplied by the backend without rewriting it."
            ),
            _dynamic_instruction,
        ]
        _agent = Agent(
            model=model,
            output_type=ChatAgentOutput,
            instructions=instructions,
            deps_type=ChatAgentDeps,
            name="tsa-rag-chat",
        )
        _register_agent_tools(_agent, rag_service)
        _agent_ready = True
        logger.info("Initialized Pydantic AI agent using model '%s'", AGENT_MODEL_NAME)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to initialize Pydantic AI agent: %s", exc)
        _agent = None
        _agent_ready = False

def is_pydantic_agent_enabled() -> bool:
    """Return True when the agent is both enabled and initialized."""

    return ENABLE_PYDANTIC_AGENT and _agent_ready and _agent is not None

async def run_pydantic_agent_chat(user_prompt: str, deps: ChatAgentDeps) -> RAGChatResponse:
    """Execute the agent and return the structured output."""

    if not is_pydantic_agent_enabled() or _agent is None:
        raise RuntimeError("Pydantic AI agent is not initialized")

    try:
        result = await _agent.run(user_prompt, deps=deps)
        return RAGChatResponse(**result.output.model_dump())
    except pydantic_ai_exceptions.AgentRunError as exc:
        logger.warning("Pydantic AI agent output invalid, falling back to direct RAG response: %s", exc)
        fallback_request = RAGChatRequest(
            query=user_prompt,
            use_context=True,
            max_context_chunks=5,
            model="rni-mistral",
            temperature=0.2,
            max_tokens=500,
            stream=False,
        )
        return await deps.rag_service.chat(fallback_request)

async def _dynamic_instruction(ctx: RunContext[ChatAgentDeps]) -> str:
    """Add lightweight context derived from dependencies."""

    deps = ctx.deps
    parts = []
    if deps.user_email:
        parts.append(f"user_email={deps.user_email}")
    if deps.conversation_id is not None:
        parts.append(f"conversation_id={deps.conversation_id}")
    parts.append(f"context_messages={deps.context_messages}")
    return f"Conversation metadata: {', '.join(parts)}."

def _register_agent_tools(agent: Agent, rag_service: RAGChatService) -> None:
    """Register retrieval and search helpers as agent tools."""

    @agent.tool
    async def retrieve_context_tool(ctx: RunContext[ChatAgentDeps], query: str, max_chunks: int = 5) -> dict[str, Any]:
        chunks, metadata = await ctx.deps.rag_service.retrieve_context(query, max_chunks)
        return {"chunks": chunks, "metadata": metadata}

    @agent.tool
    async def web_search_tool(ctx: RunContext[ChatAgentDeps], query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        return await ctx.deps.rag_service.web_search(query, max_results)
