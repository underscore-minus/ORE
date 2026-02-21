"""Tests for ore/core.py — ORE orchestrator logic."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ore.core import ORE, load_aya_system_prompt
from ore.types import Session, ToolResult

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

    @pytest.mark.invariant
    def test_reasoner_called_exactly_once_per_execute(
        self, fake_reasoner: FakeReasoner, sample_session: Session
    ):
        """Invariant: one reasoner.reason() call per ORE.execute()."""
        engine = ORE(fake_reasoner)
        engine.execute("hi")
        assert fake_reasoner.reason_call_count == 1
        engine.execute("bye")
        assert fake_reasoner.reason_call_count == 2
        engine.execute("third", session=sample_session)
        assert fake_reasoner.reason_call_count == 3

    @pytest.mark.invariant
    def test_session_append_only_no_reorder_or_delete(
        self, fake_reasoner: FakeReasoner, sample_session: Session
    ):
        """Invariant: session is append-only; no reorder, no delete of existing messages."""
        engine = ORE(fake_reasoner)
        initial_ids = [m.id for m in sample_session.messages]
        initial_len = len(sample_session.messages)
        engine.execute("next", session=sample_session)
        assert len(sample_session.messages) == initial_len + 2
        assert [m.id for m in sample_session.messages[:initial_len]] == initial_ids

    @pytest.mark.invariant
    def test_tool_results_injected_before_session(
        self, fake_reasoner: FakeReasoner, sample_session: Session
    ):
        """Invariant: message order is [system, tool_msg, session..., user]."""
        engine = ORE(fake_reasoner)
        tr = ToolResult(tool_name="echo", output="tool out", status="ok")
        engine.execute("user prompt", session=sample_session, tool_results=[tr])
        msgs = fake_reasoner.last_messages
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"
        assert "[Tool:echo]" in msgs[1].content
        assert "tool out" in msgs[1].content
        assert msgs[2].role == "user"
        assert msgs[2].content == "hello"
        assert msgs[3].role == "assistant"
        assert msgs[4].role == "user"
        assert msgs[4].content == "user prompt"

    @pytest.mark.invariant
    def test_tool_results_not_stored_in_session(self, fake_reasoner: FakeReasoner):
        """Invariant: tool results are turn-scoped; session only gets user + assistant."""
        engine = ORE(fake_reasoner)
        session = Session()
        tr = ToolResult(tool_name="echo", output="x", status="ok")
        engine.execute("hi", session=session, tool_results=[tr])
        assert len(session.messages) == 2
        assert session.messages[0].content == "hi"
        assert session.messages[1].content == "fake response"
        for m in session.messages:
            assert "[Tool:" not in m.content

    @pytest.mark.invariant
    def test_reasoner_still_called_once_with_tools(self, fake_reasoner: FakeReasoner):
        """Invariant: one reasoner call per execute() even when tool_results present."""
        engine = ORE(fake_reasoner)
        tr = ToolResult(tool_name="echo", output="y", status="ok")
        engine.execute("hi", tool_results=[tr])
        assert fake_reasoner.reason_call_count == 1


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

    @pytest.mark.invariant
    def test_reasoner_called_exactly_once_per_execute_stream(
        self, fake_reasoner: FakeReasoner, sample_session: Session
    ):
        """Invariant: one reasoner.stream_reason() call per ORE.execute_stream()."""
        engine = ORE(fake_reasoner)
        gen = engine.execute_stream("hi")
        try:
            while True:
                next(gen)
        except StopIteration:
            pass
        assert fake_reasoner.stream_reason_call_count == 1
        gen = engine.execute_stream("bye")
        try:
            while True:
                next(gen)
        except StopIteration:
            pass
        assert fake_reasoner.stream_reason_call_count == 2
        gen = engine.execute_stream("third", session=sample_session)
        try:
            while True:
                next(gen)
        except StopIteration:
            pass
        assert fake_reasoner.stream_reason_call_count == 3


class TestSkillContextInjection:
    """Tests for v0.8 skill_context injection into the message list."""

    def test_skill_context_injected_before_tool_results(
        self, fake_reasoner: FakeReasoner, sample_session: Session
    ):
        """Message order: [system, skill_system, tool_user, session..., user]."""
        engine = ORE(fake_reasoner)
        tr = ToolResult(tool_name="echo", output="tool out", status="ok")
        engine.execute(
            "prompt",
            session=sample_session,
            tool_results=[tr],
            skill_context=["[Skill:test]\nDo X."],
        )
        msgs = fake_reasoner.last_messages
        assert msgs[0].role == "system"  # Aya persona
        assert msgs[1].role == "system"  # Skill instruction
        assert "[Skill:test]" in msgs[1].content
        assert msgs[2].role == "user"  # Tool result
        assert "[Tool:echo]" in msgs[2].content
        # Session messages follow
        assert msgs[3].role == "user"
        assert msgs[3].content == "hello"
        assert msgs[4].role == "assistant"
        # User prompt is last
        assert msgs[5].role == "user"
        assert msgs[5].content == "prompt"

    @pytest.mark.invariant
    def test_skill_context_not_stored_in_session(self, fake_reasoner: FakeReasoner):
        """Invariant: skill context is turn-scoped; session only gets user + assistant."""
        engine = ORE(fake_reasoner)
        session = Session()
        engine.execute(
            "hi",
            session=session,
            skill_context=["[Skill:x]\nInstructions."],
        )
        assert len(session.messages) == 2
        assert session.messages[0].content == "hi"
        assert session.messages[1].content == "fake response"
        for m in session.messages:
            assert "[Skill:" not in m.content

    def test_skill_context_uses_system_role(self, fake_reasoner: FakeReasoner):
        """Injected skill messages have role='system'."""
        engine = ORE(fake_reasoner)
        engine.execute("hi", skill_context=["Instruction A", "Instruction B"])
        msgs = fake_reasoner.last_messages
        # msgs[0] = Aya system, msgs[1] = skill A, msgs[2] = skill B, msgs[3] = user
        assert msgs[1].role == "system"
        assert msgs[1].content == "Instruction A"
        assert msgs[2].role == "system"
        assert msgs[2].content == "Instruction B"

    @pytest.mark.invariant
    def test_reasoner_still_called_once_with_skills(self, fake_reasoner: FakeReasoner):
        """Invariant: one reason() call even with skill_context."""
        engine = ORE(fake_reasoner)
        engine.execute("hi", skill_context=["Do something."])
        assert fake_reasoner.reason_call_count == 1

    def test_no_skill_context_preserves_v07_behavior(self, fake_reasoner: FakeReasoner):
        """skill_context=None produces the same message list as v0.7."""
        engine = ORE(fake_reasoner)
        tr = ToolResult(tool_name="echo", output="out", status="ok")
        engine.execute("hi", tool_results=[tr])
        msgs = fake_reasoner.last_messages
        # v0.7 order: [system, tool_user, user]
        assert len(msgs) == 3
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"
        assert "[Tool:echo]" in msgs[1].content
        assert msgs[2].role == "user"
        assert msgs[2].content == "hi"
