"""Tests for ore/tools.py — Tool interface and built-in tools."""

from __future__ import annotations

import pytest

from ore.gate import Permission
from ore.tools import DateTimeTool, EchoTool, ReadFileTool, TOOL_REGISTRY


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


class TestDateTimeTool:
    def test_name_and_description(self):
        tool = DateTimeTool()
        assert tool.name == "datetime"
        assert len(tool.description) > 0
        assert "timezone" in tool.description.lower()

    def test_required_permissions_empty(self):
        tool = DateTimeTool()
        assert tool.required_permissions == frozenset()

    def test_run_no_args_defaults_to_utc(self):
        tool = DateTimeTool()
        result = tool.run({})
        assert result.status == "ok"
        assert result.tool_name == "datetime"
        assert "timezone=UTC" in result.output

    def test_run_with_tz_arg(self):
        tool = DateTimeTool()
        result = tool.run({"tz": "America/New_York"})
        assert result.status == "ok"
        assert "timezone=America/New_York" in result.output

    def test_run_invalid_tz_returns_error(self):
        tool = DateTimeTool()
        result = tool.run({"tz": "Not/Real"})
        assert result.status == "error"
        assert "error_message" in result.metadata
        assert "Not/Real" in result.metadata["error_message"]
        assert "tzdata" in result.metadata["error_message"]

    def test_output_contains_expected_keys(self):
        tool = DateTimeTool()
        result = tool.run({})
        assert result.status == "ok"
        for key in ("date=", "time=", "weekday=", "timezone=", "iso="):
            assert key in result.output

    def test_run_with_format_arg(self):
        tool = DateTimeTool()
        result = tool.run({"format": "%Y/%m/%d"})
        assert result.status == "ok"
        assert "formatted=" in result.output

    def test_routing_hints_nonempty(self):
        tool = DateTimeTool()
        hints = tool.routing_hints()
        assert len(hints) > 0
        assert any("time" in h for h in hints)

    def test_extract_args_iana_tz_from_prompt(self):
        tool = DateTimeTool()
        args = tool.extract_args("what time is it in America/New_York")
        assert args.get("tz") == "America/New_York"

    def test_extract_args_utc_from_prompt(self):
        tool = DateTimeTool()
        args = tool.extract_args("what is the current time in UTC")
        assert args.get("tz") == "UTC"

    def test_extract_args_no_iana_name_returns_empty(self):
        # City-only or abbreviation names are not extracted (IANA-only policy)
        tool = DateTimeTool()
        assert tool.extract_args("what time is it in London") == {}
        assert tool.extract_args("current time in EST") == {}

    def test_extract_args_no_in_phrase_returns_empty(self):
        tool = DateTimeTool()
        assert tool.extract_args("what time is it") == {}


class TestToolRegistry:
    def test_echo_registered(self):
        assert "echo" in TOOL_REGISTRY
        assert TOOL_REGISTRY["echo"].name == "echo"

    def test_read_file_registered(self):
        assert "read-file" in TOOL_REGISTRY
        assert TOOL_REGISTRY["read-file"].name == "read-file"

    def test_datetime_registered(self):
        assert "datetime" in TOOL_REGISTRY
        assert TOOL_REGISTRY["datetime"].name == "datetime"

    def test_registry_lookup_returns_tool_instance(self):
        tool = TOOL_REGISTRY["echo"]
        result = tool.run({"k": "v"})
        assert result.tool_name == "echo"
        assert "k=v" in result.output
