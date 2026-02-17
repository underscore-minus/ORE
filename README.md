# ORE

**Orchestrated Reasoning Engine** — minimal Input → Reasoner → Output loop with [Ollama](https://ollama.com).

## Quick start

```bash
# Clone and enter
git clone https://github.com/underscore-minus/ORE.git && cd ORE

# Setup (Python 3.10)
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run (Ollama must be running; pull a model first: ollama pull llama2)
python main.py "Explain the concept of an irreducible loop."
```

## Commands

| Command | Description |
|--------|-------------|
| `python main.py "Your question"` | Ask Aya (auto-picks a model) |
| `python main.py --interactive` or `-i` | Interactive loop (REPL); each turn stateless |
| `python main.py --list-models` | List installed Ollama models |
| `python main.py "Question" --model llama3.2` | Use a specific model |

## Layout

- `ore/` — core package (`types`, `reasoner`, `core`, `cli`, `models`)
- `main.py` — entry point

v0.2 adds an interactive loop; still stateless (no message history, no memory, no tools). Aya’s persona is stored in `ore/prompts/aya.txt` and injected by the orchestrator in `ore/core.py`.
