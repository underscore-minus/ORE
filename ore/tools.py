"""
Tool interface and built-in tools (v0.6).
Tools are pre-reasoning context injectors; they run before the reasoner.
v0.7 adds optional routing_hints and extract_args for intent-based routing.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List

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

    def routing_hints(self) -> List[str]:
        """Keywords/phrases for the router to match (v0.7). Override in subclasses."""
        return []

    def extract_args(self, prompt: str) -> Dict[str, str]:
        """
        Parse tool arguments from natural-language prompt (v0.7).
        Override in subclasses. Default: no extraction.
        """
        return {}


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

    def routing_hints(self) -> List[str]:
        # "repeat this line" mirrors TEST_ROUTING_TARGET so the CLI and tests agree
        return ["echo", "repeat", "say back", "repeat back", "repeat this line"]

    def extract_args(self, prompt: str) -> Dict[str, str]:
        """Use the full prompt as the message to echo (stripped)."""
        msg = prompt.strip()
        return {"msg": msg if msg else "(no message)"}

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


# Regex for path extraction: quoted (double or single) or unquoted path-like token.
# Quoted takes precedence; then a word that may contain / or ~ (path-like).
_READ_FILE_QUOTED_PATH = re.compile(r'["\']([^"\']+)["\']')
_READ_FILE_UNQUOTED_PATH = re.compile(
    r"(?:read\s+(?:the\s+)?file\s+(?:at\s+)?|file\s+|path\s+)(\S+(?:\s+\S+)*?)(?:\s+please)?\s*$",
    re.IGNORECASE,
)
_READ_FILE_SINGLE_TOKEN = re.compile(
    r"(?:read|show|cat|open)\s+(?:the\s+)?(?:file\s+)?(\S+)"
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

    def routing_hints(self) -> List[str]:
        return [
            "read file",
            "read the file",
            "show file",
            "show the file",
            "cat file",
            "open file",
        ]

    def extract_args(self, prompt: str) -> Dict[str, str]:
        """
        Extract file path from prompt. Tries: quoted path, then phrase after
        'read file' / 'file' / 'path', then single path-like token.
        """
        text = prompt.strip()
        # 1. Quoted path (double or single quotes)
        m = _READ_FILE_QUOTED_PATH.search(text)
        if m:
            return {"path": m.group(1).strip()}
        # 2. Phrase at end: "read the file at /path" or "file /path"
        m = _READ_FILE_UNQUOTED_PATH.search(text)
        if m:
            return {"path": m.group(1).strip()}
        # 3. Single path-like token after read/show/cat/open
        m = _READ_FILE_SINGLE_TOKEN.search(text)
        if m:
            return {"path": m.group(1).strip()}
        return {}

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
