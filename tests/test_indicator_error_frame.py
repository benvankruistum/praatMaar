"""Mislukt-state (canvas 1a, 07): actieknop en hover-pauze."""

from __future__ import annotations

from indicator import RecordingState
from indicator._contract import ERROR_DURATION_MS
from ui.app import ensure_app


def _pill(**kwargs):
    from indicator._qt import RecordingIndicator

    ensure_app([])
    return RecordingIndicator(**kwargs)


def test_retry_button_only_in_error_state() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.IDLE, "toggle")
    assert pill._retry_rect() is None
    pill._apply_state(RecordingState.ERROR, "toggle", "Geen microfoon gevonden")
    rect = pill._retry_rect()
    assert rect is not None
    # Canvas 07: knop >= 32 px hoog en binnen de capsule.
    assert rect.height() >= 32
    assert rect.right() <= pill.width()
    assert rect.top() >= 0


def test_retry_click_invokes_callback() -> None:
    calls: list[int] = []
    pill = _pill(on_retry=lambda: calls.append(1))
    pill._apply_state(RecordingState.ERROR, "toggle", "Geen microfoon gevonden")

    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    rect = pill._retry_rect()
    assert rect is not None
    point = QPointF(rect.center())
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        point,
        point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    pill.mousePressEvent(event)
    assert calls == [1]


def test_retry_click_does_not_start_a_drag() -> None:
    pill = _pill(on_retry=lambda: None)
    pill._apply_state(RecordingState.ERROR, "toggle", "Geen microfoon gevonden")

    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    rect = pill._retry_rect()
    assert rect is not None
    point = QPointF(rect.center())
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        point,
        point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    pill.mousePressEvent(event)
    assert pill._drag_offset is None


def test_hover_pauses_the_auto_hide_timer() -> None:
    # Canvas 07: "timer pauzeert zolang de cursor boven de pill hangt".
    pill = _pill()
    pill._apply_state(RecordingState.ERROR, "toggle", "Geen microfoon gevonden")
    assert pill._hide_timer.isActive()

    pill.enterEvent(None)
    assert not pill._hide_timer.isActive(), "hover moet de auto-hide pauzeren"

    pill.leaveEvent(None)
    assert pill._hide_timer.isActive(), "verlaten moet de auto-hide hervatten"
    assert pill._hide_timer.interval() == ERROR_DURATION_MS


def test_hover_outside_transient_states_does_nothing() -> None:
    pill = _pill()
    pill.set_destination("Klantgesprekken")
    pill._apply_state(RecordingState.IDLE, "toggle")
    assert not pill._hide_timer.isActive()
    pill.enterEvent(None)
    pill.leaveEvent(None)
    assert not pill._hide_timer.isActive()
