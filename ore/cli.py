"""
CLI layer: argument parsing and printing the reasoning output.
v0.2 adds an interactive loop (REPL); each turn remains stateless.
v0.3 adds --conversational (-c): a REPL where the session accumulates.
v0.4 adds --save-session / --resume-session for opt-in file persistence.
v0.5 adds --json / -j for structured output and stdin ingestion for piped prompts.
v0.6 adds --tool / --tool-arg / --list-tools / --grant for tool & gate framework.
v0.7 adds --route for intent-based tool selection (routing info to stderr).
v0.8 adds --skill / --list-skills for skill activation; routing merges tool + skill targets.
v0.9 adds --artifact-out / --artifact-in for chainable execution artifacts.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ._version import __version__
from .core import ORE
from .gate import Gate, GateError, Permission
from .models import default_model, fetch_models
from .reasoner import AyaReasoner
from .reasoner_deepseek import DeepSeekReasoner
from .router import RuleRouter, build_targets_from_registry
from .skills import (
    build_skill_registry,
    build_targets_from_skill_registry,
    load_skill_instructions,
)
from .store import FileSessionStore
from .tools import TOOL_REGISTRY
from .types import (
    ExecutionArtifact,
    Response,
    RoutingDecision,
    Session,
    SkillMetadata,
    ToolResult,
)

# Commands that exit any REPL mode (case-insensitive)
_REPL_EXIT_COMMANDS = frozenset({"quit", "exit"})


def _validate_output_path(path: str) -> Path:
    """
    Validate artifact output path. Rejects .. components; warns if outside cwd.
    Returns resolved Path. Raises ValueError if path contains .. components.
    Caller must skip validation when path == "-" (stdout).
    """
    p = Path(path)
    if ".." in p.parts:
        raise ValueError(
            f"Artifact output path must not contain .. components: {path!r}"
        )
    resolved = p.resolve()
    cwd = Path(os.getcwd()).resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError:
        print(
            f"Warning: artifact output path is outside working directory: {resolved}",
            file=sys.stderr,
        )
    return resolved


def _load_artifact_and_set_prompt(args: argparse.Namespace) -> None:
    """
    Load artifact from --artifact-in path, validate, and set args.prompt (and
    args.model if not overridden). Exits 1 on invalid artifact.
    """
    path = args.artifact_in
    if path == "-":
        raw = sys.stdin.read()
    else:
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"Artifact file not found: {path}", file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            print(f"Error reading artifact: {e}", file=sys.stderr)
            sys.exit(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Invalid artifact JSON: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        artifact = ExecutionArtifact.from_dict(data)
    except ValueError as e:
        print(f"Invalid artifact: {e}", file=sys.stderr)
        sys.exit(1)
    args.prompt = artifact.input.prompt
    if args.model is None:
        args.model = artifact.input.model_id


def _parse_tool_args(tool_arg_list: Optional[List[str]]) -> dict:
    """Parse --tool-arg key=value list into a dict. First '=' splits key and value."""
    if not tool_arg_list:
        return {}
    out: dict = {}
    for s in tool_arg_list:
        if "=" in s:
            k, _, v = s.partition("=")
            out[k.strip()] = v.strip()
        else:
            out[s.strip()] = ""
    return out


def _get_tool_results(
    tool_name: Optional[str],
    tool_arg_list: Optional[List[str]],
    gate: Gate,
) -> Optional[List[ToolResult]]:
    """
    If tool_name is set, resolve tool, run through gate, return [result].
    On unknown tool or GateError: print to stderr and exit(1).
    """
    if not tool_name:
        return None
    if tool_name not in TOOL_REGISTRY:
        print(f"Unknown tool: {tool_name}", file=sys.stderr)
        sys.exit(1)
    tool = TOOL_REGISTRY[tool_name]
    args = _parse_tool_args(tool_arg_list)
    try:
        result = gate.run(tool, args)
        return [result]
    except GateError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def _get_skill_context(
    skill_name: Optional[str],
    skill_registry: Dict[str, SkillMetadata],
) -> Optional[List[str]]:
    """
    If skill_name is set, load its instructions and return as skill_context.
    On unknown skill: print to stderr and exit(1).
    """
    if not skill_name:
        return None
    if skill_name not in skill_registry:
        print(f"Unknown skill: {skill_name}", file=sys.stderr)
        sys.exit(1)
    meta = skill_registry[skill_name]
    instructions = load_skill_instructions(meta.path)
    return [f"[Skill:{skill_name}]\n{instructions}"]


def _route_and_dispatch(
    prompt: str,
    gate: Gate,
    verbose: bool,
    skill_registry: Dict[str, SkillMetadata],
    confidence_threshold: float = 0.5,
) -> Tuple[Optional[List[ToolResult]], Optional[List[str]], RoutingDecision]:
    """
    Run router on prompt (tool + skill targets merged); dispatch to the
    selected target. Returns (tool_results, skill_context, decision).
    All routing info is printed to stderr so stdout stays clean for JSON.
    """
    targets = build_targets_from_registry(TOOL_REGISTRY)
    targets += build_targets_from_skill_registry(skill_registry)
    decision = RuleRouter(confidence_threshold=confidence_threshold).route(
        prompt, targets
    )
    # Always print routing to stderr (visible, non-silent)
    if decision.target is None:
        print(
            f"[Route]: No match, using reasoner only. {decision.reasoning}",
            file=sys.stderr,
        )
        return None, None, decision
    print(
        f"[Route]: {decision.target} (confidence: {decision.confidence:.2f}) — {decision.reasoning}",
        file=sys.stderr,
    )
    if verbose:
        print(
            f"  routing_id={decision.id} target_type={decision.target_type} args={decision.args}",
            file=sys.stderr,
        )

    # Dispatch based on target type
    if decision.target_type == "skill":
        meta = skill_registry[decision.target]
        instructions = load_skill_instructions(meta.path)
        skill_ctx = [f"[Skill:{decision.target}]\n{instructions}"]
        return None, skill_ctx, decision

    # target_type == "tool"
    tool = TOOL_REGISTRY[decision.target]
    args = tool.extract_args(prompt) or decision.args
    decision = RoutingDecision(
        target=decision.target,
        target_type=decision.target_type,
        confidence=decision.confidence,
        args=args,
        reasoning=decision.reasoning,
        id=decision.id,
        timestamp=decision.timestamp,
    )
    try:
        result = gate.run(tool, args)
        return [result], None, decision
    except GateError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def _print_json_response(
    response: Response,
    routing: Optional[RoutingDecision] = None,
) -> None:
    """Serialize Response to JSON and print to stdout. If routing given, include it."""
    payload = {
        "id": response.id,
        "model_id": response.model_id,
        "content": response.content,
        "timestamp": response.timestamp,
        "metadata": response.metadata,
    }
    if routing is not None:
        payload["routing"] = {
            "target": routing.target,
            "target_type": routing.target_type,
            "confidence": routing.confidence,
            "args": routing.args,
            "reasoning": routing.reasoning,
            "id": routing.id,
            "timestamp": routing.timestamp,
        }
    print(json.dumps(payload))


def _print_response(response: Response, verbose: bool = False) -> None:
    """Print a single response to stdout (content + optional metadata)."""
    print(f"\n[AYA]: {response.content}")
    if verbose:
        print(f"\n[Metadata]: ID {response.id} | Model {response.model_id}")
        if response.metadata:
            print(f"  Usage: {response.metadata}")


def _stream_turn(
    engine: ORE,
    prompt: str,
    session: Optional[Session],
    verbose: bool,
    tool_results: Optional[List[ToolResult]] = None,
    skill_context: Optional[List[str]] = None,
) -> Response:
    """Drive the streaming generator, print chunks as they arrive, return final Response."""
    gen = engine.execute_stream(
        prompt, session=session, tool_results=tool_results, skill_context=skill_context
    )
    print("[AYA]: ", end="", flush=True)
    try:
        while True:
            print(next(gen), end="", flush=True)
    except StopIteration as exc:
        response = exc.value
    print()
    if verbose:
        print(f"\n[Metadata]: ID {response.id} | Model {response.model_id}")
        if response.metadata:
            print(f"  Usage: {response.metadata}")
    return response


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser. Exposed for invariant tests (frozen surface)."""
    parser = argparse.ArgumentParser(description=f"ORE {__version__} CLI")
    parser.add_argument(
        "prompt",
        type=str,
        nargs="?",
        default=None,
        help="User prompt (omit when using --list-models, --interactive, or --conversational)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        metavar="NAME",
        help="Ollama model name (default: first available, e.g. llama3.2)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["ollama", "deepseek"],
        default="ollama",
        help="Reasoner backend: ollama (local) or deepseek (API); default ollama",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available Ollama models and exit",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run an interactive loop (REPL); each turn is stateless, no history",
    )
    parser.add_argument(
        "--conversational",
        "-c",
        action="store_true",
        help=(
            "Run a conversational loop (REPL with memory); "
            "prior turns are visible to the reasoner each turn"
        ),
    )
    parser.add_argument(
        "--save-session",
        type=str,
        default=None,
        metavar="NAME",
        help="Save session to ~/.ore/sessions/ after each turn (implies -c)",
    )
    parser.add_argument(
        "--resume-session",
        type=str,
        default=None,
        metavar="NAME",
        help="Resume session from ~/.ore/sessions/ (implies -c)",
    )
    parser.add_argument(
        "--stream",
        "-s",
        action="store_true",
        help="Stream output token-by-token (optional, any mode)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show response metadata (ID, model, token counts)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output response as JSON (single-turn only; incompatible with --stream)",
    )
    parser.add_argument(
        "--tool",
        type=str,
        default=None,
        metavar="NAME",
        help="Run a built-in tool before reasoning (single tool per turn); use --grant for permissions",
    )
    parser.add_argument(
        "--tool-arg",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Argument for the tool (repeatable); e.g. path=/tmp/foo or msg=hello",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and their required permissions, then exit",
    )
    parser.add_argument(
        "--grant",
        action="append",
        default=[],
        metavar="PERM",
        help="Grant a permission for this run (repeatable); e.g. filesystem-read, network",
    )
    parser.add_argument(
        "--route",
        action="store_true",
        help="Route prompt to a tool or skill by intent; mutually exclusive with --tool",
    )
    parser.add_argument(
        "--route-threshold",
        type=float,
        default=0.5,
        metavar="FLOAT",
        help="Confidence threshold for --route (0.0–1.0, default 0.5); lower = more permissive",
    )
    parser.add_argument(
        "--skill",
        type=str,
        default=None,
        metavar="NAME",
        help="Activate a skill by name (v0.8); injects instructions into context",
    )
    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="List discovered skills from ~/.ore/skills/ and exit",
    )
    parser.add_argument(
        "--artifact-out",
        type=str,
        nargs="?",
        const="-",
        default=None,
        metavar="PATH",
        help=(
            "Emit execution artifact (v0.9). PATH or - for stdout; omit for no artifact. "
            "Single-turn only; incompatible with --stream."
        ),
    )
    parser.add_argument(
        "--artifact-in",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Read artifact from PATH (or - for stdin) and run single-turn with its input. "
            "Mutually exclusive with prompt arg and REPL modes."
        ),
    )
    parser.add_argument(
        "--system",
        type=str,
        default="",
        metavar="PROMPT",
        help="System prompt for the reasoner (default: none)",
    )
    return parser


def run() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.route and args.tool:
        parser.error("--route and --tool are mutually exclusive")
    if args.interactive and args.conversational:
        parser.error("--interactive and --conversational are mutually exclusive")
    if args.interactive and (args.save_session or args.resume_session):
        parser.error(
            "--interactive cannot be used with --save-session or --resume-session"
        )

    # v0.9 artifact validation
    if args.artifact_in is not None:
        if args.prompt is not None:
            parser.error("--artifact-in and prompt are mutually exclusive")
        if (
            args.interactive
            or args.conversational
            or args.save_session
            or args.resume_session
        ):
            parser.error(
                "--artifact-in is single-turn only; incompatible with REPL modes"
            )
        if args.tool or args.route or args.skill:
            parser.error(
                "--artifact-in is mutually exclusive with --tool, --route, --skill"
            )
    if args.artifact_out is not None:
        if args.stream:
            parser.error("--artifact-out and --stream are mutually exclusive")
        if (
            args.interactive
            or args.conversational
            or args.save_session
            or args.resume_session
        ):
            parser.error(
                "--artifact-out is single-turn only; incompatible with REPL modes"
            )
        if args.json and (args.artifact_out == "-" or args.artifact_out is None):
            parser.error(
                "--artifact-out to stdout and --json are mutually exclusive "
                "(both write to stdout)"
            )

    if args.list_models:
        if args.backend == "deepseek":
            print(
                "DeepSeek backend uses --model to specify the model (default: deepseek-chat)."
            )
            sys.exit(0)
        models = fetch_models()
        if not models:
            print("No Ollama models found. Install one with e.g. ollama pull llama3.2")
            sys.exit(1)
        print("Available Ollama models:")
        for name in sorted(models):
            print(f"  {name}")
        sys.exit(0)

    if args.list_tools:
        print("Available tools (use --tool NAME; grant permissions with --grant PERM):")
        valid_perms = [p.value for p in Permission]
        for name in sorted(TOOL_REGISTRY.keys()):
            tool = TOOL_REGISTRY[name]
            perms = ", ".join(
                p.value
                for p in sorted(tool.required_permissions, key=lambda x: x.value)
            )
            req = f" [requires: {perms}]" if perms else " [no permissions]"
            print(f"  {name}{req}")
            print(f"    {tool.description}")
        print("\nValid --grant values:", ", ".join(valid_perms))
        sys.exit(0)

    # Build skill registry once at startup (scans ~/.ore/skills/)
    skill_registry = build_skill_registry()

    if args.list_skills:
        if not skill_registry:
            print("No skills found in ~/.ore/skills/")
            sys.exit(0)
        print("Available skills (use --skill NAME):")
        for name in sorted(skill_registry.keys()):
            meta = skill_registry[name]
            print(f"  {name}")
            print(f"    {meta.description}")
            if meta.hints:
                print(f"    hints: {', '.join(meta.hints)}")
        sys.exit(0)

    # Parse --grant into Permission set; default-deny
    valid_perm_values = {p.value for p in Permission}
    for g in args.grant:
        if g not in valid_perm_values:
            print(
                f"Unknown permission: {g}. Valid: {', '.join(sorted(valid_perm_values))}",
                file=sys.stderr,
            )
            sys.exit(1)
    allowed = frozenset(Permission(g) for g in args.grant)
    gate = Gate(allowed)

    # Mode precedence: save/resume → conversational; -c → conversational; else stateless
    _conversational = args.save_session or args.resume_session or args.conversational
    _repl_mode = args.interactive or _conversational

    if args.json and args.stream:
        parser.error("--json and --stream are mutually exclusive")
    if args.json and _repl_mode:
        parser.error(
            "--json is single-turn only; incompatible with --interactive and --conversational"
        )

    # v0.9: load prompt from artifact when --artifact-in
    if args.artifact_in is not None:
        _load_artifact_and_set_prompt(args)

    # Single-turn mode requires a prompt; REPL modes do not
    if not _repl_mode and args.prompt is None:
        if not sys.stdin.isatty():
            piped = sys.stdin.read().strip()
            if not piped:
                parser.error(
                    "stdin was empty; provide a prompt or pipe non-empty input"
                )
            args.prompt = piped
        else:
            parser.error(
                "prompt is required (or use --list-models, --list-tools, --interactive, or --conversational)"
            )

    if args.backend == "deepseek":
        model_id = args.model or "deepseek-chat"
    else:
        model_id = args.model
        if model_id is None:
            model_id = default_model()
            if not model_id:
                print(
                    "No Ollama models found. Install one with e.g. ollama pull llama3.2"
                )
                sys.exit(1)
    if not _repl_mode and not args.json and args.artifact_out != "-":
        print(f"Using model: {model_id}\n")

    if args.backend == "deepseek":
        try:
            reasoner = DeepSeekReasoner(model_id=model_id)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
    else:
        reasoner = AyaReasoner(model_id=model_id)
    engine = ORE(reasoner, system_prompt=args.system)

    if args.interactive:
        print(f"ORE {__version__} interactive (model: {model_id})")
        print("Each turn is stateless. Type quit or exit to leave.\n")
        while True:
            try:
                line = input("You: ").strip()
            except EOFError:
                print()
                break
            if line.lower() in _REPL_EXIT_COMMANDS:
                break
            skill_context = _get_skill_context(args.skill, skill_registry)
            if args.route:
                tool_results, route_skill_ctx, _ = _route_and_dispatch(
                    line,
                    gate,
                    args.verbose,
                    skill_registry,
                    confidence_threshold=args.route_threshold,
                )
                # Merge: explicit --skill + route-selected skill
                if route_skill_ctx:
                    skill_context = (skill_context or []) + route_skill_ctx
            else:
                tool_results = _get_tool_results(args.tool, args.tool_arg or None, gate)
            print("--- ORE: Reasoning ---")
            if args.stream:
                _stream_turn(
                    engine,
                    line,
                    None,
                    args.verbose,
                    tool_results=tool_results,
                    skill_context=skill_context,
                )
            else:
                response = engine.execute(
                    line, tool_results=tool_results, skill_context=skill_context
                )
                _print_response(response, verbose=args.verbose)
            print()

    elif _conversational:
        store = FileSessionStore()
        if args.resume_session:
            try:
                session = store.load(args.resume_session)
            except FileNotFoundError as e:
                print(f"Error: {e}")
                sys.exit(1)
        else:
            session = Session()
        save_name = args.save_session
        print(
            f"ORE {__version__} conversational (model: {model_id} | session: {session.id})"
        )
        if args.resume_session:
            print(f"  Resumed: {args.resume_session}")
        if save_name:
            print(f"  Saving to: {save_name}")
        print("Prior turns are visible to the reasoner. Type quit or exit to leave.\n")
        try:
            while True:
                try:
                    line = input("You: ").strip()
                except EOFError:
                    print()
                    break
                if line.lower() in _REPL_EXIT_COMMANDS:
                    break
                skill_context = _get_skill_context(args.skill, skill_registry)
                if args.route:
                    tool_results, route_skill_ctx, _ = _route_and_dispatch(
                        line,
                        gate,
                        args.verbose,
                        skill_registry,
                        confidence_threshold=args.route_threshold,
                    )
                    if route_skill_ctx:
                        skill_context = (skill_context or []) + route_skill_ctx
                else:
                    tool_results = _get_tool_results(
                        args.tool, args.tool_arg or None, gate
                    )
                print("--- ORE: Reasoning ---")
                if args.stream:
                    _stream_turn(
                        engine,
                        line,
                        session,
                        args.verbose,
                        tool_results=tool_results,
                        skill_context=skill_context,
                    )
                else:
                    response = engine.execute(
                        line,
                        session=session,
                        tool_results=tool_results,
                        skill_context=skill_context,
                    )
                    _print_response(response, verbose=args.verbose)
                if save_name:
                    store.save(session, save_name)
                print()
        finally:
            if save_name:
                store.save(session, save_name)

    else:
        routing_decision: Optional[RoutingDecision] = None
        skill_context = _get_skill_context(args.skill, skill_registry)
        if args.route:
            tool_results, route_skill_ctx, routing_decision = _route_and_dispatch(
                args.prompt,
                gate,
                args.verbose,
                skill_registry,
                confidence_threshold=args.route_threshold,
            )
            if route_skill_ctx:
                skill_context = (skill_context or []) + route_skill_ctx
        else:
            tool_results = _get_tool_results(args.tool, args.tool_arg or None, gate)
        if not args.json and args.artifact_out != "-":
            print(f"--- ORE {__version__}: Reasoning ---")
        if args.stream:
            _stream_turn(
                engine,
                args.prompt,
                None,
                args.verbose,
                tool_results=tool_results,
                skill_context=skill_context,
            )
        else:
            response = engine.execute(
                args.prompt,
                tool_results=tool_results,
                skill_context=skill_context,
            )
            # v0.9: when artifact goes to stdout, skip human/json response (stdout is artifact only)
            if args.artifact_out == "-":
                pass  # Will print artifact below
            elif args.json:
                _print_json_response(response, routing=routing_decision)
            else:
                _print_response(response, verbose=args.verbose)
            # v0.9: emit artifact if requested
            if args.artifact_out is not None:
                tool_names = [r.tool_name for r in (tool_results or [])]
                skill_names: List[str] = []
                if args.skill:
                    skill_names.append(args.skill)
                if (
                    routing_decision
                    and routing_decision.target_type == "skill"
                    and routing_decision.target
                ):
                    skill_names.append(routing_decision.target)
                skill_names = list(dict.fromkeys(skill_names))
                artifact = ExecutionArtifact.from_response(
                    response=response,
                    prompt=args.prompt,
                    model_id=model_id,
                    routing=routing_decision,
                    tools=tool_names if tool_names else None,
                    skills=skill_names if skill_names else None,
                )
                artifact_json = json.dumps(artifact.to_dict())
                if args.artifact_out == "-":
                    print(artifact_json)
                else:
                    try:
                        out_path = _validate_output_path(args.artifact_out)
                        out_path.write_text(artifact_json, encoding="utf-8")
                    except ValueError as e:
                        print(str(e), file=sys.stderr)
                        sys.exit(1)
