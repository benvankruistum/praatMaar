"""Tests for agenda-review coordinator apply path and speaker filters."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from modules._builtin.meeting_buddy.agenda_review import (
    AgendaReviewCoordinator,
    AgendaReviewSettings,
    filter_questions_for_speaker_roles,
    should_accept_question_role,
)
from modules._builtin.meeting_buddy.state import (
    MeetingPhase,
    MeetingState,
    Topic,
    TopicSource,
    TopicStatus,
)
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.semantic_analysis import (
    KIND_AGENDA_REVIEW,
    AnalysisRequest,
)
from modules.capabilities.speaker_detection import SpeakerRole


def test_should_accept_question_role() -> None:
    assert should_accept_question_role(SpeakerRole.OTHER) is True
    assert should_accept_question_role(SpeakerRole.UNKNOWN) is True
    assert should_accept_question_role(SpeakerRole.ME) is False


def test_filter_questions_drops_when_only_me() -> None:
    qs = ["Wat is de deadline?"]
    assert filter_questions_for_speaker_roles(qs, source_roles=[SpeakerRole.ME]) == []
    assert (
        filter_questions_for_speaker_roles(qs, source_roles=[SpeakerRole.OTHER, SpeakerRole.ME])
        == qs
    )


def test_apply_review_treated_then_catch_up_and_questions() -> None:
    caps = CapabilityRegistry()
    coord = AgendaReviewCoordinator(
        capabilities=caps,
        settings=AgendaReviewSettings(),
    )
    state = replace(
        MeetingState.empty("m1"),
        meeting_phase=MeetingPhase.BODY,
        topics=(
            Topic(id="t1", title="Opening", status=TopicStatus.OPEN, source=TopicSource.AGENDA),
            Topic(id="t2", title="Budget", status=TopicStatus.OPEN, source=TopicSource.AGENDA),
        ),
    )
    updated = coord.apply_review_result(
        state,
        {
            "phase": "body",
            "topic_updates": [{"topic_id": "t1", "status": "treated"}],
            "questions": ["Wat is de deadline voor het budget?"],
        },
        now_s=10.0,
    )
    assert updated.topics[0].status == TopicStatus.SEQUENTIAL
    assert updated.topics[1].status == TopicStatus.OPEN
    assert len(updated.questions) == 1
    assert "deadline" in updated.questions[0].text.lower()


def test_opening_phase_blocks_later_topic_from_llm() -> None:
    caps = CapabilityRegistry()
    coord = AgendaReviewCoordinator(capabilities=caps, settings=AgendaReviewSettings())
    state = replace(
        MeetingState.empty("m1"),
        meeting_phase=MeetingPhase.OPENING,
        topics=(
            Topic(id="t1", title="Opening", status=TopicStatus.OPEN, source=TopicSource.AGENDA),
            Topic(id="t2", title="Budget", status=TopicStatus.OPEN, source=TopicSource.AGENDA),
        ),
    )
    updated = coord.apply_review_result(
        state,
        {
            "phase": "opening",
            "topic_updates": [{"topic_id": "t2", "status": "treated"}],
            "questions": [],
        },
        now_s=5.0,
    )
    assert updated.topics[1].status == TopicStatus.OPEN


def test_provider_agenda_review_json(monkeypatch) -> None:
    from modules._builtin.local_llm.provider import OllamaSemanticAnalysis

    client = MagicMock()
    client.has_model.return_value = True
    client.chat.return_value = (
        '{"phase":"body","topic_updates":[{"topic_id":"t1","status":"treated"}],'
        '"questions":["Wie levert de cijfers?"]}'
    )
    provider = OllamaSemanticAnalysis(client, model="qwen2.5:7b")
    result = provider.analyze(
        AnalysisRequest(
            kind=KIND_AGENDA_REVIEW,
            transcript="[other] Wie levert de cijfers voor budget?",
            context={
                "phase": "body",
                "topics": [{"topic_id": "t1", "title": "Budget", "status": "open"}],
            },
        )
    )
    assert result.kind == KIND_AGENDA_REVIEW
    assert result.data is not None
    assert result.data["phase"] == "body"
    assert result.data["topic_updates"][0]["status"] == "treated"
    assert result.data["questions"]
