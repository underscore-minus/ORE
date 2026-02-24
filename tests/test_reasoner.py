"""Tests for ore/reasoner.py — Reasoner ABC and AyaReasoner with mocked Ollama."""

from __future__ import annotations

from types import SimpleNamespace
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from ore.reasoner import AyaReasoner, Reasoner
from ore.types import Message, Response


@pytest.mark.invariant
def test_reasoner_abc_has_required_members():
    """Invariant: Reasoner ABC defines reason() and stream_reason()."""
    assert hasattr(Reasoner, "reason") and callable(getattr(Reasoner, "reason"))
    assert hasattr(Reasoner, "stream_reason") and callable(
        getattr(Reasoner, "stream_reason")
    )


class TestReasonerABC:
    """Verify the base class contract and default stream_reason fallback."""

    def test_default_stream_reason_yields_full_content(self):
        class Echo(Reasoner):
            def reason(self, messages: List[Message]) -> Response:
                return Response(content="echo", model_id="echo")

        r = Echo()
        gen = r.stream_reason([Message(role="user", content="hi")])
        chunks = []
        try:
            while True:
                chunks.append(next(gen))
        except StopIteration as exc:
            resp = exc.value
        assert chunks == ["echo"]
        assert resp.content == "echo"


def _make_ollama_response(
    content: str = "ok",
    eval_count: int = 5,
    prompt_eval_count: int = 3,
    eval_duration: int = 100,
    prompt_eval_duration: int = 50,
) -> SimpleNamespace:
    """Build a fake Ollama ChatResponse-like object."""
    return SimpleNamespace(
        message=SimpleNamespace(content=content),
        eval_count=eval_count,
        prompt_eval_count=prompt_eval_count,
        eval_duration=eval_duration,
        prompt_eval_duration=prompt_eval_duration,
    )


class TestAyaReasoner:
    def test_reason_converts_messages(self):
        fake_client = MagicMock()
        fake_client.chat.return_value = _make_ollama_response("hello back")

        with patch("ollama.Client", return_value=fake_client):
            reasoner = AyaReasoner(model_id="test-model")

        msgs = [
            Message(role="system", content="you are Aya"),
            Message(role="user", content="hi"),
        ]
        resp = reasoner.reason(msgs)

        # Verify the payload sent to Ollama
        call_kwargs = fake_client.chat.call_args
        payload = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        assert payload == [
            {"role": "system", "content": "you are Aya"},
            {"role": "user", "content": "hi"},
        ]
        assert resp.content == "hello back"
        assert resp.model_id == "test-model"

    def test_reason_extracts_metadata(self):
        fake_client = MagicMock()
        fake_client.chat.return_value = _make_ollama_response(
            eval_count=10,
            prompt_eval_count=5,
            eval_duration=200,
            prompt_eval_duration=100,
        )

        with patch("ollama.Client", return_value=fake_client):
            reasoner = AyaReasoner(model_id="m")

        resp = reasoner.reason([Message(role="user", content="x")])
        assert resp.metadata["eval_count"] == 10
        assert resp.metadata["prompt_eval_count"] == 5
        assert resp.metadata["eval_duration"] == 200
        assert resp.metadata["prompt_eval_duration"] == 100

    def test_stream_reason_yields_chunks(self):
        # Simulate Ollama streaming: list of chunk objects
        chunks = [
            SimpleNamespace(
                message=SimpleNamespace(content="hello"),
                eval_count=None,
                prompt_eval_count=None,
                eval_duration=None,
                prompt_eval_duration=None,
            ),
            SimpleNamespace(
                message=SimpleNamespace(content=" world"),
                eval_count=10,
                prompt_eval_count=5,
                eval_duration=200,
                prompt_eval_duration=100,
            ),
        ]
        fake_client = MagicMock()
        fake_client.chat.return_value = iter(chunks)

        with patch("ollama.Client", return_value=fake_client):
            reasoner = AyaReasoner(model_id="m")

        gen = reasoner.stream_reason([Message(role="user", content="hi")])
        collected = []
        try:
            while True:
                collected.append(next(gen))
        except StopIteration as exc:
            resp = exc.value

        assert collected == ["hello", " world"]
        assert resp.content == "hello world"
        assert resp.metadata["eval_count"] == 10
