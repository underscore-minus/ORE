"""
DeepSeek reasoner: OpenAI-compatible API at api.deepseek.com.
Uses DEEPSEEK_API_KEY env var; fails with a clear error if missing.
"""

import os
import time
from typing import Generator, List

from openai import OpenAI

from .reasoner import Reasoner
from .types import Message, Response


def _get_api_key() -> str:
    """Read API key from DEEPSEEK_API_KEY; raise if missing."""
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "DEEPSEEK_API_KEY is not set. Set it in the environment to use the DeepSeek backend."
        )
    return key


class DeepSeekReasoner(Reasoner):
    """
    Reasoner implementation using the DeepSeek API (OpenAI-compatible).
    Requires DEEPSEEK_API_KEY in the environment.
    """

    def __init__(
        self,
        model_id: str = "deepseek-chat",
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
    ) -> None:
        self.model_id = model_id
        self._client = OpenAI(
            api_key=api_key if api_key is not None else _get_api_key(),
            base_url=base_url,
        )

    def reason(self, messages: List[Message]) -> Response:
        """Produce a single response from the given message list."""
        payload = [{"role": m.role, "content": m.content} for m in messages]
        start = time.perf_counter()
        completion = self._client.chat.completions.create(
            model=self.model_id,
            messages=payload,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        choice = completion.choices[0] if completion.choices else None
        content = (choice.message.content or "") if choice and choice.message else ""
        metadata: dict = {}
        if getattr(completion, "usage", None) is not None:
            usage = completion.usage
            if getattr(usage, "prompt_tokens", None) is not None:
                metadata["prompt_tokens"] = usage.prompt_tokens
            if getattr(usage, "completion_tokens", None) is not None:
                metadata["completion_tokens"] = usage.completion_tokens
            if getattr(usage, "total_tokens", None) is not None:
                metadata["total_tokens"] = usage.total_tokens
        return Response(
            content=content,
            model_id=self.model_id,
            metadata=metadata,
            duration_ms=duration_ms,
        )

    def stream_reason(self, messages: List[Message]) -> Generator[str, None, Response]:
        """Stream response chunks, then return the full Response."""
        payload = [{"role": m.role, "content": m.content} for m in messages]
        start = time.perf_counter()
        stream = self._client.chat.completions.create(
            model=self.model_id,
            messages=payload,
            stream=True,
        )
        full_content: list[str] = []
        metadata: dict = {}
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                text = chunk.choices[0].delta.content
                full_content.append(text)
                yield text
            # Last chunk may carry usage in some implementations
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage
                if getattr(usage, "prompt_tokens", None) is not None:
                    metadata["prompt_tokens"] = usage.prompt_tokens
                if getattr(usage, "completion_tokens", None) is not None:
                    metadata["completion_tokens"] = usage.completion_tokens
                if getattr(usage, "total_tokens", None) is not None:
                    metadata["total_tokens"] = usage.total_tokens
        duration_ms = int((time.perf_counter() - start) * 1000)
        return Response(
            content="".join(full_content),
            model_id=self.model_id,
            metadata=metadata,
            duration_ms=duration_ms,
        )
