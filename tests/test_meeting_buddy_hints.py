from dataclasses import replace

from modules._builtin.meeting_buddy.config import MeetingBuddyConfig
from modules._builtin.meeting_buddy.hints import HintEngine, HintType
from modules._builtin.meeting_buddy.state import (
    ActionItem,
    MeetingState,
    Question,
    QuestionStatus,
    Topic,
    TopicSource,
    TopicStatus,
)


def test_max_three_hints() -> None:
    topics = tuple(
        Topic(
            id=f"t{index}",
            title=f"Topic {index}",
            status=TopicStatus.OPEN,
            source=TopicSource.AGENDA,
            confidence=1.0,
            last_matched_at=None,
        )
        for index in range(5)
    )
    state = replace(MeetingState.empty("m1"), topics=topics)

    hints = HintEngine().evaluate(state, MeetingBuddyConfig.defaults(), now_s=10_000.0)

    assert len(hints) <= MeetingBuddyConfig.defaults().max_visible_hints


def test_low_confidence_question_no_hint() -> None:
    question = Question(
        id="q1",
        text="Wat?",
        status=QuestionStatus.OPEN,
        source_delta_id="d1",
        created_at=0.0,
        resolved_at=None,
        confidence=0.1,
    )
    state = replace(MeetingState.empty("m1"), questions=(question,))

    hints = HintEngine().evaluate(state, MeetingBuddyConfig.defaults(), now_s=61.0)

    assert not any(hint.type == HintType.QUESTION_OPEN for hint in hints)


def test_cooldown_suppresses_repeat() -> None:
    engine = HintEngine()
    topic = Topic(
        id="tp1",
        title="Budget",
        status=TopicStatus.OPEN,
        source=TopicSource.AGENDA,
        confidence=1.0,
        last_matched_at=None,
    )
    state = replace(MeetingState.empty("m1"), topics=(topic,))
    config = MeetingBuddyConfig.defaults()

    first = engine.evaluate(state, config, now_s=10_000.0)
    second = engine.evaluate(state, config, now_s=10_001.0)

    assert first
    assert second == [] or all(hint.related_entity_id != "tp1" for hint in second)


def test_candidate_action_without_owner_emits_exact_hint_type() -> None:
    action = ActionItem(
        id="a1",
        description="Website controleren",
        owner="UNKNOWN",
        confidence=0.9,
    )
    state = replace(MeetingState.empty("m1"), action_items=(action,))
    config = MeetingBuddyConfig.defaults().replace(
        hint_min_wait_s={
            **MeetingBuddyConfig.defaults().hint_min_wait_s,
            "candidate_action_without_owner": 0,
        }
    )

    hints = HintEngine().evaluate(state, config, now_s=10.0)

    assert [hint.type for hint in hints] == [HintType.CANDIDATE_ACTION_WITHOUT_OWNER]
