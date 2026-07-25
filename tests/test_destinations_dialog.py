"""Behaviour tests for the Qt destinations dialog (canvas #3a)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from PySide6.QtWidgets import QRadioButton

import destinations
from ui.app import ensure_app
from ui.dialogs.destinations import DestinationEditor, DestinationsDialog


def _app() -> None:
    ensure_app([])


def _current(*names: str, active: str | None = None) -> dict[str, Any]:
    return {
        "destinations": [
            {
                "name": name,
                "path": f"D:\\Werk\\{name}",
                "auto_paste": False,
                "file_mode": destinations.FILE_MODE_NEW,
                "append_file": "",
            }
            for name in names
        ],
        "active_destination": active,
    }


# --- DestinationEditor ------------------------------------------------------


def test_editor_uses_radiobuttons_for_mode() -> None:
    _app()
    editor = DestinationEditor(None, "Toevoegen", "Toevoegen")
    assert isinstance(editor.mode_new, QRadioButton)
    assert isinstance(editor.mode_append, QRadioButton)


def test_editor_append_field_hidden_for_new_mode() -> None:
    _app()
    editor = DestinationEditor(None, "Toevoegen", "Toevoegen")
    editor.mode_new.setChecked(True)
    assert editor.append_group.isHidden()


def test_editor_append_field_shown_for_append_mode() -> None:
    _app()
    editor = DestinationEditor(None, "Toevoegen", "Toevoegen")
    editor.mode_append.setChecked(True)
    assert not editor.append_group.isHidden()


def test_editor_empty_name_shows_inline_error_not_messagebox() -> None:
    _app()
    editor = DestinationEditor(None, "Toevoegen", "Toevoegen")
    editor.path.setText("D:\\Werk\\X")
    with patch("PySide6.QtWidgets.QMessageBox.warning") as warn:
        editor.attempt_accept()
    assert warn.call_count == 0
    assert editor.result is None
    assert not editor.name_error.isHidden()


def test_editor_name_collision_shows_inline_error() -> None:
    _app()
    siblings = _current("Notulen Q3")["destinations"]
    editor = DestinationEditor(None, "Toevoegen", "Toevoegen", siblings=siblings)
    editor.name.setText("notulen q3")
    editor.path.setText("D:\\Werk\\X")
    with patch("PySide6.QtWidgets.QMessageBox.warning") as warn:
        editor.attempt_accept()
    assert warn.call_count == 0
    assert editor.result is None
    assert not editor.name_error.isHidden()


def test_editor_valid_input_returns_result() -> None:
    _app()
    editor = DestinationEditor(None, "Toevoegen", "Toevoegen")
    editor.name.setText("Klant Bergman")
    editor.path.setText("D:\\Werk\\Bergman")
    editor.attempt_accept()
    assert editor.result is not None
    assert editor.result["name"] == "Klant Bergman"
    assert editor.result["file_mode"] == destinations.FILE_MODE_NEW


# --- DestinationsDialog -----------------------------------------------------


def test_empty_state_visible_without_custom_destinations() -> None:
    _app()
    dialog = DestinationsDialog(None, _current(), lambda _s: None)
    assert not dialog.empty_state.isHidden()


def test_empty_state_hidden_with_custom_destinations() -> None:
    _app()
    dialog = DestinationsDialog(None, _current("Notulen Q3"), lambda _s: None)
    assert dialog.empty_state.isHidden()


def test_active_custom_row_shows_active_pill() -> None:
    _app()
    dialog = DestinationsDialog(None, _current("Notulen Q3", active="Notulen Q3"), lambda _s: None)
    assert dialog.active_pill is not None


def test_selecting_default_disables_edit_delete_and_shows_hint() -> None:
    _app()
    dialog = DestinationsDialog(None, _current("Notulen Q3"), lambda _s: None)
    dialog.select_default()
    assert not dialog.edit_button.isEnabled()
    assert not dialog.delete_button.isEnabled()
    assert not dialog.default_hint.isHidden()


def test_selecting_custom_enables_edit_delete() -> None:
    _app()
    dialog = DestinationsDialog(None, _current("Notulen Q3"), lambda _s: None)
    dialog.select_custom(0)
    assert dialog.edit_button.isEnabled()
    assert dialog.delete_button.isEnabled()
    assert dialog.default_hint.isHidden()


def test_set_active_and_save_persists_active() -> None:
    _app()
    captured: dict[str, Any] = {}
    dialog = DestinationsDialog(None, _current("Notulen Q3"), lambda s: captured.update(s))
    dialog.select_custom(0)
    dialog._set_active()
    dialog._save()
    assert captured["active_destination"] == "Notulen Q3"


def test_delete_custom_clears_active_and_shows_empty_state() -> None:
    _app()
    dialog = DestinationsDialog(None, _current("Notulen Q3", active="Notulen Q3"), lambda _s: None)
    dialog.select_custom(0)
    dialog._delete()
    assert dialog._active is None
    assert not dialog.empty_state.isHidden()
