from modules._builtin.meeting_buddy.hints import HintType
from modules._builtin.meeting_buddy.overlay import format_elapsed, pick_emphasis
from modules._builtin.meeting_buddy.state import Hint, HintStatus


def _hint(hint_id: str, priority: int, *, status: HintStatus = HintStatus.ACTIVE) -> Hint:
    return Hint(
        id=hint_id,
        type=HintType.TOPIC_NOT_DISCUSSED,
        message=hint_id,
        priority=priority,
        confidence=0.8,
        related_entity_id="t1",
        created_at=0,
        expires_at=None,
        cooldown_key="t1",
        status=status,
    )


def test_format_elapsed() -> None:
    assert format_elapsed(1458) == "00:24:18"


def test_format_elapsed_clamps_negative_values() -> None:
    assert format_elapsed(-1) == "00:00:00"


def test_pick_emphasis_is_highest_priority_active_hint() -> None:
    hints = [
        _hint("h1", 1),
        _hint("dismissed", 99, status=HintStatus.DISMISSED),
        _hint("h2", 10),
    ]

    assert pick_emphasis(hints) == "h2"


def test_pick_emphasis_returns_none_without_active_hints() -> None:
    assert pick_emphasis([_hint("h1", 1, status=HintStatus.DISMISSED)]) is None


def test_listening_text_when_capture_active() -> None:
    import i18n
    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay
    from modules.capabilities.continuous_capture import CaptureStatus
    from modules.capabilities.speech_to_text import TranscriptionStatus

    i18n.set_ui_language("nl")
    text = MeetingBuddyOverlay._listening_text(CaptureStatus.ACTIVE, TranscriptionStatus.ACTIVE)
    assert "opname actief" in text.lower()


def test_listening_text_when_loopback_active() -> None:
    import i18n
    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay
    from modules.capabilities.continuous_capture import CaptureStatus
    from modules.capabilities.speech_to_text import TranscriptionStatus

    i18n.set_ui_language("nl")
    text = MeetingBuddyOverlay._listening_text(
        CaptureStatus.ACTIVE,
        TranscriptionStatus.ACTIVE,
        loopback_active=True,
        loopback_requested=True,
    )
    assert "meetinggeluid" in text.lower()


def test_listening_text_when_loopback_unavailable() -> None:
    import i18n
    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay
    from modules.capabilities.continuous_capture import CaptureStatus
    from modules.capabilities.speech_to_text import TranscriptionStatus

    i18n.set_ui_language("nl")
    text = MeetingBuddyOverlay._listening_text(
        CaptureStatus.ACTIVE,
        TranscriptionStatus.ACTIVE,
        loopback_active=False,
        loopback_requested=True,
    )
    assert "alleen microfoon" in text.lower()
    assert "meetinggeluid niet beschikbaar" in text.lower()


def test_listening_text_when_mic_only_mode_selected() -> None:
    import i18n
    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay
    from modules.capabilities.continuous_capture import CaptureStatus
    from modules.capabilities.speech_to_text import TranscriptionStatus

    i18n.set_ui_language("nl")
    text = MeetingBuddyOverlay._listening_text(
        CaptureStatus.ACTIVE,
        TranscriptionStatus.ACTIVE,
        loopback_active=False,
        loopback_requested=False,
    )
    assert text == "Opname: alleen microfoon"
    assert "niet beschikbaar" not in text


def test_listening_text_when_reconnecting_loopback() -> None:
    import i18n
    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay
    from modules.capabilities.continuous_capture import CaptureStatus
    from modules.capabilities.speech_to_text import TranscriptionStatus

    i18n.set_ui_language("nl")
    text = MeetingBuddyOverlay._listening_text(
        CaptureStatus.RECONNECTING,
        TranscriptionStatus.ACTIVE,
        loopback_requested=True,
    )
    assert "meetinggeluid" in text.lower()
