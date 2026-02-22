# ORE Roadmap

## Completed

**v0.1 — The Loop Exists**
Single-turn, stateless. Input → Reasoner → Output.
The irreducible primitive.

**v0.2 — Temporal Continuity**
Interactive REPL. Many turns, one process. Still stateless per turn.

**v0.2.1 — Semantics Lock**
"Interactive" explicitly defined as non-conversational. No memory, no
accumulation, no hidden context. Documentation only.

**v0.3 — Cognitive Continuity**
Session history. Explicit state. Append-only. No hidden accumulation.

**v0.3.1 — Streaming and Metadata**
Token-by-token streaming. Verbose metadata flag. Response schema locked.

**v0.4 — Persistent Sessions**
Opt-in file-based persistence. `--save-session` / `--resume-session`.
Core unchanged. CLI owns lifecycle.

**v0.4.1 — Hardening and Invariants**
Mechanical invariants documented in `docs/invariants.md`. Tests enforce
reasoner-once-per-turn, session append-only, CLI flag conflicts. CI fails
if loop or state model is broken.

**v0.4.2 — Invariants Polish**
Canonical terminology (`ORE.execute()`). Non-invariants section (determinism,
token count, semantic consistency).

**v0.5 — Composable Output**
`--json` flag for single-turn structured output. Stdin as signal source.
The pipe exists. ORE becomes chainable by humans.

**v0.6 — Tool Execution + Gate**
Tools inject real-world context into the loop. Default-deny permission gate.
The loop does things in the world.

**v0.6.1 — Formatting Fix**
Black formatting fix for CI; version bump to 0.6.1.

**v0.7 — Routing / Intent Detection**
Rule-based router. Keyword/phrase matching. No extra LLM call.
Decision visible on stderr and in JSON. Human remains override authority.

**v0.7.1 — Design Decisions Document**
Six locked design decisions for skill activation documented in
`docs/skills.md` before any code written. Interface before implementation.

**v0.8 — Skill / Instruction Activation**
Filesystem-based skills. SKILL.md + YAML frontmatter. Three-level progressive
disclosure: metadata → instructions → resources. Skills routable via existing
router. Turn-scoped, session-pure, one reasoner call preserved.

**v0.9 — Chainable Execution Artifacts**
*The last engine primitive.* Versioned execution artifact (`ore.exec.v1`) with
`--artifact-out` (emit) and `--artifact-in` (consume). Single-turn only.
Chaining via data, not runtime coupling. Schema documented in
`docs/artifact-schema.md`. Existing `--json` workflows remain backward
compatible. All core invariants preserved and test-enforced.

**v0.9.1 — Interface Lock**
*The stability declaration.*

Problem solved: a powerful tool is not infrastructure until its contracts
are frozen. v0.9.1 is where ORE stops being a personal project and becomes
something dependable.

What gets locked:
- CLI flags and their semantics
- JSON output schema
- Execution contracts (what goes in, what comes out)
- Failure modes and exit codes
- All invariants, formally documented

Rules after this point:
- Nothing changes without a version bump
- Additions are allowed; mutations are not
- Every contract has a test that enforces it

**v1.0 — The Mainframe**
*Structurally complete. Not feature complete.*

ORE at v1.0 is a stable, chainable, multi-backend reasoning engine with
explicit state, auditable actions, locked interfaces, and self-describing
output. It is ready to have a suit built on top of it.

At this point:
- Agents are libraries
- Workflows are configs
- UIs are skins
- Backends are replaceable
- Orchestration is external

The engine does not grow. It hosts growth.

**v1.1.1 — CLI Persona Agnostic**

- Removed hardcoded Aya system prompt from CLI.
- Added `--system` flag; default empty.
- Consumers supply persona explicitly. `python main.py "prompt" --system "You are Aya..."` restores prior behavior.

---

## In Progress

**feature/datetime-tool — Parked**
DateTime tool complete and tested. Held pending v1.0 feature decisions.
Branch: `feature/datetime-tool`.

---

## Post v1.0 — Platform

Everything below this line is the suit, not the mainframe.
These are not engine versions. They are products built on ORE.

**P1 — Multi-Backend Adapter**
LiteLLM integration. `--backend` flag. Claude, OpenAI, Mistral alongside
Ollama. Local-first default preserved. Backend is a detail, not a dependency.

**P2 — Thinking Model Support**
`--thinking` flag. Reasoning trace separated from final response.
Displayed as `[THINKING]:` on stderr. Clean response to stdout.
Warning on stderr if no thinking tokens produced. `--strict-thinking`
exits 1 for scripting use.

**P3 — Web Search + DateTime Tools**
Merge `feature/datetime-tool`. Add web search tool.
Real-world context available without leaving the loop.

**P4 — ORE as Library**
`import ore` as a first-class use case.
Programmatic access to the loop without the CLI.
Foundation for the node-based workflow builder.

**P5 — Frontend / Visual Shell**
The robotic suit.
Node-based workflow builder. Agent construction interface.
Real-time execution visibility. The mainframe becomes accessible
to non-technical pilots.

---

## Design Principles (Permanent)

These do not change at any version:

1. **The loop is irreducible.** Input → Reasoner → Output. No hidden steps.
2. **State is explicit.** If it exists, it is named and visible.
3. **Complexity lives at the edges.** Core stays boring.
4. **One reasoner call per turn.** Always.
5. **The engine produces objects, not behavior.**
6. **Backward clarity beats forward cleverness.**
7. **Each version adds one thing.**

---

*The film which produces the movie is the AI.*
*The projector is the ORE.*
*The mainframe runs the suit.*
*The pilot decides.*
