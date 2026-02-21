"""
ORE: Orchestrated Reasoning Engine.
Irreducible loop: Input -> Reasoner -> Output. Tools (v0.6) run pre-reasoning, gated.
Routing (v0.7) selects tools by intent when --route is used.
Skills (v0.8) inject filesystem-based instructions into context on-demand.
Artifacts (v0.9) enable chainable execution via --artifact-out / --artifact-in.
"""

from ._version import __version__

from .cli import run
from .core import ORE
from .gate import Gate, GateError, Permission
from .models import default_model, fetch_models
from .reasoner import AyaReasoner, Reasoner
from .router import (
    RuleRouter,
    Router,
    TEST_ROUTING_TARGET,
    build_targets_from_registry,
)
from .skills import (
    build_skill_registry,
    build_targets_from_skill_registry,
    load_skill_instructions,
    load_skill_metadata,
    load_skill_resource,
)
from .store import FileSessionStore, SessionStore
from .tools import TOOL_REGISTRY, Tool
from .types import (
    ARTIFACT_VERSION,
    ExecutionArtifact,
    Message,
    Response,
    RoutingDecision,
    RoutingTarget,
    Session,
    SkillMetadata,
    ToolResult,
)

__all__ = [
    "__version__",
    "ARTIFACT_VERSION",
    "ExecutionArtifact",
    "run",
    "ORE",
    "Reasoner",
    "AyaReasoner",
    "Message",
    "Response",
    "RoutingDecision",
    "RoutingTarget",
    "Router",
    "RuleRouter",
    "TEST_ROUTING_TARGET",
    "build_targets_from_registry",
    "SkillMetadata",
    "build_skill_registry",
    "build_targets_from_skill_registry",
    "load_skill_metadata",
    "load_skill_instructions",
    "load_skill_resource",
    "Session",
    "SessionStore",
    "FileSessionStore",
    "fetch_models",
    "default_model",
    "Tool",
    "TOOL_REGISTRY",
    "Gate",
    "GateError",
    "Permission",
    "ToolResult",
]
