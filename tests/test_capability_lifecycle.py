"""Lifecycle- en consumer-tests voor capabilities (Speaker Detection)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules._builtin.speaker_detection import (
    SourceBasedSpeakerDetection,
    SpeakerDetectionModule,
)
from modules._contract import ModuleContext, ModuleWithShutdown, noop_ui_dispatch
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.speaker_detection import (
    CAPABILITY_ID,
    AudioSource,
    SpeakerAssignment,
    SpeakerDetectionCapability,
    SpeakerRole,
    TranscriptSegment,
)
from modules.registry import load_enabled_modules, shutdown_modules
from modules.whisper import SharedWhisper


@dataclass
class EnrichedSegment:
    text: str
    speaker: SpeakerAssignment


class MeetingBuddyConsumer:
    """Minimale Meeting Buddy-achtige consumer (geen productmodule)."""

    def __init__(self, ctx: ModuleContext) -> None:
        provider = ctx.capabilities.get(CAPABILITY_ID, minimum_contract_version=1)
        if isinstance(provider, SpeakerDetectionCapability):
            self._speaker_detection = provider
        else:
            self._speaker_detection = None

    def enrich_transcript(self, segment: TranscriptSegment) -> EnrichedSegment:
        if self._speaker_detection is None:
            assignment = SpeakerAssignment(
                speaker_id="unknown",
                role=SpeakerRole.UNKNOWN,
                confidence=0.0,
            )
        else:
            try:
                assignment = self._speaker_detection.assign_speaker(segment)
            except Exception:
                assignment = SpeakerAssignment(
                    speaker_id="unknown",
                    role=SpeakerRole.UNKNOWN,
                    confidence=0.0,
                )
        return EnrichedSegment(text=segment.text, speaker=assignment)


class _FailingProvider:
    def start_session(self, session_id: str) -> None:
        pass

    def observe_audio(self, session_id: str, source: AudioSource) -> None:
        pass

    def assign_speaker(self, segment: TranscriptSegment) -> SpeakerAssignment:
        raise RuntimeError("boom")

    def stop_session(self, session_id: str) -> None:
        pass


class _ExplodingShutdownModule:
    id = "explode"

    def display_name_key(self) -> str:
        return "x"

    def description_key(self) -> str:
        return "x"

    def default_enabled(self) -> bool:
        return True

    def on_app_start(self, ctx: ModuleContext) -> None:
        ctx.capabilities.register("cap.x", object(), owner_module_id=self.id)

    def on_event(self, event) -> None:
        pass

    def on_app_shutdown(self) -> None:
        raise RuntimeError("shutdown failed")


def test_speaker_detection_registers_on_start(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("host.app_dir", lambda: tmp_path)
    caps = CapabilityRegistry()
    modules = load_enabled_modules(
        {
            "speaker-detection": {"enabled": True},
            "inbox-mirror": {"enabled": False},
            "audio-capture": {"enabled": False},
            "speech-to-text": {"enabled": False},
        },
        whisper=SharedWhisper(),
        capabilities=caps,
    )
    assert len(modules) == 1
    provider = caps.get(CAPABILITY_ID)
    assert isinstance(provider, SourceBasedSpeakerDetection)


def test_capability_removed_after_shutdown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("host.app_dir", lambda: tmp_path)
    caps = CapabilityRegistry()
    modules = load_enabled_modules(
        {
            "speaker-detection": {"enabled": True},
            "inbox-mirror": {"enabled": False},
            "audio-capture": {"enabled": False},
            "speech-to-text": {"enabled": False},
        },
        capabilities=caps,
    )
    assert caps.get(CAPABILITY_ID) is not None
    shutdown_modules(modules, capabilities=caps)
    assert caps.get(CAPABILITY_ID) is None


def test_capability_removed_even_if_shutdown_raises() -> None:
    caps = CapabilityRegistry()
    module = _ExplodingShutdownModule()
    ctx = ModuleContext(
        app_dir=Path("."),
        ui_dispatch=noop_ui_dispatch,
        capabilities=caps,
    )
    module.on_app_start(ctx)
    assert caps.get("cap.x") is not None
    assert isinstance(module, ModuleWithShutdown)
    shutdown_modules([module], capabilities=caps)
    assert caps.get("cap.x") is None


def test_consumer_starts_without_speaker_detection() -> None:
    ctx = ModuleContext(app_dir=Path("."), ui_dispatch=noop_ui_dispatch)
    buddy = MeetingBuddyConsumer(ctx)
    result = buddy.enrich_transcript(
        TranscriptSegment(text="hallo", session_id="s1", source=AudioSource.MICROPHONE)
    )
    assert result.speaker.role == SpeakerRole.UNKNOWN


def test_consumer_uses_provider_when_available() -> None:
    caps = CapabilityRegistry()
    service = SourceBasedSpeakerDetection()
    caps.register(CAPABILITY_ID, service, owner_module_id="speaker-detection")
    ctx = ModuleContext(
        app_dir=Path("."),
        ui_dispatch=noop_ui_dispatch,
        capabilities=caps,
    )
    buddy = MeetingBuddyConsumer(ctx)
    result = buddy.enrich_transcript(
        TranscriptSegment(text="hallo", session_id="s1", source=AudioSource.MICROPHONE)
    )
    assert result.speaker.role == SpeakerRole.ME
    assert result.speaker.speaker_id == "me"

    other = buddy.enrich_transcript(
        TranscriptSegment(text="hi", session_id="s1", source=AudioSource.SYSTEM)
    )
    assert other.speaker.role == SpeakerRole.OTHER


def test_consumer_falls_back_when_provider_errors() -> None:
    caps = CapabilityRegistry()
    caps.register(CAPABILITY_ID, _FailingProvider(), owner_module_id="speaker-detection")
    ctx = ModuleContext(
        app_dir=Path("."),
        ui_dispatch=noop_ui_dispatch,
        capabilities=caps,
    )
    buddy = MeetingBuddyConsumer(ctx)
    result = buddy.enrich_transcript(
        TranscriptSegment(text="x", session_id="s1", source=AudioSource.MICROPHONE)
    )
    assert result.speaker.role == SpeakerRole.UNKNOWN


def test_source_based_observe_audio_session_default() -> None:
    service = SourceBasedSpeakerDetection()
    service.start_session("s1")
    service.observe_audio("s1", AudioSource.SYSTEM)
    assignment = service.assign_speaker(
        TranscriptSegment(text="x", session_id="s1", source=AudioSource.UNKNOWN)
    )
    assert assignment.role == SpeakerRole.OTHER
    service.stop_session("s1")


def test_speaker_detection_module_default_disabled() -> None:
    assert SpeakerDetectionModule().default_enabled() is False
