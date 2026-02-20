"""
ORE: Orchestrated Reasoning Engine v0.7.
Irreducible loop: Input -> Reasoner -> Output. Tools (v0.6) run pre-reasoning, gated.
Routing (v0.7) selects tools by intent when --route is used.
"""

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
from .store import FileSessionStore, SessionStore
from .tools import TOOL_REGISTRY, Tool
from .types import (
    Message,
    Response,
    RoutingDecision,
    RoutingTarget,
    Session,
    ToolResult,
)

__all__ = [
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
