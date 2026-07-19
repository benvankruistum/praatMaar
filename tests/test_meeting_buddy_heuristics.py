from dataclasses import replace

from modules._builtin.meeting_buddy.config import MeetingBuddyConfig
from modules._builtin.meeting_buddy.heuristics import HeuristicsEngine
from modules._builtin.meeting_buddy.state import (
    MeetingState,
    Question,
    QuestionStatus,
    Topic,
    TopicSource,
    TopicStatus,
)
from modules.capabilities.speech_to_text import TranscriptDelta


def test_question_mark_opens_question() -> None:
    state = MeetingState.empty("m1")
    delta = TranscriptDelta("t1", 1, 0, 1000, "Hoe gaan we dit doen?", True, 0.9)

    proposals = HeuristicsEngine().proposals_for(
        delta, state, MeetingBuddyConfig.defaults(), now_s=10.0
    )

    assert any(proposal.type == "add_question" for proposal in proposals)


def test_later_overlap_marks_open_question_possibly_answered() -> None:
    question = Question(
        id="q1",
        text="Hoe gaan we de website controleren?",
        status=QuestionStatus.OPEN,
        source_delta_id="t1:1",
        created_at=10.0,
        confidence=0.9,
    )
    state = replace(MeetingState.empty("m1"), questions=(question,))
    delta = TranscriptDelta(
        "t1",
        2,
        1000,
        2000,
        "We gaan de website morgen controleren.",
        True,
        0.9,
    )

    proposals = HeuristicsEngine().proposals_for(
        delta, state, MeetingBuddyConfig.defaults(), now_s=20.0
    )

    updates = [proposal for proposal in proposals if proposal.type == "update_question"]
    assert len(updates) == 1
    assert updates[0].payload == {
        "question_id": "q1",
        "status": "possibly_answered",
        "resolved_at": 20.0,
    }


def test_topic_match_requires_score_and_tokens() -> None:
    topic = Topic(
        id="tp1",
        title="Beveiligingsrisico's",
        status=TopicStatus.OPEN,
        source=TopicSource.AGENDA,
        confidence=1.0,
        last_matched_at=None,
    )
    state = replace(MeetingState.empty("m1"), topics=(topic,))
    weak = TranscriptDelta("t1", 1, 0, 1000, "risico", True, 0.9)
    strong = TranscriptDelta("t1", 2, 1000, 2000, "beveiligingsrisico's besproken", True, 0.9)
    engine = HeuristicsEngine()
    config = MeetingBuddyConfig.defaults()

    assert not any(
        proposal.type == "mark_topic_discussed"
        for proposal in engine.proposals_for(weak, state, config, now_s=10.0)
    )
    assert any(
        proposal.type == "mark_topic_discussed"
        for proposal in engine.proposals_for(strong, state, config, now_s=10.0)
    )


def test_action_pattern_creates_candidate_without_owner() -> None:
    state = MeetingState.empty("m1")
    delta = TranscriptDelta("t1", 1, 0, 1000, "we moeten nog de website controleren", True, 0.9)

    proposals = HeuristicsEngine().proposals_for(
        delta, state, MeetingBuddyConfig.defaults(), now_s=10.0
    )

    action_proposals = [proposal for proposal in proposals if proposal.type == "add_action"]
    assert action_proposals
    assert action_proposals[0].payload.get("owner") in (None, "UNKNOWN", "unknown")


def test_non_final_delta_produces_no_proposals() -> None:
    delta = TranscriptDelta("t1", 1, 0, 1000, "Wat moeten we doen?", False, 0.9)

    proposals = HeuristicsEngine().proposals_for(
        delta, MeetingState.empty("m1"), MeetingBuddyConfig.defaults(), now_s=10.0
    )

    assert proposals == []
