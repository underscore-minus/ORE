"""
ORE: Orchestrated Reasoning Engine v0.6.
Irreducible loop: Input -> Reasoner -> Output. Tools (v0.6) run pre-reasoning, gated.
"""

from .cli import run
from .core import ORE
from .gate import Gate, GateError, Permission
from .models import default_model, fetch_models
from .reasoner import AyaReasoner, Reasoner
from .store import FileSessionStore, SessionStore
from .tools import TOOL_REGISTRY, Tool
from .types import Message, Response, Session, ToolResult

__all__ = [
    "run",
    "ORE",
    "Reasoner",
    "AyaReasoner",
    "Message",
    "Response",
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
