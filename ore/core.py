"""
Orchestrator: builds the minimal context loop and delegates to the Reasoner.
Aya persona is injected here, not in the Reasoner.
"""

from pathlib import Path

from .reasoner import Reasoner
from .types import Message, Response

PROMPTS_DIR = Path(__file__).with_name("prompts")
AYA_PROMPT_PATH = PROMPTS_DIR / "aya.txt"


def load_aya_system_prompt() -> str:
    """Load Aya's system persona from the external prompt file."""
    try:
        return AYA_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # High-level: fail fast if contract file is missing.
        msg = f"Aya system prompt not found at {AYA_PROMPT_PATH}"
        raise RuntimeError(msg) from exc


class ORE:
    """Engine that interprets the user task and runs the irreducible loop (system + user -> reasoner)."""

    def __init__(self, reasoner: Reasoner) -> None:
        # Keep Aya's persona as data, loaded from a versioned prompt file.
        self.reasoner = reasoner
        self.system_prompt = load_aya_system_prompt()

    def execute(self, user_prompt: str) -> Response:
        # Single turn: system identity + user input only (stateless)
        messages = [
            Message(role="system", content=self.system_prompt),
            Message(role="user", content=user_prompt),
        ]
        return self.reasoner.reason(messages)
