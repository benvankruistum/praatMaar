"""In-memory ``ContinuousCaptureCapability`` for tests."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from modules.capabilities.continuous_capture import (
    AudioChunk,
    AudioChunkReceived,
    CaptureEventHandler,
    CaptureSession,
    CaptureStatus,
    CaptureStatusChanged,
    CaptureStopped,
)

DEFAULT_SAMPLE_RATE = 16000


class FakeContinuousCapture:
    def __init__(self, *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
        self._sample_rate = sample_rate
        self._handlers: dict[str, list[CaptureEventHandler]] = defaultdict(list)
        self._status: dict[str, CaptureStatus] = {}
        self._elapsed_ms: dict[str, int] = defaultdict(int)
        self._chunk_counter: dict[str, int] = defaultdict(int)

    def start_session(self, config: dict[str, Any] | None = None) -> CaptureSession:
        del config
        session_id = str(uuid.uuid4())
        self._status[session_id] = CaptureStatus.ACTIVE
        self._emit(session_id, CaptureStatusChanged(session_id, CaptureStatus.ACTIVE))
        return CaptureSession(session_id=session_id)

    def subscribe(self, session_id: str, handler: CaptureEventHandler) -> None:
        self._handlers[session_id].append(handler)

    def unsubscribe(self, session_id: str, handler: CaptureEventHandler) -> None:
        handlers = self._handlers.get(session_id, [])
        if handler in handlers:
            handlers.remove(handler)

    def stop_session(self, session_id: str) -> None:
        self._status[session_id] = CaptureStatus.STOPPED
        self._emit(session_id, CaptureStopped(session_id, reason="user"))
        self._emit(session_id, CaptureStatusChanged(session_id, CaptureStatus.STOPPED))

    def get_status(self, session_id: str) -> CaptureStatus:
        return self._status.get(session_id, CaptureStatus.IDLE)

    def emit_seconds(self, seconds: float, *, session_id: str | None = None) -> AudioChunk:
        """Push a synthetic chunk and emit ``AudioChunkReceived``."""
        if session_id is None:
            active = [sid for sid, st in self._status.items() if st == CaptureStatus.ACTIVE]
            if len(active) != 1:
                raise ValueError("exactly one active session required when session_id is omitted")
            session_id = active[0]

        duration_ms = int(seconds * 1000)
        start_ms = self._elapsed_ms[session_id]
        end_ms = start_ms + duration_ms
        self._elapsed_ms[session_id] = end_ms

        sample_count = int(seconds * self._sample_rate)
        pcm_f32 = b"\x00" * (sample_count * 4)

        self._chunk_counter[session_id] += 1
        chunk = AudioChunk(
            session_id=session_id,
            chunk_id=str(self._chunk_counter[session_id]),
            start_ms=start_ms,
            end_ms=end_ms,
            sample_rate=self._sample_rate,
            pcm_f32=pcm_f32,
            source="fake",
        )
        self._emit(session_id, AudioChunkReceived(chunk))
        return chunk

    def _emit(self, session_id: str, event: object) -> None:
        for handler in list(self._handlers.get(session_id, [])):
            handler(event)
