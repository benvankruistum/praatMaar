"""Filters op Whisper-segmenten en opeenvolgende herhaling."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from modules._builtin.speech_to_text import IncrementalSpeechToText
from whisper_segments import (
    collapse_repeated_phrases,
    join_reliable_segments,
    reliable_segment_text,
)


def _seg(text: str, **scores: float) -> SimpleNamespace:
    return SimpleNamespace(text=text, **scores)


def test_segment_without_scores_is_kept() -> None:
    assert reliable_segment_text(_seg("  hallo wereld  ")) == "hallo wereld"


def test_magicmock_scores_are_ignored() -> None:
    segment = MagicMock()
    segment.text = "hallo wereld"
    assert reliable_segment_text(segment) == "hallo wereld"


def test_high_compression_is_dropped() -> None:
    assert reliable_segment_text(_seg("lus", compression_ratio=2.41)) is None
    assert reliable_segment_text(_seg("net goed", compression_ratio=2.4)) == "net goed"


def test_sampling_fallback_is_dropped() -> None:
    assert reliable_segment_text(_seg("verzonnen", temperature=0.2)) is None
    assert reliable_segment_text(_seg("beam", temperature=0.0)) == "beam"


def test_no_speech_needs_low_logprob() -> None:
    assert reliable_segment_text(_seg("stilte", no_speech_prob=0.61, avg_logprob=-1.01)) is None
    assert reliable_segment_text(_seg("zeker", no_speech_prob=0.9, avg_logprob=-0.2)) == "zeker"


def test_drop_log_has_scores_not_transcript(caplog) -> None:
    caplog.set_level(logging.INFO)
    assert reliable_segment_text(_seg("geheim zinnetje", compression_ratio=3.0)) is None
    assert "geheim" not in caplog.text
    assert "reason=compression" in caplog.text


def test_join_drops_failed_segment_and_collapses_the_rest() -> None:
    phrase = "Nou, ik wacht even mee."
    segments = [
        _seg("goed begin"),
        _seg(" ".join([phrase] * 4), compression_ratio=4.0),
        _seg(phrase),
        _seg(phrase),
        _seg(phrase),
        _seg("einde"),
    ]
    assert join_reliable_segments(segments) == f"goed begin {phrase} einde"


def test_two_repeats_stay() -> None:
    phrase = "dit blijft twee keer staan"
    assert collapse_repeated_phrases(f"{phrase} {phrase}") == f"{phrase} {phrase}"


def test_short_phrase_is_not_collapsed() -> None:
    assert collapse_repeated_phrases("waarom niet waarom niet waarom niet") == (
        "waarom niet waarom niet waarom niet"
    )


def test_continuous_stt_uses_temperature_zero_and_drops_failed_segments() -> None:
    class _Model:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def transcribe(self, _audio: object, **kwargs: object) -> tuple[list[object], object]:
            self.kwargs = kwargs
            return [
                _seg("goed"),
                _seg("lus", compression_ratio=3.0),
            ], object()

    model = _Model()
    text = IncrementalSpeechToText._transcribe_audio(model, object(), language="nl")
    assert model.kwargs["temperature"] == 0.0
    assert text == "goed"


def test_separate_runs_each_collapse_once() -> None:
    phrase = "een twee drie vier"
    other = "vijf zes zeven acht"
    text = f"{phrase} {phrase} {phrase} ertussen {other} {other} {other}"
    assert collapse_repeated_phrases(text) == f"{phrase} ertussen {other}"
