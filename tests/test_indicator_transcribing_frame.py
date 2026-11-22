"""Transcribeer-state (canvas 1a, 05): voortgangsbalk in de tekstkolom.

De chunk-teller uit het canvas ("chunk 3 van 5") is bewust niet geïmplementeerd:
geen van beide transcriptiepaden in opnamesessie.py kent parallelle chunks (het
dicteerpad doet één Whisper-run met segment-iteratie, het incrementele pad doet
al-klare deelteksten plus één staart). Zie .scratch/status-pill-verbeteringen/.
"""

from __future__ import annotations

from indicator import RecordingState
from indicator._contract import (
    INDICATOR_HEIGHT,
    PROGRESS_BAR_HEIGHT,
    set_transcription_progress,
)
from ui.app import ensure_app


def _pill():
    from indicator._qt import RecordingIndicator

    ensure_app([])
    return RecordingIndicator()


def test_progress_bar_is_four_px() -> None:
    assert PROGRESS_BAR_HEIGHT == 4


def test_progress_bar_rect_sits_in_the_text_column() -> None:
    pill = _pill()
    set_transcription_progress(62)
    pill._apply_state(RecordingState.TRANSCRIBING, "toggle")

    rect = pill._progress_bar_rect()
    assert rect is not None
    # Niet meer een draad over de volle breedte onderaan de capsule, maar een
    # balk in de tekstkolom: begint na de arc en eindigt vóór de rechterrand.
    assert rect.left() > 20
    assert rect.right() < pill.width()
    assert rect.height() == PROGRESS_BAR_HEIGHT
    # Zelfde strook als de waveform: bovenin, niet op de knoppenrij.
    assert rect.top() < INDICATOR_HEIGHT // 2
    assert rect.bottom() < pill._stop_rect().top()


def test_transcribing_follows_the_recording_grid() -> None:
    from indicator._qt import _ACTION_SIZE

    pill = _pill()
    set_transcription_progress(10)
    pill._apply_state(RecordingState.TRANSCRIBING, "toggle")

    speakers = pill._speakers_rect()
    tag = pill._mode_tag_rect()
    bar = pill._progress_bar_rect()
    assert speakers is not None and tag is not None and bar is not None
    assert speakers.width() == _ACTION_SIZE
    assert speakers.left() == pill._stop_rect().left()
    assert tag.right() < speakers.left()
    assert abs(tag.center().y() - speakers.center().y()) <= 8
    assert bar.bottom() < speakers.top()
    set_transcription_progress(None)


def test_no_progress_bar_without_percentage() -> None:
    # Onbekende duur: geen balk, alleen marching dots (indeterminate).
    pill = _pill()
    set_transcription_progress(None)
    pill._apply_state(RecordingState.TRANSCRIBING, "toggle")
    assert pill._progress_bar_rect() is None


def test_no_progress_bar_outside_transcribing() -> None:
    pill = _pill()
    set_transcription_progress(62)
    pill._apply_state(RecordingState.RECORDING, "toggle")
    assert pill._progress_bar_rect() is None
    set_transcription_progress(None)


def test_progress_fill_width_follows_percentage() -> None:
    pill = _pill()
    for percent in (0, 25, 100):
        set_transcription_progress(percent)
        pill._apply_state(RecordingState.TRANSCRIBING, "toggle")
        rect = pill._progress_bar_rect()
        assert rect is not None
        filled = pill._progress_fill_width(rect, percent)
        assert 0 <= filled <= rect.width()
        if percent == 100:
            assert filled == rect.width()
        if percent == 0:
            assert filled == 0
    set_transcription_progress(None)
