"""Confidence, timing, and cooldown filtering for Meeting Buddy hints."""

from __future__ import annotations

from enum import Enum
from uuid import uuid4

from .config import MeetingBuddyConfig
from .state import ActionItemStatus, Hint, MeetingState, QuestionStatus, TopicStatus


class HintType(str, Enum):
    TOPIC_NOT_DISCUSSED = "topic_not_discussed"
    QUESTION_OPEN = "question_open"
    CANDIDATE_ACTION_WITHOUT_OWNER = "candidate_action_without_owner"


_PRIORITY = {
    HintType.QUESTION_OPEN: 3,
    HintType.CANDIDATE_ACTION_WITHOUT_OWNER: 2,
    HintType.TOPIC_NOT_DISCUSSED: 1,
}


class HintEngine:
    """Evaluate state conservatively: uncertainty produces no hint."""

    def __init__(self) -> None:
        self._last_emitted_at: dict[str, float] = {}

    def evaluate(
        self,
        state: MeetingState,
        config: MeetingBuddyConfig,
        now_s: float,
    ) -> list[Hint]:
        candidates = [
            *self._topic_candidates(state, config, now_s),
            *self._question_candidates(state, config, now_s),
            *self._action_candidates(state, config, now_s),
        ]
        candidates.sort(key=lambda hint: (-hint.priority, -hint.confidence, hint.id))
        selected = candidates[: max(0, min(config.max_visible_hints, 3))]
        for hint in selected:
            self._last_emitted_at[hint.cooldown_key] = now_s
        return selected

    def _topic_candidates(
        self, state: MeetingState, config: MeetingBuddyConfig, now_s: float
    ) -> list[Hint]:
        hint_type = HintType.TOPIC_NOT_DISCUSSED
        if now_s < config.hint_min_wait_s[hint_type.value]:
            return []
        return [
            self._hint(
                hint_type,
                f"Nog niet besproken: {topic.title}",
                topic.id,
                topic.confidence,
                config,
                now_s,
            )
            for topic in state.topics
            if topic.status == TopicStatus.OPEN
            and self._may_emit(hint_type, topic.id, topic.confidence, config, now_s)
        ]

    def _question_candidates(
        self, state: MeetingState, config: MeetingBuddyConfig, now_s: float
    ) -> list[Hint]:
        hint_type = HintType.QUESTION_OPEN
        candidates = []
        for question in state.questions:
            created_at = question.created_at if question.created_at is not None else now_s
            age = now_s - created_at
            if (
                question.status != QuestionStatus.OPEN
                or age < config.question_hint_min_wait_s
                or age > config.question_hint_suppress_after_s
                or not self._may_emit(hint_type, question.id, question.confidence, config, now_s)
            ):
                continue
            candidates.append(
                self._hint(
                    hint_type,
                    f"Open vraag: {question.text}",
                    question.id,
                    question.confidence,
                    config,
                    now_s,
                )
            )
        return candidates

    def _action_candidates(
        self, state: MeetingState, config: MeetingBuddyConfig, now_s: float
    ) -> list[Hint]:
        hint_type = HintType.CANDIDATE_ACTION_WITHOUT_OWNER
        return [
            self._hint(
                hint_type,
                f"Mogelijk actiepunt zonder eigenaar: {action.description}",
                action.id,
                action.confidence,
                config,
                now_s,
            )
            for action in state.action_items
            if action.status == ActionItemStatus.CANDIDATE
            and action.owner.strip().casefold() in {"", "unknown"}
            and action.created_at is not None
            and now_s - action.created_at >= config.hint_min_wait_s[hint_type.value]
            and self._may_emit(hint_type, action.id, action.confidence, config, now_s)
        ]

    def _may_emit(
        self,
        hint_type: HintType,
        entity_id: str,
        confidence: float,
        config: MeetingBuddyConfig,
        now_s: float,
    ) -> bool:
        if confidence < config.min_hint_confidence:
            return False
        cooldown_key = f"{hint_type.value}:{entity_id}"
        last_emitted_at = self._last_emitted_at.get(cooldown_key)
        if last_emitted_at is None:
            return True
        return now_s - last_emitted_at >= _cooldown_s(hint_type, config)

    @staticmethod
    def _hint(
        hint_type: HintType,
        message: str,
        entity_id: str,
        confidence: float,
        config: MeetingBuddyConfig,
        now_s: float,
    ) -> Hint:
        return Hint(
            id=f"hint-{uuid4()}",
            type=hint_type,
            message=message,
            priority=_PRIORITY[hint_type],
            confidence=confidence,
            related_entity_id=entity_id,
            created_at=now_s,
            expires_at=now_s + _cooldown_s(hint_type, config),
            cooldown_key=f"{hint_type.value}:{entity_id}",
        )


def _cooldown_s(hint_type: HintType, config: MeetingBuddyConfig) -> float:
    if hint_type == HintType.QUESTION_OPEN:
        return config.question_hint_cooldown_s
    return config.hint_cooldown[hint_type.value]
