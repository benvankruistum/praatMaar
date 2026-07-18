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
        self.active = False

    def start(self) -> None:
        self.started = True
        self.active = True

    def stop(self) -> None:
        self.stopped = True
        self.active = False

    def close(self) -> None:
        self.closed = True
        self.active = False


class FakeSoundDevice:
    def __init__(self) -> None:
        self.last_callback: Any = None
        self.stream = FakeStream()
        self.input_stream_calls = 0
        self._fresh_stream_each_open = False

    def InputStream(self, **kwargs: Any) -> FakeStream:
        self.input_stream_calls += 1
        self.last_callback = kwargs.get("callback")
        if self._fresh_stream_each_open or self.input_stream_calls > 1:
            self.stream = FakeStream()
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
def session(
    host: FakeHost, sd: FakeSoundDevice, states: list[RecordingState], tmp_path: Path, monkeypatch
) -> Opnamesessie:
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
        warm_microphone=False,
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


def test_start_sets_recording_and_notifies(
    session: Opnamesessie, sd: FakeSoundDevice, states: list
) -> None:
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


def test_stop_keeps_stream_warm(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("opnamesessie.sys.platform", "win32")
    session.warm_microphone = True
    session.start()
    assert sd.input_stream_calls == 1
    # Warme stream blijft callbacks leveren (zoals PortAudio).
    assert sd.last_callback is not None
    sd.last_callback(np.zeros((160, 1), dtype=np.float32), 160, None, None)
    session.stop_and_transcribe()
    assert sd.stream.started
    assert not sd.stream.stopped
    assert not sd.stream.closed
    session.start()
    assert sd.input_stream_calls == 1


def test_stop_closes_stream_when_warm_disabled(session: Opnamesessie, sd: FakeSoundDevice) -> None:
    session.warm_microphone = False
    sd._fresh_stream_each_open = True
    session.start()
    first = sd.stream
    assert sd.last_callback is not None
    sd.last_callback(np.zeros((160, 1), dtype=np.float32), 160, None, None)
    session.stop_and_transcribe()
    assert first.closed
    assert session._audio_stream is None

    session.start()
    assert sd.input_stream_calls == 2


def test_cancel_closes_stream_when_warm_disabled(
    session: Opnamesessie, sd: FakeSoundDevice
) -> None:
    session.warm_microphone = False
    session.start()
    first = sd.stream
    session.cancel()
    assert first.closed
    assert session._audio_stream is None


def test_warmup_is_noop_when_warm_disabled(session: Opnamesessie, sd: FakeSoundDevice) -> None:
    session.warm_microphone = False
    session.warmup_microphone()
    assert sd.input_stream_calls == 0
    assert session._audio_stream is None


def test_start_reopens_inactive_warm_stream(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bluetooth uit/aan: PortAudio-stream blijft bestaan maar is niet meer active."""

    monkeypatch.setattr("opnamesessie.sys.platform", "win32")
    session.warm_microphone = True
    sd._fresh_stream_each_open = True
    session.warmup_microphone()
    assert sd.input_stream_calls == 1
    first = sd.stream
    first.active = False

    session.start()
    assert sd.input_stream_calls == 2
    assert first.stopped and first.closed
    assert sd.stream.started and sd.stream.active
    assert session.is_recording


def test_start_reopens_stale_warm_stream_without_callbacks(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch
) -> None:
    """Stream 'active' maar geen callbacks meer (klassieke BT-zombie)."""

    monkeypatch.setattr("opnamesessie.sys.platform", "win32")
    session.warm_microphone = True
    sd._fresh_stream_each_open = True
    session.warmup_microphone()
    assert sd.input_stream_calls == 1
    first = sd.stream

    # Simuleer dat open + laatste callback lang geleden waren.
    session._stream_opened_at = 0.0
    session._last_audio_callback_at = 0.0
    monkeypatch.setattr(
        "opnamesessie.time.monotonic",
        lambda: 100.0,
    )

    session.start()
    assert sd.input_stream_calls == 2
    assert first.closed
    assert session.is_recording


def test_empty_recording_refreshes_stream_for_next_start(
    session: Opnamesessie, sd: FakeSoundDevice
) -> None:
    """Geen chunks ondanks lange opname → stream afbreken voor herstel."""

    sd._fresh_stream_each_open = True
    session.minimum_recording_seconds = 0.0
    session.start()
    assert sd.input_stream_calls == 1
    first = sd.stream
    # Geen callback = geen audio.
    session.stop_and_transcribe()
    assert first.closed
    assert session._audio_stream is None

    session.start()
    assert sd.input_stream_calls == 2


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


def test_transcribe_pastes_and_copies(
    session: Opnamesessie, host: FakeHost, states: list, sd: FakeSoundDevice
) -> None:
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


def _wait_for_processing(session: Opnamesessie) -> None:
    import time

    for _ in range(50):
        if not session.is_processing:
            break
        time.sleep(0.05)


def _record_short_audio(session: Opnamesessie, sd: FakeSoundDevice) -> None:
    session.minimum_recording_seconds = 0.0
    session.start()
    assert sd.last_callback is not None
    chunk = np.zeros((1600, 1), dtype=np.float32)
    sd.last_callback(chunk, 1600, None, None)
    session.stop_and_transcribe()
    _wait_for_processing(session)


def test_destination_command_skips_paste_and_save(
    host: FakeHost,
    sd: FakeSoundDevice,
    states: list[RecordingState],
    tmp_path: Path,
    monkeypatch,
) -> None:
    import recovery

    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)

    command_calls: list[tuple[str, str | None]] = []
    save_calls: list[str] = []
    clipboard: list[str] = []
    dests = [{"name": "Boodschappenlijst", "path": str(tmp_path / "boodschappen")}]

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
        warm_microphone=False,
        wait_until_modifiers_clear=lambda: None,
        on_ready=lambda: None,
        notify=lambda state, mode=None: states.append(state),
        push_level=lambda _level: None,
        reset_levels=lambda: None,
        copy_text=clipboard.append,
        save_transcript=lambda text: (save_calls.append(text), recovery.save_transcript(text))[1],
        preserve_audio=recovery.preserve_audio,
        on_destination_command=lambda kind, name: command_calls.append((kind, name)),
        get_destinations=lambda: dests,
    )
    sess.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=_write_wav)
    sess.model = FakeModel(text="boodschappenlijst")

    _record_short_audio(sess, sd)

    assert not sess.is_processing
    assert host.paste_calls == 0
    assert clipboard == []
    assert save_calls == []
    assert command_calls == [("set", "Boodschappenlijst")]
    assert states[-1] == RecordingState.IDLE


def test_reset_command_skips_paste(
    host: FakeHost,
    sd: FakeSoundDevice,
    states: list[RecordingState],
    tmp_path: Path,
    monkeypatch,
) -> None:
    import recovery

    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)

    command_calls: list[tuple[str, str | None]] = []
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
        warm_microphone=False,
        wait_until_modifiers_clear=lambda: None,
        on_ready=lambda: None,
        notify=lambda state, mode=None: states.append(state),
        push_level=lambda _level: None,
        reset_levels=lambda: None,
        copy_text=clipboard.append,
        save_transcript=recovery.save_transcript,
        preserve_audio=recovery.preserve_audio,
        on_destination_command=lambda kind, name: command_calls.append((kind, name)),
        get_destinations=lambda: [],
    )
    sess.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=_write_wav)
    sess.model = FakeModel(text="standaard")

    _record_short_audio(sess, sd)

    assert host.paste_calls == 0
    assert clipboard == []
    assert command_calls == [("reset", None)]
    assert states[-1] == RecordingState.IDLE
