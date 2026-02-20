# ORE

**Orchestrated Reasoning Engine** — minimal Input → Reasoner → Output loop with [Ollama](https://ollama.com).

## Quick start

```bash
# Clone and enter
git clone https://github.com/underscore-minus/ORE.git && cd ORE

# Setup (Python 3.10)
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run (Ollama must be running; pull a model first: ollama pull llama3.2)
python main.py "Explain the concept of an irreducible loop."
```

## Commands

| Command | Description |
|---------|-------------|
| `python main.py "Your question"` | Ask Aya (auto-picks a model) |
| `python main.py --interactive` or `-i` | Interactive REPL — each turn stateless |
| `python main.py --conversational` or `-c` | Conversational REPL — session in memory across turns |
| `python main.py --save-session NAME` | Conversational REPL, persist to ~/.ore/sessions/ after each turn |
| `python main.py --resume-session NAME` | Resume a saved session (implies conversational) |
| `python main.py --list-models` | List installed Ollama models |
| `python main.py "Question" --model llama3.2` | Use a specific model |
| `python main.py --stream` or `-s` | Stream output token-by-token (optional, any mode) |
| `python main.py --verbose` or `-v` | Show response metadata (ID, model, token counts) |
| `python main.py "Question" --json` or `-j` | Output structured JSON (single-turn only) |
| `echo "Question" \| python main.py` | Pipe a prompt via stdin |

## Layout

- `ore/` — core package (`types`, `reasoner`, `core`, `cli`, `models`, `store`)
- `tests/` — pytest suite (types, store, core, cli, reasoner, models)
- `main.py` — entry point
- `requirements.txt` — runtime deps; `requirements-dev.txt` — dev deps (pytest, black)

## Testing and CI

```bash
pip install -r requirements-dev.txt
pytest -v
black --check .   # enforce formatting
```

CI runs on push/PR to `main`: Python 3.10, `black --check`, then `pytest`. See `.github/workflows/ci.yml`.

---

`--conversational` / `-c` enables a session-aware REPL; prior turns are visible to the reasoner via an explicit `Session`. `--save-session` and `--resume-session` (v0.4) add opt-in persistence to `~/.ore/sessions/`. Without these flags, behaviour is stateless. v0.5 adds `--json` for structured output and stdin ingestion for piped prompts. Aya's persona is stored in `ore/prompts/aya.txt` and injected by the orchestrator in `ore/core.py`.
