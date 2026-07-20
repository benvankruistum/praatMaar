"""Unit tests voor Speaker Detection (v1 — brongebaseerd ME / OTHER / UNKNOWN)."""

from __future__ import annotations

from modules._builtin.speaker_detection import (
    SourceBasedSpeakerDetection,
    SpeakerDetectionModule,
    audio_source_from_cycle,
)
from modules._contract import CycleEvent, CycleEventType, ModuleContext, noop_ui_dispatch
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.speaker_detection import (
    CAPABILITY_ID,
    AudioSource,
    SpeakerRole,
    TranscriptSegment,
)


def test_microphone_maps_to_me() -> None:
    service = SourceBasedSpeakerDetection()
    assignment = service.assign_speaker(
        TranscriptSegment(text="hallo", session_id="s1", source=AudioSource.MICROPHONE)
    )
    assert assignment.role == SpeakerRole.ME
    assert assignment.speaker_id == "me"
    assert assignment.confidence == 1.0


def test_system_maps_to_other() -> None:
    service = SourceBasedSpeakerDetection()
    assignment = service.assign_speaker(
        TranscriptSegment(text="hi", session_id="s1", source=AudioSource.SYSTEM)
    )
    assert assignment.role == SpeakerRole.OTHER
    assert assignment.speaker_id == "other"
    assert assignment.confidence == 1.0


def test_unknown_source_maps_to_unknown() -> None:
    service = SourceBasedSpeakerDetection()
    assignment = service.assign_speaker(
        TranscriptSegment(text="?", session_id="s1", source=AudioSource.UNKNOWN)
    )
    assert assignment.role == SpeakerRole.UNKNOWN
    assert assignment.speaker_id == "unknown"
    assert assignment.confidence == 0.0


def test_segment_source_overrides_session_observe() -> None:
    service = SourceBasedSpeakerDetection()
    service.start_session("s1")
    service.observe_audio("s1", AudioSource.SYSTEM)
    assignment = service.assign_speaker(
        TranscriptSegment(text="x", session_id="s1", source=AudioSource.MICROPHONE)
    )
    assert assignment.role == SpeakerRole.ME


def test_audio_source_from_cycle_live_is_microphone() -> None:
    assert audio_source_from_cycle("live") == AudioSource.MICROPHONE


def test_audio_source_from_cycle_system_is_system() -> None:
    assert audio_source_from_cycle("system") == AudioSource.SYSTEM


def test_audio_source_from_cycle_unknown_values() -> None:
    assert audio_source_from_cycle("recovery") == AudioSource.UNKNOWN
    assert audio_source_from_cycle("") == AudioSource.UNKNOWN


def test_module_tracks_session_on_cycle_events() -> None:
    module = SpeakerDetectionModule()
    caps = CapabilityRegistry()
    ctx = ModuleContext(
        app_dir=__import__("pathlib").Path("."), ui_dispatch=noop_ui_dispatch, capabilities=caps
    )
    module.on_app_start(ctx)
    provider = caps.get(CAPABILITY_ID)
    assert provider is not None

    module.on_event(
        CycleEvent(type=CycleEventType.CYCLE_STARTED, session_id="sess-1", source="live")
    )
    assignment = provider.assign_speaker(
        TranscriptSegment(text="ik", session_id="sess-1", source=AudioSource.UNKNOWN)
    )
    assert assignment.role == SpeakerRole.ME

    module.on_event(CycleEvent(type=CycleEventType.CYCLE_IDLE, session_id="sess-1"))
    assignment_after = provider.assign_speaker(
        TranscriptSegment(text="ik", session_id="sess-1", source=AudioSource.UNKNOWN)
    )
    assert assignment_after.role == SpeakerRole.UNKNOWN
