"""
CLI layer: argument parsing and printing the reasoning output.
v0.2 adds an interactive loop (REPL); each turn remains stateless.
v0.3 adds --conversational (-c): a REPL where the session accumulates.
"""

import argparse
import sys

from .core import ORE
from .models import default_model, fetch_models
from .reasoner import AyaReasoner
from .types import Response, Session

# Commands that exit any REPL mode (case-insensitive)
_REPL_EXIT_COMMANDS = frozenset({"quit", "exit"})


def _print_response(response: Response) -> None:
    """Print a single response to stdout (content + optional metadata)."""
    print(f"\n[AYA]: {response.content}")
    print(f"\n[Metadata]: ID {response.id} | Model {response.model_id}")
    if response.metadata:
        print(f"  Usage: {response.metadata}")


def run() -> None:
    parser = argparse.ArgumentParser(description="ORE v0.3 CLI")
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
            "prior turns are visible to the reasoner each turn (v0.3)"
        ),
    )
    args = parser.parse_args()

    if args.interactive and args.conversational:
        parser.error("--interactive and --conversational are mutually exclusive")

    if args.list_models:
        models = fetch_models()
        if not models:
            print("No Ollama models found. Install one with e.g. ollama pull llama3.2")
            sys.exit(1)
        print("Available Ollama models:")
        for name in sorted(models):
            print(f"  {name}")
        sys.exit(0)

    _repl_mode = args.interactive or args.conversational

    # Single-turn mode requires a prompt; REPL modes do not
    if not _repl_mode and args.prompt is None:
        parser.error(
            "prompt is required (or use --list-models, --interactive, or --conversational)"
        )

    model_id = args.model
    if model_id is None:
        model_id = default_model()
        if not model_id:
            print("No Ollama models found. Install one with e.g. ollama pull llama3.2")
            sys.exit(1)
        if not _repl_mode:
            print(f"Using model: {model_id}\n")

    engine = ORE(AyaReasoner(model_id=model_id))

    if args.interactive:
        print(f"ORE v0.2 interactive (model: {model_id})")
        print("Each turn is stateless. Type quit or exit to leave.\n")
        while True:
            try:
                line = input("You: ").strip()
            except EOFError:
                print()
                break
            if line.lower() in _REPL_EXIT_COMMANDS:
                break
            print("--- ORE: Reasoning ---")
            response = engine.execute(line)
            _print_response(response)
            print()

    elif args.conversational:
        session = Session()
        print(f"ORE v0.3 conversational (model: {model_id} | session: {session.id})")
        print("Prior turns are visible to the reasoner. Type quit or exit to leave.\n")
        while True:
            try:
                line = input("You: ").strip()
            except EOFError:
                print()
                break
            if line.lower() in _REPL_EXIT_COMMANDS:
                break
            print("--- ORE: Reasoning ---")
            response = engine.execute(line, session=session)
            _print_response(response)
            print()

    else:
        print("--- ORE v0.3: Reasoning ---")
        response = engine.execute(args.prompt)
        _print_response(response)
