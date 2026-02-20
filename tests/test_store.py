"""Tests for ore/store.py — FileSessionStore persistence."""

import json

import pytest

from ore.store import FileSessionStore
from ore.types import Message, Session


@pytest.fixture
def store(tmp_path):
    """FileSessionStore backed by a temp directory."""
    return FileSessionStore(root=tmp_path)


class TestFileSessionStore:
    def test_save_creates_json(self, store, tmp_path):
        session = Session()
        store.save(session, "demo")
        path = tmp_path / "demo.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["id"] == session.id

    def test_round_trip(self, store):
        session = Session()
        session.messages.append(Message(role="user", content="ping"))
        session.messages.append(Message(role="assistant", content="pong"))
        store.save(session, "rt")

        loaded = store.load("rt")
        assert loaded.id == session.id
        assert len(loaded.messages) == 2
        assert loaded.messages[0].role == "user"
        assert loaded.messages[0].content == "ping"
        assert loaded.messages[1].role == "assistant"
        assert loaded.messages[1].content == "pong"

    def test_round_trip_preserves_timestamps(self, store):
        session = Session()
        msg = Message(role="user", content="ts")
        session.messages.append(msg)
        store.save(session, "ts")

        loaded = store.load("ts")
        assert loaded.created_at == session.created_at
        assert loaded.messages[0].timestamp == msg.timestamp

    def test_load_missing_raises(self, store):
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            store.load("nonexistent")

    def test_list_empty(self, store):
        assert store.list() == []

    def test_list_returns_sorted_names(self, store):
        for name in ("beta", "alpha", "gamma"):
            store.save(Session(), name)
        assert store.list() == ["alpha", "beta", "gamma"]

    def test_list_missing_dir(self, tmp_path):
        store = FileSessionStore(root=tmp_path / "nope")
        assert store.list() == []

    def test_save_creates_directory(self, tmp_path):
        deep = tmp_path / "a" / "b"
        store = FileSessionStore(root=deep)
        store.save(Session(), "nested")
        assert (deep / "nested.json").exists()

    def test_overwrite_on_save(self, store):
        s = Session()
        store.save(s, "ow")
        s.messages.append(Message(role="user", content="added"))
        store.save(s, "ow")

        loaded = store.load("ow")
        assert len(loaded.messages) == 1
