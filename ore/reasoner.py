"""
Reasoner interface and Aya default implementation using Ollama (local LLM).
"""

from abc import ABC, abstractmethod
from typing import Generator, List

from .types import Message, Response


class Reasoner(ABC):
    """Abstract interface for a reasoning backend; v0.1 uses AyaReasoner (Ollama)."""

    @abstractmethod
    def reason(self, messages: List[Message]) -> Response:
        """Produce a single response from the given message list."""
        ...

    def stream_reason(self, messages: List[Message]) -> Generator[str, None, Response]:
        """Streaming mode. Default: emits full content in one chunk via reason()."""
        response = self.reason(messages)
        yield response.content
        return response


class AyaReasoner(Reasoner):
    """Default reasoner: wraps Ollama chat for the ORE loop. No persona here—consumers provide it (e.g. CLI via `--system`)."""

    def __init__(self, model_id: str = "llama2") -> None:
        from ollama import Client

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

    def stream_reason(self, messages: List[Message]) -> Generator[str, None, Response]:
        payload = [{"role": m.role, "content": m.content} for m in messages]
        full_content: list[str] = []
        metadata: dict = {}
        for chunk in self._client.chat(
            model=self.model_id, messages=payload, stream=True
        ):
            msg = getattr(chunk, "message", None)
            text = (getattr(msg, "content", None) or "") if msg else ""
            if text:
                full_content.append(text)
                yield text
            for key in (
                "eval_count",
                "prompt_eval_count",
                "eval_duration",
                "prompt_eval_duration",
            ):
                val = getattr(chunk, key, None)
                if val is not None:
                    metadata[key] = val
        return Response(
            content="".join(full_content),
            model_id=self.model_id,
            metadata=metadata,
        )
