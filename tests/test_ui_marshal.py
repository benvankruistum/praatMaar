"""ui_dispatch marshalt callbacks altijd naar de Qt-main-thread."""

from __future__ import annotations

import threading

from ui.app import ensure_app


def _flush(app) -> None:
    for _ in range(5):
        app.processEvents()


def _reset_invoker() -> None:
    import ui.marshal as marshal

    marshal._invoker = None


def test_first_dispatch_from_worker_thread_runs_on_main_thread() -> None:
    # Regression: een lazy _Invoker die op een workerthread wordt aangemaakt
    # krijgt affiniteit met die thread (zonder event loop) — callbacks
    # verdwijnen dan stil. De invoker moet altijd op de GUI-thread landen.
    from PySide6.QtCore import QThread

    from ui.marshal import ui_dispatch

    app = ensure_app([])
    _reset_invoker()

    ran_on: list[QThread] = []

    def dispatch_from_worker() -> None:
        ui_dispatch(lambda: ran_on.append(QThread.currentThread()))

    worker = threading.Thread(target=dispatch_from_worker)
    worker.start()
    worker.join(timeout=5)

    _flush(app)
    assert ran_on, "callback is nooit uitgevoerd"
    assert ran_on[0] is app.thread()


def test_failing_callback_does_not_block_next_dispatch() -> None:
    from ui.marshal import ui_dispatch

    app = ensure_app([])
    _reset_invoker()

    ran: list[str] = []

    def boom() -> None:
        raise RuntimeError("kapot")

    ui_dispatch(boom)
    ui_dispatch(lambda: ran.append("ok"))
    _flush(app)
    assert ran == ["ok"]
