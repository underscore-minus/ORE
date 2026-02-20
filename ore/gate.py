"""
Gate: permission layer for tool execution (v0.6).
Default-deny; tools run only when their required permissions are granted.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import TYPE_CHECKING, Dict

from .types import ToolResult

if TYPE_CHECKING:
    from .tools import Tool


class Permission(str, Enum):
    """Permissions that tools may require. Default-deny: grant explicitly per invocation."""

    FILESYSTEM_READ = "filesystem-read"
    FILESYSTEM_WRITE = "filesystem-write"
    SHELL = "shell"
    NETWORK = "network"


class GateError(Exception):
    """Raised when a tool is denied by the gate (missing permissions)."""

    def __init__(self, tool_name: str, missing: frozenset[Permission]) -> None:
        self.tool_name = tool_name
        self.missing = missing
        names = ", ".join(p.value for p in sorted(missing, key=lambda x: x.value))
        super().__init__(f"Tool '{tool_name}' denied: missing permissions: {names}")


class Gate:
    """
    Enforces permission checks before tool execution.
    Default-deny: only tools whose required_permissions are subset of allowed pass.
    """

    def __init__(self, allowed_permissions: frozenset[Permission]) -> None:
        self._allowed = allowed_permissions

    def check(self, tool: "Tool") -> None:
        """
        Raise GateError if tool requires any permission not in allowed set.
        Tools with empty required_permissions always pass.
        """
        missing = tool.required_permissions - self._allowed
        if missing:
            raise GateError(tool.name, missing)

    def run(self, tool: "Tool", args: Dict[str, str]) -> ToolResult:
        """
        Check permissions, then run tool. Populates result metadata with
        execution_time_ms and checked_permissions.
        """
        self.check(tool)
        start = time.perf_counter()
        result = tool.run(args)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        result.metadata.setdefault("execution_time_ms", elapsed_ms)
        result.metadata.setdefault(
            "checked_permissions", [p.value for p in sorted(tool.required_permissions, key=lambda x: x.value)]
        )
        return result

    @classmethod
    def permissive(cls) -> "Gate":
        """Gate that allows all permissions (for tests only)."""
        return cls(frozenset(Permission))
