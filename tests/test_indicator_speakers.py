"""Sprekerschakelaar op de pill: 32×32, klik zonder slepen."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from indicator import RecordingState
from indicator._qt import SPEAKER_BUTTON_SIZE, RecordingIndicator
from ui.app import ensure_app


def _pill(**kwargs):
    ensure_app([])
    return RecordingIndicator(**kwargs)


def _click(pill, point) -> None:
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


def test_speaker_button_is_at_least_32_and_clickable_while_idle() -> None:
    toggled: list[str] = []
    pill = _pill(on_speakers_toggle=lambda: toggled.append("x"))
    pill._apply_state(RecordingState.IDLE, "toggle")

    rect = pill._speakers_rect()
    assert rect is not None
    assert rect.width() >= SPEAKER_BUTTON_SIZE
    assert rect.height() >= SPEAKER_BUTTON_SIZE

    _click(pill, rect.center())
    assert toggled == ["x"]
    assert pill._drag_offset is None


def test_recording_speaker_chip_stays_clear_of_stop() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    speakers = pill._speakers_rect()
    stop = pill._stop_rect()
    from indicator._qt import _ACTION_SIZE

    assert speakers is not None
    # Tijdens opnemen alleen het icoon, kleiner dan de idle-chip, zonder "Sprekers".
    assert speakers.width() == _ACTION_SIZE
    assert speakers.height() == _ACTION_SIZE
    assert speakers.right() < stop.left()
    assert abs(speakers.center().y() - stop.center().y()) <= 1


def test_speaker_button_hidden_on_error() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.ERROR, "toggle")
    assert pill._speakers_rect() is None


def test_idle_action_and_destination_fit_beside_speaker_label() -> None:
    from PySide6.QtGui import QFontMetrics

    pill = _pill()
    pill.set_hotkey_label("Option + Command (Win)")
    pill.set_destination("Klantgesprekken")
    pill._apply_state(RecordingState.IDLE, "toggle")

    speakers = pill._speakers_rect()
    assert speakers is not None
    assert speakers.width() > SPEAKER_BUTTON_SIZE
    right_limit = speakers.left() - 10
    title_w = QFontMetrics(pill._font(14, bold=True)).horizontalAdvance("Dicteer")
    assert right_limit - 40 >= title_w
    name_w = QFontMetrics(pill._font(11)).horizontalAdvance("Klantgesprekken")
    assert right_limit - 40 >= name_w


def test_idle_without_destination_puts_record_on_the_right_edge() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.IDLE, "toggle")
    record = pill._record_rect()
    assert record.right() == pill._dismiss_rect().right()


def test_filled_follows_enabled_flag() -> None:
    pill = _pill()
    assert pill._speakers_enabled is False
    pill.set_speakers_enabled(True)
    assert pill._speakers_enabled is True
