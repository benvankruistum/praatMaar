"""Tests voor de Windows-microfoonengine zonder echte sounddevice-stream."""

from __future__ import annotations

from threading import Event
from typing import Any

import numpy as np

from modules._builtin.audio_capture import (
    CHUNK_DURATION_MS,
    CHUNK_OVERLAP_MS,
    SAMPLE_RATE,
    AudioCaptureEngine,
)
from modules.capabilities.continuous_capture import (
    AudioChunkReceived,
    CaptureGap,
    CaptureStatus,
    CaptureStatusChanged,
    CaptureStopped,
)


class FakeInputStream:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


class FakeSoundDevice:
    def __init__(self) -> None:
        self.streams: list[FakeInputStream] = []

    def InputStream(self, **kwargs: Any) -> FakeInputStream:  # noqa: N802
        stream = FakeInputStream(**kwargs)
        self.streams.append(stream)
        return stream

    @property
    def stream(self) -> FakeInputStream | None:
        return self.streams[0] if self.streams else None


def test_session_config_controls_ring_buffer_capacity() -> None:
    engine = AudioCaptureEngine(
        sounddevice_module=FakeSoundDevice(),
        platform_name="win32",
    )

    session = engine.start_session({"max_audio_buffer_duration_s": 0.25})

    state = engine._require_session(session.session_id)
    state.buffer.write(np.zeros(SAMPLE_RATE // 2, dtype=np.float32), start_ms=0)
    assert state.buffer.available_samples == SAMPLE_RATE // 4
    engine.stop_session(session.session_id)


def test_engine_emits_three_second_float32_chunk() -> None:
    sounddevice = FakeSoundDevice()
    engine = AudioCaptureEngine(
        sounddevice_module=sounddevice,
        platform_name="win32",
    )
    session = engine.start_session()
    events: list[object] = []
    chunk_ready = Event()

    def receive(event: object) -> None:
        events.append(event)
        if isinstance(event, AudioChunkReceived):
            chunk_ready.set()

    engine.subscribe(session.session_id, receive)
    assert sounddevice.stream is not None
    callback = sounddevice.stream.kwargs["callback"]
    callback(
        np.zeros((SAMPLE_RATE * CHUNK_DURATION_MS // 1000, 1), dtype=np.float32),
        SAMPLE_RATE * CHUNK_DURATION_MS // 1000,
        None,
        None,
    )

    assert chunk_ready.wait(timeout=1)
    chunks = [event.chunk for event in events if isinstance(event, AudioChunkReceived)]
    assert len(chunks) == 1
    assert chunks[0].start_ms == 0
    assert chunks[0].end_ms == CHUNK_DURATION_MS
    assert len(chunks[0].pcm_f32) == SAMPLE_RATE * CHUNK_DURATION_MS * 4 // 1000
    assert CHUNK_OVERLAP_MS == 500

    engine.stop_session(session.session_id)


def test_start_session_passes_microphone_device() -> None:
    sounddevice = FakeSoundDevice()
    engine = AudioCaptureEngine(
        sounddevice_module=sounddevice,
        platform_name="win32",
    )

    session = engine.start_session({"device": 3})

    assert sounddevice.stream is not None
    assert sounddevice.stream.kwargs["device"] == 3
    engine.stop_session(session.session_id)


def test_loopback_failure_falls_back_to_microphone_only() -> None:
    class LoopbackFailSoundDevice(FakeSoundDevice):
        def InputStream(self, **kwargs: Any) -> FakeInputStream:  # noqa: N802
            if kwargs.get("extra_settings") is not None:
                raise RuntimeError("loopback unavailable")
            return super().InputStream(**kwargs)

    sounddevice = LoopbackFailSoundDevice()
    engine = AudioCaptureEngine(
        sounddevice_module=sounddevice,
        platform_name="win32",
    )
    session = engine.start_session({"enable_loopback": True})
    state = engine._require_session(session.session_id)

    assert engine.get_status(session.session_id) == CaptureStatus.ACTIVE
    assert state.loopback_enabled is False
    assert len(sounddevice.streams) == 1

    engine.stop_session(session.session_id)


def test_loopback_and_microphone_are_mixed() -> None:
    sounddevice = FakeSoundDevice()
    sounddevice.WasapiSettings = lambda *, loopback: {"loopback": loopback}
    sounddevice.default = type("Default", (), {"device": (None, 7)})()
    sounddevice.query_devices = staticmethod(
        lambda _device: {
            "max_input_channels": 2,
            "default_samplerate": 16000,
        }
    )

    engine = AudioCaptureEngine(
        sounddevice_module=sounddevice,
        platform_name="win32",
    )
    session = engine.start_session({"enable_loopback": True})
    events: list[object] = []
    chunk_ready = Event()

    def receive(event: object) -> None:
        events.append(event)
        if isinstance(event, AudioChunkReceived):
            chunk_ready.set()

    engine.subscribe(session.session_id, receive)

    mic_callback = sounddevice.streams[0].kwargs["callback"]
    loop_callback = sounddevice.streams[1].kwargs["callback"]
    frames = SAMPLE_RATE * CHUNK_DURATION_MS // 1000
    mic_callback(
        np.full((frames, 1), 1.0, dtype=np.float32),
        frames,
        None,
        None,
    )
    loop_callback(
        np.full((frames, 1), 1.0, dtype=np.float32),
        frames,
        None,
        None,
    )

    assert chunk_ready.wait(timeout=1) or any(
        isinstance(event, AudioChunkReceived) for event in events
    )
    chunks = [event.chunk for event in events if isinstance(event, AudioChunkReceived)]
    assert chunks
    samples = np.frombuffer(chunks[0].pcm_f32, dtype="<f4")
    assert samples.size > 0
    assert float(samples.mean()) == 1.0

    engine.stop_session(session.session_id)


def test_non_windows_session_enters_error_status() -> None:
    engine = AudioCaptureEngine(
        sounddevice_module=FakeSoundDevice(),
        platform_name="linux",
    )

    session = engine.start_session()

    assert engine.get_status(session.session_id) == CaptureStatus.ERROR


def test_subscribe_replays_current_error_status_and_message() -> None:
    engine = AudioCaptureEngine(
        sounddevice_module=FakeSoundDevice(),
        platform_name="linux",
    )
    session = engine.start_session()
    events: list[object] = []

    engine.subscribe(session.session_id, events.append)

    assert events == [
        CaptureStatusChanged(
            session_id=session.session_id,
            status=CaptureStatus.ERROR,
            message="Continuous microphone capture is currently supported on Windows only.",
        )
    ]


def test_input_overflow_emits_gap_before_captured_samples() -> None:
    sounddevice = FakeSoundDevice()
    engine = AudioCaptureEngine(
        sounddevice_module=sounddevice,
        platform_name="win32",
    )
    session = engine.start_session()
    events: list[object] = []
    engine.subscribe(session.session_id, events.append)
    assert sounddevice.stream is not None
    callback = sounddevice.stream.kwargs["callback"]
    frames = SAMPLE_RATE // 10
    status = type("Status", (), {"input_overflow": True})()

    callback(
        np.zeros((frames, 1), dtype=np.float32),
        frames,
        None,
        status,
    )

    assert (
        CaptureGap(
            session_id=session.session_id,
            start_ms=0,
            end_ms=100,
            reason="input_overflow",
        )
        in events
    )
    assert engine._require_session(session.session_id).buffer.read_window(frames).start_ms == 100

    engine.stop_session(session.session_id)


def test_callback_failure_marks_capture_error_and_stopped() -> None:
    sounddevice = FakeSoundDevice()
    engine = AudioCaptureEngine(
        sounddevice_module=sounddevice,
        platform_name="win32",
    )
    session = engine.start_session()
    events: list[object] = []
    engine.subscribe(session.session_id, events.append)
    state = engine._require_session(session.session_id)

    def fail_write(_samples: np.ndarray, start_ms: int) -> None:
        del start_ms
        raise RuntimeError("device disappeared")

    state.buffer.write = fail_write
    assert sounddevice.stream is not None
    callback = sounddevice.stream.kwargs["callback"]
    callback(np.zeros((10, 1), dtype=np.float32), 10, None, None)

    assert engine.get_status(session.session_id) == CaptureStatus.ERROR
    assert any(
        isinstance(event, CaptureStatusChanged)
        and event.status == CaptureStatus.ERROR
        and "device disappeared" in (event.message or "")
        for event in events
    )
    assert CaptureStopped(session.session_id, reason="error") in events
