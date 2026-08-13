"""Pure helpers voor de chunk-transcriptie-pipeline."""

from __future__ import annotations

from chunk_transcription import (
    decide_chunk_cut,
    dedupe_overlap_text,
    trailing_silence_seconds,
)


def test_dedupe_removes_overlapping_words() -> None:
    previous = "hallo wereld dit is een test"
    new_text = "dit is een test van vandaag"
    assert dedupe_overlap_text(previous, new_text) == "van vandaag"


def test_dedupe_keeps_new_text_when_no_clear_overlap() -> None:
    previous = "hallo wereld"
    new_text = "goedemorgen allemaal"
    assert dedupe_overlap_text(previous, new_text) == "goedemorgen allemaal"


def test_dedupe_requires_at_least_two_words() -> None:
    previous = "einde zin"
    new_text = "zin opnieuw beginnen"
    # Enkel woord "zin" is te kort → niet knippen.
    assert dedupe_overlap_text(previous, new_text) == "zin opnieuw beginnen"


def test_dedupe_empty_previous_returns_new() -> None:
    assert dedupe_overlap_text("", "eerste chunk") == "eerste chunk"


def test_trailing_silence_counts_quiet_tail() -> None:
    # 5 frames luid, 10 stil; frame = 0.1 s → 1.0 s stilte.
    rms = [0.1] * 5 + [0.001] * 10
    assert trailing_silence_seconds(rms, frame_seconds=0.1, silence_rms=0.01) == 1.0


def test_trailing_silence_zero_when_loud_at_end() -> None:
    rms = [0.001] * 10 + [0.2]
    assert trailing_silence_seconds(rms, frame_seconds=0.1, silence_rms=0.01) == 0.0


def test_decide_fixed_cuts_at_chunk_seconds() -> None:
    assert (
        decide_chunk_cut(
            mode="fixed",
            open_seconds=30.0,
            trailing_silence_seconds=0.0,
            chunk_seconds=30.0,
            vad_ms=2000,
            min_seconds=1.5,
        )
        == "fixed"
    )


def test_decide_fixed_waits_below_threshold() -> None:
    assert (
        decide_chunk_cut(
            mode="fixed",
            open_seconds=10.0,
            trailing_silence_seconds=5.0,
            chunk_seconds=30.0,
            vad_ms=2000,
            min_seconds=1.5,
        )
        is None
    )


def test_decide_vad_cuts_on_silence() -> None:
    assert (
        decide_chunk_cut(
            mode="vad",
            open_seconds=5.0,
            trailing_silence_seconds=2.0,
            chunk_seconds=30.0,
            vad_ms=2000,
            min_seconds=1.5,
        )
        == "vad"
    )


def test_decide_vad_hard_cap_is_fixed() -> None:
    assert (
        decide_chunk_cut(
            mode="vad",
            open_seconds=30.0,
            trailing_silence_seconds=0.0,
            chunk_seconds=30.0,
            vad_ms=2000,
            min_seconds=1.5,
        )
        == "fixed"
    )


def test_decide_hybrid_prefers_vad_before_cap() -> None:
    assert (
        decide_chunk_cut(
            mode="hybrid",
            open_seconds=10.0,
            trailing_silence_seconds=2.5,
            chunk_seconds=30.0,
            vad_ms=2000,
            min_seconds=1.5,
        )
        == "vad"
    )


def test_decide_vad_hard_cap_wins_over_trailing_silence() -> None:
    """Stilte-only open chunk op de cap mag niet als VAD blijven hangen."""
    assert (
        decide_chunk_cut(
            mode="vad",
            open_seconds=30.0,
            trailing_silence_seconds=30.0,
            chunk_seconds=30.0,
            vad_ms=2000,
            min_seconds=1.5,
        )
        == "fixed"
    )


def test_decide_hybrid_hard_cap_wins_over_trailing_silence() -> None:
    assert (
        decide_chunk_cut(
            mode="hybrid",
            open_seconds=30.0,
            trailing_silence_seconds=30.0,
            chunk_seconds=30.0,
            vad_ms=2000,
            min_seconds=1.5,
        )
        == "fixed"
    )


def test_decide_respects_min_seconds() -> None:
    assert (
        decide_chunk_cut(
            mode="hybrid",
            open_seconds=1.0,
            trailing_silence_seconds=5.0,
            chunk_seconds=30.0,
            vad_ms=2000,
            min_seconds=1.5,
        )
        is None
    )
