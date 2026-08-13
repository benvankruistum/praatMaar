"""Tests for transcript processor catch-up after heuristics."""

from __future__ import annotations

from dataclasses import replace

from modules._builtin.meeting_buddy.binding import MeetingSessionBinding
from modules._builtin.meeting_buddy.config import MeetingBuddyConfig
from modules._builtin.meeting_buddy.state import (
    MeetingState,
    Topic,
    TopicSource,
    TopicStatus,
)
from modules._builtin.meeting_buddy.transcript_processor import TranscriptProcessor
from modules.capabilities.speech_to_text import TranscriptDelta, TranscriptDeltaReceived


def _binding() -> MeetingSessionBinding:
    return MeetingSessionBinding(
        meeting_session_id="m1",
        capture_session_id="cap1",
        transcription_session_id="stt1",
    )


def test_heuristic_topic_match_triggers_sequential_catch_up() -> None:
    topic = Topic(
        id="tp1",
        title="Beveiligingsrisico's",
        status=TopicStatus.OPEN,
        source=TopicSource.AGENDA,
    )
    state = replace(MeetingState.empty("m1"), topics=(topic,))
    delta = TranscriptDelta(
        "stt1",
        1,
        0,
        1000,
        "beveiligingsrisico's besproken",
        True,
        0.9,
    )
    event = TranscriptDeltaReceived(delta=delta)

    updated = TranscriptProcessor().process_delta(
        event,
        binding=_binding(),
        state=state,
        config=MeetingBuddyConfig.defaults(),
        elapsed_s=10.0,
        observer=None,
        use_topic_heuristics=True,
    )

    assert updated.topics[0].status == TopicStatus.SEQUENTIAL
