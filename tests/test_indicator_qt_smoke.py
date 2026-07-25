from __future__ import annotations

from PySide6.QtWidgets import QApplication

from indicator._qt import RecordingIndicator
from ui.app import ensure_app


def test_indicator_schedules_calls_and_destroy_does_not_stop_app() -> None:
    app = ensure_app([])
    indicator = RecordingIndicator()
    called: list[str] = []

    indicator.call_on_main(lambda: called.append("called"))
    app.processEvents()

    assert called == ["called"]
    assert indicator.run() is None
    assert indicator._timer.isActive()

    indicator.destroy()

    assert QApplication.instance() is app
    assert indicator._timer is None
