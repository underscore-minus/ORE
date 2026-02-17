"""
Reasoner interface and Aya default implementation using Ollama (local LLM).
"""

from abc import ABC, abstractmethod
from typing import List

from ollama import Client

from .types import Message, Response


class Reasoner(ABC):
    """Abstract interface for a reasoning backend; v0.1 uses AyaReasoner (Ollama)."""

    @abstractmethod
    def reason(self, messages: List[Message]) -> Response:
        """Produce a single response from the given message list."""
        ...


class AyaReasoner(Reasoner):
    """Default reasoner: wraps Ollama chat for the ORE loop. No Aya persona here—that lives in core."""

    def __init__(self, model_id: str = "llama2") -> None:
        self._client = Client()
        self.model_id = model_id

    def reason(self, messages: List[Message]) -> Response:
        # Convert ORE Message objects to Ollama API format (role + content only)
        payload = [{"role": m.role, "content": m.content} for m in messages]

        raw = self._client.chat(model=self.model_id, messages=payload)

        # Ollama ChatResponse: message.content; optional eval_count, prompt_eval_count, eval_duration
        msg = getattr(raw, "message", None)
        content = (
            msg.content if hasattr(msg, "content") else (msg or {}).get("content", "")
        ) or ""
        metadata: dict = {}
        for key in (
            "eval_count",
            "prompt_eval_count",
            "eval_duration",
            "prompt_eval_duration",
        ):
            val = getattr(raw, key, None)
            if val is not None:
                metadata[key] = val

        return Response(
            content=content,
            model_id=self.model_id,
            metadata=metadata,
        )
