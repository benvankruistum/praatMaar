from pathlib import Path

import pytest

from modules._builtin.meeting_buddy.module import MeetingBuddyModule
from modules._builtin.meeting_buddy.observability import RecordingObserver
from modules._builtin.meeting_buddy.orchestrator import MeetingOrchestrator
from modules._contract import ModuleContext, module_tray_actions, noop_ui_dispatch
from modules.capabilities.continuous_capture import CAPABILITY_ID as CAP_CAPTURE
from modules.capabilities.registry import CapabilityRegistry, CapabilityUnavailableError
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID as CAP_STT,
)
from modules.capabilities.speech_to_text import (
    TranscriptDelta,
    TranscriptDeltaReceived,
)
from modules.registry import all_builtin_modules
from modules.testing.fake_capture import FakeContinuousCapture
from modules.testing.fake_stt import FakeSpeechToText


def _capabilities() -> tuple[CapabilityRegistry, FakeContinuousCapture, FakeSpeechToText]:
    capabilities = CapabilityRegistry()
    capture = FakeContinuousCapture()
    stt = FakeSpeechToText(text_for_chunk=lambda _chunk: "Budget is rond")
    capabilities.register(CAP_CAPTURE, capture, "audio-capture", 1)
    capabilities.register(CAP_STT, stt, "speech-to-text", 1)
    return capabilities, capture, stt


def test_start_wires_capture_and_stt_and_updates_state(tmp_path: Path) -> None:
    capabilities, _capture, _stt = _capabilities()
    observer = RecordingObserver()
    updates = []
    orchestrator = MeetingOrchestrator(
        capabilities=capabilities,
        app_dir=tmp_path,
        observer=observer,
        on_ui_update=updates.append,
    )
    orchestrator.set_agenda("Budget\nPlanning")

    orchestrator.start()

    assert observer.names[0] == "meeting_started"
    assert orchestrator.binding is not None
    assert orchestrator.state.version >= 1
    assert [topic.title for topic in orchestrator.state.topics] == ["Budget", "Planning"]

    delta = TranscriptDelta(
        orchestrator.binding.transcription_session_id,
        1,
        0,
        1000,
        "Budget is rond",
        True,
        0.9,
    )
    orchestrator.on_stt_event(TranscriptDeltaReceived(delta=delta))

    assert orchestrator.state.version >= 2
    assert updates[-1] is orchestrator.state

    orchestrator.stop()

    assert "meeting_stopped" in observer.names
    assert orchestrator.binding is None


def test_start_fails_clearly_without_capture(tmp_path: Path) -> None:
    orchestrator = MeetingOrchestrator(
        capabilities=CapabilityRegistry(),
        app_dir=tmp_path,
        observer=RecordingObserver(),
    )

    with pytest.raises(CapabilityUnavailableError, match="continuous_capture"):
        orchestrator.start()


def test_module_registers_disabled_with_tray_actions(tmp_path: Path) -> None:
    capabilities, _capture, _stt = _capabilities()
    module = MeetingBuddyModule()
    module.on_app_start(
        ModuleContext(
            app_dir=tmp_path,
            ui_dispatch=noop_ui_dispatch,
            capabilities=capabilities,
        )
    )

    assert module.id == "meeting-buddy"
    assert module.default_enabled() is False
    assert [action.id for action in module_tray_actions(module)] == [
        "start_meeting",
        "stop_meeting",
        "prepare_agenda",
    ]
    assert any(item.id == "meeting-buddy" for item in all_builtin_modules())
