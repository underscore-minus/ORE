"""Tests for ore/gate.py — permission gate for tool execution."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ore.gate import Gate, GateError, Permission
from ore.tools import EchoTool, ReadFileTool
from ore.types import ToolResult


class TestGate:
    def test_no_permission_tool_always_passes(self):
        gate = Gate(frozenset())
        tool = EchoTool()
        result = gate.run(tool, {"msg": "hi"})
        assert result.tool_name == "echo"
        assert result.status == "ok"
        assert "msg=hi" in result.output

    def test_allowed_tool_passes(self, tmp_path):
        gate = Gate(frozenset({Permission.FILESYSTEM_READ}))
        f = tmp_path / "allowed.txt"
        f.write_text("content", encoding="utf-8")
        result = gate.run(ReadFileTool(), {"path": str(f)})
        assert result.tool_name == "read-file"
        assert result.status == "ok"
        assert result.output == "content"

    def test_denied_tool_raises_gate_error(self):
        gate = Gate(frozenset())
        tool = ReadFileTool()
        with pytest.raises(GateError) as exc_info:
            gate.run(tool, {"path": "/tmp/foo"})
        assert "read-file" in str(exc_info.value)
        assert (
            "filesystem-read" in str(exc_info.value).lower()
            or "permission" in str(exc_info.value).lower()
        )

    def test_permissive_gate_allows_everything(self):
        gate = Gate.permissive()
        tool = ReadFileTool()
        result = gate.run(tool, {"path": "/nonexistent"})
        assert result.tool_name == "read-file"
        assert result.status == "error"
        assert "error_message" in result.metadata

    def test_metadata_populated(self):
        gate = Gate(frozenset())
        tool = EchoTool()
        result = gate.run(tool, {"x": "y"})
        assert "execution_time_ms" in result.metadata
        assert isinstance(result.metadata["execution_time_ms"], (int, float))
        assert "checked_permissions" in result.metadata
        assert result.metadata["checked_permissions"] == []

    def test_metadata_checked_permissions_for_read_file(self):
        gate = Gate(frozenset({Permission.FILESYSTEM_READ}))
        tool = ReadFileTool()
        result = gate.run(tool, {"path": "/nonexistent"})
        assert "checked_permissions" in result.metadata
        assert "filesystem-read" in result.metadata["checked_permissions"]


@pytest.mark.invariant
def test_denied_tool_never_executes():
    """Invariant: when gate denies, tool.run() is never called."""
    gate = Gate(frozenset())
    tool = ReadFileTool()
    tool.run = MagicMock(
        return_value=ToolResult(tool_name="read-file", output="", status="ok")
    )
    with pytest.raises(GateError):
        gate.run(tool, {"path": "/any"})
    tool.run.assert_not_called()
