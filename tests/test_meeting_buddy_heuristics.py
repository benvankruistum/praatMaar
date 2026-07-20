from dataclasses import replace

from modules._builtin.meeting_buddy.config import MeetingBuddyConfig
from modules._builtin.meeting_buddy.heuristics import HeuristicsEngine
from modules._builtin.meeting_buddy.state import (
    ActionItemStatus,
    MeetingState,
    Question,
    QuestionStatus,
    Topic,
    TopicSource,
    TopicStatus,
)
from modules._builtin.meeting_buddy.state_service import MeetingStateService
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


def test_overlapping_final_deltas_do_not_duplicate_question_or_action() -> None:
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
            "Wie pakt dit? Laten we de website controleren.",
            True,
            0.9,
        ),
        TranscriptDelta(
            "t1",
            2,
            2500,
            5500,
            "Wie pakt dit? Laten we de website controleren.",
            True,
            0.9,
        ),
    )

    for index, delta in enumerate(deltas):
        for proposal in engine.proposals_for(delta, state, config, now_s=10.0 + index):
            state = service.apply(state, proposal)

    assert len(state.questions) == 1
    assert (
        len(
            [action for action in state.action_items if action.status == ActionItemStatus.CANDIDATE]
        )
        == 1
    )


def test_overlapping_revised_question_stays_open_without_answer_update() -> None:
    engine = HeuristicsEngine()
    service = MeetingStateService()
    config = MeetingBuddyConfig.defaults()
    state = MeetingState.empty("m1")
    first = TranscriptDelta(
        "t1",
        1,
        0,
        3000,
        "Hoe gaan we de website controleren?",
        True,
        0.9,
    )
    revised = TranscriptDelta(
        "t1",
        2,
        500,
        3500,
        "Hoe gaan we deze website controleren?",
        True,
        0.9,
    )

    for proposal in engine.proposals_for(first, state, config, now_s=10.0):
        state = service.apply(state, proposal)
    revised_proposals = engine.proposals_for(revised, state, config, now_s=11.0)
    for proposal in revised_proposals:
        state = service.apply(state, proposal)

    assert len(state.questions) == 1
    assert state.questions[0].status == QuestionStatus.OPEN
    assert not any(proposal.type == "update_question" for proposal in revised_proposals)


def test_non_final_delta_produces_no_proposals() -> None:
    delta = TranscriptDelta("t1", 1, 0, 1000, "Wat moeten we doen?", False, 0.9)

    proposals = HeuristicsEngine().proposals_for(
        delta, MeetingState.empty("m1"), MeetingBuddyConfig.defaults(), now_s=10.0
    )

    assert proposals == []
