# ORE Architecture (v0.4)

**Version**: v0.4 (Persistent sessions)
**Language**: Python 3.10 (PEP 8, `black`-formatted)
**Core idea**: An *irreducible loop* — **Input → Reasoner → Output** — run locally via Ollama.

---

## Execution Modes

ORE v0.3 supports three modes, all sharing the same loop:

| Mode | Flag | Session | History visible to reasoner |
|------|------|---------|----------------------------|
| Single-turn | _(none)_ | None | No |
| Interactive REPL | `--interactive` / `-i` | None | No |
| Conversational REPL | `--conversational` / `-c` | `Session` | Yes |
| Conversational (persisted) | `--save-session` / `--resume-session` | `Session` | Yes (implies `-c`) |

**Orthogonal flags:** `--stream` / `-s` streams output token-by-token in any mode. `--verbose` / `-v` shows response metadata (ID, model, token counts); default is metadata hidden.

**Mode precedence:** If `--save-session` or `--resume-session` is present → conversational. Else if `-c` → conversational. Else → stateless.

**Interactive ≠ Conversational.** Interactive mode (v0.2) is a REPL where turns are isolated. Conversational mode (v0.3) is a REPL where turns accumulate in an explicit `Session`. The distinction is versioned and locked.

---

## Semantics: Conversational mode (v0.3)

- **Session** — an ordered list of `Message` objects holding prior user and assistant turns.
- **Explicit state** — the session is passed as an argument to `ORE.execute()`; it is never stored inside the `ORE` object.
- **System message excluded** — Aya's system prompt is injected fresh each turn and is not part of the session.
- **Append-only** — `ORE.execute()` appends the user message and the assistant response after each turn. No messages are removed or reordered.

Any change that adds implicit history (storing state inside `ORE` without passing it as an argument) would violate the foundation's "no hidden steps" invariant.

---

## High-level Architecture

- **Runtime flow**
  - **User command** → `python main.py "prompt"` (or CLI options).
  - **`main.py`** loads environment (`.env` via `python-dotenv`) and delegates to CLI.
  - **`ore.cli`**:
    - Parses CLI arguments (`--interactive`, `--conversational`, `--model`, `--list-models`, `--stream`/`-s`, `--verbose`/`-v`).
    - Validates mutual exclusivity of `--interactive` and `--conversational`.
    - Optionally lists available Ollama models.
    - Chooses a model (explicit `--model` or auto-selected default).
    - Instantiates the orchestrator `ORE` with an `AyaReasoner`.
    - Runs the appropriate mode:
      - Single-turn: calls `engine.execute(prompt)` or `engine.execute_stream(prompt)` when `--stream`.
      - Interactive loop (`-i`): calls `engine.execute(line)` or `engine.execute_stream(line)` per turn — no session.
      - Conversational loop (`-c`): creates a `Session()`, calls `engine.execute(...)` or `engine.execute_stream(...)` per turn.
    - Prints the assistant output; metadata only when `--verbose`.
  - **`ore.core.ORE`**:
    - Loads Aya's **system persona** from `ore/prompts/aya.txt`.
    - Builds the message list for each turn:
      - Without session: `[system, user]`
      - With session: `[system] + session.messages + [user]`
    - Calls the configured **`Reasoner`** backend (`reason()` or `stream_reason()` when streaming).
    - If a session was provided, appends the user and assistant messages to it.
  - **`ore.reasoner.AyaReasoner`**:
    - Translates `Message` objects → Ollama `chat` payload.
    - Calls local Ollama via `ollama.Client.chat` (or `chat(..., stream=True)` when streaming).
    - Wraps result into a `Response` with **diagnostic metadata** (eval counts, durations).

- **Design principles**
  - **Separation of concerns**:
    - CLI/UI layer is isolated from reasoning and model selection.
    - Orchestration (`ORE`) is separate from any particular LLM backend (`Reasoner` interface).
    - Session ownership belongs to the CLI, not the engine.
  - **Pluggable backends**:
    - `Reasoner` is an abstract base class; additional reasoners can be added without changing the CLI or session logic.
  - **Data-first contracts**:
    - `Message`, `Response`, and `Session` are simple dataclasses.
    - Session history is a plain `List[Message]` — no magic, no hidden accumulation.

---

## Modules and Their Responsibilities

### `main.py`

- **Role**: Application entry point.
- **Responsibilities**:
  - Load environment variables from `.env` using `dotenv.load_dotenv()`.
  - Call `ore.cli.run()` to hand off to the CLI layer.

### `ore/__init__.py`

- **Role**: Package facade and public API surface.
- **Exports**:
  - `run` (CLI entry function).
  - `ORE` (orchestrator engine).
  - `Reasoner`, `AyaReasoner` (reasoner abstraction + default implementation).
  - `Message`, `Response`, `Session` (data contracts).
  - `SessionStore`, `FileSessionStore` (session persistence).
  - `fetch_models`, `default_model` (Ollama model utilities).

### `ore/cli.py`

- **Role**: **CLI layer** — argument parsing and user interaction via stdout/stderr.
- **Key responsibilities**:
  - Build an `argparse.ArgumentParser` with:
    - Positional `prompt` (optional in REPL modes).
    - Optional `--model NAME` flag.
    - `--list-models` flag to list Ollama models and exit.
    - `--interactive` / `-i` flag — stateless REPL.
    - `--conversational` / `-c` flag — session-aware REPL (in-memory).
    - `--save-session NAME` — persist session to ~/.ore/sessions/ (implies `-c`).
    - `--resume-session NAME` — load session from disk (implies `-c`).
    - `--stream` / `-s` flag — stream output token-by-token.
    - `--verbose` / `-v` flag — show metadata (default: hidden).
  - Enforce mutual exclusivity of `--interactive` with `--conversational`, `--save-session`, and `--resume-session`.
  - For conversational mode: create or load a `Session`, pass it to `engine.execute()` each turn, save eagerly if `--save-session` set.
  - Print per-response: `[AYA]:` content; `[Metadata]:` only when `--verbose`.
  - When `--stream`: drive `engine.execute_stream()`, print chunks as they arrive, update session after exhaustion.
- **Why it exists**:
  - Cleanly separates how users run ORE from how reasoning is performed.
  - Owns session lifecycle for conversational mode.

### `ore/core.py`

- **Role**: **Orchestrator / engine** that wires the system persona and optional session to a `Reasoner`.
- **Key responsibilities**:
  - Hold a reference to a `Reasoner` implementation.
  - Load Aya's **system prompt** from `ore/prompts/aya.txt`.
  - Construct the message list for each turn:
    - `[system]` + `session.messages` (if any) + `[user]`
  - Delegate to `self.reasoner.reason(messages)` and return its `Response`; or when streaming, to `self.reasoner.stream_reason(messages)` via `execute_stream()`.
  - If a session was provided, append the user and assistant messages after the call.
- **Why it exists**:
  - Central place to enforce the loop structure.
  - Inject persona without mixing it into the LLM backend.
  - Session threading is explicit here — no implicit state on `ORE`.

### `ore/reasoner.py`

- **Role**: **Reasoner abstraction and Aya/Ollama implementation.**
- **Components**:
  - `Reasoner` (abstract base class):
    - Declares `reason(self, messages: List[Message]) -> Response`.
    - Provides `stream_reason(self, messages) -> Generator[str, None, Response]` with a default fallback (yields full content in one chunk via `reason()`).
  - `AyaReasoner(Reasoner)`:
    - Uses `ollama.Client` as the underlying LLM driver.
    - Maps each `Message` to Ollama's `{"role": ..., "content": ...}` shape.
    - Calls `client.chat(model=self.model_id, messages=payload)` or `chat(..., stream=True)` for streaming.
    - Returns a `Response` with content, model ID, and diagnostic metadata.
    - Overrides `stream_reason()` for real token-by-token streaming via Ollama's streaming API.
- **Why it exists**:
  - Decouples how we talk to an LLM from the orchestrator.
  - Unchanged in v0.3 — the reasoner only receives a list of messages; it has no knowledge of sessions.

### `ore/models.py`

- **Role**: **Model discovery and selection** for Ollama.
- **Unchanged from v0.2.**

### `ore/types.py`

- **Role**: **Core data contracts** for messages, responses, and sessions.
- **Components**:
  - `Message` dataclass:
    - Fields: `role`, `content`, auto-generated `id`, `timestamp`.
  - `Response` dataclass:
    - Fields: `content`, `model_id`, auto-generated `id`, `timestamp`, `metadata`.
    - `metadata` schema is **locked in v0.3.1** (see table below).
  - `Session` dataclass (new in v0.3):
    - Fields: `messages` (List[Message]), auto-generated `id`, `created_at`.
    - Accumulates user and assistant turns across `ORE.execute()` calls.
    - The system message is never stored here.
- **Why it exists**:
  - Provides stable, versioned schemas for the entire data flow.
  - `Session` makes conversational state explicit and inspectable.

### `Response.metadata` — known keys (schema locked in v0.3.1)

`AyaReasoner` (Ollama backend) populates `metadata` on a best-effort basis.
The following keys are the committed stable contract as of v0.3.1:

| Key | Type | Description |
|-----|------|-------------|
| `eval_count` | `int` | Tokens generated in the response |
| `prompt_eval_count` | `int` | Tokens in the prompt sent to the model |
| `eval_duration` | `int` | Response generation time (nanoseconds) |
| `prompt_eval_duration` | `int` | Prompt processing time (nanoseconds) |

Custom reasoner backends may omit all keys or add their own; the above four are guaranteed for `AyaReasoner`.

---

## Session persistence (v0.4)

Persistence is **opt-in** and lives entirely outside `ORE` and `Reasoner`. The CLI owns load/save; the engine receives `Session` as an explicit argument and knows nothing about files.

### SessionStore abstraction

- **`SessionStore`** (abstract base class):
  - `save(session: Session, name: str) -> None`
  - `load(name: str) -> Session`
  - `list() -> list[str]`

- **`FileSessionStore`** (default implementation):
  - Root: `~/.ore/sessions/`
  - One JSON file per session: `<name>.json`
  - Full message history, no summarization
  - Human-readable and inspectable

### CLI flags

- `--save-session <name>` — persist session after each turn (implies `-c`)
- `--resume-session <name>` — load session from disk (implies `-c`)
- Both imply conversational mode; neither may be used with `--interactive`

### Save semantics

**Sessions are saved eagerly after each successful turn.** No background flushing, batching, or lazy writes. Any future change (lazy saves, checkpoints, save-on-exit-only) would be an intentional, versioned change — not silent drift.

### Name vs. ID distinction

The session **name** (CLI flag, filename) is a user-facing handle. `Session.id` is an immutable UUID identity assigned at creation. Renaming a file does not change the session's identity. This separation supports future operations: rename, fork, merge, audit.

### JSON format

```json
{
  "id": "uuid-string",
  "created_at": 1234567890.123,
  "messages": [
    {"role": "user", "content": "...", "id": "uuid", "timestamp": 1234567890.123},
    {"role": "assistant", "content": "...", "id": "uuid", "timestamp": 1234567890.123}
  ]
}
```

### Edge behaviour

- Deleting `~/.ore/sessions/` breaks nothing; the next save recreates it
- `--resume-session foo` where `foo.json` does not exist → clear error, exit
- No auto-save, no default session, no persistence baked into `Session` itself

---

## External Dependencies and Requirements

### Python and environment

- **Python version**: **3.10**.
- **Virtual environment**: `.venv` created via `python3.10 -m venv .venv`.

### Runtime dependencies (`requirements.txt`)

- **`ollama>=0.3.0`** — Python client for the local Ollama server.
- **`python-dotenv>=1.0.0`** — Loads `.env` environment variables.

### Dev/tooling dependencies (`requirements-dev.txt`)

- **`pytest`** — test runner.
- **`pytest-cov`** — optional coverage reporting.
- **`black`** — code formatting (PEP 8).

Tests live in `tests/`; CI (`.github/workflows/ci.yml`) runs on push/PR to `main`: `black --check` then `pytest`.

---

## Component Purposes at a Glance

- **`README.md`** — Developer-facing quick start and testing/CI notes.
- **`docs/foundation.md`** — Foundation invariants and versioning rules.
- **`docs/invariants.md`** — Mechanical invariants (loop, session, CLI); testable guarantees.
- **`docs/architecture.md`** (this file) — High-level architectural overview for v0.3.1.
- **`tests/`** — Pytest suite (types, store, core, cli, reasoner, models); no live Ollama required.
- **`.github/workflows/ci.yml`** — CI: Python 3.10, black check, pytest.
- **`main.py`** — Thin entry point.
- **`ore/cli.py`** — CLI UX, mode dispatch, session lifecycle.
- **`ore/core.py`** — Orchestration: loop construction, persona injection, session threading.
- **`ore/reasoner.py`** — Reasoner abstraction and Ollama backend.
- **`ore/models.py`** — Model discovery and default selection.
- **`ore/types.py`** — Typed data contracts (`Message`, `Response`, `Session`).
- **`ore/store.py`** — Session persistence (`SessionStore`, `FileSessionStore`).
- **`ore/__init__.py`** — Package API surface.

---

## How to Extend This Architecture

- **Add a new reasoner backend**
  - Implement a new subclass of `Reasoner`.
  - Provide `reason(messages: List[Message]) -> Response`.
  - Wire it in via `ORE(NewReasoner(...))`.

- **Session persistence (v0.4 — implemented)**
  - See the *Session persistence* section below.

- **Add tools (future version)**
  - Extend `ORE.execute` to inject tool-call messages into the message list.
  - Keep `Reasoner` focused on "given messages → model call → Response".

- **Add richer CLI commands**
  - Streaming and verbose are implemented (v0.3.1). Further options: different personas, named sessions.
  - Options for choosing backends (`--backend ollama`, `--backend remote`).
