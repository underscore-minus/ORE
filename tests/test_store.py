"""Tests for ore/store.py — FileSessionStore persistence."""

import json

import pytest

from ore.store import FileSessionStore, _session_to_dict
from ore.types import Message, Session

# Session file JSON shape (interface lock). Top-level and message keys.
SESSION_TOP_KEYS = frozenset({"id", "created_at", "messages"})
SESSION_MESSAGE_KEYS = frozenset({"role", "content", "id", "timestamp"})


@pytest.fixture
def store(tmp_path):
    """FileSessionStore backed by a temp directory."""
    return FileSessionStore(root=tmp_path)


@pytest.mark.invariant
def test_session_serialization_exact_keys():
    """Invariant: serialized session has exact top-level and message keys."""
    session = Session()
    session.messages.append(Message(role="user", content="hi"))
    data = _session_to_dict(session)
    assert (
        set(data.keys()) == SESSION_TOP_KEYS
    ), f"Session top-level keys expected {SESSION_TOP_KEYS}, got {set(data.keys())}"
    for msg in data["messages"]:
        assert (
            set(msg.keys()) == SESSION_MESSAGE_KEYS
        ), f"Message keys expected {SESSION_MESSAGE_KEYS}, got {set(msg.keys())}"


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


# C-2 session name path traversal: validation rejects bad names
@pytest.mark.invariant
def test_session_name_with_slash_rejected(store):
    """Invariant: session name containing / is rejected."""
    with pytest.raises(ValueError, match="Invalid session name|/|\\\\|\\.\\.|outside"):
        store.save(Session(), "a/b")
    with pytest.raises(ValueError, match="Invalid session name|/|\\\\|\\.\\.|outside"):
        store.load("a/b")


@pytest.mark.invariant
def test_session_name_with_dotdot_rejected(store):
    """Invariant: session name containing .. is rejected."""
    with pytest.raises(ValueError, match="Invalid session name|/|\\\\|\\.\\.|outside"):
        store.save(Session(), "..")
    with pytest.raises(ValueError, match="Invalid session name|/|\\\\|\\.\\.|outside"):
        store.save(Session(), "a/../b")


@pytest.mark.invariant
def test_session_name_with_backslash_rejected(store):
    """Invariant: session name containing \\ is rejected."""
    with pytest.raises(ValueError, match="Invalid session name|/|\\\\|\\.\\.|outside"):
        store.save(Session(), "a\\b")


@pytest.mark.invariant
def test_session_name_empty_rejected(store):
    """Invariant: empty session name is rejected."""
    with pytest.raises(ValueError, match="empty"):
        store.save(Session(), "")
    with pytest.raises(ValueError, match="empty"):
        store.save(Session(), "   ")


@pytest.mark.invariant
def test_valid_session_name_accepted(store):
    """Invariant: valid session name is accepted for save and load."""
    session = Session()
    session.messages.append(Message(role="user", content="hi"))
    store.save(session, "valid_name")
    loaded = store.load("valid_name")
    assert loaded.id == session.id
    assert len(loaded.messages) == 1
