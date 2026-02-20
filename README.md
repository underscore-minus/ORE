# ORE

**Orchestrated Reasoning Engine** — a CLI-first, local orchestration layer around a single invariant: **Input → Reasoner → Output**. ORE runs the loop via [Ollama](https://ollama.com), injects an explicit persona (Aya), and keeps all state visible: sessions, tools, and outputs are passed or flagged explicitly. No hidden accumulation, no implicit steps.

ORE is not a generic chatbot wrapper. It is a minimal orchestration primitive: one reasoner call per turn, append-only session history, optional tool runs gated by permissions, and structured or streamed output. The design is built to stay testable and scriptable while evolving toward routing, skills, and multi-agent workflows (see [docs/roadmap.md](docs/roadmap.md)).

---

## What ORE does

- **Single loop** — Every turn is: build message list (system + optional tool results + optional session history + user) → call reasoner once → return response. Session is passed in; tool results are turn-scoped and never stored.
- **Modes** — Single-turn, interactive REPL (stateless), conversational REPL (in-memory session), and persisted sessions (save/resume to `~/.ore/sessions/`).
- **Tools (v0.6)** — Optional pre-reasoning step: run a built-in tool (e.g. `echo`, `read-file`) via `--tool`; a gate enforces permissions (`--grant`). Tool output is injected into the turn only; it is never written into the session.
- **Routing (v0.7)** — Opt-in `--route`: select a tool by intent (keyword matching). Routing info is printed to stderr; with `--json`, the response includes a `routing` key. No extra LLM call.
- **Output** — Plain text, streamed tokens (`--stream`), or structured JSON (`--json`). Stdin can supply the prompt when not in REPL mode.

Persona, session lifecycle, and tool execution are all explicit in the CLI and in the orchestrator API. See [docs/architecture.md](docs/architecture.md) and [docs/foundation.md](docs/foundation.md) for invariants and extension rules.

---

## Quick start

```bash
# Clone and enter
git clone https://github.com/underscore-minus/ORE.git && cd ORE

# Setup (Python 3.10)
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Ollama must be running; pull a model first: ollama pull llama3.2
python main.py "Explain the concept of an irreducible loop."
```

---

## Commands

| Command | Description |
|---------|-------------|
| `python main.py "Your question"` | Single turn: ask Aya (auto-picks a model) |
| `python main.py --interactive` or `-i` | Interactive REPL — each turn stateless, no history |
| `python main.py --conversational` or `-c` | Conversational REPL — session in memory across turns |
| `python main.py --save-session NAME` | Conversational REPL, persist to `~/.ore/sessions/` after each turn |
| `python main.py --resume-session NAME` | Resume a saved session (implies conversational) |
| `python main.py --list-models` | List installed Ollama models and exit |
| `python main.py --list-tools` | List available tools and required permissions, then exit |
| `python main.py "Question" --model llama3.2` | Use a specific model |
| `python main.py "Question" --tool echo --tool-arg msg=hi` | Run a tool before reasoning (e.g. echo; no permission needed) |
| `python main.py "say back hello" --route` | Route by intent: match prompt to a tool (e.g. echo); routing on stderr |
| `python main.py "repeat" --route --route-threshold 0.3` | Lower confidence threshold (default 0.5) to accept weaker matches |
| `python main.py "Summarize" --tool read-file --tool-arg path=/path/to/file --grant filesystem-read` | Run a permissioned tool; grant required permission |
| `python main.py --stream` or `-s` | Stream output token-by-token (any mode) |
| `python main.py --verbose` or `-v` | Show response metadata (ID, model, token counts) |
| `python main.py "Question" --json` or `-j` | Output structured JSON (single-turn only) |
| `echo "Question" \| python main.py` | Pipe prompt via stdin (single-turn) |

---

## Layout

- **`ore/`** — Core package: `types`, `reasoner`, `core`, `cli`, `models`, `store`, `tools`, `gate`, `router`
- **`ore/prompts/`** — Aya system persona (injected by orchestrator)
- **`tests/`** — Pytest suite (types, store, core, cli, reasoner, models, tools, gate, router)
- **`main.py`** — Entry point
- **`docs/`** — Foundation, architecture, roadmap, invariants
- **`requirements.txt`** — Runtime deps; **`requirements-dev.txt`** — pytest, black

---

## Testing and CI

```bash
pip install -r requirements-dev.txt
pytest -v
black --check .   # enforce formatting
```

CI runs on push/PR to `main`: Python 3.10, `black --check`, then `pytest`. See [.github/workflows/ci.yml](.github/workflows/ci.yml).

---

Session persistence (v0.4) and structured output/stdin (v0.5) are opt-in. The tool & gate framework (v0.6) adds controlled, explicit side effects before reasoning; tool results are turn-scoped and never stored in the session. Routing (v0.7) adds intent-based tool selection via `--route` (rule-based; no extra LLM call). Aya's persona lives in `ore/prompts/aya.txt` and is injected by the orchestrator in `ore/core.py`.
