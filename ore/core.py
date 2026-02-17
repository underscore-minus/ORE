"""
Orchestrator: builds the minimal context loop and delegates to the Reasoner.
Aya persona is injected here, not in the Reasoner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator, Optional

from .reasoner import Reasoner
from .types import Message, Response, Session

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

    def execute(self, user_prompt: str, session: Optional[Session] = None) -> Response:
        """
        Run one turn of the irreducible loop.

        Without a session (default, v0.1/v0.2 behaviour):
            message list = [system, user]

        With a session (v0.3 cognitive continuity):
            message list = [system] + session.messages + [user]
            After the reasoner responds, the user and assistant messages are
            appended to the session so the next turn sees the full history.

        The session is an explicit argument — there is no hidden state inside ORE.
        """
        user_msg = Message(role="user", content=user_prompt)

        messages = [Message(role="system", content=self.system_prompt)]
        if session is not None:
            messages += session.messages
        messages.append(user_msg)

        response = self.reasoner.reason(messages)

        if session is not None:
            # Append user turn, then assistant turn — order is canonical.
            session.messages.append(user_msg)
            session.messages.append(Message(role="assistant", content=response.content))

        return response

    def execute_stream(
        self, user_prompt: str, session: Optional[Session] = None
    ) -> Generator[str, None, Response]:
        """
        Streaming variant: yields str chunks. Session is updated after exhaustion.
        The final StopIteration carries the Response.
        """
        user_msg = Message(role="user", content=user_prompt)

        messages = [Message(role="system", content=self.system_prompt)]
        if session is not None:
            messages += session.messages
        messages.append(user_msg)

        response = yield from self.reasoner.stream_reason(messages)

        if session is not None:
            session.messages.append(user_msg)
            session.messages.append(
                Message(role="assistant", content=response.content)
            )

        return response
