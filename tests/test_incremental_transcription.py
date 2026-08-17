"""Chunk-transcriptie: partials per audio-stuk; finaal = concatenatie (+ staart)."""

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
    incremental: bool,
    chunk_mode: str = "fixed",
    chunk_seconds: float = 0.12,
    vad_ms: int = 2000,
    min_seconds: float = 0.05,
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
        incremental_min_seconds=min_seconds,
        incremental_chunk_mode=chunk_mode,
        incremental_chunk_seconds=chunk_seconds,
        incremental_vad_ms=vad_ms,
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


def test_incremental_emits_partial_events_without_saving(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    model = SequenceModel(["eerste deel"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=True,
        chunk_seconds=0.08,
    )
    session.start()
    _feed_audio(session, seconds=0.2)
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_PARTIAL for e in events),
        timeout=3.0,
    )

    assert saves == []
    assert len(model.calls) >= 1
    partials = [e for e in events if e.type == CycleEventType.TRANSCRIPT_PARTIAL]
    assert partials[0].transcript == "eerste deel"

    session.cancel()


def test_stop_uses_chunk_texts_without_full_buffer_retranscription(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    model = SequenceModel(["alfa bravo", "alfa bravo charlie"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=True,
        chunk_seconds=0.1,
    )
    session.start()
    _feed_audio(session, seconds=0.15)
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_PARTIAL for e in events),
        timeout=3.0,
    )
    # Blokkeer verdere knippen; voeg staart toe die bij stop getranscribeerd wordt.
    session._incremental_chunk_seconds = 3600.0
    calls_during = len(model.calls)
    _feed_audio(session, seconds=0.12)

    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=3.0,
    )

    # Hoogstens één extra Whisper voor de staart — geen volle her-run van alles.
    assert len(model.calls) == calls_during + 1
    assert len(saves) == 1
    # Overlap "alfa bravo" wordt ontdubbeld → "alfa bravo charlie"
    assert saves[0].read_text(encoding="utf-8") == "alfa bravo charlie"


def test_stop_without_chunk_falls_back_to_full_whisper(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    model = SequenceModel(["volle run"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=True,
        chunk_seconds=60.0,
        min_seconds=0.01,
    )
    session.minimum_recording_seconds = 0.01
    session.start()
    _feed_audio(session)
    time.sleep(0.15)
    assert len(model.calls) == 0

    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=5.0,
    )

    assert len(model.calls) == 1
    assert saves[0].read_text(encoding="utf-8") == "volle run"


def test_incremental_off_always_runs_whisper_on_stop(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    model = SequenceModel(["uit"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=False,
    )
    session.minimum_recording_seconds = 0.01
    session.start()
    _feed_audio(session)
    time.sleep(0.15)
    assert len(model.calls) == 0

    session.stop_and_transcribe()
    _wait_until(
        lambda: any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events),
        timeout=5.0,
    )

    assert len(model.calls) == 1
    assert saves[0].read_text(encoding="utf-8") == "uit"


def test_chunk_whisper_loop_stays_alive_until_sentinel(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    """Stop-signaal + lege queue mag de Whisper-worker niet laten stoppen.

    Jobs die de decide-loop ná ``stop.set()`` (vóór de sentinel) enqueue’t,
    moeten nog verwerkt worden — anders is ``_chunk_transcripts`` leeg bij
    finalize en volgt een volle-buffer hertranscriptie.
    """
    from dicteercyclus.incremental import _ChunkWhisperJob

    model = SequenceModel(["behouden"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=True,
    )
    session.start()
    _wait_until(
        lambda: (
            session._chunk_whisper_thread is not None and session._chunk_whisper_thread.is_alive()
        ),
        timeout=2.0,
    )
    whisper = session._chunk_whisper_thread
    assert session._incremental_stop is not None
    session._incremental_stop.set()
    # Ruim meer dan de 50ms Empty-timeout in de stopping-tak (probe: ~200ms tot exit).
    time.sleep(0.5)
    assert whisper.is_alive(), "worker mag niet op Empty+stopping stoppen"

    piece = np.zeros(int(session.sample_rate * 0.1), dtype=np.float32)
    with session._lock:
        sid = session._session_id or "test"
        gen = session._live_paste_generation
    session._chunk_jobs.put(
        _ChunkWhisperJob(
            session_id=sid,
            audio_1d=piece,
            previous_text="",
            reason="fixed",
            live_generation=gen,
        )
    )
    session._chunk_jobs.put(None)
    whisper.join(timeout=5.0)
    assert not whisper.is_alive()
    assert session._chunk_transcripts == ["behouden"]

    session.cancel()


def test_orphaned_chunk_whisper_exits_when_worker_replaced(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    """wait=False restart mag geen zombie-worker achterlaten die sentinels steelt."""

    model = SequenceModel(["x"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=True,
    )
    session.start()
    _wait_until(
        lambda: (
            session._chunk_whisper_thread is not None and session._chunk_whisper_thread.is_alive()
        ),
        timeout=2.0,
    )
    orphan = session._chunk_whisper_thread
    session._stop_incremental_worker(wait=False)
    _wait_until(lambda: not orphan.is_alive(), timeout=2.0)
    session.cancel()


def test_each_chunk_whispers_bounded_window_not_full_buffer(
    tmp_path: Path,
    events: list[CycleEvent],
    saves: list[Path],
) -> None:
    model = SequenceModel(["a", "b", "c"])
    session = _make_session(
        tmp_path=tmp_path,
        events=events,
        saves=saves,
        model=model,
        incremental=True,
        chunk_seconds=0.1,
    )
    seen_sizes: list[int] = []
    original = session.create_temporary_wav

    def spy(chunks: list[Any]) -> Path:
        seen_sizes.append(sum(c.shape[0] for c in chunks))
        return original(chunks)

    session.create_temporary_wav = spy  # type: ignore[method-assign]

    session.start()
    _feed_audio(session, seconds=0.12)
    _wait_until(lambda: len(model.calls) >= 1, timeout=3.0)
    _feed_audio(session, seconds=0.12)
    _wait_until(lambda: len(model.calls) >= 2, timeout=3.0)

    assert len(seen_sizes) >= 2
    # Tweede call mag overlap meenemen, maar niet de hele buffer laten groeien
    # zoals de oude volle-hertranscriptie (die verdubbelde ruwweg).
    max_expected = int(session.sample_rate * (0.1 + 1.5 + 0.05))
    assert seen_sizes[1] <= max_expected
    assert seen_sizes[1] < seen_sizes[0] + int(session.sample_rate * 0.12)

    session.cancel()
