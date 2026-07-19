from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from modules._builtin.speech_to_text import IncrementalSpeechToText
from modules.capabilities.speech_to_text import (
    TranscriptDeltaReceived,
    TranscriptGap,
    TranscriptionStatus,
    TranscriptionStatusChanged,
)
from modules.testing.fake_capture import FakeContinuousCapture
from modules.whisper import SharedWhisper


class AlwaysBusyWhisper:
    @contextmanager
    def try_locked_model(self, timeout: float = 0.0) -> Iterator[Any | None]:
        del timeout
        yield None


def test_gap_when_busy_queue_exceeds_maximum_duration() -> None:
    capture = FakeContinuousCapture()
    events: list[object] = []
    stt = IncrementalSpeechToText(
        whisper=AlwaysBusyWhisper(),
        max_whisper_queue_duration_s=0.1,
        on_event=events.append,
    )
    capture_session = capture.start_session()
    session = stt.start_session(
        capture_session_id=capture_session.session_id,
        capture=capture,
    )

    for _ in range(4):
        capture.emit_seconds(0.05)

    gaps = [event for event in events if isinstance(event, TranscriptGap)]
    assert gaps
    assert gaps[0].session_id == session.session_id
    assert gaps[0].reason == "whisper_queue_overflow"
    assert stt.get_status(session.session_id) == TranscriptionStatus.DELAYED
    assert any(
        isinstance(event, TranscriptionStatusChanged)
        and event.status == TranscriptionStatus.DELAYED
        for event in events
    )


def test_available_whisper_emits_final_delta() -> None:
    capture = FakeContinuousCapture()
    whisper = SharedWhisper()
    whisper.set_model(object())
    events: list[object] = []
    stt = IncrementalSpeechToText(
        whisper=whisper,
        transcribe_fn=lambda _model, _chunk: "hallo wereld",
        on_event=events.append,
    )
    capture_session = capture.start_session()
    session = stt.start_session(
        capture_session_id=capture_session.session_id,
        capture=capture,
    )

    capture.emit_seconds(3)

    received = [event for event in events if isinstance(event, TranscriptDeltaReceived)]
    assert len(received) == 1
    assert received[0].delta.session_id == session.session_id
    assert received[0].delta.text == "hallo wereld"
    assert received[0].delta.is_final is True


def test_transcription_failure_stays_inside_stt_session() -> None:
    capture = FakeContinuousCapture()
    whisper = SharedWhisper()
    whisper.set_model(object())

    def fail_transcription(_model: object, _chunk: object) -> str:
        raise RuntimeError("test failure")

    stt = IncrementalSpeechToText(
        whisper=whisper,
        transcribe_fn=fail_transcription,
    )
    capture_session = capture.start_session()
    session = stt.start_session(
        capture_session_id=capture_session.session_id,
        capture=capture,
    )

    capture.emit_seconds(3)

    assert stt.get_status(session.session_id) == TranscriptionStatus.ERROR
