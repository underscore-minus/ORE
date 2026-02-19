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

## Layout

- `ore/` — core package (`types`, `reasoner`, `core`, `cli`, `models`, `store`)
- `main.py` — entry point

`--conversational` / `-c` enables a session-aware REPL; prior turns are visible to the reasoner via an explicit `Session`. `--save-session` and `--resume-session` (v0.4) add opt-in persistence to `~/.ore/sessions/`. Without these flags, behaviour is stateless. Aya's persona is stored in `ore/prompts/aya.txt` and injected by the orchestrator in `ore/core.py`.
