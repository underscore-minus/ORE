"""
CLI layer: argument parsing and printing the reasoning output.
v0.2 adds an interactive loop (REPL); each turn remains stateless.
v0.3 adds --conversational (-c): a REPL where the session accumulates.
v0.4 adds --save-session / --resume-session for opt-in file persistence.
v0.5 adds --json / -j for structured output and stdin ingestion for piped prompts.
v0.6 adds --tool / --tool-arg / --list-tools / --grant for tool & gate framework.
"""

import argparse
import json
import sys
from typing import List, Optional

from .core import ORE
from .gate import Gate, GateError, Permission
from .models import default_model, fetch_models
from .reasoner import AyaReasoner
from .store import FileSessionStore
from .tools import TOOL_REGISTRY
from .types import Response, Session, ToolResult

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


def _print_json_response(response: Response) -> None:
    """Serialize Response to JSON and print to stdout."""
    print(
        json.dumps(
            {
                "id": response.id,
                "model_id": response.model_id,
                "content": response.content,
                "timestamp": response.timestamp,
                "metadata": response.metadata,
            }
        )
    )


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
    parser = argparse.ArgumentParser(description="ORE v0.6 CLI")
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
    args = parser.parse_args()

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
            perms = ", ".join(p.value for p in sorted(tool.required_permissions, key=lambda x: x.value))
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
        print(f"ORE v0.6 interactive (model: {model_id})")
        print("Each turn is stateless. Type quit or exit to leave.\n")
        while True:
            try:
                line = input("You: ").strip()
            except EOFError:
                print()
                break
            if line.lower() in _REPL_EXIT_COMMANDS:
                break
            tool_results = _get_tool_results(args.tool, args.tool_arg or None, gate)
            print("--- ORE: Reasoning ---")
            if args.stream:
                _stream_turn(engine, line, None, args.verbose, tool_results=tool_results)
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
        print(f"ORE v0.6 conversational (model: {model_id} | session: {session.id})")
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
                tool_results = _get_tool_results(args.tool, args.tool_arg or None, gate)
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
        tool_results = _get_tool_results(args.tool, args.tool_arg or None, gate)
        if not args.json:
            print("--- ORE v0.6: Reasoning ---")
        if args.stream:
            _stream_turn(
                engine, args.prompt, None, args.verbose, tool_results=tool_results
            )
        else:
            response = engine.execute(args.prompt, tool_results=tool_results)
            if args.json:
                _print_json_response(response)
            else:
                _print_response(response, verbose=args.verbose)
