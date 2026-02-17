ORE — Foundation Document (v0.3)
Purpose

ORE (Orchestrated Reasoning Engine) is a minimal, local-first reasoning engine built around an irreducible interaction loop:

Input → Reasoner → Output

This document defines the non-negotiable foundations of ORE.
Any agent, human or AI, working on ORE must preserve these invariants unless a version explicitly breaks them.

Core Invariants (Must Hold)

Irreducible loop

A user provides input.

A reasoner produces a response.

The response is returned to the user.

No hidden steps, no implicit side effects.

Explicit state (v0.3+)

Each execution is a single turn of the irreducible loop.

State (memory, session history) may exist, but must be passed explicitly.

No implicit accumulation. If a session is present, it is a named, visible argument — not a hidden field on the engine.

Tools and disk persistence remain out of scope until a future version.

Separation of concerns

CLI/UI logic does not reason.

Orchestration does not depend on a specific model backend.

Reasoners do not define personas, UX, or session logic.

Data-first contracts

All reasoning input/output flows through explicit data structures.

Message, Response, and Session are the canonical contracts.

No implicit schemas.

Local-first execution

v0.1 assumes local execution via Ollama.

Remote backends are an extension, not a replacement.

What Exists in v0.3
Runtime Model

Three execution modes, all sharing the same irreducible loop:

Single-turn (default): system + user → reasoner → response. Stateless.

Interactive REPL (--interactive / -i): many single turns in one process. Each turn stateless. Unchanged from v0.2.

Conversational REPL (--conversational / -c): many turns in one process with a shared Session. Each turn: system + session history + user → reasoner → response. The session grows.

Session

Introduced in v0.3. An ordered list of user and assistant messages accumulated across turns.

The system message is never stored in the Session; it is injected by the orchestrator on every turn.

The Session is passed explicitly to ORE.execute(); it is not stored inside ORE.

Without a session, ORE.execute() behaves exactly as in v0.2.

Persona

The system persona ("Aya") is injected by the orchestrator.

Persona is data, not logic.

Reasoners must be persona-agnostic.

Architecture Roles

Entry

main.py
Loads environment and delegates to CLI.

CLI

ore/cli.py
Handles arguments, model selection, and stdout/stderr.
Does not reason. Owns session creation for --conversational.

Orchestrator

ore/core.py
Constructs the message list and invokes a reasoner.
Enforces the core loop.
Accepts an optional Session to prepend prior turns.

Reasoner

ore/reasoner.py
Abstract interface + Ollama-backed implementation.
Given messages → returns a response.

Model Utilities

ore/models.py
Discovery and default-selection logic for Ollama models.

Data Contracts

ore/types.py
Defines Message, Response, and Session.

Reasoner Contract (Critical)

Any reasoner must:

Accept a list of Message objects.

Return a Response.

Be free of CLI, persona, or session logic.

Treat messages as ordered, explicit inputs.

If a backend cannot satisfy this, it does not belong behind Reasoner.

What ORE Is Not (Yet)

Not an agent framework

Not a persistent memory system (in-memory only in v0.3)

Not a tool runner

Not a chatbot shell

Not a workflow engine

Those may be built on top of ORE, but do not belong in the core.

Extension Rules

Extensions must follow these rules:

No silent behavior changes

New capabilities require explicit version bumps.

State must be visible

Memory, tools, or context windows must be explicit in code and docs.

Core remains boring

Complexity lives at the edges, not in the loop.

Backward clarity beats forward cleverness

Prefer obvious code over abstract frameworks.

Versioning Philosophy

Versions describe capability, not polish.

v0.1 is intentionally limited.

New versions add one conceptual dimension at a time (e.g. time, memory, tools).

v0.1 — The loop exists (single-turn, stateless).
v0.2 — Temporal continuity (interactive REPL, still stateless per turn).
v0.3 — Cognitive continuity (session history, explicit state).

Guiding Question

When modifying ORE, always ask:

"Does this preserve the irreducible loop, or am I hiding complexity inside it?"

If complexity is hidden, the change is wrong.

End of foundation.
