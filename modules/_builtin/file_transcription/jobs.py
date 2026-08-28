"""Sequentiele bestandstranscriptie via SharedWhisper (geen Qt)."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import i18n
from modules._contract import CycleEvent, CycleEventType
from modules.whisper import SharedWhisper

SOURCE = "file"
SLICE_SECONDS = 30.0
SAMPLE_RATE = 16_000
POLL_S = 0.25


class FileItemStatus(StrEnum):
    WAIT = "wait"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class DialogState(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused-for-dictation"
    CANCELLING = "cancelling"


@dataclass
class FileItem:
    path: Path
    status: FileItemStatus = FileItemStatus.WAIT
    saved_path: Path | None = None
    transcript: str | None = None
    error_key: str | None = None

    @property
    def display_name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class FileBatchContext:
    destination_name: str | None
    save_discrete: Callable[[str], Path]


class FileJobHost(Protocol):
    def is_busy(self) -> bool: ...

    def transcribe_kwargs(self) -> dict[str, Any]: ...

    def emit(self, event: CycleEvent) -> None: ...

    def capture_batch(self) -> FileBatchContext: ...

    def destination_display(self) -> tuple[str | None, str]: ...

    def destinations(self) -> list[dict[str, Any]]: ...


DecodeFn = Callable[[Path], Any]
SleepFn = Callable[[float], None]
ChangeFn = Callable[[], None]


class FileTranscriptionQueue:
    """Wachtrij: decode buiten de lock, transcribeer in plakjes, yield aan dicteren."""

    def __init__(
        self,
        *,
        whisper: SharedWhisper,
        host: FileJobHost,
        decode_fn: DecodeFn | None = None,
        sleep_fn: SleepFn = time.sleep,
        poll_s: float = POLL_S,
        slice_seconds: float = SLICE_SECONDS,
        sample_rate: int = SAMPLE_RATE,
        on_change: ChangeFn | None = None,
    ) -> None:
        self._whisper = whisper
        self._host = host
        self._decode_fn = decode_fn or _default_decode
        self._sleep = sleep_fn
        self._poll_s = poll_s
        self._slice_seconds = slice_seconds
        self._sample_rate = sample_rate
        self._on_change = on_change
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self.items: list[FileItem] = []
        self.dialog_state = DialogState.IDLE
        self._batch: FileBatchContext | None = None

    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self, paths: Sequence[Path]) -> str | None:
        """Start een batch. Geeft een i18n-key terug bij weigering."""

        if self.is_running():
            return "modules.file_transcription.busy"
        if not self._whisper.is_ready:
            return "model.load_failed"
        if self._host.is_busy():
            return "modules.file_transcription.busy"

        unique: list[Path] = []
        seen: set[str] = set()
        for raw in paths:
            path = Path(raw)
            key = str(path)
            try:
                key = str(path.resolve())
            except OSError:
                pass
            if key in seen:
                continue
            seen.add(key)
            unique.append(path)
        if not unique:
            return "modules.file_transcription.select_first"

        self._cancel.clear()
        self.items = [FileItem(path=path) for path in unique]
        self._batch = self._host.capture_batch()
        self.dialog_state = DialogState.BUSY
        self._notify()
        self._thread = threading.Thread(
            target=self._run,
            name="file-transcription",
            daemon=False,
        )
        self._thread.start()
        return None

    def cancel(self) -> None:
        if not self.is_running():
            return
        self._cancel.set()
        self.dialog_state = DialogState.CANCELLING
        self._notify()

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def shutdown(self) -> None:
        self.cancel()
        self.join(timeout=30.0)

    def _run(self) -> None:
        try:
            for item in self.items:
                if self._cancel.is_set():
                    if item.status is FileItemStatus.WAIT:
                        item.status = FileItemStatus.CANCELLED
                        self._notify()
                    continue
                self._process_item(item)
        except Exception:
            # Mag de dicteercyclus nooit breken.
            pass
        finally:
            self.dialog_state = DialogState.IDLE
            self._notify()

    def _process_item(self, item: FileItem) -> None:
        session_id = str(uuid.uuid4())
        language = str(self._host.transcribe_kwargs().get("language") or "")
        batch = self._batch
        destination = batch.destination_name if batch is not None else None
        audio_path = str(item.path)

        item.status = FileItemStatus.RUNNING
        self._set_state(DialogState.BUSY)

        if item.path.suffix.lower() != ".wav":
            self._fail_item(
                item,
                session_id,
                "modules.file_transcription.invalid_format",
                audio_path=audio_path,
                language=language,
            )
            return

        self._host.emit(
            CycleEvent(
                type=CycleEventType.CYCLE_TRANSCRIBING,
                session_id=session_id,
                source=SOURCE,
                language=language or None,
                audio_path=audio_path,
            )
        )

        try:
            audio = self._decode_fn(item.path)
        except Exception:
            self._fail_item(
                item,
                session_id,
                "modules.file_transcription.unreadable",
                audio_path=audio_path,
                language=language,
                already_transcribing=True,
            )
            return

        samples = _as_1d(audio)
        if samples.size == 0:
            self._fail_item(
                item,
                session_id,
                "modules.file_transcription.empty_audio",
                audio_path=audio_path,
                language=language,
                already_transcribing=True,
            )
            return

        texts: list[str] = []
        slice_len = max(1, int(self._slice_seconds * self._sample_rate))
        for start in range(0, samples.size, slice_len):
            if self._cancel.is_set() and start > 0:
                break
            piece = samples[start : start + slice_len]
            if piece.size == 0:
                continue
            chunk = self._transcribe_slice(piece)
            if chunk is None:
                break
            if chunk:
                texts.append(chunk)

        transcript = " ".join(texts).strip()
        if self._cancel.is_set() and not transcript:
            item.status = FileItemStatus.CANCELLED
            self._host.emit(
                CycleEvent(
                    type=CycleEventType.CYCLE_IDLE,
                    session_id=session_id,
                    source=SOURCE,
                    audio_path=audio_path,
                )
            )
            self._notify()
            return
        if not transcript:
            self._fail_item(
                item,
                session_id,
                "modules.file_transcription.empty_audio",
                audio_path=audio_path,
                language=language,
                already_transcribing=True,
            )
            return

        self._host.emit(
            CycleEvent(
                type=CycleEventType.CYCLE_COMPLETED,
                session_id=session_id,
                source=SOURCE,
                transcript=transcript,
                language=language or None,
                destination=destination,
                audio_path=audio_path,
            )
        )

        saved: Path | None = None
        if batch is not None:
            try:
                saved = batch.save_discrete(transcript)
            except OSError:
                self._fail_item(
                    item,
                    session_id,
                    "modules.file_transcription.save_error",
                    audio_path=audio_path,
                    language=language,
                    already_transcribing=True,
                    completed=True,
                )
                return

        if saved is not None:
            self._host.emit(
                CycleEvent(
                    type=CycleEventType.TRANSCRIPT_SAVED,
                    session_id=session_id,
                    source=SOURCE,
                    transcript=transcript,
                    path=str(saved),
                    destination=destination,
                    language=language or None,
                    audio_path=audio_path,
                )
            )

        self._host.emit(
            CycleEvent(
                type=CycleEventType.CYCLE_IDLE,
                session_id=session_id,
                source=SOURCE,
            )
        )
        item.transcript = transcript
        item.saved_path = saved
        item.status = FileItemStatus.DONE
        self._notify()

    def _transcribe_slice(self, audio: Any) -> str | None:
        kwargs = dict(self._host.transcribe_kwargs())
        while True:
            if self._cancel.is_set():
                return None
            if self._whisper.dictation_active or self._host.is_busy():
                self._set_state(DialogState.PAUSED)
                self._sleep(self._poll_s)
                continue
            with self._whisper.try_locked_model() as model:
                if model is None:
                    self._set_state(DialogState.PAUSED)
                    self._sleep(self._poll_s)
                    continue
                self._set_state(DialogState.BUSY)
                segments, _info = model.transcribe(audio, **kwargs)
                return _join_segments(segments)

    def _fail_item(
        self,
        item: FileItem,
        session_id: str,
        error_key: str,
        *,
        audio_path: str,
        language: str,
        already_transcribing: bool = False,
        completed: bool = False,
    ) -> None:
        del already_transcribing, completed
        item.status = FileItemStatus.ERROR
        item.error_key = error_key
        message = i18n.t(error_key)
        self._host.emit(
            CycleEvent(
                type=CycleEventType.CYCLE_ERROR,
                session_id=session_id,
                source=SOURCE,
                error=message,
                language=language or None,
                audio_path=audio_path,
            )
        )
        self._host.emit(
            CycleEvent(
                type=CycleEventType.CYCLE_IDLE,
                session_id=session_id,
                source=SOURCE,
            )
        )
        self._notify()

    def _set_state(self, state: DialogState) -> None:
        if self._cancel.is_set() and state is not DialogState.IDLE:
            state = DialogState.CANCELLING
        if self.dialog_state is state:
            return
        self.dialog_state = state
        self._notify()

    def _notify(self) -> None:
        callback = self._on_change
        if callback is not None:
            callback()


def _join_segments(segments: Any) -> str:
    parts: list[str] = []
    for segment in segments:
        text = str(getattr(segment, "text", "")).strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()


def _as_1d(audio: Any) -> Any:
    import numpy as np

    array = np.asarray(audio, dtype=np.float32).reshape(-1)
    return array


def _default_decode(path: Path) -> Any:
    from faster_whisper.audio import decode_audio

    return decode_audio(str(path), sampling_rate=SAMPLE_RATE)
