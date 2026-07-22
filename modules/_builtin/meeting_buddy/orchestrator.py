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
    TranscriptionStatus,
    TranscriptionStatusChanged,
)

from .config import load_meeting_buddy_config
from .heuristics import HeuristicsEngine
from .hints import HintEngine
from .observability import EventObserver, log_event
from .prep import parse_agenda
from .state import Hint, HintStatus, MeetingState, TopicSource
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
        self._capture_status = CaptureStatus.IDLE
        self._transcription_status = TranscriptionStatus.IDLE
        self._last_ui_notify_at = 0.0

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

    @property
    def capture_status(self) -> CaptureStatus:
        return self._capture_status

    @property
    def transcription_status(self) -> TranscriptionStatus:
        return self._transcription_status

    def elapsed_seconds(self) -> float:
        return self._elapsed_s()

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

        capture_session = capture.start_session(self._capture_config())
        try:
            transcription_session = stt.start_session(
                capture_session_id=capture_session.session_id,
                capture=capture,
                config={
                    "max_whisper_queue_duration_s": (self._config.max_whisper_queue_duration_s),
                },
            )
        except Exception as exc:
            try:
                capture.stop_session(capture_session.session_id)
            except Exception:
                pass
            raise RuntimeError(f"Meeting Buddy starten mislukt: {exc}") from exc

        meeting_session_id = str(uuid4())
        self._binding = MeetingSessionBinding(
            meeting_session_id=meeting_session_id,
            capture_session_id=capture_session.session_id,
            transcription_session_id=transcription_session.session_id,
        )
        self._capture = capture
        self._stt = stt
        self._capture_status = capture.get_status(capture_session.session_id)
        self._transcription_status = stt.get_status(transcription_session.session_id)
        self._started_at = time.monotonic()
        self._state = MeetingState.empty(meeting_session_id)

        try:
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
            self._notify_ui(force=True)
        except Exception as exc:
            self._cleanup_sessions(self._binding)
            self._clear_running_state()
            raise RuntimeError(f"Meeting Buddy starten mislukt: {exc}") from exc

    def reconnect_capture(self) -> None:
        """Replace failed capture and STT sessions while keeping the meeting open."""

        binding = self._binding
        if binding is None:
            raise RuntimeError("Meeting Buddy is niet gestart")

        log_event(
            self._observer,
            "capture_restart",
            meeting_session_id=binding.meeting_session_id,
            capture_session_id=binding.capture_session_id,
        )
        self._capture_status = CaptureStatus.RECONNECTING
        self._notify_ui(force=True)
        self._cleanup_sessions(binding)

        capture_session = None
        try:
            capture_session = self._capture.start_session(self._capture_config())
            transcription_session = self._stt.start_session(
                capture_session_id=capture_session.session_id,
                capture=self._capture,
                config={
                    "max_whisper_queue_duration_s": (self._config.max_whisper_queue_duration_s),
                },
            )
            self._binding = MeetingSessionBinding(
                meeting_session_id=binding.meeting_session_id,
                capture_session_id=capture_session.session_id,
                transcription_session_id=transcription_session.session_id,
            )
            self._capture_status = self._capture.get_status(capture_session.session_id)
            self._transcription_status = self._stt.get_status(transcription_session.session_id)
            self._capture.subscribe(capture_session.session_id, self.on_capture_status)
            self._stt.subscribe(transcription_session.session_id, self.on_stt_event)
        except Exception as exc:
            if capture_session is not None:
                try:
                    self._capture.stop_session(capture_session.session_id)
                except Exception:
                    pass
            self._capture_status = CaptureStatus.ERROR
            self._transcription_status = TranscriptionStatus.ERROR
            self._notify_ui(force=True)
            raise RuntimeError(f"Microfoon herverbinden mislukt: {exc}") from exc

        self._notify_ui(force=True)

    def stop(self) -> None:
        binding = self._binding
        if binding is None:
            return

        try:
            self._cleanup_sessions(binding)
            try:
                log_event(
                    self._observer,
                    "meeting_stopped",
                    meeting_session_id=binding.meeting_session_id,
                    duration_ms=int(self._elapsed_s() * 1000),
                )
            except Exception:
                pass
            try:
                self._notify_ui(force=True)
            except Exception:
                pass
        finally:
            self._clear_running_state()

    def _cleanup_sessions(self, binding: MeetingSessionBinding) -> None:
        try:
            self._stt.unsubscribe(binding.transcription_session_id, self.on_stt_event)
        except Exception:
            pass
        try:
            self._capture.unsubscribe(binding.capture_session_id, self.on_capture_status)
        except Exception:
            pass
        try:
            self._stt.stop_session(binding.transcription_session_id)
        except Exception:
            pass
        try:
            self._capture.stop_session(binding.capture_session_id)
        except Exception:
            pass

    def _clear_running_state(self) -> None:
        self._binding = None
        self._capture = None
        self._stt = None
        self._started_at = None
        self._state = None
        self._capture_status = CaptureStatus.IDLE
        self._transcription_status = TranscriptionStatus.IDLE

    def on_stt_event(self, event: object) -> None:
        binding = self._binding
        if binding is None:
            return
        if isinstance(event, TranscriptionStatusChanged):
            if event.session_id != binding.transcription_session_id:
                return
            self._transcription_status = event.status
            self._notify_ui(force=True)
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
            self._transcription_status = TranscriptionStatus.DELAYED
            self._notify_ui(force=True)
            return
        if not isinstance(event, TranscriptDeltaReceived):
            return
        if event.delta.session_id != binding.transcription_session_id:
            return

        now_s = self._elapsed_s()
        version_before = self.state.version
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

        hints_before = self.state.emitted_hints
        self._update_hints(now_s)
        state_changed = self.state.version != version_before
        hints_changed = self.state.emitted_hints != hints_before
        self._notify_ui(force=state_changed or hints_changed)

    def on_capture_status(self, event: object) -> None:
        binding = self._binding
        if binding is None:
            return
        if isinstance(event, CaptureStatusChanged):
            if event.session_id != binding.capture_session_id:
                return
            self._capture_status = event.status
            self._notify_ui(force=True)
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
            self._notify_ui()

    def dismiss_hint(self, hint_id: str) -> None:
        hint = self._find_hint(hint_id)
        self._dismiss_hint(hint)
        log_event(
            self._observer,
            "hint_dismissed",
            meeting_session_id=self.state.meeting_session_id,
            hint_type=_enum_value(hint.type),
            related_entity_id=hint.related_entity_id,
            state_version=self.state.version,
        )
        self._notify_ui(force=True)

    def confirm_hint(self, hint_id: str) -> None:
        hint = self._find_hint(hint_id)
        if (
            _enum_value(hint.type) != "candidate_action_without_owner"
            or hint.related_entity_id is None
        ):
            raise ValueError("Only candidate action hints can be confirmed")
        proposal = StateProposal(
            proposal_id=f"confirm-{uuid4()}",
            meeting_session_id=self.state.meeting_session_id,
            type="update_action",
            payload={"action_id": hint.related_entity_id, "status": "confirmed"},
            source_delta_ids=(),
            confidence=1.0,
            created_at=self._elapsed_s(),
        )
        self._state = self._state_service.apply(self.state, proposal)
        self._dismiss_hint(hint)
        log_event(
            self._observer,
            "hint_dismissed",
            meeting_session_id=self.state.meeting_session_id,
            hint_type=_enum_value(hint.type),
            related_entity_id=hint.related_entity_id,
            state_version=self.state.version,
        )
        log_event(
            self._observer,
            "action_confirmed",
            meeting_session_id=self.state.meeting_session_id,
            action_item_id=hint.related_entity_id,
            state_version=self.state.version,
        )
        self._notify_ui(force=True)

    def _find_hint(self, hint_id: str) -> Hint:
        try:
            return next(hint for hint in self.state.emitted_hints if hint.id == hint_id)
        except StopIteration as exc:
            raise ValueError(f"Hint {hint_id!r} not found") from exc

    def _dismiss_hint(self, hint: Hint) -> None:
        proposal = StateProposal(
            proposal_id=f"dismiss-{uuid4()}",
            meeting_session_id=self.state.meeting_session_id,
            type="upsert_hints",
            payload={"hints": [{"id": hint.id, "status": "dismissed"}]},
            source_delta_ids=(),
            confidence=1.0,
            created_at=self._elapsed_s(),
        )
        self._state = self._state_service.apply(self.state, proposal)

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
        fresh = self._hints.evaluate(self.state, self._config, now_s)
        merged = _merge_visible_hints(self.state.emitted_hints, fresh, now_s)
        if _hints_equivalent(self.state.emitted_hints, merged):
            return
        proposal = StateProposal(
            proposal_id=f"hints-{uuid4()}",
            meeting_session_id=self.state.meeting_session_id,
            type="set_hints",
            payload={"hints": [_hint_payload(hint) for hint in merged]},
            source_delta_ids=(),
            confidence=1.0,
            created_at=now_s,
        )
        self._state = self._state_service.apply(self.state, proposal)
        for hint in merged:
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

    def _capture_config(self) -> dict[str, object]:
        """Build audio-capture options: app mic + Meeting Buddy loopback settings."""

        from config import load_config

        app_settings = load_config()
        microphone_device = app_settings.get("microphone_device")
        device = microphone_device if isinstance(microphone_device, int) else None
        return {
            "max_audio_buffer_duration_s": self._config.max_audio_buffer_duration_s,
            "device": device,
            "enable_loopback": self._config.enable_loopback,
            "loopback_device": self._config.loopback_device,
        }

    def _notify_ui(self, *, force: bool = False) -> None:
        if self._state is None:
            return
        if not force:
            now = time.monotonic()
            if now - self._last_ui_notify_at < 0.5:
                return
            self._last_ui_notify_at = now
        else:
            self._last_ui_notify_at = time.monotonic()
        self._on_ui_update(self.state)


def _merge_visible_hints(
    current: tuple[Hint, ...],
    fresh: list[Hint],
    now_s: float,
) -> list[Hint]:
    """Keep active hints during cooldown gaps; refresh by cooldown_key."""

    active = {
        hint.cooldown_key: hint
        for hint in current
        if hint.status == HintStatus.ACTIVE
        and hint.cooldown_key
        and (hint.expires_at is None or hint.expires_at > now_s)
    }
    for hint in fresh:
        active[hint.cooldown_key] = hint
    merged = list(active.values())
    merged.sort(key=lambda hint: (-hint.priority, -hint.confidence, hint.id))
    return merged[:3]


def _hints_equivalent(current: tuple[Hint, ...], merged: list[Hint]) -> bool:
    if len(current) != len(merged):
        return False
    for left, right in zip(current, merged, strict=True):
        if (
            left.id != right.id
            or left.message != right.message
            or left.status != right.status
            or left.priority != right.priority
        ):
            return False
    return True


def _hint_payload(hint: Hint) -> dict[str, object]:
    payload = asdict(hint)
    payload["type"] = _enum_value(hint.type)
    payload["status"] = _enum_value(hint.status)
    return payload


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)
