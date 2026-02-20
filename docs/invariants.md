# ORE Mechanical Invariants (v0.9)

This document lists the **mechanical invariants** of ORE — concrete, testable guarantees that must hold. For philosophical foundations and extension rules, see [foundation.md](foundation.md). For architectural design, see [architecture.md](architecture.md).

---

## Purpose

Single source of truth for "what must hold" at runtime. CI runs tests that enforce these invariants; any change that breaks the loop or state model causes a test failure.

**Terminology:** We use `ORE.execute()` and `ORE.execute_stream()` as the canonical API names (the orchestrator instance may be named `engine` elsewhere).

---

## Loop Invariant

**One reasoner call per turn.**

For each `ORE.execute()` or `ORE.execute_stream()` invocation:

- The reasoner's `reason()` or `stream_reason()` is called **exactly once**.
- No double-calls, no skipped calls.

**How we test:** `tests/test_core.py` — `test_reasoner_called_exactly_once_per_execute` and `test_reasoner_called_exactly_once_per_execute_stream` use a `FakeReasoner` with call counters and assert the count increments by one per turn.

---

## Session Immutability Invariants

**Session is append-only.**

- No messages are removed or reordered from `session.messages`.
- Only user and assistant messages are appended after each turn; the system message is never stored in the session.
- Existing messages retain their identity (same `id`) and order.

**How we test:** `tests/test_core.py` — `test_session_append_only_no_reorder_or_delete` records message IDs before a turn and asserts they are unchanged after; `test_system_prompt_not_in_session` asserts no system role in the session; `test_session_grows_after_execute` asserts the expected growth per turn.

---

## Explicit State Invariant

**Session is passed as an argument; ORE does not store it.**

- `ORE.execute()` and `ORE.execute_stream()` accept an optional `session` parameter.
- Without a session, behaviour is identical to v0.2 (stateless).
- ORE holds no hidden session or message history internally.

**How we test:** `tests/test_core.py` — `test_no_session_no_side_effects` and `test_with_session_includes_history` assert that execution with and without a session behaves correctly; session is never retained across stateless calls.

---

## Tool & Gate Invariants (v0.6)

**Tool results are turn-scoped.**

- Tool result messages are injected into the message list for the current turn only. They are **never** stored in the session and **never** persisted to disk.
- Only user and assistant messages are appended to the session after each turn.

**Gate is default-deny.**

- With no `--grant` flags, only tools that require no permissions (e.g. `echo`) may run. Permissioned tools (e.g. `read-file`) raise `GateError` and the CLI exits with code 1.

**Denied tools never execute.**

- When the gate denies a tool, `tool.run()` is never called. Permission check happens before execution.

**How we test:** `tests/test_core.py` — `test_tool_results_not_stored_in_session`, `test_reasoner_still_called_once_with_tools`; `tests/test_gate.py` — `test_denied_tool_never_executes` (invariant); `tests/test_cli.py` — `test_tool_gate_denied_exits_cleanly`.

---

## Routing (v0.7)

- **One reasoner call per turn** — Routing does not introduce a second LLM/reasoner call. Routing is rule-based (non-LLM).
- **Routing decision visible** — Chosen route (tool, skill, or fallback) is printed to stderr; with `--json`, the `routing` key is included in stdout payload.
- **Session and loop unchanged** — Session remains append-only; only user and assistant messages are appended. Existing invariant tests continue to pass.
- **Router does not mutate targets** — `Router.route(prompt, targets)` must not mutate the `targets` list or its items.

**How we test:** `tests/test_router.py` — `test_route_does_not_mutate_targets_list` and `test_route_does_not_mutate_skill_targets` (invariants). Routing behaviour: `tests/test_router.py` (RuleRouter, build_targets); `tests/test_cli.py` — `TestRouteCli`, `test_route_and_tool_rejected` (invariant).

---

## Skill Invariants (v0.8)

- **Skill context is turn-scoped** — Skill instruction messages are injected for the current turn only. They are **never** stored in the session and **never** persisted to disk.
- **Skill messages use `role="system"`** — Injected skill messages extend the system prompt; they are not conversation messages.
- **One reasoner call per turn** — Skill activation does not introduce a second reasoner call. Preserved alongside tool and routing invariants.
- **Session append-only** — Session behaviour is unchanged; only user and assistant messages are appended.
- **`skill_context=None` is a no-op** — Without skill context, the message list is identical to v0.7 behaviour.
- **Resource path traversal blocked** — `load_skill_resource()` resolves the full path and rejects anything that escapes `skill_dir/resources/`.

**How we test:** `tests/test_core.py` — `test_skill_context_not_stored_in_session`, `test_skill_context_uses_system_role`, `test_reasoner_still_called_once_with_skills` (invariant), `test_no_skill_context_preserves_v07_behavior`. `tests/test_skills.py` — `test_path_traversal_blocked`, `test_path_traversal_blocked_sibling`.

---

## CLI Flag Conflict Invariants

**`--interactive` is mutually exclusive with conversational/session flags.**

- `--interactive` and `--conversational` may not be used together.
- `--interactive` and `--save-session` may not be used together.
- `--interactive` and `--resume-session` may not be used together.

**How we test:** `tests/test_cli.py` — `TestModeValidation` asserts that each invalid combination causes `run()` to exit with an error (`parser.error`).

---

## Artifact Invariants (v0.9)

**Artifact is single-turn only.**

- `--artifact-out` and `--artifact-in` are incompatible with REPL modes (interactive, conversational, save/resume).
- `--artifact-in` is mutually exclusive with prompt, `--tool`, `--route`, `--skill`.
- `--artifact-out` and `--stream` are mutually exclusive.
- `--artifact-out -` and `--json` are mutually exclusive (both write to stdout).

**One reasoner call per turn** — Artifact emit/ingest does not add a second reasoner call. Artifact is materialized after the response; ingestion runs a single turn with the artifact's input.prompt.

**Artifact schema is versioned** — `artifact_version` (e.g. `ore.exec.v1`) required; unsupported versions raise `ValueError` on parse.

**How we test:** `tests/test_cli.py` — `TestArtifactCli` (emission, ingestion, invalid artifact, flag conflicts); `tests/test_types.py` — `TestExecutionArtifact` (serialization, schema validation).

---

## Non-invariants (explicitly not guaranteed)

The following are **not** invariants; we do not guarantee them:

- **Determinism** — No guarantee of identical output across different models or runs.
- **Token count or cost** — No guarantee of token usage, latency, or cost bounds.
- **Semantic consistency** — No guarantee that equivalent prompts yield semantically similar responses across runs.

This prevents future contributors from treating these as upgradable invariants.

---

## Tests Marked as Invariant

Tests that encode these guarantees are marked with `@pytest.mark.invariant` and are part of the main pytest run. Breaking any invariant will cause CI to fail. Run invariant tests specifically with: `pytest -m invariant`. See `tests/test_core.py`, `tests/test_cli.py`, `tests/test_gate.py`, `tests/test_router.py`, and artifact tests in `tests/test_cli.py` for the full suite.
