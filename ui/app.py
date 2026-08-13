"""Application lifecycle helpers for the Qt UI."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ui.theme import apply_theme

_app: QApplication | None = None


def ensure_app(argv: list[str] | None = None) -> QApplication:
    """Return praatMaar's singleton ``QApplication``."""
    global _app
    existing = QApplication.instance()
    if existing is not None:
        _app = existing
        return existing

    _app = QApplication(argv if argv is not None else sys.argv)
    _app.setApplicationName("praatMaar")
    _app.setOrganizationName("praatMaar")
    # Tray-driven app: closing a dialog (or hiding the pill) must not quit the
    # process. Quitting happens only via the tray or an explicit request.
    _app.setQuitOnLastWindowClosed(False)
    apply_theme(_app)
    return _app
