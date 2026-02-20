ORE — Foundation Document (v0.7)

Purpose

ORE (Orchestrated Reasoning Engine) is a minimal, local-first reasoning engine built around an irreducible interaction loop:

Input → Reasoner → Output

This document defines the non-negotiable foundations of ORE.
Any agent, human or AI, working on ORE must preserve these invariants unless a version explicitly breaks them.

Mechanical invariants and how they are tested are documented in [docs/invariants.md](invariants.md).

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

Session persistence (v0.4) is opt-in via `--save-session` / `--resume-session`; without these flags, behaviour is unchanged.

Tools (v0.6) are in scope only when explicitly invoked (e.g. `--tool NAME`) and gated by permissions (`--grant`). Tool results are passed into the engine as a visible argument (`tool_results`) and are turn-scoped — never stored in the session.

Separation of concerns

CLI/UI logic does not reason.

Orchestration does not depend on a specific model backend.

Reasoners do not define personas, UX, or session logic.

Data-first contracts

All reasoning input/output flows through explicit data structures.

Message, Response, Session, and ToolResult (v0.6) are the canonical contracts.

No implicit schemas.

Local-first execution

v0.1 assumes local execution via Ollama.

Remote backends are an extension, not a replacement.

What Exists in v0.6

Runtime Model

Four execution modes, all sharing the same irreducible loop:

Single-turn (default): system + user → reasoner → response. Stateless.

Interactive REPL (--interactive / -i): many single turns in one process. Each turn stateless. Unchanged from v0.2.

Conversational REPL (--conversational / -c): many turns in one process with a shared Session. Each turn: system + session history + user → reasoner → response. The session grows.

Persistent sessions (--save-session NAME / --resume-session NAME): opt-in file-based persistence in ~/.ore/sessions/. Both imply conversational mode. Sessions saved eagerly after each turn.

Tools (v0.6): optional pre-reasoning step. One or more tools can be run via CLI (--tool NAME, --tool-arg KEY=VALUE). A gate enforces permissions (--grant PERM; default-deny). Tool results are injected into the message list for that turn only; they are never stored in the session. One reasoner call per turn is preserved.

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
Does not reason. Owns session creation for --conversational and persistence for --save-session / --resume-session. Owns stdin ingestion and JSON output via --json. Resolves --tool, parses --tool-arg and --grant, runs tools through the gate, and passes tool_results to the engine.

Orchestrator

ore/core.py
Constructs the message list and invokes a reasoner.
Enforces the core loop.
Accepts an optional Session to prepend prior turns and optional tool_results (v0.6) to inject after the system message, before session history.

Reasoner

ore/reasoner.py
Abstract interface + Ollama-backed implementation.
Given messages → returns a response.

Model Utilities

ore/models.py
Discovery and default-selection logic for Ollama models.

Data Contracts

ore/types.py
Defines Message, Response, Session, and ToolResult (v0.6).

ore/store.py
SessionStore abstraction and FileSessionStore for opt-in persistence.

ore/tools.py (v0.6)
Tool interface and built-in tools (e.g. EchoTool, ReadFileTool). TOOL_REGISTRY for CLI dispatch.

ore/gate.py (v0.6)
Permission gate: default-deny; checks tool required_permissions before execution.

Reasoner Contract (Critical)

Any reasoner must:

Accept a list of Message objects.

Return a Response.

Be free of CLI, persona, or session logic.

Treat messages as ordered, explicit inputs.

If a backend cannot satisfy this, it does not belong behind Reasoner.

What ORE Is Not (Yet)

Not an agent framework

Not a persistent memory system (opt-in session persistence in v0.4; default remains in-memory)

Not a full tool runtime (v0.6 adds a minimal tool & gate layer; routing and skill-based tool selection come later)

Not a chatbot shell (ORE is an orchestration primitive with a single loop and explicit state)

Not a workflow engine

Not a script execution runtime (v0.8 skills inject file contents as context; executable resources are deferred — not forbidden, just out of scope for the current version)

Those may be built on top of ORE, or added in later versions; the core stays minimal and explicit.

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
v0.4 — Persistent sessions (opt-in, file-based; CLI flags only; core unchanged).
v0.5 — Composable output (structured JSON, stdin ingestion; CLI only; core unchanged).
v0.6 — Tool & gate framework (explicit tools, default-deny permissions; tool results turn-scoped, not stored in session).
v0.7 — Routing / intent detection (opt-in `--route`; rule-based selection of tool from prompt; no extra LLM call; routing decision visible on stderr and in `--json`).

Guiding Question

When modifying ORE, always ask:

"Does this preserve the irreducible loop, or am I hiding complexity inside it?"

If complexity is hidden, the change is wrong.

End of foundation.
