"""
Shared test fixtures for ORE test suite.
"""

from __future__ import annotations

from typing import Generator, List

import pytest

from ore.reasoner import Reasoner
from ore.types import Message, Response, Session


class FakeReasoner(Reasoner):
    """Deterministic reasoner that echoes prompts — no Ollama needed."""

    def __init__(self, canned: str = "fake response", model_id: str = "fake-model"):
        self.canned = canned
        self.model_id = model_id
        self.last_messages: List[Message] = []

    def reason(self, messages: List[Message]) -> Response:
        self.last_messages = list(messages)
        return Response(content=self.canned, model_id=self.model_id)

    def stream_reason(self, messages: List[Message]) -> Generator[str, None, Response]:
        self.last_messages = list(messages)
        # Yield canned response word-by-word to simulate streaming
        words = self.canned.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else f" {word}"
            yield chunk
        return Response(content=self.canned, model_id=self.model_id)


@pytest.fixture
def fake_reasoner() -> FakeReasoner:
    return FakeReasoner()


@pytest.fixture
def sample_session() -> Session:
    """Session pre-loaded with one user/assistant exchange."""
    session = Session()
    session.messages.append(Message(role="user", content="hello"))
    session.messages.append(Message(role="assistant", content="hi there"))
    return session
