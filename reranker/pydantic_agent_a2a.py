"""FastA2A server exposure for the Technical Service Assistant agent."""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fasta2a import FastA2A, Skill
from fasta2a.broker import InMemoryBroker
from fasta2a.schema import Artifact, Message, TaskIdParams, TaskSendParams
from fasta2a.storage import InMemoryStorage
from fasta2a.worker import Worker
from pydantic_agent import ChatAgentDeps, initialize_pydantic_agent, is_pydantic_agent_enabled, run_pydantic_agent_chat

from reranker.rag_chat import RAGChatResponse, RAGChatService

logger = logging.getLogger(__name__)


class TSAWorker(Worker[Dict[str, Any]]):
    """Worker that delegates execution to the feature-flagged Pydantic AI agent."""

    def __init__(self, broker: InMemoryBroker, storage: InMemoryStorage[Dict[str, Any]], rag_service: RAGChatService):
        super().__init__(broker=broker, storage=storage)
        self._rag_service = rag_service

    async def run_task(self, params: TaskSendParams) -> None:
        start_time = time.monotonic()
        task_id = params["id"]
        context_id = params["context_id"]
        message = params["message"]
        logger.info("TSAWorker processing task %s", task_id)

        await self.storage.update_task(task_id, state="working")
        prompt = self._extract_prompt(message)
        if not prompt:
            logger.warning("A2A message missing text content; marking task as failed")
            await self.storage.update_task(task_id, state="failed")
            return

        context = await self.storage.load_context(context_id) or {"message_count": 0, "conversation_id": None}
        deps = ChatAgentDeps(
            user_email=message.get("metadata", {}).get("user_email", "a2a-client"),
            conversation_id=context.get("conversation_id"),
            rag_service=self._rag_service,
            context_messages=context.get("message_count", 0),
        )

        try:
            agent_response = await run_pydantic_agent_chat(prompt, deps)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.exception(
                "Pydantic AI agent failed while handling A2A task %s after %sms: %s", task_id, duration_ms, exc
            )
            await self.storage.update_task(task_id, state="failed")
            return

        artifacts = self.build_artifacts(agent_response)
        agent_message = self._build_agent_message(agent_response)
        await self.storage.update_task(
            task_id,
            state="completed",
            new_artifacts=artifacts,
            new_messages=[agent_message],
        )
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info("TSAWorker marked task %s as completed in %sms", task_id, duration_ms)

        context["message_count"] = context.get("message_count", 0) + 1
        await self.storage.update_context(context_id, context)

    async def cancel_task(self, params: TaskIdParams) -> None:
        await self.storage.update_task(params["id"], state="canceled")

    def build_message_history(self, history: List[Message]) -> List[Any]:
        return history

    def build_artifacts(self, result: RAGChatResponse) -> List[Artifact]:
        artifact_id = str(uuid.uuid4())
        return [
            Artifact(
                artifact_id=artifact_id,
                name="assistant_response",
                parts=[
                    {
                        "kind": "text",
                        "text": result.response,
                    }
                ],
                metadata={
                    "web_sources": result.web_sources,
                    "context_metadata": result.context_metadata,
                },
            )
        ]

    def _build_agent_message(self, response: RAGChatResponse) -> Message:
        message_id = str(uuid.uuid4())
        return Message(
            role="agent",
            kind="message",
            message_id=message_id,
            parts=[
                {
                    "kind": "text",
                    "text": response.response,
                }
            ],
            metadata={
                "web_sources": response.web_sources,
                "context_used": response.context_used,
            },
        )

    @staticmethod
    def _extract_prompt(message: Message) -> str:
        for part in message.get("parts", []):
            part_kind = part.get("kind") or part.get("type")
            if part_kind in {"input_text", "text"}:
                return part.get("text", "")
        return ""


@dataclass
class A2AService:
    """Wrapper that owns the FastA2A app and its worker lifecycle."""

    rag_service: RAGChatService
    storage: InMemoryStorage[Dict[str, Any]] = field(default_factory=InMemoryStorage)
    broker: InMemoryBroker = field(default_factory=InMemoryBroker)
    worker: Optional[TSAWorker] = field(init=False, default=None)
    app: Optional[FastA2A] = field(init=False, default=None)
    _worker_cm: Any = field(init=False, default=None)
    _app_cm: Any = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.worker = TSAWorker(self.broker, self.storage, self.rag_service)
        base_url = os.getenv("A2A_BASE_URL", "http://localhost:8008/a2a")
        skills: List[Skill] = [
            Skill(
                name="technical-service-chat",
                description="Answer Technical Service Assistant questions with citations.",
                examples=["Explain the RNI 4.16 architecture", "Walk me through troubleshooting meter read failures"],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
        ]
        self.app = FastA2A(
            storage=self.storage,
            broker=self.broker,
            name="Technical Service Assistant",
            url=base_url,
            version="1.0.0",
            description="Enterprise Technical Service Assistant exposed via the Agent2Agent protocol.",
            skills=skills,
        )

    async def startup(self) -> None:
        if self._worker_cm is not None:
            return
        self._app_cm = self.app.router.lifespan_context(self.app)
        await self._app_cm.__aenter__()
        self._worker_cm = self.worker.run()
        await self._worker_cm.__aenter__()
        logger.info("A2A worker started")

    async def shutdown(self) -> None:
        if self._worker_cm:
            await self._worker_cm.__aexit__(None, None, None)
            self._worker_cm = None
        if self._app_cm:
            await self._app_cm.__aexit__(None, None, None)
            self._app_cm = None
        logger.info("A2A worker stopped")


def create_a2a_service(rag_service: RAGChatService) -> A2AService:
    if not is_pydantic_agent_enabled():
        initialize_pydantic_agent(rag_service)
    if not is_pydantic_agent_enabled():
        raise RuntimeError("Pydantic AI agent must be enabled before exposing the A2A endpoint")
    return A2AService(rag_service=rag_service)
