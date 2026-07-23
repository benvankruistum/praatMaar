import pytest

from modules._builtin.meeting_buddy.config import MeetingBuddyConfig
from modules._builtin.meeting_buddy.heuristics import HeuristicsEngine
from modules._builtin.meeting_buddy.hint_coordinator import _hints_equivalent, _merge_visible_hints
from modules._builtin.meeting_buddy.hints import HintType
from modules._builtin.meeting_buddy.state import Hint, HintStatus, MeetingState


def test_heuristics_ignore_too_short_question_fragment() -> None:
    state = MeetingState.empty("m1")
    from modules.capabilities.speech_to_text import TranscriptDelta

    delta = TranscriptDelta("t1", 1, 0, 1000, "De vraag is hoe", True, 0.9)
    proposals = HeuristicsEngine().proposals_for(
        delta,
        state,
        MeetingBuddyConfig.defaults(),
        now_s=10.0,
    )

    assert not any(proposal.type == "add_question" for proposal in proposals)


def test_merge_visible_hints_keeps_active_during_cooldown_gap() -> None:
    existing = Hint(
        id="question_open:q1",
        type=HintType.QUESTION_OPEN,
        message="Deze vraag staat nog open: «Wanneer?»",
        priority=3,
        confidence=0.9,
        related_entity_id="q1",
        created_at=0.0,
        expires_at=100.0,
        cooldown_key="question_open:q1",
        status=HintStatus.ACTIVE,
    )
    merged = _merge_visible_hints((existing,), [], now_s=5.0)
    assert merged == [existing]


def test_hints_equivalent_compares_message_and_status() -> None:
    hint = Hint(
        id="topic_not_discussed:t1",
        type=HintType.TOPIC_NOT_DISCUSSED,
        message="Agendapunt nog niet besproken: «Budget»",
        priority=1,
        confidence=0.9,
        related_entity_id="t1",
        created_at=0.0,
        expires_at=None,
        cooldown_key="topic_not_discussed:t1",
        status=HintStatus.ACTIVE,
    )
    assert _hints_equivalent((hint,), [hint])


def test_meeting_start_forces_meeting_pill_mode_via_begin_meeting(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After start, explicitly sync pill so mode is meeting (not leftover ↔ toggle)."""

    from indicator import RecordingState
    from modules._builtin.meeting_buddy.module import MeetingBuddyModule
    from modules._contract import ModuleContext, noop_ui_dispatch
    from modules.capabilities.continuous_capture import CAPABILITY_ID as CAP_CAPTURE
    from modules.capabilities.continuous_capture import CaptureStatus
    from modules.capabilities.registry import CapabilityRegistry
    from modules.capabilities.speech_to_text import CAPABILITY_ID as CAP_STT
    from modules.testing.fake_capture import FakeContinuousCapture
    from modules.testing.fake_stt import FakeSpeechToText

    notified: list[tuple[RecordingState, str]] = []

    def _notify(state: RecordingState, mode: str = "toggle") -> None:
        notified.append((state, mode))

    monkeypatch.setattr("modules._builtin.meeting_buddy.module.notify_state", _notify)
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda *_a, **_k: None)
    monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "modules._builtin.meeting_buddy.module.MeetingBuddyModule._show_overlay_update",
        lambda *a, **k: None,
    )

    capabilities = CapabilityRegistry()
    capture = FakeContinuousCapture()
    stt = FakeSpeechToText(text_for_chunk=lambda _chunk: "")
    capabilities.register(CAP_CAPTURE, capture, "audio-capture", 1)
    capabilities.register(CAP_STT, stt, "speech-to-text", 1)

    module = MeetingBuddyModule()
    module.on_app_start(
        ModuleContext(app_dir=tmp_path, ui_dispatch=noop_ui_dispatch, capabilities=capabilities)
    )
    module.set_agenda("Opening")

    original_start = module._require_orchestrator().start

    def start_then_mark_active() -> None:
        original_start()
        module._require_orchestrator()._sessions._capture_status = CaptureStatus.ACTIVE

    monkeypatch.setattr(module._require_orchestrator(), "start", start_then_mark_active)
    try:
        module._begin_meeting()
        assert notified[-1] == (RecordingState.RECORDING, "meeting")
    finally:
        module.stop_meeting()


def test_meeting_capture_active_shows_recording_pill(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from indicator import RecordingState
    from modules._builtin.meeting_buddy.module import MeetingBuddyModule
    from modules._contract import ModuleContext, noop_ui_dispatch
    from modules.capabilities.continuous_capture import CAPABILITY_ID as CAP_CAPTURE
    from modules.capabilities.registry import CapabilityRegistry
    from modules.capabilities.speech_to_text import CAPABILITY_ID as CAP_STT
    from modules.testing.fake_capture import FakeContinuousCapture
    from modules.testing.fake_stt import FakeSpeechToText

    notified: list[tuple[RecordingState, str]] = []

    def _notify(state: RecordingState, mode: str = "toggle") -> None:
        notified.append((state, mode))

    monkeypatch.setattr("modules._builtin.meeting_buddy.module.notify_state", _notify)
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda *_a, **_k: None)
    monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "modules._builtin.meeting_buddy.module.MeetingBuddyModule._show_overlay_update",
        lambda *a, **k: None,
    )

    capabilities = CapabilityRegistry()
    capture = FakeContinuousCapture()
    stt = FakeSpeechToText(text_for_chunk=lambda _chunk: "")
    capabilities.register(CAP_CAPTURE, capture, "audio-capture", 1)
    capabilities.register(CAP_STT, stt, "speech-to-text", 1)

    module = MeetingBuddyModule()
    module.on_app_start(
        ModuleContext(app_dir=tmp_path, ui_dispatch=noop_ui_dispatch, capabilities=capabilities)
    )
    try:
        module._require_orchestrator().start()
        assert notified[-1] == (RecordingState.RECORDING, "meeting")
        module.stop_meeting()
        assert notified[-1] == (RecordingState.IDLE, "meeting")
    finally:
        if module._require_orchestrator().binding is not None:
            module.stop_meeting()


def test_meeting_capture_error_shows_error_pill(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from indicator import RecordingState
    from modules._builtin.meeting_buddy.module import MeetingBuddyModule
    from modules._contract import ModuleContext, noop_ui_dispatch
    from modules.capabilities.continuous_capture import CAPABILITY_ID as CAP_CAPTURE
    from modules.capabilities.continuous_capture import CaptureStatus, CaptureStatusChanged
    from modules.capabilities.registry import CapabilityRegistry
    from modules.capabilities.speech_to_text import CAPABILITY_ID as CAP_STT
    from modules.testing.fake_capture import FakeContinuousCapture
    from modules.testing.fake_stt import FakeSpeechToText

    notified: list[tuple[RecordingState, str]] = []

    def _notify(state: RecordingState, mode: str = "toggle") -> None:
        notified.append((state, mode))

    monkeypatch.setattr("modules._builtin.meeting_buddy.module.notify_state", _notify)
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda *_a, **_k: None)
    monkeypatch.setattr("tkinter.messagebox.showinfo", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "modules._builtin.meeting_buddy.module.MeetingBuddyModule._show_overlay_update",
        lambda *a, **k: None,
    )

    capabilities = CapabilityRegistry()
    capture = FakeContinuousCapture()
    stt = FakeSpeechToText(text_for_chunk=lambda _chunk: "")
    capabilities.register(CAP_CAPTURE, capture, "audio-capture", 1)
    capabilities.register(CAP_STT, stt, "speech-to-text", 1)

    module = MeetingBuddyModule()
    module.on_app_start(
        ModuleContext(app_dir=tmp_path, ui_dispatch=noop_ui_dispatch, capabilities=capabilities)
    )
    orchestrator = module._require_orchestrator()
    try:
        orchestrator.start()
        binding = orchestrator.binding
        assert binding is not None

        capture._emit(
            binding.capture_session_id,
            CaptureStatusChanged(binding.capture_session_id, CaptureStatus.ERROR),
        )

        assert notified[-1] == (RecordingState.ERROR, "meeting")
    finally:
        module.stop_meeting()
