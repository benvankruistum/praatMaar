"""Chunked agenda-review via ``ai.semantic_analysis`` (fase, topics, vragen)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock, Thread
from uuid import uuid4

from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.semantic_analysis import (
    CAPABILITY_ID,
    CONTRACT_VERSION,
    KIND_AGENDA_REVIEW,
    AnalysisRequest,
)
from modules.capabilities.speaker_detection import SpeakerRole

from .hint_text import clean_question_text, question_is_substantial
from .state import MeetingPhase, MeetingState, QuestionStatus
from .state_service import MeetingStateService, StateProposal, StateProposalType

log = logging.getLogger(__name__)

OnReview = Callable[[MeetingState], None]


@dataclass
class AgendaReviewSettings:
    enabled: bool = True
    interval_s: float = 45.0
    min_new_chars: int = 120
    language: str = "nl"


@dataclass(frozen=True)
class LabeledFinal:
    text: str
    speaker_role: SpeakerRole = SpeakerRole.UNKNOWN


class AgendaReviewCoordinator:
    """Schedules agenda_review LLM calls; applies phase/topics/questions to state."""

    def __init__(
        self,
        *,
        capabilities: CapabilityRegistry,
        settings: AgendaReviewSettings,
        on_review: OnReview | None = None,
    ) -> None:
        self._capabilities = capabilities
        self._settings = settings
        self._on_review = on_review
        self._lock = Lock()
        self._buffer: list[LabeledFinal] = []
        self._chars_since = 0
        self._last_run_at = time.monotonic()
        self._busy = False
        self._llm_ready = False
        self._state_service = MeetingStateService()

    @property
    def llm_ready(self) -> bool:
        with self._lock:
            return self._llm_ready

    def update_settings(self, settings: AgendaReviewSettings) -> None:
        with self._lock:
            self._settings = settings

    def reset(self) -> None:
        with self._lock:
            self._buffer = []
            self._chars_since = 0
            self._last_run_at = time.monotonic()
            self._busy = False
            self._llm_ready = False

    def provider_is_ready(self) -> bool:
        provider = self._capabilities.get(
            CAPABILITY_ID,
            minimum_contract_version=CONTRACT_VERSION,
        )
        if provider is None:
            return False
        if hasattr(provider, "is_ready") and not provider.is_ready():
            return False
        return True

    def on_final(
        self,
        labeled: LabeledFinal,
        *,
        state: MeetingState,
        now: float | None = None,
    ) -> None:
        chunk = labeled.text.strip()
        if not chunk:
            return
        with self._lock:
            if not self._settings.enabled:
                return
            self._buffer.append(labeled)
            self._chars_since += len(chunk)
            should = self._should_run_unlocked(now=now if now is not None else time.monotonic())
            if not should:
                return
            self._busy = True
            snapshot = list(self._buffer)
            language = self._settings.language
            state_snapshot = state
        Thread(
            target=self._run_analyze,
            args=(snapshot, state_snapshot, language),
            name="meeting-buddy-agenda-review",
            daemon=True,
        ).start()

    def _should_run_unlocked(self, *, now: float) -> bool:
        if self._busy:
            return False
        if self._chars_since < self._settings.min_new_chars:
            return False
        if (now - self._last_run_at) < self._settings.interval_s:
            return False
        provider = self._capabilities.get(
            CAPABILITY_ID,
            minimum_contract_version=CONTRACT_VERSION,
        )
        return provider is not None

    def _run_analyze(
        self,
        labeled_parts: list[LabeledFinal],
        state: MeetingState,
        language: str,
    ) -> None:
        provider = self._capabilities.get(
            CAPABILITY_ID,
            minimum_contract_version=CONTRACT_VERSION,
        )
        try:
            if provider is None:
                log.warning("Agenda review: geen ai.semantic_analysis capability")
                return
            if hasattr(provider, "is_ready") and not provider.is_ready():
                log.warning("Agenda review: Local LLM niet klaar")
                with self._lock:
                    self._last_run_at = time.monotonic()
                    self._llm_ready = False
                return
            with self._lock:
                self._llm_ready = True
            transcript = _format_labeled_transcript(labeled_parts)
            topics_ctx = [
                {
                    "topic_id": topic.id,
                    "title": topic.title,
                    "status": topic.status.value,
                }
                for topic in state.topics
            ]
            result = provider.analyze(
                AnalysisRequest(
                    kind=KIND_AGENDA_REVIEW,
                    transcript=transcript,
                    language=language,
                    context={
                        "phase": state.meeting_phase.value,
                        "topics": topics_ctx,
                    },
                )
            )
            data = result.data if isinstance(result.data, dict) else {}
            roles = [part.speaker_role for part in labeled_parts]
            questions = [str(q) for q in (data.get("questions") or [])]
            data = {
                **data,
                "questions": filter_questions_for_speaker_roles(questions, source_roles=roles),
            }
            updated = self.apply_review_result(state, data, now_s=time.time())
            with self._lock:
                self._chars_since = 0
                self._last_run_at = time.monotonic()
            if self._on_review is not None:
                self._on_review(updated)
        except Exception:
            log.exception("Agenda review analyse mislukt")
        finally:
            with self._lock:
                self._busy = False

    def apply_review_result(
        self,
        state: MeetingState,
        data: dict[str, object],
        *,
        now_s: float,
    ) -> MeetingState:
        """Pure-ish apply path (also used from tests)."""

        updated = state
        phase_raw = str(data.get("phase", state.meeting_phase.value)).lower()
        try:
            phase = MeetingPhase(phase_raw)
        except ValueError:
            phase = state.meeting_phase
        if phase != updated.meeting_phase:
            updated = self._state_service.apply(
                updated,
                StateProposal(
                    proposal_id=f"phase-{uuid4()}",
                    meeting_session_id=updated.meeting_session_id,
                    type=StateProposalType.SET_MEETING_PHASE,
                    payload={"phase": phase.value},
                    source_delta_ids=(),
                    confidence=1.0,
                    created_at=now_s,
                ),
            )

        for item in data.get("topic_updates") or ():
            if not isinstance(item, dict):
                continue
            topic_id = str(item.get("topic_id", ""))
            status = str(item.get("status", "")).lower()
            if not topic_id or status not in {"treated", "confirmed"}:
                continue
            updated = self._state_service.apply(
                updated,
                StateProposal(
                    proposal_id=f"topic-{uuid4()}",
                    meeting_session_id=updated.meeting_session_id,
                    type=StateProposalType.SET_TOPIC_STATUS,
                    payload={
                        "topic_id": topic_id,
                        "status": status,
                        "matched_at": now_s,
                    },
                    source_delta_ids=(),
                    confidence=0.85,
                    created_at=now_s,
                ),
            )

        updated = self._state_service.apply(
            updated,
            StateProposal(
                proposal_id=f"catchup-{uuid4()}",
                meeting_session_id=updated.meeting_session_id,
                type=StateProposalType.APPLY_TOPIC_CATCH_UP,
                payload={},
                source_delta_ids=(),
                confidence=1.0,
                created_at=now_s,
            ),
        )

        for raw_q in data.get("questions") or ():
            text = clean_question_text(str(raw_q))
            if not question_is_substantial(text):
                continue
            if _has_similar_open_question(updated, text):
                continue
            updated = self._state_service.apply(
                updated,
                StateProposal(
                    proposal_id=f"q-{uuid4()}",
                    meeting_session_id=updated.meeting_session_id,
                    type=StateProposalType.ADD_QUESTION,
                    payload={"text": text, "created_at": now_s},
                    source_delta_ids=(),
                    confidence=0.8,
                    created_at=now_s,
                ),
            )
        return updated


def _format_labeled_transcript(parts: list[LabeledFinal]) -> str:
    lines = []
    for part in parts:
        role = part.speaker_role.value if isinstance(part.speaker_role, SpeakerRole) else "unknown"
        lines.append(f"[{role}] {part.text.strip()}")
    return "\n".join(lines)


def _has_similar_open_question(state: MeetingState, text: str) -> bool:
    needle = text.casefold().strip()
    return any(
        q.status == QuestionStatus.OPEN and q.text.casefold().strip() == needle
        for q in state.questions
    )


def filter_questions_for_speaker_roles(
    questions: list[str],
    *,
    source_roles: list[SpeakerRole],
) -> list[str]:
    """Drop questions if the only recent speakers were ME (defensive prefilter)."""

    if not source_roles:
        return questions
    if all(role == SpeakerRole.ME for role in source_roles):
        return []
    return questions


def should_accept_question_role(role: SpeakerRole) -> bool:
    """ME excluded; OTHER and UNKNOWN allowed."""

    return role != SpeakerRole.ME
