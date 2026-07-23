from dataclasses import replace

from modules._builtin.meeting_buddy.config import MeetingBuddyConfig
from modules._builtin.meeting_buddy.heuristics import HeuristicsEngine
from modules._builtin.meeting_buddy.state import (
    MeetingState,
    Topic,
    TopicSource,
    TopicStatus,
)
from modules._builtin.meeting_buddy.state_service import MeetingStateService
from modules.capabilities.speech_to_text import TranscriptDelta


def test_heuristics_do_not_add_questions() -> None:
    state = MeetingState.empty("m1")
    delta = TranscriptDelta("t1", 1, 0, 1000, "Hoe gaan we dit doen?", True, 0.9)

    proposals = HeuristicsEngine().proposals_for(
        delta, state, MeetingBuddyConfig.defaults(), now_s=10.0
    )

    assert not any(proposal.type.value == "add_question" for proposal in proposals)


def test_topic_match_marks_treated_only() -> None:
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
        proposal.type.value == "mark_topic_treated"
        for proposal in engine.proposals_for(weak, state, config, now_s=10.0)
    )
    treated = [
        proposal
        for proposal in engine.proposals_for(strong, state, config, now_s=10.0)
        if proposal.type.value == "mark_topic_treated"
    ]
    assert treated
    service = MeetingStateService()
    updated = service.apply(state, treated[0])
    assert updated.topics[0].status == TopicStatus.TREATED


def test_action_pattern_creates_candidate_without_owner() -> None:
    state = MeetingState.empty("m1")
    delta = TranscriptDelta("t1", 1, 0, 1000, "we moeten nog de website controleren", True, 0.9)

    proposals = HeuristicsEngine().proposals_for(
        delta, state, MeetingBuddyConfig.defaults(), now_s=10.0
    )

    action_proposals = [proposal for proposal in proposals if proposal.type.value == "add_action"]
    assert action_proposals
    assert action_proposals[0].payload.get("owner") in (None, "UNKNOWN", "unknown")


def test_overlapping_final_deltas_do_not_duplicate_action() -> None:
    engine = HeuristicsEngine()
    service = MeetingStateService()
    config = MeetingBuddyConfig.defaults()
    state = MeetingState.empty("m1")
    deltas = (
        TranscriptDelta(
            "t1",
            1,
            0,
            3000,
            "Laten we de website controleren.",
            True,
            0.9,
        ),
        TranscriptDelta(
            "t1",
            2,
            2500,
            5500,
            "Laten we de website controleren.",
            True,
            0.9,
        ),
    )
    for now_s, delta in enumerate(deltas, start=10):
        for proposal in engine.proposals_for(delta, state, config, now_s=float(now_s)):
            state = service.apply(state, proposal)

    assert len(state.action_items) == 1
