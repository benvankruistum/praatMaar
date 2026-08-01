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
    assert label == "Control + Option + Command (Win) + Spatie"


def test_format_hotkey_win_cmd_as_win(monkeypatch) -> None:
    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    assert "Win" in hotkeys.format_hotkey(["cmd", "space"])


def test_keycode_escape_maps_to_esc_token() -> None:
    """Windows/pynput may deliver Esc as Key.esc on press and KeyCode(vk=27) on release."""
    from pynput.keyboard import Key, KeyCode

    hotkeys.init(__import__("pynput.keyboard", fromlist=["keyboard"]))
    assert hotkeys.key_to_token(Key.esc) == "esc"
    assert hotkeys.key_to_token(KeyCode.from_vk(27)) == "esc"


def test_keycode_space_maps_to_space_token() -> None:
    from pynput.keyboard import Key, KeyCode

    hotkeys.init(__import__("pynput.keyboard", fromlist=["keyboard"]))
    assert hotkeys.key_to_token(Key.space) == "space"
    assert hotkeys.key_to_token(KeyCode.from_vk(32)) == "space"


def test_shift_esc_release_via_vk_clears_pressed_set() -> None:
    """Regression: after Shift+Esc, Esc must leave pressed_tokens even if release is vk27."""
    from pynput.keyboard import Key, KeyCode

    hotkeys.init(__import__("pynput.keyboard", fromlist=["keyboard"]))
    pressed: set[str] = set()
    for key in (Key.shift, Key.esc):
        token = hotkeys.key_to_token(key)
        assert token is not None
        pressed.add(token)
    assert {"shift", "esc"}.issubset(pressed)
    # Release Esc as KeyCode (observed mismatch on Windows) then Shift.
    for key in (KeyCode.from_vk(27), Key.shift):
        token = hotkeys.key_to_token(key)
        assert token is not None
        pressed.discard(token)
    assert pressed == set()
    # Shift alone must not reconstitute the hotkey.
    pressed.add(hotkeys.key_to_token(Key.shift) or "")
    assert not {"shift", "esc"}.issubset(pressed)
