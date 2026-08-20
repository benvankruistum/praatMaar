from modules._builtin.meeting_buddy.hints import HintType
from modules._builtin.meeting_buddy.overlay import format_elapsed, pick_emphasis, summary_points
from modules._builtin.meeting_buddy.state import Hint, HintStatus


def _dispose_overlay(app: object, overlay: object) -> None:
    """Close the HUD and flush Qt DeferredDelete before the next test.

    Windows CI has seen access violations during GC when a previous overlay
    (live QTimers / deleteLater'd widgets) overlapped the next __init__.
    """
    from PySide6.QtCore import QCoreApplication, QEvent

    overlay.close()  # type: ignore[attr-defined]
    app.processEvents()  # type: ignore[attr-defined]
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()  # type: ignore[attr-defined]


def test_summary_points_splits_lines_and_strips_bullets() -> None:
    assert summary_points("- one\n* two\n3. three") == ["one", "two", "three"]


def test_summary_points_caps_at_five() -> None:
    assert summary_points("a\nb\nc\nd\ne\nf") == ["a", "b", "c", "d", "e"]


def test_summary_points_splits_paragraph_into_sentences() -> None:
    points = summary_points(
        "First thing. Second thing. Third thing. Fourth thing. Fifth thing. Sixth thing."
    )
    assert points == [
        "First thing.",
        "Second thing.",
        "Third thing.",
        "Fourth thing.",
        "Fifth thing.",
    ]


def test_summary_points_empty() -> None:
    assert summary_points("") == []
    assert summary_points("   ") == []


def test_summary_points_strips_bullet_on_single_line() -> None:
    assert summary_points("- Only point") == ["Only point"]


def test_overlay_rerender_does_not_accumulate_rows() -> None:
    # Regression: _render_topics/_render_questions add rows via addLayout; the
    # clear step must free those nested widgets so repeated update() calls don't
    # stack stale dot+label widgets.
    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay, _StatusDot
    from modules._builtin.meeting_buddy.state import MeetingState, Topic, TopicStatus
    from ui.app import ensure_app

    app = ensure_app([])
    topics = (
        Topic("1", "A", TopicStatus.OPEN),
        Topic("2", "B", TopicStatus.SEQUENTIAL),
        Topic("3", "C", TopicStatus.CONFIRMED),
    )
    state = MeetingState("s", 1, topics, (), (), (), ())
    overlay = MeetingBuddyOverlay(
        elapsed_seconds=lambda: 0.0,
        on_dismiss=lambda _i: None,
        on_confirm=lambda _i: None,
        on_reconnect=lambda: None,
    )
    try:
        for _ in range(3):
            overlay.update(state, capture_status="active", transcription_status="active")
        # The running event loop frees deleteLater()'d widgets continuously; flush
        # the DeferredDelete queue here so the test observes the same result.
        from PySide6.QtCore import QCoreApplication, QEvent

        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert len(overlay._topics.findChildren(_StatusDot)) == len(topics)
    finally:
        _dispose_overlay(app, overlay)


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


def test_overlay_is_a_non_activating_qt_hud() -> None:
    from PySide6.QtCore import Qt

    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay
    from ui.app import ensure_app

    app = ensure_app([])
    overlay = MeetingBuddyOverlay(
        elapsed_seconds=lambda: 0,
        on_dismiss=lambda _hint_id: None,
        on_confirm=lambda _hint_id: None,
        on_reconnect=lambda: None,
    )
    try:
        flags = overlay.window.windowFlags()
        assert flags & Qt.WindowType.Tool
        assert flags & Qt.WindowType.WindowStaysOnTopHint
        assert flags & Qt.WindowType.WindowDoesNotAcceptFocus
    finally:
        _dispose_overlay(app, overlay)


def _drag_mouse(widget: object, local: object, delta: object) -> None:
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    assert isinstance(local, QPoint) and isinstance(delta, QPoint)
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(local),
        QPointF(widget.mapToGlobal(local)),  # type: ignore[attr-defined]
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(press)  # type: ignore[attr-defined]
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(local + delta),
        QPointF(widget.mapToGlobal(local) + delta),  # type: ignore[attr-defined]
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseMoveEvent(move)  # type: ignore[attr-defined]


def test_overlay_shows_source_levels_when_capture_active() -> None:
    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay, _SourceWaveforms
    from modules._builtin.meeting_buddy.state import MeetingState
    from ui.app import ensure_app

    app = ensure_app([])
    overlay = MeetingBuddyOverlay(
        elapsed_seconds=lambda: 0.0,
        on_dismiss=lambda _i: None,
        on_confirm=lambda _i: None,
        on_reconnect=lambda: None,
    )
    try:
        overlay.update(
            MeetingState("s", 1, (), (), (), (), ()),
            capture_status="active",
            transcription_status="active",
            loopback_active=True,
            loopback_requested=True,
        )
        app.processEvents()
        host = overlay.window.findChild(_SourceWaveforms)
        assert host is not None
        assert host.isVisible()
        assert not host._warn.isVisible()
    finally:
        _dispose_overlay(app, overlay)


def test_overlay_meeting_levels_warn_when_loopback_unavailable() -> None:
    import i18n
    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay, _SourceWaveforms
    from modules._builtin.meeting_buddy.state import MeetingState
    from ui.app import ensure_app

    i18n.set_ui_language("nl")
    app = ensure_app([])
    overlay = MeetingBuddyOverlay(
        elapsed_seconds=lambda: 0.0,
        on_dismiss=lambda _i: None,
        on_confirm=lambda _i: None,
        on_reconnect=lambda: None,
    )
    try:
        overlay.update(
            MeetingState("s", 1, (), (), (), (), ()),
            capture_status="active",
            transcription_status="active",
            loopback_active=False,
            loopback_requested=True,
        )
        app.processEvents()
        host = overlay.window.findChild(_SourceWaveforms)
        assert host is not None
        assert host.isVisible()
        assert host._warn.isVisible()
        assert "niet beschikbaar" in host._warn.text().lower()
    finally:
        _dispose_overlay(app, overlay)


def test_overlay_header_drag_moves_window() -> None:
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QFrame

    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay
    from modules._builtin.meeting_buddy.state import MeetingState
    from ui.app import ensure_app

    app = ensure_app([])
    overlay = MeetingBuddyOverlay(
        elapsed_seconds=lambda: 0.0,
        on_dismiss=lambda _i: None,
        on_confirm=lambda _i: None,
        on_reconnect=lambda: None,
    )
    try:
        overlay.update(
            MeetingState("s", 1, (), (), (), (), ()),
            capture_status="active",
            transcription_status="active",
        )
        app.processEvents()
        header = overlay.window.findChild(QFrame, "mbHeader")
        assert header is not None
        start = overlay.window.pos()
        delta = QPoint(40, 25)
        _drag_mouse(header, QPoint(20, 10), delta)
        app.processEvents()
        assert overlay.window.pos() == start + delta
    finally:
        _dispose_overlay(app, overlay)


def test_overlay_minimize_button_does_not_start_drag() -> None:
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QFrame, QPushButton

    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay
    from modules._builtin.meeting_buddy.state import MeetingState
    from ui.app import ensure_app

    app = ensure_app([])
    overlay = MeetingBuddyOverlay(
        elapsed_seconds=lambda: 0.0,
        on_dismiss=lambda _i: None,
        on_confirm=lambda _i: None,
        on_reconnect=lambda: None,
    )
    try:
        overlay.update(
            MeetingState("s", 1, (), (), (), (), ()),
            capture_status="active",
            transcription_status="active",
        )
        app.processEvents()
        header = overlay.window.findChild(QFrame, "mbHeader")
        assert header is not None
        minimize = next(btn for btn in header.findChildren(QPushButton) if btn.text() == "—")
        start = overlay.window.pos()
        local = QPoint(5, 5)
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(local),
            QPointF(minimize.mapToGlobal(local)),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        minimize.mousePressEvent(press)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(local + QPoint(40, 25)),
            QPointF(minimize.mapToGlobal(local) + QPoint(40, 25)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        header.mouseMoveEvent(move)
        app.processEvents()
        assert overlay.window.pos() == start
    finally:
        _dispose_overlay(app, overlay)


def test_mini_pill_drag_moves_window() -> None:
    from PySide6.QtCore import QPoint

    from modules._builtin.meeting_buddy.overlay import MeetingBuddyOverlay
    from modules._builtin.meeting_buddy.state import MeetingState
    from ui.app import ensure_app

    app = ensure_app([])
    overlay = MeetingBuddyOverlay(
        elapsed_seconds=lambda: 0.0,
        on_dismiss=lambda _i: None,
        on_confirm=lambda _i: None,
        on_reconnect=lambda: None,
    )
    try:
        overlay.update(
            MeetingState("s", 1, (), (), (), (), ()),
            capture_status="active",
            transcription_status="active",
        )
        app.processEvents()
        overlay.minimize()
        app.processEvents()
        mini = overlay._mini
        assert mini is not None and mini.isVisible()
        start = mini.pos()
        delta = QPoint(30, 15)
        _drag_mouse(mini, QPoint(40, 20), delta)
        app.processEvents()
        assert mini.pos() == start + delta
    finally:
        _dispose_overlay(app, overlay)


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
