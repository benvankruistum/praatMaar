"""Immutable entities that make up a Meeting Buddy state snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TopicStatus(str, Enum):
    OPEN = "open"
    DISCUSSED = "discussed"


class TopicSource(str, Enum):
    AGENDA = "agenda"
    MANUAL = "manual"


class QuestionStatus(str, Enum):
    OPEN = "open"
    POSSIBLY_ANSWERED = "possibly_answered"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


class ActionItemStatus(str, Enum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class HintStatus(str, Enum):
    ACTIVE = "active"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    status: TopicStatus = TopicStatus.OPEN
    source: TopicSource = TopicSource.MANUAL
    confidence: float = 1.0
    last_matched_at: float | None = None


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    status: QuestionStatus = QuestionStatus.OPEN
    source_delta_id: str | None = None
    created_at: float | None = None
    resolved_at: float | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class ActionItem:
    id: str
    description: str
    owner: str = "UNKNOWN"
    status: ActionItemStatus = ActionItemStatus.CANDIDATE
    source_delta_id: str | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class Hint:
    id: str
    type: str
    message: str
    priority: int
    confidence: float
    related_entity_id: str | None = None
    created_at: float | None = None
    expires_at: float | None = None
    cooldown_key: str = ""
    status: HintStatus = HintStatus.ACTIVE


@dataclass(frozen=True)
class MeetingState:
    meeting_session_id: str
    version: int
    topics: tuple[Topic, ...]
    goals: tuple[str, ...]
    questions: tuple[Question, ...]
    action_items: tuple[ActionItem, ...]
    emitted_hints: tuple[Hint, ...]

    @classmethod
    def empty(cls, meeting_session_id: str) -> MeetingState:
        """Create the initial immutable snapshot for a meeting."""

        return cls(
            meeting_session_id=meeting_session_id,
            version=0,
            topics=(),
            goals=(),
            questions=(),
            action_items=(),
            emitted_hints=(),
        )
