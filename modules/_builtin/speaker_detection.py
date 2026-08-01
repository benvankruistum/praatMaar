"""
Speaker Detection — source-mode (ME/OTHER) + cluster-mode (spk_n, single mic).

Capability: ``audio.speaker_detection`` (contract v2).
"""

from __future__ import annotations

from modules._builtin.speaker_clustering import OnlineSpeakerCluster
from modules._contract import CycleEvent, CycleEventType, ModuleContext
from modules.capabilities.speaker_detection import (
    CAPABILITY_ID,
    CONTRACT_VERSION,
    AudioSource,
    LabelingMode,
    SpeakerAssignment,
    SpeakerRole,
    TranscriptSegment,
)


def audio_source_from_cycle(source: str) -> AudioSource:
    """Map dicteercyclus ``CycleEvent.source`` naar ``AudioSource``."""

    if source == "live":
        return AudioSource.MICROPHONE
    if source == "system":
        return AudioSource.SYSTEM
    return AudioSource.UNKNOWN


class SpeakerDetectionService:
    """v2: source-based ME/OTHER of single-mic clustering (geen ME)."""

    def __init__(self) -> None:
        self._session_sources: dict[str, AudioSource] = {}
        self._modes: dict[str, LabelingMode] = {}
        self._cluster = OnlineSpeakerCluster()

    def start_session(self, session_id: str) -> None:
        self._session_sources[session_id] = AudioSource.UNKNOWN
        self._modes.setdefault(session_id, LabelingMode.SOURCE)
        self._cluster.start_session(session_id)

    def set_labeling_mode(self, session_id: str, mode: LabelingMode) -> None:
        self._modes[session_id] = mode

    def observe_audio(self, session_id: str, source: AudioSource) -> None:
        self._session_sources[session_id] = source

    def observe_pcm(
        self,
        session_id: str,
        pcm_f32: bytes,
        start_ms: int,
        end_ms: int,
        sample_rate: int,
    ) -> None:
        self._cluster.observe_pcm(session_id, pcm_f32, start_ms, end_ms, sample_rate)

    def assign_speaker(self, segment: TranscriptSegment) -> SpeakerAssignment:
        mode = self._modes.get(segment.session_id, LabelingMode.SOURCE)
        if mode == LabelingMode.CLUSTER:
            hit = self._cluster.assign(segment.session_id, segment.start_ms, segment.end_ms)
            if hit is None:
                return SpeakerAssignment(
                    speaker_id="unknown",
                    role=SpeakerRole.UNKNOWN,
                    confidence=0.0,
                )
            return SpeakerAssignment(
                speaker_id=hit.speaker_id,
                role=SpeakerRole.OTHER,
                confidence=hit.confidence,
            )

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
        self._modes.pop(session_id, None)
        self._cluster.stop_session(session_id)


# Back-compat alias used by older tests/docs.
SourceBasedSpeakerDetection = SpeakerDetectionService


class SpeakerDetectionModule:
    id = "speaker-detection"

    def __init__(self) -> None:
        self._service: SpeakerDetectionService | None = None

    def display_name_key(self) -> str:
        return "modules.speaker_detection.name"

    def description_key(self) -> str:
        return "modules.speaker_detection.description"

    def default_enabled(self) -> bool:
        return False

    def on_app_start(self, ctx: ModuleContext) -> None:
        self._service = SpeakerDetectionService()
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
            self._service.set_labeling_mode(event.session_id, LabelingMode.SOURCE)
            self._service.observe_audio(
                event.session_id,
                audio_source_from_cycle(event.source),
            )
        elif event.type == CycleEventType.CYCLE_IDLE:
            self._service.stop_session(event.session_id)

    def on_app_shutdown(self) -> None:
        self._service = None
