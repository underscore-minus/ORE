# ORE — Orchestrated Reasoning Engine

**v1.2.0 — The Mainframe**

---

## What ORE Is

ORE is a minimal, local-first reasoning engine built around one irreducible loop:
**Input → Reasoner → Output**. It supports multiple backends: [Ollama](https://ollama.com) (local)
and DeepSeek (API). State is explicit and visible; every turn produces exactly one
reasoner call. Nothing is hidden: sessions are passed as arguments, tool results
are turn-scoped and never stored, and routing decisions are printed to stderr. ORE
is the mainframe — the stable, auditable primitive that agents, workflows, and
interfaces are built on top of. It does not grow. It hosts growth.

---

## What ORE Is Not

These boundaries are explicit and permanent.

- **Not an agent framework.** ORE does not orchestrate other instances of itself,
  manage agent lifecycles, or maintain implicit goal state.
- **Not a workflow engine.** Chaining is done via data (execution artifacts), not
  runtime coupling. ORE does not know what happens after its output.
- **Not a chatbot shell.** The CLI is a thin dispatch layer over a structured API.
  Persona, session, and tool logic are wired explicitly in code.
- **Not feature complete.** Multi-backend support, a visual shell, and platform
  tooling are post-v1.0 work (see `docs/roadmap.md`).
- **Structurally complete.** The loop, the contracts, the invariants, and the
  interfaces are locked. Additions are permitted; mutations are not.

---

## The Version Story

Each version added one conceptual dimension. The engine was built in layers,
and each layer is still visible.

| Version | What it added |
|---------|---------------|
| v0.1 | The loop: single-turn, stateless. Input → Reasoner → Output. |
| v0.2 | Temporal continuity: interactive REPL, still stateless per turn. |
| v0.2.1 | Semantics lock: "interactive" explicitly defined as non-conversational. |
| v0.3 | Cognitive continuity: session history, explicit append-only state. |
| v0.3.1 | Streaming and metadata: token-by-token output; response schema locked. |
| v0.4 | Persistent sessions: opt-in file-based save/resume; core unchanged. |
| v0.4.1 | Hardening: mechanical invariants documented and test-enforced. |
| v0.4.2 | Invariants polish: canonical API naming; non-invariants explicitly listed. |
| v0.5 | Composable output: `--json` flag; stdin as signal source. The pipe exists. |
| v0.6 | Tool execution + gate: default-deny permissions; tool results turn-scoped. |
| v0.6.1 | Black formatting fix; version bump. |
| v0.7 | Routing / intent detection: rule-based, no extra LLM call; decision visible. |
| v0.7.1 | Design decisions for skill activation documented before code written. |
| v0.8 | Skill activation: filesystem-based instructions; three-level loading; turn-scoped. |
| v0.9 | Chainable execution artifacts: `--artifact-out` / `--artifact-in`; data-only chaining. |
| v0.9.1 | Interface lock: CLI flags, JSON schema, exit codes, and `__all__` frozen. |
| v1.0 | The Mainframe: version declaration, docs cleanup, structurally complete. |
| v1.1.1 | CLI persona agnostic: `--system` flag; default empty; no hardcoded Aya prompt. |
| v1.2.0 | DeepSeek backend: `--backend deepseek`, `DeepSeekReasoner`, `DEEPSEEK_API_KEY` env. |

---

## Installation

**Requires:** Python 3.10. For the default **Ollama** backend: [Ollama](https://ollama.com) running
locally with at least one model pulled. For the **DeepSeek** backend: set the
`DEEPSEEK_API_KEY` environment variable (see Key flags below).

**Install as a dependency** (from another project):

```bash
pip install "git+https://github.com/underscore-minus/ORE.git@v1.2.0"
# or latest from main:
# pip install "git+https://github.com/underscore-minus/ORE.git"
```

**Run from source** (clone, then CLI):

```bash
# Clone
git clone https://github.com/underscore-minus/ORE.git
cd ORE

# Create and activate virtual environment
python3.10 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows

# Install the package (editable for development)
pip install -e .

# Pull a model (if you haven't already)
ollama pull llama3.2

# Run
python main.py "What is an irreducible loop?"
```

Dev dependencies (pytest, black):

```bash
pip install -r requirements-dev.txt
```

---

## Usage

### Modes

| Mode | Invocation | Session | Notes |
|------|-----------|---------|-------|
| Single-turn | `python main.py "prompt"` | None | Stateless. Default. |
| Interactive REPL | `python main.py -i` | None | Many turns, each stateless. |
| Conversational REPL | `python main.py -c` | In-memory | Turns accumulate in a shared session. |
| Persistent session | `python main.py --save-session NAME` | File-backed | Saved to `~/.ore/sessions/` after each turn. |
| Resume session | `python main.py --resume-session NAME` | File-backed | Load a prior session; implies `-c`. |

### Key flags

```bash
# Backend: ollama (local, default) or deepseek (API; requires DEEPSEEK_API_KEY)
python main.py "prompt" --backend ollama
python main.py "prompt" --backend deepseek   # uses DEEPSEEK_API_KEY env var

# Model selection (--model applies to the chosen backend)
python main.py "prompt" --model llama3.2     # Ollama
python main.py "prompt" --backend deepseek --model deepseek-chat   # DeepSeek default

# List available Ollama models (Ollama backend only)
python main.py --list-models

# Structured JSON output (single-turn only)
python main.py "prompt" --json

# Stream tokens as they arrive
python main.py "prompt" --stream

# Verbose: show response metadata (ID, model, token counts)
python main.py "prompt" --verbose

# System prompt for the reasoner (default: none)
python main.py "who are you?" --system "You are a helpful assistant."

# Read prompt from stdin
echo "What is ORE?" | python main.py
```

### Tools

Tools run a pre-reasoning step and inject their output into the current turn.
Tool results are turn-scoped — they are never stored in the session.

```bash
# Built-in echo tool (no permissions required)
python main.py "What did the tool say?" --tool echo --tool-arg msg="hello"

# Read a file into context (requires filesystem-read permission)
python main.py "Summarize this" \
  --tool read-file --tool-arg path=/path/to/file \
  --grant filesystem-read

# List available tools and their required permissions
python main.py --list-tools
```

### Skills

Skills are filesystem-based instruction modules stored in `~/.ore/skills/`.
Activating a skill injects its instructions as `role="system"` messages before
tool results. Skills are turn-scoped and never stored in the session.

```bash
# Activate a skill by name
python main.py "Review this code" --skill my-skill

# List discovered skills
python main.py --list-skills
```

Skill format: `~/.ore/skills/<name>/SKILL.md` with YAML frontmatter
(`name`, `description`, optional `hints`) followed by instruction body.
Optional resources live in `<skill-dir>/resources/`.

### Routing

`--route` uses keyword matching to select a tool or skill from the prompt.
No extra LLM call. The routing decision is printed to stderr.

```bash
# Auto-select a tool or skill based on prompt keywords
python main.py "read the config file" --route

# Lower the confidence threshold (default 0.5)
python main.py "read something" --route --route-threshold 0.3

# Route + JSON: routing decision appears in the JSON payload
python main.py "echo hello" --route --json
```

`--route` and `--tool` are mutually exclusive.

### Artifacts

An execution artifact is a self-describing JSON record of one ORE turn.
Chaining is via data, not runtime coupling.

```bash
# Emit an artifact to a file
python main.py "Explain the loop" --artifact-out result.json

# Emit to stdout (suppresses normal response)
python main.py "Explain the loop" --artifact-out -

# Consume an artifact and run one turn with its prompt
python main.py --artifact-in result.json

# Pipeline: emit then consume
python main.py "First prompt" --artifact-out - | python main.py --artifact-in -
```

Artifact schema: see `docs/artifact-schema.md`.

### Using ORE as a library

Import `ore` as a module first so that `ore.__version__` and other module-level
attributes are available; then import the names you need.

```python
import ore
from ore import ORE, AyaReasoner, DeepSeekReasoner, default_model

# One-shot with Ollama (default backend)
model_id = default_model() or "llama3.2"
engine = ORE(AyaReasoner(model_id=model_id), system_prompt="You are a helpful assistant.")
response = engine.execute("What is an irreducible loop?")
print(response.content)

# Or with DeepSeek (set DEEPSEEK_API_KEY in the environment)
# engine = ORE(DeepSeekReasoner(model_id="deepseek-chat"), system_prompt="...")
```

**With a session** (conversational turns):

```python
import ore
from ore import ORE, AyaReasoner, Session, default_model

model_id = default_model() or "llama3.2"  # or use DeepSeekReasoner with DEEPSEEK_API_KEY
engine = ORE(AyaReasoner(model_id=model_id), system_prompt="You are a helpful assistant.")
session = Session()

r1 = engine.execute("My name is Alice.", session=session)
r2 = engine.execute("What is my name?", session=session)
print(r2.content)  # refers to prior turn
```

**API:** `engine.execute(user_prompt, session=None, tool_results=None, skill_context=None)` returns a `Response`. Use `engine.execute_stream(...)` for token-by-token streaming (same args, yields `str` chunks then returns the final `Response`). Full signatures and data contracts: `docs/interface-lock.md` §6 and §7.

**Message order** (how the engine builds the turn):  
`[system] + [skill_context] + [tool_results] + session.messages + [user]`.  
Skill and tool data are turn-scoped and never stored in the session. Details: `docs/architecture.md` and `docs/skills.md`.

**Full public API:** `ore/__init__.py` `__all__` and `docs/interface-lock.md` §12.

---

## Architecture in One Paragraph

`main.py` loads the environment and delegates to `ore/cli.py`, which owns argument
parsing, mode dispatch, session lifecycle, tool execution, and routing. The CLI
passes a clean message list to `ore/core.py` (the orchestrator), which constructs
the turn: consumer-provided system prompt + optional skill context + optional tool results + optional
session history + user message. The orchestrator calls a `Reasoner` exactly once
and returns a `Response`. `ore/reasoner.py` holds the abstract `Reasoner` base
class and `AyaReasoner` (Ollama); `ore/reasoner_deepseek.py` provides `DeepSeekReasoner` (DeepSeek API). All data flows through typed
contracts in `ore/types.py`. Session persistence lives in `ore/store.py`. Tools,
their permission gate, the intent router, and the skill loader are in
`ore/tools.py`, `ore/gate.py`, `ore/router.py`, and `ore/skills.py` respectively.
Nothing in the engine knows about the CLI, the system prompt content, or the session — those are
wired at the edges.

---

## Docs Index

| File | Contents |
|------|----------|
| `docs/foundation.md` | Core invariants, extension rules, versioning philosophy, and the permanent guiding question. Start here. |
| `docs/invariants.md` | Mechanical, testable guarantees (loop, session, tools, routing, skills, artifacts, interface lock) with test references. |
| `docs/interface-lock.md` | Frozen consumer contracts: every CLI flag, exit code, JSON schema, Python public API, and data contract field. |
| `docs/architecture.md` | Full architectural walkthrough: modules, data flows, execution modes, session semantics, and extension patterns. |
| `docs/artifact-schema.md` | Execution artifact schema, field definitions, CLI contract, and forward-compatibility rules. |
| `docs/skills.md` | Locked design decisions for skill activation (injection order, message role, simultaneous tool+skill, resources). |
| `docs/roadmap.md` | Complete version history (v0.1–v1.0), post-v1.0 platform plans, and the seven permanent design principles. |

---

## Extending ORE

### Adding a new tool

Implement the `Tool` abstract base class from `ore/tools.py`. A tool must define
`name` (str), `description` (str), `required_permissions` (list of `Permission`),
and `run(args: dict) -> ToolResult`. Optionally implement `routing_hints()` to
make the tool selectable via `--route`, and `extract_args(prompt)` to parse
arguments from natural language. Once implemented, register it in `TOOL_REGISTRY`
in `ore/tools.py` under a string key. The CLI will discover it automatically via
`--tool KEY` and `--list-tools`.

### Adding a new reasoner backend

Implement the `Reasoner` abstract base class from `ore/reasoner.py`. A reasoner
must implement `reason(messages: List[Message]) -> Response`. Optionally override
`stream_reason(messages)` for token-by-token streaming — the default fallback
delegates to `reason()` and yields the full response in one chunk. Wire the new
reasoner and system prompt at instantiation: `ORE(YourReasoner(model_id), system_prompt="...")`. The orchestrator,
session, and CLI layer have no knowledge of the backend and require no changes.
Reasoners must be persona-agnostic: they receive an ordered list of `Message`
objects and return a `Response`, nothing more.

**Example backends:** `AyaReasoner` (Ollama, in `ore/reasoner.py`) and
`DeepSeekReasoner` (DeepSeek API, in `ore/reasoner_deepseek.py`). The DeepSeek
backend requires the `DEEPSEEK_API_KEY` environment variable; the CLI uses
`--backend deepseek` and exits with a clear error if the key is missing.

---

## Design Principles

These do not change at any version.

1. **The loop is irreducible.** Input → Reasoner → Output. No hidden steps.
2. **State is explicit.** If it exists, it is named and visible.
3. **Complexity lives at the edges.** Core stays boring.
4. **One reasoner call per turn.** Always.
5. **The engine produces objects, not behavior.**
6. **Backward clarity beats forward cleverness.**
7. **Each version adds one thing.**

---

## Testing and CI

```bash
# Run the full suite
pytest -v

# Run only invariant tests
pytest -m invariant

# Check formatting
black --check .
```

193 tests (including invariants). CI runs on push/PR to `main`: Python 3.10,
`black --check`, then `pytest`. See `.github/workflows/ci.yml`.

---

*The film which produces the movie is the AI.*  
*The projector is ORE.*  
*The mainframe runs the suit.*  
*The pilot decides.*
