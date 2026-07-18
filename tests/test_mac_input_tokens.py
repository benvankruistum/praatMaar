"""Tests voor mac_input keycode→token (geen AppKit nodig)."""

from __future__ import annotations

import hotkeys
from mac_input import MacKey, _token_for_keycode


def test_space_and_modifiers_keycodes() -> None:
    assert _token_for_keycode(0x31) == "space"
    assert _token_for_keycode(0x35) == "esc"
    assert _token_for_keycode(0x3B) == "ctrl"
    assert _token_for_keycode(0x38) == "shift"
    assert _token_for_keycode(0x3A) == "alt"
    assert _token_for_keycode(0x37) == "cmd"


def test_mackey_token_roundtrip() -> None:
    key = MacKey("space")
    assert hotkeys.key_to_token(key) == "space"
    assert hotkeys.key_to_token(MacKey("ctrl")) == "ctrl"
