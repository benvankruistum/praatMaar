"""Tests for transcription progress helpers."""

from __future__ import annotations

from indicator._contract import (
    get_transcription_progress,
    set_transcription_progress,
    transcription_percent,
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
