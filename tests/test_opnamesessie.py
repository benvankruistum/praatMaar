"""Tests voor Opnamesessie — dicteercyclus zonder echte mic/Whisper."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from indicator import RecordingState
from opnamesessie import Opnamesessie


class FakeHost:
    def __init__(self) -> None:
        self.paste_calls = 0

    def paste(self) -> None:
        self.paste_calls += 1

    def set_autostart(self, enabled: bool) -> None:
        pass

    def is_autostart_enabled(self) -> bool:
        return False

    def app_dir(self) -> Path:
        raise NotImplementedError

    def acquire_single_instance(self) -> bool:
        return True


class FakeStream:
    def __init__(self) -> None:
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
        self.last_callback: Any = None
        self.stream = FakeStream()
        self.input_stream_calls = 0

    def InputStream(self, **kwargs: Any) -> FakeStream:
        self.input_stream_calls += 1
        self.last_callback = kwargs.get("callback")
        return self.stream


class FakeModel:
    def __init__(self, text: str = "hallo wereld") -> None:
        self.text = text
        self.calls: list[str] = []

    def transcribe(self, path: str, **kwargs: Any) -> tuple[list[Any], Any]:
        self.calls.append(path)
        segment = MagicMock()
        segment.text = self.text
        return [segment], MagicMock()


@pytest.fixture
def host() -> FakeHost:
    return FakeHost()


@pytest.fixture
def sd() -> FakeSoundDevice:
    return FakeSoundDevice()


@pytest.fixture
def states() -> list[RecordingState]:
    return []


@pytest.fixture
def session(host: FakeHost, sd: FakeSoundDevice, states: list[RecordingState], tmp_path: Path, monkeypatch) -> Opnamesessie:
    import recovery

    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)

    clipboard: list[str] = []

    sess = Opnamesessie(
        host=host,
        sample_rate=16000,
        channels=1,
        minimum_recording_seconds=0.05,
        auto_paste=True,
        paste_delay_seconds=0.0,
        language="nl",
        delete_temp_audio=True,
        mode="toggle",
        wait_until_modifiers_clear=lambda: None,
        on_ready=lambda: None,
        notify=lambda state, mode=None: states.append(state),
        push_level=lambda _level: None,
        reset_levels=lambda: None,
        copy_text=clipboard.append,
        save_transcript=recovery.save_transcript,
        preserve_audio=recovery.preserve_audio,
    )
    sess.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=_write_wav)
    sess.model = FakeModel()
    sess._clipboard = clipboard  # type: ignore[attr-defined]
    return sess


def _write_wav(path: Path, rate: int, data: np.ndarray) -> None:
    path.write_bytes(b"RIFF" + data.tobytes()[:8])


def test_start_sets_recording_and_notifies(session: Opnamesessie, sd: FakeSoundDevice, states: list) -> None:
    assert not session.is_recording
    session.start()
    assert session.is_recording
    assert sd.stream.started
    assert states[-1] == RecordingState.RECORDING


def test_start_while_recording_is_noop(session: Opnamesessie, sd: FakeSoundDevice) -> None:
    session.start()
    first = sd.stream
    session.start()
    assert sd.stream is first


def test_stop_keeps_stream_warm(session: Opnamesessie, sd: FakeSoundDevice) -> None:
    session.start()
    assert sd.input_stream_calls == 1
    session.stop_and_transcribe()
    assert sd.stream.started
    assert not sd.stream.stopped
    assert not sd.stream.closed
    session.start()
    assert sd.input_stream_calls == 1


def test_cancel_clears_recording(session: Opnamesessie, states: list) -> None:
    session.start()
    session.cancel()
    assert not session.is_recording
    assert states[-1] == RecordingState.CANCELLED


def test_short_recording_does_not_process(session: Opnamesessie, states: list) -> None:
    session.minimum_recording_seconds = 10.0
    session.start()
    session.stop_and_transcribe()
    assert not session.is_recording
    assert not session.is_processing
    assert states[-1] == RecordingState.IDLE
    assert session.model.calls == []  # type: ignore[union-attr]


def test_transcribe_pastes_and_copies(session: Opnamesessie, host: FakeHost, states: list, sd: FakeSoundDevice) -> None:
    session.minimum_recording_seconds = 0.0
    session.start()
    # Simuleer één audioblok via de callback.
    assert sd.last_callback is not None
    chunk = np.zeros((1600, 1), dtype=np.float32)
    sd.last_callback(chunk, 1600, None, None)
    session.stop_and_transcribe()

    # Wacht tot de daemon-thread klaar is.
    import time

    for _ in range(50):
        if not session.is_processing:
            break
        time.sleep(0.05)

    assert not session.is_processing
    assert host.paste_calls == 1
    assert session._clipboard == ["hallo wereld"]  # type: ignore[attr-defined]
    assert states[-1] == RecordingState.IDLE
