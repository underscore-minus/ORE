# ORE Roadmap

Short notes on version intent. Not a feature backlog.

---

**v0.2** — Temporal continuity without cognitive continuity. The user can run many turns in one process (interactive REPL), but each turn is isolated; there is no conversation memory or shared context.

**v0.2.1** — Semantics lock: "interactive" is explicitly defined as non-conversational (no memory, no accumulation, no hidden context). Documentation only.

**v0.3** — Cognitive continuity. The first version where the reasoner sees prior turns. A `Session` holds the ordered message history; `ORE.execute()` accepts an optional session argument. Without a session, behaviour is identical to v0.2. A new `--conversational` / `-c` CLI flag activates the session-aware REPL. Session state lives in memory only; no persistence to disk.

**v0.3.1** — QoL: optional streaming (`--stream` / `-s`) and metadata toggle (`--verbose` / `-v`). CLI only. Core loop unchanged. `Response.metadata` schema locked.
