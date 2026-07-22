"""Incrementele transcriptie: partials + finaal uit laatste partial (optie C)."""

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


class FakeHost:
    def paste(self) -> None:
        pass


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

    def InputStream(self, **kwargs: Any) -> FakeStream:
        self.last_callback = kwargs.get("callback")
        return self.stream


class CountingModel:
    """Whisper-stub die calls telt."""

    def __init__(self, text: str = "tussentijdse tekst") -> None:
        self.text = text
        self.calls: list[str] = []
        self.lock = threading.Lock()
        self._call_index = 0

    def transcribe(self, path: str, **_kwargs: Any) -> tuple[list[Any], Any]:
        with self.lock:
            self._call_index += 1
            self.calls.append(path)

        segment = MagicMock()
        segment.text = self.text
        return [segment], MagicMock()


def _write_wav(path: Path, _rate: int, data: np.ndarray) -> None:
    path.write_bytes(b"RIFF" + data.tobytes()[:8])


@pytest.fixture
def events() -> list[CycleEvent]:
    return []


@pytest.fixture
def saves() -> list[Path]:
    return []


@pytest.fixture
def model() -> CountingModel:
    return CountingModel()


def _make_session(
    *,
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
    model: CountingModel,
    incremental: bool,
    interval: float = 0.05,
    min_seconds: float = 0.01,
) -> Opnamesessie:
    sd = FakeSoundDevice()

    def save_transcript(text: str) -> Path:
        path = tmp_path / f"saved-{len(saves)}.txt"
        path.write_text(text, encoding="utf-8")
        saves.append(path)
        return path

    sess = Opnamesessie(
        host=FakeHost(),
        sample_rate=16000,
        channels=1,
        minimum_recording_seconds=0.05,
        auto_paste=False,
        paste_delay_seconds=0.0,
        language="nl",
        delete_temp_audio=True,
        mode="toggle",
        warm_microphone=False,
        incremental_transcription=incremental,
        incremental_interval_seconds=interval,
        incremental_min_seconds=min_seconds,
        wait_until_modifiers_clear=lambda: None,
        on_ready=lambda: None,
        notify=lambda *_args, **_kwargs: None,
        push_level=lambda _level: None,
        reset_levels=lambda: None,
        emit_event=events.append,
        copy_text=lambda _text: None,
        save_transcript=save_transcript,
    )
    sess.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=_write_wav)
    sess.model = model
    sess._sd_ref = sd  # type: ignore[attr-defined]
    return sess


@pytest.fixture
def session(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
    model: CountingModel,
) -> Opnamesessie:
    return _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=True,
    )


def _feed_audio(session: Opnamesessie, seconds: float = 0.2) -> None:
    sd = session._sd_ref  # type: ignore[attr-defined]
    assert sd.last_callback is not None
    frames = max(1, int(session.sample_rate * seconds))
    sd.last_callback(np.zeros((frames, 1), dtype=np.float32), frames, None, None)


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timeout waiting for condition")


def test_incremental_emits_partial_events_without_saving(
    session: Opnamesessie,
    events: list[CycleEvent],
    saves: list[Path],
    model: CountingModel,
) -> None:
    session.start()
    _feed_audio(session)

    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_PARTIAL for e in events),
        timeout=2.0,
    )

    assert saves == []
    assert len(model.calls) >= 1
    partials = [e for e in events if e.type == CycleEventType.TRANSCRIPT_PARTIAL]
    assert partials
    assert partials[0].transcript

    session.cancel()


def test_stop_reuses_last_partial_without_extra_whisper(
    session: Opnamesessie,
    events: list[CycleEvent],
    saves: list[Path],
    model: CountingModel,
) -> None:
    """Optie C: laatste partial wordt finaal; geen Whisper meer bij stop."""

    session.start()
    _feed_audio(session)
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_PARTIAL for e in events),
        timeout=2.0,
    )
    # Voorkom een volgende partial vóór stop (interval was kort voor de test).
    session._incremental_interval_seconds = 3600.0
    calls_during_recording = len(model.calls)
    last_partial = next(
        e.transcript for e in reversed(events) if e.type == CycleEventType.TRANSCRIPT_PARTIAL
    )

    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=2.0,
    )

    assert len(model.calls) == calls_during_recording
    assert len(saves) == 1
    assert saves[0].read_text(encoding="utf-8") == last_partial


def test_stop_without_partial_falls_back_to_full_whisper(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
    model: CountingModel,
) -> None:
    """Geen partial klaar → volle Whisper zoals voorheen."""

    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=True,
        interval=60.0,
        min_seconds=0.01,
    )
    session.start()
    _feed_audio(session)
    time.sleep(0.05)
    assert len(model.calls) == 0

    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=2.0,
    )

    assert len(model.calls) == 1
    assert len(saves) == 1
    assert saves[0].read_text(encoding="utf-8") == "tussentijdse tekst"


def test_incremental_off_always_runs_whisper_on_stop(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
    model: CountingModel,
) -> None:
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=False,
    )
    session.start()
    _feed_audio(session)
    time.sleep(0.1)
    assert len(model.calls) == 0

    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=2.0,
    )

    assert len(model.calls) == 1
    assert len(saves) == 1


def test_each_partial_retranscribes_full_buffer_not_only_new_chunk(
    session: Opnamesessie,
    model: CountingModel,
) -> None:
    seen_sizes: list[int] = []
    original = session.create_temporary_wav

    def spy(chunks: list[Any]) -> Path:
        seen_sizes.append(sum(c.shape[0] for c in chunks))
        return original(chunks)

    session.create_temporary_wav = spy  # type: ignore[method-assign]

    session.start()
    _feed_audio(session, seconds=0.1)
    _wait_until(lambda: len(model.calls) >= 1, timeout=2.0)
    _feed_audio(session, seconds=0.2)
    _wait_until(lambda: len(model.calls) >= 2, timeout=2.0)

    assert len(seen_sizes) >= 2
    assert seen_sizes[1] > seen_sizes[0]

    session.cancel()
