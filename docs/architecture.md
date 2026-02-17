# ORE Architecture (v0.2.1)

**Version**: v0.2.1 (stateless; single-turn or interactive REPL; semantics locked)  
**Language**: Python 3.10 (PEP 8, `black`-formatted)  
**Core idea**: An *irreducible loop* — **Input → Reasoner → Output** — run locally via Ollama.

---

## Semantics: Interactive mode (locked v0.2.1)

**Interactive ≠ Conversational.** Interactive mode is a REPL: multiple separate turns in one process. It is *not* a conversation.

- **No memory** — the reasoner never sees prior turns.
- **No accumulation** — no message history is built or passed.
- **No hidden context** — each turn invokes `ORE.execute` with only the current user input; the message list is always system + this single user message.

Any change that adds history, context window, or conversational continuity would be a new capability (e.g. a later version), not a redefinition of “interactive”.

---

## High-level Architecture

- **Runtime flow**
  - **User command** → `python main.py "prompt"` (or CLI options).
  - **`main.py`** loads environment (`.env` via `python-dotenv`) and delegates to CLI.
  - **`ore.cli`**:
    - Parses CLI arguments (including `--interactive` / `-i` for REPL mode).
    - Optionally lists available Ollama models.
    - Chooses a model (explicit `--model` or auto-selected default).
    - Instantiates the orchestrator `ORE` with an `AyaReasoner`.
    - Either runs a single turn (prompt on command line) or an interactive loop; each turn calls `engine.execute(prompt)` once — no message history.
    - Prints the assistant output and metadata to stdout.
  - **`ore.core.ORE`**:
    - Loads Aya’s **system persona** from `ore/prompts/aya.txt`.
    - Builds a minimal two-message list: system + user.
    - Calls the configured **`Reasoner`** backend.
  - **`ore.reasoner.AyaReasoner`**:
    - Translates `Message` objects → Ollama `chat` payload.
    - Calls local Ollama via `ollama.Client.chat`.
    - Wraps result into a `Response` with **diagnostic, unstable metadata** (eval counts, durations).

- **Design principles**
  - **Separation of concerns**:
    - CLI/UI layer is isolated from reasoning and model selection.
    - Orchestration (`ORE`) is separate from any particular LLM backend (`Reasoner` interface).
  - **Pluggable backends**:
    - `Reasoner` is an abstract base class; additional reasoners (remote API, tools, memory) can be added without changing the CLI.
  - **Data-first contracts**:
    - `Message` and `Response` are simple dataclasses designed to support multi-turn and memory later.

---

## Modules and Their Responsibilities

### `main.py`

- **Role**: Application entry point.
- **Responsibilities**:
  - Load environment variables from `.env` using `dotenv.load_dotenv()`.
  - Call `ore.cli.run()` to hand off to the CLI layer.
- **Notes**:
  - This file is what the README’s `python main.py ...` commands execute.

### `ore/__init__.py`

- **Role**: Package facade and public API surface.
- **Exports**:
  - `run` (CLI entry function).
  - `ORE` (orchestrator engine).
  - `Reasoner`, `AyaReasoner` (reasoner abstraction + default implementation).
  - `Message`, `Response` (data contracts).
  - `fetch_models`, `default_model` (Ollama model utilities).
- **Purpose**:
  - Allows consumers to import `ore` as a coherent package (e.g. `from ore import ORE, AyaReasoner`).

### `ore/cli.py`

- **Role**: **CLI layer** — argument parsing and user interaction via stdout/stderr.
- **Key responsibilities**:
  - Build an `argparse.ArgumentParser` with:
    - Positional `prompt` (optional when `--list-models` or `--interactive` is used).
    - Optional `--model NAME` flag to select a specific Ollama model.
    - `--list-models` flag to list all locally available Ollama models and exit.
    - `--interactive` / `-i` flag to run an interactive loop (REPL); each turn is stateless, no history.
  - Execute **model listing**:
    - Call `fetch_models()` to inspect Ollama.
    - Handle “no models installed” by printing guidance and exiting with non-zero status.
  - Execute **reasoning run** (single-turn or interactive):
    - Validate that `prompt` is present when not listing models and not using `--interactive`.
    - Determine `model_id`:
      - Use explicit `--model`, or
      - Use `default_model()` to auto-select from preferred models (`llama3.2`, `llama3.1`, `llama3`, `mistral`, `llama2`, `qwen2.5`) or first available.
    - Instantiate `ORE(AyaReasoner(model_id=model_id))`.
    - **Single-turn**: call `engine.execute(prompt)` once and print response.
    - **Interactive (`-i`)**: loop reading user input; for each line (until `quit`/`exit` or EOF), call `engine.execute(line)` and print response; no message history between turns.
    - Print for each response: `[AYA]:` content and `[Metadata]:` ID, model ID, optional diagnostic metadata.
- **Why it exists**:
  - Cleanly separates *how* users run ORE (CLI UX) from *how* reasoning is performed.

### `ore/core.py`

- **Role**: **Orchestrator / engine** that wires the system persona to a `Reasoner`.
- **Key responsibilities**:
  - Hold a reference to a `Reasoner` implementation.
  - Load Aya’s **system prompt** from `ore/prompts/aya.txt` (data, not logic).
  - Construct the message list for a single stateless turn:
    - `Message(role="system", content=system_prompt)`
    - `Message(role="user", content=user_prompt)`
  - Delegate to `self.reasoner.reason(messages)` and return its `Response`.
- **Why it exists**:
  - Central place to:
    - Enforce the irreducible loop structure.
    - Inject persona / rules without mixing them into the LLM backend logic.
    - Provide a future extension point for memory, tools, and multi-turn conversations.

### `ore/reasoner.py`

- **Role**: **Reasoner abstraction and Aya/Ollama implementation.**
- **Components**:
  - `Reasoner` (abstract base class):
    - Declares `reason(self, messages: List[Message]) -> Response`.
    - Intended to be implemented by any backend that can produce an answer from a list of messages.
  - `AyaReasoner(Reasoner)`:
    - Uses `ollama.Client` as the underlying LLM driver.
    - In `__init__`, stores the `model_id` (e.g. `llama3.2:latest`) and constructs an Ollama client.
    - In `reason`:
      - Maps each `Message` to Ollama’s expected `{"role": ..., "content": ...}` shape.
      - Calls `client.chat(model=self.model_id, messages=payload)`.
      - Extracts the `content` from the returned message.
      - Collects optional **diagnostic** metadata fields (eval counts, durations) into a dictionary.
      - Returns a `Response` with the content, model ID, and metadata.
- **Why it exists**:
  - Decouples *how* we talk to an LLM (Ollama today) from the orchestrator.
  - Makes it straightforward to add more sophisticated or remote backends later (e.g. cloud APIs, tool-enabled reasoning).

### `ore/models.py`

- **Role**: **Model discovery and selection** for Ollama.
- **Key responsibilities**:
  - `fetch_models(host: str | None = None) -> List[str]`:
    - Creates an `ollama.Client` (optionally pointed at a custom `host`).
    - Calls `client.list()` to retrieve models from the local Ollama server.
    - Normalizes the `model` field into a `List[str]` (e.g. `["llama3.2:latest", "mistral:latest"]`).
  - `default_model(host: str | None = None) -> str | None`:
    - Retrieves all available models via `fetch_models`.
    - Builds a mapping from base name (e.g. `llama3.2`) to first full name (e.g. `llama3.2:latest`).
    - Iterates through `PREFERRED_MODELS` in order and returns the first match, or falls back to the first available model.
    - Returns `None` if no models are available.
- **Why it exists**:
  - Encapsulates model selection policies in a single location.
  - Allows the CLI and future code to rely on a simple `default_model()` call instead of handling Ollama specifics.

### `ore/types.py`

- **Role**: **Core data contracts** for messages and responses.
- **Components**:
  - `Message` dataclass:
    - Fields: `role`, `content`, auto-generated `id`, `timestamp`.
    - Represents any message in a conversation (`"system"`, `"user"`, or `"assistant"`).
  - `Response` dataclass:
    - Fields: `content`, `model_id`, auto-generated `id`, `timestamp`, `metadata`.
    - `metadata` is **diagnostic and unstable** in v0.2: it may include token usage, latencies, or backend-specific fields, and its exact schema may change between versions.
- **Why it exists**:
  - Provides a stable schema that can evolve toward richer conversational histories and memory.
  - Keeps type hints and structure explicit for easier maintenance and refactoring.

---

## External Dependencies and Requirements

### Python and environment

- **Python version**: **3.10** (as used in the virtual environment and documented in `README.md`).
- **Virtual environment**:
  - Project assumes a `.venv` created via `python3.10 -m venv .venv`.
  - Dependencies installed into `.venv` via `pip install -r requirements.txt`.

### Runtime dependencies (`requirements.txt`)

- **`ollama>=0.3.0`**
  - Python client for interacting with the local Ollama server.
  - Used in:
    - `ore.reasoner.AyaReasoner` (`ollama.Client.chat`).
    - `ore.models.fetch_models` / `default_model` (`ollama.Client.list`).
  - **Requirement**: A compatible **Ollama server** running locally with at least one model pulled (e.g. `ollama pull llama3.2`).

- **`python-dotenv>=1.0.0`**
  - Loads environment variables from a `.env` file into `os.environ`.
  - Used in:
    - `main.py` via `load_dotenv()`.
  - **Purpose**:
    - Let users configure environment-level settings (future API keys, host overrides, etc.) without hard-coding them.

### Dev/tooling dependencies (from local `.venv`)

- The `.venv` includes **`black`** and its transitive dependencies:
  - Code is formatted with `black`, following PEP 8 style conventions.
  - Not required at runtime, but recommended for contributing or modifying the project.

---

## Component Purposes at a Glance

- **`README.md`**
  - Developer-facing quick start: cloning, environment setup, and example commands.
  - Explains layout and v0.2 limitations (stateless, no tools, one-turn).

- **`docs/foundation.md`**
  - Foundation and invariants for ORE (irreducible loop, stateless v0.1.x, separation of concerns, versioning rules).

- **`docs/architecture.md` (this file)**
  - High-level architectural overview for v0.2.
  - Describes modules, data contracts, and external dependencies.
  - Clarifies that response metadata is diagnostic and unstable.

- **`main.py`**
  - Thin entry point that wires environment loading to the CLI.

- **`ore/cli.py`**
  - CLI UX: argument parsing, model listing, user input handling, and human-readable output.

- **`ore/core.py`**
  - Orchestration logic: constructs the minimal loop and injects Aya’s persona from `ore/prompts/aya.txt`.

- **`ore/reasoner.py`**
  - Abstraction and Ollama-based implementation of the reasoning backend.

- **`ore/models.py`**
  - Model discovery and default selection policy for Ollama models.

- **`ore/types.py`**
  - Typed data contracts (`Message`, `Response`) used across orchestrator and reasoners.

- **`ore/__init__.py`**
  - Package API surface for importing ORE components in other Python code.

---

## How to Extend This Architecture

- **Add a new reasoner backend**
  - Implement a new subclass of `Reasoner` in `ore/reasoner.py` or a new module.
  - Provide a `reason(messages: List[Message]) -> Response` implementation using any LLM API or custom logic.
  - Wire it into the CLI or another entry point by constructing `ORE(NewReasoner(...))`.

- **Add tools or memory**
  - Extend `ORE.execute` to:
    - Maintain a list of `Message` objects across turns.
    - Insert tool call responses or memory as additional `Message` instances.
  - Keep `Reasoner` focused on “given messages → model call → Response”.

- **Add richer CLI commands**
  - Enhance `ore.cli`:
    - New flags for multi-turn sessions, streaming, or different personas.
    - Options for choosing backends (`--backend ollama`, `--backend remote`).

