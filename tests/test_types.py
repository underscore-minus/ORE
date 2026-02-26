"""Tests for ore/types.py — Message, Response, Session, ExecutionArtifact data contracts."""

import json
import time
import uuid
from dataclasses import fields

import pytest

from ore.types import (
    ARTIFACT_VERSION,
    ExecutionArtifact,
    ExecutionArtifactContinuation,
    ExecutionArtifactInput,
    ExecutionArtifactOutput,
    Message,
    Response,
    RoutingDecision,
    RoutingTarget,
    Session,
    SkillMetadata,
    ToolResult,
)

# Frozen field sets (interface lock). New fields may be added; these must exist.
DATACLASS_FIELD_CONTRACTS = {
    Message: frozenset({"role", "content", "id", "timestamp"}),
    Response: frozenset({"content", "model_id", "id", "timestamp", "metadata", "duration_ms"}),
    Session: frozenset({"messages", "id", "created_at"}),
    ToolResult: frozenset(
        {"tool_name", "output", "status", "id", "timestamp", "metadata"}
    ),
    SkillMetadata: frozenset({"name", "description", "hints", "path"}),
    RoutingTarget: frozenset({"name", "target_type", "description", "hints"}),
    RoutingDecision: frozenset(
        {"target", "target_type", "confidence", "args", "reasoning", "id", "timestamp"}
    ),
    ExecutionArtifactInput: frozenset(
        {"prompt", "model_id", "mode", "routing", "tools", "skills"}
    ),
    ExecutionArtifactOutput: frozenset(
        {"id", "content", "model_id", "timestamp", "metadata"}
    ),
    ExecutionArtifactContinuation: frozenset({"requested", "reason"}),
    ExecutionArtifact: frozenset(
        {
            "artifact_version",
            "execution_id",
            "timestamp",
            "input",
            "output",
            "continuation",
        }
    ),
}


@pytest.mark.invariant
def test_dataclass_field_contracts():
    """Invariant: each dataclass has at least the frozen set of field names."""
    for cls, expected in DATACLASS_FIELD_CONTRACTS.items():
        actual = frozenset(f.name for f in fields(cls))
        assert (
            expected <= actual
        ), f"{cls.__name__}: expected fields {expected}, missing {expected - actual}"


class TestMessage:
    def test_defaults(self):
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        # Auto-generated UUID and timestamp
        uuid.UUID(msg.id)  # raises if invalid
        assert isinstance(msg.timestamp, float)
        assert msg.timestamp <= time.time()

    def test_unique_ids(self):
        a = Message(role="user", content="a")
        b = Message(role="user", content="b")
        assert a.id != b.id

    def test_explicit_fields(self):
        msg = Message(role="assistant", content="ok", id="custom-id", timestamp=1.0)
        assert msg.id == "custom-id"
        assert msg.timestamp == 1.0


class TestResponse:
    def test_defaults(self):
        resp = Response(content="answer", model_id="llama3.2")
        assert resp.content == "answer"
        assert resp.model_id == "llama3.2"
        uuid.UUID(resp.id)
        assert isinstance(resp.timestamp, float)
        assert resp.metadata == {}
        assert resp.duration_ms == 0

    def test_response_constructed_without_duration_ms_has_zero(self):
        """Response built without duration_ms defaults to 0 (additive)."""
        resp = Response(content="x", model_id="m")
        assert resp.duration_ms == 0

    def test_metadata(self):
        meta = {"eval_count": 42, "prompt_eval_count": 10}
        resp = Response(content="x", model_id="m", metadata=meta)
        assert resp.metadata["eval_count"] == 42


class TestSession:
    def test_defaults(self):
        session = Session()
        assert session.messages == []
        uuid.UUID(session.id)
        assert isinstance(session.created_at, float)

    def test_messages_are_mutable(self):
        session = Session()
        session.messages.append(Message(role="user", content="hi"))
        assert len(session.messages) == 1
        assert session.messages[0].content == "hi"

    def test_unique_ids(self):
        a = Session()
        b = Session()
        assert a.id != b.id


class TestExecutionArtifact:
    """Tests for v0.9 ExecutionArtifact schema and serialization."""

    @pytest.mark.invariant
    def test_artifact_schema_exact_top_level_keys(self):
        """Invariant: to_dict() produces exact top-level keys."""
        from ore.types import Response

        resp = Response(content="ok", model_id="m1")
        artifact = ExecutionArtifact.from_response(
            response=resp, prompt="hi", model_id="m1"
        )
        data = artifact.to_dict()
        expected = frozenset(
            {
                "artifact_version",
                "execution_id",
                "timestamp",
                "input",
                "output",
                "continuation",
            }
        )
        assert (
            set(data.keys()) == expected
        ), f"Artifact top-level keys expected {expected}, got {set(data.keys())}"

    @pytest.mark.invariant
    def test_artifact_version_constant(self):
        """Invariant: ARTIFACT_VERSION is ore.exec.v1."""
        assert ARTIFACT_VERSION == "ore.exec.v1"

    def test_from_response_to_dict_roundtrip(self):
        resp = Response(content="ok", model_id="m1")
        artifact = ExecutionArtifact.from_response(
            response=resp,
            prompt="hi",
            model_id="m1",
            routing=None,
            tools=["echo"],
            skills=None,
        )
        data = artifact.to_dict()
        assert data["artifact_version"] == ARTIFACT_VERSION
        assert data["input"]["prompt"] == "hi"
        assert data["input"]["tools"] == ["echo"]
        assert data["output"]["content"] == "ok"
        # Roundtrip
        parsed = ExecutionArtifact.from_dict(data)
        assert parsed.input.prompt == artifact.input.prompt
        assert parsed.output.content == artifact.output.content

    def test_from_dict_requires_version(self):
        with pytest.raises(ValueError, match="artifact_version"):
            ExecutionArtifact.from_dict({"input": {}, "output": {}})

    def test_from_dict_rejects_unsupported_version(self):
        data = {
            "artifact_version": "ore.exec.v99",
            "execution_id": "x",
            "timestamp": 1.0,
            "input": {"prompt": "p", "model_id": "m", "mode": "single_turn"},
            "output": {
                "id": "x",
                "content": "c",
                "model_id": "m",
                "timestamp": 1.0,
                "metadata": {},
            },
            "continuation": {"requested": False, "reason": None},
        }
        with pytest.raises(ValueError, match="Unsupported"):
            ExecutionArtifact.from_dict(data)

    def test_from_dict_requires_input_prompt_and_model_id(self):
        data = {
            "artifact_version": ARTIFACT_VERSION,
            "execution_id": "x",
            "timestamp": 1.0,
            "input": {"mode": "single_turn"},  # missing prompt, model_id
            "output": {
                "id": "x",
                "content": "c",
                "model_id": "m",
                "timestamp": 1.0,
                "metadata": {},
            },
            "continuation": {"requested": False, "reason": None},
        }
        with pytest.raises(ValueError, match="prompt|model_id"):
            ExecutionArtifact.from_dict(data)

    @pytest.mark.invariant
    def test_forward_compat_tolerates_unknown_top_level_keys(self):
        """Invariant: unknown top-level keys are tolerated for forward compatibility."""
        data = {
            "artifact_version": ARTIFACT_VERSION,
            "execution_id": "x",
            "timestamp": 1.0,
            "input": {"prompt": "p", "model_id": "m", "mode": "single_turn"},
            "output": {
                "id": "x",
                "content": "c",
                "model_id": "m",
                "timestamp": 1.0,
                "metadata": {},
            },
            "continuation": {"requested": False, "reason": None},
            "unknown_future_field": "ignored",
        }
        artifact = ExecutionArtifact.from_dict(data)
        assert artifact.input.prompt == "p"

    def test_from_response_with_routing(self):
        routing = RoutingDecision(
            target="echo",
            target_type="tool",
            confidence=0.8,
            args={"msg": "hi"},
            reasoning="matched",
        )
        resp = Response(content="ok", model_id="m")
        artifact = ExecutionArtifact.from_response(
            response=resp,
            prompt="echo hi",
            model_id="m",
            routing=routing,
            tools=["echo"],
            skills=None,
        )
        assert artifact.input.routing is not None
        assert artifact.input.routing["target"] == "echo"

    def test_from_dict_null_timestamp_raises(self):
        """Null timestamp in output raises ValueError (not TypeError)."""
        data = {
            "artifact_version": ARTIFACT_VERSION,
            "execution_id": "x",
            "timestamp": 1.0,
            "input": {"prompt": "p", "model_id": "m", "mode": "single_turn"},
            "output": {
                "id": "x",
                "content": "c",
                "model_id": "m",
                "timestamp": None,
                "metadata": {},
            },
            "continuation": {"requested": False, "reason": None},
        }
        with pytest.raises(ValueError, match="timestamp|number"):
            ExecutionArtifact.from_dict(data)
