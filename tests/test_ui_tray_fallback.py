"""The Qt tray remains usable when a desktop tray is unavailable."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtWidgets import QSystemTrayIcon

from ui.app import ensure_app
from ui.tray import TrayIcon


def test_tray_fallback_exposes_menu_and_state() -> None:
    ensure_app([])

    with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
        tray = TrayIcon(
            on_quit=lambda: None,
            on_settings=lambda: None,
            on_destinations=lambda: None,
            on_modules=lambda: None,
            on_help=lambda: None,
        )

    assert tray._fallback_window is not None
    tray.set_state(tray._state)
    tray.popup_menu(10, 10)
    tray.stop()
