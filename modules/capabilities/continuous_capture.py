"""
Contract voor capability ``audio.continuous_capture``.

Implementaties leven in ``modules._builtin``; consumers importeren alleen dit
contract + de capability-ID via de registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

CAPABILITY_ID = "audio.continuous_capture"
CONTRACT_VERSION = 1

CaptureEventHandler = Callable[[Any], None]


class CaptureStatus(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass(frozen=True)
class CaptureSession:
    session_id: str


@dataclass(frozen=True)
class AudioChunk:
    session_id: str
    chunk_id: str
    start_ms: int
    end_ms: int
    sample_rate: int
    pcm_f32: bytes  # little-endian float32 mono
    source: str = "microphone"


@dataclass(frozen=True)
class AudioChunkReceived:
    chunk: AudioChunk


@dataclass(frozen=True)
class CaptureStatusChanged:
    session_id: str
    status: CaptureStatus
    message: str | None = None


@dataclass(frozen=True)
class CaptureStopped:
    session_id: str
    reason: str  # "user" | "error" | …


@dataclass(frozen=True)
class CaptureGap:
    session_id: str
    start_ms: int
    end_ms: int
    reason: str


@runtime_checkable
class ContinuousCaptureCapability(Protocol):
    def start_session(self, config: dict[str, Any] | None = None) -> CaptureSession: ...

    def subscribe(self, session_id: str, handler: CaptureEventHandler) -> None: ...

    def unsubscribe(self, session_id: str, handler: CaptureEventHandler) -> None: ...

    def stop_session(self, session_id: str) -> None: ...

    def get_status(self, session_id: str) -> CaptureStatus: ...
