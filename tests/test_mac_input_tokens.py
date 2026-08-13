"""Tests voor mac_input keycode→token (geen AppKit nodig)."""

from __future__ import annotations

import hotkeys
from mac_input import MacKey, _token_for_keycode, _token_from_characters


def test_space_and_modifiers_keycodes() -> None:
    assert _token_for_keycode(0x31) == "space"
    assert _token_for_keycode(0x35) == "esc"
    assert _token_for_keycode(0x3B) == "ctrl"
    assert _token_for_keycode(0x38) == "shift"
    assert _token_for_keycode(0x3A) == "alt"
    assert _token_for_keycode(0x37) == "cmd"


def test_arrows_and_iso_section() -> None:
    assert _token_for_keycode(0x7B) == "left"
    assert _token_for_keycode(0x7C) == "right"
    assert _token_for_keycode(0x0A) == "section"


def test_characters_fallback() -> None:
    assert _token_from_characters("A") == "a"
    assert _token_from_characters(" ") == "space"
    assert _token_from_characters("\uf702") == "left"  # NSLeftArrowFunctionKey


def test_mackey_token_roundtrip() -> None:
    key = MacKey("space")
    assert hotkeys.key_to_token(key) == "space"
    assert hotkeys.key_to_token(MacKey("ctrl")) == "ctrl"
    assert hotkeys.key_to_token(MacKey("kc12")) == "kc12"
