"""Live-plak van chunk-/staart-delta's tijdens incrementele transcriptie."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from modules._contract import CycleEvent, CycleEventType
from opnamesessie import Opnamesessie


class TrackingHost:
    def __init__(self, clipboard: list[str], pastes: list[str]) -> None:
        self._clipboard = clipboard
        self._pastes = pastes

    def paste(self) -> None:
        self._pastes.append(self._clipboard[-1] if self._clipboard else "")


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
        self.default_input: dict[str, Any] = {
            "name": "Default Mic",
            "hostapi": 0,
            "max_input_channels": 1,
        }

    def query_devices(self, *args: Any, kind: str | None = None, **_kwargs: Any) -> Any:
        if kind == "input" or not args:
            if kind == "input":
                return dict(self.default_input)
            return [dict(self.default_input)]
        raise ValueError(f"missing device {args[0]}")

    def InputStream(self, **kwargs: Any) -> FakeStream:
        self.last_callback = kwargs.get("callback")
        return self.stream


class SequenceModel:
    """Whisper-stub met vaste teksten per call."""

    def __init__(self, texts: list[str] | None = None) -> None:
        self.texts = list(texts or ["chunk tekst"])
        self.calls: list[str] = []
        self.lock = threading.Lock()
        self._call_index = 0

    def transcribe(self, path: str, **_kwargs: Any) -> tuple[list[Any], Any]:
        with self.lock:
            idx = self._call_index
            self._call_index += 1
            self.calls.append(path)
            text = self.texts[idx] if idx < len(self.texts) else self.texts[-1]

        segment = MagicMock()
        segment.text = text
        segment.end = 0.5
        return [segment], MagicMock()


def _write_wav(path: Path, _rate: int, data: np.ndarray) -> None:
    path.write_bytes(b"RIFF" + data.tobytes()[:8])


@pytest.fixture
def events() -> list[CycleEvent]:
    return []


@pytest.fixture
def saves() -> list[Path]:
    return []


def _make_session(
    *,
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
    model: SequenceModel,
    clipboard: list[str],
    pastes: list[str],
    incremental: bool = True,
    live_paste: bool = True,
    auto_paste: bool = False,
    chunk_seconds: float = 0.12,
    min_seconds: float = 0.05,
    on_destination_command: Any = None,
    get_destinations: Any = None,
) -> Opnamesessie:
    sd = FakeSoundDevice()

    def save_transcript(text: str) -> Path:
        path = tmp_path / f"saved-{len(saves)}.txt"
        path.write_text(text, encoding="utf-8")
        saves.append(path)
        return path

    sess = Opnamesessie(
        host=TrackingHost(clipboard, pastes),
        sample_rate=16000,
        channels=1,
        minimum_recording_seconds=0.05,
        auto_paste=auto_paste,
        paste_delay_seconds=0.0,
        language="nl",
        delete_temp_audio=True,
        mode="toggle",
        warm_microphone=False,
        incremental_transcription=incremental,
        incremental_live_paste=live_paste,
        incremental_min_seconds=min_seconds,
        incremental_chunk_mode="fixed",
        incremental_chunk_seconds=chunk_seconds,
        incremental_vad_ms=2000,
        wait_until_modifiers_clear=lambda: None,
        on_ready=lambda: None,
        notify=lambda *_args, **_kwargs: None,
        push_level=lambda _level: None,
        reset_levels=lambda: None,
        emit_event=events.append,
        copy_text=clipboard.append,
        save_transcript=save_transcript,
        on_destination_command=on_destination_command,
        get_destinations=get_destinations,
    )
    sess.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=_write_wav)
    sess.model = model
    sess._sd_ref = sd  # type: ignore[attr-defined]
    sess._chunk_poll_seconds = 0.05
    return sess


def _feed_audio(session: Opnamesessie, seconds: float = 0.2) -> None:
    sd = session._sd_ref  # type: ignore[attr-defined]
    assert sd.last_callback is not None
    frames = max(1, int(session.sample_rate * seconds))
    sd.last_callback(np.zeros((frames, 1), dtype=np.float32), frames, None, None)


def _wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timeout waiting for condition")


def test_live_paste_pastes_chunk_deltas_not_full_transcript(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    pastes: list[str] = []
    clipboard: list[str] = []
    model = SequenceModel(["alfa", "beta", "x"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        clipboard=clipboard,
        pastes=pastes,
        incremental=True,
        live_paste=True,
        auto_paste=False,
        chunk_seconds=0.1,
    )
    session.start()
    _feed_audio(session, seconds=0.15)
    _wait_until(lambda: len(clipboard) >= 1, timeout=3.0)
    _feed_audio(session, seconds=0.15)
    _wait_until(lambda: len(clipboard) >= 2, timeout=3.0)

    # Geen lange staart: blokkeer verdere knippen en stop met te korte rest.
    session._incremental_chunk_seconds = 3600.0
    session._incremental_min_seconds = 10.0
    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=3.0,
    )

    assert clipboard == ["alfa", "beta"]
    assert "alfa beta" not in clipboard
    assert pastes == clipboard
    assert session._live_pasted_text == "alfa beta"
    assert len(saves) == 1
    assert saves[0].read_text(encoding="utf-8") == "alfa beta"


def test_live_paste_with_auto_paste_false_still_pastes_deltas(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    pastes: list[str] = []
    clipboard: list[str] = []
    model = SequenceModel(["een", "twee"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        clipboard=clipboard,
        pastes=pastes,
        live_paste=True,
        auto_paste=False,
        chunk_seconds=0.1,
    )
    session.start()
    _feed_audio(session, seconds=0.15)
    _wait_until(lambda: len(pastes) >= 1, timeout=3.0)
    _feed_audio(session, seconds=0.15)
    _wait_until(lambda: len(pastes) >= 2, timeout=3.0)
    session._incremental_chunk_seconds = 3600.0
    session._incremental_min_seconds = 10.0
    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=3.0,
    )

    assert pastes == ["een", "twee"]
    assert clipboard == pastes


def test_live_paste_skips_destination_commands(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    pastes: list[str] = []
    clipboard: list[str] = []
    command_calls: list[tuple[str, str | None]] = []
    dests = [{"name": "Boodschappenlijst", "path": str(tmp_path / "boodschappen")}]
    model = SequenceModel(["unused"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        clipboard=clipboard,
        pastes=pastes,
        live_paste=True,
        auto_paste=True,
        on_destination_command=lambda kind, name: command_calls.append((kind, name)),
        get_destinations=lambda: dests,
    )

    session._apply_transcript("Boodschappenlijst")

    assert command_calls == []
    assert len(saves) == 1
    assert saves[0].read_text(encoding="utf-8") == "Boodschappenlijst"
    # Nog niets live geplakt → staart-delta = volledige transcript.
    assert clipboard == ["Boodschappenlijst"]
    assert pastes == clipboard


def test_empty_piece_text_does_not_paste(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    pastes: list[str] = []
    clipboard: list[str] = []
    model = SequenceModel(["x"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        clipboard=clipboard,
        pastes=pastes,
        live_paste=True,
    )

    session._paste_delta("")
    session._paste_delta("   ")
    assert clipboard == []
    assert pastes == []


def test_live_paste_off_uses_end_auto_paste(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    pastes: list[str] = []
    clipboard: list[str] = []
    model = SequenceModel(["eindresultaat"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        clipboard=clipboard,
        pastes=pastes,
        incremental=True,
        live_paste=False,
        auto_paste=True,
        chunk_seconds=60.0,
        min_seconds=0.01,
    )
    session.minimum_recording_seconds = 0.01
    session.start()
    _feed_audio(session)
    time.sleep(0.15)
    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=5.0,
    )

    assert clipboard == ["eindresultaat"]
    assert pastes == ["eindresultaat"]


def test_live_paste_pastes_tail_delta_once(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    pastes: list[str] = []
    clipboard: list[str] = []
    # Eerste call = chunk; tweede = staart met overlap die wordt ontdubbeld.
    model = SequenceModel(["alfa bravo", "alfa bravo charlie"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        clipboard=clipboard,
        pastes=pastes,
        live_paste=True,
        auto_paste=False,
        chunk_seconds=0.1,
    )
    session.start()
    _feed_audio(session, seconds=0.15)
    _wait_until(lambda: len(clipboard) >= 1, timeout=3.0)
    session._incremental_chunk_seconds = 3600.0
    calls_during = len(model.calls)
    _feed_audio(session, seconds=0.12)

    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=3.0,
    )

    assert len(model.calls) == calls_during + 1
    assert clipboard == ["alfa bravo", "charlie"]
    assert "alfa bravo charlie" not in clipboard
    assert pastes == clipboard
    assert saves[0].read_text(encoding="utf-8") == "alfa bravo charlie"


def test_live_paste_enabled_requires_both_flags(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    clipboard: list[str] = []
    pastes: list[str] = []
    model = SequenceModel(["x"])
    both = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        clipboard=clipboard,
        pastes=pastes,
        incremental=True,
        live_paste=True,
    )
    only_inc = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        clipboard=clipboard,
        pastes=pastes,
        incremental=True,
        live_paste=False,
    )
    only_live = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        clipboard=clipboard,
        pastes=pastes,
        incremental=False,
        live_paste=True,
    )
    assert both._live_paste_enabled() is True
    assert only_inc._live_paste_enabled() is False
    assert only_live._live_paste_enabled() is False
