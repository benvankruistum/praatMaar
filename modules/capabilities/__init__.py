"""Gedeelde capability-contracten (geen concrete module-implementaties)."""

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
    "AudioSource",
    "CapabilityRegistration",
    "CapabilityRegistry",
    "CapabilityUnavailableError",
    "SPEAKER_DETECTION_CAPABILITY_ID",
    "SpeakerAssignment",
    "SpeakerDetectionCapability",
    "SpeakerRole",
    "TranscriptSegment",
]
