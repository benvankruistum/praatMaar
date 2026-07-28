from __future__ import annotations

import threading
import time
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


def _wait_until(predicate, *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(f"condition not met within {timeout}s")


class AlwaysBusyWhisper:
    dictation_active = False

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

    try:
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
    finally:
        # Anders blijft de drain-thread tot procesende pollen en concurreert
        # hij met latere tests om de GIL (flake-bron).
        stt.shutdown()


def test_session_config_overrides_default_queue_duration() -> None:
    capture = FakeContinuousCapture()
    events: list[object] = []
    stt = IncrementalSpeechToText(
        whisper=AlwaysBusyWhisper(),
        max_whisper_queue_duration_s=10,
        on_event=events.append,
    )
    capture_session = capture.start_session()
    session = stt.start_session(
        capture_session_id=capture_session.session_id,
        capture=capture,
        config={"max_whisper_queue_duration_s": 0.1},
    )

    try:
        for _ in range(4):
            capture.emit_seconds(0.05)

        assert any(
            isinstance(event, TranscriptGap)
            and event.session_id == session.session_id
            and event.reason == "whisper_queue_overflow"
            for event in events
        )
    finally:
        stt.shutdown()


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

    _wait_until(lambda: any(isinstance(event, TranscriptDeltaReceived) for event in events))
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

    _wait_until(lambda: stt.get_status(session.session_id) == TranscriptionStatus.ERROR)
    assert stt.get_status(session.session_id) == TranscriptionStatus.ERROR


def test_dictation_priority_stops_buddy_reclaiming_between_chunks() -> None:
    capture = FakeContinuousCapture()
    whisper = SharedWhisper()
    whisper.set_model(object())
    buddy_started = threading.Event()
    finish_buddy_chunk = threading.Event()
    dictation_acquired = threading.Event()
    release_dictation = threading.Event()
    transcribed_chunks: list[str] = []

    def transcribe(_model: object, chunk: object) -> str:
        transcribed_chunks.append(chunk.chunk_id)
        if len(transcribed_chunks) == 1:
            buddy_started.set()
            assert finish_buddy_chunk.wait(timeout=2)
        return "buddy"

    stt = IncrementalSpeechToText(whisper=whisper, transcribe_fn=transcribe)
    capture_session = capture.start_session()
    session = stt.start_session(
        capture_session_id=capture_session.session_id,
        capture=capture,
    )
    buddy = threading.Thread(target=capture.emit_seconds, args=(0.05,))
    buddy.start()
    assert buddy_started.wait(timeout=1)

    queued = [threading.Thread(target=capture.emit_seconds, args=(0.05,)) for _ in range(4)]
    for producer in queued:
        producer.start()

    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        with stt._lock:
            if len(stt._sessions[session.session_id].queue) == len(queued):
                break
        time.sleep(0.005)
    else:
        raise AssertionError("Buddy chunks were not queued in time")

    def dictate() -> None:
        with whisper.locked_model():
            dictation_acquired.set()
            release_dictation.wait(timeout=2)

    dictation = threading.Thread(target=dictate)
    dictation.start()
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline and not whisper.dictation_active:
        time.sleep(0.005)
    assert whisper.dictation_active

    finish_buddy_chunk.set()
    assert dictation_acquired.wait(timeout=1)
    assert transcribed_chunks == ["1"]
    assert stt.get_status(session.session_id) == TranscriptionStatus.DELAYED

    release_dictation.set()
    buddy.join(timeout=1)
    dictation.join(timeout=1)
    for producer in queued:
        producer.join(timeout=1)


def test_stop_waits_for_drain_and_publishes_in_flight_delta() -> None:
    capture = FakeContinuousCapture()
    whisper = SharedWhisper()
    whisper.set_model(object())
    transcription_started = threading.Event()
    finish_transcription = threading.Event()
    stop_done = threading.Event()
    events: list[object] = []

    def transcribe(_model: object, _chunk: object) -> str:
        transcription_started.set()
        assert finish_transcription.wait(timeout=2)
        return "eindstuk"

    stt = IncrementalSpeechToText(
        whisper=whisper,
        transcribe_fn=transcribe,
        on_event=events.append,
    )
    capture_session = capture.start_session()
    session = stt.start_session(
        capture_session_id=capture_session.session_id,
        capture=capture,
    )
    emitter = threading.Thread(target=capture.emit_seconds, args=(0.05,))
    emitter.start()
    assert transcription_started.wait(timeout=1)

    def stop() -> None:
        stt.stop_session(session.session_id)
        stop_done.set()

    stopper = threading.Thread(target=stop)
    stopper.start()
    try:
        assert not stop_done.wait(timeout=0.05)
    finally:
        finish_transcription.set()
        emitter.join(timeout=1)
        stopper.join(timeout=1)

    assert stop_done.is_set()
    deltas = [e for e in events if isinstance(e, TranscriptDeltaReceived)]
    assert len(deltas) == 1
    assert deltas[0].delta.text == "eindstuk"
    assert stt.get_status(session.session_id) == TranscriptionStatus.IDLE


def test_stop_drains_queued_chunks() -> None:
    capture = FakeContinuousCapture()
    whisper = SharedWhisper()
    whisper.set_model(object())
    gate = threading.Event()
    events: list[object] = []
    seen: list[str] = []

    def transcribe(_model: object, chunk: object) -> str:
        gate.wait(timeout=2)
        text = f"c{chunk.chunk_id}"
        seen.append(text)
        return text

    stt = IncrementalSpeechToText(
        whisper=whisper,
        transcribe_fn=transcribe,
        on_event=events.append,
        max_whisper_queue_duration_s=60.0,
    )
    capture_session = capture.start_session()
    session = stt.start_session(
        capture_session_id=capture_session.session_id,
        capture=capture,
    )
    capture.emit_seconds(0.05)
    capture.emit_seconds(0.05)
    # Laat enqueue afronden, daarna stop vóór gate open — flush moet beide doen.
    time.sleep(0.05)
    gate.set()
    stt.stop_session(session.session_id)

    deltas = [e for e in events if isinstance(e, TranscriptDeltaReceived)]
    assert len(deltas) >= 2
    assert stt.get_status(session.session_id) == TranscriptionStatus.IDLE
    assert len(seen) >= 2


def test_stop_waits_for_capture_callback_and_suppresses_late_events() -> None:
    capture = FakeContinuousCapture()
    callback_started = threading.Event()
    finish_callback = threading.Event()
    stop_done = threading.Event()
    events: list[object] = []
    late_events: list[object] = []

    def record_event(event: object) -> None:
        events.append(event)
        if stop_done.is_set():
            late_events.append(event)

    stt = IncrementalSpeechToText(
        whisper=AlwaysBusyWhisper(),
        max_whisper_queue_duration_s=0.01,
        on_event=record_event,
        # Korte flush-timeout: de volle 2s liet nauwelijks marge op de
        # stopper-join hieronder (flake-bron op trage CI).
        flush_busy_timeout_s=0.1,
    )
    capture_session = capture.start_session()
    session = stt.start_session(
        capture_session_id=capture_session.session_id,
        capture=capture,
    )
    events.clear()

    original_trim_queue = stt._trim_queue
    # Asserts op een workerthread worden een warning i.p.v. een failure; vang
    # ze op en laat de main-thread erover struikelen.
    thread_errors: list[BaseException] = []

    def pause_after_stopping_check(state: object) -> list[TranscriptGap]:
        try:
            callback_started.set()
            # Ruime failsafe: bij succes kost dit niets, en scheduling onder
            # CI-load haalt geen krappe deadline meer.
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with stt._lock:
                    if getattr(state, "stopping", False):
                        break
                time.sleep(0.001)
            else:
                raise AssertionError("stop_session zette stopping niet binnen 30s")
            if not finish_callback.wait(timeout=30):
                raise AssertionError("finish_callback bleef 30s uit")
        except BaseException as exc:  # noqa: BLE001 - doorgeven aan main-thread
            thread_errors.append(exc)
            raise
        return original_trim_queue(state)

    stt._trim_queue = pause_after_stopping_check
    emitter = threading.Thread(target=capture.emit_seconds, args=(0.05,))
    emitter.start()
    assert callback_started.wait(timeout=1)

    def stop() -> None:
        stt.stop_session(session.session_id)
        stop_done.set()

    stopper = threading.Thread(target=stop)
    stopper.start()
    try:
        assert not stop_done.wait(timeout=0.05)
    finally:
        finish_callback.set()
        emitter.join(timeout=1)
        # Model blijft bezet → flush-busy-timeout (~2s) vóór stop terugkeert.
        stopper.join(timeout=5)

    assert not thread_errors, f"fout op workerthread: {thread_errors[0]}"
    assert stop_done.is_set()
    assert late_events == []
    assert not any(isinstance(event, TranscriptGap) for event in events)
    assert not any(
        isinstance(event, TranscriptionStatusChanged)
        and event.status == TranscriptionStatus.DELAYED
        for event in events
    )
    assert stt.get_status(session.session_id) == TranscriptionStatus.IDLE
