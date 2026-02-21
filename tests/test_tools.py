"""Tests for ore/tools.py — Tool interface and built-in tools."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ore.gate import Permission
from ore.tools import EchoTool, ReadFileTool, Tool, TOOL_REGISTRY

# Tool ABC contract (interface lock): required members.
TOOL_ABSTRACT_PROPERTIES = frozenset({"name", "description", "required_permissions"})
TOOL_ABSTRACT_METHODS = frozenset({"run"})
TOOL_OPTIONAL_METHODS = frozenset({"routing_hints", "extract_args"})


@pytest.mark.invariant
def test_tool_abc_has_required_members():
    """Invariant: Tool ABC defines required abstract properties and run()."""
    for name in TOOL_ABSTRACT_PROPERTIES:
        assert hasattr(Tool, name), f"Tool missing property: {name}"
    for name in TOOL_ABSTRACT_METHODS:
        assert hasattr(Tool, name), f"Tool missing method: {name}"
    # run must be abstract
    assert getattr(Tool.run, "__isabstractmethod__", False) or "run" in dir(Tool)


class TestEchoTool:
    def test_name_and_description(self):
        tool = EchoTool()
        assert tool.name == "echo"
        assert len(tool.description) > 0
        assert "echo" in tool.description.lower()

    def test_required_permissions_empty(self):
        tool = EchoTool()
        assert tool.required_permissions == frozenset()

    def test_run_no_args(self):
        tool = EchoTool()
        result = tool.run({})
        assert result.tool_name == "echo"
        assert result.status == "ok"
        assert "(no arguments)" in result.output

    def test_run_with_args(self):
        tool = EchoTool()
        result = tool.run({"msg": "hello", "x": "y"})
        assert result.status == "ok"
        assert "msg=hello" in result.output
        assert "x=y" in result.output


class TestReadFileTool:
    def test_name_and_description(self):
        tool = ReadFileTool()
        assert tool.name == "read-file"
        assert len(tool.description) > 0
        assert "path" in tool.description.lower()

    def test_required_permissions(self):
        tool = ReadFileTool()
        assert tool.required_permissions == frozenset({Permission.FILESYSTEM_READ})

    def test_run_missing_path(self):
        tool = ReadFileTool()
        result = tool.run({})
        assert result.status == "error"
        assert "error_message" in result.metadata
        assert "path" in result.metadata["error_message"].lower()

    def test_run_empty_path(self):
        tool = ReadFileTool()
        result = tool.run({"path": "   "})
        assert result.status == "error"

    def test_run_reads_file(self, tmp_path):
        f = tmp_path / "foo.txt"
        f.write_text("hello world", encoding="utf-8")
        tool = ReadFileTool()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = tool.run({"path": "foo.txt"})
            assert result.status == "ok"
            assert result.output == "hello world"
        finally:
            os.chdir(old_cwd)

    def test_run_missing_file(self):
        tool = ReadFileTool()
        # Use path under cwd so we reach the file-not-found path (not path validation)
        result = tool.run({"path": "nonexistent_path_12345"})
        assert result.status == "error"
        assert "error_message" in result.metadata
        assert "not found" in result.metadata["error_message"].lower()

    @pytest.mark.invariant
    def test_read_file_dotdot_path_rejected(self):
        """Invariant: path with .. components is rejected."""
        tool = ReadFileTool()
        result = tool.run({"path": "../../etc/passwd"})
        assert result.status == "error"
        assert "error_message" in result.metadata
        assert ".." in result.metadata["error_message"].lower()

    @pytest.mark.invariant
    def test_read_file_absolute_path_outside_cwd_rejected(self):
        """Invariant: absolute path outside CWD is rejected."""
        tool = ReadFileTool()
        cwd = Path(os.getcwd()).resolve()
        # Path under parent of cwd is outside cwd
        parent_file = cwd.parent / "file_outside_cwd_ore_test"
        try:
            parent_file.write_text("x")
            res = tool.run({"path": str(parent_file)})
            assert res.status == "error"
            assert "error_message" in res.metadata
        finally:
            if parent_file.exists():
                parent_file.unlink()

    @pytest.mark.invariant
    def test_read_file_within_cwd_allowed(self, tmp_path):
        """Invariant: path under CWD is allowed."""
        f = tmp_path / "allowed.txt"
        f.write_text("allowed content", encoding="utf-8")
        tool = ReadFileTool()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = tool.run({"path": "allowed.txt"})
            assert result.status == "ok"
            assert result.output == "allowed content"
        finally:
            os.chdir(old_cwd)


class TestToolRegistry:
    def test_echo_registered(self):
        assert "echo" in TOOL_REGISTRY
        assert TOOL_REGISTRY["echo"].name == "echo"

    def test_read_file_registered(self):
        assert "read-file" in TOOL_REGISTRY
        assert TOOL_REGISTRY["read-file"].name == "read-file"

    def test_registry_lookup_returns_tool_instance(self):
        tool = TOOL_REGISTRY["echo"]
        result = tool.run({"k": "v"})
        assert result.tool_name == "echo"
        assert "k=v" in result.output
