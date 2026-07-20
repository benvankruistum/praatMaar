"""Tests voor module registry config."""

from __future__ import annotations

from modules._builtin.inbox_mirror import InboxMirrorModule
from modules.registry import (
    all_builtin_modules,
    load_enabled_modules,
    module_enabled,
    sanitize_modules_config,
)


def test_sanitize_modules_config_ignores_unknown() -> None:
    raw = {"inbox-mirror": {"enabled": False}, "unknown": {"enabled": True}}
    assert sanitize_modules_config(raw) == {"inbox-mirror": {"enabled": False}}


def test_module_enabled_uses_default_when_missing() -> None:
    module = InboxMirrorModule()
    assert module_enabled(module, {}) is True


def test_load_enabled_modules_respects_config(tmp_path, monkeypatch) -> None:
    import host

    monkeypatch.setattr(host, "app_dir", lambda: tmp_path)
    modules = load_enabled_modules(
        {
            "inbox-mirror": {"enabled": False},
            "audio-capture": {"enabled": False},
            "speech-to-text": {"enabled": False},
        }
    )
    assert modules == []


def test_audio_capture_is_a_builtin_module() -> None:
    assert "audio-capture" in {module.id for module in all_builtin_modules()}


def test_speech_to_text_is_a_builtin_module() -> None:
    assert "speech-to-text" in {module.id for module in all_builtin_modules()}
