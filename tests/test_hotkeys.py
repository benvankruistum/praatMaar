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


def test_normalize_deduplicates() -> None:
    assert hotkeys.normalize(["ctrl", "ctrl", "a"]) == ["ctrl", "a"]


def test_format_hotkey_default_style() -> None:
    label = hotkeys.format_hotkey(hotkeys.DEFAULT_HOTKEY)
    assert label == "Ctrl + Shift + Alt + Spatie"


def test_format_hotkey_empty() -> None:
    assert hotkeys.format_hotkey([]) == "(geen)"


def test_format_hotkey_letter() -> None:
    assert hotkeys.format_hotkey(["ctrl", "r"]) == "Ctrl + R"
