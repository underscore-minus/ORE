"""Tests for ore/cli.py — argument parsing and mode validation."""

from __future__ import annotations

import argparse
import io
import json
from unittest.mock import patch

import pytest

from .conftest import FakeReasoner


def _parse(args: list[str]) -> argparse.Namespace:
    """Parse args using ORE's real CLI parser (no model calls)."""
    from ore.cli import _build_parser

    return _build_parser().parse_args(args)


# Minimum CLI flag surface (interface lock): dest -> default. New flags allowed; these must exist.
_CLI_FLAG_SURFACE = {
    "prompt": None,
    "model": None,
    "list_models": False,
    "interactive": False,
    "conversational": False,
    "save_session": None,
    "resume_session": None,
    "stream": False,
    "verbose": False,
    "json": False,
    "tool": None,
    "tool_arg": [],
    "list_tools": False,
    "grant": [],
    "route": False,
    "route_threshold": 0.5,
    "skill": None,
    "list_skills": False,
    "artifact_out": None,
    "artifact_in": None,
}


class TestCliFrozenSurface:
    """Invariant tests: CLI parser has at least the frozen flag set with correct defaults."""

    @pytest.mark.invariant
    def test_cli_parser_has_minimum_flag_surface(self):
        """Invariant: parser has at least these flags with documented types/defaults."""
        from ore.cli import _build_parser

        parser = _build_parser()
        by_dest = {a.dest: a for a in parser._actions if a.dest is not None}
        for dest, expected_default in _CLI_FLAG_SURFACE.items():
            assert dest in by_dest, f"Missing CLI flag/option: {dest}"
            actual_default = getattr(by_dest[dest], "default", None)
            assert (
                actual_default == expected_default
            ), f"Flag {dest}: expected default {expected_default!r}, got {actual_default!r}"


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
    def test_interactive_and_conversational_rejected(self, capsys):
        """run() should exit when both -i and -c are given."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "-i", "-c"]):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "interactive" in err.lower() and "conversational" in err.lower()

    @pytest.mark.invariant
    def test_interactive_with_save_session_rejected(self, capsys):
        with patch("ore.cli.argparse._sys.argv", ["ore", "-i", "--save-session", "x"]):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "interactive" in err.lower() and "save-session" in err.lower()

    @pytest.mark.invariant
    def test_interactive_with_resume_session_rejected(self, capsys):
        with patch(
            "ore.cli.argparse._sys.argv", ["ore", "-i", "--resume-session", "x"]
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "interactive" in err.lower() and "resume-session" in err.lower()

    def test_no_prompt_no_mode_rejected(self, capsys):
        # TTY with no prompt → parser.error; avoid stdin read path
        with patch("ore.cli.argparse._sys.argv", ["ore"]):
            with patch("ore.cli.sys.stdin.isatty", return_value=True):
                with pytest.raises(SystemExit):
                    from ore.cli import run

                    run()
        err = capsys.readouterr().err
        assert "prompt" in err.lower()

    @pytest.mark.invariant
    def test_json_and_stream_rejected(self, capsys):
        with patch(
            "ore.cli.argparse._sys.argv", ["ore", "hello", "--json", "--stream"]
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "json" in err.lower() and "stream" in err.lower()

    @pytest.mark.invariant
    def test_json_and_interactive_rejected(self, capsys):
        with patch("ore.cli.argparse._sys.argv", ["ore", "-i", "--json"]):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "json" in err.lower() and "single-turn" in err.lower()

    @pytest.mark.invariant
    def test_json_and_conversational_rejected(self, capsys):
        with patch("ore.cli.argparse._sys.argv", ["ore", "-c", "--json"]):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "json" in err.lower() and "single-turn" in err.lower()

    @pytest.mark.invariant
    def test_route_and_tool_rejected(self, capsys):
        """--route and --tool are mutually exclusive."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hi", "--route", "--tool", "echo"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "route" in err.lower() and "tool" in err.lower()


# Exact key sets for --json output (interface lock). New keys may be added; these must exist.
_JSON_BASE_KEYS = frozenset({"id", "model_id", "content", "timestamp", "metadata"})
_JSON_ROUTING_KEYS = frozenset(
    {"target", "target_type", "confidence", "args", "reasoning", "id", "timestamp"}
)


class TestJsonOutput:
    """Smoke tests for --json output and stdin ingestion."""

    @pytest.mark.invariant
    def test_json_output_exact_base_keys(self, capsys):
        """Invariant: single-turn --json has exactly the 5 base keys (no extras)."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "hello", "--json"]):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert (
            set(data.keys()) == _JSON_BASE_KEYS
        ), f"Expected base keys {_JSON_BASE_KEYS}, got {set(data.keys())}"

    def test_json_output_keys(self, capsys):
        """Single-turn with --json produces valid JSON with required keys."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "hello", "--json"]):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert _JSON_BASE_KEYS <= set(data.keys())

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


class TestExitCodes:
    """Invariant tests: CLI exit code contract (0=success, 1=app error, 2=usage)."""

    @pytest.mark.invariant
    def test_list_tools_exits_0(self, capsys):
        """Invariant: --list-tools exits 0."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "--list-tools"]):
            with pytest.raises(SystemExit) as exc_info:
                from ore.cli import run

                run()
        assert exc_info.value.code == 0

    @pytest.mark.invariant
    def test_list_skills_exits_0_when_empty(self, capsys):
        """Invariant: --list-skills with no skills exits 0."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "--list-skills"]):
            with patch("ore.cli.build_skill_registry", return_value={}):
                with pytest.raises(SystemExit) as exc_info:
                    from ore.cli import run

                    run()
        assert exc_info.value.code == 0

    @pytest.mark.invariant
    def test_unknown_tool_exits_1(self, capsys):
        """Invariant: unknown --tool name exits 1."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hi", "--tool", "nonexistent-tool"],
        ):
            with patch("ore.cli.default_model", return_value="fake-model"):
                with pytest.raises(SystemExit) as exc_info:
                    from ore.cli import run

                    run()
        assert exc_info.value.code == 1

    @pytest.mark.invariant
    def test_unknown_grant_exits_1(self, capsys):
        """Invariant: unknown --grant value exits 1."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hi", "--grant", "invalid-perm"],
        ):
            with patch("ore.cli.default_model", return_value="fake-model"):
                with pytest.raises(SystemExit) as exc_info:
                    from ore.cli import run

                    run()
        assert exc_info.value.code == 1


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

    @pytest.mark.invariant
    def test_route_with_json_routing_object_exact_keys(self, capsys):
        """Invariant: --route with --json: routing object has exact keys."""
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
        assert "routing" in data
        assert (
            set(data["routing"].keys()) == _JSON_ROUTING_KEYS
        ), f"Expected routing keys {_JSON_ROUTING_KEYS}, got {set(data['routing'].keys())}"
        assert data["routing"]["target"] == "echo"

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


class TestSkillCli:
    """Tests for v0.8 --skill / --list-skills."""

    @pytest.fixture(autouse=True)
    def _skill_fixtures(self, tmp_path):
        """Create a minimal skill directory for CLI tests."""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test skill\n"
            "hints:\n  - activate test\n---\n\nBe concise and factual.\n",
            encoding="utf-8",
        )
        self._skills_root = tmp_path
        self._skill_registry = {
            "test-skill": __import__(
                "ore.types", fromlist=["SkillMetadata"]
            ).SkillMetadata(
                name="test-skill",
                description="A test skill",
                hints=["activate test"],
                path=skill_dir,
            )
        }

    def test_list_skills_flag(self, capsys):
        """--list-skills prints discovered skills and exits 0."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "--list-skills"]):
            with patch(
                "ore.cli.build_skill_registry", return_value=self._skill_registry
            ):
                with pytest.raises(SystemExit) as exc_info:
                    from ore.cli import run

                    run()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "test-skill" in out
        assert "A test skill" in out

    def test_list_skills_empty(self, capsys):
        """--list-skills with no skills prints message and exits 0."""
        with patch("ore.cli.argparse._sys.argv", ["ore", "--list-skills"]):
            with patch("ore.cli.build_skill_registry", return_value={}):
                with pytest.raises(SystemExit) as exc_info:
                    from ore.cli import run

                    run()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "No skills" in out

    def test_skill_flag_loads_and_injects(self, capsys):
        """--skill NAME loads instructions and passes skill_context to engine."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--skill", "test-skill", "--json"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    with patch(
                        "ore.cli.build_skill_registry",
                        return_value=self._skill_registry,
                    ):
                        from ore.cli import run

                        run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["content"] == "fake response"

    def test_skill_and_tool_coexist(self, capsys):
        """--skill and --tool can be used together."""
        with patch(
            "ore.cli.argparse._sys.argv",
            [
                "ore",
                "hello",
                "--skill",
                "test-skill",
                "--tool",
                "echo",
                "--tool-arg",
                "msg=hi",
                "--json",
            ],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    with patch(
                        "ore.cli.build_skill_registry",
                        return_value=self._skill_registry,
                    ):
                        from ore.cli import run

                        run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["content"] == "fake response"

    def test_unknown_skill_exits(self, capsys):
        """--skill with unknown name prints error and exits 1."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--skill", "nonexistent"],
        ):
            with patch("ore.cli.default_model", return_value="fake-model"):
                with patch("ore.cli.build_skill_registry", return_value={}):
                    with pytest.raises(SystemExit) as exc_info:
                        from ore.cli import run

                        run()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "Unknown skill" in err

    def test_route_selects_skill(self, capsys):
        """--route with a skill-matching prompt dispatches correctly."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "activate test please", "--route", "--json"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    with patch(
                        "ore.cli.build_skill_registry",
                        return_value=self._skill_registry,
                    ):
                        from ore.cli import run

                        run()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "content" in data
        assert "routing" in data
        assert data["routing"]["target"] == "test-skill"
        assert data["routing"]["target_type"] == "skill"


class TestArtifactCli:
    """Tests for v0.9 --artifact-out / --artifact-in."""

    def test_artifact_out_includes_required_keys(self, tmp_path, capsys):
        """--artifact-out produces valid JSON with artifact_version and required keys."""
        out_path = tmp_path / "artifact.json"
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", str(out_path)],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        captured = capsys.readouterr()
        assert "[AYA]:" in captured.out
        data = json.loads(out_path.read_text())
        assert data["artifact_version"] == "ore.exec.v1"
        assert "execution_id" in data
        assert "timestamp" in data
        assert "input" in data
        assert data["input"]["prompt"] == "hello"
        assert data["input"]["model_id"] == "fake-model"
        assert data["input"]["mode"] == "single_turn"
        assert "output" in data
        assert data["output"]["content"] == "fake response"
        assert "continuation" in data
        assert "requested" in data["continuation"]

    def test_artifact_out_to_stdout(self, capsys):
        """--artifact-out - writes artifact JSON to stdout."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["artifact_version"] == "ore.exec.v1"
        assert data["input"]["prompt"] == "hello"
        assert data["output"]["content"] == "fake response"

    def test_artifact_out_stdout_always_allowed(self, capsys):
        """--artifact-out - (stdout) is always allowed; no path validation."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["artifact_version"] == "ore.exec.v1"

    def test_artifact_out_cwd_path_allowed(self, tmp_path, capsys):
        """--artifact-out to a path under cwd is allowed."""
        out_path = tmp_path / "artifact.json"
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", str(out_path)],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        data = json.loads(out_path.read_text())
        assert data["artifact_version"] == "ore.exec.v1"
        assert data["input"]["prompt"] == "hello"

    def test_artifact_out_dotdot_path_rejected(self, capsys):
        """--artifact-out with .. in path is rejected (exit 1)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "../../etc/artifact.json"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    with pytest.raises(SystemExit) as exc_info:
                        from ore.cli import run

                        run()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert ".." in err or "Artifact" in err

    def test_artifact_in_reproduces_prompt(self, tmp_path, capsys):
        """--artifact-in runs single-turn with artifact's input.prompt."""
        artifact_path = tmp_path / "prev.json"
        artifact_path.write_text(
            json.dumps(
                {
                    "artifact_version": "ore.exec.v1",
                    "execution_id": "x",
                    "timestamp": 1.0,
                    "input": {
                        "prompt": "prompt from artifact",
                        "model_id": "fake-model",
                        "mode": "single_turn",
                    },
                    "output": {
                        "id": "x",
                        "content": "old response",
                        "model_id": "fake-model",
                        "timestamp": 1.0,
                        "metadata": {},
                    },
                    "continuation": {"requested": False, "reason": None},
                }
            )
        )
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", str(artifact_path)],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        captured = capsys.readouterr()
        assert "prompt from artifact" not in captured.out  # That was input
        assert "fake response" in captured.out  # New reasoner response

    def test_artifact_in_from_stdin(self, capsys):
        """--artifact-in - reads artifact from stdin."""
        artifact_json = json.dumps(
            {
                "artifact_version": "ore.exec.v1",
                "execution_id": "x",
                "timestamp": 1.0,
                "input": {
                    "prompt": "stdin artifact prompt",
                    "model_id": "fake-model",
                    "mode": "single_turn",
                },
                "output": {
                    "id": "x",
                    "content": "old",
                    "model_id": "fake-model",
                    "timestamp": 1.0,
                    "metadata": {},
                },
                "continuation": {"requested": False, "reason": None},
            }
        )
        fake_stdin = io.StringIO(artifact_json)
        with patch("ore.cli.argparse._sys.argv", ["ore", "--artifact-in", "-"]):
            with patch("ore.cli.sys.stdin", fake_stdin):
                with patch("ore.cli.AyaReasoner", FakeReasoner):
                    with patch("ore.cli.default_model", return_value="fake-model"):
                        from ore.cli import run

                        run()
        captured = capsys.readouterr()
        assert "fake response" in captured.out

    def test_artifact_out_file_with_json(self, tmp_path, capsys):
        """--artifact-out FILE --json: JSON on stdout, artifact in file."""
        out_path = tmp_path / "artifact.json"
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", str(out_path), "--json"],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "id" in data
        assert "content" in data
        assert data["content"] == "fake response"
        artifact_data = json.loads(out_path.read_text())
        assert artifact_data["artifact_version"] == "ore.exec.v1"
        assert artifact_data["input"]["prompt"] == "hello"
        assert artifact_data["output"]["content"] == "fake response"

    def test_artifact_in_then_artifact_out(self, tmp_path, capsys):
        """--artifact-in X --artifact-out Y: consume artifact, produce new artifact (chaining)."""
        in_path = tmp_path / "prev.json"
        out_path = tmp_path / "next.json"
        in_path.write_text(
            json.dumps(
                {
                    "artifact_version": "ore.exec.v1",
                    "execution_id": "prev",
                    "timestamp": 1.0,
                    "input": {
                        "prompt": "chained prompt",
                        "model_id": "fake-model",
                        "mode": "single_turn",
                    },
                    "output": {
                        "id": "prev",
                        "content": "old response",
                        "model_id": "fake-model",
                        "timestamp": 1.0,
                        "metadata": {},
                    },
                    "continuation": {"requested": False, "reason": None},
                }
            )
        )
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", str(in_path), "--artifact-out", str(out_path)],
        ):
            with patch("ore.cli.AyaReasoner", FakeReasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        captured = capsys.readouterr()
        assert "fake response" in captured.out
        artifact_data = json.loads(out_path.read_text())
        assert artifact_data["artifact_version"] == "ore.exec.v1"
        assert artifact_data["input"]["prompt"] == "chained prompt"
        assert artifact_data["output"]["content"] == "fake response"

    def test_artifact_in_malformed_json_exits_1(self, capsys):
        """--artifact-in - with malformed JSON on stdin exits 1."""
        fake_stdin = io.StringIO("not json at all")
        with patch("ore.cli.argparse._sys.argv", ["ore", "--artifact-in", "-"]):
            with patch("ore.cli.sys.stdin", fake_stdin):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    with pytest.raises(SystemExit) as exc_info:
                        from ore.cli import run

                        run()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "invalid" in err.lower() or "json" in err.lower()

    def test_invalid_artifact_exits_1(self, capsys):
        """Invalid artifact (missing version) exits 1 with stderr message."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "-"],
        ):
            with patch("ore.cli.sys.stdin", io.StringIO('{"input":{},"output":{}}')):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    with pytest.raises(SystemExit) as exc_info:
                        from ore.cli import run

                        run()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "artifact_version" in err or "Invalid artifact" in err

    @pytest.mark.invariant
    def test_artifact_in_with_prompt_rejected(self, capsys):
        """--artifact-in and prompt are mutually exclusive."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-in", "/dev/null"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-in" in err.lower() and "prompt" in err.lower()

    @pytest.mark.invariant
    def test_artifact_out_with_stream_rejected(self, capsys):
        """--artifact-out and --stream are mutually exclusive."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-", "--stream"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-out" in err.lower() and "stream" in err.lower()

    @pytest.mark.invariant
    def test_artifact_out_with_json_to_stdout_rejected(self, capsys):
        """--artifact-out - and --json are mutually exclusive (both stdout)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-", "--json"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-out" in err.lower() and "json" in err.lower()

    @pytest.mark.invariant
    def test_artifact_in_with_interactive_rejected(self, capsys):
        """--artifact-in with -i is rejected (single-turn only)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "-i"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-in" in err.lower() and (
            "single-turn" in err.lower() or "repl" in err.lower()
        )

    @pytest.mark.invariant
    def test_artifact_in_with_conversational_rejected(self, capsys):
        """--artifact-in with -c is rejected (single-turn only)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "-c"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-in" in err.lower() and (
            "single-turn" in err.lower() or "repl" in err.lower()
        )

    @pytest.mark.invariant
    def test_artifact_in_with_tool_rejected(self, capsys):
        """--artifact-in with --tool is rejected (mutually exclusive)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "--tool", "echo"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-in" in err.lower() and "mutually exclusive" in err.lower()

    @pytest.mark.invariant
    def test_artifact_in_with_route_rejected(self, capsys):
        """--artifact-in with --route is rejected (mutually exclusive)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "--route"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-in" in err.lower() and "mutually exclusive" in err.lower()

    @pytest.mark.invariant
    def test_artifact_in_with_skill_rejected(self, capsys):
        """--artifact-in with --skill is rejected (mutually exclusive)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "--skill", "foo"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-in" in err.lower() and "mutually exclusive" in err.lower()

    @pytest.mark.invariant
    def test_artifact_out_with_interactive_rejected(self, capsys):
        """--artifact-out with -i is rejected (single-turn only)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-", "-i"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-out" in err.lower() and (
            "single-turn" in err.lower() or "repl" in err.lower()
        )

    @pytest.mark.invariant
    def test_artifact_out_with_conversational_rejected(self, capsys):
        """--artifact-out with -c is rejected (single-turn only)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-", "-c"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()
        err = capsys.readouterr().err
        assert "artifact-out" in err.lower() and (
            "single-turn" in err.lower() or "repl" in err.lower()
        )

    @pytest.mark.invariant
    def test_reasoner_called_once_with_artifact_out(self, tmp_path):
        """One reasoner call per artifact-driven turn (invariant)."""
        out_path = tmp_path / "artifact.json"
        reasoner_instance: list[FakeReasoner] = []

        def capture_reasoner(*args: object, **kwargs: object) -> FakeReasoner:
            inst = FakeReasoner(*args, **kwargs)
            reasoner_instance.append(inst)
            return inst

        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", str(out_path)],
        ):
            with patch("ore.cli.AyaReasoner", side_effect=capture_reasoner):
                with patch("ore.cli.default_model", return_value="fake-model"):
                    from ore.cli import run

                    run()
        assert len(reasoner_instance) == 1
        assert reasoner_instance[0].reason_call_count == 1
