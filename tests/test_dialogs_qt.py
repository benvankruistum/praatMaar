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


def test_tray_app_survives_closing_last_window() -> None:
    # A tray-driven app must not quit when a dialog (its last window) closes.
    app = ensure_app([])
    assert app.quitOnLastWindowClosed() is False


def test_dialog_facades_accept_no_parent() -> None:
    ensure_app([])
    open_settings_dialog(None, {}, lambda _settings: None)
    open_destinations_dialog(None, {}, lambda _settings: None)
    open_modules_dialog(None, {}, lambda _settings: None)
    open_help(None)
    assert len(QApplication.topLevelWidgets()) >= 4
    _close_dialogs()


def test_closing_dialog_schedules_deletion() -> None:
    # Regression: bij sluiten werd alleen de module-globale referentie gewist;
    # de C++-widgetboom bleef als kind van de pill bestaan tot app-exit
    # (N keer Instellingen openen = N dialoogbomen in het geheugen).
    from PySide6.QtCore import QCoreApplication, QEvent

    import ui.dialogs.settings as settings_mod
    from ui.dialogs.settings import SettingsDialog

    app = ensure_app([])
    _close_dialogs()
    open_settings_dialog(None, {}, lambda _settings: None)
    dialog = settings_mod._open_dialog
    assert isinstance(dialog, SettingsDialog)

    dialog.close()
    app.processEvents()
    assert settings_mod._open_dialog is None

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    import shiboken6

    assert not shiboken6.isValid(dialog), "dialoog moet na sluiten opgeruimd zijn"
