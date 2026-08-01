"""
Pure helpers voor chunk-gewijze transcriptie (geen I/O, geen Whisper).

Zie `docs/superpowers/specs/2026-08-01-chunk-transcription-pipeline-design.md`.
"""

from __future__ import annotations

OVERLAP_SECONDS = 1.5

_CHUNK_MODES = frozenset({"fixed", "vad", "hybrid"})


def normalize_chunk_mode(value: object, default: str = "hybrid") -> str:
    text = str(value or "").strip().lower()
    if text in _CHUNK_MODES:
        return text
    return default if default in _CHUNK_MODES else "hybrid"


def dedupe_overlap_text(previous: str, new_text: str, *, min_words: int = 2) -> str:
    """
    Verwijder een duidelijke woord-overlap aan het begin van ``new_text``.

    Conservatief: zonder match van minstens ``min_words`` opeenvolgende woorden
    wordt ``new_text`` ongewijzigd teruggegeven (liever dubbel dan kwijt).
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
        if prev_words[-k:] == new_words[:k]:
            remainder = new_words[k:]
            return " ".join(remainder).strip()
    return nxt


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

    if mode_n == "vad":
        if silence_hit:
            return "vad"
        if at_cap:
            return "fixed"
        return None

    # hybrid
    if silence_hit:
        return "vad"
    if at_cap:
        return "fixed"
    return None
