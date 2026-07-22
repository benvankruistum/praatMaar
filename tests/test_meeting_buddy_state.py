from dataclasses import FrozenInstanceError

import pytest

from modules._builtin.meeting_buddy.state import (
    ActionItemStatus,
    HintStatus,
    MeetingState,
    QuestionStatus,
    TopicSource,
    TopicStatus,
)
from modules._builtin.meeting_buddy.state_service import (
    MeetingStateService,
    StateProposal,
    StateProposalType,
)


def proposal(proposal_type: str | StateProposalType, payload: dict[str, object]) -> StateProposal:
    resolved_type = (
        proposal_type
        if isinstance(proposal_type, StateProposalType)
        else StateProposalType(proposal_type)
    )
    return StateProposal(
        proposal_id=f"p-{resolved_type.value}",
        meeting_session_id="m1",
        type=resolved_type,
        payload=payload,
        source_delta_ids=("d1",),
        confidence=0.8,
        created_at=10.0,
    )


def test_apply_increments_version_immutably() -> None:
    s0 = MeetingState.empty(meeting_session_id="m1")
    assert s0.version == 0
    p = proposal("add_topics", {"titles": ["Budget"], "source": "agenda"})

    s1 = MeetingStateService().apply(s0, p)

    assert s1.version == 1
    assert s0.version == 0
    assert s0.topics == ()
    assert len(s1.topics) == 1
    assert s1.topics[0].title == "Budget"
    assert s1.topics[0].status == TopicStatus.OPEN
    assert s1.topics[0].source == TopicSource.AGENDA
    with pytest.raises(FrozenInstanceError):
        s1.version = 2  # type: ignore[misc]


def test_apply_supports_all_meeting_state_transitions() -> None:
    service = MeetingStateService()
    state = MeetingState.empty("m1")
    state = service.apply(
        state,
        proposal(
            "add_topics",
            {"topics": [{"id": "t1", "title": "Budget", "source": "manual"}]},
        ),
    )
    state = service.apply(
        state,
        proposal("mark_topic_discussed", {"topic_id": "t1", "matched_at": 12.0}),
    )
    state = service.apply(
        state,
        proposal("add_question", {"id": "q1", "text": "Wie pakt dit?"}),
    )
    state = service.apply(
        state,
        proposal(
            "update_question",
            {"question_id": "q1", "status": "answered", "resolved_at": 20.0},
        ),
    )
    state = service.apply(
        state,
        proposal("add_action", {"id": "a1", "description": "Plan review"}),
    )
    state = service.apply(
        state,
        proposal(
            "update_action",
            {"action_id": "a1", "owner": "Kim", "status": "confirmed"},
        ),
    )
    state = service.apply(
        state,
        proposal(
            "upsert_hints",
            {
                "hints": [
                    {
                        "id": "h1",
                        "type": "question_open",
                        "message": "Vraag staat nog open",
                        "priority": 2,
                        "related_entity_id": "q1",
                        "cooldown_key": "question:q1",
                    }
                ]
            },
        ),
    )
    state = service.apply(
        state,
        proposal(
            "upsert_hints",
            {"hints": [{"id": "h1", "status": "dismissed", "message": "Gesloten"}]},
        ),
    )

    assert state.version == 8
    assert state.topics[0].status == TopicStatus.DISCUSSED
    assert state.topics[0].last_matched_at == 12.0
    assert state.questions[0].status == QuestionStatus.ANSWERED
    assert state.questions[0].source_delta_id == "d1"
    assert state.action_items[0].status == ActionItemStatus.CONFIRMED
    assert state.action_items[0].owner == "Kim"
    assert state.emitted_hints[0].status == HintStatus.DISMISSED
    assert state.emitted_hints[0].message == "Gesloten"


@pytest.mark.parametrize(
    ("proposal_type", "payload"),
    [
        ("mark_topic_discussed", {"topic_id": "missing"}),
        ("update_question", {"question_id": "missing", "status": "answered"}),
        ("update_action", {"action_id": "missing", "status": "confirmed"}),
    ],
)
def test_apply_rejects_updates_for_unknown_entities(
    proposal_type: str, payload: dict[str, object]
) -> None:
    with pytest.raises(ValueError, match="not found"):
        MeetingStateService().apply(
            MeetingState.empty("m1"),
            proposal(proposal_type, payload),
        )


def test_apply_rejects_wrong_session_and_unknown_type() -> None:
    state = MeetingState.empty("m1")
    wrong_session = StateProposal(
        proposal_id="p1",
        meeting_session_id="m2",
        type=StateProposalType.ADD_TOPICS,
        payload={"titles": ["Budget"]},
        source_delta_ids=(),
        confidence=1.0,
    )

    with pytest.raises(ValueError, match="session"):
        MeetingStateService().apply(state, wrong_session)
    invalid = proposal("add_topics", {"titles": ["Budget"]})
    object.__setattr__(invalid, "type", "no_such_type")
    with pytest.raises(ValueError, match="Unsupported"):
        MeetingStateService().apply(state, invalid)
