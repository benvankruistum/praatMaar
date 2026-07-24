"""Compact Qt Meeting Buddy heads-up display; deliberately has no transcript view."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import i18n
from ui.app import ensure_app
from ui.overlay_flags import apply_hud_window_flags

from .hints import HintType
from .state import Hint, HintStatus, MeetingState, Question, QuestionStatus, Topic, TopicStatus
from .topic_ladder import is_at_least_sequential


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as a stable ``HH:MM:SS`` timer."""
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


_TOPIC_MARK = {
    TopicStatus.OPEN: "○",
    TopicStatus.TREATED: "◐",
    TopicStatus.SEQUENTIAL: "●",
    TopicStatus.CONFIRMED: "✓",
}


def format_topic_line(topic: Topic) -> str:
    """Compact agenda line with ladder mark plus title."""
    return f"{_TOPIC_MARK.get(topic.status, '○')} {topic.title}"


def topic_line_color(topic: Topic) -> str:
    if topic.status == TopicStatus.CONFIRMED:
        return "#8A94A0"
    if is_at_least_sequential(topic.status):
        return "#0A4C86"
    if topic.status == TopicStatus.TREATED:
        return "#0F6CBD"
    return "#1B1F24"


def pick_emphasis(hints: Sequence[Hint]) -> str | None:
    """Return the id of the highest-priority active hint."""
    active = [hint for hint in hints if hint.status == HintStatus.ACTIVE]
    return (
        max(active, key=lambda hint: (hint.priority, hint.confidence, hint.id)).id
        if active
        else None
    )


class _HudWindow(QWidget):
    def closeEvent(self, event: QCloseEvent) -> None:
        self.hide()
        event.ignore()


class MeetingBuddyOverlay:
    """Small always-on-top status and hints window."""

    def __init__(
        self,
        *,
        elapsed_seconds: Callable[[], float],
        on_dismiss: Callable[[str], None],
        on_confirm: Callable[[str], None],
        on_reconnect: Callable[[], None],
        on_stop: Callable[[], None] | None = None,
        parent: Any = None,
    ) -> None:
        ensure_app()
        self._elapsed_seconds = elapsed_seconds
        self._on_dismiss = on_dismiss
        self._on_confirm = on_confirm
        self._on_reconnect = on_reconnect
        self._shown_once = False
        self._capture_status: object = None
        self._pulse_on = False
        self._hint_cards: dict[str, QFrame] = {}

        self.window = _HudWindow(parent if isinstance(parent, QWidget) else None)
        apply_hud_window_flags(self.window)
        self.window.setWindowTitle(i18n.t("modules.meeting_buddy.overlay.title"))
        self.window.setStyleSheet("QWidget { background: #F7F9FB; }")
        self.window.setMinimumWidth(360)

        outer = QVBoxLayout(self.window)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)
        header = QHBoxLayout()
        self._listening_dot = QLabel("●")
        self._listening_dot.setStyleSheet("color: #9AA0A6; font-weight: bold;")
        self._listening = QLabel()
        self._timer_label = QLabel("00:00:00")
        self._timer_label.setStyleSheet("font-family: Consolas; font-weight: bold;")
        header.addWidget(self._listening_dot)
        header.addWidget(self._listening)
        header.addWidget(self._timer_label)
        header.addStretch()
        if on_stop is not None:
            stop = QPushButton(i18n.t("modules.meeting_buddy.overlay.stop"))
            stop.clicked.connect(on_stop)
            header.addWidget(stop)
        minimize = QPushButton(i18n.t("modules.meeting_buddy.overlay.minimize"))
        minimize.clicked.connect(self.minimize)
        header.addWidget(minimize)
        outer.addLayout(header)

        self._recording_label = QLabel()
        self._recording_label.setWordWrap(True)
        self._recording_label.setStyleSheet(
            "background: #FFEBEE; color: #B71C1C; font-weight: 600; padding: 6px;"
        )
        self._recording_label.hide()
        outer.addWidget(self._recording_label)
        self._topics = self._section(outer, "modules.meeting_buddy.overlay.agenda")
        self._summary = self._section(outer, "modules.meeting_buddy.overlay.summary")
        self._summary_body = QLabel()
        self._summary_body.setWordWrap(True)
        self._summary.layout().addWidget(self._summary_body)
        self._questions = self._section(outer, "modules.meeting_buddy.overlay.questions")
        self._hints = QWidget()
        self._hints.setLayout(QVBoxLayout())
        self._hints.layout().setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._hints)
        self._status = QLabel()
        self._status.setStyleSheet("color: #5A6572;")
        outer.addWidget(self._status)
        self._reconnect = QPushButton(i18n.t("modules.meeting_buddy.overlay.reconnect"))
        self._reconnect.clicked.connect(on_reconnect)
        self._reconnect.hide()
        outer.addWidget(self._reconnect)

        self._timer = QTimer(self.window)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    @staticmethod
    def _section(outer: QVBoxLayout, key: str) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        heading = QLabel(i18n.t(key))
        heading.setStyleSheet("color: #5A6572; font-size: 11px; font-weight: 600;")
        layout.addWidget(heading)
        outer.addWidget(section)
        section.hide()
        return section

    def update(
        self,
        state: MeetingState,
        *,
        capture_status: object,
        transcription_status: object,
        loopback_active: bool | None = None,
        loopback_requested: bool = True,
    ) -> None:
        """Render one immutable state snapshot, capped at three active hints."""
        active = [hint for hint in state.emitted_hints if hint.status == HintStatus.ACTIVE]
        active.sort(key=lambda hint: (-hint.priority, -hint.confidence, hint.id))
        visible = active[:3]
        self._render_topics(state.topics)
        self._render_summary(
            state.live_summary, enabled=bool(getattr(state, "live_summary_enabled", False))
        )
        self._render_questions(state.questions)
        self._render_hints(visible, pick_emphasis(visible))
        self._capture_status = capture_status
        self._listening.setText(
            self._listening_text(
                capture_status,
                transcription_status,
                loopback_active=loopback_active,
                loopback_requested=loopback_requested,
            )
        )
        self._update_recording_banner(
            capture_status,
            transcription_status,
            loopback_active=loopback_active,
            loopback_requested=loopback_requested,
        )
        self._update_listening_dot(capture_status, transcription_status)
        self._status.setText(
            "  ·  ".join(
                (
                    self._status_text("capture", capture_status),
                    self._status_text("stt", transcription_status),
                )
            )
        )
        self._reconnect.setVisible(_enum_value(capture_status) == "error")
        self.window.show()
        if not self._shown_once:
            self._shown_once = True
            self._place_top_right()

    def minimize(self) -> None:
        self.window.hide()

    def close(self) -> None:
        self._timer.stop()
        self.window.close()
        self.window.deleteLater()

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _render_topics(self, topics: Sequence[Topic]) -> None:
        layout = self._topics.layout()
        assert isinstance(layout, QVBoxLayout)
        self._clear_layout(layout)
        if not topics:
            self._topics.hide()
            return
        for topic in topics:
            label = QLabel(format_topic_line(topic))
            label.setStyleSheet(f"color: {topic_line_color(topic)};")
            layout.addWidget(label)
        self._topics.show()

    def _render_questions(self, questions: Sequence[Question]) -> None:
        layout = self._questions.layout()
        assert isinstance(layout, QVBoxLayout)
        self._clear_layout(layout)
        open_questions = [
            question for question in questions if question.status == QuestionStatus.OPEN
        ][:5]
        if not open_questions:
            self._questions.hide()
            return
        for question in open_questions:
            label = QLabel(f"? {question.text}")
            label.setWordWrap(True)
            label.setStyleSheet("color: #8A4B08;")
            layout.addWidget(label)
        self._questions.show()

    def _render_summary(self, summary: str, *, enabled: bool = False) -> None:
        if not enabled:
            self._summary.hide()
            return
        text = (summary or "").strip() or i18n.t("modules.meeting_buddy.overlay.summary_waiting")
        self._summary_body.setText(text)
        self._summary_body.setStyleSheet(
            "color: #1B1F24;" if summary.strip() else "color: #6C7C87;"
        )
        self._summary.show()

    def _render_hints(self, hints: Sequence[Hint], emphasis_id: str | None) -> None:
        layout = self._hints.layout()
        assert isinstance(layout, QVBoxLayout)
        self._clear_layout(layout)
        self._hint_cards.clear()
        if not hints:
            empty = QLabel(i18n.t("modules.meeting_buddy.overlay.no_hints"))
            empty.setStyleSheet("color: #6C7C87;")
            layout.addWidget(empty)
            return
        for hint in hints:
            card = QFrame()
            emphasized = hint.id == emphasis_id
            background = "#EAF3FC" if emphasized else "#FFFFFF"
            border_width = 2 if emphasized else 1
            border_color = "#0F6CBD" if emphasized else "#CFD9E0"
            card.setStyleSheet(
                f"QFrame {{ background: {background}; border: {border_width}px solid"
                f" {border_color}; border-radius: 4px; }}"
            )
            card_layout = QVBoxLayout(card)
            message = QLabel(hint.message)
            message.setWordWrap(True)
            if emphasized:
                message.setStyleSheet("font-weight: 600;")
            card_layout.addWidget(message)
            controls = QHBoxLayout()
            controls.addStretch()
            if _enum_value(hint.type) == HintType.CANDIDATE_ACTION_WITHOUT_OWNER.value:
                confirm = QPushButton(i18n.t("modules.meeting_buddy.overlay.confirm"))
                confirm.clicked.connect(
                    lambda _checked=False, hint_id=hint.id: self._on_confirm(hint_id)
                )
                controls.addWidget(confirm)
            dismiss = QPushButton(i18n.t("modules.meeting_buddy.overlay.dismiss"))
            dismiss.clicked.connect(
                lambda _checked=False, hint_id=hint.id: self._on_dismiss(hint_id)
            )
            controls.addWidget(dismiss)
            card_layout.addLayout(controls)
            layout.addWidget(card)
            self._hint_cards[hint.id] = card

    def _tick(self) -> None:
        self._timer_label.setText(format_elapsed(self._elapsed_seconds()))
        if _enum_value(self._capture_status) == "active":
            self._pulse_on = not self._pulse_on
            self._listening_dot.setStyleSheet(
                f"color: {'#E53935' if self._pulse_on else '#FF8A80'}; font-weight: bold;"
            )

    def _update_recording_banner(
        self,
        capture_status: object,
        transcription_status: object,
        *,
        loopback_active: bool | None,
        loopback_requested: bool,
    ) -> None:
        capture = _enum_value(capture_status)
        if capture == "active":
            text = self._active_recording_text(
                delayed=_enum_value(transcription_status) == "delayed",
                loopback_active=loopback_active,
                loopback_requested=loopback_requested,
            )
        elif capture in {"starting", "reconnecting"}:
            text = i18n.t("modules.meeting_buddy.overlay.recording.starting")
        elif capture == "error":
            text = i18n.t("modules.meeting_buddy.overlay.recording.error")
        else:
            self._recording_label.hide()
            return
        self._recording_label.setText(text)
        self._recording_label.show()

    def _update_listening_dot(self, capture_status: object, transcription_status: object) -> None:
        if _enum_value(capture_status) != "active":
            self._listening_dot.setStyleSheet(
                f"color: {self._listening_color(capture_status, transcription_status)}; font-weight: bold;"
            )

    def _place_top_right(self) -> None:
        self.window.adjustSize()
        screen = self.window.screen()
        if screen is not None:
            geometry = screen.availableGeometry()
            self.window.move(geometry.right() - self.window.width() - 24, geometry.top() + 24)

    @staticmethod
    def _status_text(kind: str, status: object) -> str:
        value = _enum_value(status)
        key = f"modules.meeting_buddy.overlay.{kind}.{value}"
        translated = i18n.t(key)
        return f"{i18n.t(f'modules.meeting_buddy.overlay.{kind}')}: {str(value) if translated == key else translated}"

    @staticmethod
    def _active_recording_text(
        *, delayed: bool, loopback_active: bool | None, loopback_requested: bool
    ) -> str:
        if loopback_active is True:
            return i18n.t(
                "modules.meeting_buddy.overlay.recording.active_loopback_delayed"
                if delayed
                else "modules.meeting_buddy.overlay.recording.active_loopback"
            )
        if loopback_requested and loopback_active is False:
            return i18n.t(
                "modules.meeting_buddy.overlay.recording.mic_only_unavailable_delayed"
                if delayed
                else "modules.meeting_buddy.overlay.recording.mic_only_unavailable"
            )
        if not loopback_requested:
            return i18n.t(
                "modules.meeting_buddy.overlay.recording.mic_only_delayed"
                if delayed
                else "modules.meeting_buddy.overlay.recording.mic_only"
            )
        return i18n.t(
            "modules.meeting_buddy.overlay.recording.active_delayed"
            if delayed
            else "modules.meeting_buddy.overlay.recording.active"
        )

    @staticmethod
    def _listening_text(
        capture_status: object,
        transcription_status: object,
        *,
        loopback_active: bool | None = None,
        loopback_requested: bool = True,
    ) -> str:
        capture, stt = _enum_value(capture_status), _enum_value(transcription_status)
        if capture == "error":
            return i18n.t("modules.meeting_buddy.overlay.listening.error")
        if capture in {"starting", "reconnecting"}:
            return i18n.t(
                "modules.meeting_buddy.overlay.listening.reconnecting_loopback"
                if capture == "reconnecting" and loopback_requested
                else "modules.meeting_buddy.overlay.listening.starting"
            )
        if capture == "active" and loopback_active is True:
            return i18n.t(
                "modules.meeting_buddy.overlay.listening.active_loopback_delayed"
                if stt == "delayed"
                else "modules.meeting_buddy.overlay.listening.active_loopback"
            )
        if capture == "active" and loopback_requested and loopback_active is False:
            return i18n.t("modules.meeting_buddy.overlay.listening.mic_only_unavailable")
        if capture == "active" and not loopback_requested:
            return i18n.t(
                "modules.meeting_buddy.overlay.listening.mic_only_delayed"
                if stt == "delayed"
                else "modules.meeting_buddy.overlay.listening.mic_only"
            )
        if capture == "active" and stt == "delayed":
            return i18n.t("modules.meeting_buddy.overlay.listening.delayed")
        if capture == "active":
            return i18n.t("modules.meeting_buddy.overlay.listening.active")
        return i18n.t("modules.meeting_buddy.overlay.listening.idle")

    @staticmethod
    def _listening_color(capture_status: object, transcription_status: object) -> str:
        capture, stt = _enum_value(capture_status), _enum_value(transcription_status)
        if capture == "error":
            return "#E53935"
        if capture in {"starting", "reconnecting"}:
            return "#FFB020"
        if capture == "active" and stt in {"active", "delayed"}:
            return "#43A047"
        return "#9AA0A6"


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)
