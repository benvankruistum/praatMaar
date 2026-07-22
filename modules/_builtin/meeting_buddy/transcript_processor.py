"""Transcript delta heuristics and agenda application."""

from __future__ import annotations

from uuid import uuid4

from modules.capabilities.speech_to_text import TranscriptDeltaReceived

from .binding import MeetingSessionBinding
from .config import MeetingBuddyConfig
from .heuristics import HeuristicsEngine
from .observability import EventObserver, log_event
from .prep import parse_agenda
from .state import MeetingState, TopicSource
from .state_service import MeetingStateService, StateProposal, StateProposalType


class TranscriptProcessor:
    """Turn transcript deltas and agenda text into state proposals."""

    def __init__(self) -> None:
        self._heuristics = HeuristicsEngine()
        self._state_service = MeetingStateService()

    def apply_agenda(self, state: MeetingState, agenda_text: str) -> MeetingState:
        topics = parse_agenda(agenda_text)
        if not topics:
            return state
        proposal = StateProposal(
            proposal_id=f"agenda-{uuid4()}",
            meeting_session_id=state.meeting_session_id,
            type=StateProposalType.ADD_TOPICS,
            payload={
                "topics": [{"title": title, "source": TopicSource.AGENDA.value} for title in topics]
            },
            source_delta_ids=(),
            confidence=1.0,
            created_at=0.0,
        )
        return self._state_service.apply(state, proposal)

    def process_delta(
        self,
        event: TranscriptDeltaReceived,
        *,
        binding: MeetingSessionBinding,
        state: MeetingState,
        config: MeetingBuddyConfig,
        elapsed_s: float,
        observer: EventObserver | None,
    ) -> MeetingState:
        if event.delta.session_id != binding.transcription_session_id:
            return state

        updated = state
        for proposal in self._heuristics.proposals_for(
            event.delta,
            updated,
            config,
            elapsed_s,
        ):
            previous_version = updated.version
            updated = self._state_service.apply(updated, proposal)
            log_event(
                observer,
                "state_version",
                meeting_session_id=binding.meeting_session_id,
                previous_version=previous_version,
                state_version=updated.version,
                proposal_type=proposal.type.value,
            )
        return updated
