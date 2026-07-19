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
        self.stream: FakeInputStream | None = None

    def InputStream(self, **kwargs: Any) -> FakeInputStream:  # noqa: N802
        self.stream = FakeInputStream(**kwargs)
        return self.stream


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
