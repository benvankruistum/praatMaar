"""Klembord-helpers (extract uit dictation)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


def copy_to_clipboard(
    text: str,
    *,
    pyperclip_mod: Any | None,
    ui_dispatch: Callable[[Callable[[], None]], None],
) -> None:
    """Kopieert tekst naar het klembord (pyperclip, anders Qt-fallback)."""

    try:
        if pyperclip_mod is not None:
            pyperclip_mod.copy(text)
            return
    except Exception:
        pass
    copy_to_clipboard_via_qt(text, ui_dispatch=ui_dispatch)


def copy_to_clipboard_via_qt(
    text: str,
    *,
    ui_dispatch: Callable[[Callable[[], None]], None],
) -> None:
    """Best-effort klembord-fallback via Qt (thread-veilig gemarshald)."""

    from PySide6.QtCore import QThread
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("Geen Qt-applicatie voor klembord-fallback.")

    def _set() -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    if QThread.currentThread() == app.thread():
        _set()
        return
    done = threading.Event()

    def _run() -> None:
        try:
            _set()
        finally:
            done.set()

    ui_dispatch(_run)
    done.wait(timeout=1.0)
