"""Agendapunt-status ladder helpers (catch-up, ordering)."""

from __future__ import annotations

from dataclasses import replace

from .state import MeetingPhase, Topic, TopicStatus

_STATUS_RANK = {
    TopicStatus.OPEN: 0,
    TopicStatus.TREATED: 1,
    TopicStatus.SEQUENTIAL: 2,
    TopicStatus.CONFIRMED: 3,
}


def status_rank(status: TopicStatus) -> int:
    return _STATUS_RANK[status]


def is_at_least_sequential(status: TopicStatus) -> bool:
    return status_rank(status) >= status_rank(TopicStatus.SEQUENTIAL)


def is_journal_checked(status: TopicStatus) -> bool:
    """Agenda checkbox in transcript journal: sequential or confirmed."""

    return is_at_least_sequential(status)


def apply_sequential_catch_up(topics: tuple[Topic, ...]) -> tuple[Topic, ...]:
    """Promote treated → sequential when all predecessors are ≥ sequential."""

    result = list(topics)
    changed = True
    while changed:
        changed = False
        for index, topic in enumerate(result):
            if topic.status != TopicStatus.TREATED:
                continue
            predecessors = result[:index]
            if all(is_at_least_sequential(prev.status) for prev in predecessors):
                result[index] = replace(topic, status=TopicStatus.SEQUENTIAL)
                changed = True
    return tuple(result)


def may_mark_treated(
    topics: tuple[Topic, ...],
    topic_id: str,
    *,
    phase: MeetingPhase,
) -> bool:
    """In opening phase only the first topic may become treated."""

    if phase != MeetingPhase.OPENING:
        return True
    if not topics:
        return False
    return topics[0].id == topic_id
