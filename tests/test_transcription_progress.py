"""Tests for transcription progress helpers + hybrid ticker."""

from __future__ import annotations

import time

from indicator._contract import (
    get_transcription_progress,
    set_transcription_progress,
    transcription_percent,
)
from transcription_progress import (
    DEFAULT_RTF,
    MAX_TICK_PERCENT,
    TranscriptionProgressTicker,
    hybrid_percent,
    time_based_percent,
)


def test_transcription_percent_clamps() -> None:
    assert transcription_percent(0, 10) == 0
    assert transcription_percent(5, 10) == 50
    assert transcription_percent(10, 10) == 99
    assert transcription_percent(12, 10) == 99
    assert transcription_percent(1, 0) == 0


def test_set_and_get_transcription_progress() -> None:
    set_transcription_progress(None)
    assert get_transcription_progress() is None
    set_transcription_progress(0)
    assert get_transcription_progress() == 0
    set_transcription_progress(45)
    assert get_transcription_progress() == 45
    set_transcription_progress(150)
    assert get_transcription_progress() == 100
    set_transcription_progress(None)
    assert get_transcription_progress() is None


def test_time_based_percent_clamps_and_scales() -> None:
    assert time_based_percent(0, 10, rtf=0.4) == 1
    # 2 s elapsed, expected = 10 * 0.4 = 4 s → 50%
    assert time_based_percent(2.0, 10.0, rtf=0.4) == 50
    assert time_based_percent(100.0, 10.0, rtf=0.4) == MAX_TICK_PERCENT
    assert time_based_percent(1.0, 0.0) == 1
    assert DEFAULT_RTF == 0.4


def test_hybrid_percent_takes_max() -> None:
    assert hybrid_percent(40, None) == 40
    assert hybrid_percent(40, 25) == 40
    assert hybrid_percent(40, 70) == 70


def test_ticker_moves_during_wait() -> None:
    set_transcription_progress(None)
    ticker = TranscriptionProgressTicker(10.0, rtf=0.4, interval_seconds=0.05)
    ticker.start()
    try:
        time.sleep(0.2)
        mid = get_transcription_progress()
        assert mid is not None
        assert 1 <= mid <= MAX_TICK_PERCENT
        ticker.note_segment(10)
        assert get_transcription_progress() is not None
        assert get_transcription_progress() >= mid  # type: ignore[operator]
    finally:
        ticker.stop(100)
    assert get_transcription_progress() == 100
    set_transcription_progress(None)


def test_ticker_segment_does_not_lower_time_floor() -> None:
    set_transcription_progress(None)
    ticker = TranscriptionProgressTicker(1.0, rtf=0.01, interval_seconds=0.05)
    ticker.start()
    try:
        time.sleep(0.15)
        high = get_transcription_progress()
        assert high is not None and high >= 50
        ticker.note_segment(5)
        assert get_transcription_progress() >= high
    finally:
        ticker.stop(None)
    assert get_transcription_progress() is None
