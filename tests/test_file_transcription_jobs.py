"""Tests voor sequentiele bestandstranscriptie-jobs."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import recovery
from modules._builtin.file_transcription.jobs import (
    SAMPLE_RATE,
    FileBatchContext,
    FileItemStatus,
    FileTranscriptionQueue,
)
from modules._contract import CycleEvent, CycleEventType
from modules.whisper import SharedWhisper


class SpyWhisper(SharedWhisper):
    def __init__(self) -> None:
        super().__init__()
        self.locked_calls = 0
        self.try_calls = 0
        self.priority_calls = 0

    @contextmanager
    def locked_model(self) -> Iterator[Any]:
        self.locked_calls += 1
        with super().locked_model() as model:
            yield model

    @contextmanager
    def try_locked_model(self, timeout: float = 0.0) -> Iterator[Any | None]:
        self.try_calls += 1
        with super().try_locked_model(timeout=timeout) as model:
            yield model

    @contextmanager
    def dictation_priority(self) -> Iterator[None]:
        self.priority_calls += 1
        with super().dictation_priority():
            yield


class FakeModel:
    def __init__(self, text: str = "hallo") -> None:
        self.text = text
        self.calls: list[Any] = []
        self.on_call: Any = None

    def transcribe(self, audio: Any, **kwargs: object) -> tuple[list[object], object]:
        self.calls.append((audio, kwargs))
        if self.on_call is not None:
            self.on_call()

        class _Seg:
            def __init__(self, value: str) -> None:
                self.text = value

        return [_Seg(self.text)], object()


@dataclass
class FakeHost:
    save_dir: Path
    busy: bool = False
    kwargs: dict[str, Any] = field(default_factory=lambda: {"language": "nl", "beam_size": 5})
    events: list[CycleEvent] = field(default_factory=list)
    dest: str | None = "Notulen"

    def is_busy(self) -> bool:
        return self.busy

    def transcribe_kwargs(self) -> dict[str, Any]:
        return dict(self.kwargs)

    def emit(self, event: CycleEvent) -> None:
        self.events.append(event)

    def capture_batch(self) -> FileBatchContext:
        directory = self.save_dir
        dest = self.dest

        def save(text: str) -> Path:
            return recovery.save_transcript(
                text,
                directory=directory,
                stem_prefix=recovery.FILE_TRANSCRIPT_STEM_PREFIX,
            )

        return FileBatchContext(destination_name=dest, save_discrete=save)

    def destination_display(self) -> tuple[str | None, str]:
        return self.dest, str(self.save_dir)

    def destinations(self) -> list[dict[str, Any]]:
        return []


def _queue(
    tmp_path: Path,
    *,
    whisper: SpyWhisper,
    host: FakeHost | None = None,
    decode_fn: Any = None,
    sleep_fn: Any = None,
    slice_seconds: float = 30.0,
) -> tuple[FileTranscriptionQueue, FakeHost]:
    host = host or FakeHost(save_dir=tmp_path / "out")
    host.save_dir.mkdir(parents=True, exist_ok=True)
    queue = FileTranscriptionQueue(
        whisper=whisper,
        host=host,
        decode_fn=decode_fn or (lambda _path: np.zeros(SAMPLE_RATE, dtype=np.float32)),
        sleep_fn=sleep_fn or (lambda _s: None),
        poll_s=0.0,
        slice_seconds=slice_seconds,
    )
    return queue, host


def _wav(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(b"RIFF")
    return path


def test_start_refuses_when_host_busy(tmp_path: Path) -> None:
    whisper = SpyWhisper()
    whisper.set_model(FakeModel())
    host = FakeHost(save_dir=tmp_path / "out", busy=True)
    queue, _ = _queue(tmp_path, whisper=whisper, host=host)
    assert queue.start([_wav(tmp_path, "a.wav")]) == "modules.file_transcription.busy"
    assert not queue.is_running()
    assert whisper.locked_calls == 0
    assert whisper.priority_calls == 0


def test_start_refuses_when_model_not_ready(tmp_path: Path) -> None:
    whisper = SpyWhisper()
    queue, _ = _queue(tmp_path, whisper=whisper)
    assert queue.start([_wav(tmp_path, "a.wav")]) == "model.load_failed"


def test_sequential_wav_jobs_save_file_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)
    whisper = SpyWhisper()
    model = FakeModel("hallo wereld")
    whisper.set_model(model)
    queue, host = _queue(tmp_path, whisper=whisper)
    first = _wav(tmp_path, "a.wav")
    second = _wav(tmp_path, "b.wav")
    assert queue.start([first, second]) is None
    queue.join(timeout=5)
    assert [item.status for item in queue.items] == [
        FileItemStatus.DONE,
        FileItemStatus.DONE,
    ]
    assert all(
        item.saved_path is not None and item.saved_path.name.startswith("file_")
        for item in queue.items
    )
    sources = [event.source for event in host.events]
    assert "recovery" not in sources
    assert all(event.source == "file" for event in host.events if event.source)
    types = [event.type for event in host.events]
    assert types.count(CycleEventType.TRANSCRIPT_SAVED) == 2
    assert whisper.locked_calls == 0
    assert whisper.priority_calls == 0
    assert whisper.try_calls >= 2
    assert model.calls[0][1]["language"] == "nl"


def test_non_wav_is_per_file_error_and_rest_continues(tmp_path: Path) -> None:
    whisper = SpyWhisper()
    whisper.set_model(FakeModel())
    decoded: list[Path] = []

    def decode(path: Path) -> np.ndarray:
        decoded.append(path)
        return np.zeros(SAMPLE_RATE, dtype=np.float32)

    queue, host = _queue(tmp_path, whisper=whisper, decode_fn=decode)
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"xx")
    wav = _wav(tmp_path, "ok.wav")
    assert queue.start([mp3, wav]) is None
    queue.join(timeout=5)
    assert queue.items[0].status is FileItemStatus.ERROR
    assert queue.items[0].error_key == "modules.file_transcription.invalid_format"
    assert queue.items[1].status is FileItemStatus.DONE
    assert decoded == [wav]
    assert any(event.type is CycleEventType.CYCLE_ERROR for event in host.events)


def test_empty_speech_errors_and_continues(tmp_path: Path) -> None:
    whisper = SpyWhisper()
    model = FakeModel("")
    whisper.set_model(model)
    queue, _ = _queue(tmp_path, whisper=whisper)
    assert queue.start([_wav(tmp_path, "a.wav"), _wav(tmp_path, "b.wav")]) is None
    queue.join(timeout=5)
    assert queue.items[0].status is FileItemStatus.ERROR
    assert queue.items[0].error_key == "modules.file_transcription.empty_audio"
    assert queue.items[1].status is FileItemStatus.ERROR


def test_slices_yield_to_dictation(tmp_path: Path) -> None:
    whisper = SpyWhisper()
    model = FakeModel("stuk")
    whisper.set_model(model)
    sleeps: list[float] = []

    def on_call() -> None:
        if len(model.calls) == 1:
            whisper._dictation_count = 1

    model.on_call = on_call

    def sleep(_seconds: float) -> None:
        sleeps.append(_seconds)
        whisper._dictation_count = 0

    audio = np.zeros(int(45 * SAMPLE_RATE), dtype=np.float32)
    queue, _ = _queue(
        tmp_path,
        whisper=whisper,
        decode_fn=lambda _path: audio,
        sleep_fn=sleep,
        slice_seconds=30.0,
    )
    assert queue.start([_wav(tmp_path, "long.wav")]) is None
    queue.join(timeout=5)
    assert queue.items[0].status is FileItemStatus.DONE
    assert len(model.calls) == 2
    assert sleeps
    assert whisper.locked_calls == 0
    assert whisper.priority_calls == 0


def test_cancel_skips_remaining_files(tmp_path: Path) -> None:
    whisper = SpyWhisper()
    model = FakeModel("x")
    whisper.set_model(model)
    queue: FileTranscriptionQueue | None = None

    def on_call() -> None:
        assert queue is not None
        queue.cancel()

    model.on_call = on_call
    built, _host = _queue(tmp_path, whisper=whisper)
    queue = built
    assert queue.start([_wav(tmp_path, "a.wav"), _wav(tmp_path, "b.wav")]) is None
    queue.join(timeout=5)
    assert queue.items[1].status is FileItemStatus.CANCELLED


def test_failure_does_not_write_recovery_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recovery, "config_dir", lambda: tmp_path)
    whisper = SpyWhisper()
    whisper.set_model(FakeModel())

    def decode(_path: Path) -> np.ndarray:
        raise OSError("cannot decode")

    queue, _ = _queue(tmp_path, whisper=whisper, decode_fn=decode)
    assert queue.start([_wav(tmp_path, "a.wav")]) is None
    queue.join(timeout=5)
    assert queue.items[0].status is FileItemStatus.ERROR
    assert recovery.list_recovery_wavs() == []


def test_in_memory_events_may_include_audio_path(tmp_path: Path) -> None:
    whisper = SpyWhisper()
    whisper.set_model(FakeModel("ok"))
    queue, host = _queue(tmp_path, whisper=whisper)
    wav = _wav(tmp_path, "interview.wav")
    assert queue.start([wav]) is None
    queue.join(timeout=5)
    transcribing = next(
        event for event in host.events if event.type is CycleEventType.CYCLE_TRANSCRIBING
    )
    assert transcribing.audio_path is not None
    assert transcribing.audio_path.endswith("interview.wav")
    saved = next(event for event in host.events if event.type is CycleEventType.TRANSCRIPT_SAVED)
    assert saved.path is not None
    assert Path(saved.path).name.startswith("file_")
    assert saved.recovery_path is None
