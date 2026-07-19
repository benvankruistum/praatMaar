"""Tests voor module registry config."""

from __future__ import annotations

from modules._builtin.inbox_mirror import InboxMirrorModule
from modules.registry import load_enabled_modules, module_enabled, sanitize_modules_config


def test_sanitize_modules_config_ignores_unknown() -> None:
    raw = {"inbox-mirror": {"enabled": False}, "unknown": {"enabled": True}}
    assert sanitize_modules_config(raw) == {"inbox-mirror": {"enabled": False}}


def test_module_enabled_uses_default_when_missing() -> None:
    module = InboxMirrorModule()
    assert module_enabled(module, {}) is True


def test_load_enabled_modules_respects_config(tmp_path, monkeypatch) -> None:
    import host

    monkeypatch.setattr(host, "app_dir", lambda: tmp_path)
    modules = load_enabled_modules({"inbox-mirror": {"enabled": False}})
    assert modules == []
