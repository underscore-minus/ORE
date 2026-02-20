"""Tests for ore/models.py — model discovery and default selection with mocked Ollama."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ore.models import PREFERRED_MODELS, default_model, fetch_models


def _fake_client(model_names: list[str]) -> MagicMock:
    """Build a mock Client whose list() returns the given model names."""
    models = [SimpleNamespace(model=n) for n in model_names]
    client = MagicMock()
    client.list.return_value = SimpleNamespace(models=models)
    return client


class TestFetchModels:
    def test_returns_names(self):
        client = _fake_client(["llama3.2:latest", "mistral:latest"])
        with patch("ore.models.Client", return_value=client):
            names = fetch_models()
        assert names == ["llama3.2:latest", "mistral:latest"]

    def test_empty_when_no_models(self):
        client = _fake_client([])
        with patch("ore.models.Client", return_value=client):
            assert fetch_models() == []


class TestDefaultModel:
    def test_picks_preferred(self):
        client = _fake_client(["mistral:latest", "llama3.2:latest"])
        with patch("ore.models.Client", return_value=client):
            result = default_model()
        # llama3.2 is higher in PREFERRED_MODELS than mistral
        assert result == "llama3.2:latest"

    def test_falls_back_to_first(self):
        client = _fake_client(["some-obscure-model:latest"])
        with patch("ore.models.Client", return_value=client):
            result = default_model()
        assert result == "some-obscure-model:latest"

    def test_none_when_empty(self):
        client = _fake_client([])
        with patch("ore.models.Client", return_value=client):
            assert default_model() is None

    def test_preferred_order(self):
        # First preferred model should win even if listed after others
        all_models = [f"{name}:latest" for name in reversed(PREFERRED_MODELS)]
        client = _fake_client(all_models)
        with patch("ore.models.Client", return_value=client):
            result = default_model()
        assert result == f"{PREFERRED_MODELS[0]}:latest"
