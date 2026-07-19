"""Meeting Buddy session binding and transcript-to-state orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from modules.capabilities.continuous_capture import (
    CAPABILITY_ID as CAP_CAPTURE,
)
from modules.capabilities.continuous_capture import (
    CONTRACT_VERSION as CAPTURE_CONTRACT_VERSION,
)
from modules.capabilities.continuous_capture import (
    CaptureGap,
    CaptureStatus,
    CaptureStatusChanged,
)
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID as CAP_STT,
)
from modules.capabilities.speech_to_text import (
    CONTRACT_VERSION as STT_CONTRACT_VERSION,
)
from modules.capabilities.speech_to_text import (
    TranscriptDeltaReceived,
    TranscriptGap,
)

from .config import load_meeting_buddy_config
from .heuristics import HeuristicsEngine
from .hints import HintEngine
from .observability import EventObserver, log_event
from .prep import parse_agenda
from .state import Hint, MeetingState, TopicSource
from .state_service import MeetingStateService, StateProposal

UiUpdate = Callable[[MeetingState], None]


@dataclass(frozen=True)
class MeetingSessionBinding:
    meeting_session_id: str
    capture_session_id: str
    transcription_session_id: str


class MeetingOrchestrator:
    """Owns a Meeting Buddy session and its capability subscriptions."""

    def __init__(
        self,
        *,
        capabilities: CapabilityRegistry,
        app_dir: Path,
        observer: EventObserver | None = None,
        on_ui_update: UiUpdate | None = None,
    ) -> None:
        self._capabilities = capabilities
        self._config = load_meeting_buddy_config(app_dir)
        self._observer = observer
        self._on_ui_update = on_ui_update or (lambda _state: None)
        self._state_service = MeetingStateService()
        self._heuristics = HeuristicsEngine()
        self._hints = HintEngine()
        self._agenda_text = ""
        self._binding: MeetingSessionBinding | None = None
        self._state: MeetingState | None = None
        self._capture: Any = None
        self._stt: Any = None
        self._started_at: float | None = None

    @property
    def binding(self) -> MeetingSessionBinding | None:
        return self._binding

    @property
    def state(self) -> MeetingState:
        if self._state is None:
            raise RuntimeError("Meeting Buddy is niet gestart")
        return self._state

    @property
    def agenda_text(self) -> str:
        return self._agenda_text

    def set_agenda(self, text: str) -> None:
        self._agenda_text = text

    def start(self, agenda_text: str | None = None) -> None:
        if self._binding is not None:
            raise RuntimeError("Meeting Buddy is al gestart")
        if agenda_text is not None:
            self.set_agenda(agenda_text)

        capture = self._capabilities.require(
            CAP_CAPTURE,
            minimum_contract_version=CAPTURE_CONTRACT_VERSION,
        )
        stt = self._capabilities.require(
            CAP_STT,
            minimum_contract_version=STT_CONTRACT_VERSION,
        )

        capture_session = capture.start_session()
        try:
            transcription_session = stt.start_session(
                capture_session_id=capture_session.session_id,
                capture=capture,
            )
        except Exception:
            capture.stop_session(capture_session.session_id)
            raise

        meeting_session_id = str(uuid4())
        self._binding = MeetingSessionBinding(
            meeting_session_id=meeting_session_id,
            capture_session_id=capture_session.session_id,
            transcription_session_id=transcription_session.session_id,
        )
        self._capture = capture
        self._stt = stt
        self._started_at = time.monotonic()
        self._state = MeetingState.empty(meeting_session_id)

        capture.subscribe(capture_session.session_id, self.on_capture_status)
        stt.subscribe(transcription_session.session_id, self.on_stt_event)
        self._apply_agenda()
        log_event(
            self._observer,
            "meeting_started",
            meeting_session_id=meeting_session_id,
            capture_session_id=capture_session.session_id,
            transcription_session_id=transcription_session.session_id,
        )
        self._notify_ui()

    def stop(self) -> None:
        binding = self._binding
        if binding is None:
            return

        self._stt.unsubscribe(binding.transcription_session_id, self.on_stt_event)
        self._capture.unsubscribe(binding.capture_session_id, self.on_capture_status)
        self._stt.stop_session(binding.transcription_session_id)
        self._capture.stop_session(binding.capture_session_id)
        duration_ms = int(self._elapsed_s() * 1000)
        log_event(
            self._observer,
            "meeting_stopped",
            meeting_session_id=binding.meeting_session_id,
            duration_ms=duration_ms,
        )
        self._binding = None
        self._capture = None
        self._stt = None
        self._started_at = None

    def on_stt_event(self, event: object) -> None:
        binding = self._binding
        if binding is None:
            return
        if isinstance(event, TranscriptGap):
            log_event(
                self._observer,
                "transcript_gap",
                meeting_session_id=binding.meeting_session_id,
                transcription_session_id=event.session_id,
                start_ms=event.start_ms,
                end_ms=event.end_ms,
                reason=event.reason,
            )
            return
        if not isinstance(event, TranscriptDeltaReceived):
            return
        if event.delta.session_id != binding.transcription_session_id:
            return

        now_s = self._elapsed_s()
        for proposal in self._heuristics.proposals_for(
            event.delta,
            self.state,
            self._config,
            now_s,
        ):
            previous_version = self.state.version
            self._state = self._state_service.apply(self.state, proposal)
            log_event(
                self._observer,
                "state_version",
                meeting_session_id=binding.meeting_session_id,
                previous_version=previous_version,
                state_version=self.state.version,
                proposal_type=proposal.type,
            )

        self._update_hints(now_s)
        self._notify_ui()

    def on_capture_status(self, event: object) -> None:
        binding = self._binding
        if binding is None:
            return
        if isinstance(event, CaptureStatusChanged) and event.status == CaptureStatus.RECONNECTING:
            log_event(
                self._observer,
                "capture_restart",
                meeting_session_id=binding.meeting_session_id,
                capture_session_id=event.session_id,
            )
        elif isinstance(event, CaptureGap):
            log_event(
                self._observer,
                "transcript_gap",
                meeting_session_id=binding.meeting_session_id,
                capture_session_id=event.session_id,
                start_ms=event.start_ms,
                end_ms=event.end_ms,
                reason=event.reason,
            )

    def _apply_agenda(self) -> None:
        topics = parse_agenda(self._agenda_text)
        if not topics:
            return
        proposal = StateProposal(
            proposal_id=f"agenda-{uuid4()}",
            meeting_session_id=self.state.meeting_session_id,
            type="add_topics",
            payload={
                "topics": [{"title": title, "source": TopicSource.AGENDA.value} for title in topics]
            },
            source_delta_ids=(),
            confidence=1.0,
            created_at=0.0,
        )
        self._state = self._state_service.apply(self.state, proposal)

    def _update_hints(self, now_s: float) -> None:
        hints = self._hints.evaluate(self.state, self._config, now_s)
        if tuple(hints) == self.state.emitted_hints:
            return
        proposal = StateProposal(
            proposal_id=f"hints-{uuid4()}",
            meeting_session_id=self.state.meeting_session_id,
            type="set_hints",
            payload={"hints": [_hint_payload(hint) for hint in hints]},
            source_delta_ids=(),
            confidence=1.0,
            created_at=now_s,
        )
        self._state = self._state_service.apply(self.state, proposal)
        for hint in hints:
            log_event(
                self._observer,
                "hint_emitted",
                meeting_session_id=self.state.meeting_session_id,
                hint_type=_enum_value(hint.type),
                related_entity_id=hint.related_entity_id,
                state_version=self.state.version,
            )

    def _elapsed_s(self) -> float:
        if self._started_at is None:
            return 0.0
        return time.monotonic() - self._started_at

    def _notify_ui(self) -> None:
        self._on_ui_update(self.state)


def _hint_payload(hint: Hint) -> dict[str, object]:
    payload = asdict(hint)
    payload["type"] = _enum_value(hint.type)
    payload["status"] = _enum_value(hint.status)
    return payload


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)
