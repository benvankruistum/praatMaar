"""Tests for local-llm Ollama client helpers and semantic analysis provider."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules._builtin.local_llm.ollama_client import OllamaClient, OllamaError
from modules._builtin.local_llm.provider import OllamaSemanticAnalysis
from modules.capabilities.semantic_analysis import (
    CAPABILITY_ID,
    CONTRACT_VERSION,
    KIND_AGENDA_REVIEW,
    KIND_RUNNING_SUMMARY,
    AnalysisRequest,
)
from modules.registry import all_builtin_modules


def test_semantic_analysis_contract_ids() -> None:
    assert CAPABILITY_ID == "ai.semantic_analysis"
    assert CONTRACT_VERSION == 2
    assert KIND_RUNNING_SUMMARY == "running_summary"
    assert KIND_AGENDA_REVIEW == "agenda_review"


def test_local_llm_in_builtin_registry() -> None:
    ids = [module.id for module in all_builtin_modules()]
    assert "local-llm" in ids
    module = next(m for m in all_builtin_modules() if m.id == "local-llm")
    assert module.default_enabled() is False


def test_ollama_has_model(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OllamaClient("http://127.0.0.1:11434")

    def fake_tags() -> list[str]:
        return ["qwen2.5:7b", "llama3.2:3b"]

    monkeypatch.setattr(client, "tags", fake_tags)
    assert client.has_model("qwen2.5:7b") is True
    assert client.has_model("missing") is False


def test_provider_running_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.has_model.return_value = True
    client.chat.return_value = "Korte samenvatting van de meeting."
    provider = OllamaSemanticAnalysis(client, model="qwen2.5:7b")
    assert provider.is_ready() is True
    result = provider.analyze(
        AnalysisRequest(
            kind=KIND_RUNNING_SUMMARY,
            transcript="We bespraken het budget.",
            previous_summary=None,
            language="nl",
        )
    )
    assert result.kind == KIND_RUNNING_SUMMARY
    assert "samenvatting" in result.text.lower()
    client.chat.assert_called_once()


def test_provider_rejects_unknown_kind() -> None:
    provider = OllamaSemanticAnalysis(MagicMock(), model="qwen2.5:7b")
    with pytest.raises(ValueError, match="Onbekend"):
        provider.analyze(AnalysisRequest(kind="nope", transcript="x"))


def test_ollama_error_on_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OllamaClient("http://127.0.0.1:9")

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"not-json"

    monkeypatch.setattr(
        "modules._builtin.local_llm.ollama_client.urllib.request.urlopen",
        lambda *a, **k: FakeResp(),
    )
    with pytest.raises(OllamaError):
        client.tags()
