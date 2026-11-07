"""Whisper-segmenten die de decode zelf wantrouwt, niet in het transcript.

Faster-Whisper levert een segment ook als de beam-decode faalt. Zonder
temperature-ladder (``temperature=0`` bij ``transcribe``) is er geen tweede,
lossere poging. Een segment met te hoge compressieratio, met sampling
(``temperature`` > 0), of met hoge geen-spraak-kans én lage log-prob, valt
hier weg. Een zinsdeel van minstens vier woorden dat drie keer achter elkaar
staat, blijft één keer staan.

Drempels zijn de Faster-Whisper 1.2.1-defaults voor compressie, log-prob en
geen-spraak. Ontbrekende of niet-numerieke scores tellen niet: tests en
stubs die alleen ``text`` zetten blijven gewoon staan.
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# faster-whisper TranscriptionOptions defaults (1.2.1).
COMPRESSION_RATIO_MAX = 2.4
LOG_PROB_MIN = -1.0
NO_SPEECH_MAX = 0.6

MIN_REPEAT_WORDS = 4
MIN_REPEAT_COUNT = 3
# Lange vergaderingen: niet elke zinslengte tot het eind van de tekst proberen.
MAX_REPEAT_WORDS = 40


def _score(segment: object, name: str) -> float | None:
    value = getattr(segment, name, None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number:  # NaN
        return None
    return number


def _log_drop(reason: str, segment: object) -> None:
    # Geen segmenttekst: die hoort niet in praatMaar.log.
    _log.info(
        "whisper.segment dropped reason=%s compression=%s no_speech=%s logprob=%s temperature=%s",
        reason,
        _score(segment, "compression_ratio"),
        _score(segment, "no_speech_prob"),
        _score(segment, "avg_logprob"),
        _score(segment, "temperature"),
    )


def reliable_segment_text(segment: object) -> str | None:
    """Tekst van één segment, of ``None`` als de decode niet betrouwbaar is."""

    raw = getattr(segment, "text", "")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None

    temperature = _score(segment, "temperature")
    if temperature is not None and temperature > 0.0:
        _log_drop("temperature", segment)
        return None

    compression = _score(segment, "compression_ratio")
    if compression is not None and compression > COMPRESSION_RATIO_MAX:
        _log_drop("compression", segment)
        return None

    no_speech = _score(segment, "no_speech_prob")
    avg_logprob = _score(segment, "avg_logprob")
    if (
        no_speech is not None
        and avg_logprob is not None
        and no_speech > NO_SPEECH_MAX
        and avg_logprob < LOG_PROB_MIN
    ):
        _log_drop("no_speech", segment)
        return None

    return text


def collapse_repeated_phrases(
    text: str,
    *,
    min_words: int = MIN_REPEAT_WORDS,
    min_repeats: int = MIN_REPEAT_COUNT,
) -> str:
    """Houd één kopie van een zinsdeel dat ``min_repeats`` keer op rij staat."""

    words = text.split()
    if min_words < 1 or min_repeats < 2 or len(words) < min_words * min_repeats:
        return " ".join(words)

    output: list[str] = []
    index = 0
    total = len(words)
    while index < total:
        remaining = total - index
        max_len = min(MAX_REPEAT_WORDS, remaining // min_repeats)
        phrase_len = _repeated_phrase_length(
            words, index, min_words=min_words, min_repeats=min_repeats, max_len=max_len
        )
        if phrase_len:
            output.extend(words[index : index + phrase_len])
            index += phrase_len * _repeat_count(words, index, phrase_len)
            continue
        output.append(words[index])
        index += 1
    return " ".join(output)


def _repeated_phrase_length(
    words: list[str],
    index: int,
    *,
    min_words: int,
    min_repeats: int,
    max_len: int,
) -> int:
    for length in range(max_len, min_words - 1, -1):
        if _repeat_count(words, index, length) >= min_repeats:
            return length
    return 0


def _repeat_count(words: list[str], index: int, length: int) -> int:
    phrase = words[index : index + length]
    count = 1
    start = index + length
    while start + length <= len(words) and words[start : start + length] == phrase:
        count += 1
        start += length
    return count


def join_reliable_segments(segments: Any) -> str:
    """Betrouwbare segmenttekst, met opeenvolgende herhaling ingekort."""

    parts: list[str] = []
    for segment in segments:
        text = reliable_segment_text(segment)
        if text:
            parts.append(text)
    return collapse_repeated_phrases(" ".join(parts))
