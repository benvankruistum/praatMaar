"""Windows microfooncapture voor ``audio.continuous_capture``."""

from __future__ import annotations

import logging
import sys
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event, RLock, Thread
from typing import Any

import numpy as np

from modules._contract import CycleEvent, ModuleContext
from modules.capabilities.continuous_capture import (
    CAPABILITY_ID,
    CONTRACT_VERSION,
    AudioChunk,
    AudioChunkReceived,
    CaptureEventHandler,
    CaptureGap,
    CaptureSession,
    CaptureStatus,
    CaptureStatusChanged,
    CaptureStopped,
)
from modules.capabilities.registry import CapabilityRegistry

SAMPLE_RATE = 16_000
CHANNELS = 1
CHUNK_DURATION_MS = 3_000
CHUNK_OVERLAP_MS = 500
MAX_BUFFER_DURATION_S = 30.0

log = logging.getLogger("praatmaar.audio_capture")


@dataclass(frozen=True)
class BufferedWindow:
    start_ms: int
    samples: np.ndarray


class RingBuffer:
    """Thread-safe, begrensde float32-buffer die overflow expliciet meldt."""

    def __init__(
        self,
        max_duration_s: float,
        sample_rate: int,
        session_id: str = "",
    ) -> None:
        if max_duration_s <= 0:
            raise ValueError("max_duration_s moet groter dan nul zijn")
        if sample_rate <= 0:
            raise ValueError("sample_rate moet groter dan nul zijn")

        self._capacity = max(1, int(max_duration_s * sample_rate))
        self._sample_rate = sample_rate
        self._session_id = session_id
        self._samples = np.empty(0, dtype=np.float32)
        self._start_ms = 0
        self._lock = RLock()
        self.on_gap: Callable[[CaptureGap], None] | None = None

    @property
    def available_samples(self) -> int:
        with self._lock:
            return int(self._samples.size)

    def write(self, samples: np.ndarray, start_ms: int) -> None:
        incoming = np.asarray(samples, dtype=np.float32).reshape(-1)
        if incoming.size == 0:
            return

        gap: CaptureGap | None = None
        with self._lock:
            if self._samples.size == 0:
                self._start_ms = start_ms
            combined = np.concatenate((self._samples, incoming))
            overflow = max(0, int(combined.size) - self._capacity)
            if overflow:
                gap_start_ms = self._start_ms
                gap_end_ms = gap_start_ms + round(overflow * 1000 / self._sample_rate)
                gap = CaptureGap(
                    session_id=self._session_id,
                    start_ms=gap_start_ms,
                    end_ms=gap_end_ms,
                    reason="ring_buffer_overflow",
                )
                combined = combined[overflow:]
                self._start_ms = gap_end_ms
            self._samples = combined

        if gap is not None and self.on_gap is not None:
            self.on_gap(gap)

    def read_window(
        self,
        sample_count: int,
        retain_samples: int = 0,
    ) -> BufferedWindow | None:
        if sample_count <= 0:
            raise ValueError("sample_count moet groter dan nul zijn")
        if retain_samples < 0 or retain_samples >= sample_count:
            raise ValueError("retain_samples moet tussen nul en sample_count liggen")

        with self._lock:
            if self._samples.size < sample_count:
                return None
            start_ms = self._start_ms
            samples = self._samples[:sample_count].copy()
            consumed = sample_count - retain_samples
            self._samples = self._samples[consumed:]
            self._start_ms += round(consumed * 1000 / self._sample_rate)
        return BufferedWindow(start_ms=start_ms, samples=samples)


@dataclass
class _CaptureState:
    session_id: str
    buffer: RingBuffer
    stop_event: Event
    handlers: list[CaptureEventHandler]
    status: CaptureStatus = CaptureStatus.IDLE
    status_message: str | None = None
    stream: Any | None = None
    worker: Thread | None = None
    captured_samples: int = 0


class AudioCaptureEngine:
    """Continue 16-kHz mono microfooncapture met overlappende PCM-vensters."""

    def __init__(
        self,
        *,
        sounddevice_module: Any | None = None,
        platform_name: str | None = None,
    ) -> None:
        self._sounddevice = sounddevice_module
        self._platform_name = platform_name if platform_name is not None else sys.platform
        self._sessions: dict[str, _CaptureState] = {}
        self._lock = RLock()

    def start_session(self, config: dict[str, Any] | None = None) -> CaptureSession:
        options = config or {}
        session_id = str(uuid.uuid4())
        max_buffer_duration_s = float(
            options.get("max_audio_buffer_duration_s", MAX_BUFFER_DURATION_S)
        )
        buffer = RingBuffer(max_buffer_duration_s, SAMPLE_RATE, session_id)
        state = _CaptureState(
            session_id=session_id,
            buffer=buffer,
            stop_event=Event(),
            handlers=[],
        )
        buffer.on_gap = lambda gap: self._publish(state, gap)
        with self._lock:
            self._sessions[session_id] = state

        self._set_status(state, CaptureStatus.STARTING)
        if self._platform_name != "win32":
            self._set_status(
                state,
                CaptureStatus.ERROR,
                "Continuous microphone capture is currently supported on Windows only.",
            )
            return CaptureSession(session_id=session_id)

        try:
            sounddevice = self._get_sounddevice()
            state.stream = sounddevice.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                callback=lambda data, frames, time_info, status: self._audio_callback(
                    state, data, frames, time_info, status
                ),
                device=options.get("device"),
                latency="low",
            )
            state.worker = Thread(
                target=self._worker,
                args=(state,),
                name=f"audio-capture-{session_id[:8]}",
                daemon=True,
            )
            state.worker.start()
            state.stream.start()
        except Exception as exc:
            state.stop_event.set()
            self._close_stream(state)
            self._set_status(state, CaptureStatus.ERROR, f"Microphone capture failed: {exc}")
            return CaptureSession(session_id=session_id)

        self._set_status(state, CaptureStatus.ACTIVE)
        return CaptureSession(session_id=session_id)

    def subscribe(self, session_id: str, handler: CaptureEventHandler) -> None:
        state = self._require_session(session_id)
        with self._lock:
            if handler not in state.handlers:
                state.handlers.append(handler)
            current_status = CaptureStatusChanged(
                session_id=state.session_id,
                status=state.status,
                message=state.status_message,
            )
        self._notify_handler(state, handler, current_status)

    def unsubscribe(self, session_id: str, handler: CaptureEventHandler) -> None:
        state = self._require_session(session_id)
        with self._lock:
            if handler in state.handlers:
                state.handlers.remove(handler)

    def stop_session(self, session_id: str) -> None:
        state = self._require_session(session_id)
        state.stop_event.set()
        self._close_stream(state)
        worker = state.worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=2)
        self._set_status(state, CaptureStatus.STOPPED)
        self._publish(state, CaptureStopped(session_id=session_id, reason="user"))

    def get_status(self, session_id: str) -> CaptureStatus:
        return self._require_session(session_id).status

    def shutdown(self) -> None:
        with self._lock:
            session_ids = list(self._sessions)
        for session_id in session_ids:
            state = self._require_session(session_id)
            if state.status not in {CaptureStatus.STOPPED, CaptureStatus.ERROR}:
                self.stop_session(session_id)

    def _get_sounddevice(self) -> Any:
        if self._sounddevice is None:
            import sounddevice

            self._sounddevice = sounddevice
        return self._sounddevice

    def _require_session(self, session_id: str) -> _CaptureState:
        with self._lock:
            state = self._sessions.get(session_id)
        if state is None:
            raise ValueError(f"Onbekende capture-sessie: {session_id}")
        return state

    def _audio_callback(
        self,
        state: _CaptureState,
        data: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        del time_info
        if state.stop_event.is_set():
            return
        if status:
            log.warning("Microfoonstatus voor sessie %s: %s", state.session_id, status)
        if getattr(status, "input_overflow", False):
            gap_start_ms = round(state.captured_samples * 1000 / SAMPLE_RATE)
            state.captured_samples += frames
            self._publish(
                state,
                CaptureGap(
                    session_id=state.session_id,
                    start_ms=gap_start_ms,
                    end_ms=round(state.captured_samples * 1000 / SAMPLE_RATE),
                    reason="input_overflow",
                ),
            )
        samples = np.asarray(data, dtype=np.float32).reshape(-1)
        if frames < samples.size:
            samples = samples[:frames]
        start_ms = round(state.captured_samples * 1000 / SAMPLE_RATE)
        state.captured_samples += int(samples.size)
        state.buffer.write(samples, start_ms=start_ms)

    def _worker(self, state: _CaptureState) -> None:
        sample_count = SAMPLE_RATE * CHUNK_DURATION_MS // 1000
        overlap_samples = SAMPLE_RATE * CHUNK_OVERLAP_MS // 1000
        while not state.stop_event.is_set():
            window = state.buffer.read_window(sample_count, overlap_samples)
            if window is None:
                state.stop_event.wait(0.01)
                continue
            end_ms = window.start_ms + CHUNK_DURATION_MS
            chunk = AudioChunk(
                session_id=state.session_id,
                chunk_id=str(uuid.uuid4()),
                start_ms=window.start_ms,
                end_ms=end_ms,
                sample_rate=SAMPLE_RATE,
                pcm_f32=window.samples.astype("<f4", copy=False).tobytes(),
            )
            self._publish(state, AudioChunkReceived(chunk=chunk))

    def _set_status(
        self,
        state: _CaptureState,
        status: CaptureStatus,
        message: str | None = None,
    ) -> None:
        state.status = status
        state.status_message = message
        self._publish(
            state,
            CaptureStatusChanged(
                session_id=state.session_id,
                status=status,
                message=message,
            ),
        )

    def _publish(self, state: _CaptureState, event: object) -> None:
        with self._lock:
            handlers = list(state.handlers)
        for handler in handlers:
            self._notify_handler(state, handler, event)

    @staticmethod
    def _notify_handler(
        state: _CaptureState,
        handler: CaptureEventHandler,
        event: object,
    ) -> None:
        try:
            handler(event)
        except Exception:
            log.exception("Capture-eventhandler faalde voor sessie %s", state.session_id)

    @staticmethod
    def _close_stream(state: _CaptureState) -> None:
        stream = state.stream
        state.stream = None
        if stream is None:
            return
        try:
            stream.stop()
        finally:
            stream.close()


class AudioCaptureModule:
    """Registreert de Windows microfooncapture-capability."""

    id = "audio-capture"

    def __init__(self) -> None:
        self._engine: AudioCaptureEngine | None = None
        self._capabilities: CapabilityRegistry | None = None

    def display_name_key(self) -> str:
        return "modules.audio_capture.name"

    def description_key(self) -> str:
        return "modules.audio_capture.description"

    def default_enabled(self) -> bool:
        return True

    def on_app_start(self, ctx: ModuleContext) -> None:
        self._engine = AudioCaptureEngine()
        self._capabilities = ctx.capabilities
        ctx.capabilities.register(
            capability_id=CAPABILITY_ID,
            provider=self._engine,
            owner_module_id=self.id,
            contract_version=CONTRACT_VERSION,
        )

    def on_event(self, event: CycleEvent) -> None:
        del event

    def on_app_shutdown(self) -> None:
        try:
            if self._engine is not None:
                self._engine.shutdown()
        finally:
            try:
                if self._capabilities is not None:
                    self._capabilities.unregister_owner(self.id)
            finally:
                self._engine = None
                self._capabilities = None
