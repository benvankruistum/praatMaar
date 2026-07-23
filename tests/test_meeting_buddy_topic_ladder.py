"""Tests for agendapunt-status ladder and catch-up."""

from dataclasses import replace

import pytest

from modules._builtin.meeting_buddy.state import (
    MeetingPhase,
    MeetingState,
    Topic,
    TopicSource,
    TopicStatus,
)
from modules._builtin.meeting_buddy.state_service import (
    MeetingStateService,
    StateProposal,
    StateProposalType,
)
from modules._builtin.meeting_buddy.topic_ladder import (
    apply_sequential_catch_up,
    is_journal_checked,
    may_mark_treated,
)


def _topics(*pairs: tuple[str, TopicStatus]) -> tuple[Topic, ...]:
    return tuple(
        Topic(id=tid, title=tid, status=status, source=TopicSource.AGENDA) for tid, status in pairs
    )


def test_catch_up_promotes_treated_when_predecessors_sequential() -> None:
    topics = _topics(
        ("t1", TopicStatus.SEQUENTIAL),
        ("t2", TopicStatus.TREATED),
        ("t3", TopicStatus.TREATED),
    )
    result = apply_sequential_catch_up(topics)
    assert result[1].status == TopicStatus.SEQUENTIAL
    assert result[2].status == TopicStatus.SEQUENTIAL


def test_catch_up_waits_for_sequential_predecessors() -> None:
    topics = _topics(
        ("t1", TopicStatus.TREATED),
        ("t2", TopicStatus.TREATED),
    )
    result = apply_sequential_catch_up(topics)
    assert result[0].status == TopicStatus.SEQUENTIAL
    assert result[1].status == TopicStatus.SEQUENTIAL


def test_first_topic_treated_becomes_sequential_immediately() -> None:
    topics = _topics(("t1", TopicStatus.TREATED))
    assert apply_sequential_catch_up(topics)[0].status == TopicStatus.SEQUENTIAL


def test_opening_blocks_later_topics() -> None:
    topics = _topics(("open", TopicStatus.OPEN), ("budget", TopicStatus.OPEN))
    assert may_mark_treated(topics, "open", phase=MeetingPhase.OPENING)
    assert not may_mark_treated(topics, "budget", phase=MeetingPhase.OPENING)
    assert may_mark_treated(topics, "budget", phase=MeetingPhase.BODY)


def test_mark_treated_no_catch_up() -> None:
    service = MeetingStateService()
    state = replace(
        MeetingState.empty("m1"),
        topics=_topics(("t1", TopicStatus.OPEN), ("t2", TopicStatus.OPEN)),
    )
    state = service.apply(
        state,
        StateProposal(
            proposal_id="p1",
            meeting_session_id="m1",
            type=StateProposalType.MARK_TOPIC_TREATED,
            payload={"topic_id": "t1", "matched_at": 1.0},
            source_delta_ids=(),
            confidence=0.9,
        ),
    )
    assert state.topics[0].status == TopicStatus.TREATED
    assert state.topics[1].status == TopicStatus.OPEN

    state = service.apply(
        state,
        StateProposal(
            proposal_id="p2",
            meeting_session_id="m1",
            type=StateProposalType.APPLY_TOPIC_CATCH_UP,
            payload={},
            source_delta_ids=(),
            confidence=1.0,
        ),
    )
    assert state.topics[0].status == TopicStatus.SEQUENTIAL


def test_confirm_requires_sequential() -> None:
    service = MeetingStateService()
    state = replace(
        MeetingState.empty("m1"),
        topics=_topics(("t1", TopicStatus.TREATED)),
    )
    state = service.apply(
        state,
        StateProposal(
            proposal_id="p1",
            meeting_session_id="m1",
            type=StateProposalType.SET_TOPIC_STATUS,
            payload={"topic_id": "t1", "status": "confirmed"},
            source_delta_ids=(),
            confidence=1.0,
        ),
    )
    assert state.topics[0].status == TopicStatus.TREATED

    state = replace(state, topics=_topics(("t1", TopicStatus.SEQUENTIAL)))
    state = service.apply(
        state,
        StateProposal(
            proposal_id="p2",
            meeting_session_id="m1",
            type=StateProposalType.SET_TOPIC_STATUS,
            payload={"topic_id": "t1", "status": "confirmed"},
            source_delta_ids=(),
            confidence=1.0,
        ),
    )
    assert state.topics[0].status == TopicStatus.CONFIRMED


def test_opening_phase_rejects_later_treated() -> None:
    service = MeetingStateService()
    state = replace(
        MeetingState.empty("m1"),
        meeting_phase=MeetingPhase.OPENING,
        topics=_topics(("t1", TopicStatus.OPEN), ("t2", TopicStatus.OPEN)),
    )
    state = service.apply(
        state,
        StateProposal(
            proposal_id="p1",
            meeting_session_id="m1",
            type=StateProposalType.MARK_TOPIC_TREATED,
            payload={"topic_id": "t2"},
            source_delta_ids=(),
            confidence=1.0,
        ),
    )
    assert state.topics[1].status == TopicStatus.OPEN


@pytest.mark.parametrize(
    ("status", "checked"),
    [
        (TopicStatus.OPEN, False),
        (TopicStatus.TREATED, False),
        (TopicStatus.SEQUENTIAL, True),
        (TopicStatus.CONFIRMED, True),
    ],
)
def test_journal_checked(status: TopicStatus, checked: bool) -> None:
    assert is_journal_checked(status) is checked
