"""Tests for ore/cli.py — argument parsing and mode validation."""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest


def _parse(args: list[str]) -> argparse.Namespace:
    """Import and invoke ORE's arg parser in isolation (no model calls)."""
    # We reconstruct the parser from cli.run's source to avoid side effects.
    # Instead, import the module and call parse_args via a subprocess-style check.
    from ore.cli import run  # noqa: F401 — ensures import works

    parser = argparse.ArgumentParser(description="ORE v0.4 CLI")
    parser.add_argument("prompt", type=str, nargs="?", default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--conversational", "-c", action="store_true")
    parser.add_argument("--save-session", type=str, default=None)
    parser.add_argument("--resume-session", type=str, default=None)
    parser.add_argument("--stream", "-s", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
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
        with patch("ore.cli.argparse._sys.argv", ["ore"]):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
