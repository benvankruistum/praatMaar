"""
Speaker Detection (v1) — brongebaseerde ME / OTHER / UNKNOWN.

Capability: ``audio.speaker_detection``. Geen diarization of stemprofielen.
"""

from __future__ import annotations

from modules._contract import CycleEvent, CycleEventType, ModuleContext
from modules.capabilities.speaker_detection import (
    CAPABILITY_ID,
    CONTRACT_VERSION,
    AudioSource,
    SpeakerAssignment,
    SpeakerRole,
    TranscriptSegment,
)


def audio_source_from_cycle(source: str) -> AudioSource:
    """Map dicteercyclus ``CycleEvent.source`` naar ``AudioSource`` (v1)."""

    if source == "live":
        return AudioSource.MICROPHONE
    if source == "system":
        return AudioSource.SYSTEM
    return AudioSource.UNKNOWN


class SourceBasedSpeakerDetection:
    """v1: microfoon → ME, systeemaudio → OTHER, anders UNKNOWN."""

    def __init__(self) -> None:
        self._session_sources: dict[str, AudioSource] = {}

    def start_session(self, session_id: str) -> None:
        self._session_sources[session_id] = AudioSource.UNKNOWN

    def observe_audio(self, session_id: str, source: AudioSource) -> None:
        self._session_sources[session_id] = source

    def assign_speaker(self, segment: TranscriptSegment) -> SpeakerAssignment:
        source = segment.source
        if source == AudioSource.UNKNOWN:
            source = self._session_sources.get(segment.session_id, AudioSource.UNKNOWN)

        if source == AudioSource.MICROPHONE:
            return SpeakerAssignment(
                speaker_id="me",
                role=SpeakerRole.ME,
                confidence=1.0,
            )
        if source == AudioSource.SYSTEM:
            return SpeakerAssignment(
                speaker_id="other",
                role=SpeakerRole.OTHER,
                confidence=1.0,
            )
        return SpeakerAssignment(
            speaker_id="unknown",
            role=SpeakerRole.UNKNOWN,
            confidence=0.0,
        )

    def stop_session(self, session_id: str) -> None:
        self._session_sources.pop(session_id, None)


class SpeakerDetectionModule:
    id = "speaker-detection"

    def __init__(self) -> None:
        self._service: SourceBasedSpeakerDetection | None = None

    def display_name_key(self) -> str:
        return "modules.speaker_detection.name"

    def description_key(self) -> str:
        return "modules.speaker_detection.description"

    def default_enabled(self) -> bool:
        return False

    def on_app_start(self, ctx: ModuleContext) -> None:
        self._service = SourceBasedSpeakerDetection()
        ctx.capabilities.register(
            capability_id=CAPABILITY_ID,
            provider=self._service,
            owner_module_id=self.id,
            contract_version=CONTRACT_VERSION,
        )

    def on_event(self, event: CycleEvent) -> None:
        if self._service is None:
            return

        if event.type == CycleEventType.CYCLE_STARTED:
            self._service.start_session(event.session_id)
            self._service.observe_audio(
                event.session_id,
                audio_source_from_cycle(event.source),
            )
        elif event.type == CycleEventType.CYCLE_IDLE:
            self._service.stop_session(event.session_id)

    def on_app_shutdown(self) -> None:
        self._service = None
