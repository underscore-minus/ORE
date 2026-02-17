"""
Ollama model discovery: fetch available models from the local (or configured) server.
"""

from typing import List

from ollama import Client


# Preferred base names (no tag) in order when auto-choosing a default
PREFERRED_MODELS = ("llama3.2", "llama3.1", "llama3", "mistral", "llama2", "qwen2.5")


def fetch_models(host: str | None = None) -> List[str]:
    """
    Return full list of available Ollama model names as returned by the server
    (e.g. ['llama3.2:latest', 'mistral:latest']). Use these for --model and chat().
    """
    client = Client(host=host) if host else Client()
    resp = client.list()
    models = getattr(resp, "models", None) or []
    names = []
    for m in models:
        raw = getattr(m, "model", None)
        if raw and isinstance(raw, str):
            names.append(raw)
    return names


def default_model(host: str | None = None) -> str | None:
    """
    Pick a default model: first from PREFERRED_MODELS that is available, else first available.
    Returns the full model name (e.g. llama3.2:latest) for use with chat(). None if none installed.
    """
    available = fetch_models(host)
    if not available:
        return None
    # Build base name -> first full name (e.g. "llama3.2" -> "llama3.2:latest")
    base_to_full: dict[str, str] = {}
    for full in available:
        base = full.split(":")[0] if ":" in full else full
        if base not in base_to_full:
            base_to_full[base] = full
    for preferred in PREFERRED_MODELS:
        if preferred in base_to_full:
            return base_to_full[preferred]
    return available[0]
