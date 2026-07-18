"""Tests voor Tk-keysym → token (macOS Instellingen-opname / PC-boards)."""

from __future__ import annotations

import hotkeys


def test_tk_win_key_as_cmd() -> None:
    assert hotkeys.tk_keysym_to_token("Super_L") == "cmd"
    assert hotkeys.tk_keysym_to_token("Meta_L") == "cmd"
    assert hotkeys.tk_keysym_to_token("Win_L") == "cmd"


def test_tk_modifiers_and_space() -> None:
    assert hotkeys.tk_keysym_to_token("Control_L") == "ctrl"
    assert hotkeys.tk_keysym_to_token("Alt_R") == "alt"
    assert hotkeys.tk_keysym_to_token("space") == "space"
    assert hotkeys.tk_keysym_to_token("a") == "a"
    assert hotkeys.tk_keysym_to_token("F5") == "f5"


def test_tk_event_modifier_bits() -> None:
    # Shift + Control + Mod1(Alt) + Super
    state = 0x0001 | 0x0004 | 0x0008 | 0x0040
    mods = hotkeys.tk_event_modifier_tokens(state)
    assert mods == {"shift", "ctrl", "alt", "cmd"}


def test_format_mac_cmd_mentions_win(monkeypatch) -> None:
    monkeypatch.setattr(hotkeys.sys, "platform", "darwin")
    label = hotkeys.format_hotkey(["cmd", "space"])
    assert "Win" in label
    assert "Spatie" in label
