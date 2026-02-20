"""Tests for ore/types.py — Message, Response, Session data contracts."""

import time
import uuid

from ore.types import Message, Response, Session


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
