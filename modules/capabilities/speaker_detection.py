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
CONTRACT_VERSION = 2


class SpeakerRole(StrEnum):
    ME = "me"
    OTHER = "other"
    UNKNOWN = "unknown"


class AudioSource(StrEnum):
    """Bronlabel voor source-mode (geen diarization)."""

    MICROPHONE = "microphone"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class LabelingMode(StrEnum):
    """Hoe sprekers binnen een sessie gelabeld worden."""

    SOURCE = "source"
    CLUSTER = "cluster"


@dataclass(frozen=True)
class TranscriptSegment:
    """Segment voor speaker-assignment."""

    text: str
    session_id: str
    source: AudioSource = AudioSource.UNKNOWN
    start_ms: int | None = None
    end_ms: int | None = None


@dataclass(frozen=True)
class SpeakerAssignment:
    speaker_id: str
    role: SpeakerRole
    confidence: float


@runtime_checkable
class SpeakerDetectionCapability(Protocol):
    def start_session(self, session_id: str) -> None: ...

    def observe_audio(self, session_id: str, source: AudioSource) -> None: ...

    def observe_pcm(
        self,
        session_id: str,
        pcm_f32: bytes,
        start_ms: int,
        end_ms: int,
        sample_rate: int,
    ) -> None: ...

    def set_labeling_mode(self, session_id: str, mode: LabelingMode) -> None: ...

    def assign_speaker(self, segment: TranscriptSegment) -> SpeakerAssignment: ...

    def stop_session(self, session_id: str) -> None: ...
