"""
Contract voor capability ``audio.speaker_detection``.

Implementaties leven in ``modules._builtin``; consumers importeren alleen dit
contract + de capability-ID via de registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

CAPABILITY_ID = "audio.speaker_detection"
CONTRACT_VERSION = 1


class SpeakerRole(StrEnum):
    ME = "me"
    OTHER = "other"
    UNKNOWN = "unknown"


class AudioSource(StrEnum):
    """Bronlabel voor v1 (geen echte diarization)."""

    MICROPHONE = "microphone"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TranscriptSegment:
    """Minimaal segment voor speaker-assignment (v1)."""

    text: str
    session_id: str
    source: AudioSource = AudioSource.UNKNOWN


@dataclass(frozen=True)
class SpeakerAssignment:
    speaker_id: str
    role: SpeakerRole
    confidence: float


@runtime_checkable
class SpeakerDetectionCapability(Protocol):
    def start_session(self, session_id: str) -> None: ...

    def observe_audio(self, session_id: str, source: AudioSource) -> None: ...

    def assign_speaker(self, segment: TranscriptSegment) -> SpeakerAssignment: ...

    def stop_session(self, session_id: str) -> None: ...
