"""Tests for Meeting Buddy stop routing and overlay agenda lines."""

from __future__ import annotations

from indicator import RecordingState
from modules._builtin.meeting_buddy import module as mb_module
from modules._builtin.meeting_buddy.overlay import format_topic_line
from modules._builtin.meeting_buddy.state import Topic, TopicSource, TopicStatus
from modules._builtin.meeting_buddy.stop_routing import stop_active_meeting
from modules.capabilities.continuous_capture import CaptureStatus


def test_sync_recording_pill_releases_when_session_stopped(monkeypatch) -> None:
    # After a meeting stops (no binding), a late capture=ACTIVE update must not
    # re-arm the pill to RECORDING; it should stay released.
    calls: list[tuple[object, str]] = []
    monkeypatch.setattr(
        mb_module, "notify_state", lambda state, mode="toggle": calls.append((state, mode))
    )
    module = mb_module.MeetingBuddyModule()
    module._pill_capture_status = CaptureStatus.ACTIVE  # meeting had the pill recording
    assert module.is_session_active is False  # session already stopped

    module._sync_recording_pill(CaptureStatus.ACTIVE)

    assert (RecordingState.RECORDING, "meeting") not in calls
    assert (RecordingState.IDLE, "meeting") in calls
    assert module._pill_capture_status is None


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
    treated = Topic(
        id="t2",
        title="Budget",
        status=TopicStatus.TREATED,
        source=TopicSource.AGENDA,
    )
    sequential = Topic(
        id="t3",
        title="Roadmap",
        status=TopicStatus.SEQUENTIAL,
        source=TopicSource.AGENDA,
    )
    confirmed = Topic(
        id="t4",
        title="Rondvraag",
        status=TopicStatus.CONFIRMED,
        source=TopicSource.AGENDA,
    )
    assert format_topic_line(open_topic).startswith("○")
    assert format_topic_line(treated).startswith("◐")
    assert format_topic_line(sequential).startswith("●")
    assert format_topic_line(confirmed).startswith("✓")
    assert "Opening" in format_topic_line(open_topic)
