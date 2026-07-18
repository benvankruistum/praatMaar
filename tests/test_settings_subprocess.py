"""Tests voor het macOS-instellingen-subprocess (geen echte GUI)."""

from __future__ import annotations

import json
from pathlib import Path

import settings_process


def test_run_settings_subprocess_reads_result(monkeypatch) -> None:
    saved = {
        "model": "small",
        "microphone_device": None,
        "auto_paste": True,
        "indicator_position": "boven-midden",
        "mode": "toggle",
        "hotkey": ["ctrl", "space"],
        "autostart": False,
    }

    def fake_run(cmd, env=None, check=False):  # noqa: ANN001
        out = Path(cmd[-1])
        out.write_text(json.dumps(saved), encoding="utf-8")
        return None

    monkeypatch.setattr(settings_process.subprocess, "run", fake_run)
    monkeypatch.setattr(settings_process.sys, "frozen", False, raising=False)

    result = settings_process.run_settings_subprocess({"model": "base"})
    assert result == saved


def test_run_settings_subprocess_cancel_returns_none(monkeypatch) -> None:
    def fake_run(cmd, env=None, check=False):  # noqa: ANN001
        return None

    monkeypatch.setattr(settings_process.subprocess, "run", fake_run)
    assert settings_process.run_settings_subprocess({"model": "base"}) is None


def test_run_settings_subprocess_frozen_argv(monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd, env=None, check=False):  # noqa: ANN001
        seen.append(list(cmd))
        return None

    monkeypatch.setattr(settings_process.subprocess, "run", fake_run)
    monkeypatch.setattr(settings_process.sys, "frozen", True, raising=False)
    monkeypatch.setattr(settings_process.sys, "executable", "/App/praatMaar")

    settings_process.run_settings_subprocess({"model": "base"})
    assert seen
    assert seen[0][0] == "/App/praatMaar"
    assert seen[0][1] == "--praatmaar-settings-ui"
