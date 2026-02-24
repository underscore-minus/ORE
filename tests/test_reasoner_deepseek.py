"""Tests for ore/reasoner_deepseek.py — DeepSeekReasoner with mocked OpenAI client."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ore.reasoner_deepseek import DeepSeekReasoner
from ore.types import Message, Response


def test_missing_api_key_raises():
    """DeepSeekReasoner raises ValueError when DEEPSEEK_API_KEY is not set."""
    with patch.dict("os.environ", {}, clear=False):
        # Remove key if it exists
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": ""}, clear=False):
            with pytest.raises(ValueError) as excinfo:
                DeepSeekReasoner(model_id="deepseek-chat")
    assert "DEEPSEEK_API_KEY" in str(excinfo.value)


def test_reason_converts_messages():
    """reason() sends correct payload and returns Response with content and metadata."""
    fake_completion = MagicMock()
    fake_completion.choices = [
        MagicMock(message=MagicMock(content="hello from deepseek"))
    ]
    fake_completion.usage = MagicMock(
        prompt_tokens=10, completion_tokens=5, total_tokens=15
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_completion

    with patch("ore.reasoner_deepseek.OpenAI", return_value=fake_client):
        reasoner = DeepSeekReasoner(model_id="deepseek-chat", api_key="test-key")

    msgs = [
        Message(role="system", content="You are helpful."),
        Message(role="user", content="Hi"),
    ]
    resp = reasoner.reason(msgs)

    create_kw = fake_client.chat.completions.create.call_args
    assert create_kw.kwargs["model"] == "deepseek-chat"
    assert create_kw.kwargs["messages"] == [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
    ]
    assert resp.content == "hello from deepseek"
    assert resp.model_id == "deepseek-chat"
    assert resp.metadata["prompt_tokens"] == 10
    assert resp.metadata["completion_tokens"] == 5
    assert resp.metadata["total_tokens"] == 15


def test_reason_no_usage_metadata():
    """reason() works when completion has no usage (metadata stays empty or minimal)."""
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=MagicMock(content="ok"))]
    fake_completion.usage = None
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_completion

    with patch("ore.reasoner_deepseek.OpenAI", return_value=fake_client):
        reasoner = DeepSeekReasoner(model_id="deepseek-chat", api_key="test-key")

    resp = reasoner.reason([Message(role="user", content="x")])
    assert resp.content == "ok"
    assert resp.model_id == "deepseek-chat"
    assert resp.metadata == {}


def test_stream_reason_yields_chunks_and_returns_response():
    """stream_reason() yields content chunks and returns full Response."""
    chunk1 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))],
        usage=None,
    )
    chunk2 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=" world"))],
        usage=None,
    )
    chunk3 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None))],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=2, total_tokens=4),
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = iter([chunk1, chunk2, chunk3])

    with patch("ore.reasoner_deepseek.OpenAI", return_value=fake_client):
        reasoner = DeepSeekReasoner(model_id="deepseek-chat", api_key="test-key")

    gen = reasoner.stream_reason([Message(role="user", content="hi")])
    collected = []
    try:
        while True:
            collected.append(next(gen))
    except StopIteration as exc:
        resp = exc.value

    assert collected == ["hello", " world"]
    assert resp.content == "hello world"
    assert resp.model_id == "deepseek-chat"
    assert resp.metadata.get("total_tokens") == 4
