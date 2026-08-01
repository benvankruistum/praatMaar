from __future__ import annotations

from PySide6.QtWidgets import QApplication

from indicator import RecordingState, notify_state
from indicator._contract import drain_status_queue
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


def test_indicator_applies_preparing_and_error_hint() -> None:
    app = ensure_app([])
    drain_status_queue()
    indicator = RecordingIndicator()
    indicator.run()

    notify_state(RecordingState.PREPARING, "toggle", hint="Mic openen…")
    indicator._tick()
    assert indicator._state == RecordingState.PREPARING
    assert indicator._status_hint == "Mic openen…"

    notify_state(RecordingState.ERROR, "toggle", hint="Controleer microfoon in Instellingen")
    indicator._tick()
    assert indicator._state == RecordingState.ERROR
    assert indicator._status_hint == "Controleer microfoon in Instellingen"

    notify_state(RecordingState.IDLE, "toggle")
    indicator._tick()
    assert indicator._state == RecordingState.IDLE
    assert indicator._status_hint == ""

    indicator.destroy()
    assert QApplication.instance() is app


def test_indicator_ready_cue_shows_then_hides_without_destination() -> None:
    app = ensure_app([])
    indicator = RecordingIndicator()
    indicator.set_hotkey_label("Ctrl + Space")
    indicator.show_ready_cue(duration_ms=50)
    assert indicator._ready_cue_active
    assert indicator.isVisible()

    indicator._hide_timer.timeout.emit()
    assert not indicator._ready_cue_active
    assert not indicator.isVisible()

    indicator.destroy()
    assert QApplication.instance() is app
