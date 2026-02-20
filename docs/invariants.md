# ORE Mechanical Invariants (v0.4.x)

This document lists the **mechanical invariants** of ORE — concrete, testable guarantees that must hold. For philosophical foundations and extension rules, see [foundation.md](foundation.md). For architectural design, see [architecture.md](architecture.md).

---

## Purpose

Single source of truth for "what must hold" at runtime. CI runs tests that enforce these invariants; any change that breaks the loop or state model causes a test failure.

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

## CLI Flag Conflict Invariants

**`--interactive` is mutually exclusive with conversational/session flags.**

- `--interactive` and `--conversational` may not be used together.
- `--interactive` and `--save-session` may not be used together.
- `--interactive` and `--resume-session` may not be used together.

**How we test:** `tests/test_cli.py` — `TestModeValidation` asserts that each invalid combination causes `run()` to exit with an error (`parser.error`).

---

## Tests Marked as Invariant

Tests that encode these guarantees are marked with `@pytest.mark.invariant` and are part of the main pytest run. Breaking any invariant will cause CI to fail. Run invariant tests specifically with: `pytest -m invariant`. See `tests/test_core.py` and `tests/test_cli.py` for the full suite.
