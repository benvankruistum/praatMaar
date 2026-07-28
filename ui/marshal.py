"""Schedule UI work on Qt's main thread."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal, Slot

from ui.app import ensure_app

log = logging.getLogger(__name__)


class _Invoker(QObject):
    _requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._requested.connect(self._run, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _run(self, fn: object) -> None:
        if not callable(fn):
            return
        try:
            fn()
        except Exception:
            # Eén falende callback mag de UI-dispatch-keten niet breken.
            log.exception("ui_dispatch-callback faalde")

    def dispatch(self, fn: Callable[[], None]) -> None:
        self._requested.emit(fn)


_invoker: _Invoker | None = None
_invoker_lock = threading.Lock()


def ui_dispatch(fn: Callable[[], None]) -> None:
    """Schedule ``fn`` on the Qt main thread."""
    app = ensure_app()
    global _invoker
    if _invoker is None:
        with _invoker_lock:
            if _invoker is None:
                invoker = _Invoker()
                # De eerste aanroep kan van een workerthread komen; zonder
                # verhuizing krijgt de invoker affiniteit met die thread
                # (zonder event loop) en verdwijnen callbacks stil.
                if invoker.thread() is not app.thread():
                    invoker.moveToThread(app.thread())
                _invoker = invoker
    _invoker.dispatch(fn)
