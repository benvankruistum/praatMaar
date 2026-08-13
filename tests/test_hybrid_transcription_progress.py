"""Integratie: hybride voortgang beweegt tijdens trage Whisper vóór segmenten."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np

from indicator._contract import get_transcription_progress, set_transcription_progress
from opnamesessie import Opnamesessie
from transcription_progress import MAX_TICK_PERCENT


class FakeHost:
    def paste(self) -> None:
        pass


class FakeStream:
    def __init__(self) -> None:
        self.active = False

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def close(self) -> None:
        self.active = False


class FakeSoundDevice:
    def __init__(self) -> None:
        self.last_callback: Any = None
        self.stream = FakeStream()

    def InputStream(self, **kwargs: Any) -> FakeStream:
        self.last_callback = kwargs.get("callback")
        return self.stream


class SlowModel:
    """Simuleert VAD/encode-fase: wacht vóór het eerste segment."""

    def __init__(self, delay_s: float = 0.35) -> None:
        self.delay_s = delay_s

    def transcribe(self, path: str, **_kwargs: Any) -> tuple[list[Any], Any]:
        time.sleep(self.delay_s)
        segment = MagicMock()
        segment.text = "hallo"
        segment.end = 2.0
        return [segment], MagicMock()


def _write_wav(path: Path, _rate: int, data: np.ndarray) -> None:
    path.write_bytes(b"RIFF" + data.tobytes()[:8])


def test_full_path_progress_moves_before_first_segment(tmp_path: Path) -> None:
    set_transcription_progress(None)
    sd = FakeSoundDevice()
    done = threading.Event()
    samples: list[int | None] = []
    stop_poll = threading.Event()

    def poll() -> None:
        while not stop_poll.is_set():
            samples.append(get_transcription_progress())
            time.sleep(0.03)

    def save_transcript(text: str) -> Path:
        path = tmp_path / "out.txt"
        path.write_text(text, encoding="utf-8")
        return path

    sess = Opnamesessie(
        host=FakeHost(),
        sample_rate=16000,
        channels=1,
        minimum_recording_seconds=0.01,
        auto_paste=False,
        paste_delay_seconds=0.0,
        language="nl",
        delete_temp_audio=True,
        mode="toggle",
        warm_microphone=False,
        incremental_transcription=False,
        wait_until_modifiers_clear=lambda: None,
        on_ready=done.set,
        notify=lambda *_a, **_k: None,
        push_level=lambda _level: None,
        reset_levels=lambda: None,
        copy_text=lambda _text: None,
        save_transcript=save_transcript,
    )
    sess.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=_write_wav)
    # Ruim genoeg audio zodat RTF-schatting niet meteen op 95% zit.
    sess.model = SlowModel(delay_s=0.4)

    sess.start()
    assert sd.last_callback is not None
    frames = int(sess.sample_rate * 2.0)
    sd.last_callback(np.zeros((frames, 1), dtype=np.float32), frames, None, None)
    time.sleep(0.05)

    poller = threading.Thread(target=poll, daemon=True)
    poller.start()
    sess.stop_and_transcribe()
    assert done.wait(timeout=10), "dicteercyclus niet afgerond"
    stop_poll.set()
    poller.join(timeout=1.0)

    mid = [p for p in samples if isinstance(p, int) and 1 <= p <= MAX_TICK_PERCENT]
    assert mid, f"verwacht tussenliggende progress, kreeg: {samples[:20]}…"
    assert any(p == 100 for p in samples) or get_transcription_progress() in (100, None)

    set_transcription_progress(None)
