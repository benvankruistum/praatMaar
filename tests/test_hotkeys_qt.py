"""Tests for translating Qt key events into persistent hotkey tokens."""

from __future__ import annotations

from PySide6.QtCore import Qt

from hotkeys import qt_key_to_token


def test_qt_key_to_token_maps_modifiers_and_special_keys() -> None:
    assert qt_key_to_token(Qt.Key.Key_Control) == "ctrl"
    assert qt_key_to_token(Qt.Key.Key_Shift) == "shift"
    assert qt_key_to_token(Qt.Key.Key_Alt) == "alt"
    assert qt_key_to_token(Qt.Key.Key_Meta) == "cmd"
    assert qt_key_to_token(Qt.Key.Key_Space) == "space"
    assert qt_key_to_token(Qt.Key.Key_Return) == "enter"


def test_qt_key_to_token_maps_letters_function_keys_and_punctuation() -> None:
    assert qt_key_to_token(Qt.Key.Key_A) == "a"
    assert qt_key_to_token(Qt.Key.Key_F5) == "f5"
    assert qt_key_to_token(Qt.Key.Key_BracketLeft) == "["
