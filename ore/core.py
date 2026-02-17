"""
Orchestrator: builds the minimal context loop and delegates to the Reasoner.
Aya persona is injected here, not in the Reasoner.
"""

from .reasoner import Reasoner
from .types import Message, Response


class ORE:
    """Engine that interprets the user task and runs the irreducible loop (system + user -> reasoner)."""

    def __init__(self, reasoner: Reasoner) -> None:
        self.reasoner = reasoner
        self.system_prompt = (
            "You are Aya, the central AI assistant of the ORE. "
            "You are intuitive, transparent, and focused on structured reasoning."
        )

    def execute(self, user_prompt: str) -> Response:
        # Single turn: system identity + user input only (stateless)
        messages = [
            Message(role="system", content=self.system_prompt),
            Message(role="user", content=user_prompt),
        ]
        return self.reasoner.reason(messages)
