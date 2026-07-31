"""Session controller wires Meeting Buddy capture into cluster speaker mode."""

from __future__ import annotations

from modules._builtin.meeting_buddy.config import MeetingBuddyConfig
from modules._builtin.meeting_buddy.session_controller import CapabilitySessionController
from modules.capabilities.continuous_capture import (
    CAPABILITY_ID as CAP_CAPTURE,
)
from modules.capabilities.continuous_capture import (
    AudioChunk,
    AudioChunkReceived,
    CaptureSession,
    CaptureStatus,
)
from modules.capabilities.registry import CapabilityRegistry
from modules.capabilities.speaker_detection import (
    CAPABILITY_ID as CAP_SPEAKER,
)
from modules.capabilities.speaker_detection import (
    CONTRACT_VERSION as SPEAKER_CONTRACT_VERSION,
)
from modules.capabilities.speaker_detection import (
    LabelingMode,
)
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID as CAP_STT,
)
from modules.capabilities.speech_to_text import (
    TranscriptionSession,
    TranscriptionStatus,
)


class _FakeCapture:
    def __init__(self) -> None:
        self.handlers: list[object] = []
        self.stopped: list[str] = []

    def start_session(self, config=None):
        return CaptureSession(session_id="cap-1")

    def subscribe(self, session_id: str, handler) -> None:
        self.handlers.append(handler)

    def unsubscribe(self, session_id: str, handler) -> None:
        if handler in self.handlers:
            self.handlers.remove(handler)

    def stop_session(self, session_id: str) -> None:
        self.stopped.append(session_id)

    def get_status(self, session_id: str) -> CaptureStatus:
        return CaptureStatus.ACTIVE


class _FakeStt:
    def start_session(self, *, capture_session_id, capture, config=None):
        return TranscriptionSession(session_id="stt-1")

    def subscribe(self, session_id: str, handler) -> None:
        pass

    def unsubscribe(self, session_id: str, handler) -> None:
        pass

    def stop_session(self, session_id: str) -> None:
        pass

    def get_status(self, session_id: str) -> TranscriptionStatus:
        return TranscriptionStatus.ACTIVE


class _FakeSpeaker:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.modes: dict[str, LabelingMode] = {}
        self.pcm: list[tuple[str, int, int]] = []
        self.stopped: list[str] = []

    def start_session(self, session_id: str) -> None:
        self.started.append(session_id)

    def set_labeling_mode(self, session_id: str, mode: LabelingMode) -> None:
        self.modes[session_id] = mode

    def observe_pcm(
        self,
        session_id: str,
        pcm_f32: bytes,
        start_ms: int,
        end_ms: int,
        sample_rate: int,
    ) -> None:
        self.pcm.append((session_id, start_ms, end_ms))

    def stop_session(self, session_id: str) -> None:
        self.stopped.append(session_id)


def test_start_uses_cluster_mode_and_feeds_pcm(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "modules._builtin.meeting_buddy.session_controller.load_config",
        lambda: {"microphone_device": None, "speech_language": "nl"},
        raising=False,
    )
    monkeypatch.setattr(
        "config.load_config", lambda: {"microphone_device": None, "speech_language": "nl"}
    )

    caps = CapabilityRegistry()
    capture = _FakeCapture()
    stt = _FakeStt()
    speaker = _FakeSpeaker()
    caps.register(CAP_CAPTURE, capture, owner_module_id="audio-capture")
    caps.register(CAP_STT, stt, owner_module_id="speech-to-text")
    caps.register(
        CAP_SPEAKER,
        speaker,
        owner_module_id="speaker-detection",
        contract_version=SPEAKER_CONTRACT_VERSION,
    )

    controller = CapabilitySessionController(
        capabilities=caps,
        config=MeetingBuddyConfig.defaults(),
    )
    binding = controller.start()
    assert speaker.started == [binding.meeting_session_id]
    assert speaker.modes[binding.meeting_session_id] == LabelingMode.CLUSTER

    controller.subscribe(
        on_capture_status=controller.handle_capture_event, on_stt_event=lambda e: None
    )
    # Drive the subscribed handler the way capture would.
    handler = capture.handlers[0]
    chunk = AudioChunk(
        session_id="cap-1",
        chunk_id="c1",
        start_ms=0,
        end_ms=800,
        sample_rate=16000,
        pcm_f32=b"\x00\x00\x00\x00",
    )
    handler(AudioChunkReceived(chunk=chunk))
    assert speaker.pcm == [(binding.meeting_session_id, 0, 800)]

    controller.stop(duration_ms=1000)
    assert speaker.stopped == [binding.meeting_session_id]
