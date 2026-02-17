"""
Core data contracts for ORE v0.1.
List-first schema to support future context windows and memory.
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

    Notes for v0.1.1:
    - `metadata` is **diagnostic and unstable**: it may include token counts,
      latencies, or backend-specific fields, and its exact schema can change
      between versions.
    - Callers must not depend on specific metadata keys for core behavior.
    """

    content: str
    model_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
