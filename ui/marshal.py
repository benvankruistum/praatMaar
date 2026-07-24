"""Schedule UI work on Qt's main thread."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal, Slot

from ui.app import ensure_app


class _Invoker(QObject):
    _requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._requested.connect(self._run, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _run(self, fn: object) -> None:
        assert callable(fn)
        fn()

    def dispatch(self, fn: Callable[[], None]) -> None:
        self._requested.emit(fn)


_invoker: _Invoker | None = None


def ui_dispatch(fn: Callable[[], None]) -> None:
    """Schedule ``fn`` on the Qt main thread."""
    ensure_app()
    global _invoker
    if _invoker is None:
        _invoker = _Invoker()
    _invoker.dispatch(fn)
