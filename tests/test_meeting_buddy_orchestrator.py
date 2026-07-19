from dataclasses import replace
from pathlib import Path

import pytest

from modules._builtin.meeting_buddy import module as meeting_buddy_module
from modules._builtin.meeting_buddy.hints import HintType
from modules._builtin.meeting_buddy.module import MeetingBuddyModule
from modules._builtin.meeting_buddy.observability import RecordingObserver
from modules._builtin.meeting_buddy.orchestrator import MeetingOrchestrator
from modules._builtin.meeting_buddy.state import (
    ActionItem,
    ActionItemStatus,
    Hint,
    HintStatus,
)
from modules._contract import ModuleContext, module_tray_actions, noop_ui_dispatch
from modules.capabilities.continuous_capture import (
    CAPABILITY_ID as CAP_CAPTURE,
)
from modules.capabilities.continuous_capture import (
    CaptureStatus,
    CaptureStatusChanged,
)
from modules.capabilities.registry import CapabilityRegistry, CapabilityUnavailableError
from modules.capabilities.speech_to_text import (
    CAPABILITY_ID as CAP_STT,
)
from modules.capabilities.speech_to_text import (
    TranscriptionStatus,
    TranscriptionStatusChanged,
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
    capabilities, capture, _stt = _capabilities()
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

    capture.emit_seconds(1)

    assert orchestrator.state.version >= 2
    assert updates[-1] is orchestrator.state

    orchestrator.stop()

    assert "meeting_stopped" in observer.names
    assert orchestrator.binding is None


def test_start_failure_cleans_up_started_sessions_and_state(tmp_path: Path) -> None:
    capabilities, capture, stt = _capabilities()

    def fail_ui(_state: object) -> None:
        raise RuntimeError("UI kapot")

    orchestrator = MeetingOrchestrator(
        capabilities=capabilities,
        app_dir=tmp_path,
        observer=RecordingObserver(),
        on_ui_update=fail_ui,
    )

    with pytest.raises(RuntimeError, match="starten mislukt"):
        orchestrator.start()

    assert orchestrator.binding is None
    with pytest.raises(RuntimeError, match="niet gestart"):
        _ = orchestrator.state
    assert all(status.value == "stopped" for status in capture._status.values())
    assert all(status.value == "idle" for status in stt._status.values())


def test_stop_attempts_every_cleanup_step_and_always_clears_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capabilities, capture, stt = _capabilities()
    observer = RecordingObserver()
    ui_updates = []
    orchestrator = MeetingOrchestrator(
        capabilities=capabilities,
        app_dir=tmp_path,
        observer=observer,
        on_ui_update=ui_updates.append,
    )
    orchestrator.start()
    calls = []

    monkeypatch.setattr(
        stt,
        "unsubscribe",
        lambda *_args: (calls.append("unsubscribe_stt"), (_ for _ in ()).throw(RuntimeError())),
    )
    monkeypatch.setattr(
        capture,
        "unsubscribe",
        lambda *_args: (calls.append("unsubscribe_capture"), (_ for _ in ()).throw(RuntimeError())),
    )
    monkeypatch.setattr(
        stt,
        "stop_session",
        lambda *_args: (calls.append("stop_stt"), (_ for _ in ()).throw(RuntimeError())),
    )
    monkeypatch.setattr(
        capture,
        "stop_session",
        lambda *_args: (calls.append("stop_capture"), (_ for _ in ()).throw(RuntimeError())),
    )
    monkeypatch.setattr(
        observer,
        "record",
        lambda _event: (calls.append("log"), (_ for _ in ()).throw(RuntimeError())),
    )
    orchestrator._on_ui_update = lambda _state: (
        calls.append("ui"),
        (_ for _ in ()).throw(RuntimeError()),
    )

    orchestrator.stop()

    assert calls == [
        "unsubscribe_stt",
        "unsubscribe_capture",
        "stop_stt",
        "stop_capture",
        "log",
        "ui",
    ]
    assert orchestrator.binding is None
    with pytest.raises(RuntimeError, match="niet gestart"):
        _ = orchestrator.state


def test_start_fails_clearly_without_capture(tmp_path: Path) -> None:
    orchestrator = MeetingOrchestrator(
        capabilities=CapabilityRegistry(),
        app_dir=tmp_path,
        observer=RecordingObserver(),
    )

    with pytest.raises(CapabilityUnavailableError, match="continuous_capture"):
        orchestrator.start()


def test_overlay_actions_apply_dismiss_and_confirm_proposals(tmp_path: Path) -> None:
    capabilities, _capture, _stt = _capabilities()
    observer = RecordingObserver()
    orchestrator = MeetingOrchestrator(
        capabilities=capabilities,
        app_dir=tmp_path,
        observer=observer,
    )
    orchestrator.start()
    action = ActionItem(id="a1", description="Website controleren")
    dismissible_hint = Hint(
        id="h0",
        type=HintType.TOPIC_NOT_DISCUSSED,
        message="Nog niet besproken",
        priority=1,
        confidence=0.9,
    )
    action_hint = Hint(
        id="h1",
        type=HintType.CANDIDATE_ACTION_WITHOUT_OWNER,
        message="Mogelijk actiepunt",
        priority=2,
        confidence=0.9,
        related_entity_id=action.id,
    )
    orchestrator._state = replace(
        orchestrator.state,
        action_items=(action,),
        emitted_hints=(dismissible_hint, action_hint),
    )

    orchestrator.dismiss_hint("h0")
    orchestrator.confirm_hint("h1")

    assert orchestrator.state.action_items[0].status == ActionItemStatus.CONFIRMED
    assert all(hint.status == HintStatus.DISMISSED for hint in orchestrator.state.emitted_hints)
    assert "action_confirmed" in observer.names


def test_status_events_refresh_ui_and_expose_current_status(tmp_path: Path) -> None:
    capabilities, _capture, _stt = _capabilities()
    updates = []
    orchestrator = MeetingOrchestrator(
        capabilities=capabilities,
        app_dir=tmp_path,
        on_ui_update=updates.append,
    )
    orchestrator.start()
    assert orchestrator.binding is not None
    binding = orchestrator.binding
    previous_updates = len(updates)

    orchestrator.on_capture_status(
        CaptureStatusChanged(binding.capture_session_id, CaptureStatus.ERROR)
    )
    orchestrator.on_stt_event(
        TranscriptionStatusChanged(binding.transcription_session_id, TranscriptionStatus.DELAYED)
    )

    assert len(updates) == previous_updates + 2
    assert orchestrator.capture_status == CaptureStatus.ERROR
    assert orchestrator.transcription_status == TranscriptionStatus.DELAYED


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


def test_module_dispatches_orchestrator_updates_to_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capabilities, _capture, _stt = _capabilities()
    dispatched = []
    overlays = []

    class FakeOverlay:
        def __init__(self, **callbacks: object) -> None:
            self.callbacks = callbacks
            self.updates = []
            overlays.append(self)

        def update(self, state: object, **statuses: object) -> None:
            self.updates.append((state, statuses))

        def close(self) -> None:
            pass

    monkeypatch.setattr(meeting_buddy_module, "MeetingBuddyOverlay", FakeOverlay)
    module = MeetingBuddyModule()
    module.on_app_start(
        ModuleContext(
            app_dir=tmp_path,
            ui_dispatch=dispatched.append,
            capabilities=capabilities,
        )
    )

    module.start_meeting()
    assert len(dispatched) == 1
    dispatched.pop()()

    assert len(overlays) == 1
    assert overlays[0].updates[0][1] == {
        "capture_status": CaptureStatus.ACTIVE,
        "transcription_status": TranscriptionStatus.ACTIVE,
    }
