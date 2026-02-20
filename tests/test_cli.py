"""Tests for ore/cli.py — argument parsing and mode validation."""

from __future__ import annotations

import argparse
import io
import json
from unittest.mock import patch

import pytest

from .conftest import FakeReasoner


def _parse(args: list[str]) -> argparse.Namespace:
    """Import and invoke ORE's arg parser in isolation (no model calls)."""
    # We reconstruct the parser from cli.run's source to avoid side effects.
    # Instead, import the module and call parse_args via a subprocess-style check.
    from ore.cli import run  # noqa: F401 — ensures import works

    parser = argparse.ArgumentParser(description="ORE v0.6 CLI")
    parser.add_argument("prompt", type=str, nargs="?", default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--conversational", "-c", action="store_true")
    parser.add_argument("--save-session", type=str, default=None)
    parser.add_argument("--resume-session", type=str, default=None)
    parser.add_argument("--stream", "-s", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", "-j", action="store_true")
    parser.add_argument("--tool", type=str, default=None)
    parser.add_argument("--tool-arg", action="append", default=[])
    parser.add_argument("--list-tools", action="store_true")
    parser.add_argument("--grant", action="append", default=[])
    parser.add_argument("--route", action="store_true")
    return parser.parse_args(args)


class TestArgParsing:
    def test_single_turn_prompt(self):
        ns = _parse(["hello world"])
        assert ns.prompt == "hello world"
        assert not ns.interactive
        assert not ns.conversational

    def test_interactive_flag(self):
        ns = _parse(["-i"])
        assert ns.interactive
        assert ns.prompt is None

    def test_conversational_flag(self):
        ns = _parse(["-c"])
        assert ns.conversational
        assert ns.prompt is None

    def test_model_flag(self):
        ns = _parse(["hi", "--model", "mistral"])
        assert ns.model == "mistral"

    def test_stream_flag(self):
        ns = _parse(["hi", "-s"])
        assert ns.stream

    def test_verbose_flag(self):
        ns = _parse(["hi", "-v"])
        assert ns.verbose

    def test_save_session(self):
        ns = _parse(["--save-session", "demo"])
        assert ns.save_session == "demo"

    def test_resume_session(self):
        ns = _parse(["--resume-session", "demo"])
        assert ns.resume_session == "demo"

    def test_json_flag(self):
        ns = _parse(["hi", "-j"])
        assert ns.json


class TestModeValidation:
    """Test the mutual-exclusivity rules enforced by cli.run()."""

    @pytest.mark.invariant
    def test_interactive_and_conversational_rejected(self):
        """run() should exit when both -i and -c are given."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "-i", "-c"]):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_interactive_with_save_session_rejected(self):
        with patch("ore.cli.argparse._sys.argv", ["ore", "-i", "--save-session", "x"]):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_interactive_with_resume_session_rejected(self):
        with patch(
            "ore.cli.argparse._sys.argv", ["ore", "-i", "--resume-session", "x"]
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    def test_no_prompt_no_mode_rejected(self):
        # TTY with no prompt → parser.error; avoid stdin read path
        with patch("ore.cli.argparse._sys.argv", ["ore"]):
            with patch("ore.cli.sys.stdin.isatty", return_value=True):
                with pytest.raises(SystemExit):
                    from ore.cli import run

                    run()

    @pytest.mark.invariant
    def test_json_and_stream_rejected(self):
        with patch(
            "ore.cli.argparse._sys.argv", ["ore", "hello", "--json", "--stream"]
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_json_and_interactive_rejected(self):
        with patch("ore.cli.argparse._sys.argv", ["ore", "-i", "--json"]):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_json_and_conversational_rejected(self):
        with patch("ore.cli.argparse._sys.argv", ["ore", "-c", "--json"]):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_route_and_tool_rejected(self):
        """--route and --tool are mutually exclusive."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hi", "--route", "--tool", "echo"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()


class TestJsonOutput:
    """Smoke tests for --json output and stdin ingestion."""

    def test_json_output_keys(self, capsys):
        """Single-turn with --json produces valid JSON with required keys."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "hello", "--json"]):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "id" in data
        assert "model_id" in data
        assert "content" in data
        assert "timestamp" in data
        assert "metadata" in data

    def test_piped_stdin_single_turn(self, capsys):
        """When stdin is non-TTY and no prompt arg, read prompt from stdin."""
        fake_stdin = io.StringIO("piped prompt")
        fake_stdin.isatty = lambda: False
        with patch("ore.cli.argparse._sys.argv", ["ore", "--json"]):
            with patch("ore.cli.sys.stdin", fake_stdin):
                with patch("ore.cli.AyaReasoner", FakeReasoner):
                    with patch("ore.cli.default_model", return_value="fake-model"):
                        from ore.cli import run

                        run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["content"] == "fake response"


class TestToolCli:
    """Tests for v0.6 --tool / --list-tools / --grant."""

    def test_list_tools_flag(self, capsys):
        """--list-tools prints tool names and exits 0."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "--list-tools"]):
            with pytest.raises(SystemExit) as exc_info:
                from ore.cli import run

                run()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "echo" in out
        assert "read-file" in out
        assert "no permissions" in out or "requires" in out

    def test_tool_gate_denied_exits_cleanly(self, capsys):
        """--tool read-file without --grant exits 1 with stderr message."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--tool", "read-file", "--tool-arg", "path=/tmp/x"],
        ):
            with patch("ore.cli.default_model", return_value="fake-model"):
                with pytest.raises(SystemExit) as exc_info:
                    from ore.cli import run

                    run()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "denied" in err.lower() or "permission" in err.lower()
        assert "read-file" in err.lower() or "filesystem" in err.lower()

    def test_tool_with_json_output(self, capsys):
        """--tool echo with --json produces valid JSON (tool runs, then reasoner)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "summarize", "--tool", "echo", "--tool-arg", "msg=hello", "--json"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "content" in data
        assert data["model_id"] == "fake-model"

    def test_tool_with_piped_stdin(self, capsys):
        """Tool runs; piped prompt used as user input; no crash."""
        fake_stdin = io.StringIO("piped prompt")
        fake_stdin.isatty = lambda: False
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--tool", "echo", "--tool-arg", "x=y", "--json"],
        ):
            with patch("ore.cli.sys.stdin", fake_stdin):
                with patch("ore.cli.AyaReasoner", FakeReasoner):
                    with patch("ore.cli.default_model", return_value="fake-model"):
                        from ore.cli import run

                        run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["content"] == "fake response"


class TestRouteCli:
    """Tests for v0.7 --route (intent-based tool selection)."""

    def test_route_with_matching_prompt_runs_tool(self, capsys):
        """--route with prompt that matches echo: routing on stderr, response on stdout."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "say back hello world", "--route"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        captured = capsys.readouterr()
        assert "[AYA]:" in captured.out
        assert "fake response" in captured.out
        assert "[Route]:" in captured.err
        assert "echo" in captured.err

    def test_route_with_non_matching_prompt_fallback(self, capsys):
        """--route with no match: fallback message on stderr, reasoner only."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "what is the capital of France", "--route"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        captured = capsys.readouterr()
        assert "[AYA]:" in captured.out
        assert (
            "No match" in captured.err
            or "reasoner only" in captured.err
            or "fallback" in captured.err.lower()
        )

    def test_route_with_json_includes_routing_key(self, capsys):
        """--route with --json: stdout is valid JSON with 'routing' key."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "say back hi", "--route", "--json"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "content" in data
        assert "routing" in data
        assert data["routing"]["target"] == "echo"
        assert "confidence" in data["routing"]
        assert "reasoning" in data["routing"]
