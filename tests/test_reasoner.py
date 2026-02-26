"""Tests for ore/reasoner.py — Reasoner ABC and AyaReasoner with mocked Ollama."""

from __future__ import annotations

import time
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

    def test_reason_normalizes_ollama_token_fields_in_metadata(self):
        """Ollama native fields get normalized prompt_tokens, completion_tokens, total_tokens."""
        fake_client = MagicMock()
        fake_client.chat.return_value = _make_ollama_response(
            content="ok",
            eval_count=50,
            prompt_eval_count=30,
            eval_duration=0,
            prompt_eval_duration=0,
        )

        with patch("ollama.Client", return_value=fake_client):
            reasoner = AyaReasoner(model_id="m")

        resp = reasoner.reason([Message(role="user", content="x")])
        assert resp.metadata["prompt_tokens"] == 30
        assert resp.metadata["completion_tokens"] == 50
        assert resp.metadata["total_tokens"] == 80
        # Native fields unchanged
        assert resp.metadata["prompt_eval_count"] == 30
        assert resp.metadata["eval_count"] == 50

    def test_reason_sets_duration_ms(self):
        """reason() sets duration_ms from wall-clock timing of API call."""
        fake_client = MagicMock()

        def chat_slow(*args, **kwargs):
            time.sleep(0.02)
            return _make_ollama_response("ok")

        fake_client.chat.side_effect = chat_slow

        with patch("ollama.Client", return_value=fake_client):
            reasoner = AyaReasoner(model_id="m")

        resp = reasoner.reason([Message(role="user", content="x")])
        assert resp.duration_ms > 0

    def test_stream_reason_sets_duration_ms(self):
        """stream_reason() sets duration_ms from wall-clock timing."""
        chunks = [
            SimpleNamespace(
                message=SimpleNamespace(content="a"),
                eval_count=None,
                prompt_eval_count=None,
                eval_duration=None,
                prompt_eval_duration=None,
            ),
            SimpleNamespace(
                message=SimpleNamespace(content="b"),
                eval_count=1,
                prompt_eval_count=1,
                eval_duration=1,
                prompt_eval_duration=1,
            ),
        ]
        fake_client = MagicMock()

        def chat_stream(*args, **kwargs):
            time.sleep(0.02)
            return iter(chunks)

        fake_client.chat.side_effect = chat_stream

        with patch("ollama.Client", return_value=fake_client):
            reasoner = AyaReasoner(model_id="m")

        gen = reasoner.stream_reason([Message(role="user", content="hi")])
        try:
            while True:
                next(gen)
        except StopIteration as exc:
            resp = exc.value
        assert resp.duration_ms > 0

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
        assert resp.metadata["prompt_tokens"] == 5
        assert resp.metadata["completion_tokens"] == 10
        assert resp.metadata["total_tokens"] == 15
