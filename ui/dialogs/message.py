"""Small QMessageBox wrappers for module-facing notifications."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMessageBox, QWidget

from ui.app import ensure_app


def _parent(parent: Any) -> QWidget | None:
    return parent if isinstance(parent, QWidget) else None


def info(title: str, text: str, *, parent: Any = None) -> None:
    """Show an informational message dialog."""
    ensure_app()
    QMessageBox.information(_parent(parent), title, text)


def warning(title: str, text: str, *, parent: Any = None) -> None:
    """Show a warning message dialog."""
    ensure_app()
    QMessageBox.warning(_parent(parent), title, text)


def error(title: str, text: str, *, parent: Any = None) -> None:
    """Show an error message dialog.

    Alleen voor **expliciete** gebruikersacties (Instellingen, tray, modules).
    Automatische mic-/hotkey-fouten moeten ``dictation._report_user_error``
    gebruiken (tray attention + ERROR-pill), niet deze modal.
    """
    ensure_app()
    QMessageBox.critical(_parent(parent), title, text)
