"""Windows microfooncapture voor ``audio.continuous_capture``."""

from __future__ import annotations

import logging
import sys
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Event, RLock, Thread
from typing import Any

import numpy as np

from modules._builtin.audio_capture_mix import mix_mono_chunks, resample_mono, stereo_to_mono
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
    mic_stream: Any | None = None
    loopback_stream: Any | None = None
    worker: Thread | None = None
    captured_samples: int = 0
    loopback_enabled: bool = False
    loopback_sample_rate: int = SAMPLE_RATE
    mix_lock: RLock = field(default_factory=RLock)
    mic_pending: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float32))
    loopback_pending: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.float32))


class AudioCaptureEngine:
    """Continue 16-kHz mono capture (microfoon + optioneel WASAPI loopback)."""

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
            self._start_mic_stream(state, sounddevice, options)
            if options.get("enable_loopback"):
                self._try_start_loopback_stream(state, sounddevice, options)
            state.worker = Thread(
                target=self._worker,
                args=(state,),
                name=f"audio-capture-{session_id[:8]}",
                daemon=True,
            )
            state.worker.start()
            state.mic_stream.start()
            if state.loopback_stream is not None:
                state.loopback_stream.start()
        except Exception as exc:
            state.stop_event.set()
            self._close_streams(state)
            self._set_status(state, CaptureStatus.ERROR, f"Microphone capture failed: {exc}")
            return CaptureSession(session_id=session_id)

        self._set_status(state, CaptureStatus.ACTIVE)
        return CaptureSession(session_id=session_id)

    def _start_mic_stream(
        self, state: _CaptureState, sounddevice: Any, options: dict[str, Any]
    ) -> None:
        state.mic_stream = sounddevice.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=lambda data, frames, time_info, status: self._mic_stream_callback(
                state, data, frames, time_info, status
            ),
            finished_callback=lambda: self._mic_stream_finished(state),
            device=options.get("device"),
            latency="low",
        )

    def _try_start_loopback_stream(
        self, state: _CaptureState, sounddevice: Any, options: dict[str, Any]
    ) -> None:
        try:
            device, sample_rate, channels, extra_settings = self._resolve_loopback(
                sounddevice,
                options.get("loopback_device"),
            )
        except Exception as exc:
            log.warning(
                "Loopback niet beschikbaar voor sessie %s, alleen microfoon: %s",
                state.session_id,
                exc,
            )
            return

        try:
            state.loopback_stream = sounddevice.InputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="float32",
                callback=lambda data, frames, time_info, status: self._loopback_stream_callback(
                    state, data, frames, time_info, status
                ),
                finished_callback=lambda: self._loopback_stream_finished(state),
                device=device,
                extra_settings=extra_settings,
                latency="low",
            )
            state.loopback_enabled = True
            state.loopback_sample_rate = sample_rate
        except Exception as exc:
            log.warning(
                "Loopback starten mislukt voor sessie %s, alleen microfoon: %s",
                state.session_id,
                exc,
            )
            state.loopback_stream = None
            state.loopback_enabled = False

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
        self._close_streams(state)
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

    def _mic_stream_callback(
        self,
        state: _CaptureState,
        data: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        try:
            self._mic_audio_callback(state, data, frames, time_info, status)
        except Exception as exc:
            log.exception("Microfooncapture faalde voor sessie %s", state.session_id)
            self._fail_capture(state, f"Microphone capture failed: {exc}")

    def _loopback_stream_callback(
        self,
        state: _CaptureState,
        data: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        try:
            self._loopback_audio_callback(state, data, frames, time_info, status)
        except Exception as exc:
            log.warning("Loopbackcapture faalde voor sessie %s: %s", state.session_id, exc)
            self._disable_loopback(state)

    def _mic_audio_callback(
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
        samples = stereo_to_mono(np.asarray(data, dtype=np.float32))
        if frames < samples.size:
            samples = samples[:frames]
        self._append_mic_samples(state, samples)

    def _loopback_audio_callback(
        self,
        state: _CaptureState,
        data: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        del time_info
        if state.stop_event.is_set() or not state.loopback_enabled:
            return
        if status:
            log.warning("Loopbackstatus voor sessie %s: %s", state.session_id, status)
        samples = stereo_to_mono(np.asarray(data, dtype=np.float32))
        if frames < samples.size:
            samples = samples[:frames]
        samples = resample_mono(samples, from_rate=state.loopback_sample_rate)
        self._append_loopback_samples(state, samples)

    def _append_mic_samples(self, state: _CaptureState, samples: np.ndarray) -> None:
        with state.mix_lock:
            state.mic_pending = np.concatenate((state.mic_pending, samples))
            self._flush_mixed_samples(state)

    def _append_loopback_samples(self, state: _CaptureState, samples: np.ndarray) -> None:
        with state.mix_lock:
            state.loopback_pending = np.concatenate((state.loopback_pending, samples))
            self._flush_mixed_samples(state)

    def _flush_mixed_samples(self, state: _CaptureState) -> None:
        while True:
            if state.loopback_enabled:
                count = min(state.mic_pending.size, state.loopback_pending.size)
                if count <= 0:
                    break
                mic_chunk = state.mic_pending[:count]
                loop_chunk = state.loopback_pending[:count]
                state.mic_pending = state.mic_pending[count:]
                state.loopback_pending = state.loopback_pending[count:]
                mixed = mix_mono_chunks(mic_chunk, loop_chunk)
            else:
                count = state.mic_pending.size
                if count <= 0:
                    break
                mixed = state.mic_pending[:count]
                state.mic_pending = state.mic_pending[count:]

            start_ms = round(state.captured_samples * 1000 / SAMPLE_RATE)
            state.captured_samples += int(mixed.size)
            state.buffer.write(mixed, start_ms=start_ms)
            if state.status == CaptureStatus.ACTIVE and mixed.size > 0:
                from indicator import push_level

                push_level(float(np.sqrt(np.mean(np.square(mixed)))))

    def _mic_stream_finished(self, state: _CaptureState) -> None:
        if not state.stop_event.is_set():
            self._fail_capture(state, "Microphone device disconnected.")

    def _loopback_stream_finished(self, state: _CaptureState) -> None:
        if state.stop_event.is_set():
            return
        log.warning("Loopback device disconnected voor sessie %s", state.session_id)
        self._disable_loopback(state)

    def _disable_loopback(self, state: _CaptureState) -> None:
        if not state.loopback_enabled:
            return
        state.loopback_enabled = False
        state.loopback_pending = np.empty(0, dtype=np.float32)
        stream = state.loopback_stream
        state.loopback_stream = None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

    def _fail_capture(self, state: _CaptureState, message: str) -> None:
        with self._lock:
            if state.status in {CaptureStatus.ERROR, CaptureStatus.STOPPED}:
                return
            state.stop_event.set()
        self._set_status(state, CaptureStatus.ERROR, message)
        self._publish(state, CaptureStopped(session_id=state.session_id, reason="error"))

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
    def _resolve_loopback(
        sounddevice: Any,
        loopback_device: int | None,
    ) -> tuple[int, int, int, Any]:
        wasapi_settings = getattr(sounddevice, "WasapiSettings", None)
        if wasapi_settings is None:
            raise RuntimeError("WASAPI loopback is not available in this sounddevice build.")

        device = loopback_device
        if device is None:
            default = sounddevice.default.device
            if isinstance(default, (tuple, list)) and len(default) >= 2:
                device = default[1]
            else:
                device = sounddevice.default.device[1]
        if device is None:
            raise RuntimeError("No default output device for loopback capture.")

        info = sounddevice.query_devices(device)
        channels = int(info.get("max_input_channels") or info.get("max_output_channels") or 2)
        channels = max(1, min(2, channels))
        sample_rate = int(info.get("default_samplerate") or SAMPLE_RATE)
        return device, sample_rate, channels, wasapi_settings(loopback=True)

    @staticmethod
    def _close_streams(state: _CaptureState) -> None:
        for attr in ("mic_stream", "loopback_stream"):
            stream = getattr(state, attr)
            setattr(state, attr, None)
            if stream is None:
                continue
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
