"""Tests for WASAPI loopback helper and capture wiring."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from modules._builtin.audio_capture import AudioCaptureEngine
from modules._builtin.wasapi_loopback import (
    list_loopback_output_devices,
    resolve_loopback_device_info,
)
from modules.capabilities.continuous_capture import CaptureStatus
from tests.test_audio_capture_engine import FakeSoundDevice


class FakeWasapiModule:
    """Minimal stand-in for modules._builtin.wasapi_loopback."""

    @staticmethod
    def is_available() -> bool:
        return True

    @staticmethod
    def resolve_loopback_device_info(loopback_device: int | None) -> dict[str, Any]:
        index = 13 if loopback_device is None else int(loopback_device)
        return {
            "index": index,
            "name": "Fake Speakers [Loopback]",
            "maxInputChannels": 2,
            "defaultSampleRate": 48000,
            "isLoopbackDevice": True,
        }

    class WasapiLoopbackStream:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.sample_rate = int(kwargs["device_info"]["defaultSampleRate"])
            self.started = False
            self.stopped = False
            self.closed = False
            self._callback = kwargs["callback"]

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        def close(self) -> None:
            self.closed = True

        def push(self, frames: int = 480) -> None:
            data = np.zeros((frames, 2), dtype=np.float32)
            data[:, 0] = 0.2
            self._callback(data, frames, None, None)


def test_list_devices_includes_default_and_loopbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePa:
        def get_loopback_device_info_generator(self):
            yield {
                "index": 13,
                "name": "Speakers (Realtek(R) Audio) [Loopback]",
                "maxInputChannels": 2,
                "defaultSampleRate": 48000,
                "isLoopbackDevice": True,
            }
            yield {
                "index": 14,
                "name": "Odyssey G91SD [Loopback]",
                "maxInputChannels": 2,
                "defaultSampleRate": 48000,
                "isLoopbackDevice": True,
            }

        def terminate(self) -> None:
            pass

    options = list_loopback_output_devices(
        default_label="Windows-standaard",
        pyaudio_factory=FakePa,
    )
    assert options[0] == ("Windows-standaard", None)
    assert ("Speakers (Realtek(R) Audio)", 13) in options
    assert ("Odyssey G91SD", 14) in options


def test_resolve_uses_explicit_loopback_index() -> None:
    class FakePa:
        def get_device_info_by_index(self, index: int) -> dict[str, Any]:
            return {
                "index": index,
                "name": "Speakers [Loopback]",
                "maxInputChannels": 2,
                "defaultSampleRate": 48000,
                "isLoopbackDevice": True,
            }

        def terminate(self) -> None:
            pass

    info = resolve_loopback_device_info(13, pyaudio_instance=FakePa())
    assert info["index"] == 13
    assert info["isLoopbackDevice"] is True


def test_engine_prefers_wasapi_over_sounddevice_loopback() -> None:
    sounddevice = FakeSoundDevice()
    engine = AudioCaptureEngine(
        sounddevice_module=sounddevice,
        platform_name="win32",
        wasapi_loopback_module=FakeWasapiModule,
    )
    session = engine.start_session({"enable_loopback": True, "loopback_device": 13})
    state = engine._require_session(session.session_id)

    assert state.loopback_enabled is True
    assert state.loopback_sample_rate == 48000
    assert isinstance(state.loopback_stream, FakeWasapiModule.WasapiLoopbackStream)
    assert state.loopback_stream.started is True
    # Mic still via sounddevice; loopback not a second sounddevice InputStream.
    assert len(sounddevice.streams) == 1

    engine.stop_session(session.session_id)
    assert state.loopback_stream is None or state.loopback_stream.closed


def test_wasapi_loopback_audio_reaches_mix() -> None:
    sounddevice = FakeSoundDevice()
    engine = AudioCaptureEngine(
        sounddevice_module=sounddevice,
        platform_name="win32",
        wasapi_loopback_module=FakeWasapiModule,
    )
    session = engine.start_session({"enable_loopback": True})
    state = engine._require_session(session.session_id)
    assert engine.get_status(session.session_id) == CaptureStatus.ACTIVE

    mic_cb = sounddevice.streams[0].kwargs["callback"]
    mic_frames = 1600
    mic_cb(np.zeros((mic_frames, 1), dtype=np.float32), mic_frames, None, None)
    assert isinstance(state.loopback_stream, FakeWasapiModule.WasapiLoopbackStream)
    # Loopback stream draait op 48 kHz; na resample ×1/3 moet dit op mic-frames landen.
    state.loopback_stream.push(mic_frames * 3)

    assert state.captured_samples == mic_frames
    engine.stop_session(session.session_id)
