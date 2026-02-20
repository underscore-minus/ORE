"""Tests for ore/tools.py — Tool interface and built-in tools."""

from __future__ import annotations

import pytest

from ore.gate import Permission
from ore.tools import EchoTool, ReadFileTool, TOOL_REGISTRY


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
        result = tool.run({"path": str(f)})
        assert result.status == "ok"
        assert result.output == "hello world"

    def test_run_missing_file(self):
        tool = ReadFileTool()
        result = tool.run({"path": "/nonexistent/path/12345"})
        assert result.status == "error"
        assert "error_message" in result.metadata
        assert "not found" in result.metadata["error_message"].lower()


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
