"""Opname-state (canvas 1a, 04): looptijd, stopknop en waveform-maten."""

from __future__ import annotations

from indicator import RecordingState
from indicator._contract import (
    INDICATOR_HEIGHT,
    NUM_BARS,
    STOP_BUTTON_SIZE,
    WAVEFORM_BAR_MAX_HEIGHT,
    WAVEFORM_BAR_WIDTH,
    elapsed_label,
)
from ui.app import ensure_app


def test_elapsed_label_formats_minutes_and_seconds() -> None:
    assert elapsed_label(0) == "00:00"
    assert elapsed_label(42) == "00:42"
    assert elapsed_label(62) == "01:02"
    assert elapsed_label(3599) == "59:59"


def test_elapsed_label_shows_hours_when_needed() -> None:
    assert elapsed_label(3600) == "1:00:00"
    assert elapsed_label(3661) == "1:01:01"


def test_elapsed_label_clamps_negative() -> None:
    assert elapsed_label(-5) == "00:00"


def test_waveform_matches_canvas_dimensions() -> None:
    # Canvas: 18 staven, 3 px breed, max 24 px hoog.
    assert NUM_BARS == 18
    assert WAVEFORM_BAR_WIDTH == 3.0
    assert WAVEFORM_BAR_MAX_HEIGHT == 24.0


def test_stop_button_is_36_and_fits_the_capsule() -> None:
    assert STOP_BUTTON_SIZE == 36
    assert STOP_BUTTON_SIZE <= INDICATOR_HEIGHT


def _pill():
    from indicator._qt import RecordingIndicator

    ensure_app([])
    return RecordingIndicator()


def test_stop_rect_uses_stop_button_size() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.RECORDING, "toggle")
    rect = pill._stop_rect()
    assert rect.width() == STOP_BUTTON_SIZE
    assert rect.height() == STOP_BUTTON_SIZE
    # Verticaal gecentreerd in de capsule.
    assert abs(rect.center().y() - INDICATOR_HEIGHT // 2) <= 1
    # En binnen de capsule.
    assert rect.top() >= 0 and rect.bottom() <= INDICATOR_HEIGHT


def test_dismiss_rect_stays_32() -> None:
    # Canvas 11: dismiss blijft 32×32; alleen de stopknop groeit naar 36.
    pill = _pill()
    pill._apply_state(RecordingState.IDLE, "toggle")
    assert pill._dismiss_rect().width() == 32


def test_recording_tracks_elapsed_seconds() -> None:
    pill = _pill()
    pill._apply_state(RecordingState.IDLE, "toggle")
    assert pill._elapsed_seconds() == 0

    pill._apply_state(RecordingState.RECORDING, "toggle")
    # Meteen na start staat de teller op 0 en loopt hij vanaf dat moment.
    assert pill._elapsed_seconds() == 0
    pill._recording_started_at -= 42.0
    assert pill._elapsed_seconds() == 42

    # Buiten de opname is er geen looptijd.
    pill._apply_state(RecordingState.TRANSCRIBING, "toggle")
    assert pill._elapsed_seconds() == 0
