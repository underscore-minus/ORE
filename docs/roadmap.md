# ORE Roadmap

Short notes on version intent. Not a feature backlog.

---

**v0.2** — Temporal continuity without cognitive continuity. The user can run many turns in one process (interactive REPL), but each turn is isolated; there is no conversation memory or shared context.

**v0.2.1** — Semantics lock: "interactive" is explicitly defined as non-conversational (no memory, no accumulation, no hidden context). Documentation only.

**v0.3** — Cognitive continuity. The first version where the reasoner sees prior turns. A `Session` holds the ordered message history; `ORE.execute()` accepts an optional session argument. Without a session, behaviour is identical to v0.2. A new `--conversational` / `-c` CLI flag activates the session-aware REPL. Session state lives in memory only; no persistence to disk.

**v0.3.1** — QoL: optional streaming (`--stream` / `-s`) and metadata toggle (`--verbose` / `-v`). CLI only. Core loop unchanged. `Response.metadata` schema locked.

**v0.4** — Persistent sessions. Opt-in file-based persistence via `--save-session <name>` and `--resume-session <name>`. Both imply conversational mode. Sessions stored as JSON in `~/.ore/sessions/`. Eager save after each turn. ORE core unchanged.

**v0.4.1** — Hardening & invariants. Mechanical invariants documented in `docs/invariants.md`; tests enforce reasoner-once-per-turn, session append-only, CLI flag conflicts. CI fails if loop or state model is broken.

**v0.4.2** — invariants.md: canonical terminology (`ORE.execute()`), non-invariants section (determinism, token count, semantic consistency).

**v0.5** — Composable output. Add --json / -j for single-turn structured output. Support stdin ingestion for piped prompts. REPL and conversational flows unchanged. Core loop, reasoner, types, store unchanged.

**v0.6** — Tool & Gate Framework. Tool interface (`ore/tools.py`) with EchoTool and ReadFileTool; gate (`ore/gate.py`) for default-deny permissions; `--tool`, `--tool-arg`, `--list-tools`, `--grant` CLI flags. Tool results injected pre-reasoning, turn-scoped (never stored in session). One reasoner call per turn preserved; denied tools never execute.

**v0.6.1** — Black formatting fix for CI; version bump to 0.6.1.

**v0.7** — Routing / Intent Detection (implemented). Opt-in `--route`; `--route-threshold FLOAT` to tune confidence (default 0.5); `RuleRouter` with keyword/phrase matching; `RoutingTarget` / `RoutingDecision`; routing info to stderr; `--json` includes `routing` key; fallback when no match or below threshold; invariant: router does not mutate targets. `TEST_ROUTING_TARGET` exported for deterministic test setups.

---

Next features (v0.8 → v1.0):

**v0.8** — Skill / Instruction Activation

Goal: Modularize agent behaviors via instructions or "skills."
Problem solved: v0.7 routing exists but skills are not yet first-class, reusable, or filesystem-based.
Changes:

Introduce filesystem-based skill structure: metadata, instructions, resources.

Skills loaded on-demand; context-aware activation without context bloat.

CLI / routing layer can trigger skills automatically.
Tests / Validation:

Skill activation triggers correct instructions and outputs.

Session immutability and reasoner call invariants enforced.

Integration tests: multiple skills used in one workflow.

---

**v0.9** — Multi-Agent / Parallel Orchestration

Goal: Scale orchestration across multiple reasoning engines.
Problem solved: v0.8 supports skills and routing, but single-agent only; parallel reasoning, aggregation, or QA pipelines are impossible.
Changes:

Introduce multi-agent message orchestration (fan-out/fan-in).

Merge outputs or vote on conflicting results.

Session and invariant rules extended to multi-agent workflows.
Tests / Validation:

Simulated parallel agents with overlapping skills.

Ensure session append-only + single reasoner call per agent per turn.

**v1.0** — Stable, CLI-First Orchestration Platform

Goal: Provide a production-ready, extensible CLI loop for complex orchestration.
Problem solved: All previous features exist but were incremental; v1.0 locks them into a coherent, predictable, testable system.
Changes:

Documented, enforceable invariants via CI.

Fully modular skills, tools, routing, multi-agent orchestration.

CLI-only interface still guarantees reproducibility and scripting.

Extensible for future GUI or API layers without touching the core loop.
Tests / Validation:

Full invariant + integration suite passes.

Multi-agent, skill, and tool orchestration tested end-to-end.

CLI reproducibility validated: JSON, REPL, piped input, persistence.
