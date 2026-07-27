"""Cycle-timing formatter + logging bij volle Whisper-stop."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from modules._contract import CycleEvent, CycleEventType
from opnamesessie import CycleTiming, Opnamesessie, format_cycle_timing


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


class StubModel:
    def transcribe(self, path: str, **_kwargs: Any) -> tuple[list[Any], Any]:
        segment = MagicMock()
        segment.text = "hallo wereld"
        segment.end = 0.5
        return [segment], MagicMock()


def _write_wav(path: Path, _rate: int, data: np.ndarray) -> None:
    path.write_bytes(b"RIFF" + data.tobytes()[:8])


def test_format_cycle_timing_full_path() -> None:
    timing = CycleTiming(
        session_id="abcdefgh-ijkl",
        path="full",
        record_s=1.25,
        stop_at=time.perf_counter() - 2.0,
        stop_join_s=0.01,
        wav_s=0.002,
        whisper_s=1.5,
        deliver_s=0.3,
    )
    line = format_cycle_timing(timing)
    assert line.startswith("cycle.timing id=abcdefgh path=full ")
    assert "record=1.250s" in line
    assert "stop_join=0.010s" in line
    assert "wav=0.002s" in line
    assert "whisper=1.500s" in line
    assert "deliver=0.300s" in line
    assert re.search(r"total_after_stop=\d+\.\d{3}s", line)


def test_format_cycle_timing_partial_uses_em_dash() -> None:
    timing = CycleTiming(
        session_id="xyz",
        path="partial",
        record_s=0.5,
        stop_at=time.perf_counter(),
        stop_join_s=0.0,
        wav_s=None,
        whisper_s=None,
        deliver_s=0.1,
    )
    line = format_cycle_timing(timing)
    assert "path=partial" in line
    assert "wav=—" in line
    assert "whisper=—" in line
    assert "deliver=0.100s" in line


def test_stop_logs_cycle_timing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events: list[CycleEvent] = []
    sd = FakeSoundDevice()

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
        on_ready=lambda: None,
        notify=lambda *_a, **_k: None,
        push_level=lambda _level: None,
        reset_levels=lambda: None,
        emit_event=events.append,
        copy_text=lambda _text: None,
        save_transcript=save_transcript,
    )
    sess.bind_audio(numpy_mod=np, sounddevice_mod=sd, write_wav=_write_wav)
    sess.model = StubModel()

    sess.start()
    assert sd.last_callback is not None
    frames = int(sess.sample_rate * 0.2)
    sd.last_callback(np.zeros((frames, 1), dtype=np.float32), frames, None, None)
    time.sleep(0.05)

    # Deterministisch wachten op het cycluseinde: on_ready draait ná
    # timing.log() in het finally-blok, dus daarna staat de print vast in
    # de captured output (eerder: sleep(0.05) hopen dat de print landde).
    import threading

    cycle_done = threading.Event()
    sess.on_ready = cycle_done.set
    sess.stop_and_transcribe()

    assert cycle_done.wait(timeout=30), "dicteercyclus niet afgerond"
    assert any(e.type == CycleEventType.TRANSCRIPT_SAVED for e in events), (
        "transcript niet opgeslagen"
    )
    out = capsys.readouterr().out
    assert "cycle.timing" in out
    assert "path=full" in out
    assert "whisper=" in out
    assert "wav=" in out
