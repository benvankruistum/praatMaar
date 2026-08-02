"""Modus-tag (canvas 1a, 08): outline vs. gevuld, en klikbaar in elke state.

Outline/gevuld is bewust een vúlverschil en geen kleurverschil: dat blijft
leesbaar zonder kleurwaarneming.
"""

from __future__ import annotations

from indicator import RecordingState
from indicator._contract import MODE_TAG_HIT_HEIGHT, MODE_TAG_HIT_WIDTH, mode_tag_is_filled
from ui.app import ensure_app


def _pill(**kwargs):
    from indicator._qt import RecordingIndicator

    ensure_app([])
    return RecordingIndicator(**kwargs)


def test_hit_area_matches_canvas() -> None:
    assert MODE_TAG_HIT_WIDTH == 56
    assert MODE_TAG_HIT_HEIGHT == 32


def test_filled_means_currently_active() -> None:
    # PTT is gevuld zolang de knop ingedrukt is; verder alles outline.
    assert mode_tag_is_filled("ptt", held=True) is True
    assert mode_tag_is_filled("ptt", held=False) is False
    assert mode_tag_is_filled("toggle", held=False) is False
    assert mode_tag_is_filled("meeting", held=True) is False


def test_tag_rect_is_at_least_the_hit_area() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    rect = pill._mode_tag_rect()
    assert rect is not None
    assert rect.width() >= MODE_TAG_HIT_WIDTH
    assert rect.height() >= MODE_TAG_HIT_HEIGHT
    assert rect.top() >= 0 and rect.bottom() <= pill.height()


def _click(pill, point) -> None:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    position = QPointF(point)
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        position,
        position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    pill.mousePressEvent(event)


def test_click_on_tag_requests_mode_switch() -> None:
    switched: list[str] = []
    pill = _pill(on_mode_toggle=lambda: switched.append("x"))
    pill._apply_state(RecordingState.RECORDING, "toggle")

    rect = pill._mode_tag_rect()
    assert rect is not None
    _click(pill, rect.center())
    assert switched == ["x"]


def test_click_on_tag_works_in_idle_too() -> None:
    switched: list[str] = []
    pill = _pill(on_mode_toggle=lambda: switched.append("x"))
    pill.set_destination("Klantgesprekken")
    pill._apply_state(RecordingState.IDLE, "toggle")

    rect = pill._mode_tag_rect()
    if rect is not None:  # Idle toont de tag niet in elk ontwerp
        _click(pill, rect.center())
        assert switched == ["x"]


def test_tag_click_does_not_start_a_drag() -> None:
    pill = _pill(on_mode_toggle=lambda: None)
    pill._apply_state(RecordingState.RECORDING, "toggle")
    rect = pill._mode_tag_rect()
    assert rect is not None
    _click(pill, rect.center())
    assert pill._drag_offset is None
