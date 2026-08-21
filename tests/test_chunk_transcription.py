"""Pure helpers voor de chunk-transcriptie-pipeline."""

from __future__ import annotations

from chunk_transcription import (
    TimedWord,
    commit_window,
    decide_chunk_cut,
    dedupe_overlap_text,
    merge_chunk_text,
    merge_timed_chunk,
    timed_words_from_segments,
    trailing_silence_seconds,
    words_after_overlap,
)


def test_dedupe_removes_overlapping_words() -> None:
    previous = "hallo wereld dit is een test"
    new_text = "dit is een test van vandaag"
    assert dedupe_overlap_text(previous, new_text) == "van vandaag"


def test_dedupe_keeps_new_text_when_no_clear_overlap() -> None:
    previous = "hallo wereld"
    new_text = "goedemorgen allemaal"
    assert dedupe_overlap_text(previous, new_text) == "goedemorgen allemaal"


def test_dedupe_drops_single_identical_overlap_token() -> None:
    """Pandora-naad: één eigennaam op de knip, geen prefix-gok."""

    previous = "Zeus schonk haar aan Prometheus."
    new_text = "Prometheus. Maar deze wist"
    assert dedupe_overlap_text(previous, new_text) == "Maar deze wist"


def test_dedupe_does_not_prefix_match_short_token_to_longer_word() -> None:
    previous = "stal Prometheus een pa"
    new_text = "paard uit Olympus"
    assert dedupe_overlap_text(previous, new_text) == "paard uit Olympus"


def test_dedupe_empty_previous_returns_new() -> None:
    assert dedupe_overlap_text("", "eerste chunk") == "eerste chunk"


def test_dedupe_ignores_trailing_punctuation_when_matching() -> None:
    previous = "Ik draai nu deze feature."
    new_text = "deze feature op twee plekken"
    assert dedupe_overlap_text(previous, new_text) == "op twee plekken"


def test_dedupe_matches_overlap_case_insensitively() -> None:
    previous = "Ik draai nu deze feature."
    new_text = "Deze feature op twee plekken"
    assert dedupe_overlap_text(previous, new_text) == "op twee plekken"


def test_dedupe_ignores_ellipsis_at_token_edges() -> None:
    previous = "de kwaliteit is van..."
    new_text = "kwaliteit is van groot belang"
    assert dedupe_overlap_text(previous, new_text) == "groot belang"


def test_dedupe_ignores_unicode_ellipsis_at_token_edges() -> None:
    previous = "de kwaliteit is van…"
    new_text = "kwaliteit is van groot belang"
    assert dedupe_overlap_text(previous, new_text) == "groot belang"


def test_dedupe_matches_unicode_composed_and_decomposed_tokens() -> None:
    previous = "een café bezoek"
    new_text = "een cafe\u0301 bezoek morgen"
    assert dedupe_overlap_text(previous, new_text) == "morgen"


def test_dedupe_ignores_curly_quotes_at_token_edges() -> None:
    previous = "Ik draai nu deze “feature”"
    new_text = "deze feature op twee plekken"
    assert dedupe_overlap_text(previous, new_text) == "op twee plekken"


def test_dedupe_keeps_original_remainder_text() -> None:
    previous = "einde van de zin."
    new_text = "van de zin Extra woorden"
    assert dedupe_overlap_text(previous, new_text) == "Extra woorden"


def test_dedupe_does_not_treat_similar_words_as_the_same_audio() -> None:
    previous = "we gaan inspelen op het onderwerp"
    new_text = "inspreken op het onderwerp vanavond"
    assert dedupe_overlap_text(previous, new_text) == "inspreken op het onderwerp vanavond"


def test_words_after_overlap_drops_broken_prefix_from_mid_word_cut() -> None:
    """Pegasus-naad: overlap start midden in 'gevleugelde' → 'leugende'."""

    words = [
        TimedWord("leugende", 0.10, 0.55),
        TimedWord("paard", 0.56, 0.80),
        TimedWord("getempt", 0.81, 1.20),
        TimedWord("kon", 1.21, 1.35),
        TimedWord("worden", 1.36, 1.48),
        TimedWord("Deze", 1.50, 1.70),
        TimedWord("prins", 1.71, 2.00),
    ]
    kept = words_after_overlap(words, overlap_seconds=1.5)
    assert " ".join(w.text for w in kept) == "Deze prins"


def test_words_after_overlap_keeps_all_when_no_overlap() -> None:
    words = [TimedWord("eerste", 0.0, 0.4), TimedWord("chunk", 0.4, 0.8)]
    kept = words_after_overlap(words, overlap_seconds=0.0)
    assert " ".join(w.text for w in kept) == "eerste chunk"


def test_words_after_overlap_drops_straddling_word_that_starts_in_overlap() -> None:
    words = [
        TimedWord("getemd", 1.40, 1.70),
        TimedWord("kon", 1.71, 1.90),
    ]
    kept = words_after_overlap(words, overlap_seconds=1.5)
    assert " ".join(w.text for w in kept) == "kon"


def test_merge_chunk_text_prefers_timestamps_over_punctuated_echo() -> None:
    previous = "Ik draai nu deze feature."
    words = [
        TimedWord("deze", 0.10, 0.30),
        TimedWord("feature", 0.30, 0.70),
        TimedWord("op", 1.60, 1.80),
        TimedWord("twee", 1.80, 2.10),
        TimedWord("plekken", 2.10, 2.50),
    ]
    assert (
        merge_chunk_text(
            previous,
            raw_text="deze feature op twee plekken",
            words=words,
            overlap_seconds=1.5,
        )
        == "op twee plekken"
    )


def test_merge_chunk_text_falls_back_to_word_dedupe_without_timestamps() -> None:
    previous = "hallo wereld dit is een test"
    assert (
        merge_chunk_text(
            previous,
            raw_text="dit is een test van vandaag",
            words=(),
            overlap_seconds=1.5,
        )
        == "van vandaag"
    )


def test_timed_words_from_segments_reads_faster_whisper_words() -> None:
    class _Word:
        def __init__(self, word: str, start: float, end: float) -> None:
            self.word = word
            self.start = start
            self.end = end

    class _Segment:
        text = "hello world"
        words = [_Word("hello", 0.0, 0.4), _Word("world", 0.4, 0.8)]

    timed = timed_words_from_segments([_Segment()])
    assert [(w.text, w.start, w.end) for w in timed] == [
        ("hello", 0.0, 0.4),
        ("world", 0.4, 0.8),
    ]


def test_timed_words_from_segments_skips_mock_segments_without_real_words() -> None:
    from unittest.mock import MagicMock

    segment = MagicMock()
    segment.text = "alfa bravo"
    segment.end = 0.5
    assert timed_words_from_segments([segment]) == []


def test_timed_words_from_segments_uses_segment_span_without_word_list() -> None:
    class _Segment:
        text = "vuurige vlammen"
        start = 1.6
        end = 2.4
        words = None

    timed = timed_words_from_segments([_Segment()])
    assert timed == [TimedWord("vuurige vlammen", 1.6, 2.4)]


def test_merge_timed_chunk_replaces_truncated_tail_with_overlap_revision() -> None:
    """Afgehakt 'vla...' in de staart wordt door chunk B's overlap 'vlammen'."""

    first = merge_timed_chunk(
        raw_text="Het monster blies vuurige vla",
        words=[
            TimedWord("Het", 0.0, 0.2),
            TimedWord("monster", 0.2, 0.6),
            TimedWord("blies", 0.6, 1.0),
            TimedWord("vuurige", 28.6, 29.0),
            TimedWord("vla...", 29.0, 29.4),
        ],
        overlap_seconds=0.0,
        piece_duration=30.0,
        previous_tail="",
        previous_confirmed="",
    )
    assert first.commit_text == "Het monster blies"
    assert first.new_tail == "vuurige vla..."

    second = merge_timed_chunk(
        raw_text="vuurige vlammen blies en stinkende rook verder",
        words=[
            TimedWord("vuurige", 0.1, 0.5),
            TimedWord("vlammen", 0.5, 1.0),
            TimedWord("blies", 1.0, 1.4),
            TimedWord("en", 1.6, 1.8),
            TimedWord("stinkende", 1.8, 2.3),
            TimedWord("rook", 2.3, 2.6),
            TimedWord("verder", 28.8, 29.5),
        ],
        overlap_seconds=1.5,
        piece_duration=30.0,
        previous_tail=first.new_tail,
        previous_confirmed=first.commit_text,
    )
    assert second.commit_text == "vuurige vlammen blies en stinkende rook"
    assert second.new_tail == "verder"


def test_merge_timed_chunk_drops_overlap_when_no_pending_tail() -> None:
    result = merge_timed_chunk(
        raw_text="leugende paard Deze prins",
        words=[
            TimedWord("leugende", 0.1, 0.5),
            TimedWord("paard", 0.5, 0.9),
            TimedWord("Deze", 1.6, 1.9),
            TimedWord("prins", 1.9, 2.2),
        ],
        overlap_seconds=1.5,
        piece_duration=5.0,
        previous_tail="",
        previous_confirmed="gevleugelde paard",
    )
    assert result.commit_text == "Deze prins"
    assert result.new_tail == ""


def test_segment_spanning_overlap_is_kept_not_dropped() -> None:
    """Eén lang Whisper-segment dat in de overlap begint mag de zin niet wissen."""

    result = merge_timed_chunk(
        raw_text="Hij liep en hij liep naar de berg",
        words=[TimedWord("Hij liep en hij liep naar de berg", 0.0, 4.0)],
        overlap_seconds=1.5,
        piece_duration=4.0,
        previous_tail="",
        previous_confirmed="de toom in zijn hand",
    )
    assert result.commit_text == "Hij liep en hij liep naar de berg"
    assert result.new_tail == ""


def test_merge_timed_chunk_falls_back_to_text_dedupe() -> None:
    result = merge_timed_chunk(
        raw_text="dit is een test van vandaag",
        words=(),
        overlap_seconds=1.5,
        piece_duration=5.0,
        previous_tail="",
        previous_confirmed="hallo wereld dit is een test",
    )
    assert result.commit_text == "van vandaag"
    assert result.new_tail == ""


def test_short_chunk_commits_all_new_audio_instead_of_holding_tail() -> None:
    """Korte VAD-knip mag het midden niet in een steeds overschreven staart parkeren."""

    result = merge_timed_chunk(
        raw_text="ging scheep naar Griekenland",
        words=[
            TimedWord("ging", 0.1, 0.4),
            TimedWord("scheep", 0.4, 0.8),
            TimedWord("naar", 0.8, 1.1),
            TimedWord("Griekenland", 1.1, 1.8),
        ],
        overlap_seconds=0.0,
        piece_duration=2.0,
        previous_tail="",
        previous_confirmed="",
    )
    assert result.commit_text == "ging scheep naar Griekenland"
    assert result.new_tail == ""


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


_SR = 16_000


def _s(seconds: float) -> int:
    return int(seconds * _SR)


def test_commit_window_first_cut_holds_six_second_tail() -> None:
    window = commit_window(committed=0, cut_end=_s(20), sample_rate=_SR)
    assert window.slice_start == 0
    assert window.commit_end == _s(14)


def test_commit_window_second_cut_uses_committed_not_cut_cadence() -> None:
    window = commit_window(committed=_s(14), cut_end=_s(40), sample_rate=_SR)
    assert window.slice_start == _s(12.5)
    assert window.commit_end == _s(34)


def test_commit_window_sequence_does_not_drift() -> None:
    committed = 0
    expected = [
        (0, _s(14)),
        (_s(12.5), _s(34)),
        (_s(32.5), _s(54)),
        (_s(52.5), _s(74)),
    ]
    windows = []
    for cut_s in (20, 40, 60, 80):
        window = commit_window(committed=committed, cut_end=_s(cut_s), sample_rate=_SR)
        windows.append((window.slice_start, window.commit_end))
        committed = window.commit_end
    assert windows == expected


def test_commit_window_hold_at_exact_minimum_available() -> None:
    tail = _s(6)
    overlap = _s(1.5)
    minimum = tail + 2 * overlap
    window = commit_window(committed=0, cut_end=minimum, sample_rate=_SR)
    assert window.commit_end == minimum - tail
    assert window.slice_start == 0


def test_commit_window_no_hold_when_available_below_minimum() -> None:
    tail = _s(6)
    overlap = _s(1.5)
    minimum = tail + 2 * overlap
    window = commit_window(committed=0, cut_end=minimum - 1, sample_rate=_SR)
    assert window.commit_end == minimum - 1
    assert window.slice_start == 0
