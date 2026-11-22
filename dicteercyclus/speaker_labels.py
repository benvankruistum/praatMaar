"""Zet Whisper-segmenten om in regels met een anoniem sprekerlabel."""

from __future__ import annotations

from typing import Any

from modules.capabilities.speaker_detection import (
    AudioSource,
    TranscriptSegment,
)
from whisper_segments import collapse_repeated_phrases


def format_transcript_with_speakers(
    provider: Any,
    session_id: str,
    notes: list[dict[str, Any]],
) -> str | None:
    """Labelt gehouden segmenten. ``None`` als er niets te labelen valt."""

    kept = [note for note in notes if note.get("kept") and str(note.get("text") or "").strip()]
    if not kept:
        return None

    lines: list[str] = []
    current: str | None = None
    bucket: list[str] = []

    def flush() -> None:
        nonlocal current, bucket
        if not bucket:
            return
        body = collapse_repeated_phrases(" ".join(bucket))
        bucket = []
        if not body:
            return
        if current:
            lines.append(f"[{current}] {body}")
        else:
            lines.append(body)

    for note in kept:
        text = str(note.get("text") or "").strip()
        label = _speaker_id(provider, session_id, note)
        if bucket and label != current:
            flush()
        current = label
        bucket.append(text)
    flush()
    return "\n".join(lines) if lines else None


def _speaker_id(provider: Any, session_id: str, note: dict[str, Any]) -> str | None:
    start_ms = _ms(note.get("start_s"))
    end_ms = _ms(note.get("end_s"))
    try:
        assignment = provider.assign_speaker(
            TranscriptSegment(
                text=str(note.get("text") or ""),
                session_id=session_id,
                source=AudioSource.MICROPHONE,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )
    except Exception:
        return None
    speaker = str(getattr(assignment, "speaker_id", "") or "").strip()
    if not speaker or speaker == "unknown":
        return None
    return speaker


def _ms(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(float(value) * 1000)
