"""Opname-state (canvas 1a, 04): looptijd, stopknop en waveform-maten."""

from __future__ import annotations

from PySide6.QtGui import QImage, QPainter

from indicator import RecordingState, set_chunk_leds_enabled, signal_chunk_trigger
from indicator._contract import (
    INDICATOR_HEIGHT,
    NUM_BARS,
    STOP_BUTTON_SIZE,
    WAVEFORM_BAR_MAX_HEIGHT,
    WAVEFORM_BAR_WIDTH,
    elapsed_label,
)
from indicator._qt import _CHUNK_LED_GAP, _CHUNK_LED_SIZE
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


def _paint_chunk_leds_at(pill, right_x: int) -> int:
    image = QImage(INDICATOR_HEIGHT * 8, INDICATOR_HEIGHT, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        return pill._paint_chunk_leds(painter, right_x)
    finally:
        painter.end()
        set_chunk_leds_enabled(False)


def test_chunk_leds_hidden_when_module_off() -> None:
    pill = _pill()
    set_chunk_leds_enabled(False)
    assert _paint_chunk_leds_at(pill, 200) == 200


def test_chunk_leds_reserve_icon_width_not_letters() -> None:
    """Incrementele knip-LED’s zijn ruit + stopwatch, geen V/T-letters."""

    import inspect

    from indicator._qt import RecordingIndicator

    source = inspect.getsource(RecordingIndicator._paint_chunk_leds)
    helpers = inspect.getsource(RecordingIndicator._paint_chunk_led_diamond) + inspect.getsource(
        RecordingIndicator._paint_chunk_led_clock
    )
    assert "drawText" not in source and "drawText" not in helpers
    assert '"V"' not in source and '"T"' not in source

    pill = _pill()
    set_chunk_leds_enabled(True)
    left = _paint_chunk_leds_at(pill, 200)
    expected = int(_CHUNK_LED_SIZE + _CHUNK_LED_GAP + _CHUNK_LED_SIZE)
    assert 200 - left == expected


def test_chunk_leds_paint_when_lit() -> None:
    pill = _pill()
    set_chunk_leds_enabled(True)
    signal_chunk_trigger("vad")
    signal_chunk_trigger("fixed")
    left = _paint_chunk_leds_at(pill, 200)
    assert left < 200
