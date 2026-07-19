"""In-memory ``SpeechToTextCapability`` wired to fake capture."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from modules.capabilities.continuous_capture import AudioChunk, AudioChunkReceived
from modules.capabilities.speech_to_text import (
    SttEventHandler,
    TranscriptDelta,
    TranscriptDeltaReceived,
    TranscriptionSession,
    TranscriptionStatus,
    TranscriptionStatusChanged,
)


class FakeSpeechToText:
    def __init__(
        self,
        *,
        text_for_chunk: Callable[[AudioChunk], str],
        confidence: float = 1.0,
        is_final: bool = True,
    ) -> None:
        self._text_for_chunk = text_for_chunk
        self._confidence = confidence
        self._is_final = is_final
        self._handlers: dict[str, list[SttEventHandler]] = defaultdict(list)
        self._status: dict[str, TranscriptionStatus] = {}
        self._sequence: dict[str, int] = defaultdict(int)
        self._capture_handlers: dict[str, Callable[[Any], None]] = {}

    def start_session(
        self,
        *,
        capture_session_id: str,
        capture: Any,
        config: dict[str, Any] | None = None,
    ) -> TranscriptionSession:
        del config
        session_id = str(uuid.uuid4())
        self._status[session_id] = TranscriptionStatus.ACTIVE
        self._emit(session_id, TranscriptionStatusChanged(session_id, TranscriptionStatus.ACTIVE))

        def on_capture_event(event: object) -> None:
            if not isinstance(event, AudioChunkReceived):
                return
            if event.chunk.session_id != capture_session_id:
                return
            self._emit_delta(session_id, event.chunk)

        self._capture_handlers[session_id] = on_capture_event
        capture.subscribe(capture_session_id, on_capture_event)
        return TranscriptionSession(session_id=session_id)

    def subscribe(self, session_id: str, handler: SttEventHandler) -> None:
        self._handlers[session_id].append(handler)

    def unsubscribe(self, session_id: str, handler: SttEventHandler) -> None:
        handlers = self._handlers.get(session_id, [])
        if handler in handlers:
            handlers.remove(handler)

    def stop_session(self, session_id: str) -> None:
        self._status[session_id] = TranscriptionStatus.IDLE
        self._emit(session_id, TranscriptionStatusChanged(session_id, TranscriptionStatus.IDLE))

    def get_status(self, session_id: str) -> TranscriptionStatus:
        return self._status.get(session_id, TranscriptionStatus.IDLE)

    def _emit_delta(self, session_id: str, chunk: AudioChunk) -> None:
        self._sequence[session_id] += 1
        delta = TranscriptDelta(
            session_id=session_id,
            sequence=self._sequence[session_id],
            start_ms=chunk.start_ms,
            end_ms=chunk.end_ms,
            text=self._text_for_chunk(chunk),
            is_final=self._is_final,
            confidence=self._confidence,
        )
        self._emit(session_id, TranscriptDeltaReceived(delta))

    def _emit(self, session_id: str, event: object) -> None:
        for handler in list(self._handlers.get(session_id, [])):
            handler(event)
