"""Incrementele transcriptie via de gedeelde Whisper-instantie."""

from __future__ import annotations

import logging
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Condition, Lock, RLock
from typing import Any

import numpy as np

from modules._contract import CycleEvent, ModuleContext
from modules.capabilities.continuous_capture import AudioChunk, AudioChunkReceived
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID,
    CONTRACT_VERSION,
    SttEventHandler,
    TranscriptDelta,
    TranscriptDeltaReceived,
    TranscriptGap,
    TranscriptionSession,
    TranscriptionStatus,
    TranscriptionStatusChanged,
)
from modules.whisper import SharedWhisper

MAX_WHISPER_QUEUE_DURATION_S = 10.0

log = logging.getLogger("praatmaar.speech_to_text")

TranscribeFn = Callable[[Any, AudioChunk], str]


@dataclass
class _TranscriptionState:
    session_id: str
    capture_session_id: str
    capture: Any
    capture_handler: Callable[[object], None]
    handlers: list[SttEventHandler] = field(default_factory=list)
    queue: deque[AudioChunk] = field(default_factory=deque)
    callback_condition: Condition = field(default_factory=Condition)
    active_callbacks: int = 0
    drain_lock: Lock = field(default_factory=Lock)
    status: TranscriptionStatus = TranscriptionStatus.IDLE
    sequence: int = 0
    stopping: bool = False


class IncrementalSpeechToText:
    """Zet capture-chunks om in deltas zonder dicteerwerk te blokkeren."""

    def __init__(
        self,
        *,
        whisper: SharedWhisper,
        max_whisper_queue_duration_s: float = MAX_WHISPER_QUEUE_DURATION_S,
        transcribe_fn: TranscribeFn | None = None,
        on_event: SttEventHandler | None = None,
    ) -> None:
        if max_whisper_queue_duration_s <= 0:
            raise ValueError("max_whisper_queue_duration_s moet groter dan nul zijn")
        self._whisper = whisper
        self._max_queue_duration_ms = round(max_whisper_queue_duration_s * 1000)
        self._transcribe_fn = transcribe_fn or self._transcribe
        self._on_event = on_event
        self._sessions: dict[str, _TranscriptionState] = {}
        self._lock = RLock()

    def start_session(
        self,
        *,
        capture_session_id: str,
        capture: Any,
        config: dict[str, Any] | None = None,
    ) -> TranscriptionSession:
        del config
        session_id = str(uuid.uuid4())

        def handle_capture_event(event: object) -> None:
            self._handle_capture_event(session_id, event)

        state = _TranscriptionState(
            session_id=session_id,
            capture_session_id=capture_session_id,
            capture=capture,
            capture_handler=handle_capture_event,
        )
        with self._lock:
            self._sessions[session_id] = state
        capture.subscribe(capture_session_id, handle_capture_event)
        self._set_status(state, TranscriptionStatus.ACTIVE)
        return TranscriptionSession(session_id=session_id)

    def subscribe(self, session_id: str, handler: SttEventHandler) -> None:
        state = self._require_session(session_id)
        with self._lock:
            if handler not in state.handlers:
                state.handlers.append(handler)
            status = state.status
        self._notify(handler, TranscriptionStatusChanged(session_id, status))

    def unsubscribe(self, session_id: str, handler: SttEventHandler) -> None:
        state = self._require_session(session_id)
        with self._lock:
            if handler in state.handlers:
                state.handlers.remove(handler)

    def stop_session(self, session_id: str) -> None:
        state = self._require_session(session_id)
        with state.callback_condition:
            with self._lock:
                state.stopping = True
        state.capture.unsubscribe(state.capture_session_id, state.capture_handler)
        with state.callback_condition:
            state.callback_condition.wait_for(lambda: state.active_callbacks == 0)
        with state.drain_lock:
            with self._lock:
                state.queue.clear()
                state.status = TranscriptionStatus.IDLE

    def get_status(self, session_id: str) -> TranscriptionStatus:
        return self._require_session(session_id).status

    def shutdown(self) -> None:
        with self._lock:
            session_ids = list(self._sessions)
        for session_id in session_ids:
            state = self._require_session(session_id)
            if state.status != TranscriptionStatus.IDLE:
                self.stop_session(session_id)

    def _handle_capture_event(self, session_id: str, event: object) -> None:
        if not isinstance(event, AudioChunkReceived):
            return
        state = self._require_session(session_id)
        with state.callback_condition:
            with self._lock:
                if state.stopping:
                    return
                state.active_callbacks += 1
        try:
            with self._lock:
                state.queue.append(event.chunk)
                gaps = self._trim_queue(state)
            if gaps:
                self._set_status(state, TranscriptionStatus.DELAYED)
            for gap in gaps:
                self._publish(state, gap)
            self._drain_queue(state)
        finally:
            with state.callback_condition:
                state.active_callbacks -= 1
                if state.active_callbacks == 0:
                    state.callback_condition.notify_all()

    def _trim_queue(self, state: _TranscriptionState) -> list[TranscriptGap]:
        gaps: list[TranscriptGap] = []
        while (
            state.queue
            and state.queue[-1].end_ms - state.queue[0].start_ms > self._max_queue_duration_ms
        ):
            dropped = state.queue.popleft()
            gap_end_ms = (
                min(dropped.end_ms, state.queue[0].start_ms) if state.queue else dropped.end_ms
            )
            gaps.append(
                TranscriptGap(
                    session_id=state.session_id,
                    start_ms=dropped.start_ms,
                    end_ms=gap_end_ms,
                    reason="whisper_queue_overflow",
                )
            )
        return gaps

    def _drain_queue(self, state: _TranscriptionState) -> None:
        with state.drain_lock:
            self._drain_queue_serially(state)

    def _drain_queue_serially(self, state: _TranscriptionState) -> None:
        while True:
            with self._lock:
                if state.stopping:
                    return
                queue_empty = not state.queue
                was_delayed = state.status == TranscriptionStatus.DELAYED
            if queue_empty:
                if was_delayed:
                    self._set_status(state, TranscriptionStatus.ACTIVE)
                return

            if self._whisper.dictation_active:
                self._set_status(state, TranscriptionStatus.DELAYED)
                return

            with self._whisper.try_locked_model() as model:
                if model is None:
                    self._set_status(state, TranscriptionStatus.DELAYED)
                    return
                with self._lock:
                    if not state.queue:
                        continue
                    chunk = state.queue.popleft()
                try:
                    text = self._transcribe_fn(model, chunk).strip()
                except Exception as exc:
                    with self._lock:
                        if state.stopping:
                            return
                    log.exception("Transcriptie faalde voor sessie %s", state.session_id)
                    self._set_status(
                        state,
                        TranscriptionStatus.ERROR,
                        f"Whisper transcription failed: {exc}",
                    )
                    return

            with self._lock:
                if state.stopping:
                    return
                state.sequence += 1
                sequence = state.sequence
            if text:
                self._publish(
                    state,
                    TranscriptDeltaReceived(
                        TranscriptDelta(
                            session_id=state.session_id,
                            sequence=sequence,
                            start_ms=chunk.start_ms,
                            end_ms=chunk.end_ms,
                            text=text,
                            is_final=True,
                            confidence=1.0,
                        )
                    ),
                )

    def _set_status(
        self,
        state: _TranscriptionState,
        status: TranscriptionStatus,
        message: str | None = None,
    ) -> None:
        with self._lock:
            if state.stopping:
                return
            if state.status == status and message is None:
                return
            state.status = status
        self._publish(
            state,
            TranscriptionStatusChanged(
                session_id=state.session_id,
                status=status,
                message=message,
            ),
        )

    def _publish(self, state: _TranscriptionState, event: object) -> None:
        with self._lock:
            if state.stopping:
                return
            handlers = list(state.handlers)
        if self._on_event is not None:
            self._notify(self._on_event, event)
        for handler in handlers:
            self._notify(handler, event)

    @staticmethod
    def _notify(handler: SttEventHandler, event: object) -> None:
        try:
            handler(event)
        except Exception:
            log.exception("STT-eventhandler faalde")

    def _require_session(self, session_id: str) -> _TranscriptionState:
        with self._lock:
            state = self._sessions.get(session_id)
        if state is None:
            raise ValueError(f"Onbekende transcriptiesessie: {session_id}")
        return state

    @staticmethod
    def _transcribe(model: Any, chunk: AudioChunk) -> str:
        audio = np.frombuffer(chunk.pcm_f32, dtype="<f4")
        segments, _info = model.transcribe(audio)
        return " ".join(segment.text.strip() for segment in segments if segment.text.strip())


class SpeechToTextModule:
    """Registreert incrementele lokale spraak-naar-tekst."""

    id = "speech-to-text"

    def __init__(self, *, transcribe_fn: TranscribeFn | None = None) -> None:
        self._transcribe_fn = transcribe_fn
        self._engine: IncrementalSpeechToText | None = None
        self._capabilities: CapabilityRegistry | None = None

    def display_name_key(self) -> str:
        return "modules.speech_to_text.name"

    def description_key(self) -> str:
        return "modules.speech_to_text.description"

    def default_enabled(self) -> bool:
        return True

    def on_app_start(self, ctx: ModuleContext) -> None:
        self._engine = IncrementalSpeechToText(
            whisper=ctx.whisper,
            transcribe_fn=self._transcribe_fn,
        )
        self._capabilities = ctx.capabilities
        ctx.capabilities.register(
            capability_id=CAPABILITY_ID,
            provider=self._engine,
            owner_module_id=self.id,
            contract_version=CONTRACT_VERSION,
        )

    def on_event(self, event: CycleEvent) -> None:
        del event

    def on_app_shutdown(self) -> None:
        try:
            if self._engine is not None:
                self._engine.shutdown()
        finally:
            try:
                if self._capabilities is not None:
                    self._capabilities.unregister_owner(self.id)
            finally:
                self._engine = None
                self._capabilities = None
