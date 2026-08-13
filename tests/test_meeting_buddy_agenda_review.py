"""Tests for agenda-review coordinator apply path and speaker filters."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from modules._builtin.meeting_buddy.agenda_review import (
    AgendaReviewCoordinator,
    AgendaReviewSettings,
    LabeledFinal,
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


def test_filter_questions_drops_me_matched_in_mixed_chunk() -> None:
    qs = ["Wat is de deadline?", "Wie levert de cijfers?"]
    parts = [
        LabeledFinal(text="Wat is de deadline voor ons?", speaker_role=SpeakerRole.ME),
        LabeledFinal(text="Wie levert de cijfers voor budget?", speaker_role=SpeakerRole.OTHER),
    ]
    assert filter_questions_for_speaker_roles(qs, labeled_parts=parts) == ["Wie levert de cijfers?"]


def test_format_labeled_transcript_prefers_speaker_id() -> None:
    from modules._builtin.meeting_buddy.agenda_review import _format_labeled_transcript

    text = _format_labeled_transcript(
        [
            LabeledFinal(
                text="Hallo",
                speaker_role=SpeakerRole.OTHER,
                speaker_id="spk_1",
            ),
            LabeledFinal(text="Dag", speaker_role=SpeakerRole.UNKNOWN),
        ]
    )
    assert text == "[spk_1] Hallo\n[unknown] Dag"


def test_uses_llm_review_requires_enabled_and_ready() -> None:
    caps = CapabilityRegistry()
    coord = AgendaReviewCoordinator(
        capabilities=caps,
        settings=AgendaReviewSettings(enabled=False),
    )
    assert coord.uses_llm_review() is False
    coord.update_settings(AgendaReviewSettings(enabled=True))
    assert coord.uses_llm_review() is False


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


def test_run_analyze_uses_meeting_clock_for_created_at() -> None:
    # Regression: created_at kreeg epoch-tijd (time.time() ~ 1.7e9) terwijl de
    # hint-engine met meeting-seconden (elapsed_s) rekent — age werd dan
    # extreem negatief en LLM-vragen leverden nooit een hint op.
    from modules.capabilities.semantic_analysis import (
        CAPABILITY_ID,
        CONTRACT_VERSION,
        AnalysisResult,
    )

    class FakeProvider:
        def is_ready(self) -> bool:
            return True

        def analyze(self, request: AnalysisRequest) -> AnalysisResult:
            return AnalysisResult(
                kind=KIND_AGENDA_REVIEW,
                text="",
                data={"phase": "body", "questions": ["Wat is de deadline?"]},
            )

    caps = CapabilityRegistry()
    caps.register(CAPABILITY_ID, FakeProvider(), "local-llm", CONTRACT_VERSION)

    reviewed: list[MeetingState] = []
    coord = AgendaReviewCoordinator(
        capabilities=caps,
        settings=AgendaReviewSettings(enabled=True),
        on_review=reviewed.append,
        clock=lambda: 42.0,
    )
    state = replace(MeetingState.empty("m1"), meeting_phase=MeetingPhase.BODY)
    coord._run_analyze(
        [LabeledFinal(text="Wat is de deadline?", speaker_role=SpeakerRole.OTHER)],
        state,
        "nl",
    )

    assert reviewed, "on_review is niet aangeroepen"
    question = reviewed[-1].questions[0]
    assert question.created_at == 42.0


def test_apply_review_matches_topic_by_title_when_id_unknown() -> None:
    from modules._builtin.meeting_buddy.agenda_review import _find_topic_id_by_title

    topics = (
        Topic(id="t1", title="Budget", status=TopicStatus.OPEN, source=TopicSource.AGENDA),
        Topic(id="t2", title="Planning", status=TopicStatus.OPEN, source=TopicSource.AGENDA),
    )
    assert _find_topic_id_by_title(topics, "Budget") == "t1"
    assert _find_topic_id_by_title(topics, "  planning ") == "t2"
    assert _find_topic_id_by_title(topics, "Onbekend") is None
