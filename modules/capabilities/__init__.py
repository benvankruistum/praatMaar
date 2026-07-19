"""Gedeelde capability-contracten (geen concrete module-implementaties)."""

from modules.capabilities.continuous_capture import (
    CAPABILITY_ID as CONTINUOUS_CAPTURE_CAPABILITY_ID,
)
from modules.capabilities.continuous_capture import (
    AudioChunk,
    AudioChunkReceived,
    CaptureGap,
    CaptureSession,
    CaptureStatus,
    CaptureStatusChanged,
    CaptureStopped,
    ContinuousCaptureCapability,
)
from modules.capabilities.registry import (
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityUnavailableError,
)
from modules.capabilities.speaker_detection import (
    CAPABILITY_ID as SPEAKER_DETECTION_CAPABILITY_ID,
)
from modules.capabilities.speaker_detection import (
    AudioSource,
    SpeakerAssignment,
    SpeakerDetectionCapability,
    SpeakerRole,
    TranscriptSegment,
)

__all__ = [
    "AudioChunk",
    "AudioChunkReceived",
    "AudioSource",
    "CaptureGap",
    "CaptureSession",
    "CaptureStatus",
    "CaptureStatusChanged",
    "CaptureStopped",
    "CapabilityRegistration",
    "CapabilityRegistry",
    "CapabilityUnavailableError",
    "CONTINUOUS_CAPTURE_CAPABILITY_ID",
    "ContinuousCaptureCapability",
    "SPEAKER_DETECTION_CAPABILITY_ID",
    "SpeakerAssignment",
    "SpeakerDetectionCapability",
    "SpeakerRole",
    "TranscriptSegment",
]
