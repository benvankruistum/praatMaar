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
from modules.capabilities.semantic_analysis import (
    CAPABILITY_ID as SEMANTIC_ANALYSIS_CAPABILITY_ID,
)
from modules.capabilities.semantic_analysis import (
    CONTRACT_VERSION as SEMANTIC_ANALYSIS_CONTRACT_VERSION,
)
from modules.capabilities.semantic_analysis import (
    KIND_RUNNING_SUMMARY,
    AnalysisRequest,
    AnalysisResult,
    SemanticAnalysisCapability,
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
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID as SPEECH_TO_TEXT_CAPABILITY_ID,
)
from modules.capabilities.speech_to_text import (
    SpeechToTextCapability,
    TranscriptDelta,
    TranscriptDeltaReceived,
    TranscriptGap,
    TranscriptionSession,
    TranscriptionStatus,
    TranscriptionStatusChanged,
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
    "SEMANTIC_ANALYSIS_CAPABILITY_ID",
    "SEMANTIC_ANALYSIS_CONTRACT_VERSION",
    "KIND_RUNNING_SUMMARY",
    "AnalysisRequest",
    "AnalysisResult",
    "SemanticAnalysisCapability",
    "SPEAKER_DETECTION_CAPABILITY_ID",
    "SPEECH_TO_TEXT_CAPABILITY_ID",
    "SpeakerAssignment",
    "SpeakerDetectionCapability",
    "SpeakerRole",
    "SpeechToTextCapability",
    "TranscriptDelta",
    "TranscriptDeltaReceived",
    "TranscriptGap",
    "TranscriptionSession",
    "TranscriptionStatus",
    "TranscriptionStatusChanged",
    "TranscriptSegment",
]
