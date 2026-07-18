"""Tests voor hotkeys.normalize / format_hotkey (geen pynput nodig)."""

from __future__ import annotations

import hotkeys


def test_normalize_orders_modifiers_first() -> None:
    assert hotkeys.normalize(["space", "alt", "ctrl", "shift"]) == [
        "ctrl",
        "shift",
        "alt",
        "space",
    ]


def test_normalize_includes_cmd_modifier() -> None:
    assert hotkeys.normalize(["a", "cmd", "shift"]) == ["shift", "cmd", "a"]


def test_normalize_deduplicates() -> None:
    assert hotkeys.normalize(["ctrl", "ctrl", "a"]) == ["ctrl", "a"]


def test_format_hotkey_default_style() -> None:
    label = hotkeys.format_hotkey(hotkeys.DEFAULT_HOTKEY)
    assert "Spatie" in label
    assert "Shift" in label


def test_format_hotkey_empty() -> None:
    assert hotkeys.format_hotkey([]) == "(geen)"


def test_format_hotkey_letter() -> None:
    assert hotkeys.format_hotkey(["ctrl", "r"]).endswith("R")


def test_format_hotkey_mac_labels(monkeypatch) -> None:
    monkeypatch.setattr(hotkeys.sys, "platform", "darwin")
    label = hotkeys.format_hotkey(["ctrl", "alt", "cmd", "space"])
    assert label == "Control + Option + Command + Spatie"


def test_format_hotkey_win_cmd_as_win(monkeypatch) -> None:
    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    assert "Win" in hotkeys.format_hotkey(["cmd", "space"])
