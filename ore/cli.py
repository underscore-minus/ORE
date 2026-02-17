"""
CLI layer: argument parsing and printing the reasoning output.
"""

import argparse
import sys

from .core import ORE
from .models import default_model, fetch_models
from .reasoner import AyaReasoner


def run() -> None:
    parser = argparse.ArgumentParser(description="ORE v0.1.2 CLI")
    parser.add_argument(
        "prompt",
        type=str,
        nargs="?",
        default=None,
        help="User input for Aya (omit when using --list-models)",
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
    args = parser.parse_args()

    if args.list_models:
        models = fetch_models()
        if not models:
            print("No Ollama models found. Install one with e.g. ollama pull llama3.2")
            sys.exit(1)
        print("Available Ollama models:")
        for name in sorted(models):
            print(f"  {name}")
        sys.exit(0)

    if args.prompt is None:
        parser.error("prompt is required (or use --list-models)")

    model_id = args.model
    if model_id is None:
        model_id = default_model()
        if not model_id:
            print("No Ollama models found. Install one with e.g. ollama pull llama3.2")
            sys.exit(1)
        # Show which model we're using when auto-selected
        print(f"Using model: {model_id}\n")

    engine = ORE(AyaReasoner(model_id=model_id))

    print("--- ORE v0.1.2: Reasoning ---")
    response = engine.execute(args.prompt)

    print(f"\n[AYA]: {response.content}")
    print(f"\n[Metadata]: ID {response.id} | Model {response.model_id}")
    if response.metadata:
        print(f"  Usage: {response.metadata}")
