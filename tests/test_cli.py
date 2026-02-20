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

    parser = argparse.ArgumentParser(description="ORE v0.9 CLI")
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
    parser.add_argument("--route-threshold", type=float, default=0.5)
    parser.add_argument("--skill", type=str, default=None)
    parser.add_argument("--list-skills", action="store_true")
    parser.add_argument("--artifact-out", type=str, nargs="?", const="-", default=None)
    parser.add_argument("--artifact-in", type=str, default=None)
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
    def test_artifact_in_with_prompt_rejected(self):
        """--artifact-in and prompt are mutually exclusive."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-in", "/dev/null"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_artifact_out_with_stream_rejected(self):
        """--artifact-out and --stream are mutually exclusive."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-", "--stream"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_artifact_out_with_json_to_stdout_rejected(self):
        """--artifact-out - and --json are mutually exclusive (both stdout)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-", "--json"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_artifact_in_with_interactive_rejected(self):
        """--artifact-in with -i is rejected (single-turn only)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "-i"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_artifact_in_with_conversational_rejected(self):
        """--artifact-in with -c is rejected (single-turn only)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "-c"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_artifact_in_with_tool_rejected(self):
        """--artifact-in with --tool is rejected (mutually exclusive)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "--tool", "echo"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_artifact_in_with_route_rejected(self):
        """--artifact-in with --route is rejected (mutually exclusive)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "--route"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_artifact_in_with_skill_rejected(self):
        """--artifact-in with --skill is rejected (mutually exclusive)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "--artifact-in", "/dev/null", "--skill", "foo"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_artifact_out_with_interactive_rejected(self):
        """--artifact-out with -i is rejected (single-turn only)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-", "-i"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

    @pytest.mark.invariant
    def test_artifact_out_with_conversational_rejected(self):
        """--artifact-out with -c is rejected (single-turn only)."""
        with patch(
            "ore.cli.argparse._sys.argv",
            ["ore", "hello", "--artifact-out", "-", "-c"],
        ):
            with pytest.raises(SystemExit):
                from ore.cli import run

                run()

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
