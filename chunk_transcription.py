"""
Pure helpers voor chunk-gewijze transcriptie (geen I/O, geen Whisper).

Runtime-pad: ``dedupe_overlap_text`` (token-match na ``str.split()``,
normalisatie alleen voor de vergelijking: NFC, casefold, interpunctie
aan tokenranden; default minstens één identiek token, geen prefix).
Output-remainder blijft de originele Whisper-tekst.
Incrementeel houdt de laatste ``UNPROCESSED_TAIL_SECONDS`` (6 s) audio
achter tot de volgende knip; venster via ``commit_window``.

``TimedWord`` / ``merge_timed_chunk`` / ``tail_hold_seconds`` zijn een
experimentele dead path: unit tests leggen overlap-semantiek vast, maar de
helpers zijn niet aangesloten. Niet opnieuw wiren zonder benchmark (WER,
duplicaten, deleties, stop-latency). Zie
``docs/superpowers/specs/2026-08-20-chunk-merge-postmortem.md``.

Zie ook `docs/superpowers/specs/2026-08-01-chunk-transcription-pipeline-design.md`.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from numbers import Real
from typing import Any

OVERLAP_SECONDS = 1.5
UNPROCESSED_TAIL_SECONDS = 6.0

_CHUNK_MODES = frozenset({"fixed", "vad", "hybrid"})


@dataclass(frozen=True)
class TimedWord:
    """Eén token met tijd t.o.v. het begin van het Whisper-stuk (seconden).

    Experimenteel / niet aangesloten. Zie module-docstring.
    """

    text: str
    start: float
    end: float


def normalize_chunk_mode(value: object, default: str = "hybrid") -> str:
    text = str(value or "").strip().lower()
    if text in _CHUNK_MODES:
        return text
    return default if default in _CHUNK_MODES else "hybrid"


@dataclass(frozen=True)
class CommitWindow:
    """Whisper-slice in samples: [slice_start, commit_end)."""

    slice_start: int
    commit_end: int


def commit_window(
    *,
    committed: int,
    cut_end: int,
    sample_rate: int,
    tail_seconds: float = UNPROCESSED_TAIL_SECONDS,
    overlap_seconds: float = OVERLAP_SECONDS,
) -> CommitWindow:
    """Bepaal het commit-Whisper-venster t.o.v. ``committed``, niet de cut-cadans."""

    rate = max(1, int(sample_rate))
    committed_i = max(0, int(committed))
    cut_i = max(committed_i, int(cut_end))
    tail_samples = max(0, int(float(tail_seconds) * rate))
    overlap_samples = max(0, int(float(overlap_seconds) * rate))
    available = cut_i - committed_i
    min_hold_available = tail_samples + 2 * overlap_samples
    if available >= min_hold_available and tail_samples > 0:
        commit_end = cut_i - tail_samples
    else:
        commit_end = cut_i
    if committed_i <= 0:
        slice_start = 0
    else:
        slice_start = max(0, committed_i - overlap_samples)
    if commit_end < slice_start:
        commit_end = slice_start
    return CommitWindow(slice_start=slice_start, commit_end=commit_end)


def _strip_edge_punctuation(token: str) -> str:
    start = 0
    end = len(token)
    while start < end and unicodedata.category(token[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(token[end - 1]).startswith("P"):
        end -= 1
    return token[start:end]


def _token_for_match(token: str) -> str:
    """Normaliseer alleen voor overlap-vergelijking; output blijft origineel."""

    normalized = unicodedata.normalize("NFC", token).casefold()
    return _strip_edge_punctuation(normalized)


def _token_windows_match(left: Sequence[str], right: Sequence[str]) -> bool:
    for a, b in zip(left, right, strict=True):
        key = _token_for_match(a)
        if not key or key != _token_for_match(b):
            return False
    return True


def dedupe_overlap_text(previous: str, new_text: str, *, min_words: int = 1) -> str:
    """
    Verwijder een duidelijke woord-overlap aan het begin van ``new_text``.

    Conservatief: zonder match van minstens ``min_words`` opeenvolgende
    identieke tokens (default 1; geen prefix zoals ``pa``/``paard``) wordt
    ``new_text`` ongewijzigd teruggegeven (liever dubbel dan kwijt).
    Interpunctie aan tokenranden telt niet mee bij de match; de remainder
    behoudt de originele Whisper-tekst.
    """

    prev = previous.strip()
    nxt = new_text.strip()
    if not nxt:
        return ""
    if not prev:
        return nxt

    prev_words = prev.split()
    new_words = nxt.split()
    if len(new_words) < min_words:
        return nxt

    max_k = min(len(prev_words), len(new_words))
    for k in range(max_k, min_words - 1, -1):
        if _token_windows_match(prev_words[-k:], new_words[:k]):
            remainder = new_words[k:]
            return " ".join(remainder).strip()
    return nxt


def words_after_overlap(
    words: Sequence[TimedWord],
    overlap_seconds: float,
) -> list[TimedWord]:
    """Houd tokens die ná de overlap-prefix beginnen (straddlers vallen weg)."""

    if overlap_seconds <= 0:
        return list(words)
    return [word for word in words if word.start >= overlap_seconds]


def merge_chunk_text(
    previous: str,
    *,
    raw_text: str,
    words: Sequence[TimedWord],
    overlap_seconds: float,
) -> str:
    """Nieuwe chunk-tekst: timestamps als die er zijn, anders woord-dedupe."""

    if words:
        kept = words_after_overlap(words, overlap_seconds)
        return " ".join(word.text for word in kept if word.text).strip()
    return dedupe_overlap_text(previous, raw_text)


def join_timed_text(words: Sequence[TimedWord]) -> str:
    return " ".join(word.text for word in words if word.text.strip()).strip()


def tail_hold_seconds(*, piece_duration: float, overlap_seconds: float) -> float:
    """Houd een mutable staart alleen als er genoeg nieuwe audio overblijft.

    Experimenteel / niet aangesloten. Zie module-docstring.

    Bij korte VAD-knippen (≤ 2× overlap) zou de hele nieuwe audio in de staart
    belanden en bij de volgende knip overschreven worden — het midden verdwijnt.
    De 1,5 s-staart in dit pad bleek te kort t.o.v. Whisper-frases; volgende
    poging hoort 4–8 s te zijn, niet deze helper opnieuw live te zetten.
    """

    new_seconds = max(0.0, float(piece_duration) - max(0.0, float(overlap_seconds)))
    if new_seconds < OVERLAP_SECONDS * 2:
        return 0.0
    return min(OVERLAP_SECONDS, new_seconds)


@dataclass(frozen=True)
class TimedChunkMerge:
    """Bevestigde delta plus nieuwe mutable staart (nog niet gecommit).

    Experimenteel / niet aangesloten. Zie module-docstring.
    """

    commit_text: str
    new_tail: str


def merge_timed_chunk(
    *,
    raw_text: str,
    words: Sequence[TimedWord],
    overlap_seconds: float,
    piece_duration: float,
    previous_tail: str,
    previous_confirmed: str,
) -> TimedChunkMerge:
    """Overlap van B vervangt de staart van A; nieuwe staart blijft mutable.

    Experimenteel / niet aangesloten. Segment- of word-timestamp merge op een
    1,5 s-staart is geen productiepad. Zie module-docstring en postmortem.
    """

    if not words:
        previous = " ".join(
            part for part in (previous_confirmed, previous_tail) if part.strip()
        ).strip()
        return TimedChunkMerge(
            commit_text=dedupe_overlap_text(previous, raw_text),
            new_tail="",
        )

    duration = float(piece_duration)
    if duration <= 0:
        duration = max((word.end for word in words), default=0.0)
    overlap_s = max(0.0, float(overlap_seconds))
    hold = tail_hold_seconds(piece_duration=duration, overlap_seconds=overlap_s)
    tail_start = duration - hold if hold > 0 else duration + 1.0

    overlap_words: list[TimedWord] = []
    confirmed: list[TimedWord] = []
    tail: list[TimedWord] = []
    for word in words:
        # Alleen tokens die volledig in de overlap-prefix vallen, weggooien.
        # Een lang segment met start=0 en end voorbij de overlap is nieuwe zin.
        fully_in_overlap = overlap_s > 0 and word.end <= overlap_s
        if fully_in_overlap:
            overlap_words.append(word)
        elif word.start >= tail_start:
            tail.append(word)
        else:
            confirmed.append(word)

    parts: list[str] = []
    if overlap_s > 0 and previous_tail.strip():
        revision = join_timed_text(overlap_words)
        prev_n = len(previous_tail.split())
        rev_n = len(revision.split()) if revision else 0
        # Korte overlap-decode mag een lange staart niet wissen.
        if revision and rev_n >= max(1, prev_n // 2):
            parts.append(revision)
        else:
            parts.append(previous_tail.strip())
    elif previous_tail.strip() and overlap_s <= 0:
        parts.append(previous_tail.strip())

    confirmed_text = join_timed_text(confirmed)
    if confirmed_text:
        parts.append(confirmed_text)

    return TimedChunkMerge(
        commit_text=" ".join(parts).strip(),
        new_tail=join_timed_text(tail),
    )


def _finite_seconds(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _timed_word_from_obj(item: object) -> TimedWord | None:
    text = str(getattr(item, "word", None) or getattr(item, "text", None) or "").strip()
    start = _finite_seconds(getattr(item, "start", None))
    end = _finite_seconds(getattr(item, "end", None))
    if not text or start is None or end is None:
        return None
    return TimedWord(text=text, start=start, end=end)


def _real_word_list(segment: object) -> list[Any] | None:
    words = getattr(segment, "words", None)
    if type(words) is list or type(words) is tuple:
        return list(words)
    return None


def timed_words_from_segments(segments: Iterable[object]) -> list[TimedWord]:
    """Word-timestamps, anders segment-span (zonder dure word-alignment)."""

    timed: list[TimedWord] = []
    for segment in segments:
        raw_words = _real_word_list(segment)
        if raw_words is not None:
            for item in raw_words:
                word = _timed_word_from_obj(item)
                if word is not None:
                    timed.append(word)
            continue
        text = str(getattr(segment, "text", "") or "").strip()
        start = _finite_seconds(getattr(segment, "start", None))
        end = _finite_seconds(getattr(segment, "end", None))
        if text and start is not None and end is not None:
            timed.append(TimedWord(text=text, start=start, end=end))
    return timed


def trailing_silence_seconds(
    rms_per_frame: list[float],
    *,
    frame_seconds: float,
    silence_rms: float,
) -> float:
    """Duur van aaneengesloten stille frames aan het eind van de lijst."""

    if frame_seconds <= 0 or not rms_per_frame:
        return 0.0
    count = 0
    for level in reversed(rms_per_frame):
        if float(level) < silence_rms:
            count += 1
        else:
            break
    return count * frame_seconds


def decide_chunk_cut(
    *,
    mode: str,
    open_seconds: float,
    trailing_silence_seconds: float,
    chunk_seconds: float,
    vad_ms: int,
    min_seconds: float,
) -> str | None:
    """
    Bepaal of de open chunk geknipt moet worden.

    Retourneert ``\"vad\"``, ``\"fixed\"``, of ``None`` (nog niet knippen).
    Hard cap in vad-modus telt als ``fixed``.
    """

    mode_n = normalize_chunk_mode(mode)
    if open_seconds < min_seconds:
        return None

    vad_seconds = max(0.0, float(vad_ms) / 1000.0)
    at_cap = open_seconds >= chunk_seconds
    silence_hit = vad_seconds > 0 and trailing_silence_seconds >= vad_seconds

    if mode_n == "fixed":
        return "fixed" if at_cap else None

    # Hard cap before stilte: anders blijft VAD "vad" teruggeven terwijl de open
    # chunk (bijna) alleen stilte is, `_try_commit_chunk` early-returnt, en de
    # cursor nooit opschuift — live-plak/LED's lijken dan "gestopt".
    if at_cap:
        return "fixed"
    if silence_hit:
        return "vad"
    return None
