"""Recovery re-transcribe acties (extract uit dictation)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import destinations
import i18n
import recovery
from modules import CycleEvent, CycleEventType


def save_transcript_routed(
    text: str,
    *,
    active_destination: str | None,
    destinations_list: list[dict[str, Any]],
) -> Path:
    """Slaat transcript op in de actieve bestemmingsmap of de defaultmap."""

    destination = destinations.find_destination(active_destination, destinations_list)
    append_path = destinations.resolve_append_file(destination)
    if append_path is not None:
        return recovery.append_transcript(text, append_path)

    directory = destinations.resolve_save_dir(
        active_destination,
        destinations_list,
        recovery.transcripts_dir(),
    )
    return recovery.save_transcript(text, directory=directory)


def retranscribe_recovery_wav(
    path: Path,
    *,
    session: Any,
    shared_whisper: Any,
    module_bus: Any,
    language: str,
    mode: str,
    active_destination: str | None,
    destinations_list: list[dict[str, Any]],
    auto_paste: bool,
    paste_delay_seconds: float,
    host_obj: Any,
    copy_text: Callable[[str], None],
    wait_until_modifiers_clear: Callable[[], None],
) -> str:
    """
    Transcribeert een recovery-WAV met het geladen model.

    Blokkerend — aanroepen vanaf een achtergrondthread.
    """

    if session.is_recording or session.is_processing:
        raise RuntimeError(i18n.t("recovery.busy"))
    if not shared_whisper.is_ready:
        raise RuntimeError(i18n.t("model.load_failed"))

    resolved = path.resolve()
    if resolved.parent != recovery.recovery_dir().resolve():
        raise ValueError(i18n.t("recovery.invalid_file"))

    session_id = str(uuid.uuid4())
    module_bus.emit(
        CycleEvent(
            type=CycleEventType.CYCLE_TRANSCRIBING,
            session_id=session_id,
            language=language,
            mode=mode,
            recovery_path=str(resolved),
            source="recovery",
        )
    )

    with shared_whisper.locked_model() as whisper_model:
        segments, _info = whisper_model.transcribe(
            str(resolved),
            **session.transcribe_kwargs(),
        )
        text_parts: list[str] = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                text_parts.append(text)
    transcript = " ".join(text_parts).strip()
    if not transcript:
        module_bus.emit(
            CycleEvent(
                type=CycleEventType.CYCLE_IDLE,
                session_id=session_id,
                source="recovery",
            )
        )
        raise RuntimeError(i18n.t("rec.no_speech"))

    module_bus.emit(
        CycleEvent(
            type=CycleEventType.CYCLE_COMPLETED,
            session_id=session_id,
            transcript=transcript,
            destination=active_destination,
            language=language,
            mode=mode,
            recovery_path=str(resolved),
            source="recovery",
        )
    )

    saved_path: Path | None = None
    try:
        saved_path = save_transcript_routed(
            transcript,
            active_destination=active_destination,
            destinations_list=destinations_list,
        )
    except OSError as exc:
        print(i18n.t("rec.save_warn", error=exc))

    if saved_path is not None:
        module_bus.emit(
            CycleEvent(
                type=CycleEventType.TRANSCRIPT_SAVED,
                session_id=session_id,
                transcript=transcript,
                path=str(saved_path),
                destination=active_destination,
                language=language,
                mode=mode,
                recovery_path=str(resolved),
                source="recovery",
            )
        )

    module_bus.emit(
        CycleEvent(
            type=CycleEventType.RECOVERY_RETRANSCRIBED,
            session_id=session_id,
            transcript=transcript,
            path=str(saved_path) if saved_path is not None else None,
            recovery_path=str(resolved),
            source="recovery",
        )
    )

    try:
        copy_text(transcript)
    except Exception as exc:
        print(i18n.t("rec.clipboard_warn", error=exc))

    if auto_paste:
        wait_until_modifiers_clear()
        time.sleep(paste_delay_seconds)
        try:
            host_obj.paste()
        except Exception as exc:
            print(i18n.t("rec.paste_failed"))
            print(i18n.t("rec.error", error=exc))

    module_bus.emit(
        CycleEvent(
            type=CycleEventType.CYCLE_IDLE,
            session_id=session_id,
            source="recovery",
        )
    )

    return transcript
