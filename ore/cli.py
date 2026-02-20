"""
CLI layer: argument parsing and printing the reasoning output.
v0.2 adds an interactive loop (REPL); each turn remains stateless.
v0.3 adds --conversational (-c): a REPL where the session accumulates.
v0.4 adds --save-session / --resume-session for opt-in file persistence.
v0.5 adds --json / -j for structured output and stdin ingestion for piped prompts.
v0.6 adds --tool / --tool-arg / --list-tools / --grant for tool & gate framework.
v0.7 adds --route for intent-based tool selection (routing info to stderr).
"""

import argparse
import json
import sys
from typing import List, Optional, Tuple

from .core import ORE
from .gate import Gate, GateError, Permission
from .models import default_model, fetch_models
from .reasoner import AyaReasoner
from .router import RuleRouter, build_targets_from_registry
from .store import FileSessionStore
from .tools import TOOL_REGISTRY
from .types import Response, RoutingDecision, Session, ToolResult

# Commands that exit any REPL mode (case-insensitive)
_REPL_EXIT_COMMANDS = frozenset({"quit", "exit"})


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


def _route_and_get_tool_results(
    prompt: str,
    gate: Gate,
    verbose: bool,
    confidence_threshold: float = 0.5,
) -> Tuple[Optional[List[ToolResult]], RoutingDecision]:
    """
    Run router on prompt; if a tool is selected, run it through gate and return
    [result] + decision. Otherwise return (None, decision). All routing info
    is printed to stderr so stdout stays clean for JSON.
    """
    targets = build_targets_from_registry(TOOL_REGISTRY)
    decision = RuleRouter(confidence_threshold=confidence_threshold).route(
        prompt, targets
    )
    # Always print routing to stderr (visible, non-silent)
    if decision.target is None:
        print(
            f"[Route]: No match, using reasoner only. {decision.reasoning}",
            file=sys.stderr,
        )
        return None, decision
    print(
        f"[Route]: {decision.target} (confidence: {decision.confidence:.2f}) — {decision.reasoning}",
        file=sys.stderr,
    )
    if verbose:
        print(
            f"  routing_id={decision.id} target_type={decision.target_type} args={decision.args}",
            file=sys.stderr,
        )
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
        return [result], decision
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
) -> Response:
    """Drive the streaming generator, print chunks as they arrive, return final Response."""
    gen = engine.execute_stream(prompt, session=session, tool_results=tool_results)
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


def run() -> None:
    parser = argparse.ArgumentParser(description="ORE v0.7 CLI")
    parser.add_argument(
        "prompt",
        type=str,
        nargs="?",
        default=None,
        help="User input for Aya (omit when using --list-models, --interactive, or --conversational)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        metavar="NAME",
        help="Ollama model name (default: first available, e.g. llama3.2)",
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
        help="Route prompt to a tool by intent (v0.7); mutually exclusive with --tool",
    )
    parser.add_argument(
        "--route-threshold",
        type=float,
        default=0.5,
        metavar="FLOAT",
        help="Confidence threshold for --route (0.0–1.0, default 0.5); lower = more permissive",
    )
    args = parser.parse_args()

    if args.route and args.tool:
        parser.error("--route and --tool are mutually exclusive")
    if args.interactive and args.conversational:
        parser.error("--interactive and --conversational are mutually exclusive")
    if args.interactive and (args.save_session or args.resume_session):
        parser.error(
            "--interactive cannot be used with --save-session or --resume-session"
        )

    if args.list_models:
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

    model_id = args.model
    if model_id is None:
        model_id = default_model()
        if not model_id:
            print("No Ollama models found. Install one with e.g. ollama pull llama3.2")
            sys.exit(1)
        if not _repl_mode and not args.json:
            print(f"Using model: {model_id}\n")

    engine = ORE(AyaReasoner(model_id=model_id))

    if args.interactive:
        print(f"ORE v0.7 interactive (model: {model_id})")
        print("Each turn is stateless. Type quit or exit to leave.\n")
        while True:
            try:
                line = input("You: ").strip()
            except EOFError:
                print()
                break
            if line.lower() in _REPL_EXIT_COMMANDS:
                break
            if args.route:
                tool_results, _ = _route_and_get_tool_results(
                    line, gate, args.verbose, confidence_threshold=args.route_threshold
                )
            else:
                tool_results = _get_tool_results(args.tool, args.tool_arg or None, gate)
            print("--- ORE: Reasoning ---")
            if args.stream:
                _stream_turn(
                    engine, line, None, args.verbose, tool_results=tool_results
                )
            else:
                response = engine.execute(line, tool_results=tool_results)
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
        print(f"ORE v0.7 conversational (model: {model_id} | session: {session.id})")
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
                if args.route:
                    tool_results, _ = _route_and_get_tool_results(
                        line,
                        gate,
                        args.verbose,
                        confidence_threshold=args.route_threshold,
                    )
                else:
                    tool_results = _get_tool_results(
                        args.tool, args.tool_arg or None, gate
                    )
                print("--- ORE: Reasoning ---")
                if args.stream:
                    _stream_turn(
                        engine, line, session, args.verbose, tool_results=tool_results
                    )
                else:
                    response = engine.execute(
                        line, session=session, tool_results=tool_results
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
        if args.route:
            tool_results, routing_decision = _route_and_get_tool_results(
                args.prompt,
                gate,
                args.verbose,
                confidence_threshold=args.route_threshold,
            )
        else:
            tool_results = _get_tool_results(args.tool, args.tool_arg or None, gate)
        if not args.json:
            print("--- ORE v0.7: Reasoning ---")
        if args.stream:
            _stream_turn(
                engine, args.prompt, None, args.verbose, tool_results=tool_results
            )
        else:
            response = engine.execute(args.prompt, tool_results=tool_results)
            if args.json:
                _print_json_response(response, routing=routing_decision)
            else:
                _print_response(response, verbose=args.verbose)
