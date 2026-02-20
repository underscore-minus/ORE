"""Tests for ore/core.py — ORE orchestrator logic."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ore.core import ORE, load_aya_system_prompt
from ore.types import Session

from .conftest import FakeReasoner


class TestLoadAyaSystemPrompt:
    def test_loads_text(self):
        prompt = load_aya_system_prompt()
        assert "Aya" in prompt
        assert len(prompt) > 0

    def test_missing_file_raises(self, tmp_path):
        fake_path = tmp_path / "missing.txt"
        with patch("ore.core.AYA_PROMPT_PATH", fake_path):
            with pytest.raises(RuntimeError, match="not found"):
                load_aya_system_prompt()


class TestOREExecute:
    def test_single_turn_message_list(self, fake_reasoner: FakeReasoner):
        engine = ORE(fake_reasoner)
        engine.execute("hi")
        msgs = fake_reasoner.last_messages
        # Expect [system, user]
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"
        assert msgs[1].content == "hi"

    def test_single_turn_returns_response(self, fake_reasoner: FakeReasoner):
        engine = ORE(fake_reasoner)
        resp = engine.execute("hi")
        assert resp.content == "fake response"
        assert resp.model_id == "fake-model"

    def test_no_session_no_side_effects(self, fake_reasoner: FakeReasoner):
        engine = ORE(fake_reasoner)
        engine.execute("hi")
        # No session → nothing to mutate
        engine.execute("bye")
        msgs = fake_reasoner.last_messages
        assert len(msgs) == 2  # still just [system, user]

    def test_with_session_includes_history(
        self, fake_reasoner: FakeReasoner, sample_session: Session
    ):
        engine = ORE(fake_reasoner)
        engine.execute("follow up", session=sample_session)
        msgs = fake_reasoner.last_messages
        # [system, prior_user, prior_assistant, new_user]
        assert len(msgs) == 4
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"
        assert msgs[1].content == "hello"
        assert msgs[2].role == "assistant"
        assert msgs[2].content == "hi there"
        assert msgs[3].role == "user"
        assert msgs[3].content == "follow up"

    def test_session_grows_after_execute(self, fake_reasoner: FakeReasoner):
        engine = ORE(fake_reasoner)
        session = Session()
        assert len(session.messages) == 0

        engine.execute("first", session=session)
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "first"
        assert session.messages[1].role == "assistant"
        assert session.messages[1].content == "fake response"

        engine.execute("second", session=session)
        assert len(session.messages) == 4

    def test_system_prompt_not_in_session(self, fake_reasoner: FakeReasoner):
        engine = ORE(fake_reasoner)
        session = Session()
        engine.execute("test", session=session)
        # Session should only have user + assistant, never system
        for msg in session.messages:
            assert msg.role != "system"


class TestOREExecuteStream:
    def test_stream_yields_chunks(self, fake_reasoner: FakeReasoner):
        engine = ORE(fake_reasoner)
        gen = engine.execute_stream("hi")
        chunks = []
        try:
            while True:
                chunks.append(next(gen))
        except StopIteration as exc:
            response = exc.value
        assert len(chunks) > 0
        assert response.content == "fake response"

    def test_stream_updates_session(self, fake_reasoner: FakeReasoner):
        engine = ORE(fake_reasoner)
        session = Session()
        gen = engine.execute_stream("hi", session=session)
        # Exhaust the generator
        try:
            while True:
                next(gen)
        except StopIteration:
            pass
        assert len(session.messages) == 2
        assert session.messages[0].content == "hi"
        assert session.messages[1].content == "fake response"
