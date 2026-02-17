ORE — Foundation Document (v0.1)
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

Stateless by default (v0.1)

Each execution is a single, isolated turn.

No memory, no tools, no persistence.

State may be added only in later versions and must be explicit.

Separation of concerns

CLI/UI logic does not reason.

Orchestration does not depend on a specific model backend.

Reasoners do not define personas or UX.

Data-first contracts

All reasoning input/output flows through explicit data structures.

Message and Response are the canonical contracts.

No implicit schemas.

Local-first execution

v0.1 assumes local execution via Ollama.

Remote backends are an extension, not a replacement.

What Exists in v0.1
Runtime Model

Single-turn execution

One system message + one user message

One response

There is no conversation history.

Persona

The system persona (“Aya”) is injected by the orchestrator.

Persona is data, not logic.

Reasoners must be persona-agnostic.

Architecture Roles

Entry

main.py
Loads environment and delegates to CLI.

CLI

ore/cli.py
Handles arguments, model selection, and stdout/stderr.
Does not reason.

Orchestrator

ore/core.py
Constructs the message list and invokes a reasoner.
Enforces the core loop.

Reasoner

ore/reasoner.py
Abstract interface + Ollama-backed implementation.
Given messages → returns a response.

Model Utilities

ore/models.py
Discovery and default-selection logic for Ollama models.

Data Contracts

ore/types.py
Defines Message and Response.

Reasoner Contract (Critical)

Any reasoner must:

Accept a list of Message objects.

Return a Response.

Be free of CLI, persona, or session logic.

Treat messages as ordered, explicit inputs.

If a backend cannot satisfy this, it does not belong behind Reasoner.

What ORE Is Not (Yet)

Not an agent framework

Not a memory system

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

Guiding Question

When modifying ORE, always ask:

“Does this preserve the irreducible loop, or am I hiding complexity inside it?”

If complexity is hidden, the change is wrong.

End of foundation.