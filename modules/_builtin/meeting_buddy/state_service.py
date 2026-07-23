"""Single mutation boundary for immutable Meeting Buddy state snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from .state import (
    ActionItem,
    ActionItemStatus,
    Hint,
    HintStatus,
    MeetingPhase,
    MeetingState,
    Question,
    QuestionStatus,
    Topic,
    TopicSource,
    TopicStatus,
)
from .topic_ladder import apply_sequential_catch_up, may_mark_treated, status_rank


class StateProposalType(str, Enum):
    ADD_TOPICS = "add_topics"
    MARK_TOPIC_TREATED = "mark_topic_treated"
    SET_TOPIC_STATUS = "set_topic_status"
    APPLY_TOPIC_CATCH_UP = "apply_topic_catch_up"
    SET_MEETING_PHASE = "set_meeting_phase"
    ADD_QUESTION = "add_question"
    UPDATE_QUESTION = "update_question"
    ADD_ACTION = "add_action"
    UPDATE_ACTION = "update_action"
    UPSERT_HINTS = "upsert_hints"
    SET_HINTS = "set_hints"
    # Compat alias used by older tests / call sites
    MARK_TOPIC_DISCUSSED = "mark_topic_discussed"


@dataclass(frozen=True)
class StateProposal:
    proposal_id: str
    meeting_session_id: str
    type: StateProposalType
    payload: Mapping[str, Any]
    source_delta_ids: tuple[str, ...] | list[str]
    confidence: float
    created_at: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_delta_ids", tuple(self.source_delta_ids))


class MeetingStateService:
    """Apply proposals and return a new, monotonically versioned snapshot."""

    def apply(self, state: MeetingState, proposal: StateProposal) -> MeetingState:
        if proposal.meeting_session_id != state.meeting_session_id:
            raise ValueError("Proposal and state session IDs do not match")

        handlers = {
            StateProposalType.ADD_TOPICS: self._add_topics,
            StateProposalType.MARK_TOPIC_TREATED: self._mark_topic_treated,
            StateProposalType.MARK_TOPIC_DISCUSSED: self._mark_topic_treated,
            StateProposalType.SET_TOPIC_STATUS: self._set_topic_status,
            StateProposalType.APPLY_TOPIC_CATCH_UP: self._apply_topic_catch_up,
            StateProposalType.SET_MEETING_PHASE: self._set_meeting_phase,
            StateProposalType.ADD_QUESTION: self._add_question,
            StateProposalType.UPDATE_QUESTION: self._update_question,
            StateProposalType.ADD_ACTION: self._add_action,
            StateProposalType.UPDATE_ACTION: self._update_action,
            StateProposalType.UPSERT_HINTS: self._upsert_hints,
            StateProposalType.SET_HINTS: self._set_hints,
        }
        try:
            handler = handlers[proposal.type]
        except KeyError as exc:
            raise ValueError(f"Unsupported proposal type: {proposal.type}") from exc
        updated = handler(state, proposal)
        return replace(updated, version=state.version + 1)

    @staticmethod
    def _add_topics(state: MeetingState, proposal: StateProposal) -> MeetingState:
        payload = proposal.payload
        raw_topics = payload.get("topics")
        if raw_topics is None:
            raw_topics = [{"title": title} for title in payload.get("titles", ())]

        topics = list(state.topics)
        for index, raw_topic in enumerate(raw_topics):
            values = dict(raw_topic)
            topics.append(
                Topic(
                    id=str(values.get("id", f"{proposal.proposal_id}:topic:{index}")),
                    title=str(values["title"]),
                    status=TopicStatus(values.get("status", TopicStatus.OPEN)),
                    source=TopicSource(
                        values.get("source", payload.get("source", TopicSource.MANUAL))
                    ),
                    confidence=float(values.get("confidence", proposal.confidence)),
                    last_matched_at=values.get("last_matched_at"),
                )
            )
        return replace(state, topics=tuple(topics))

    @staticmethod
    def _mark_topic_treated(state: MeetingState, proposal: StateProposal) -> MeetingState:
        """Heuristics / LLM: open → treated only (no catch-up)."""

        topic_id = str(proposal.payload["topic_id"])
        if not may_mark_treated(state.topics, topic_id, phase=state.meeting_phase):
            return state
        topic = _find_by_id(state.topics, topic_id, "Topic")
        if topic.status != TopicStatus.OPEN:
            return state
        updated = replace(
            topic,
            status=TopicStatus.TREATED,
            last_matched_at=proposal.payload.get("matched_at", proposal.created_at),
            confidence=float(proposal.payload.get("confidence", proposal.confidence)),
        )
        return replace(state, topics=_replace_by_id(state.topics, updated))

    @staticmethod
    def _set_topic_status(state: MeetingState, proposal: StateProposal) -> MeetingState:
        topic_id = str(proposal.payload["topic_id"])
        target = TopicStatus(proposal.payload["status"])
        topic = _find_by_id(state.topics, topic_id, "Topic")

        if target == TopicStatus.TREATED:
            if not may_mark_treated(state.topics, topic_id, phase=state.meeting_phase):
                return state
            if topic.status != TopicStatus.OPEN:
                return state
        elif target == TopicStatus.CONFIRMED:
            if topic.status != TopicStatus.SEQUENTIAL:
                return state
        elif target == TopicStatus.SEQUENTIAL:
            # Prefer catch-up proposal; allow explicit set only from treated
            if topic.status != TopicStatus.TREATED:
                return state
        elif target == TopicStatus.OPEN:
            return state
        else:
            return state

        if status_rank(target) < status_rank(topic.status):
            return state

        updated = replace(
            topic,
            status=target,
            last_matched_at=proposal.payload.get("matched_at", proposal.created_at),
            confidence=float(proposal.payload.get("confidence", proposal.confidence)),
        )
        return replace(state, topics=_replace_by_id(state.topics, updated))

    @staticmethod
    def _apply_topic_catch_up(state: MeetingState, proposal: StateProposal) -> MeetingState:
        del proposal  # unused; catch-up is deterministic from topics
        return replace(state, topics=apply_sequential_catch_up(state.topics))

    @staticmethod
    def _set_meeting_phase(state: MeetingState, proposal: StateProposal) -> MeetingState:
        phase = MeetingPhase(proposal.payload["phase"])
        return replace(state, meeting_phase=phase)

    @staticmethod
    def _add_question(state: MeetingState, proposal: StateProposal) -> MeetingState:
        payload = proposal.payload
        question = Question(
            id=str(payload.get("id", f"{proposal.proposal_id}:question")),
            text=str(payload["text"]),
            status=QuestionStatus(payload.get("status", QuestionStatus.OPEN)),
            source_delta_id=payload.get("source_delta_id", _first_source_delta(proposal)),
            created_at=payload.get("created_at", proposal.created_at),
            resolved_at=payload.get("resolved_at"),
            confidence=float(payload.get("confidence", proposal.confidence)),
        )
        return replace(state, questions=(*state.questions, question))

    @staticmethod
    def _update_question(state: MeetingState, proposal: StateProposal) -> MeetingState:
        payload = proposal.payload
        question_id = str(payload["question_id"])
        question = _find_by_id(state.questions, question_id, "Question")
        changes = _present_values(payload, "text", "source_delta_id", "resolved_at", "confidence")
        if "status" in payload:
            changes["status"] = QuestionStatus(payload["status"])
        updated = replace(question, **changes)
        return replace(state, questions=_replace_by_id(state.questions, updated))

    @staticmethod
    def _add_action(state: MeetingState, proposal: StateProposal) -> MeetingState:
        payload = proposal.payload
        action = ActionItem(
            id=str(payload.get("id", f"{proposal.proposal_id}:action")),
            description=str(payload["description"]),
            owner=str(payload.get("owner", "UNKNOWN")),
            status=ActionItemStatus(payload.get("status", ActionItemStatus.CANDIDATE)),
            source_delta_id=payload.get("source_delta_id", _first_source_delta(proposal)),
            created_at=payload.get("created_at", proposal.created_at),
            confidence=float(payload.get("confidence", proposal.confidence)),
        )
        return replace(state, action_items=(*state.action_items, action))

    @staticmethod
    def _update_action(state: MeetingState, proposal: StateProposal) -> MeetingState:
        payload = proposal.payload
        action_id = str(payload["action_id"])
        action = _find_by_id(state.action_items, action_id, "Action item")
        changes = _present_values(
            payload,
            "description",
            "owner",
            "source_delta_id",
            "created_at",
            "confidence",
        )
        if "status" in payload:
            changes["status"] = ActionItemStatus(payload["status"])
        updated = replace(action, **changes)
        return replace(state, action_items=_replace_by_id(state.action_items, updated))

    @staticmethod
    def _upsert_hints(state: MeetingState, proposal: StateProposal) -> MeetingState:
        hints = list(state.emitted_hints)
        for raw_hint in proposal.payload.get("hints", ()):
            values = dict(raw_hint)
            hint_id = str(values["id"])
            existing = next((hint for hint in hints if hint.id == hint_id), None)
            if existing is None:
                hint = _new_hint(values, proposal)
                hints.append(hint)
            else:
                changes = _present_values(
                    values,
                    "type",
                    "message",
                    "priority",
                    "confidence",
                    "related_entity_id",
                    "created_at",
                    "expires_at",
                    "cooldown_key",
                )
                if "status" in values:
                    changes["status"] = HintStatus(values["status"])
                hints[hints.index(existing)] = replace(existing, **changes)
        return replace(state, emitted_hints=tuple(hints))

    @staticmethod
    def _set_hints(state: MeetingState, proposal: StateProposal) -> MeetingState:
        hints = tuple(_new_hint(dict(raw), proposal) for raw in proposal.payload.get("hints", ()))
        return replace(state, emitted_hints=hints)


def _new_hint(values: Mapping[str, Any], proposal: StateProposal) -> Hint:
    return Hint(
        id=str(values["id"]),
        type=str(values["type"]),
        message=str(values["message"]),
        priority=int(values.get("priority", 0)),
        confidence=float(values.get("confidence", proposal.confidence)),
        related_entity_id=values.get("related_entity_id"),
        created_at=values.get("created_at", proposal.created_at),
        expires_at=values.get("expires_at"),
        cooldown_key=str(values.get("cooldown_key", "")),
        status=HintStatus(values.get("status", HintStatus.ACTIVE)),
    )


def _first_source_delta(proposal: StateProposal) -> str | None:
    return proposal.source_delta_ids[0] if proposal.source_delta_ids else None


def _find_by_id(entities: tuple[Any, ...], entity_id: str, label: str) -> Any:
    try:
        return next(entity for entity in entities if entity.id == entity_id)
    except StopIteration as exc:
        raise ValueError(f"{label} {entity_id!r} not found") from exc


def _replace_by_id(entities: tuple[Any, ...], updated: Any) -> tuple[Any, ...]:
    return tuple(updated if entity.id == updated.id else entity for entity in entities)


def _present_values(payload: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload}
