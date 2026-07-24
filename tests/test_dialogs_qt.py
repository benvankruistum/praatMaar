"""Qt dialog smoke tests for the compatibility facades."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from destinations_dialog import open_destinations_dialog
from help_dialog import open_help
from modules_dialog import open_modules_dialog
from settings import open_settings_dialog
from ui.app import ensure_app


def _close_dialogs() -> None:
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()


def test_dialog_facades_accept_no_parent() -> None:
    ensure_app([])
    open_settings_dialog(None, {}, lambda _settings: None)
    open_destinations_dialog(None, {}, lambda _settings: None)
    open_modules_dialog(None, {}, lambda _settings: None)
    open_help(None)
    assert len(QApplication.topLevelWidgets()) >= 4
    _close_dialogs()
