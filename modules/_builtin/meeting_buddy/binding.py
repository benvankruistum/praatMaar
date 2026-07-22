"""Meeting Buddy capability session correlation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MeetingSessionBinding:
    meeting_session_id: str
    capture_session_id: str
    transcription_session_id: str
