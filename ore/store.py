"""
Session persistence abstraction (v0.4).
Filesystem-backed store; ORE core is unaware of persistence.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict
import json
from pathlib import Path
from typing import List

from .types import Message, Session


class SessionStore(ABC):
    """Minimal interface for session persistence. No extra methods."""

    @abstractmethod
    def save(self, session: Session, name: str) -> None:
        """Persist session under the given name (user-facing handle)."""
        ...

    @abstractmethod
    def load(self, name: str) -> Session:
        """Load session by name. Raises if not found."""
        ...

    @abstractmethod
    def list(self) -> List[str]:
        """Return sorted list of stored session names."""
        ...


def _session_to_dict(session: Session) -> dict:
    """Serialize Session to a JSON-serializable dict (messages as list of dicts)."""
    return {
        "id": session.id,
        "created_at": session.created_at,
        "messages": [asdict(m) for m in session.messages],
    }


def _dict_to_session(data: dict) -> Session:
    """Deserialize dict to Session (reconstruct Message objects)."""
    messages = [
        Message(
            role=m["role"],
            content=m["content"],
            id=m.get("id", ""),
            timestamp=m.get("timestamp", 0.0),
        )
        for m in data.get("messages", [])
    ]
    return Session(
        messages=messages,
        id=data.get("id", ""),
        created_at=data.get("created_at", 0.0),
    )


def _validate_session_name(name: str, root: Path) -> None:
    """
    Validate session name to prevent path traversal. Rejects names that would
    escape root. Raises ValueError with a clear message on rejection.
    """
    if not name or not name.strip():
        raise ValueError("Session name cannot be empty")
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError(
            f"Invalid session name: must not contain /, \\, or .. (got {name!r})"
        )
    resolved = (root / f"{name}.json").resolve()
    root_resolved = root.resolve()
    if not str(resolved).startswith(str(root_resolved)):
        raise ValueError(
            f"Session name would resolve outside session directory: {name!r}"
        )


class FileSessionStore(SessionStore):
    """
    Filesystem-backed session store.
    Default root: ~/.ore/sessions/
    One JSON file per session: <name>.json
    """

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path.home() / ".ore" / "sessions"

    def save(self, session: Session, name: str) -> None:
        """Write session to <root>/<name>.json. Creates directory if missing."""
        _validate_session_name(name, self._root)
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{name}.json"
        with path.open("w") as f:
            json.dump(_session_to_dict(session), f, indent=2)

    def load(self, name: str) -> Session:
        """Read session from <root>/<name>.json. Raises FileNotFoundError if missing."""
        _validate_session_name(name, self._root)
        path = self._root / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session '{name}' not found at {path}")
        with path.open() as f:
            data = json.load(f)
        return _dict_to_session(data)

    def list(self) -> List[str]:
        """Return sorted session names (stripped of .json suffix)."""
        if not self._root.exists():
            return []
        names = []
        for p in self._root.glob("*.json"):
            if not p.is_file():
                continue
            try:
                _validate_session_name(p.stem, self._root)
                names.append(p.stem)
            except ValueError:
                continue
        return sorted(names)
