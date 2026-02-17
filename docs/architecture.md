# ORE Architecture (v0.3.1)

**Version**: v0.3.1 (QoL: optional streaming and metadata toggle)
**Language**: Python 3.10 (PEP 8, `black`-formatted)
**Core idea**: An *irreducible loop* — **Input → Reasoner → Output** — run locally via Ollama.

---

## Execution Modes

ORE v0.3 supports three modes, all sharing the same loop:

| Mode | Flag | Session | History visible to reasoner |
|------|------|---------|----------------------------|
| Single-turn | _(none)_ | None | No |
| Interactive REPL | `--interactive` / `-i` | None | No (unchanged from v0.2) |
| Conversational REPL | `--conversational` / `-c` | `Session` | Yes |

**Orthogonal flags (v0.3.1):** `--stream` / `-s` streams output token-by-token in any mode. `--verbose` / `-v` shows response metadata (ID, model, token counts); default is metadata hidden.

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
  - `fetch_models`, `default_model` (Ollama model utilities).

### `ore/cli.py`

- **Role**: **CLI layer** — argument parsing and user interaction via stdout/stderr.
- **Key responsibilities**:
  - Build an `argparse.ArgumentParser` with:
    - Positional `prompt` (optional in REPL modes).
    - Optional `--model NAME` flag.
    - `--list-models` flag to list Ollama models and exit.
    - `--interactive` / `-i` flag — v0.2 stateless REPL.
    - `--conversational` / `-c` flag — v0.3 session-aware REPL.
    - `--stream` / `-s` flag — stream output token-by-token (v0.3.1).
    - `--verbose` / `-v` flag — show metadata (default: hidden) (v0.3.1).
  - Enforce mutual exclusivity of `--interactive` and `--conversational`.
  - For `--conversational`: create a `Session()` before the loop and pass it to `engine.execute()` each turn.
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

## External Dependencies and Requirements

### Python and environment

- **Python version**: **3.10**.
- **Virtual environment**: `.venv` created via `python3.10 -m venv .venv`.

### Runtime dependencies (`requirements.txt`)

- **`ollama>=0.3.0`** — Python client for the local Ollama server.
- **`python-dotenv>=1.0.0`** — Loads `.env` environment variables.

### Dev/tooling dependencies

- **`black`** — code formatting (PEP 8).

---

## Component Purposes at a Glance

- **`README.md`** — Developer-facing quick start.
- **`docs/foundation.md`** — Foundation invariants and versioning rules.
- **`docs/architecture.md`** (this file) — High-level architectural overview for v0.3.1.
- **`main.py`** — Thin entry point.
- **`ore/cli.py`** — CLI UX, mode dispatch, session lifecycle.
- **`ore/core.py`** — Orchestration: loop construction, persona injection, session threading.
- **`ore/reasoner.py`** — Reasoner abstraction and Ollama backend.
- **`ore/models.py`** — Model discovery and default selection.
- **`ore/types.py`** — Typed data contracts (`Message`, `Response`, `Session`).
- **`ore/__init__.py`** — Package API surface.

---

## How to Extend This Architecture

- **Add a new reasoner backend**
  - Implement a new subclass of `Reasoner`.
  - Provide `reason(messages: List[Message]) -> Response`.
  - Wire it in via `ORE(NewReasoner(...))`.

- **Add disk-persistent sessions (future version)**
  - Serialise/deserialise `Session.messages` to/from a file or database.
  - The `Session` contract is already list-based and serialisation-friendly.
  - This belongs in the CLI or a new `SessionStore` module — not in `ORE` or `Reasoner`.

- **Add tools (future version)**
  - Extend `ORE.execute` to inject tool-call messages into the message list.
  - Keep `Reasoner` focused on "given messages → model call → Response".

- **Add richer CLI commands**
  - Streaming and verbose are implemented (v0.3.1). Further options: different personas, named sessions.
  - Options for choosing backends (`--backend ollama`, `--backend remote`).
