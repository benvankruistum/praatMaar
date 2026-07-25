"""Tests for local-llm config endpoint modes and properties helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules._builtin.local_llm.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    ENDPOINT_MODE_BUNDLED,
    ENDPOINT_MODE_CUSTOM,
    LocalLlmConfigError,
    load_local_llm_config,
    save_local_llm_config,
    validate_base_url,
    validate_model_name,
)
from modules._builtin.local_llm.module import LocalLlmModule
from modules._builtin.local_llm.properties_dialog import (
    build_properties_result,
    show_properties_dialog,
)


def test_validate_base_url_accepts_http() -> None:
    assert validate_base_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    assert validate_base_url("https://ollama.lan:11434") == "https://ollama.lan:11434"


def test_validate_base_url_rejects_bad() -> None:
    with pytest.raises(LocalLlmConfigError, match="empty_url"):
        validate_base_url("  ")
    with pytest.raises(LocalLlmConfigError, match="invalid_url"):
        validate_base_url("not-a-url")
    with pytest.raises(LocalLlmConfigError, match="invalid_url"):
        validate_base_url("ftp://127.0.0.1:11434")


def test_validate_model_name() -> None:
    assert validate_model_name(" qwen2.5:32b ") == "qwen2.5:32b"
    with pytest.raises(LocalLlmConfigError, match="empty_model"):
        validate_model_name("")


def test_load_defaults_bundled(tmp_path: Path) -> None:
    cfg = load_local_llm_config(tmp_path)
    assert cfg["endpoint_mode"] == ENDPOINT_MODE_BUNDLED
    assert cfg["ollama_base_url"] == DEFAULT_BASE_URL
    assert cfg["ollama_model"] == DEFAULT_MODEL


def test_save_custom_and_reload(tmp_path: Path) -> None:
    save_local_llm_config(
        tmp_path,
        endpoint_mode=ENDPOINT_MODE_CUSTOM,
        ollama_base_url="http://192.168.1.10:11434",
        ollama_model="qwen2.5:32b",
    )
    cfg = load_local_llm_config(tmp_path)
    assert cfg["endpoint_mode"] == ENDPOINT_MODE_CUSTOM
    assert cfg["ollama_base_url"] == "http://192.168.1.10:11434"
    assert cfg["ollama_model"] == "qwen2.5:32b"
    assert cfg["custom_base_url"] == "http://192.168.1.10:11434"


def test_bundled_mode_uses_defaults_but_keeps_custom_stored(tmp_path: Path) -> None:
    save_local_llm_config(
        tmp_path,
        endpoint_mode=ENDPOINT_MODE_CUSTOM,
        ollama_base_url="http://10.0.0.2:11434",
        ollama_model="llama3.1:70b",
    )
    save_local_llm_config(tmp_path, endpoint_mode=ENDPOINT_MODE_BUNDLED)
    cfg = load_local_llm_config(tmp_path)
    assert cfg["endpoint_mode"] == ENDPOINT_MODE_BUNDLED
    assert cfg["ollama_base_url"] == DEFAULT_BASE_URL
    assert cfg["ollama_model"] == DEFAULT_MODEL
    assert cfg["custom_base_url"] == "http://10.0.0.2:11434"
    assert cfg["custom_model"] == "llama3.1:70b"


def test_build_properties_result_bundled_ignores_fields() -> None:
    result = build_properties_result(
        endpoint_mode=ENDPOINT_MODE_BUNDLED,
        base_url="http://evil.example:9",
        model="nope",
    )
    assert result.endpoint_mode == ENDPOINT_MODE_BUNDLED
    assert result.ollama_base_url == DEFAULT_BASE_URL
    assert result.ollama_model == DEFAULT_MODEL


def test_build_properties_result_custom_validates() -> None:
    result = build_properties_result(
        endpoint_mode=ENDPOINT_MODE_CUSTOM,
        base_url="http://127.0.0.1:11435/",
        model=" my-model ",
    )
    assert result.endpoint_mode == ENDPOINT_MODE_CUSTOM
    assert result.ollama_base_url == "http://127.0.0.1:11435"
    assert result.ollama_model == "my-model"


def test_module_exposes_properties_action() -> None:
    module = LocalLlmModule()
    ids = [action.id for action in module.actions()]
    assert ids[0] == "properties"
    assert "check_status" in ids


def test_show_properties_dialog_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDialog:
        def __init__(self, **_kwargs: object) -> None:
            self.result = None

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(
        "modules._builtin.local_llm.properties_dialog._PropertiesDialog",
        FakeDialog,
    )
    monkeypatch.setattr(
        "modules._builtin.local_llm.properties_dialog.ensure_app",
        lambda: None,
    )
    assert show_properties_dialog() is None
