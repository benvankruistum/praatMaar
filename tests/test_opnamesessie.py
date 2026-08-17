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
        self.default_input: dict[str, Any] = {
            "name": "Default Mic",
            "hostapi": 0,
            "max_input_channels": 1,
        }
        self.devices_by_index: dict[int, dict[str, Any]] = {
            0: {
                "name": "Default Mic",
                "hostapi": 0,
                "max_input_channels": 1,
            },
            1: {
                "name": "Headset",
                "hostapi": 0,
                "max_input_channels": 1,
            },
        }

    def query_devices(self, *args: Any, kind: str | None = None, **_kwargs: Any) -> Any:
        if kind == "input":
            return dict(self.default_input)
        if args:
            device = int(args[0])
            info = self.devices_by_index.get(device)
            if info is None:
                raise ValueError(f"missing device {device}")
            return dict(info)
        # Volledige lijst (first_input_device_index / enumeratie).
        if not self.devices_by_index:
            return []
        max_index = max(self.devices_by_index)
        return [
            dict(self.devices_by_index.get(i, {"name": f"missing-{i}", "max_input_channels": 0}))
            for i in range(max_index + 1)
        ]

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
        notify=lambda state, mode="toggle", **_kwargs: states.append(state),
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
    assert RecordingState.PREPARING in states
    assert states[-1] == RecordingState.RECORDING
    assert states.index(RecordingState.PREPARING) < states.index(RecordingState.RECORDING)


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
    assert RecordingState.PREPARING in states
    assert RecordingState.RECORDING not in states
    assert states[-1] == RecordingState.ERROR
    assert len(errors) == 1
    assert "microfoon" in errors[0].lower()
    assert "No Default Input Device Available" in errors[0]


def test_start_failure_notifies_error_with_mic_hint(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    notified: list[tuple] = []

    def capture(state, mode="toggle", *, hint=None, **_kwargs):
        notified.append((state, mode, hint or ""))

    session._notify = capture

    def boom(**_kwargs):
        raise RuntimeError("No Default Input Device Available")

    sd.InputStream = boom  # type: ignore[method-assign]
    session.start()
    assert notified[0][0] == RecordingState.PREPARING
    assert notified[-1][0] == RecordingState.ERROR
    assert "microfoon" in notified[-1][2].lower() or "instellingen" in notified[-1][2].lower()


def test_start_while_recording_is_noop(session: Opnamesessie, sd: FakeSoundDevice) -> None:
    session.start()
    first = sd.stream
    session.start()
    assert sd.stream is first


def test_stop_keeps_stream_warm(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("dicteercyclus.mic_stream.sys.platform", "win32")
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

    monkeypatch.setattr("dicteercyclus.mic_stream.sys.platform", "win32")
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

    monkeypatch.setattr("dicteercyclus.mic_stream.sys.platform", "win32")
    session.warm_microphone = True
    sd._fresh_stream_each_open = True
    session.warmup_microphone()
    assert sd.input_stream_calls == 1
    first = sd.stream

    # Simuleer dat open + laatste callback lang geleden waren.
    session._stream_opened_at = 0.0
    session._last_audio_callback_at = 0.0
    monkeypatch.setattr(
        "dicteercyclus.session.time.monotonic",
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
    done = _install_cycle_done(session)
    session.stop_and_transcribe()
    assert done.wait(timeout=30), "dicteercyclus niet afgerond"

    assert not session.is_processing
    assert host.paste_calls == 1
    assert session._clipboard == ["hallo wereld"]  # type: ignore[attr-defined]
    assert states[-1] == RecordingState.IDLE


def _install_cycle_done(session: Opnamesessie) -> threading.Event:
    """Deterministische cycle-synchronisatie via het on_ready-seam.

    on_ready draait als allerlaatste in het finally-blok van de
    transcriptie-worker (ná _processing=False, notify(IDLE) en CYCLE_IDLE) —
    dus na deze Event zijn álle asserts race-vrij. Vervangt de eerdere
    2,5s-poll op is_processing die onder CI-load stil afliep (flaky).
    """

    done = threading.Event()
    previous = session.on_ready

    def _ready() -> None:
        previous()
        done.set()

    session.on_ready = _ready
    return done


def _record_short_audio(session: Opnamesessie, sd: FakeSoundDevice) -> None:
    session.minimum_recording_seconds = 0.0
    session.start()
    assert sd.last_callback is not None
    chunk = np.zeros((1600, 1), dtype=np.float32)
    sd.last_callback(chunk, 1600, None, None)
    done = _install_cycle_done(session)
    session.stop_and_transcribe()
    assert done.wait(timeout=30), "dicteercyclus niet afgerond"


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
        notify=lambda state, mode="toggle", **_kwargs: states.append(state),
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
        notify=lambda state, mode="toggle", **_kwargs: states.append(state),
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
        notify=lambda state, mode="toggle", **_kwargs: states.append(state),
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


def test_event_accepts_explicit_session_id(session: Opnamesessie) -> None:
    # Regression: de transcribe-worker emitte events via self._session_id,
    # dat door een nét gestarte nieuwe cyclus al vervangen kon zijn.
    from opnamesessie import CycleEventType

    emitted: list[Any] = []
    session._emit_event = emitted.append
    session._session_id = "nieuw"
    session._event(CycleEventType.CYCLE_IDLE, session_id="oud")
    assert emitted[-1].session_id == "oud"


def test_clear_session_id_does_not_clobber_newer_session(session: Opnamesessie) -> None:
    session._session_id = "nieuw"
    session._clear_session_id("oud")
    assert session._session_id == "nieuw"
    session._clear_session_id("nieuw")
    assert session._session_id is None


def test_ensure_stream_skips_portaudio_refresh_when_modules_capture(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch
) -> None:
    # Regression: refresh_portaudio doet _terminate() tot PortAudio uit is —
    # met een actieve Meeting Buddy-capture op dezelfde sounddevice-module
    # trok dat die stream eronder weg (dode stream of native crash).
    calls: list[int] = []
    monkeypatch.setattr("dicteercyclus.mic_stream.refresh_portaudio", lambda _sd: calls.append(1))

    session._has_external_streams = lambda: True
    session.start()
    assert calls == []

    session.stop_audio_stream()
    session._has_external_streams = lambda: False
    session._ensure_stream()
    assert calls == [1]


def test_warm_stream_reused_when_device_identity_unchanged(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("dicteercyclus.mic_stream.sys.platform", "win32")
    session.warm_microphone = True
    sd._fresh_stream_each_open = True
    session.warmup_microphone()
    assert sd.input_stream_calls == 1
    assert session._bound_device_identity == ("Default Mic", 0)
    assert sd.last_callback is not None
    sd.last_callback(np.zeros((160, 1), dtype=np.float32), 160, None, None)

    session._ensure_stream()
    assert sd.input_stream_calls == 1


def test_warm_stream_keeps_alive_when_identity_unavailable(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Geen query_devices-info → geen force-reopen van een levende stream."""

    monkeypatch.setattr("dicteercyclus.mic_stream.sys.platform", "win32")
    session.warm_microphone = True
    sd._fresh_stream_each_open = True
    session.warmup_microphone()
    assert sd.last_callback is not None
    sd.last_callback(np.zeros((160, 1), dtype=np.float32), 160, None, None)
    session._bound_device_identity = None

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("no devices")

    sd.query_devices = boom  # type: ignore[method-assign]
    session._ensure_stream()
    assert sd.input_stream_calls == 1


def test_warm_stream_reopens_when_device_identity_changes(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("dicteercyclus.mic_stream.sys.platform", "win32")
    session.warm_microphone = True
    sd._fresh_stream_each_open = True
    session.warmup_microphone()
    first = sd.stream
    assert sd.input_stream_calls == 1
    assert sd.last_callback is not None
    sd.last_callback(np.zeros((160, 1), dtype=np.float32), 160, None, None)

    sd.default_input = {
        "name": "BT Headset",
        "hostapi": 0,
        "max_input_channels": 1,
    }
    session._ensure_stream()
    assert sd.input_stream_calls == 2
    assert first.closed
    assert session._bound_device_identity == ("BT Headset", 0)
    assert session._audio_stream is sd.stream


def test_resolve_clears_pinned_device_when_gone(session: Opnamesessie, sd: FakeSoundDevice) -> None:
    session.microphone_device = 99
    device = session._resolve_input_device(sd)
    assert device is None
    assert session.microphone_device is None


def test_ensure_stream_opens_default_after_pinned_gone(
    session: Opnamesessie, sd: FakeSoundDevice
) -> None:
    session.microphone_device = 99
    session._ensure_stream()
    assert session.microphone_device is None
    assert sd.input_stream_calls == 1
    assert session._bound_device_identity == ("Default Mic", 0)


def test_stop_audio_stream_clears_bound_device_identity(
    session: Opnamesessie, sd: FakeSoundDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("dicteercyclus.mic_stream.sys.platform", "win32")
    session.warm_microphone = True
    session.warmup_microphone()
    assert session._bound_device_identity is not None
    session.refresh_input_device()
    assert session._audio_stream is None
    assert session._bound_device_identity is None


def test_transcribe_kwargs_defaults_and_optional_prompt(session: Opnamesessie) -> None:
    kwargs = session.transcribe_kwargs()
    assert kwargs["language"] == "nl"
    assert kwargs["beam_size"] == 5
    assert kwargs["vad_filter"] is True
    assert kwargs["vad_parameters"] == {"min_silence_duration_ms": 300}
    assert kwargs["condition_on_previous_text"] is False
    assert kwargs["no_speech_threshold"] == 0.6
    assert "initial_prompt" not in kwargs
    assert "hotwords" not in kwargs

    session.whisper_vad_filter = False
    session.whisper_beam_size = 3
    session.whisper_initial_prompt = "  praatMaar  "
    session.whisper_hotwords = "Teams, Zoom"
    session.whisper_condition_on_previous_text = True
    session.whisper_no_speech_threshold = 0.4
    kwargs = session.transcribe_kwargs()
    assert kwargs["beam_size"] == 3
    assert kwargs["vad_filter"] is False
    assert "vad_parameters" not in kwargs
    assert kwargs["initial_prompt"] == "praatMaar"
    assert kwargs["hotwords"] == "Teams, Zoom"
    assert kwargs["condition_on_previous_text"] is True
    assert kwargs["no_speech_threshold"] == 0.4
