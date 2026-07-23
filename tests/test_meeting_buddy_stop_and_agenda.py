"""Tests for Meeting Buddy stop routing and overlay agenda lines."""

from __future__ import annotations

from modules._builtin.meeting_buddy.overlay import format_topic_line
from modules._builtin.meeting_buddy.state import Topic, TopicSource, TopicStatus
from modules._builtin.meeting_buddy.stop_routing import stop_active_meeting


class _FakeMeeting:
    id = "meeting-buddy"

    def __init__(self, *, active: bool) -> None:
        self.is_session_active = active
        self.stopped = False

    def stop_meeting(self) -> None:
        self.stopped = True
        self.is_session_active = False


def test_stop_active_meeting_stops_running_session() -> None:
    meeting = _FakeMeeting(active=True)
    assert stop_active_meeting([meeting]) is True
    assert meeting.stopped is True


def test_stop_active_meeting_noop_when_idle() -> None:
    meeting = _FakeMeeting(active=False)
    assert stop_active_meeting([meeting]) is False
    assert meeting.stopped is False


def test_stop_active_meeting_ignores_other_modules() -> None:
    other = type("Other", (), {"id": "audio-capture", "is_session_active": True})()
    meeting = _FakeMeeting(active=True)
    assert stop_active_meeting([other, meeting]) is True
    assert meeting.stopped is True


def test_format_topic_line_marks_status() -> None:
    open_topic = Topic(id="t1", title="Opening", status=TopicStatus.OPEN, source=TopicSource.AGENDA)
    done = Topic(
        id="t2",
        title="Rondvraag",
        status=TopicStatus.DISCUSSED,
        source=TopicSource.AGENDA,
    )
    assert format_topic_line(open_topic).startswith("○")
    assert "Opening" in format_topic_line(open_topic)
    assert format_topic_line(done).startswith("✓")
