"""
Orchestrator: builds the minimal context loop and delegates to the Reasoner.
System prompt is provided by the consumer; the engine is persona-agnostic.
"""

from __future__ import annotations

from typing import Generator, List, Optional

from .reasoner import Reasoner
from .types import Message, Response, Session, ToolResult


class ORE:
    """Engine that interprets the user task and runs the irreducible loop (system + user -> reasoner)."""

    def __init__(self, reasoner: Reasoner, system_prompt: str = "") -> None:
        self.reasoner = reasoner
        self.system_prompt = system_prompt

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
