"""
Core data contracts for ORE.
List-first schema to support context windows and memory.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

import time
import uuid


@dataclass
class Message:
    """Single message in a conversation; role must be system, user, or assistant."""

    role: str  # "system", "user", or "assistant"
    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)


@dataclass
class Response:
    """
    Reasoner output for a single turn.

    Metadata (diagnostic — schema will be locked in v0.3.1):
    The `metadata` dict is populated by the reasoner backend on a best-effort
    basis. Callers must not depend on specific keys for core behaviour.

    Known keys produced by AyaReasoner (Ollama backend):
      eval_count          (int)   — tokens generated in the response.
      prompt_eval_count   (int)   — tokens in the prompt sent to the model.
      eval_duration       (int)   — response generation time in nanoseconds.
      prompt_eval_duration(int)   — prompt processing time in nanoseconds.

    These keys will be formally committed to in v0.3.1. Until then, treat
    them as present-when-available but structurally unstable.
    """

    content: str
    model_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """
    An ordered, mutable history of messages for a single conversational context.

    Introduced in v0.3 (cognitive continuity).  The session accumulates user
    and assistant messages across turns so the reasoner can see prior exchanges.
    The system message is never stored here; it is injected by the orchestrator
    on every turn.

    State contract:
    - `messages` grows only through `ORE.execute(..., session=session)`.
    - No message is ever removed or reordered silently.
    - Callers may inspect or copy `messages` freely; they must not mutate it
      directly (treat as append-only outside of ORE internals).
    """

    messages: List[Message] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
