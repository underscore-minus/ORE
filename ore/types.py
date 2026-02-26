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

    Metadata (diagnostic — schema locked in v0.3.1):
    The `metadata` dict is populated by the reasoner backend on a best-effort
    basis. Callers must not depend on specific keys for core behaviour.

    Known keys produced by AyaReasoner (Ollama backend):
      eval_count          (int)   — tokens generated in the response.
      prompt_eval_count   (int)   — tokens in the prompt sent to the model.
      eval_duration       (int)   — response generation time in nanoseconds.
      prompt_eval_duration(int)   — prompt processing time in nanoseconds.

    These keys are formally committed for AyaReasoner in v0.3.1.
    Custom reasoners may omit keys unless they adopt the same contract.
    """

    content: str
    model_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0  # v1.3: wall-clock time of API call in ms; 0 if not set


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


# ---------------------------------------------------------------------------
# v0.9 — Chainable Execution Artifacts
# ---------------------------------------------------------------------------

ARTIFACT_VERSION = "ore.exec.v1"

"""
Non-goals for the artifact (v0.9):
- No embedded session history replay by default.
- No hidden execution directives.
- No engine-side invocation of subsequent ORE executions.
- Chaining happens via data, not runtime coupling.
"""


@dataclass
class ExecutionArtifactInput:
    """
    Input context that produced an execution. Captured for reconstructability.

    mode: "single_turn" for v0.9; conversational modes deferred.
    routing/tool/skill summaries capture what was injected into the turn.
    """

    prompt: str
    model_id: str
    mode: str  # "single_turn"
    routing: Optional[Dict[str, Any]] = None  # RoutingDecision as dict, or None
    tools: Optional[List[str]] = None  # Tool names run this turn
    skills: Optional[List[str]] = None  # Skill names activated this turn


@dataclass
class ExecutionArtifactOutput:
    """Reasoner output; matches Response shape for JSON compatibility."""

    id: str
    content: str
    model_id: str
    timestamp: float
    metadata: Dict[str, Any]


@dataclass
class ExecutionArtifactContinuation:
    """
    Declared signal only. Never inferred.

    requested: True if the output explicitly asked for a follow-up run.
    reason: Optional human-readable explanation (e.g. from output parsing).
    """

    requested: bool = False
    reason: Optional[str] = None


@dataclass
class ExecutionArtifact:
    """
    v0.9 self-describing execution artifact.

    One ORE execution produces this; a platform can feed it into another
    without reinterpretation or human involvement.

    Schema version: ARTIFACT_VERSION. Forward-compat: tolerate unknown keys.
    """

    artifact_version: str
    execution_id: str
    timestamp: float
    input: ExecutionArtifactInput
    output: ExecutionArtifactOutput
    continuation: ExecutionArtifactContinuation

    @classmethod
    def from_response(
        cls,
        response: Response,
        prompt: str,
        model_id: str,
        routing: Optional[RoutingDecision] = None,
        tools: Optional[List[str]] = None,
        skills: Optional[List[str]] = None,
        continuation_requested: bool = False,
        continuation_reason: Optional[str] = None,
    ) -> "ExecutionArtifact":
        """Build artifact from a completed turn (single-turn only)."""
        routing_dict: Optional[Dict[str, Any]] = None
        if routing is not None:
            routing_dict = {
                "target": routing.target,
                "target_type": routing.target_type,
                "confidence": routing.confidence,
                "args": routing.args,
                "reasoning": routing.reasoning,
                "id": routing.id,
                "timestamp": routing.timestamp,
            }
        return cls(
            artifact_version=ARTIFACT_VERSION,
            execution_id=response.id,
            timestamp=response.timestamp,
            input=ExecutionArtifactInput(
                prompt=prompt,
                model_id=model_id,
                mode="single_turn",
                routing=routing_dict,
                tools=tools or None,
                skills=skills or None,
            ),
            output=ExecutionArtifactOutput(
                id=response.id,
                content=response.content,
                model_id=response.model_id,
                timestamp=response.timestamp,
                metadata=dict(response.metadata),
            ),
            continuation=ExecutionArtifactContinuation(
                requested=continuation_requested,
                reason=continuation_reason,
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-serializable dict."""
        return {
            "artifact_version": self.artifact_version,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp,
            "input": {
                "prompt": self.input.prompt,
                "model_id": self.input.model_id,
                "mode": self.input.mode,
                "routing": self.input.routing,
                "tools": self.input.tools,
                "skills": self.input.skills,
            },
            "output": {
                "id": self.output.id,
                "content": self.output.content,
                "model_id": self.output.model_id,
                "timestamp": self.output.timestamp,
                "metadata": self.output.metadata,
            },
            "continuation": {
                "requested": self.continuation.requested,
                "reason": self.continuation.reason,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionArtifact":
        """
        Deserialize from dict (e.g. JSON load).
        Raises ValueError if artifact_version missing or unsupported.
        Tolerates unknown top-level keys for forward compatibility.
        """
        version = data.get("artifact_version")
        if not version:
            raise ValueError("Artifact missing required field: artifact_version")
        if version != ARTIFACT_VERSION:
            raise ValueError(
                f"Unsupported artifact version: {version}. Expected {ARTIFACT_VERSION}"
            )

        inp = data.get("input")
        if not inp or not isinstance(inp, dict):
            raise ValueError("Artifact missing or invalid 'input' object")
        prompt = inp.get("prompt")
        model_id = inp.get("model_id")
        if prompt is None or model_id is None:
            raise ValueError("Artifact input must include 'prompt' and 'model_id'")
        raw_mode = inp.get("mode")
        mode = str(raw_mode) if raw_mode is not None else "single_turn"
        input_obj = ExecutionArtifactInput(
            prompt=str(prompt),
            model_id=str(model_id),
            mode=mode,
            routing=(
                inp.get("routing") if isinstance(inp.get("routing"), dict) else None
            ),
            tools=inp.get("tools") if isinstance(inp.get("tools"), list) else None,
            skills=inp.get("skills") if isinstance(inp.get("skills"), list) else None,
        )

        out = data.get("output")
        if not out or not isinstance(out, dict):
            raise ValueError("Artifact missing or invalid 'output' object")
        try:
            out_ts = float(out.get("timestamp", 0.0))
        except (TypeError, ValueError):
            raise ValueError("Artifact output.timestamp must be a number")
        output_obj = ExecutionArtifactOutput(
            id=str(out.get("id", "")),
            content=str(out.get("content", "")),
            model_id=str(out.get("model_id", "")),
            timestamp=out_ts,
            metadata=(
                dict(out.get("metadata", {}))
                if isinstance(out.get("metadata"), dict)
                else {}
            ),
        )

        cont = data.get("continuation")
        if not cont or not isinstance(cont, dict):
            cont = {}
        continuation_obj = ExecutionArtifactContinuation(
            requested=bool(cont.get("requested", False)),
            reason=cont.get("reason") if isinstance(cont.get("reason"), str) else None,
        )

        try:
            top_ts = float(data.get("timestamp", output_obj.timestamp))
        except (TypeError, ValueError):
            raise ValueError("Artifact timestamp must be a number")
        return cls(
            artifact_version=str(data.get("artifact_version", ARTIFACT_VERSION)),
            execution_id=str(data.get("execution_id", output_obj.id)),
            timestamp=top_ts,
            input=input_obj,
            output=output_obj,
            continuation=continuation_obj,
        )
