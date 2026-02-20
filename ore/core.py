"""
Orchestrator: builds the minimal context loop and delegates to the Reasoner.
Aya persona is injected here, not in the Reasoner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator, List, Optional

from .reasoner import Reasoner
from .types import Message, Response, Session, ToolResult

PROMPTS_DIR = Path(__file__).with_name("prompts")
AYA_PROMPT_PATH = PROMPTS_DIR / "aya.txt"


def load_aya_system_prompt() -> str:
    """Load Aya's system persona from the external prompt file."""
    try:
        return AYA_PROMPT_PATH.read_text(encoding="utf-8")
    except (
        FileNotFoundError
    ) as exc:  # High-level: fail fast if contract file is missing.
        msg = f"Aya system prompt not found at {AYA_PROMPT_PATH}"
        raise RuntimeError(msg) from exc


class ORE:
    """Engine that interprets the user task and runs the irreducible loop (system + user -> reasoner)."""

    def __init__(self, reasoner: Reasoner) -> None:
        # Keep Aya's persona as data, loaded from a versioned prompt file.
        self.reasoner = reasoner
        self.system_prompt = load_aya_system_prompt()

    def execute(
        self,
        user_prompt: str,
        session: Optional[Session] = None,
        tool_results: Optional[List[ToolResult]] = None,
        skill_context: Optional[List[str]] = None,
    ) -> Response:
        """
        Run one turn of the irreducible loop.

        Message list (v0.8):
            [system] + [skill_messages...] + [tool_results...] + session.messages + [user]

        skill_context (v0.8): instruction strings injected as role="system"
        after the persona prompt, before tool results. Turn-scoped — never
        stored in session. See docs/skills.md for design decisions.

        tool_results (v0.6): injected as role="user" after skill context,
        before session. Turn-scoped.

        The session is an explicit argument — there is no hidden state.
        """
        user_msg = Message(role="user", content=user_prompt)

        messages = [Message(role="system", content=self.system_prompt)]
        if skill_context:
            for instruction in skill_context:
                messages.append(Message(role="system", content=instruction))
        if tool_results:
            for r in tool_results:
                messages.append(
                    Message(
                        role="user",
                        content=f"[Tool:{r.tool_name}]\n{r.output}",
                    )
                )
        if session is not None:
            messages += session.messages
        messages.append(user_msg)

        response = self.reasoner.reason(messages)

        if session is not None:
            session.messages.append(user_msg)
            session.messages.append(Message(role="assistant", content=response.content))

        return response

    def execute_stream(
        self,
        user_prompt: str,
        session: Optional[Session] = None,
        tool_results: Optional[List[ToolResult]] = None,
        skill_context: Optional[List[str]] = None,
    ) -> Generator[str, None, Response]:
        """
        Streaming variant: yields str chunks. Session is updated after exhaustion.
        Skill context and tool results injected same as execute().
        """
        user_msg = Message(role="user", content=user_prompt)

        messages = [Message(role="system", content=self.system_prompt)]
        if skill_context:
            for instruction in skill_context:
                messages.append(Message(role="system", content=instruction))
        if tool_results:
            for r in tool_results:
                messages.append(
                    Message(
                        role="user",
                        content=f"[Tool:{r.tool_name}]\n{r.output}",
                    )
                )
        if session is not None:
            messages += session.messages
        messages.append(user_msg)

        response = yield from self.reasoner.stream_reason(messages)

        if session is not None:
            session.messages.append(user_msg)
            session.messages.append(Message(role="assistant", content=response.content))

        return response
