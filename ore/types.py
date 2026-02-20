"""
Core data contracts for ORE.
List-first schema to support context windows and memory.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

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


@dataclass
class ToolResult:
    """
    Result of a single tool execution (v0.6).

    Turn-scoped: never stored in Session or persisted.

    Known metadata keys (documented, not enforced):
      execution_time_ms   (float) — wall-clock time for tool.run() in ms.
      checked_permissions (list[str]) — permission names evaluated by the gate.
      error_message      (str) — present when status == "error"; human-readable.
    """

    tool_name: str
    output: str
    status: str  # "ok" or "error"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillMetadata:
    """
    Level 1 skill metadata (v0.8) — always loaded, low token cost.

    Used for discovery (--list-skills) and routing (hints → RoutingTarget).
    Instructions (Level 2) and resources (Level 3) are loaded on-demand
    by the skill loader, not stored here.
    """

    name: str
    description: str
    hints: List[str]
    path: Path  # Absolute path to the skill directory


@dataclass
class RoutingTarget:
    """
    A routable target (tool or skill) for the router (v0.7).

    Used to keep routing generic: same structure for tools now and skills in v0.8.
    """

    name: str
    target_type: str  # "tool" or "skill"
    description: str
    hints: List[str]  # Keywords/phrases for rule-based matching


@dataclass
class RoutingDecision:
    """
    Result of routing: which target (if any) was selected and why.

    Turn-scoped; visible in CLI/output. target is None for fallback (reasoner only).
    """

    target: Optional[str]  # Name of selected target, or None for fallback
    target_type: str  # "tool", "skill", or "fallback"
    confidence: float  # 0.0 to 1.0; deterministic for RuleRouter
    args: Dict[str, str]  # Extracted args for the target
    reasoning: str  # Human-readable explanation for the decision
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
