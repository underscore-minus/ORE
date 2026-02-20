"""
Tool interface and built-in tools (v0.6).
Tools are pre-reasoning context injectors; they run before the reasoner.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict

from .gate import Permission
from .types import ToolResult


class Tool(ABC):
    """Abstract interface for a runnable tool. Requires explicit permissions via Gate."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for CLI lookup and logging."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description for --list-tools."""
        ...

    @property
    @abstractmethod
    def required_permissions(self) -> frozenset[Permission]:
        """Permissions the gate must grant for this tool to run. Empty = no permissions."""
        ...

    @abstractmethod
    def run(self, args: Dict[str, str]) -> ToolResult:
        """Execute the tool. Args are key=value from --tool-arg. Return ToolResult."""
        ...


class EchoTool(Tool):
    """Echoes provided args back as output. No permissions required."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo arguments back (e.g. msg=hello). No permissions required."

    @property
    def required_permissions(self) -> frozenset[Permission]:
        return frozenset()

    def run(self, args: Dict[str, str]) -> ToolResult:
        if not args:
            return ToolResult(
                tool_name=self.name,
                output="(no arguments)",
                status="ok",
            )
        lines = [f"{k}={v}" for k, v in sorted(args.items())]
        return ToolResult(
            tool_name=self.name,
            output="\n".join(lines),
            status="ok",
        )


class ReadFileTool(Tool):
    """Reads a local file. Requires path=... in args. Needs FILESYSTEM_READ."""

    @property
    def name(self) -> str:
        return "read-file"

    @property
    def description(self) -> str:
        return "Read a local file. Args: path=<filepath>. Requires filesystem-read."

    @property
    def required_permissions(self) -> frozenset[Permission]:
        return frozenset({Permission.FILESYSTEM_READ})

    def run(self, args: Dict[str, str]) -> ToolResult:
        path_str = args.get("path", "").strip()
        if not path_str:
            return ToolResult(
                tool_name=self.name,
                output="",
                status="error",
                metadata={"error_message": "Missing required argument: path=..."},
            )
        try:
            content = Path(path_str).read_text(encoding="utf-8")
            return ToolResult(
                tool_name=self.name,
                output=content,
                status="ok",
            )
        except FileNotFoundError:
            return ToolResult(
                tool_name=self.name,
                output="",
                status="error",
                metadata={"error_message": f"File not found: {path_str}"},
            )
        except (OSError, PermissionError) as e:
            return ToolResult(
                tool_name=self.name,
                output="",
                status="error",
                metadata={"error_message": str(e)},
            )


# Registry for CLI dispatch: name -> Tool instance
TOOL_REGISTRY: Dict[str, Tool] = {
    EchoTool().name: EchoTool(),
    ReadFileTool().name: ReadFileTool(),
}
