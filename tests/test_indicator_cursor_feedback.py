"""Cursor- en hover-feedback (canvas 1a, 10-13).

Sleep-snap is bewust niet geïmplementeerd: de pill blijft exact waar je hem
laat (keuze van de gebruiker, afwijkend van het canvas).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from indicator import RecordingState
from ui.app import ensure_app


def _pill(**kwargs):
    from indicator._qt import RecordingIndicator

    ensure_app([])
    return RecordingIndicator(**kwargs)


def _move(pill, point) -> None:
    from PySide6.QtCore import QEvent

    position = QPointF(point)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        position,
        position,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    pill.mouseMoveEvent(event)


def test_body_uses_open_hand_cursor() -> None:
    pill = _pill()
    pill.set_destination("Klantgesprekken")
    pill._apply_state(RecordingState.IDLE, "toggle")
    # Midden-links is body: daar sleep je de pill.
    _move(pill, QPointF(60.0, 30.0))
    assert pill.cursor().shape() == Qt.CursorShape.OpenHandCursor


def test_buttons_use_arrow_cursor() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    stop = pill._stop_rect()
    _move(pill, QPointF(stop.center()))
    assert pill.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_mode_tag_uses_arrow_cursor() -> None:
    pill = _pill(on_mode_toggle=lambda: None)
    pill._apply_state(RecordingState.RECORDING, "toggle")
    tag = pill._mode_tag_rect()
    assert tag is not None
    _move(pill, QPointF(tag.center()))
    assert pill.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_hover_marks_the_control_for_brighter_paint() -> None:
    # Canvas: +6% helderheid op de knopvulling bij hover, geen schaal-animatie.
    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    assert pill._hovered_control is None

    stop = pill._stop_rect()
    _move(pill, QPointF(stop.center()))
    assert pill._hovered_control == "control"

    _move(pill, QPointF(60.0, 30.0))
    assert pill._hovered_control is None


def test_leaving_the_pill_clears_hover() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    _move(pill, QPointF(pill._stop_rect().center()))
    assert pill._hovered_control is not None
    pill.leaveEvent(None)
    assert pill._hovered_control is None


def test_dragging_still_works_from_the_body() -> None:
    # Cursor-feedback mag het slepen niet in de weg zitten.
    from PySide6.QtCore import QEvent

    pill = _pill()
    pill.set_destination("Klantgesprekken")
    pill._apply_state(RecordingState.IDLE, "toggle")
    position = QPointF(60.0, 30.0)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        position,
        position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    pill.mousePressEvent(press)
    assert pill._drag_offset is not None


def test_hover_brightens_the_control_fill() -> None:
    from indicator._contract import COLOR_RECORDING

    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    base = pill._control_fill(COLOR_RECORDING)
    _move(pill, QPointF(pill._stop_rect().center()))
    hovered = pill._control_fill(COLOR_RECORDING)
    assert hovered.lightness() > base.lightness()
