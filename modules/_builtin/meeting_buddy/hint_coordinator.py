"""Hint evaluation, merge logic, and user-driven hint actions."""

from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from .config import MeetingBuddyConfig
from .hints import HintEngine, HintType
from .observability import EventObserver, log_event
from .state import Hint, HintStatus, MeetingState
from .state_service import MeetingStateService, StateProposal, StateProposalType


class HintCoordinator:
    """Apply hint engine output and overlay dismiss/confirm actions."""

    def __init__(self) -> None:
        self._hints = HintEngine()
        self._state_service = MeetingStateService()

    def update_hints(
        self,
        state: MeetingState,
        config: MeetingBuddyConfig,
        now_s: float,
        *,
        observer: EventObserver | None,
    ) -> MeetingState:
        fresh = self._hints.evaluate(state, config, now_s)
        merged = _merge_visible_hints(state.emitted_hints, fresh, now_s)
        if _hints_equivalent(state.emitted_hints, merged):
            return state
        proposal = StateProposal(
            proposal_id=f"hints-{uuid4()}",
            meeting_session_id=state.meeting_session_id,
            type=StateProposalType.SET_HINTS,
            payload={"hints": [_hint_payload(hint) for hint in merged]},
            source_delta_ids=(),
            confidence=1.0,
            created_at=now_s,
        )
        updated = self._state_service.apply(state, proposal)
        for hint in merged:
            log_event(
                observer,
                "hint_emitted",
                meeting_session_id=state.meeting_session_id,
                hint_type=_enum_value(hint.type),
                related_entity_id=hint.related_entity_id,
                state_version=updated.version,
            )
        return updated

    def dismiss_hint(
        self,
        state: MeetingState,
        hint_id: str,
        *,
        elapsed_s: float,
        observer: EventObserver | None,
    ) -> MeetingState:
        hint = _find_hint(state, hint_id)
        updated = self._apply_hint_status(state, hint, elapsed_s=elapsed_s)
        log_event(
            observer,
            "hint_dismissed",
            meeting_session_id=state.meeting_session_id,
            hint_type=_enum_value(hint.type),
            related_entity_id=hint.related_entity_id,
            state_version=updated.version,
        )
        return updated

    def confirm_hint(
        self,
        state: MeetingState,
        hint_id: str,
        *,
        elapsed_s: float,
        observer: EventObserver | None,
    ) -> MeetingState:
        hint = _find_hint(state, hint_id)
        if (
            _enum_value(hint.type) != HintType.CANDIDATE_ACTION_WITHOUT_OWNER.value
            or hint.related_entity_id is None
        ):
            raise ValueError("Only candidate action hints can be confirmed")
        proposal = StateProposal(
            proposal_id=f"confirm-{uuid4()}",
            meeting_session_id=state.meeting_session_id,
            type=StateProposalType.UPDATE_ACTION,
            payload={"action_id": hint.related_entity_id, "status": "confirmed"},
            source_delta_ids=(),
            confidence=1.0,
            created_at=elapsed_s,
        )
        updated = self._state_service.apply(state, proposal)
        updated = self._apply_hint_status(updated, hint, elapsed_s=elapsed_s)
        log_event(
            observer,
            "hint_dismissed",
            meeting_session_id=state.meeting_session_id,
            hint_type=_enum_value(hint.type),
            related_entity_id=hint.related_entity_id,
            state_version=updated.version,
        )
        log_event(
            observer,
            "action_confirmed",
            meeting_session_id=state.meeting_session_id,
            action_item_id=hint.related_entity_id,
            state_version=updated.version,
        )
        return updated

    def _apply_hint_status(
        self,
        state: MeetingState,
        hint: Hint,
        *,
        elapsed_s: float,
    ) -> MeetingState:
        proposal = StateProposal(
            proposal_id=f"dismiss-{uuid4()}",
            meeting_session_id=state.meeting_session_id,
            type=StateProposalType.UPSERT_HINTS,
            payload={"hints": [{"id": hint.id, "status": "dismissed"}]},
            source_delta_ids=(),
            confidence=1.0,
            created_at=elapsed_s,
        )
        return self._state_service.apply(state, proposal)


def _find_hint(state: MeetingState, hint_id: str) -> Hint:
    try:
        return next(hint for hint in state.emitted_hints if hint.id == hint_id)
    except StopIteration as exc:
        raise ValueError(f"Hint {hint_id!r} not found") from exc


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
