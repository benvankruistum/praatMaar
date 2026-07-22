"""Tests voor Opnamesessie — dicteercyclus zonder echte mic/Whisper."""

from __future__ import annotations

import threading
import time
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


def test_start_failure_shows_user_error(
    session: Opnamesessie, sd: FakeSoundDevice, states: list
) -> None:
    errors: list[str] = []
    session._on_user_error = errors.append

    def boom(**_kwargs):
        raise RuntimeError("No Default Input Device Available")

    sd.InputStream = boom  # type: ignore[method-assign]
    session.start()
    assert not session.is_recording
    assert states[-1] == RecordingState.ERROR
    assert len(errors) == 1
    assert "microfoon" in errors[0].lower()
    assert "No Default Input Device Available" in errors[0]


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


def test_active_destination_without_auto_paste_skips_clipboard(
    host: FakeHost,
    sd: FakeSoundDevice,
    states: list[RecordingState],
    tmp_path: Path,
    monkeypatch,
) -> None:
    import recovery

    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)

    clipboard: list[str] = []
    save_calls: list[str] = []
    dests = [
        {
            "name": "Boodschappen",
            "path": str(tmp_path / "boodschappen"),
            "auto_paste": False,
        }
    ]

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
        get_destinations=lambda: dests,
        get_active_destination=lambda: "Boodschappen",
    )
    sess.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=_write_wav)
    sess.model = FakeModel(text="melk en brood")

    _record_short_audio(sess, sd)

    assert save_calls == ["melk en brood"]
    assert clipboard == []
    assert host.paste_calls == 0
    assert states[-1] == RecordingState.IDLE


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


def test_successful_cycle_emits_module_events(session: Opnamesessie, sd: FakeSoundDevice) -> None:
    from modules._contract import CycleEventType

    events: list[str] = []

    def capture(event) -> None:
        events.append(str(event.type))

    session._emit_event = capture  # type: ignore[method-assign]
    _record_short_audio(session, sd)

    assert events[0] == CycleEventType.CYCLE_STARTED
    assert CycleEventType.CYCLE_TRANSCRIBING in events
    assert CycleEventType.CYCLE_COMPLETED in events
    assert CycleEventType.TRANSCRIPT_SAVED in events
    assert events[-1] == CycleEventType.CYCLE_IDLE
    assert session._session_id is None


def test_stop_notifies_ui_before_incremental_worker_joins(
    host: FakeHost, sd: FakeSoundDevice, tmp_path: Path, monkeypatch
) -> None:
    """Stop mag de pill niet laten wachten op een in-flight partial-Whisper."""

    import recovery

    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)

    states: list[RecordingState] = []
    entered = threading.Event()
    release = threading.Event()

    class BlockingModel:
        def transcribe(self, path: str, **_kwargs: Any) -> tuple[list[Any], Any]:
            entered.set()
            assert release.wait(timeout=5.0)
            segment = MagicMock()
            segment.text = "partial"
            segment.end = 0.2
            return [segment], MagicMock()

    sess = Opnamesessie(
        host=host,
        sample_rate=16000,
        channels=1,
        minimum_recording_seconds=0.05,
        auto_paste=False,
        paste_delay_seconds=0.0,
        language="nl",
        delete_temp_audio=True,
        mode="toggle",
        warm_microphone=False,
        incremental_transcription=True,
        incremental_interval_seconds=0.05,
        incremental_min_seconds=0.01,
        wait_until_modifiers_clear=lambda: None,
        on_ready=lambda: None,
        notify=lambda state, mode=None: states.append(state),
        push_level=lambda _level: None,
        reset_levels=lambda: None,
        copy_text=lambda _text: None,
        save_transcript=recovery.save_transcript,
    )
    sess.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=_write_wav)
    sess.model = BlockingModel()

    sess.start()
    assert sd.last_callback is not None
    sd.last_callback(np.zeros((3200, 1), dtype=np.float32), 3200, None, None)
    assert entered.wait(timeout=2.0)
    # Voorbij minimum_recording_seconds zodat stop niet als "te kort" eindigt.
    time.sleep(0.08)

    stop_done = threading.Event()

    def _stop() -> None:
        sess.stop_and_transcribe()
        stop_done.set()

    threading.Thread(target=_stop, daemon=True).start()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if RecordingState.TRANSCRIBING in states:
            break
        time.sleep(0.01)

    assert RecordingState.TRANSCRIBING in states, (
        "UI moet meteen Transcriberen tonen, niet pas na einde van de partial-Whisper"
    )
    assert not stop_done.is_set(), "stop mag nog joinen op de worker, maar UI is al bijgewerkt"

    release.set()
    assert stop_done.wait(timeout=2.0)
