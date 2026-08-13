"""Tests for manual topic completion and ladder helpers."""

from __future__ import annotations

from dataclasses import replace

from modules._builtin.meeting_buddy.state import (
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
from modules._builtin.meeting_buddy.topic_ladder import current_topic_id, open_topic_titles


def _topics(*pairs: tuple[str, TopicStatus]) -> tuple[Topic, ...]:
    return tuple(
        Topic(id=tid, title=tid, status=status, source=TopicSource.AGENDA) for tid, status in pairs
    )


def test_manual_mark_topic_done_from_open() -> None:
    state = replace(MeetingState.empty("m1"), topics=_topics(("t1", TopicStatus.OPEN)))
    updated = MeetingStateService().apply(
        state,
        StateProposal(
            proposal_id="manual",
            meeting_session_id="m1",
            type=StateProposalType.MANUAL_MARK_TOPIC_DONE,
            payload={"topic_id": "t1", "matched_at": 1.0},
            source_delta_ids=(),
            confidence=1.0,
            created_at=1.0,
        ),
    )
    assert updated.topics[0].status == TopicStatus.SEQUENTIAL


def test_current_topic_id_prefers_first_open_or_treated() -> None:
    topics = _topics(
        ("t1", TopicStatus.SEQUENTIAL),
        ("t2", TopicStatus.TREATED),
        ("t3", TopicStatus.OPEN),
    )
    assert current_topic_id(topics) == "t2"


def test_open_topic_titles_lists_open_only() -> None:
    topics = _topics(
        ("a", TopicStatus.OPEN),
        ("b", TopicStatus.TREATED),
        ("c", TopicStatus.SEQUENTIAL),
    )
    assert open_topic_titles(topics) == ["a"]
