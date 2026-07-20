"""
Contract voor capability ``transcription.speech_to_text``.

Implementaties leven in ``modules._builtin``; consumers importeren alleen dit
contract + de capability-ID via de registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

CAPABILITY_ID = "transcription.speech_to_text"
CONTRACT_VERSION = 1

SttEventHandler = Callable[[Any], None]


class TranscriptionStatus(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"
    DELAYED = "delayed"
    ERROR = "error"


@dataclass(frozen=True)
class TranscriptionSession:
    session_id: str


@dataclass(frozen=True)
class TranscriptDelta:
    session_id: str
    sequence: int
    start_ms: int
    end_ms: int
    text: str
    is_final: bool
    confidence: float


@dataclass(frozen=True)
class TranscriptDeltaReceived:
    delta: TranscriptDelta


@dataclass(frozen=True)
class TranscriptionStatusChanged:
    session_id: str
    status: TranscriptionStatus
    message: str | None = None


@dataclass(frozen=True)
class TranscriptGap:
    session_id: str
    start_ms: int
    end_ms: int
    reason: str


@runtime_checkable
class SpeechToTextCapability(Protocol):
    def start_session(
        self,
        *,
        capture_session_id: str,
        capture: Any,  # ContinuousCaptureCapability
        config: dict[str, Any] | None = None,
    ) -> TranscriptionSession: ...

    def subscribe(self, session_id: str, handler: SttEventHandler) -> None: ...

    def unsubscribe(self, session_id: str, handler: SttEventHandler) -> None: ...

    def stop_session(self, session_id: str) -> None: ...

    def get_status(self, session_id: str) -> TranscriptionStatus: ...
